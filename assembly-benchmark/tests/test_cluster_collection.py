"""Scheduler accounting must not outrun the output files being collected."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.cluster import collect
from pipeline.common import ROOT, load, save


class ClusterCollectionTests(unittest.TestCase):
    def test_scheduler_is_sampled_before_output_copy_and_includes_diagnostic_jobs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as directory:
            batch = Path(directory)
            save(batch/'submission.json', {'cluster':{'host':'test-host','remote_root':'/tmp/assembly-benchmark'}, 'jobs':{'assemble':'100'}})
            save(batch/'diagnostic_submission.json', {'job_id':'200'})
            save(batch/'diagnostic_review_submission.json', {'job_id':'300'})
            events = []
            def scheduler(host, argv):
                events.append(('scheduler', argv))
                return '100|RUNNING|0:0|00:01|'
            def external(argv, **kwargs):
                events.append((argv[0], argv))
                return SimpleNamespace(returncode=0)
            with patch('pipeline.cluster.ssh', side_effect=scheduler), patch('pipeline.cluster.subprocess.run', side_effect=external):
                collect(batch)
            self.assertEqual(events[0][0], 'scheduler')
            self.assertIn('100,200,300', events[0][1])
            self.assertTrue(any(kind == 'rsync' for kind, _ in events))
            self.assertIn('RUNNING', (batch/'accounting.tsv').read_text())


class DiagnosticSubmissionTests(unittest.TestCase):
    def test_interim_review_preserves_queued_final_job_and_uses_own_script(self):
        from pipeline.cluster import submit_diagnostics
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as directory:
            batch = Path(directory)
            save(batch/'submission.json', {'cluster':{'host':'test-host','remote_root':'/tmp/assembly-benchmark', 'pixi':'/tools/pixi','account':'test','partition':'short'}, 'jobs':{'assemble':'100'}})
            final = {'job_id':'200','after_job':'100'}
            save(batch/'diagnostic_submission.json', final)
            with patch('pipeline.cluster.transfer'), patch('pipeline.cluster.ssh', return_value='300') as scheduler, patch('pipeline.cluster.subprocess.run'):
                result = submit_diagnostics(batch, interim=True)
            self.assertTrue(result['interim'])
            self.assertEqual(load(batch/'diagnostic_submission.json'), final)
            self.assertEqual(load(batch/'diagnostic_review_submission.json')['job_id'], '300')
            self.assertTrue(scheduler.call_args.args[1][-1].endswith('/slurm/diagnostics-review.sh'))
            self.assertNotIn('--dependency', scheduler.call_args.args[1])
            with self.assertRaises(ValueError):
                submit_diagnostics(batch, interim=True)


if __name__ == '__main__':
    unittest.main()
