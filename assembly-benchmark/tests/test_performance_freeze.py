"""Report snapshots admit only source-bound, terminal performance records."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import digest, load, save
from scripts import freeze_performance


class PerformanceFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.batch = self.root / 'runs/example'
        self.identifier = '000_GCF_000000001.1'
        selection = {'datasets':[{'id':self.identifier}]}
        save(self.root/'selection.json', selection); save(self.batch/'selection.json', selection)
        tools = ['flye','raven','plassembler','miniasm-plus']
        self.path = self.root/'performance/snapshot.json'
        save(self.path, {'schema_version':1,'track':'broad-performance','selection':'selection.json',
            'tools':tools,'dataset_count':1,'expected_executions':4,'results':[]})
        execution = self.batch/'results'/self.identifier/'flye/execution.json'; save(execution, {'status':'pass'})
        rows = [{'dataset_id':self.identifier,'tool':t,'status':'pending','genome_outcome':'pending'} for t in tools]
        rows[0].update(status='complete',genome_outcome='fully_complete',
            execution_path=str(execution.relative_to(self.root)),provenance={'execution_sha256':digest(execution)})
        self.source = self.batch/'performance-results.json'; save(self.source, {'batch_id':'example','results':rows})
        self.state = self.root/'evidence/broad-performance-v1/status.json'
        save(self.state, {'batch_id':'example','status':'running','jobs':{},
            'result_path':str(self.source.relative_to(self.root)), 'selection_sha256':digest(self.batch/'selection.json')})

    def test_pending_slots_are_excluded_and_terminal_records_are_retained(self):
        with patch.object(freeze_performance, 'ROOT', self.root):result = freeze_performance.freeze()
        self.assertEqual(result['recorded_results'], 1)
        self.assertEqual(load(self.path)['results'][0]['tool'], 'flye')

    def test_changed_execution_does_not_replace_snapshot(self):
        original = self.path.read_bytes()
        execution = self.batch/'results'/self.identifier/'flye/execution.json'; execution.write_text('changed')
        with patch.object(freeze_performance, 'ROOT', self.root), self.assertRaisesRegex(ValueError,'bind'):
            freeze_performance.freeze()
        self.assertEqual(self.path.read_bytes(), original)

    def test_input_binding_error_blocks_freeze(self):
        state = load(self.state); state['input_binding_errors'] = ['mismatch']; save(self.state,state)
        with patch.object(freeze_performance, 'ROOT', self.root), self.assertRaisesRegex(ValueError,'bindings'):
            freeze_performance.freeze()

    def test_stale_complete_status_cannot_release_pending_slots(self):
        original = self.path.read_bytes()
        state = load(self.state); state['status'] = 'complete'; save(self.state, state)
        with patch.object(freeze_performance, 'ROOT', self.root), self.assertRaisesRegex(ValueError, 'Complete release'):
            freeze_performance.freeze()
        self.assertEqual(self.path.read_bytes(), original)
