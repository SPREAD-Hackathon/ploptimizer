import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import finish_batch_evidence as worker


class FinishBatchEvidenceTests(unittest.TestCase):
    def test_nucmer_exit_codes_control_completion_without_changing_scores(self):
        for returncode, expected_status in [(0,'complete'),(1,'needs_review')]:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                batch = root / 'runs/example'
                execution = batch / 'results/case/tool/execution.json'
                execution.parent.mkdir(parents=True)
                execution.write_text('{"status":"pass"}')
                (batch / 'config.json').write_text('{}')
                (batch / 'tasks.json').write_text('{"assemble":[{}]}')
                original = execution.read_bytes()
                graph = {'executions':[{'artifact':{'status':'available'}}]}
                with patch.multiple(worker, ROOT=root,
                     batch_directory=lambda identifier:batch,
                     run_batch=lambda path:{'complete':1},
                     collect_selected=lambda *args:graph,
                     write_sidecars=lambda *args:None,
                     collect_lengths=lambda path:1,
                     collect_identities=lambda path:{'inventories':1},
                     publish=lambda *args,**kwargs:{'results':[{'status':'pass'}]},
                     comparison_plan=lambda *args:{'tasks':[{}]},
                     run_task=lambda *args:returncode):
                    result = worker.finish('example')
                self.assertEqual(result['status'],expected_status)
                self.assertEqual(result['coordinate_comparisons'],{'complete' if returncode == 0 else 'error':1})
                self.assertEqual(execution.read_bytes(),original)
                self.assertEqual(json.loads((batch / 'evidence_status.json').read_text())['status'],expected_status)
