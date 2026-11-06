from pathlib import Path
import tempfile
import unittest

from pipeline.common import digest, save
from pipeline.minipolish import run
from pipeline.miniasm import extract_unitigs
from pipeline.graph_artifacts import parse_miniasm_unitig_info


class PolishedMiniasm(unittest.TestCase):
    def test_polished_gfa_without_length_tag_keeps_sequence_and_depth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / 'polished.gfa'
            raw.write_text('S\tutg000001l\tACGT\tdp:f:31.5\n')
            extract_unitigs(raw, root / 'graph.gfa', root / 'assembly.fa', require_length_tag=False)
            info = parse_miniasm_unitig_info(root / 'graph.gfa')
            self.assertEqual((root / 'assembly.fa').read_text(), '>utg000001l\nACGT\n')
            self.assertEqual(info['contigs'][0]['reported_coverage'], 31.5)
            self.assertEqual(info['contigs'][0]['length_bp'], 4)

    def test_modified_source_graph_is_rejected_before_polishing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reads, graph, execution = root / 'reads.fq', root / 'raw.gfa', root / 'execution.json'
            reads.write_text('fixture')
            graph.write_text('S\tutg000001l\tACGT\tLN:i:4\n')
            save(execution, {'tool': 'miniasm', 'status': 'fail', 'reads_sha256': digest(reads),
                 'assembly_workflow': {'status': 'complete', 'conversion': {'raw_gfa_sha256': digest(graph)}}})
            graph.write_text('changed')
            with self.assertRaises(ValueError):
                run(reads, graph, execution, root / 'output', 2)
            self.assertFalse((root / 'output').exists())
