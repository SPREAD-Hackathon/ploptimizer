"""Mapping explanations retain strict outcomes and qualify incomplete evidence."""

import copy
import csv
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cases import plan
from pipeline.common import ROOT, load, write_fasta
from pipeline.diagnostics import DEFAULT_POLICY
from pipeline.report import build, diagnostic_summary, diagnostic_table, write_diagnostic_tsv
from pipeline.scoring import evaluate


def molecule(accession="p", fraction=1, kind="plasmid", **flags):
    return {"accession": accession, "name": accession, "molecule_type": kind,
            "recovered_fraction": fraction, "alignment_identity": .999 if fraction else None,
            "length_bp": 4001 if kind == "chromosome" else 1000,
            "aligned_reference_bp": round((4001 if kind == "chromosome" else 1000) * fraction),
            "contig_count": 1 if fraction else 0,
            "candidate_flags": {"no_supported_alignment": fraction == 0, "fragmented": False,
                                "duplicated": False, "joined": False, **flags}}


def diagnostic(*rows, policy=None):
    return {"status": "complete", "mapper_version": "fixture mapper", "evidence": {
        "policy": {**DEFAULT_POLICY, **(policy or {})}, "replicons": list(rows),
        "limitations": "Mapping evidence is supplementary; circular-origin splits may be missed."}}


