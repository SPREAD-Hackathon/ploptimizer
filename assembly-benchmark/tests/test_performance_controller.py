"""Broad Slurm orchestration keeps reported workflows and intermediate jobs separate."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pipeline.common import digest,load,save
from scripts import broad_performance as controller

class PerformanceControllerTests(unittest.TestCase):
    def test_existing_input_jobs_are_reused_and_four_primary_workflows_queued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);batch=root/'runs/frozen';(batch/'slurm').mkdir(parents=True)
            (root/'pipeline/performance').mkdir(parents=True);(root/'pipeline/performance/assessment.py').write_text('')
            save(batch/'selection.json',{'frozen':True})
            cluster={'host':'test','remote_root':'/remote/.b','cache_root':'/remote/.cache/pixi','pixi':'/pixi','account':'test','partition':'short'}
            record={'cluster':cluster,'selection_sha256':digest(batch/'selection.json'),'jobs':{'prepare':'101','inputs':'102'},'status':'inputs_submitted'}
            save(batch/'submission.json',record);status=root/'status.json';save(status,{'jobs':dict(record['jobs'])})
            calls=[]
            def ssh(host,args):
                if args[0]=='sbatch':calls.append(args);return str(200+len(calls))
                return ''
            with patch.object(controller,'ROOT',root),patch.object(controller,'STATUS',status),patch.object(controller,'ssh',ssh),patch.object(controller.subprocess,'run'):
                result=controller.queue(batch)
            self.assertEqual(len(calls),9)
            self.assertEqual(result['jobs']['inputs'],'102')
            self.assertEqual(len([k for k in result['jobs'] if k.startswith('assemble-')]),5)
            self.assertEqual(len([k for k in result['jobs'] if k.startswith('assess-')]),4)
            plassembler=next(c for c in calls if 'ploptimizer-broad-assemble-plassembler' in c)
            self.assertEqual(plassembler[plassembler.index('--time')+1],'02:00:00')
            self.assertTrue(all(c[c.index('--array')+1]=='0-49%1000' for c in calls))
            self.assertEqual(load(batch/'submission.json')['status'],'submitted')

    def test_submit_refuses_duplicate_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            status=Path(temporary)/'status.json';save(status,{'batch_id':'existing'})
            with patch.object(controller,'STATUS',status),patch.object(controller,'ssh') as ssh:
                with self.assertRaisesRegex(ValueError,'Durable submission'):controller.submit()
            ssh.assert_not_called()

    def test_condensed_terminal_array_accounting_is_explicit(self):
        states=controller.accounting_states('345_[0-2,5%1000]|CANCELLED by 123|00:00:00|0:0|\n346_7|TIMEOUT|04:00:01|0:15|')
        self.assertEqual(states['345_1'][1],'CANCELLED by 123')
        self.assertEqual(states['345_5'][0],'345_[0-2,5%1000]')
        self.assertNotIn('345_4',states)
        self.assertEqual(states['346_7'][1],'TIMEOUT')

    def test_ambiguous_submission_failure_cannot_be_replayed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);batch=root/'runs/frozen';(batch/'slurm').mkdir(parents=True)
            (root/'pipeline/performance').mkdir(parents=True);(root/'pipeline/performance/assessment.py').write_text('')
            save(batch/'selection.json',{'frozen':True})
            cluster={'host':'test','remote_root':'/remote/.b','cache_root':'/remote/cache','pixi':'/pixi','account':'test','partition':'short'}
            save(batch/'submission.json',{'cluster':cluster,'selection_sha256':digest(batch/'selection.json'),'jobs':{'prepare':'101','inputs':'102'}})
            status=root/'status.json';save(status,{'jobs':{'prepare':'101','inputs':'102'}})
            def broken(host,args):
                if args[0]=='sbatch':raise TimeoutError('Reply lost after scheduler may have accepted the job')
                return ''
            with patch.object(controller,'ROOT',root),patch.object(controller,'STATUS',status),patch.object(controller,'ssh',broken),patch.object(controller.subprocess,'run'):
                with self.assertRaises(TimeoutError):controller.queue(batch)
                with self.assertRaisesRegex(ValueError,'unresolved intent'):controller.queue(batch)
            self.assertEqual(load(batch/'submission.json')['submission_intent']['role'],'assemble-flye')
