"""Scheduler receipts use the actual element ID and require terminal evidence."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import load, save
from pipeline.performance import worker


class SchedulerReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.batch = Path(self.temp.name) / 'batch'
        self.execution = self.batch / 'results/example/flye/execution.json'
        save(self.execution, {'status': 'running', 'slurm_job_id': '34524149',
                              'slurm_array_task_id': '24'})

    def test_element_id_is_not_combined_with_array_index(self):
        with patch.object(worker, 'configuration', return_value=({}, {}, [{'id': 'example'}])), \
                patch('subprocess.check_output', return_value='34524149|OUT_OF_MEMORY|00:02:00|0:125\n') as accounting, \
                patch('pipeline.performance.assessment.assess', return_value={}) as assess:
            worker.assess_result(self.batch, 0, 'flye')
        self.assertEqual(accounting.call_args.args[0][2], '34524149')
        self.assertIn('--format=JobIDRaw,State,Elapsed,ExitCode', accounting.call_args.args[0])
        self.assertEqual(load(self.execution)['scheduler_state'], 'OUT_OF_MEMORY')
        self.assertEqual(load(self.execution)['status'], 'error')
        assess.assert_called_once()

    def test_nonterminal_scheduler_does_not_finalise_execution(self):
        original = self.execution.read_bytes()
        with patch.object(worker, 'configuration', return_value=({}, {}, [{'id': 'example'}])), \
                patch('subprocess.check_output', return_value='34524149|RUNNING|00:02:00|0:0\n'), \
                patch('pipeline.performance.assessment.assess') as assess, \
                self.assertRaisesRegex(ValueError, 'terminal scheduler'):
            worker.assess_result(self.batch, 0, 'flye')
        self.assertEqual(self.execution.read_bytes(), original)
        assess.assert_not_called()

    def test_missing_execution_does_not_create_a_failure_before_assembly(self):
        self.execution.unlink()
        with patch.object(worker, 'configuration', return_value=({}, {}, [{'id': 'example'}])), \
                self.assertRaisesRegex(ValueError, 'No execution record'):
            worker.assess_result(self.batch, 0, 'flye')
        self.assertFalse(self.execution.exists())
