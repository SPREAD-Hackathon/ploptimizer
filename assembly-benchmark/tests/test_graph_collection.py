"""Collection preserves outputs and never exports GFA sequence fields."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest

from pipeline.common import ROOT, digest, save
from pipeline.graph_artifacts import attach_graph_artifacts

spec = importlib.util.spec_from_file_location('graph_collection', ROOT / 'scripts/collect_graph_artifacts.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class GraphCollectionTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.cache')
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.destination = self.root / 'collected'
        self.batch = self.source / 'runs/fixture'
        self.relative = 'results/case/flye/execution.json'
        self.execution = self.batch / self.relative
        self.directory = self.execution.parent
        self.output = self.directory / 'output'
        self.output.mkdir(parents=True)
        self.sequence = 'GATTACA' * 20
        self.assembly = self.output / 'assembly.fasta'
        self.assembly.write_text('>contig_1\n' + self.sequence + '\n')
        self.graph = self.output / 'assembly_graph.gfa'
        self.graph.write_text('H\tVN:Z:1.0\nS\t1\t' + self.sequence + '\tLN:i:140\tDP:f:30\tZZ:Z:' + self.sequence + '\nL\t1\t+\t1\t+\t0M\nP\tcontig_1\t1+\t*\n')
        self.info = self.output / 'assembly_info.txt'
        self.info.write_text('#seq_name\tlength\tcov.\tcirc.\trepeat\tmult.\talt_group\tgraph_path\ncontig_1\t140\t30\tY\tN\t1\t*\t1\n')
        self.record = {'batch_id': 'fixture', 'scenario_id': 'case', 'tool': 'flye', 'status': 'pass',
                       'assembly_file': str(self.assembly.relative_to(self.batch)), 'assembly_sha256': digest(self.assembly)}
        save(self.execution, self.record)

    def tearDown(self):
        self.temporary.cleanup()

    def collect(self):
        return collector.collect_selected(self.source, 'fixture', [self.relative])

    def test_local_route_keeps_provenance_and_drops_sequences(self):
        original = {path: digest(path) for path in (self.execution, self.assembly, self.graph, self.info)}
        document = self.collect()
        artifact = document['executions'][0]['artifact']
        self.assertEqual(artifact['input_hashes']['execution_sha256'], original[self.execution])
        self.assertEqual(artifact['input_hashes']['assembly_sha256'], original[self.assembly])
        self.assertEqual(artifact['graph']['nodes'][0]['length_bp'], 140)
        self.assertEqual(artifact['graph']['self_loop_segment_ids'], ['1'])
        self.assertNotIn(self.sequence, json.dumps(document))
        written = collector.write_sidecars(self.destination, 'fixture', document)
        self.assertEqual(written, ['runs/fixture/results/case/flye/graph_artifacts.json'])
        self.assertEqual(original, {path: digest(path) for path in original})
        self.assertFalse((self.directory / 'graph_artifacts.json').exists())

    def test_missing_and_unverified_assembly_are_explicit(self):
        self.graph.unlink(); self.info.unlink()
        artifact = self.collect()['executions'][0]['artifact']
        self.assertEqual(artifact['graph']['status'], 'missing')
        self.assertEqual(artifact['assembly_info']['status'], 'missing')
        self.assembly.write_text('>changed\nAAAA\n')
        artifact = self.collect()['executions'][0]['artifact']
        self.assertEqual(artifact['status'], 'invalid')
        self.assertIn('hash differs', artifact['reason'])

    def test_symlinked_graph_outside_execution_is_not_followed(self):
        outside = self.root / 'outside.gfa'
        outside.write_text('S\toutside\t' + self.sequence + '\n')
        self.graph.unlink(); self.graph.symlink_to(outside)
        artifact = self.collect()['executions'][0]['artifact']
        self.assertEqual(artifact['graph']['status'], 'missing')
        self.assertIn('rejected_outside_execution', [row['status'] for row in artifact['collection']['candidate_files']])
        self.assertNotIn(self.sequence, json.dumps(artifact))

    def test_selection_limits_and_path_escape_are_fail_closed(self):
        with self.assertRaises(ValueError):
            collector.collect_selected(self.source, 'fixture', [self.relative] * 9)
        result = collector.collect_selected(self.source, 'fixture', ['../../outside/execution.json'])
        self.assertEqual(result['executions'][0]['artifact']['status'], 'invalid')
        with self.assertRaises(ValueError):
            collector.write_sidecars(self.destination, 'fixture', result)

    def test_streamed_remote_helper_never_installs_or_writes_sources(self):
        original_run = subprocess.run
        before = {path: digest(path) for path in self.source.rglob('*') if path.is_file()}
        calls = []

        def transport(argv, **kwargs):
            calls.append(argv)
            return original_run([sys.executable, '-c', collector.REMOTE_BOOTSTRAP], **kwargs)

        with patch.object(collector.subprocess, 'run', side_effect=transport):
            document = collector.collect_remote('fixture-host', self.source, 'fixture', [self.relative])
        self.assertEqual(calls[0][0], 'ssh')
        self.assertIn('BatchMode=yes', calls[0])
        self.assertEqual(document['executions'][0]['artifact']['graph']['nodes'][0]['length_bp'], 140)
        self.assertNotIn(self.sequence, json.dumps(document))
        self.assertEqual(before, {path: digest(path) for path in self.source.rglob('*') if path.is_file()})

    def test_plassembler_component_is_not_labelled_final_plasmid_graph(self):
        directory = self.batch / 'results/case/plassembler'
        component = directory / 'output/flye_output'
        component.mkdir(parents=True)
        (component / 'assembly_graph.gfa').write_text(self.graph.read_text())
        (component / 'assembly_info.txt').write_text(self.info.read_text())
        assembly = directory / 'output/plasmids.fasta'
        assembly.write_text(self.assembly.read_text())
        record = dict(self.record, tool='plassembler', assembly_file=str(assembly.relative_to(self.batch)), assembly_sha256=digest(assembly))
        save(directory / 'execution.json', record)
        artifact = collector.collect_selected(self.source, 'fixture', ['results/case/plassembler/execution.json'])['executions'][0]['artifact']
        self.assertEqual(artifact['collection']['source_role'], 'initial_flye')
        self.assertEqual(artifact['graph']['source']['role'], 'initial_flye')
        self.assertNotIn(self.sequence, json.dumps(artifact))

    def test_final_plassembler_graph_and_summary_precede_initial_component(self):
        directory = self.batch / 'results/case/plassembler'
        component = directory / 'output/flye_output'
        component.mkdir(parents=True)
        (component / 'assembly_graph.gfa').write_text(self.graph.read_text())
        (component / 'assembly_info.txt').write_text(self.info.read_text())
        assembly = directory / 'output/benchmark_plasmids.fasta'
        assembly.write_text(self.assembly.read_text())
        final_graph = directory / 'output/benchmark_plasmids.gfa'
        final_graph.write_text(self.graph.read_text())
        summary = directory / 'output/benchmark_summary.tsv'
        summary.write_text('contig\tlength\tcircularity\ncontig_1\t140\tcircular\n')
        record = dict(self.record, tool='plassembler', command=['plassembler', 'long', '--prefix', 'benchmark'],
                      assembly_file=str(assembly.relative_to(self.batch)), assembly_sha256=digest(assembly))
        save(directory / 'execution.json', record)
        relative = 'results/case/plassembler/execution.json'
        artifact = collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']
        self.assertEqual(artifact['collection']['source_role'], 'final')
        self.assertEqual(artifact['graph']['source']['filename'], 'benchmark_plasmids.gfa')
        self.assertEqual(artifact['assembly_info']['source']['kind'], 'plassembler_summary')
        self.assertEqual(artifact['assembly_info']['contigs'][0]['reported_circularity'], 'circular')
        summary.unlink()
        artifact = collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']
        self.assertEqual(artifact['collection']['source_role'], 'final')
        self.assertEqual(artifact['assembly_info']['status'], 'missing')

    def test_failed_execution_retains_graph_without_claiming_primary_assembly(self):
        failed = dict(self.record, status='error')
        failed.pop('assembly_file'); failed.pop('assembly_sha256')
        save(self.execution, failed)
        self.assembly.unlink()
        before = {path: digest(path) for path in (self.execution, self.graph, self.info)}
        artifact = self.collect()['executions'][0]['artifact']
        self.assertEqual(artifact['status'], 'available')
        self.assertEqual(artifact['collection']['source_role'], 'partial_output')
        self.assertFalse(artifact['collection']['assembly_hash_verified'])
        self.assertIsNone(artifact['input_hashes']['assembly_sha256'])
        save(self.directory / 'graph_artifacts.json', artifact)
        attached = attach_graph_artifacts(failed, self.execution)
        self.assertEqual(attached['status'], 'error')
        self.assertEqual(attached['graph_artifacts']['status'], 'available')
        self.assertEqual(before, {path: digest(path) for path in before})

    def test_failed_earlier_graph_takes_precedence_over_final_claim_only(self):
        self.graph.unlink()
        earlier = self.output / '20-repeat/graph_before_rr.gfa'
        earlier.parent.mkdir()
        earlier.write_text('S\tinitial\tACGT\n')
        failed = dict(self.record, status='timeout')
        save(self.execution, failed)
        artifact = self.collect()['executions'][0]['artifact']
        self.assertEqual(artifact['status'], 'available')
        self.assertEqual(artifact['collection']['source_role'], 'partial_repeat_graph')
        self.assertEqual(artifact['graph']['source']['filename'], 'graph_before_rr.gfa')
        self.assertEqual(artifact['assembly_info']['status'], 'missing')
        self.assertFalse(artifact['collection']['assembly_hash_verified'])

    def test_failed_plassembler_initial_component_and_nonterminal_admission(self):
        directory = self.batch / 'results/case/plassembler'
        component = directory / 'output/flye_output'
        component.mkdir(parents=True)
        (component / 'assembly_graph.gfa').write_text(self.graph.read_text())
        (component / 'assembly_info.txt').write_text(self.info.read_text())
        execution = directory / 'execution.json'
        record = dict(self.record, status='error', tool='plassembler')
        record.pop('assembly_file'); record.pop('assembly_sha256')
        save(execution, record)
        relative = 'results/case/plassembler/execution.json'
        artifact = collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']
        self.assertEqual(artifact['status'], 'available')
        self.assertEqual(artifact['graph']['source']['role'], 'initial_flye')
        save(directory / 'graph_artifacts.json', artifact)
        self.assertEqual(attach_graph_artifacts(record, execution)['graph_artifacts']['status'], 'available')
        record['status'] = 'running'
        save(execution, record)
        self.assertEqual(attach_graph_artifacts(record, execution)['graph_artifacts']['status'], 'not_collected')
        self.assertEqual(collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']['status'], 'missing')

    def test_failed_empty_final_placeholders_do_not_hide_initial_graph(self):
        directory = self.batch / 'results/case/plassembler'
        component = directory / 'output/flye_output'
        component.mkdir(parents=True)
        (component / 'assembly_graph.gfa').write_text(self.graph.read_text())
        (component / 'assembly_info.txt').write_text(self.info.read_text())
        (directory / 'output/benchmark_plasmids.gfa').write_text('')
        (directory / 'output/benchmark_summary.tsv').write_text('')
        execution = directory / 'execution.json'
        record = dict(self.record, tool='plassembler', status='error',
                      command=['plassembler', 'long', '--prefix', 'benchmark'])
        record.pop('assembly_file'); record.pop('assembly_sha256')
        save(execution, record)
        relative = 'results/case/plassembler/execution.json'
        artifact = collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']
        self.assertEqual(artifact['status'], 'available')
        self.assertEqual(artifact['graph']['source']['role'], 'initial_flye')
        self.assertEqual(len(artifact['graph']['nodes']), 1)
        self.assertEqual(artifact['assembly_info']['status'], 'available')
        self.assertEqual(artifact['collection']['candidate_files'][0]['status'], 'empty_placeholder')
        assembly = directory / 'output/benchmark_plasmids.fasta'
        assembly.write_text(self.assembly.read_text())
        record.update(status='pass', assembly_file=str(assembly.relative_to(self.batch)), assembly_sha256=digest(assembly))
        save(execution, record)
        artifact = collector.collect_selected(self.source, 'fixture', [relative])['executions'][0]['artifact']
        self.assertEqual(artifact['graph']['source']['role'], 'final')
        self.assertEqual(artifact['graph']['nodes'], [])
