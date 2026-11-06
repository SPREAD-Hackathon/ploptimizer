from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.common import digest, save
from scripts.miniasm_followup import validate_input, stage


class FrozenMiniasmInputs(unittest.TestCase):
    def test_original_bytes_are_required_even_when_case_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = {'id': 'fixture', 'fingerprint': 'frozen'}
            pairs = [('reads.fastq.gz', 'reads_sha256'), ('truth.fasta', 'truth_sha256'),
                     ('read_origins.tsv.gz', 'origins_sha256')]
            manifest = {'status': 'valid', 'case': case}
            for filename, key in pairs:
                (root / filename).write_bytes(b'frozen fixture')
                manifest[key] = digest(root / filename)
            save(root / 'input.json', manifest)
            self.assertEqual(validate_input(root, case), manifest)
            with self.assertRaises(ValueError):
                validate_input(root, {**case, 'fingerprint': 'changed'})
            (root / 'reads.fastq.gz').write_bytes(b'changed reads')
            with self.assertRaises(ValueError):
                validate_input(root, case)

    def test_staging_keeps_original_manifest_and_reuses_file_inodes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            case = {'id': 'fixture', 'fingerprint': 'frozen'}
            source = root / 'source/runs/original'
            inputs = source / 'cases/fixture'
            inputs.mkdir(parents=True)
            manifest = {'status': 'valid', 'case': case}
            for filename, key in [('reads.fastq.gz', 'reads_sha256'), ('truth.fasta', 'truth_sha256'),
                                  ('read_origins.tsv.gz', 'origins_sha256')]:
                (inputs / filename).write_bytes(b'frozen bytes')
                manifest[key] = digest(inputs / filename)
            save(inputs / 'input.json', manifest)
            save(source / 'evidence_status.json', {'status': 'complete', 'expected_executions': 24})
            batch = root / 'followup'
            batch.mkdir()
            save(batch / 'submission.json', {'input_source_root': str(root / 'source'), 'input_source_batch': 'original'})
            save(batch / 'config.json', {})
            (root / 'pixi.toml').write_text('fixture')
            (root / 'pixi.lock').write_text('fixture')
            with patch('scripts.miniasm_followup.ROOT', root), patch('scripts.miniasm_followup.plan', return_value=[case]):
                stage(batch)
            target = batch / 'cases/fixture'
            self.assertEqual((target / 'reads.fastq.gz').stat().st_ino, (inputs / 'reads.fastq.gz').stat().st_ino)
            self.assertEqual((target / 'input.json').read_bytes(), (inputs / 'input.json').read_bytes())
