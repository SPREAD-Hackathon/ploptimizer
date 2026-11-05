"""Presentation packaging keeps complete evidence separate from runtime assets."""
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.web_downloads import package_downloads


class WebDownloadTests(unittest.TestCase):
    def fixture(self, root):
        documents = {
            'data/results.json': {'batch': 'fixture', 'evaluation': {'score': 2.5}, 'provenance': ['α', 'sha256']},
            'data/results/example.json': {'assessment': {'fail': False}, 'graph': {'nodes': []}},
            'data/aggregates/data.json': {'values': [1, None, -2.5]},
            'batches/fixture/data/results.json': {'batch': 'archived'},
            'data/overview.json': {'runtime': True},
            'batches/fixture/data/overview.json': {'runtime': True},
            'assets/build.json': {'asset': 'checksum'},
        }
        for name, value in documents.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        (root / 'vercel.json').write_text('{"cleanUrls":true,"redirects":[{"source":"/history","destination":"/"}]}')
        (root / 'index.html').write_text('<a href="data/results.json?download=1#source">Download JSON</a><a href="data/overview.json">Runtime model</a><a href="https://elsewhere.test/data/results.json">External JSON</a>')
        (root / 'results').mkdir()
        (root / 'results/example.html').write_text('<script type="application/json">{"link":"../data/results/example.json"}</script><a href="../data/results/example.json">Execution JSON</a>')
        (root / 'batches/fixture/index.html').write_text('<base href="/batches/fixture/"><a href="data/results.json">Batch JSON</a>')
        (root / 'data/results/example-report.md').write_text('- Source: `../results.json`\n')
        (root / 'data/results-bundle.zip').write_bytes(b'complete frozen backend archive bytes')
        return documents

    def test_presentation_only_preserves_runtime_tables_and_backend_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            backend = root.parent / (root.name + '-backend.json')
            backend.write_bytes(b'unchanged backend')
            self.addCleanup(backend.unlink)
            inline = '<script type="application/json">{"link":"../data/results/example.json"}</script>'
            (root/'data/summary.tsv').write_text('score\n2.5\n')
            before = (root/'data/overview.json').read_bytes()
            audit = package_downloads(root)
            self.assertEqual(audit['policy'], 'presentation-only')
            for name in ('data/results.json', 'data/results/example.json', 'data/results-bundle.zip', 'data/results/example-report.md'):
                self.assertFalse((root/name).exists(), name)
            self.assertEqual((root/'data/overview.json').read_bytes(), before)
            self.assertEqual((root/'data/summary.tsv').read_text(), 'score\n2.5\n')
            self.assertIn(inline, (root/'results/example.html').read_text())
            self.assertNotIn('Download JSON</a>', (root/'index.html').read_text())
            self.assertIn('External JSON</a>', (root/'index.html').read_text())
            self.assertEqual(backend.read_bytes(), b'unchanged backend')
            self.assertEqual(json.loads((root/'vercel.json').read_text())['redirects'][0]['source'], '/history')
            self.assertLess(audit['website_bytes_after'], audit['website_bytes_before'])
