"""Metadata repair preserves original attempts and never runs sequence analysis."""
import tempfile
import unittest
from pathlib import Path
from pipeline.common import digest, load, save
from scripts.reconcile_performance_failures import reconcile


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.batch = Path(self.temp.name) / 'batch'
        self.case = {'id': 'example', 'fingerprint': 'frozen'}
        save(self.batch / 'selection.json', {'fixed': True})
        save(self.batch / 'submission.json', {'selection_sha256': digest(self.batch / 'selection.json'),
             'reported_tools': ['flye'], 'jobs': {'assemble-flye': '100'}})
        save(self.batch / 'cases.json', [self.case])
        save(self.batch / 'cases/example/input.json', {'status': 'valid', 'case': self.case,
             'reads_sha256': 'a' * 64, 'truth_sha256': 'b' * 64})
        self.execution = self.batch / 'results/example/flye/execution.json'
        save(self.execution, {'tool': 'flye', 'scenario_id': 'example', 'scenario_fingerprint': 'frozen',
             'status': 'timeout', 'reads_sha256': 'a' * 64, 'truth_sha256': 'b' * 64})
        (self.batch / 'accounting.tsv').write_text('100_0|TIMEOUT|04:00:00|0:15|\n')

    def test_recovers_timeout_without_sequence_files_and_preserves_attempt(self):
        original = self.execution.read_bytes()
        rows = reconcile(self.batch)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['outcome'], 'did_not_complete')
        self.assertEqual(self.execution.read_bytes(), original)
        result = load(self.execution.with_name('performance.json'))
        self.assertEqual(result['replicons'], [])
        self.assertEqual(result['provenance']['execution_sha256'], digest(self.execution))
        self.assertEqual(reconcile(self.batch), [])

    def test_nonterminal_scheduler_blocks_repair(self):
        (self.batch / 'accounting.tsv').write_text('100_0|RUNNING|00:00:10|0:0|\n')
        with self.assertRaisesRegex(ValueError, 'terminal scheduler'):
            reconcile(self.batch)
        self.assertFalse(self.execution.with_name('performance.json').exists())

    def test_completed_sequence_outcome_is_not_reassessed(self):
        record = load(self.execution); record['status'] = 'pass'; save(self.execution, record)
        self.assertEqual(reconcile(self.batch), [])
        self.assertFalse(self.execution.with_name('performance.json').exists())
