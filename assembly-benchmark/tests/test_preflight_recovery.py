"""Only a proven pre-tool socket failure permits infrastructure recovery."""
import unittest

from scripts.recover_preflight_failures import eligible


class PreflightRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.record = {'status': 'error', 'error': 'OSError: AF_UNIX path too long'}

    def test_exact_preflight_failure_is_eligible(self):
        self.assertTrue(eligible(self.record))

    def test_any_evidence_of_tool_or_input_consumption_blocks_recovery(self):
        for field in ('command', 'version', 'reads_sha256', 'truth_sha256',
                      'assembly_file', 'evaluation'):
            with self.subTest(field=field):
                self.assertFalse(eligible(dict(self.record, **{field: 'recorded'})))

    def test_software_resource_and_nonterminal_failures_are_ineligible(self):
        for change in ({'error': 'exit 139'}, {'error': 'out of memory'},
                       {'status': 'running'}, {'status': 'timeout'}):
            with self.subTest(change=change):
                self.assertFalse(eligible(dict(self.record, **change)))
