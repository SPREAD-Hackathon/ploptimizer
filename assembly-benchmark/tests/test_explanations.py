"""Outcome explanations must preserve uncertainty and artefact-specific reviews."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from pipeline.common import digest
from pipeline.explanations import attach_explanation, explain_result


def record(fraction=1.0, identity=1.0, flags=None):
    return {"scenario_id": "s1-case", "tool": "raven", "status": "fail",
            "evaluation": {"status": "fail", "contig_count": 1, "replicons": [
                {"accession": "p", "name": "plasmid", "molecule_type": "plasmid", "status": "fail", "exact_contigs": [], "extra_full_copy_contigs": []}]},
            "diagnostics": {"status": "complete", "evidence": {"replicons": [
                {"accession": "p", "name": "plasmid", "molecule_type": "plasmid", "recovered_fraction": fraction,
                 "alignment_identity": identity, "contig_count": 1, "candidate_flags": flags or {}}]}}}


class ExplanationTests(unittest.TestCase):
    def test_verified_review_overrides_generic_mapping_and_preserves_scope(self):
        row = record(0.9701)
        review = {"status": "verified", "strict_status": "fail", "scenario_id": "s1-case", "tool": "raven",
                  "summary": "Checked five-base deletion", "explanation": "This archived sequence has a five-base deletion. The internal branch remains unresolved.",
                  "source_document": "RAVEN_CAUSE_REVIEW.md", "scope": "This archived contig only."}
        row["sequence_review"] = review
        result = explain_result(row)
        self.assertEqual(result["kind"], "reviewed_finding")
        self.assertEqual(result["interpretation"], review["explanation"])
        self.assertEqual(result["scope"], review["scope"])
        self.assertIsNone(result["mechanism_confidence"])
        self.assertEqual(result["confidence"], "confirmed")

    def test_unverified_or_mismatched_review_is_not_generalised(self):
        for changes in ({"status": "draft"}, {"tool": "flye"}, {"scenario_id": "another"}, {"strict_status": "pass"}):
            row = record()
            row["sequence_review"] = {"status": "verified", "strict_status": "fail", "tool": "raven", "scenario_id": "s1-case",
                                      "summary": "Other claim", "explanation": "Do not reuse", **changes}
            self.assertNotEqual(explain_result(row)["kind"], "reviewed_finding")

    def test_plassembler_stop_message_does_not_claim_insufficient_depth(self):
        row = {"status": "error", "tool": "plassembler", "exit_code": 1}
        result = explain_result(row, stderr_text="[ERROR] No chromosome was identified! Increase depth if appropriate.")
        self.assertEqual(result["kind"], "tool_stopped")
        self.assertEqual(result["source"], "execution_log")
        self.assertIn("does not by itself establish insufficient depth", result["interpretation"])
        self.assertNotIn("Increase depth", json.dumps(result))
        self.assertEqual(result["mechanism_confidence"], "unresolved")

    def test_successful_sequence_fail_is_not_reclassified_from_incidental_stderr(self):
        result = explain_result(record(0.5), stderr_text="No chromosome identified")
        self.assertEqual(result["kind"], "partial_aligned_recovery")

    def test_explicit_tool_stop_no_disjointigs(self):
        result = explain_result({"status": "error", "exit_code": 1}, stderr_text="No disjointigs were assembled")
        self.assertEqual(result["kind"], "tool_stopped")
        self.assertIn("without assembled contigs", result["summary"])

    def test_pipeline_error_and_generic_tool_exit_remain_distinct(self):
        result = explain_result({"status": "error", "error": "Result provenance does not match this report configuration"})
        self.assertEqual(result["kind"], "pipeline_error")
        self.assertEqual(explain_result({"status": "error", "exit_code": 2})["kind"], "tool_stopped")
        result = explain_result({"status": "error", "error": "Unknown exception"})
        self.assertEqual(result["kind"], "execution_error")
        self.assertEqual(result["confidence"], "unresolved")

    def test_scheduler_memory_and_time_limits_are_execution_outcomes(self):
        self.assertEqual(explain_result({"status": "error", "scheduler_state": "OUT_OF_MEMORY"})["kind"], "resource_stop")
        result = explain_result({"status": "timeout", "scheduler_state": "TIMEOUT"})
        self.assertEqual(result["kind"], "time_limit")
        self.assertIn("no final sequence assessment", result["interpretation"])

    def test_invalid_and_unfinished_have_no_scientific_failure_explanation(self):
        for status in ("not_run", "pending", "running"):
            self.assertEqual(explain_result({"status": status})["kind"], "awaiting_assessment")
        self.assertEqual(explain_result({"status": "invalid_input"})["kind"], "invalid_input")

    def test_pass_is_limited_to_recorded_endpoint(self):
        result = explain_result({"status": "pass"})
        self.assertEqual(result["kind"], "exact_pass")
        self.assertIn("this input", result["interpretation"])
        self.assertEqual(result["mechanism_confidence"], "unresolved")

    def test_exact_duplicate_and_embedded_full_copy_are_confirmed_observations(self):
        for exact, embedded in ((["a", "b"], []), (["a"], ["long-contig"])):
            row = record()
            row["evaluation"]["replicons"][0].update(exact_contigs=exact, extra_full_copy_contigs=embedded)
            result = explain_result(row)
            self.assertEqual(result["kind"], "exact_duplicate_or_embedded")
            self.assertEqual(result["confidence"], "confirmed")
            self.assertEqual(result["mechanism_confidence"], "unresolved")

    def test_alignment_candidate_structure_is_suspected_not_confirmed(self):
        for flag in ("fragmented", "duplicated", "joined"):
            result = explain_result(record(1, flags={flag: True}))
            self.assertEqual(result["kind"], "candidate_structure")
            self.assertEqual(result["confidence"], "suspected")
            self.assertIn(flag, result["symptom"])

    def test_partial_mapping_is_not_a_physical_absence_claim(self):
        result = explain_result(record(0.5))
        self.assertEqual(result["kind"], "partial_aligned_recovery")
        self.assertIn("not automatically physically absent", result["interpretation"])
        self.assertEqual(result["evidence"][-1]["metrics"]["recovered_fraction"], 0.5)

    def test_full_perfect_mapping_does_not_invent_five_base_difference(self):
        result = explain_result(record(1, 1))
        self.assertEqual(result["kind"], "near_full_non_exact")
        self.assertNotIn("five", json.dumps(result).lower())
        self.assertIn("assignment remain unresolved", result["interpretation"])

    def test_mapping_policy_own_near_full_threshold_is_used(self):
        row = record(0.97)
        self.assertEqual(explain_result(row)["kind"], "near_full_non_exact")
        row["diagnostics"]["evidence"]["policy"] = {"complete_fraction": 0.99}
        self.assertEqual(explain_result(row)["kind"], "partial_aligned_recovery")

    def test_no_alignment_reports_exclusions_without_inventing_identity(self):
        row = record(0, None)
        row["diagnostics"]["evidence"]["excluded_alignment_counts"] = {"secondary_or_unclassified": 3, "low_mapq": 2}
        result = explain_result(row)
        self.assertEqual(result["kind"], "no_retained_alignment")
        self.assertIn("does not prove biological absence", result["interpretation"])
        self.assertNotIn("alignment identity", result["evidence"][1]["text"])
        self.assertIn("5 alignment record", result["evidence"][-1]["text"])

    def test_failed_diagnostics_do_not_erase_strict_failure_or_invent_reason(self):
        row = record()
        row["diagnostics"] = {"status": "error", "error": "mapper failed"}
        result = explain_result(row)
        self.assertEqual(result["kind"], "unresolved_exact_failure")
        self.assertEqual(result["confidence"], "unresolved")

    def test_explicit_tolerant_pass_can_explain_non_exact_sequence_numerically(self):
        row = record()
        row["tolerant_assessment"] = {"status": "pass", "replicons": [{"accession": "p", "name": "plasmid", "status": "pass",
            "dedicated_candidates": [{"placements": [{"edit_distance": 5}]}]}]}
        result = explain_result(row)
        self.assertEqual(result["kind"], "non_exact_tolerant_recovery")
        self.assertIn("edit distance 5", result["evidence"][-1]["text"])
        self.assertEqual(result["mechanism_confidence"], "unresolved")

    def test_ambiguous_assignment_and_competing_copy_remain_supplementary(self):
        row = record()
        row["tolerant_assessment"] = {"status": "unscored", "replicons": [{"accession": "p", "ambiguous_evidence": [{"contig": "x"}], "reason": "Copy assignment unresolved"}]}
        self.assertEqual(explain_result(row)["kind"], "ambiguous_assignment")
        row["tolerant_assessment"]["replicons"][0] = {"accession": "p", "second_copy_evidence": [{"contig": "x"}], "reason": "Near-copy screen triggered"}
        result = explain_result(row)
        self.assertEqual(result["kind"], "candidate_copy")
        self.assertEqual(result["confidence"], "suspected")

    def test_plassembler_retained_chromosome_is_excluded_from_plasmid_explanation(self):
        row = record(0.5)
        row["tool"] = "plassembler"
        row["evaluation"]["replicons"].append({"accession": "chr", "molecule_type": "chromosome", "status": "fail", "exact_contigs": [], "extra_full_copy_contigs": ["something"]})
        self.assertEqual(explain_result(row)["kind"], "partial_aligned_recovery")

    def test_chromosome_only_output_criterion_is_explained_without_plasmid_label(self):
        row = {"status": "fail", "tool": "plassembler", "evaluation": {"contig_count": 1, "replicons": []}}
        self.assertEqual(explain_result(row)["kind"], "unexpected_control_output")

    def test_attachment_is_deterministic_immutable_and_audits_only_known_log_patterns(self):
        row = {"status": "error", "tool": "plassembler", "exit_code": 1}
        original = copy.deepcopy(row)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "execution.json"
            path.write_text(json.dumps(row))
            stderr = path.with_name("stderr.log")
            stderr.write_text("private arbitrary log text\nNo chromosome identified\n" + "x" * 70000 + "\nNo contigs were assembled\n")
            first = attach_explanation(row, path)
            second = attach_explanation(row, path)
            self.assertEqual(first, second)
            self.assertEqual(first["explanation_log"]["sha256"], digest(stderr))
            self.assertEqual(first["explanation"], explain_result(first))
            self.assertNotIn("private arbitrary", json.dumps(first))
            self.assertEqual(path.read_text(), json.dumps(row))
        self.assertEqual(row, original)

    def test_wrong_filename_is_not_used_as_an_arbitrary_log_reader(self):
        with self.assertRaises(ValueError):
            attach_explanation({"status": "error"}, Path("elsewhere.json"))


if __name__ == "__main__":
    unittest.main()
