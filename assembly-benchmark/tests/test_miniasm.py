from pathlib import Path
import tempfile
import unittest

from pipeline.command_view import render_command
from pipeline.execution import command, ENVIRONMENTS
from pipeline.graph_artifacts import parse_gfa, parse_miniasm_unitig_info
from pipeline.miniasm import extract_unitigs
from scripts.collect_graph_artifacts import select_artifacts


class MiniasmAdapter(unittest.TestCase):
    def test_gfa_conversion_preserves_unitigs_links_and_annotations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            raw, graph, fasta = [root / name for name in ('raw.gfa', 'graph.gfa', 'assembly.fa')]
            raw.write_text('S\tutg000001c\tACGTAC\tLN:i:6\nL\tutg000001c\t+\tutg000001c\t+\t0M\na\tutg000001c\t0\tread1\t+\t6\nx\tutg000001c\t6\t1\n')
            result = extract_unitigs(raw, graph, fasta)
            self.assertEqual(fasta.read_text(), '>utg000001c\nACGTAC\n')
            self.assertEqual(result['raw_annotation_records'], {'a': 1, 'x': 1})
            self.assertEqual(parse_gfa(graph)['self_loop_segment_ids'], ['utg000001c'])
            info = parse_miniasm_unitig_info(graph)
            self.assertEqual(info['contigs'][0]['reported_circularity'], 'circular')
            self.assertIsNone(info['contigs'][0]['reported_coverage'])
            self.assertIn('a\t', raw.read_text())

    def test_missing_sequence_or_bad_length_is_an_error(self):
        for row in ('S\tutg000001l\t*\tLN:i:6\n', 'S\tutg000001l\tACGT\tLN:i:6\n'):
            with self.subTest(row=row), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                raw = root / 'raw.gfa'
                raw.write_text(row)
                with self.assertRaises(ValueError):
                    extract_unitigs(raw, root / 'graph.gfa', root / 'assembly.fa')

    def test_graph_is_also_the_reported_unitig_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            graph = root / 'output/assembly_graph.gfa'
            graph.parent.mkdir()
            graph.write_text('S\tutg000001l\tACGT\tLN:i:4\n')
            selected, role, _ = select_artifacts(root, {'tool': 'miniasm', 'status': 'pass'})
            self.assertEqual(selected['gfa'], selected['assembly_info'])
            self.assertEqual(role, 'final')
            self.assertEqual(parse_miniasm_unitig_info(graph)['contigs'][0]['reported_circularity'], 'not_circular')

    def test_command_report_shows_both_real_steps_and_no_polishing(self):
        record = {'tool': 'miniasm', 'status': 'pass', 'scenario_id': 'fixture',
                  'command': ['python', '-m', 'pipeline.miniasm'], 'version': '0.3-r179',
                  'assembly_workflow': {'steps': [
                      {'name': 'Overlaps', 'command': ['minimap2', '-x', 'ava-ont', '-t', '4', '/private/runs/b/cases/a/reads.fq', '/private/runs/b/cases/a/reads.fq'], 'stdout_file': '/private/runs/b/results/a/miniasm/output/overlaps.paf'},
                      {'name': 'Assembly', 'command': ['miniasm', '-f', '/private/runs/b/cases/a/reads.fq', 'overlaps.paf'], 'stdout_file': 'raw.gfa'}]}}
        html = render_command(record)
        self.assertIn('ava-ont', html)
        self.assertIn('No polishing step is run', html)
        self.assertIn('miniasm -f', html)
        self.assertNotIn('/private/', html)
        self.assertNotIn('pipeline.miniasm', html)

    def test_adapter_uses_miniasm_environment_and_rejects_invented_mode(self):
        self.assertEqual(ENVIRONMENTS['miniasm'], 'miniasm')
        args = command('miniasm', Path('reads.fq'), Path('output'), {'threads': 4})
        self.assertIn('pipeline.miniasm', args)
        with self.assertRaises(ValueError):
            command('miniasm', Path('reads.fq'), Path('output'), {'threads': 4}, 'deterministic')
