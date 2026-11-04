"""Ensure Raven's relative checkpoint file belongs to one execution directory."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.common import ROOT, digest, fingerprint, load, save, write_fasta
from pipeline.execution import run


class RavenIsolationTests(unittest.TestCase):
    def test_two_runs_keep_checkpoint_writes_separate(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as temporary:
            root = Path(temporary)
            config = load(ROOT / 'config/pilot.json')
            rng = random.Random(48)
            sequences = {'chromosome': ''.join(rng.choice('ACGT') for _ in range(401)),
                         'plasmid': ''.join(rng.choice('ACGT') for _ in range(73))}
            case = {'id': 'checkpoint-fixture', 'replicons': [
                {'refseq_accession': name, 'replicon_name': name, 'molecule_type': name,
                 'topology': 'circular', 'length_bp': len(sequence)} for name, sequence in sequences.items()]}
            case['fingerprint'] = fingerprint(case)
            batches = [root / 'first', root / 'second']
            for batch in batches:
                source = batch / 'cases' / case['id']
                source.mkdir(parents=True)
                write_fasta(source / 'truth.fasta', sequences)
                (source / 'reads.fastq.gz').write_bytes(b'frozen reads; fake process does not parse input')
                save(source / 'input.json', {'status': 'valid', 'case': case,
                     'reads_sha256': digest(source / 'reads.fastq.gz'), 'truth_sha256': digest(source / 'truth.fasta')})
            observed = []
            other_observed = []
            sentinel = ROOT / 'raven.cereal'
            original = digest(sentinel) if sentinel.exists() else None

            class FakeRaven:
                def __init__(self, argv, stdout, cwd, **kwargs):
                    content = ''.join(f'>{name}\n{sequence}\n' for name, sequence in sequences.items())
                    if argv[0] == 'raven':
                        observed.append(Path(cwd))
                        if not Path(argv[-1]).is_absolute():
                            raise AssertionError('Input path must remain absolute after changing working directory')
                        (Path(cwd) / 'raven.cereal').write_text(f'checkpoint-for-{len(observed)}')
                        stdout.write(content)
                    else:
                        other_observed.append(Path(cwd))
                        output = Path(argv[argv.index('--out-dir') + 1])
                        output.mkdir(parents=True)
                        (output / 'assembly.fasta').write_text(content)

                def wait(self, timeout):
                    return 0

            with patch('pipeline.execution.subprocess.run', return_value=SimpleNamespace(stdout='1.8.3', stderr='', returncode=0)) as version, \
                 patch('pipeline.execution.subprocess.Popen', FakeRaven), \
                 patch('pipeline.execution.platform.system', return_value='Darwin'), \
                 patch('pipeline.execution.socket.socket'), \
                 patch.dict('os.environ', {'TMPDIR': str(ROOT / '.t/isolation')}):
                results = [run(case, 'raven', batch, config) for batch in batches]
                flye = run(case, 'flye', batches[0], config)
            self.assertEqual([result['status'] for result in results], ['pass', 'pass'])
            self.assertNotEqual(observed[0], observed[1])
            self.assertEqual((observed[0] / 'raven.cereal').read_text(), 'checkpoint-for-1')
            self.assertEqual((observed[1] / 'raven.cereal').read_text(), 'checkpoint-for-2')
            self.assertEqual([call.kwargs['cwd'] for call in version.call_args_list[:2]], observed)
            self.assertEqual(other_observed, [ROOT])
            self.assertEqual(flye['status'], 'pass')
            self.assertNotIn('working_directory', flye)
            self.assertNotIn('cwd', version.call_args_list[-1].kwargs)
            self.assertEqual(digest(sentinel) if sentinel.exists() else None, original)
            for batch, result, cwd in zip(batches, results, observed):
                self.assertEqual(result['working_directory_base'], 'batch')
                self.assertEqual(batch / result['working_directory'], cwd)
                self.assertEqual(result['command'][0:3], ['raven', '-t', '4'])
