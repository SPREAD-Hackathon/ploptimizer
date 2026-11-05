"""Synthetic report fixtures; aggregation never reinterprets biological scores."""
import copy
from pathlib import Path
import tempfile
import unittest
from pipeline.overview import build_overview, render_home, render_family, write_overview


class OverviewTests(unittest.TestCase):
    def setUp(self):
        self.cohort = {"schema_version": 1, "primary_batches": ["primary"], "families": ["S1", "S2", "S3", "S4", "S6"], "tools": ["flye", "flye-meta", "raven", "plassembler"]}
        self.document = {"batch": "primary", "config": {}, "scenarios": [{"id": "case", "title": "Synthetic <case>", "category": "S1", "organism": "Example genome", "assembly_accession": "TEST.1"}],
                         "results": [{"scenario_id": "case", "tool": "flye", "status": "pass", "version": "1.0", "threads": 1, "evaluation": {"status": "unchanged"}}, {"scenario_id": "case", "tool": "raven", "status": "error", "tolerant_assessment": {"status": "pass"}}]}

    def build(self, documents=None, **kwargs):
        return build_overview(documents or [self.document], cohort=self.cohort, **kwargs)

    def test_exact_endpoint_is_unchanged_and_errors_are_outside_denominator(self):
        before = copy.deepcopy(self.document)
        model = self.build()
        self.assertEqual(model["counts"]["pass"], 1)
        self.assertEqual(model["counts"]["errors"], 1)
        self.assertEqual(model["counts"]["denominator"], 1)
        self.assertEqual(before, self.document)
        raven = next(t for t in model["families"][0]["tools"] if t["id"] == "raven")
        self.assertIsNone(raven["pass_fraction"])
        self.assertIn('overview-cell neutral', render_home(model))

    def test_primary_selection_and_archived_scope_have_different_links(self):
        historical = copy.deepcopy(self.document)
        historical["batch"] = "pilot"
        model = self.build([historical, self.document])
        self.assertEqual(model["excluded_batches"], ["pilot"])
        self.assertEqual(model["counts"]["total"], 2)
        self.assertEqual(model["families"][0]["records"][0]["href"], 'batches/primary/results/case--flye.html')
        archived = self.build([historical, self.document], archived_batch="pilot")
        self.assertEqual(archived["included_batches"], ["pilot"])
        self.assertEqual(archived["families"][0]["records"][0]["href"], 'results/case--flye.html')
        self.assertIn('href="../results/case--flye.html"', render_family(archived, "S1"))
        self.assertNotIn('batches/primary/', render_family(archived, "S1"))

    def test_repeats_preserved_and_s3_override_is_explicit(self):
        self.document["config"]["determinism"] = {"repeats": 2}
        self.document["results"] = [{"scenario_id": "case", "tool": "flye", "status": "fail", "threads": threads, "run_id": f"threads-{threads}-repeat-{repeat}"} for threads in (1, 4) for repeat in (1, 2)]
        model = self.build()
        self.assertEqual(model["families"][0]["counts"]["total"], 0)
        family = model["families"][2]
        self.assertEqual(family["id"], "S3")
        self.assertEqual(family["counts"]["fail"], 4)
        self.assertEqual(len({r["href"] for r in family["records"]}), 4)
        self.assertIn('separate endpoint', render_family(model, "S3"))

    def test_duplicate_and_unknown_inputs_rejected(self):
        with self.assertRaises(ValueError):
            self.build([self.document, self.document])
        self.document["results"].append(copy.deepcopy(self.document["results"][0]))
        with self.assertRaises(ValueError):
            self.build()
        self.document["results"].pop()
        self.document["results"][0]["scenario_id"] = "unknown"
        with self.assertRaises(ValueError):
            self.build()

    def test_missing_batches_explicit_and_output_does_not_replace_evidence(self):
        self.cohort["primary_batches"].append("missing")
        model = self.build()
        self.assertEqual(model["missing_batches"], ["missing"])
        self.assertIn('Counts are incomplete', render_home(model))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / 'data').mkdir()
            evidence = output / 'data/results.json'
            evidence.write_text('original scientific JSON')
            write_overview([self.document], output, cohort=self.cohort)
            self.assertEqual(evidence.read_text(), 'original scientific JSON')
            self.assertTrue((output / 'data/overview.json').exists())
            self.assertTrue((output / 'scenarios/s6.html').exists())
            body = (output / 'scenarios/s1.html').read_text()
            self.assertIn('Synthetic &lt;case&gt;', body)
            self.assertIn('../batches/primary/results/case--flye.html', body)
            self.assertNotIn('evaluation', body)


if __name__ == '__main__':
    unittest.main()
