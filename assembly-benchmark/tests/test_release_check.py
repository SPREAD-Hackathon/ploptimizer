"""Release gates use metadata only and distinguish scheduler finish from evidence readiness."""
import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_check', ROOT / 'scripts/check_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseCheckTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.cache')
        self.root = Path(self.temporary.name)
        self.batch = self.root / 'runs/test'
        self.tasks = {'simulate': ['case'], 'assemble': [{'scenario': 'case', 'tool': 'flye'}]}
        self.document = {'batch': 'test', 'config': {}, 'inputs': {'case': {'status': 'valid', 'reads_sha256': 'reads', 'truth_sha256': 'truth'}},
                         'scenarios': [{'id': 'case', 'fingerprint': 'casehash'}],
                         'results': [{'scenario_id': 'case', 'tool': 'flye', 'status': 'pass', 'evaluation': {'status': 'pass', 'endpoint': 'Synthetic metadata fixture'}, 'assembly_sha256': 'asm', 'scenario_fingerprint': 'casehash', 'reads_sha256': 'reads', 'truth_sha256': 'truth',
                                      'diagnostics': {'status': 'complete', 'evidence': {'metric_version': 'fixture'}, 'input_hashes': {'assembly_sha256': 'asm', 'reads_sha256': 'reads', 'truth_sha256': 'truth'}}}]}
        self.write(self.batch / 'submission.json', {'jobs': {'prepare': '8', 'simulate': '9', 'assemble': '10', 'report': '11'}})
        self.write(self.batch / 'diagnostic_submission.json', {'job_id': '12'})
        (self.batch / 'accounting.tsv').write_text('8|COMPLETED|0:0\n9_0|COMPLETED|0:0\n10_0|COMPLETED|0:0\n11|COMPLETED|0:0\n12|COMPLETED|0:0\n')
        self.sync()

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def sync(self):
        for row in self.document['results']:
            row.setdefault('config_fingerprint', hashlib.sha256(json.dumps(self.document['config'], sort_keys=True).encode()).hexdigest())
        self.write(self.batch / 'tasks.json', self.tasks)
        self.write(self.root / 'published/test.json', self.document)

    def check(self):
        self.sync()
        return release.check_release(self.root, ['test'])

    def test_unsubmitted_not_run_cells_do_not_block_finished_selected_tasks(self):
        self.document['results'].append({'scenario_id': 'planned', 'tool': 'flye', 'status': 'not_run'})
        result = self.check()
        self.assertTrue(result['release_ready'])
        self.assertEqual(result['batches'][0]['submitted_executions'], 1)
        self.assertEqual(result['batches'][0]['unsubmitted_not_run_rows'], 1)

    def test_finished_jobs_with_missing_diagnostic_are_not_release_ready(self):
        self.document['results'][0].pop('diagnostics')
        result = self.check()
        self.assertTrue(result['jobs_finished'])
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['release_ready'])

    def test_recorded_tool_error_is_unscored_reviewable_terminal_outcome(self):
        row = self.document['results'][0]
        row.update(status='error', error='No chromosome was identified', exit_code=1)
        row['explanation'] = self.finding()
        (self.batch / 'accounting.tsv').write_text('8|COMPLETED|0:0\n9_0|COMPLETED|0:0\n10_0|FAILED|1:0\n11|COMPLETED|0:0\n12|COMPLETED|0:0\n')
        result = self.check()
        self.assertTrue(result['release_ready'])
        self.assertEqual(result['batches'][0]['status_counts'], {'error': 1})
        self.assertEqual(result['batches'][0]['review_items'][0]['explanation'], 'No chromosome was identified')
        row.pop('error')
        self.assertFalse(self.check()['release_ready'])

    @staticmethod
    def finding():
        return {'summary': 'Recorded fixture symptom', 'symptom': 'Recorded fixture symptom',
                'interpretation': 'The internal cause remains unresolved', 'confidence': 'unresolved',
                'confidence_scope': 'Synthetic metadata fixture',
                'evidence': [{'source': 'evaluation', 'text': 'Recorded fixture evidence'}]}

    def test_generic_exact_fail_endpoint_alone_is_not_a_failure_explanation(self):
        row = self.document['results'][0]
        row.update(status='fail', evaluation={'status': 'fail', 'endpoint': 'Exact recovery required'})
        self.assertFalse(self.check()['release_ready'])
        row['explanation'] = self.finding()
        self.assertTrue(self.check()['release_ready'])

    def test_repeat_identity_cannot_match_only_scenario_and_tool(self):
        self.tasks['assemble'][0].update(run_id='threads-1-repeat-1', threads=1, repeat=1)
        result = self.check()
        self.assertFalse(result['release_ready'])
        self.assertEqual(result['batches'][0]['matched_snapshot_executions'], 0)

    def test_noisy_assessment_error_blocks_but_reasoned_unscored_is_preserved(self):
        self.document['config']['noisy_panel'] = {'profiles': ['fixture']}
        self.document['results'][0].pop('config_fingerprint', None)
        row = self.document['results'][0]
        row['tolerant_assessment'] = {'status': 'error', 'error': 'evaluator unavailable'}
        self.assertFalse(self.check()['release_ready'])
        row['tolerant_assessment'] = {'status': 'unscored', 'reason': 'Copy assignment remains ambiguous',
                                       'input_hashes': {'assembly_sha256': 'asm', 'execution_sha256': 'exec'}}
        self.assertTrue(self.check()['release_ready'])
        row['tolerant_assessment']['input_hashes']['assembly_sha256'] = 'different'
        self.assertFalse(self.check()['release_ready'])
        row['tolerant_assessment']['input_hashes']['assembly_sha256'] = 'asm'
        row['evaluation'] = {}
        self.assertFalse(self.check()['release_ready'])

    def test_missing_frozen_manifest_or_duplicate_snapshot_identity_blocks(self):
        self.document['results'].append(dict(self.document['results'][0]))
        self.assertFalse(self.check()['release_ready'])
        (self.batch / 'tasks.json').unlink()
        result = release.check_release(self.root, ['test'])
        self.assertFalse(result['release_ready'])

    def test_completed_accounting_for_wrong_array_indices_does_not_certify_selected_tasks(self):
        (self.batch / 'accounting.tsv').write_text('10_1|COMPLETED|0:0\n10_2|COMPLETED|0:0\n')
        state = release.job_state(self.batch, '10', expected_count=2)
        self.assertFalse(state['finished'])
        self.assertEqual(state['missing_indices'], [0])
        self.assertEqual(state['unexpected_indices'], [2])
