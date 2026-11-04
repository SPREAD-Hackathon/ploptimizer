"""Noisy preparation can run while assemblies wait for an earlier study."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.cluster import submit
from pipeline.common import ROOT,load


class NoisySubmissionTests(unittest.TestCase):
    def test_assessment_order_and_independent_assembly_dependency(self):
        config=load(ROOT/'config/noisy-smoke.json')
        cluster={'host':'test-host','remote_root':'/tmp/assembly-benchmark','account':'test','partition':'short','pixi':'/tools/pixi','cpus':4,'memory':'16G','time':'04:00:00','array_concurrency':4}
        for noisy in (True,False):
            selected=dict(config)
            if not noisy:selected.pop('noisy_panel')
            calls=[]
            def scheduler(host,argv):
                if argv[0]=='sbatch':
                    calls.append(argv)
                    return str(400+len(calls))
                return ''
            with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory, patch('pipeline.cluster.ROOT',Path(directory)), patch('pipeline.cluster.ensure_assets'), patch('pipeline.cluster.plan',return_value=[{'id':'case'}]), patch('pipeline.cluster.transfer'), patch('pipeline.cluster.subprocess.run'), patch('pipeline.cluster.ssh',side_effect=scheduler):
                result=submit(selected,cluster,assembly_after_job='999')
            self.assertEqual(len(calls),5 if noisy else 4)
            self.assertNotIn('--dependency',calls[0])
            self.assertIn('afterok:402,afterany:999',calls[2])
            self.assertIn('afterany:403',calls[3])
            if noisy:
                self.assertIn('afterany:404',calls[4])
                self.assertIn('assessment',result['jobs'])
            else:
                self.assertNotIn('assessment',result['jobs'])


if __name__=='__main__':
    unittest.main()
