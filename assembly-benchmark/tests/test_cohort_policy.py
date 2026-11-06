"""Metadata-only eligibility, boundary conditions and historical preservation."""
import copy
import unittest
from pipeline.cohort_policy import reporting_role
from pipeline.overview_model import build_overview


class CohortPolicyTests(unittest.TestCase):
    policy = {'minimum_plasmid_bp': 20000}

    def case(self, *sizes):
        return {'id': 'control', 'category': 'S1', 'replicons': [
            {'molecule_type': 'chromosome', 'length_bp': 1000000},
            *[{'molecule_type': 'plasmid', 'length_bp': n} for n in sizes]]}

    def test_boundary_and_mixed_inputs(self):
        for sizes in [(), (20000,), (20000, 30000)]:
            self.assertEqual(reporting_role(self.case(*sizes), 'S1', self.policy), ('primary', None))
        for sizes in [(19999,), (30000, 19999), (None,)]:
            self.assertEqual(reporting_role(self.case(*sizes), 'S1', self.policy)[0], 'supplementary')
        self.assertEqual(reporting_role(self.case(), 'S2', self.policy)[0], 'supplementary')
        self.assertEqual(reporting_role(self.case(5000), 'S4', self.policy), ('primary', None))

    def test_primary_and_archive_keep_scores_and_links(self):
        case = self.case(5000)
        source = {'batch': 'fixture', 'config': {}, 'scenarios': [case], 'results': [
            {'scenario_id': 'control', 'tool': 'flye', 'status': 'fail', 'version': 'fixture'}]}
        before = copy.deepcopy(source)
        cohort = {'schema_version': 1, 'primary_batches': ['fixture'], 'families': ['S1'],
                  'tools': ['flye'], 'root_batch': 'fixture', 'baseline_policy': self.policy}
        model = build_overview([source], cohort=cohort)
        self.assertEqual(model['counts']['total'], 0)
        self.assertEqual(model['supplementary_counts']['fail'], 1)
        record = model['families'][0]['records'][0]
        self.assertEqual(record['status'], 'fail')
        self.assertEqual(record['href'], 'results/control--flye.html')
        archive = build_overview([source], cohort=cohort, archived_batch='fixture')
        self.assertEqual(archive['counts']['fail'], 1)
        self.assertEqual(source, before)

    def test_s6_revised_policy_excludes_small_plasmids_without_rewriting_history(self):
        revised = dict(self.policy, families=['S1', 'S2', 'S3', 'S6'])
        self.assertEqual(reporting_role(self.case(5360), 'S6', revised)[0], 'supplementary')
        self.assertEqual(reporting_role(self.case(100021), 'S6', revised)[0], 'primary')
        self.assertEqual(reporting_role(self.case(100021, 5360), 'S6', revised)[0], 'supplementary')
        self.assertEqual(reporting_role(self.case(), 'S6', revised)[0], 'supplementary')
        self.assertEqual(reporting_role(self.case(5360), 'S6', self.policy)[0], 'primary')

    def test_s5_uses_selected_native_assemblies_and_retires_isolated_controls(self):
        policy = dict(self.policy, families=['S5'], linear_assemblies=['GCF_036177905.1'])
        native = self.case(134326)
        native['assembly_accession'] = 'GCF_036177905.1'
        for molecule in native['replicons']:
            molecule['topology'] = 'linear'
        self.assertEqual(reporting_role(native, 'S5', policy)[0], 'primary')
        isolated = self.case(356023)
        isolated['replicons'] = isolated['replicons'][1:]
        self.assertEqual(reporting_role(isolated, 'S5', policy)[0], 'supplementary')
        native['replicons'][0]['topology'] = 'circular'
        self.assertEqual(reporting_role(native, 'S5', policy)[0], 'supplementary')
