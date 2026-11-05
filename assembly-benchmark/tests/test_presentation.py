"""First-release copy separates recorded outcomes, support and causal certainty."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cases import plan
from pipeline.common import ROOT, load
from pipeline.report import batch_progress, build, diagnostic_summary, explained_records, finding_panel, interpretation_guide


def explanation(confidence="suspected", symptom="Near-full mapped sequence; exact recovery failed"):
    return {"summary": symptom, "symptom": symptom, "confidence": confidence,
            "confidence_scope": "Saved mapping supports a sequence symptom, not a causal mechanism.",
            "interpretation": "Sequence is retained; exact unique recovery is a separate endpoint.",
            "mechanism_confidence": "unresolved", "evidence": [{"text": "97.5% mapped reference coverage", "source": "diagnostics.json"}]}


class PresentationTests(unittest.TestCase):
    def test_complete_failed_and_unrun_states_are_not_conflated(self):
        self.assertEqual(batch_progress([]), "No comparisons recorded.")
        self.assertIn("Complete: all 2", batch_progress([{"status": "pass"}, {"status": "fail"}]))
        self.assertIn("Runs finished: 1 sequence assessments; 1 execution errors", batch_progress([{"status": "fail"}, {"status": "error"}]))
        self.assertIn("In progress: 1 assessed; 1 queued or running", batch_progress([{"status": "pass"}, {"status": "pending"}]))
        self.assertEqual(batch_progress([{"status": "not_run"}]), "0 assessed; 1 not run; 0 unscored execution outcomes.")
        self.assertNotIn("Complete", batch_progress([{"status": "not_run"}]))

    def test_suspected_cause_and_verified_symptom_have_distinct_labels(self):
        record = {"status": "fail", "explanation": explanation()}
        html = finding_panel(record)
        self.assertIn("Suspected explanation", html)
        self.assertIn("97.5% mapped reference coverage", html)
        self.assertIn("Source: diagnostics.json", html)
        self.assertIn("software-internal cause remains unresolved", html)
        confirmed = finding_panel({**record, "explanation": explanation("confirmed")})
        self.assertIn("Verified observation", confirmed)
        self.assertNotIn("Confirmed cause", confirmed)
        self.assertIn("software-internal cause remains unresolved", confirmed)
        self.assertIn("<details><summary>", finding_panel(record, compact=True))

    def test_checked_review_retains_scope_and_safe_source_link(self):
        record = {"status": "fail", "explanation": explanation("confirmed"), "sequence_review": {
            "source_document": "RAVEN_CAUSE_REVIEW.md", "scope": "Only this saved contig; internal trimming branch remains uninstrumented."}}
        html = finding_panel(record)
        self.assertIn("/RAVEN_CAUSE_REVIEW.md", html)
        self.assertIn("Only this saved contig", html)
        record["sequence_review"]["source_document"] = "javascript:alert(1)"
        self.assertNotIn("javascript:", finding_panel(record))
        record["explanation"]["symptom"] = "<script>alert(1)</script>"
        self.assertNotIn("<script>", finding_panel(record))
        self.assertIn("&lt;script&gt;", finding_panel(record))

    def test_legend_prevents_absence_and_candidate_errors_becoming_confirmed_claims(self):
        html = interpretation_guide()
        self.assertIn("absence is not established", html)
        self.assertIn("not a confirmed structural error", html)
        self.assertIn("does not automatically establish its software-internal cause", html)
        self.assertIn("Job errors, invalid inputs and missing assessments are unscored", html)
        self.assertEqual(finding_panel({"status": "running"}), '<p class="muted">No completed result to explain yet.</p>')

    def test_archive_enrichment_needs_no_local_logs_and_keeps_richer_explanations(self):
        from pipeline.explanations import attach_explanation
        case = plan(load(ROOT / "config/pilot.json"))[2]
        existing = {"scenario_id": case["id"], "tool": "flye", "status": "error", "explanation": explanation(),
                    "explanation_log": {"sha256": "saved-log-hash", "observations": []}}
        missing = {"scenario_id": case["id"], "tool": "raven", "status": "fail"}
        original = copy.deepcopy([existing, missing])
        with patch("pipeline.explanations.attach_explanation", wraps=attach_explanation) as attach:
            enriched = explained_records([existing, missing], [case])
        self.assertEqual([existing, missing], original)
        self.assertEqual(enriched[0]["explanation"], original[0]["explanation"])
        self.assertEqual(enriched[0]["explanation_log"], original[0]["explanation_log"])
        self.assertIn("explanation", enriched[1])
        self.assertEqual(enriched[1]["status"], "fail")
        attach.assert_called_once()
        self.assertIsNone(attach.call_args.kwargs.get("execution_path"))

    def test_checked_review_supersedes_generic_archive_explanation(self):
        case = plan(load(ROOT / "config/pilot.json"))[2]
        record = {"scenario_id": case["id"], "tool": "raven", "status": "fail", "explanation": explanation(),
                  "sequence_review": {"status": "verified", "strict_status": "fail", "summary": "Checked saved deletion",
                                      "explanation": "The saved sequence has a checked deletion.", "scope": "Only this saved contig."}}
        enriched = explained_records([record], [case])[0]
        self.assertEqual(enriched["explanation"]["source"], "curated_review")
        self.assertEqual(enriched["explanation"]["summary"], "Checked saved deletion")
        self.assertEqual(enriched["explanation"]["scope"], "Only this saved contig.")
        self.assertEqual(record["explanation"], explanation())

    def test_overview_and_downloads_keep_exact_status_when_explanation_is_near_recovery(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        config = load(ROOT / "config/pilot.json")
        case = plan(config)[2]
        tool = "flye"
        record = {"scenario_id": case["id"], "tool": tool, "status": "fail", "explanation": explanation(),
                  "started_at": "fixture-time", "evaluation": {"status": "fail", "endpoint": "One exact dedicated plasmid",
                  "replicons": [{"accession": case["replicons"][1]["refseq_accession"], "name": "pRK2", "molecule_type": "plasmid", "status": "fail", "reason": "No exact dedicated molecule"}]}}
        config["tools"] = [tool]
        document = {"config": config, "scenarios": [case], "results": [record], "inputs": {}, "batch": "fixture", "generated_at": "fixture-time"}
        original = copy.deepcopy(document)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as folder:
            root = Path(folder)
            assets = root / "generated"
            assets.mkdir()
            (assets / "genomicx.js").write_text("/* fixture */")
            (root / "website").mkdir()
            (root / "website/methods.html").write_text("<h1>Fixture methods</h1>")
            with patch("pipeline.report.ROOT", root), patch("pipeline.report.ensure_assets", return_value=assets):
                output = build(config, output=root / "dist", document=document, include_history=False)
            overview = (output / "index.html").read_text()
            self.assertIn("Whole-scenario exact recovery", overview)
            self.assertIn("Chromosome-only controls use their declared endpoints", overview)
            self.assertIn("not a general assembler ranking", overview)
            self.assertIn("0 pass · 1 fail", overview)
            self.assertIn("Suspected: Near-full mapped sequence", overview)
            details = (output / "scenarios" / (case["id"] + ".html")).read_text()
            self.assertIn("Original exact-sequence assessment", details)
            self.assertIn("Suspected explanation", details)
            self.assertIn('data-benchmark-status="fail"', details)
            saved = load(output / "data" / (case["id"] + "-flye.json"))
            self.assertEqual(saved["status"], "fail")
            self.assertEqual(saved["explanation"]["confidence"], "suspected")
            self.assertEqual(load(output / "data/results.json")["results"][0]["evaluation"]["status"], "fail")
        self.assertEqual(document, original)
        self.assertIn("Suspected:", diagnostic_summary(record, case))


if __name__ == "__main__":
    unittest.main()
