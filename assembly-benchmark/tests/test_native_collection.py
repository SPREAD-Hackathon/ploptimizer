"""Collectors must write their checkpoint locally, never at the remote source path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import load, save
from scripts import native_linear


class NativeCollectionTests(unittest.TestCase):
    def test_incomplete_evidence_updates_original_local_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            status = root / 'evidence/status.json'
            save(status, {'batch_id': 'toy'})
            batch = root / 'runs/toy'
            save(batch / 'submission.json', {'cluster': {'host': 'test', 'remote_root': '/remote/source'}})
            save(batch / 'evidence_status.json', {'status': 'needs_review'})
            with patch.object(native_linear, 'ROOT', root), patch.object(native_linear, 'collect'), \
                 patch.object(native_linear, 'ssh'), patch.object(native_linear.subprocess, 'run'):
                result = native_linear.collect_panel(status)
            self.assertEqual(result['status'], 'needs_review')
            self.assertEqual(load(status), result)