class FailureExplanationTests(unittest.TestCase):
    def setUp(self):
        self.config = load(ROOT / "config/pilot.json")
        self.case = copy.deepcopy(plan(self.config)[2])
        self.case["id"] = "s1-fixture-p"
        self.case["title"] = "Fixture plasmid case"
        self.case["replicons"] = [
            {"refseq_accession": "c", "replicon_name": "chromosome", "molecule_type": "chromosome", "topology": "circular", "length_bp": 4001},
            {"refseq_accession": "p", "replicon_name": "p", "molecule_type": "plasmid", "topology": "circular", "length_bp": 1000}]

    def test_full_mapped_recovery_does_not_override_a_real_strict_failure(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as directory:
            root = Path(directory)
            rng = random.Random(32)
            truth = {r["refseq_accession"]: ''.join(rng.choice("ACGT") for _ in range(r["length_bp"])) for r in self.case["replicons"]}
            write_fasta(root / "truth.fa", truth)
            changed = ("A" if truth["p"][0] != "A" else "C") + truth["p"][1:]
            write_fasta(root / "assembly.fa", {"plasmid": changed})
            score = evaluate(self.case, root / "truth.fa", root / "assembly.fa")
            self.assertEqual(score["status"], "fail")
            record = {"scenario_id": self.case["id"], "tool": "flye", "status": score["status"], "evaluation": score,
                      "diagnostics": diagnostic(molecule())}
            document = {"config": {**self.config, "tools": ["flye"]}, "scenarios": [self.case], "results": [record],
                        "inputs": {}, "batch": "fixture", "generated_at": "fixture time"}
            original = copy.deepcopy(document)
            assets = root / "generated"
            assets.mkdir()
            (assets / "genomicx.js").write_text("/* fixture */")
            (root / "website").mkdir()
            (root / "website/methods.html").write_text("<h1>Fixture methods</h1>")
            with patch("pipeline.report.ROOT", root), patch("pipeline.report.ensure_assets", return_value=assets):
                output = build(document["config"], output=root / "dist", document=document, include_history=False)
            self.assertEqual(document, original)
            saved = load(output / "data/results.json")
            self.assertEqual(saved["results"][0]["status"], "fail")
            self.assertEqual(saved["results"][0]["evaluation"]["status"], "fail")
            overview = (output / "index.html").read_text()
            self.assertIn('data-status="fail"', overview)
            self.assertIn("Full aligned recovery; exact recovery failed", overview)
            self.assertIn('href="data/recovery-evidence.tsv"', overview)
            details = (output / "scenarios/s1-fixture-p.html").read_text()
            self.assertIn("100.00%", details)
            self.assertIn("The exact endpoint still fails", details)
            self.assertIn("mapQ ≥20", details)
            self.assertIn("identity ≥90%", details)

    def test_no_retained_alignment_never_proves_absence(self):
        evidence = diagnostic(molecule(fraction=0))
        record = {"tool": "flye", "status": "fail", "diagnostics": evidence}
        self.assertIn("No retained alignment", diagnostic_summary(record, self.case))
        self.assertIn("absence not established", diagnostic_summary(record, self.case))
        details = diagnostic_table(evidence)
        self.assertIn("not evidence of plasmid absence", details)
        self.assertIn("filtering or alignment heuristics", details)
        self.assertNotIn("plasmid is absent", details)

    def test_near_full_partial_and_candidate_flags_are_separate_evidence(self):
        near = {"tool": "raven", "status": "fail", "diagnostics": diagnostic(molecule(fraction=.97))}
        self.assertIn("Near-full aligned recovery; exact recovery failed", diagnostic_summary(near, self.case))
        partial = {"tool": "flye", "status": "fail", "diagnostics": diagnostic(molecule(fraction=.70, fragmented=True, duplicated=True, joined=True))}
        compact = diagnostic_summary(partial, self.case)
        self.assertIn("Partial aligned recovery", compact)
        self.assertIn("candidate fragmentation, duplication, join", compact)
        details = diagnostic_table(partial["diagnostics"])
        self.assertIn("70.00%", details)
        self.assertIn("not confirmed structural errors", details)
        self.assertIn("union gain of at least 5%", details)
        self.assertIn("overlapping reference coverage ≥20%", details)
        self.assertIn("at most 20%", details)
        custom = diagnostic(molecule(fraction=.97), policy={"complete_fraction": .99})
        self.assertIn("Partial aligned recovery", diagnostic_summary({**near, "diagnostics": custom}, self.case))

    def test_final_plasmid_output_does_not_misclassify_omitted_chromosome(self):
        evidence = diagnostic(molecule("c", 0, kind="chromosome"), molecule("p", 1))
        record = {"tool": "plassembler", "status": "pass", "diagnostics": evidence}
        self.assertNotIn("No retained alignment", diagnostic_summary(record, self.case))
        details = diagnostic_table(evidence, plasmid_only=True)
        self.assertIn("retained chromosome recovery is assessed separately", details)
        self.assertNotIn("not evidence of chromosome absence", details)
        self.assertNotIn("No retained alignment", details)
        chromosome_only = {**self.case, "replicons": self.case["replicons"][:1]}
        self.assertIn("chromosome assessed separately", diagnostic_summary(record, chromosome_only))
        self.assertNotIn("No retained alignment", diagnostic_summary(record, chromosome_only))

    def test_failed_chromosome_does_not_hide_successful_plasmid_mapping(self):
        record = {"tool": "flye", "status": "pass", "diagnostics": diagnostic(molecule("c", 0, kind="chromosome"), molecule()),
                  "evaluation": {"replicons": [{"accession": "c", "status": "fail"}, {"accession": "p", "status": "pass"}]}}
        summary = diagnostic_summary(record, self.case)
        self.assertIn("Full aligned recovery", summary)
        self.assertNotIn("No retained alignment", summary)
        self.assertNotIn("exact recovery failed", summary)

    def test_mapper_error_pending_and_unavailable_remain_distinct(self):
        base = {"tool": "flye", "status": "fail"}
        self.assertEqual(diagnostic_summary(base, self.case), "Recovery diagnostics not available")
        self.assertEqual(diagnostic_summary({**base, "diagnostics": {"status": "pending"}}, self.case), "Recovery mapping pending")
        error = {"status": "error", "error": "Minimap2 exited with code 1"}
        self.assertEqual(diagnostic_summary({**base, "diagnostics": error}, self.case), "Mapper diagnostic error")
        self.assertIn("Minimap2 exited with code 1", diagnostic_table(error))
        self.assertNotIn("No retained alignment", diagnostic_table(error))
        self.assertEqual(diagnostic_summary({**base, "status": "running"}, self.case), "Awaiting assembly assessment")

    def test_molecule_tsv_retains_strict_status_and_omits_unassessed_chromosome(self):
        record = {"scenario_id": self.case["id"], "tool": "plassembler", "status": "fail",
                  "diagnostics": diagnostic(molecule("c", 0, kind="chromosome"), molecule("p", .7, fragmented=True)),
                  "evaluation": {"replicons": [{"accession": "p", "status": "fail"}, {"accession": "c", "status": "fail"}]}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "data").mkdir()
            write_diagnostic_tsv(output, [self.case], [record])
            with (output / "data/recovery-evidence.tsv").open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["accession"], "p")
        self.assertEqual(rows[0]["strict_status"], "fail")
        self.assertEqual(rows[0]["aligned_reference_fraction"], "0.7")
        self.assertEqual(rows[0]["candidate_fragmentation"], "True")
        self.assertEqual(rows[0]["minimum_mapq"], "20")


if __name__ == "__main__":
    unittest.main()
