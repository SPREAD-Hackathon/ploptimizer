"""Only attach supplementary evidence tied to the exact execution record."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import ROOT, digest, fingerprint, save
from pipeline.report import collect_records


class DiagnosticProvenanceTests(unittest.TestCase):
    def test_report_rejects_stale_execution_or_assembly_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as folder:
            batch = Path(folder)
            config = {'tools':['flye']}
            case = {'id':'test', 'fingerprint':'case-hash'}
            path = batch/'results/test/flye/execution.json'
            record = {'scenario_fingerprint':'case-hash', 'config_fingerprint':fingerprint(config), 'status':'fail', 'assembly_sha256':'assembly-hash'}
            save(path, record)
            hashes = {'execution_sha256':digest(path), 'assembly_sha256':'assembly-hash'}
            with patch('pipeline.report.plan', return_value=[case]):
                for field in (None, 'execution_sha256', 'assembly_sha256'):
                    changed = dict(hashes)
                    if field:
                        changed[field] = 'stale'
                    save(path.parent/'diagnostics.json', {'status':'complete', 'input_hashes':changed, 'command':['private-path'], 'evidence':{}})
                    result = collect_records(config, batch)[0]
                    self.assertEqual('diagnostics' in result, field is None)
                    if field is None:
                        self.assertNotIn('command', result['diagnostics'])
                    self.assertEqual(result['status'], 'fail')


if __name__ == '__main__':
    unittest.main()
