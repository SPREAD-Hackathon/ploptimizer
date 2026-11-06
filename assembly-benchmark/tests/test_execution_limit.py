"""Time limits and incomplete execution reporting are independent of sequence scores."""
import unittest
from pipeline.execution import execution_timeout
from pipeline.result_model import verdict
from pipeline.overview_model import _counts
from pipeline.report import badge


class ExecutionLimitTests(unittest.TestCase):
    def test_plassembler_cap_preserves_shorter_limits_and_other_tools(self):
        self.assertEqual(execution_timeout("plassembler", {"timeout_seconds": 14400}), 7200)
        self.assertEqual(execution_timeout("plassembler", {"timeout_seconds": 600}), 600)
        self.assertEqual(execution_timeout("flye", {"timeout_seconds": 14400}), 14400)

    def test_incomplete_is_a_failure_without_sequence_evaluation(self):
        row = {"status": "timeout", "execution_outcome": "did_not_complete",
               "error": "Stopped by user after two hours."}
        heading, reason = verdict(row)
        self.assertEqual(heading, "Fail — did not complete")
        self.assertEqual(reason, row["error"])
        counts = _counts([row, {"status": "pass"}])
        self.assertEqual((counts["pass"], counts["fail"], counts["errors"]), (1, 1, 0))
        self.assertNotIn("evaluation", row)
        self.assertIn("Fail — did not complete", badge("timeout"))

    def test_historical_errors_are_not_rewritten(self):
        self.assertEqual(_counts([{"status": "error"}])["errors"], 1)
