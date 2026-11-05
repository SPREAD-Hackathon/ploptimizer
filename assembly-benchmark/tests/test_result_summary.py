"""Presentation must not confuse mapping, endpoint scope or execution failures."""

import copy
import unittest

from pipeline.result_summary import outcome_section, verdict


class ResultSummaryTests(unittest.TestCase):
    def record(self):
        return {"tool": "flye", "status": "fail", "evaluation": {"replicons": [
            {"accession": "c", "name": "chromosome", "length_bp": 1000, "molecule_type": "chromosome", "status": "fail", "exact_contigs": []},
            {"accession": "p", "name": "fixture plasmid", "length_bp": 100, "molecule_type": "plasmid", "status": "fail", "exact_contigs": []}]},
            "diagnostics": {"evidence": {"replicons": [
                {"accession": "c", "recovered_fraction": 0.99, "contig_count": 2},
                {"accession": "p", "recovered_fraction": 0, "contig_count": 0}]}}}

    def test_plasmid_failure_leads_and_zero_mapping_never_becomes_proven_absence(self):
        record = self.record()
        original = copy.deepcopy(record)
        body = outcome_section(record)
        self.assertIn("Fail — fixture plasmid (100 bp) not recovered exactly", body)
        self.assertLess(body.index('<h3>fixture plasmid'), body.index('<h3>chromosome'))
        self.assertIn("supporting context", body)
        self.assertIn("0.00%", body)
        self.assertIn("does not establish that the sequence is absent", body)
        self.assertIn("Not established by the saved evidence", body)
        self.assertEqual(record, original)

    def test_pass_does_not_invent_a_failure_to_explain(self):
        record = self.record()
        record["status"] = "pass"
        record["evaluation"]["replicons"][1].update(status="pass", exact_contigs=["p1"])
        body = outcome_section(record)
        self.assertIn("Pass — exact recovery", body)
        self.assertNotIn("Why did the assembler do this?", body)
        self.assertNotIn("internal cause", body)

    def test_full_mapping_does_not_turn_a_strict_failure_into_a_pass(self):
        record = self.record()
        record["diagnostics"]["evidence"]["replicons"][1]["recovered_fraction"] = 1
        body = outcome_section(record)
        self.assertIn("100.00%", body)
        self.assertIn("Fail — fixture plasmid", body)
        self.assertIn("An alignment is not an exact-copy test", body)

    def test_execution_error_and_negative_control_use_their_own_endpoints(self):
        record = self.record()
        record.update(status="error", error="Synthetic stopped run")
        heading, text = verdict(record)
        self.assertEqual(heading, "No completed exact assessment")
        self.assertEqual(text, "Synthetic stopped run")
        self.assertNotIn('class="molecule-evidence"', outcome_section(record))
        record.update(status="pass", tool="plassembler", evaluation={"replicons": []})
        self.assertIn("negative control", verdict(record)[0])

    def test_verified_review_is_preserved_and_html_is_escaped(self):
        record = self.record()
        record.update(scenario_id="fixture",assembly_sha256="a",truth_sha256="t")
        record["sequence_review"] = {"status":"verified","strict_status":"fail","scenario_id":"fixture","tool":"flye","hashes":{"assembly_sha256":"a","truth_sha256":"t"},"summary":"Checked <synthetic> mismatch"}
        body = outcome_section(record)
        self.assertIn("Checked &lt;synthetic&gt; mismatch", body)
        self.assertNotIn("Not established by the saved evidence", body)

    def test_unbound_verified_flag_does_not_claim_a_checked_mismatch(self):
        record=self.record()
        record['sequence_review']={'status':'verified','summary':'Unbound mismatch claim'}
        body=outcome_section(record)
        self.assertNotIn('Unbound mismatch claim',body)
        self.assertNotIn('The checked mismatch',body)
        self.assertIn('Not established by the saved evidence',body)


if __name__ == "__main__":
    unittest.main()
