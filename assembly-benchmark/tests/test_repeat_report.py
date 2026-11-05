"""Static S3 report checks: complete repeat evidence and honest pending states."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.cases import plan
from pipeline.common import ROOT, fingerprint, load, save
from pipeline.determinism import assembly_tasks
from pipeline.repeat_report import build_repeat


class RepeatReportTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root / "runs/repeat-fixture"
        self.config = load(ROOT / "config/determinism.json")
        self.cases = [case for case in plan(self.config) if case["id"] in self.config["determinism"]["scenarios"]]
        self.tasks = assembly_tasks(self.config, self.cases)
        save(self.batch / "tasks.json", {"assemble": self.tasks})
        save(self.batch / "submission.json", {"jobs": {"assemble": "123"}})
        (self.root / "website").mkdir()
        (self.root / "website/methods.html").write_text("<h1>Fixture methods</h1>")
        self.assets = self.root / "generated"
        self.assets.mkdir()
        (self.assets / "genomicx.js").write_text("/* fixture asset */")
        (self.assets / "genomicx.css").write_text("/* fixture asset */")
        for case in self.cases:
            save(self.batch / "cases" / case["id"] / "input.json", {
                "status": "valid", "reads_sha256": "fixed-reads-" + case["id"],
                "truth_sha256": "fixed-truth", "replicons": []})

    def render(self, *, batch=True, document=None, folder="dist"):
        output = self.root / folder
        with patch("pipeline.repeat_report.ROOT", self.root), \
             patch("pipeline.report.ROOT", self.root), \
             patch("pipeline.repeat_report.ensure_assets", return_value=self.assets):
            build_repeat(self.config, self.batch if batch else None, output, document, include_history=False)
        return output

    def write_terminal_records(self):
        cases = {case["id"]: case for case in self.cases}
        for task in self.tasks:
            # A consistently wrong assembly remains repeatable. These are
            # explicit report fixtures, not claimed assembler observations.
            record = {"status": "fail", "scenario_fingerprint": cases[task["scenario"]]["fingerprint"],
                      "config_fingerprint": fingerprint(self.config), "threads": task["threads"],
                      "repeat": task["repeat"], "reads_sha256": "fixed-reads-" + task["scenario"],
                      "truth_sha256": "fixed-truth", "assembly_sha256": "same-bytes",
                      "normalised_assembly_sha256": "same-sequence", "biological_sha256": "same-fail",
                      "elapsed_seconds": 2.5}
            save(self.batch / "results" / task["scenario"] / task["tool"] / "repeats" / task["run_id"] / "execution.json", record)

    def test_pending_report_has_eighty_rows_without_claiming_repeatability(self):
        output = self.render()
        document = load(output / "data/results.json")
        self.assertEqual(len(document["results"]), 80)
        self.assertEqual(len(document["scenarios"]), 2)
        self.assertEqual(document["results"], document["determinism"]["executions"])
        self.assertEqual({row["status"] for row in document["results"]}, {"pending"})
        html = (output / "batch-details.html").read_text()
        self.assertIn("0 of 80 executions assessed", html)
        self.assertIn("Not assessed", html)
        self.assertNotIn(">Identical<", html)
        self.assertIn("Repeatable can still be wrong", html)
        self.assertEqual(len(list((output / "scenarios").glob("s1-*.html"))), 2)
        with (output / "data/results.tsv").open() as stream:
            rows = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(len(rows), 80)
        self.assertEqual({row["threads"] for row in rows}, {"1", "4"})
        self.assertTrue((self.batch / "site/index.html").exists())

    def test_repeatability_and_biological_failure_are_separate(self):
        self.write_terminal_records()
        output = self.render()
        html = (output / "batch-details.html").read_text()
        self.assertIn("80 of 80 executions assessed", html)
        self.assertIn("80 fail", html)
        self.assertIn(">Identical<", html)
        scenario = (output / "scenarios/s1-w-prk2.html").read_text()
        self.assertIn("fixed-reads-s1-w-prk2", scenario)
        self.assertIn("fixed-truth", scenario)
        self.assertIn('data-benchmark-status="fail"', scenario)
        records = list((output / "data").glob("s1-w-prk2-flye-threads-*.json"))
        self.assertEqual(len(records), 10)
        self.assertIn("biological_sha256", load(records[0]))

    def test_snapshot_rebuild_needs_no_batch_and_retains_frozen_evidence(self):
        self.write_terminal_records()
        first = self.render()
        document = load(first / "data/results.json")
        with patch("pipeline.repeat_report.collect_summary", side_effect=AssertionError("Snapshot must not collect")):
            output = self.render(batch=False, document=document, folder="archive")
        self.assertEqual(load(output / "data/results.json"), document)
        for path in ("index.html", "scenarios/index.html", "methods.html", "about.html", "history.html", "assets/genomicx.js"):
            self.assertTrue((output / path).exists(), path)
        self.assertIn("fixed-reads-s1-w-prk2", (output / "scenarios/s1-w-prk2.html").read_text())
        self.assertIn('href="/history.html"', (output / "history.html").read_text())


if __name__ == "__main__":
    unittest.main()
