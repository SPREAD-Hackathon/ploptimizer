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

    def test_mode_panel_has_distinct_supported_execution_identities(self):
        self.config = load(ROOT / 'config/determinism-modes.json')
        cases = [case for case in plan(self.config) if case['id'] in self.config['determinism']['scenarios']]
        tasks = assembly_tasks(self.config, cases)
        self.assertEqual(len(tasks), 120)
        self.assertEqual(len({(row['scenario'], row['tool'], row['run_id']) for row in tasks}), 120)
        for tool in self.config['tools']:
            selected = [row for row in tasks if row['tool'] == tool]
            self.assertEqual({row['mode'] for row in selected},
                             {'default', 'deterministic'} if tool in ('flye', 'flye-meta') else {'default'})
        self.assertEqual(execution_id(1, 1), 'threads-1-repeat-1')
        self.assertEqual(execution_id(1, 1, 'default'), 'mode-default-threads-1-repeat-1')
        self.assertNotEqual(execution_id(1, 1, 'default'), execution_id(1, 1, 'deterministic'))

    def test_mode_validation_rejects_unsupported_and_incomplete_capabilities(self):
        base = load(ROOT / 'config/determinism-modes.json')
        for tool, modes in [('raven', ['deterministic']), ('plassembler', ['deterministic']),
                            ('flye', ['default', 'default']), ('flye', ['unknown'])]:
            config = copy.deepcopy(base)
            config['determinism']['modes'][tool] = modes
            with self.assertRaises(ValueError):
                repeat_settings(config)
        del base['determinism']['modes']['raven']
        with self.assertRaises(ValueError):
            repeat_settings(base)
        with self.assertRaises(ValueError):
            execution_id(1, 1, 'unknown')

    def test_deterministic_command_is_explicit_and_limited_to_direct_flye(self):
        from pipeline.execution import command
        for tool in ('flye', 'flye-meta'):
            default = command(tool, 'reads', 'out', self.config)
            deterministic = command(tool, 'reads', 'out', self.config, mode='deterministic')
            self.assertNotIn('--deterministic', default)
            self.assertEqual(deterministic, default + ['--deterministic'])
            self.assertEqual(deterministic[deterministic.index('--threads') + 1], '4')
        for tool in ('raven', 'plassembler'):
            with self.assertRaises(ValueError):
                command(tool, 'reads', 'out', self.config, mode='deterministic')

    def test_mode_task_dispatch_preserves_mode_and_thread_request(self):
        import benchmark
        from types import SimpleNamespace
        from unittest.mock import patch
        self.config = load(ROOT / 'config/determinism-modes.json')
        save(self.path / 'config.json', self.config)
        save(self.path / 'tasks.json', {'assemble': [{'scenario': 's1-w-prk2', 'tool': 'flye',
             'threads': 4, 'repeat': 2, 'mode': 'deterministic',
             'run_id': execution_id(4, 2, 'deterministic')}]})
        with patch.object(benchmark, 'batch_path', return_value=self.path), \
             patch.object(benchmark.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as invoked, \
             patch.dict('os.environ', {'SLURM_CPUS_PER_TASK': '4'}):
            self.assertEqual(benchmark.main(['task', '--batch', 'fixture', '--kind', 'assemble', '--index', '0']), 0)
        argv = invoked.call_args.args[0]
        self.assertEqual(argv[argv.index('--mode') + 1], 'deterministic')
        self.assertEqual(argv[argv.index('--threads') + 1], '4')
        self.assertEqual(argv[argv.index('--repeat') + 1], '2')

    def test_mode_runs_require_explicit_supported_configuration_before_writing(self):
        from pipeline.execution import run
        self.config = load(ROOT / 'config/determinism-modes.json')
        case = next(case for case in plan(self.config) if case['id'] == 's1-w-prk2')
        for tool, mode in [('flye', None), ('raven', 'deterministic'), ('plassembler', 'deterministic')]:
            with self.assertRaises(ValueError):
                run(case, tool, self.path, self.config, threads=4, repeat=1, mode=mode)
        self.assertFalse((self.path / 'results').exists())

    def test_modes_are_compared_separately_and_wrong_mode_provenance_is_rejected(self):
        self.config = load(ROOT / 'config/determinism-modes.json')
        tasks = self.write_repeat_panel()
        for task in tasks:
            if task['mode'] == 'deterministic':
                path = self.path / 'results' / task['scenario'] / task['tool'] / 'repeats' / task['run_id'] / 'execution.json'
                record = load(path)
                record['normalised_assembly_sha256'] = 'different-from-default-but-stable'
                save(path, record)
        summary = collect_summary(self.config, self.path)
        self.assertEqual(len(summary['within_thread']), 24)
        self.assertEqual(len(summary['across_threads']), 12)
        self.assertTrue(all(row['normalised_sequence_identical'] for row in summary['within_thread']))
        self.assertTrue(all(row['normalised_sequence_identical'] for row in summary['across_threads']))
        task = next(row for row in tasks if row['mode'] == 'deterministic')
        path = self.path / 'results' / task['scenario'] / task['tool'] / 'repeats' / task['run_id'] / 'execution.json'
        record = load(path)
        record['mode'] = 'default'
        save(path, record)
        summary = collect_summary(self.config, self.path)
        affected = next(row for row in summary['within_thread'] if row['scenario_id'] == task['scenario'] and row['tool'] == task['tool'] and row['threads'] == task['threads'] and row['mode'] == 'deterministic')
        self.assertFalse(affected['complete'])
        self.assertIsNone(affected['normalised_sequence_identical'])
        self.assertEqual(affected['status_counts']['error'], 1)

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
                      'biological_sha256': 'same-outcome',
                      **({'mode': task['mode']} if 'mode' in task else {})}
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
