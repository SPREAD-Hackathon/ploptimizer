import unittest
import copy
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from pipeline.base_review import circular_equivalence, reverse_complement, review_gapfree_pair
from pipeline.base_review_records import attach_base_review
from pipeline.common import digest


class BaseReviewTests(unittest.TestCase):
    def setUp(self):
        self.reference = 'AACCGGTTAACC'
        self.query = 'GATTAACCTACC'
        self.paf = (b'q\t12\t0\t8\t+\tr\t12\t4\t12\t7\t8\t60\tNM:i:1\tcg:Z:8M\n'
                    b'q\t12\t8\t12\t+\tr\t12\t0\t4\t3\t4\t60\tNM:i:1\tcg:Z:4M\n')

    def test_direct_positions_across_circular_origin(self):
        result = review_gapfree_pair({'r':self.reference}, {'q':self.query}, self.paf)
        events = result['events']
        self.assertEqual([(e['reference_position_1based'],e['query_position_1based'],e['reference_base'],e['output_base_reference_forward']) for e in events],
                         [(1,9,'A','T'),(6,2,'G','A')])

    def test_reverse_strand_positions_and_bases_remain_reference_forward(self):
        paf = (b'q\t12\t0\t4\t-\tr\t12\t0\t4\t3\t4\t60\tNM:i:1\tcg:Z:4M\n'
               b'q\t12\t4\t12\t-\tr\t12\t4\t12\t7\t8\t60\tNM:i:1\tcg:Z:8M\n')
        result = review_gapfree_pair({'r':self.reference}, {'q':reverse_complement(self.query)}, paf)
        self.assertEqual([(e['reference_position_1based'],e['query_position_1based'],e['output_base_reference_forward']) for e in result['events']],
                         [(1,4,'T'),(6,11,'A')])

    def test_inconsistent_saved_counts_and_missing_spans_are_rejected(self):
        for paf in [self.paf.replace(b'NM:i:1',b'NM:i:0'),self.paf.splitlines()[0]]:
            with self.assertRaises(ValueError):
                review_gapfree_pair({'r':self.reference}, {'q':self.query}, paf)

    def test_circular_equivalence_does_not_normalise_a_substitution(self):
        self.assertIsNotNone(circular_equivalence(self.reference, self.reference[4:] + self.reference[:4]))
        self.assertIsNotNone(circular_equivalence(self.reference, reverse_complement(self.reference)))
        self.assertIsNone(circular_equivalence(self.reference, self.query))

    def test_export_requires_same_execution_paf_spans_and_event_count(self):
        review = review_gapfree_pair({'r':self.reference}, {'q':self.query}, self.paf)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / 'reviews/bases'
            notes.mkdir(parents=True)
            execution = root / 'artifacts/b/results/example/tool/execution.json'
            execution.parent.mkdir(parents=True)
            execution.write_text('{}')
            record = {'scenario_id':'example','tool':'tool','status':'fail','assembly_sha256':'a','truth_sha256':'t'}
            review.update(batch_id='b',scenario_id='example',tool='tool',strict_status='fail',status='verified',
                          hashes={'assembly_sha256':'a','truth_sha256':'t','paf_sha256':'p','execution_sha256':digest(execution)})
            (notes / 'review.json').write_text(json.dumps(review))
            summary = {'evidence_kind':'saved_alignment_counts','source_sha256':'p','facts':[{'label':'Base mismatches','value':2}]}
            plot = {'alignments':review['alignment_records']}
            with patch('pipeline.base_review_records.ROOT',root):
                attached = copy.deepcopy(summary)
                attach_base_review(attached,record,'b',root / 'artifacts',plot)
                self.assertEqual(attached['base_changes_status'],'recorded')
                self.assertEqual(len(attached['events']),2)
                wrong = copy.deepcopy(plot)
                wrong['alignments'][0]['mapq'] = 0
                rejected = copy.deepcopy(summary)
                attach_base_review(rejected,record,'b',root / 'artifacts',wrong)
                self.assertNotIn('events',rejected)
                execution.write_text('{"changed":true}')
                attach_base_review(rejected,record,'b',root / 'artifacts',plot)
                self.assertNotIn('events',rejected)
