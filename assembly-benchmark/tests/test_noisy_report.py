"""Noisy-read reports preserve separate endpoints and recorded measurements."""

import copy
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import ROOT, load, save
from pipeline.noisy_report import build_noisy, metrics_table, numeric_metrics


class NoisyReportTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assets = self.root / "assets-fixture"
        self.assets.mkdir()
        (self.assets / "genomicx.js").write_text("/* fixture */")
        self.config = {"noisy_panel": {"profiles": ["fixture"]}, "tools": ["flye", "flye-meta", "raven", "plassembler"], "profile_id": "s6-fixture"}
        self.case = {"id": "s6-fixture", "category": "S6", "title": "Fixture with simulated read errors",
                     "organism": "Escherichia coli", "simulation": {"model": "matched-error-v1"}}
        rows = [{"scenario_id": self.case["id"], "tool": tool, "status": "fail", "evaluation": {"status": "fail"}} for tool in self.config["tools"]]
        rows[0]["tolerant_assessment"] = {"status": "pass", "endpoint": "Recorded tolerant fixture endpoint", "metrics": {"aligned_fraction": .998, "identity": .991}, "policy": {"minimum_identity": .99}}
        rows[1]["tolerant_assessment"] = {"status": "fail", "metrics": {"aligned_fraction": .40}}
        rows[3]["tolerant_assessment"] = {"status": "error", "error": "Fixture evaluator could not read alignment"}
        self.manifest = {"status": "valid", "reads_sha256": "frozen-noisy-reads", "truth_sha256": "frozen-truth",
                         "new_quality_schema": {"observed_identity_mean": .9495, "length": {"median_bp": 8500}},
                         "noise_profile": {"label": "fixture profile", "target_identity": .95}}
        self.document = {"config": self.config, "scenarios": [self.case], "results": rows, "inputs": {self.case["id"]: self.manifest},
                         "batch": "noisy-fixture", "generated_at": "fixture time"}

    def render(self, document=None, batch=None, folder="dist"):
        with patch("pipeline.noisy_report.ROOT", self.root), patch("pipeline.report.ROOT", self.root), \
             patch("pipeline.noisy_report.ensure_assets", return_value=self.assets):
            return build_noisy(self.config, batch=batch, output=self.root / folder, document=document, include_history=False)

    def test_exact_failure_and_tolerant_pass_remain_independent(self):
        original = copy.deepcopy(self.document)
        output = self.render(self.document)
        self.assertEqual(self.document, original)
        saved = load(output / "data/results.json")
        self.assertEqual(saved["results"][0]["status"], "fail")
        self.assertEqual(saved["results"][0]["tolerant_assessment"]["status"], "pass")
        overview = (output / "index.html").read_text()
        self.assertEqual(overview.count('data-fail="1"'), 4)
        self.assertNotIn("Tolerant: 1 pass", overview)
        batch_details = (output / "batch-details.html").read_text()
        self.assertIn("Exact: 0 pass · 4 fail · 0 unscored", batch_details)
        self.assertIn("Tolerant: 1 pass · 1 fail · 2 unscored", batch_details)
        self.assertIn("exact sequence failure alone does not show that a plasmid was lost", batch_details)
        details = (output / "scenarios/s6-fixture.html").read_text()
        self.assertIn("Unscored", details)
        self.assertIn("../results/s6-fixture--raven.html", details)
        self.assertNotIn("Fixture evaluator could not read alignment", details)
        evaluator_error = (output / "results/s6-fixture--plassembler.html").read_text()
        self.assertIn("Fixture evaluator could not read alignment", evaluator_error)
        assessed = (output / "results/s6-fixture--flye.html").read_text()
        self.assertIn("Tolerant assessment policy", assessed)
        self.assertIn("Separate tolerant endpoint", assessed)
        with (output / "data/results.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(rows[0]["exact_status"], "fail")
        self.assertEqual(rows[0]["tolerant_status"], "pass")
        self.assertEqual(rows[2]["tolerant_status"], "unscored")
        self.assertEqual(rows[3]["tolerant_status"], "error")

    def test_unknown_measurement_schema_and_frozen_hashes_are_retained(self):
        output = self.render(self.document)
        details = (output / "scenarios/s6-fixture.html").read_text()
        for value in ("new_quality_schema.observed_identity_mean", "0.9495", "new_quality_schema.length.median_bp", "8500", "frozen-noisy-reads", "frozen-truth"):
            self.assertIn(value, details)
        self.assertIn("no read-quality estimate is inferred", details)
        result = (output / "results/s6-fixture--flye.html").read_text()
        self.assertIn("0.998", result)
        self.assertIn("0.991", result)
        evidence = load(output / "data/results/s6-fixture--flye.json")
        self.assertEqual(evidence["tolerant_assessment"]["metrics"]["identity"], .991)
        self.assertIn("No continuous measurements", metrics_table({}, "Empty measurements"))
        self.assertEqual(list(numeric_metrics({"bad": float("nan"), "flag": True, "quality": [.95, .96]})), [("quality[0]", "0.95"), ("quality[1]", "0.96")])

    def test_snapshot_rebuild_needs_no_cluster_and_provides_all_routes(self):
        with patch("pipeline.noisy_report.collect_records", side_effect=AssertionError("No collection for snapshot")):
            output = self.render(self.document, folder="archive")
        rebuilt = load(output / "data/results.json")
        for row in rebuilt["results"]:
            self.assertIn("explanation", row)
            row.pop("explanation")
            self.assertIn("graph_artifacts", row)
            row.pop("graph_artifacts")
        self.assertEqual(rebuilt, self.document)
        for path in ("index.html", "scenarios/index.html", "scenarios/s6-fixture.html", "methods.html", "about.html", "data/results.tsv", "assets/genomicx.js"):
            self.assertTrue((output / path).exists(), path)
        self.assertFalse((output / 'history.html').exists())
        self.assertNotIn('All batches', (output / 'index.html').read_text())
        self.assertIn("verified chemistry/basecaller", (output / "methods.html").read_text())

    def test_per_replicon_tolerant_contract_and_stage_counts_render_without_metrics_wrapper(self):
        document = copy.deepcopy(self.document)
        document["assessment_stage"] = {"status_counts": {"complete": 1, "pending": 3}}
        document["scenarios"][0]["error_profile"] = {"id": "fixture-profile", "error_model": "random", "qscore_model": "ideal", "identity_beta_percent": {"mean": 95, "maximum": 99, "sd": 2}}
        document["results"][0]["tolerant_assessment"] = {
            "status": "pass", "endpoint_version": "fixture-tolerant-v1", "limitations": "Fixture policy caveat",
            "policy": {"minimum_identity": .99}, "replicons": [{"accession": "p", "status": "pass", "reason": "Fixture dedicated molecule",
            "coverage": .9995, "identity": .994, "candidate_flags": {"joined": False}}]}
        output = self.render(document)
        scenario = (output / "scenarios/s6-fixture.html").read_text()
        self.assertIn("fixture-profile", scenario)
        details = (output / "results/s6-fixture--flye.html").read_text()
        for text in ("Tolerant molecule assessments", "Fixture dedicated molecule", "replicons[0].coverage", "0.9995", "0.994", "fixture-tolerant-v1", "Fixture policy caveat"):
            self.assertIn(text, details)
        self.assertIn("status_counts.complete", (output / "batch-details.html").read_text())
        with (output / "data/results.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertIn('"replicons"', rows[0]["tolerant_metrics_json"])

    def test_runtime_collection_includes_inputs_and_sanitises_public_records(self):
        batch = self.root / "runs/noisy-fixture"
        save(batch / "cases" / self.case["id"] / "input.json", self.manifest)
        save(batch / "provenance/versions.json", {"simulator": "fixture version"})
        rows = copy.deepcopy(self.document["results"])
        rows[0].update(host="private-host", assembly_file="/remote/assembly.fa", command=["assembler", "/remote/runs/noisy-fixture/reads.fq"])
        with patch("pipeline.noisy_report.plan", return_value=[self.case]), patch("pipeline.noisy_report.collect_records", return_value=rows):
            output = self.render(batch=batch)
        saved = load(output / "data/results.json")
        self.assertEqual(saved["inputs"][self.case["id"]], self.manifest)
        self.assertEqual(saved["provenance"], {"versions": {"simulator": "fixture version"}})
        self.assertNotIn("host", saved["results"][0])
        self.assertNotIn("assembly_file", saved["results"][0])
        self.assertEqual(saved["results"][0]["command"][1], "<workdir>/runs/noisy-fixture/reads.fq")
        self.assertTrue((batch / "site/scenarios/s6-fixture.html").exists())


if __name__ == "__main__":
    unittest.main()
