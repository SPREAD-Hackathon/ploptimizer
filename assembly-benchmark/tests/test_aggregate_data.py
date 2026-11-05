"""Aggregate reporting preserves saved outcomes, missingness and cohort separation."""
import copy
import unittest
from pipeline.aggregate_data import aggregate_data, number


class AggregateDataTests(unittest.TestCase):
    def fixture(self):
        case = {'id':'case','replicons':[{'refseq_accession':'reference','molecule_type':'plasmid','length_bp':30000,'topology':'circular'}]}
        record = {'scenario_id':'case','tool':'flye','status':'fail','elapsed_seconds':5,'peak_memory_kb':1024,
                  'reads_sha256':'reads','evaluation':{'replicons':[{'accession':'reference','molecule_type':'plasmid','length_bp':30000,'status':'fail'}]},
                  'diagnostics':{'status':'complete','evidence':{'replicons':[{'accession':'reference','recovered_fraction':1.0,'alignment_identity':1.0}]}},
                  'report_evidence':{'required_accessions':['reference']}}
        doc = {'batch':'batch','scenarios':[case],'results':[record], 'inputs':{'case':{'reads_sha256':'reads','replicons':[{'accession':'reference','achieved_depth':30,'mean_read_length':10000}]}}}
        row = {'batch':'batch','scenario_id':'case','tool':'flye','run_id':None,'family':'S1','cohort_role':'supplementary'}
        overview = {'families':[{'records':[row]}],'tools':[{'id':'flye','label':'Flye'}]}
        return doc, overview

    def test_full_mapping_never_promotes_exact_failure_or_changes_source(self):
        doc, overview = self.fixture(); before=copy.deepcopy(doc)
        data=aggregate_data([doc], overview)
        self.assertEqual(data['molecules'][0]['exact_status'],'fail')
        self.assertEqual(data['molecules'][0]['aligned_reference_fraction'],1.0)
        self.assertEqual(data['groups'][0]['id'],'s1-supplementary')
        self.assertEqual(doc,before)

    def test_input_histograms_deduplicate_assembler_executions_and_missing_stays_missing(self):
        doc, overview=self.fixture()
        second=copy.deepcopy(doc['results'][0]);second['tool']='raven';second.pop('peak_memory_kb');second['diagnostics']={}
        doc['results'].append(second)
        row=copy.deepcopy(overview['families'][0]['records'][0]);row['tool']='raven';overview['families'][0]['records'].append(row)
        data=aggregate_data([doc],overview)
        self.assertEqual(len(data['inputs']),1)
        self.assertEqual(len(data['executions']),2)
        self.assertIsNone(data['executions'][1]['peak_memory_kib'])
        self.assertIsNone(data['molecules'][1]['aligned_reference_fraction'])
        self.assertIsNone(number(True));self.assertIsNone(number(float('nan')))

    def test_unselected_historical_records_are_excluded(self):
        doc, overview=self.fixture();historical=copy.deepcopy(doc);historical['batch']='old'
        data=aggregate_data([doc,historical],overview)
        self.assertEqual(len(data['executions']),1)
