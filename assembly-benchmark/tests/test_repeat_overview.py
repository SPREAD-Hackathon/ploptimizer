"""Repeatability is independent of reference recovery and file-byte differences."""
import copy
import unittest
from pipeline.overview import build_overview, render_home, render_family
from pipeline.repeat_report import summary_table, unrun_summary


class RepeatOverviewTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "case", "title": "Example input", "category": "S1", "organism": "Example", "assembly_accession": "TEST.1"}
        self.group = {"scenario_id": "case", "tool": "flye", "threads": 1, "complete": True,
                      "inputs_identical": True, "normalised_sequence_identical": True, "byte_identical": False,
                      "expected_runs": 2, "scored_runs": 2}
        self.document = {"batch": "primary", "config": {"determinism": {"repeats": 2}}, "scenarios": [self.case],
                         "results": [{"scenario_id": "case", "tool": "flye", "status": "fail", "threads": 1, "run_id": f"repeat-{r}"} for r in (1, 2)],
                         "determinism": {"within_thread": [self.group], "across_threads": []}}
        self.cohort = {"schema_version": 1, "primary_batches": ["primary"], "families": ["S3"], "tools": ["flye"]}

    def build(self):
        return build_overview([self.document], cohort=self.cohort)

    def test_headline_uses_saved_sequence_agreement_not_failures_or_file_bytes(self):
        before = copy.deepcopy(self.document)
        model = self.build()
        family = model["families"][0]
        self.assertEqual(family["repeatability"], {"identical": 1, "different": 0, "not_assessed": 0, "total": 1})
        self.assertEqual(family["counts"]["fail"], 2)
        self.assertIn('1 identical · 0 different', render_home(model))
        page = render_family(model, "S3")
        self.assertIn('Default', page)
        self.assertIn('Deterministic-mode results have not been collected', page)
        self.assertIn('Different</td><td>Identical', page)
        self.assertIn('<details><summary>Reference recovery for individual runs', page)
        self.assertEqual(before, self.document)

    def test_incomplete_or_unverified_inputs_are_not_assessed_and_modes_stay_separate(self):
        incomplete = {**self.group, "threads": 4, "complete": False, "normalised_sequence_identical": False}
        unverified = {**self.group, "inputs_identical": False}
        deterministic = {**self.group, "mode": "deterministic", "normalised_sequence_identical": False}
        self.document["determinism"]["within_thread"] = [incomplete, unverified, deterministic]
        family = self.build()["families"][0]
        self.assertEqual(family["repeatability"], {"identical": 0, "different": 1, "not_assessed": 2, "total": 3})
        self.assertEqual([g["mode"] for g in family["repeatability_groups"]], ["default", "default", "deterministic"])
        self.assertNotIn('>Identical</td>', summary_table([unverified], [self.case]))

    def test_planned_mode_groups_are_unassessed_without_results(self):
        config = {"tools": ["flye", "raven"], "determinism": {"scenarios": ["case"], "threads": [1, 4], "repeats": 2,
                  "modes": {"flye": ["default", "deterministic"], "raven": ["default"]}}}
        summary = unrun_summary(config, [self.case])
        self.assertEqual(len(summary['within_thread']), 6)
        self.assertEqual(len(summary['across_threads']), 3)
        self.assertEqual(summary['expected_runs'], 12)
        self.assertTrue(all(g['inputs_identical'] is None and not g['complete'] for g in summary['within_thread']))


if __name__ == '__main__':
    unittest.main()
