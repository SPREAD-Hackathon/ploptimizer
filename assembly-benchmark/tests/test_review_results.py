"""Regression checks for audit denominators and the circular-origin explanation."""

import importlib.util
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import ROOT, save

spec = importlib.util.spec_from_file_location('review_results', ROOT / 'scripts/review_results.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewResultsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.cache').mkdir(exist_ok=True)

    def test_only_submitted_tasks_count_and_diagnostic_errors_do_not_change_strict_scores(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as temporary:
            root = Path(temporary)
            batch = root / 'runs/test'
            save(batch / 'tasks.json', {'assemble': [{'scenario': 'submitted', 'tool': 'raven'}]})
            save(root / 'published/test.json', {'results': [
                {'scenario_id': 'submitted', 'tool': 'raven', 'status': 'pass'},
                {'scenario_id': 'planned', 'tool': 'raven', 'status': 'not_run'}]})
            directory = batch / 'results/submitted/raven'
            save(directory / 'execution.json', {'status': 'fail', 'evaluation': {'status': 'fail'}})
            save(directory / 'diagnostics.json', {'status': 'error', 'error': 'mapper failed'})
            with patch.object(review, 'ROOT', root):
                result = review.submitted_rows('test')
            self.assertEqual(result['submitted_executions'], 1)
            self.assertEqual(result['status_counts'], {'fail': 1})
            self.assertEqual(result['completed_diagnostics'], 0)
            self.assertEqual(result['executions'][0]['published_status'], 'pass')

    def test_circular_suffix_can_be_present_despite_mapper_omission(self):
        rng = random.Random(293)
        reference = ''.join(rng.choice('ACGT') for _ in range(5360))
        query = reference[155:3261] + reference[3266:] + reference[:155]
        result = review.check_pilot_sequences({'query': query, 'reference': reference})
        self.assertTrue(result['circular_tail_155bp_matches_reference_origin'])
        self.assertTrue(result['query_equals_reference_rotation_with_5bp_deletion'])
        self.assertEqual(result['reference_length'] - result['query_length'], 5)
        altered = ('A' if query[0] != 'A' else 'C') + query[1:]
        self.assertFalse(review.check_pilot_sequences({'query': altered, 'reference': reference})['query_equals_reference_rotation_with_5bp_deletion'])

    def test_unknown_batch_is_not_silently_an_empty_success(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as temporary:
            with patch.object(review, 'ROOT', Path(temporary)):
                with self.assertRaises(ValueError):
                    review.submitted_rows('unknown')
