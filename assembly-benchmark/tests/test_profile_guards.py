"""A proposed noisy profile must never silently generate exact reads."""
import copy
import tempfile
import unittest
from pathlib import Path
from benchmark import main
from pipeline.cases import plan
from pipeline.common import ROOT, load, save
from pipeline.reads import exact_reads


class ProfileGuardTests(unittest.TestCase):
    def test_cli_refuses_non_executable_design_proposal(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            path = Path(directory)/'proposed.json'
            save(path, {'status':'proposed'})
            with self.assertRaisesRegex(ValueError, 'design proposal'):
                main(['--config',str(path),'plan'])

    def test_unknown_simulator_cannot_fall_back_to_exact_reads(self):
        case = copy.deepcopy(plan(load(ROOT/'config/pilot.json'))[0])
        case['simulation']['model'] = 'unimplemented-noisy-model'
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as directory:
            with self.assertRaisesRegex(ValueError, 'unknown models cannot fall back'):
                exact_reads(case, {}, Path(directory))
            self.assertFalse((Path(directory)/'reads.fastq.gz').exists())


if __name__ == '__main__':
    unittest.main()
