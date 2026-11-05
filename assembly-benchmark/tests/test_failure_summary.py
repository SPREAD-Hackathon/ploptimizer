"""Source-bound report facts stay separate from an exact fail or a mechanism."""
import copy
import unittest
from pipeline.common import ROOT, load
from pipeline.failure_summary import failure_summary
from pipeline.result_summary import failure_facts


class FailureSummaryTests(unittest.TestCase):
    def setUp(self):
        source=load(ROOT/'published/20261104T190455.json')
        self.row=copy.deepcopy(next(r for r in source['results'] if r['scenario_id']=='s1-w-chromosome' and r['tool']=='flye-meta'))

    def test_existing_review_facts_preserved_without_new_analysis(self):
        before=copy.deepcopy(self.row);summary=failure_summary(self.row)
        self.assertEqual(summary['location_status'],'recorded')
        facts={f['label']:f for f in summary['facts']}
        self.assertEqual(facts['Recorded excess']['value'],13)
        self.assertEqual(facts['Output intervals']['value'],self.row['sequence_review']['validation']['query_intervals_0based_half_open'])
        self.assertIn('13 bp',failure_facts(self.row))
        self.assertIn('0-based',failure_facts(self.row))
        self.assertEqual(summary['mechanism_confidence'],'unresolved')
        self.assertEqual(self.row,before)

    def test_wrong_source_scope_never_earns_confirmed_locations(self):
        for field in ('scenario_id','tool','strict_status'):
            row=copy.deepcopy(self.row);row['sequence_review'][field]='other'
            self.assertEqual(failure_summary(row)['facts'],[])
        for field in ('assembly_sha256','truth_sha256'):
            row=copy.deepcopy(self.row);row['sequence_review']['hashes'][field]='other'
            self.assertEqual(failure_summary(row)['observation_confidence'],'unresolved')

    def test_full_coverage_and_length_delta_alone_do_not_invent_changes(self):
        self.row.pop('sequence_review')
        self.row['diagnostics']={'evidence':{'replicons':[{'recovered_fraction':1}]}}
        summary=failure_summary(self.row)
        self.assertFalse(summary['facts'])
        self.assertEqual(summary['location_status'],'not_recorded')
        self.assertIn('not recorded',failure_facts(self.row))
        self.row['status']='pass';self.assertIsNone(failure_summary(self.row))
        self.assertEqual(failure_facts(self.row),'')
