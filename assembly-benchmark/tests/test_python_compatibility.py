"""Controller upgrades must not introduce syntax unsupported by pinned BMRC Python."""
import ast
import unittest

from pipeline.common import ROOT


class PythonCompatibilityTests(unittest.TestCase):
    def test_runtime_sources_parse_as_python_311(self):
        paths = [ROOT / 'benchmark.py', *(ROOT / 'pipeline').glob('*.py'), *(ROOT / 'scripts').glob('*.py')]
        for path in paths:
            with self.subTest(source=str(path.relative_to(ROOT))):
                ast.parse(path.read_text(), filename=str(path), feature_version=(3,11))
