"""New size-controlled panels must not change the historical case definitions."""
import copy
import unittest

from pipeline.cases import plan
from pipeline.common import ROOT, load
from pipeline.determinism import assembly_tasks


class LargeBaselineTests(unittest.TestCase):
    def test_exact_requested_panels_and_task_counts(self):
        expected = [('baseline-large',2,8),('coverage-large',10,40),('repeatability-large',2,120)]
        for name, inputs, tasks in expected:
            config = load(ROOT / 'config' / (name + '.json'))
            cases = plan(config)
            self.assertEqual(len(cases),inputs)
            self.assertEqual(len(assembly_tasks(config,cases)),tasks)
            for case in cases:
                self.assertEqual(case['truth_type'],'derived_subset')
                self.assertTrue(all(r['length_bp'] >= 20000 for r in case['replicons'] if r['molecule_type'] == 'plasmid'))
        baseline = plan(load(ROOT / 'config/baseline-large.json'))
        self.assertTrue(all(sum(r['molecule_type']=='plasmid' for r in c['replicons']) == 3 for c in baseline))

    def test_coverage_changes_only_relative_depth_within_each_matched_input(self):
        cases = plan(load(ROOT / 'config/coverage-large.json'))
        for accession in {c['assembly_accession'] for c in cases}:
            selected = [c for c in cases if c['assembly_accession'] == accession]
            self.assertEqual({c['simulation']['plasmid_relative_depth'] for c in selected},{0.8,1,1.2,3,5})
            normalised = []
            for case in selected:
                value = copy.deepcopy(case)
                for key in ('id','title','fingerprint'):value.pop(key)
                value['simulation'].pop('plasmid_relative_depth')
                normalised.append(value)
            self.assertTrue(all(value == normalised[0] for value in normalised))

    def test_invalid_selection_cannot_silently_submit_another_panel(self):
        source = load(ROOT / 'config/baseline-large.json')
        for patch in [{'minimum_plasmid_bp':True},{'minimum_plasmid_bp':0}, {'scenario_ids':['absent']}, {'scenario_ids':[]}]:
            with self.assertRaises(ValueError):plan({**source,**patch})

    def test_historical_frozen_cases_remain_unchanged(self):
        document = load(ROOT / 'published/20261104T190455.json')
        self.assertEqual(plan(document['config']),document['scenarios'])
