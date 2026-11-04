"""Check repeat identity, finite plans and honest incomplete-run summaries."""

import copy
import tempfile
import unittest
from pathlib import Path

from pipeline.cases import plan
from pipeline.common import ROOT, digest, fingerprint, load, reverse_complement, save, write_fasta
from pipeline.determinism import assembly_tasks, biological_signature, collect_summary, execution_id, repeat_settings, sequence_signature


class DeterminismTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.cache')
        self.path = Path(self.temporary.name)
        self.config = load(ROOT / 'config/determinism.json')

    def tearDown(self):
        self.temporary.cleanup()

    def test_finite_panel_shares_two_inputs_for_eighty_executions(self):
        cases = [case for case in plan(self.config) if case['id'] in self.config['determinism']['scenarios']]
        tasks = assembly_tasks(self.config, cases)
        self.assertEqual(len(tasks), 80)
        self.assertEqual({task['scenario'] for task in tasks}, {'s1-w-prk2', 's1-mgh78578-pkpn7'})
        self.assertEqual({task['threads'] for task in tasks}, {1, 4})
        self.assertEqual(len({(task['scenario'], task['tool'], task['run_id']) for task in tasks}), 80)
        self.assertEqual(len(assembly_tasks(load(ROOT / 'config/pilot.json'), cases)), 8)

    def test_invalid_repeat_settings_are_rejected(self):
        for settings in ({'threads': [1, 1]}, {'threads': [0, 4]}, {'repeats': 1}, {'repeats': True}):
            config = copy.deepcopy(self.config)
            config['determinism'].update(settings)
            with self.assertRaises(ValueError):
                repeat_settings(config)
        with self.assertRaises(ValueError):
            execution_id(1, 0)

    def test_sequence_signature_ignores_names_order_strand_and_exact_circle_rotation(self):
        case = {'replicons': [{'refseq_accession': 'p', 'topology': 'circular'}]}
        reference = 'AACCGTTGAC'
        write_fasta(self.path / 'truth.fa', {'p': reference})
        write_fasta(self.path / 'a.fa', {'first': reference, 'second': 'AGGC'})
        write_fasta(self.path / 'b.fa', {'renamed': reverse_complement('AGGC'), 'other': reverse_complement(reference[3:] + reference[:3])})
        a = sequence_signature(case, self.path / 'truth.fa', self.path / 'a.fa')
        b = sequence_signature(case, self.path / 'truth.fa', self.path / 'b.fa')
        self.assertNotEqual(digest(self.path / 'a.fa'), digest(self.path / 'b.fa'))
        self.assertEqual(a['sha256'], b['sha256'])
        write_fasta(self.path / 'b.fa', {'p1': reference, 'p2': reference})
        self.assertNotEqual(a['sha256'], sequence_signature(case, self.path / 'truth.fa', self.path / 'b.fa')['sha256'])

    def test_linear_or_unclassified_ends_are_not_rotatable(self):
        reference = 'AACCGTTGAC'
        write_fasta(self.path / 'truth.fa', {'p': reference})
        write_fasta(self.path / 'a.fa', {'p': reference})
        write_fasta(self.path / 'b.fa', {'p': reference[3:] + reference[:3]})
        case = {'replicons': [{'refseq_accession': 'p', 'topology': 'linear'}]}
        self.assertNotEqual(sequence_signature(case, self.path / 'truth.fa', self.path / 'a.fa')['sha256'],
                            sequence_signature(case, self.path / 'truth.fa', self.path / 'b.fa')['sha256'])

    def test_biological_signature_ignores_contig_names_but_preserves_outcome(self):
        base = {'status': 'pass', 'contig_count': 1, 'replicons': [{'accession': 'p', 'status': 'pass', 'exact_contigs': ['old'], 'extra_full_copy_contigs': [], 'topology_status': 'not_assessed'}]}
        renamed = copy.deepcopy(base)
        renamed['replicons'][0]['exact_contigs'] = ['new']
        self.assertEqual(biological_signature(base), biological_signature(renamed))
        renamed['replicons'][0]['status'] = 'fail'
        self.assertNotEqual(biological_signature(base), biological_signature(renamed))

    def write_repeat_panel(self, omit_last=False):
        cases = [case for case in plan(self.config) if case['id'] in self.config['determinism']['scenarios']]
        tasks = assembly_tasks(self.config, cases)
        save(self.path / 'tasks.json', {'assemble': tasks})
        by_id = {case['id']: case for case in cases}
        for index, task in enumerate(tasks):
            if omit_last and index == len(tasks) - 1:
                continue
            record = {'status': 'pass', 'config_fingerprint': fingerprint(self.config),
                      'scenario_fingerprint': by_id[task['scenario']]['fingerprint'],
                      'threads': task['threads'], 'repeat': task['repeat'],
                      'reads_sha256': 'frozen-reads', 'truth_sha256': 'frozen-truth',
                      'assembly_sha256': 'same-bytes', 'normalised_assembly_sha256': 'same-sequence',
                      'biological_sha256': 'same-outcome'}
            save(self.path / 'results' / task['scenario'] / task['tool'] / 'repeats' / task['run_id'] / 'execution.json', record)
        return tasks

    def test_missing_repeat_does_not_claim_determinism(self):
        self.write_repeat_panel(omit_last=True)
        summary = collect_summary(self.config, self.path)
        group = summary['within_thread'][-1]
        self.assertFalse(group['complete'])
        self.assertIsNone(group['byte_identical'])
        self.assertEqual(summary['status_counts'], {'pass': 79, 'not_run': 1})
        across = next(row for row in summary['across_threads'] if row['scenario_id'] == group['scenario_id'] and row['tool'] == group['tool'])
        self.assertIsNone(across['normalised_sequence_identical'])

    def test_byte_differences_separate_from_sequence_and_outcome(self):
        tasks = self.write_repeat_panel()
        task = tasks[0]
        path = self.path / 'results' / task['scenario'] / task['tool'] / 'repeats' / task['run_id'] / 'execution.json'
        record = load(path)
        record['assembly_sha256'] = 'different-header'
        save(path, record)
        group = collect_summary(self.config, self.path)['within_thread'][0]
        self.assertTrue(group['complete'])
        self.assertFalse(group['byte_identical'])
        self.assertTrue(group['normalised_sequence_identical'])
        self.assertTrue(group['biological_identical'])
        record['reads_sha256'] = 'different-input'
        save(path, record)
        group = collect_summary(self.config, self.path)['within_thread'][0]
        self.assertFalse(group['inputs_identical'])
        self.assertIsNone(group['normalised_sequence_identical'])

    def test_scheduler_failure_is_not_missing(self):
        tasks = self.write_repeat_panel(omit_last=True)
        save(self.path / 'submission.json', {'jobs': {'assemble': '123'}})
        (self.path / 'accounting.tsv').write_text(f'123_{len(tasks)-1}|OUT_OF_MEMORY|1:0|\n')
        self.assertEqual(collect_summary(self.config, self.path)['executions'][-1]['status'], 'error')

    def test_execution_reuses_frozen_reads_and_honours_selected_threads(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from pipeline.execution import run
        case = next(case for case in plan(self.config) if case['id'] == 's1-w-prk2')
        directory = self.path / 'cases' / case['id']
        directory.mkdir(parents=True)
        sequences = {replicon['refseq_accession']: 'AACCGTTGAC' + 'G' * index for index, replicon in enumerate(case['replicons'])}
        write_fasta(directory / 'truth.fasta', sequences)
        (directory / 'reads.fastq.gz').write_bytes(b'frozen read fixture')
        save(directory / 'input.json', {'status': 'valid', 'case': case,
                                       'reads_sha256': digest(directory / 'reads.fastq.gz'),
                                       'truth_sha256': digest(directory / 'truth.fasta')})
        commands = []

        class Process:
            def __init__(self, argv, stdout, **kwargs):
                commands.append(argv)
                stdout.write(''.join(f'>renamed{index}\n{sequence}\n' for index, sequence in enumerate(sequences.values())))

            def wait(self, timeout):
                return 0

        with patch('pipeline.execution.subprocess.run', return_value=SimpleNamespace(stdout='version', stderr='', returncode=0)), \
             patch('pipeline.execution.subprocess.Popen', Process), \
             patch('pipeline.execution.platform.system', return_value='Darwin'), \
             patch('pipeline.execution.socket.socket'), \
             patch.dict('os.environ', {'TMPDIR': str(ROOT / '.t/x'), 'SLURM_CPUS_PER_TASK': '4'}):
            first = run(case, 'raven', self.path, self.config, threads=1, repeat=1)
            second = run(case, 'raven', self.path, self.config, threads=4, repeat=1)
            with self.assertRaises(ValueError):
                run(case, 'raven', self.path, self.config, threads=4, repeat=1)
        self.assertEqual(first['status'], 'pass', first.get('error'))
        self.assertEqual(second['status'], 'pass')
        self.assertEqual(first['reads_sha256'], second['reads_sha256'])
        self.assertEqual(first['normalised_assembly_sha256'], second['normalised_assembly_sha256'])
        self.assertEqual(first['allocated_cpus'], 4)
        self.assertEqual(commands[0][1:3], ['-t', '1'])
        self.assertEqual(commands[1][1:3], ['-t', '4'])
        self.assertEqual(self.config['threads'], 4)
