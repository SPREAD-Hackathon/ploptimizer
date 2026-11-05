"""Existing coordinate metadata can be drawn without new sequence analyses."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import ROOT,load
from pipeline.recorded_coordinates import recorded_paf_plot,parse_coordinate_columns
from pipeline.bundle import prepare_document,export_bundle,load_bundle


class RecordedCoordinateTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.cache').mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.batch='fixture-batch'
        self.case={'id':'fixture','title':'Synthetic coordinate fixture','category':'S1','organism':'Synthetic fixture',
                   'assembly_accession':'fixture-assembly','replicons':[{'refseq_accession':'fixture-ref','replicon_name':'Fixture reference','molecule_type':'chromosome','length_bp':100}]}
        self.record={'scenario_id':'fixture','tool':'flye','status':'fail','assembly_sha256':'a'*64,'truth_sha256':'b'*64,
                     'explanation':{'confidence':'unresolved','summary':'Synthetic exact failure','interpretation':'No reviewed change recorded.'},
                     'evaluation':{'status':'fail','endpoint':'Synthetic fixture endpoint','replicons':[{'accession':'fixture-ref','name':'Fixture reference','molecule_type':'chromosome','length_bp':100,'status':'fail','exact_contigs':[]}]}}
        self.directory=self.root/self.batch/'results/fixture/flye';self.directory.mkdir(parents=True)
        self.execution=b'{"status":"fail"}\n';(self.directory/'execution.json').write_bytes(self.execution)
        self.data=b'fixture-query\t110\t0\t100\t-\tfixture-ref\t100\t0\t100\t99\t100\t60\tcs:Z:DO_NOT_EXPORT\xff\n'
        self.write_coordinates(self.data)

    def write_coordinates(self,data):
        (self.directory/'alignment.paf').write_bytes(data)
        self.record['diagnostics']={'status':'complete','batch_id':self.batch,'scenario_id':'fixture','tool':'flye','strict_status':'fail','run_id':None,
            'paf_file':'results/fixture/flye/alignment.paf','paf_sha256':hashlib.sha256(data).hexdigest(),'mapper_version':'fixture-only',
            'input_hashes':{'assembly_sha256':'a'*64,'truth_sha256':'b'*64,'execution_sha256':hashlib.sha256(self.execution).hexdigest()},
            'evidence':{'replicons':[]}}

    def plot(self):
        return recorded_paf_plot(self.case,self.record,self.batch,self.root)

    def test_only_mandatory_columns_are_preserved_and_no_software_is_run(self):
        before=copy.deepcopy(self.record)
        with patch('subprocess.run',side_effect=AssertionError('No external software')):
            result=self.plot()
        self.assertEqual(result['status'],'available')
        self.assertEqual(result['alignments'][0]['strand'],'-')
        self.assertEqual(result['alignments'][0]['query_interval'],[0,100])
        self.assertEqual(result['alignments'][0]['query_length'],110)
        self.assertNotIn('DO_NOT_EXPORT',json.dumps(result))
        self.assertEqual(result['difference_events_status'],'not_collected')
        self.assertEqual(self.record,before)

    def test_frozen_hash_mismatch_and_absence_are_distinct(self):
        (self.directory/'alignment.paf').write_bytes(b'changed')
        self.assertEqual(self.plot()['status'],'hash_mismatch')
        (self.directory/'alignment.paf').unlink()
        self.assertEqual(self.plot()['status'],'missing')
        self.assertEqual(recorded_paf_plot(self.case,self.record,self.batch,None)['status'],'not_collected')

    def test_provenance_mismatch_is_not_a_coordinate_plot(self):
        self.record['truth_sha256']='c'*64
        self.assertEqual(self.plot()['status'],'provenance_mismatch')

    def test_empty_saved_file_remains_explicitly_empty(self):
        self.write_coordinates(b'')
        result=self.plot()
        self.assertEqual(result['status'],'available')
        self.assertTrue(result['empty'])
        self.assertEqual(result['alignments'],[])

    def test_invalid_rows_reject_the_whole_source_without_sampling(self):
        self.write_coordinates(self.data+b'invalid\n')
        self.assertEqual(self.plot()['status'],'invalid')
        with self.assertRaisesRegex(ValueError,'Unknown'):
            parse_coordinate_columns(self.data,[{'id':'different-reference','length_bp':100}])

    def test_no_change_event_is_inferred_from_query_reference_length_difference(self):
        document={'schema_version':1,'batch':self.batch,'scenarios':[self.case],'results':[self.record],
                  'config':{'profile_id':'fixture','tools':['flye']}}
        prepared=prepare_document(document,artifact_root=self.root)
        details=prepared['results'][0]['report_evidence']['failure_details']
        self.assertEqual(details['recorded_change']['status'],'not_recorded')
        self.assertIsNone(details['recorded_change']['length_bp']['value'])
        self.assertEqual(details['mechanism']['confidence'],'unresolved')
        self.assertEqual(prepared['results'][0]['evaluation'],self.record['evaluation'])

    def test_export_packages_the_verified_source_and_availability_counts(self):
        document={'schema_version':1,'batch':self.batch,'scenarios':[self.case],'results':[self.record],
                  'config':{'profile_id':'fixture','tools':['flye']}}
        source=self.root/'snapshot.json';source.write_text(json.dumps(document))
        cohort={'schema_version':1,'primary_batches':[self.batch],'families':['S1'],'tools':['flye']}
        bundle=export_bundle([source],self.root/'bundle',primary_batch=self.batch,cohort=cohort,artifact_root=self.root)
        _,documents=load_bundle(bundle)
        coverage=load(bundle/'evidence-coverage.json')
        self.assertEqual(coverage['primary_cohort']['plot_status_counts'],{'available':1})
        self.assertTrue((bundle/'evidence-availability.tsv').exists())
        self.assertTrue(list((bundle/'reports').rglob('*-alignment.svg')))
        report=next((bundle/'reports').rglob('*.md')).read_text()
        self.assertIn('No reviewed sequence change is recorded',report)
        self.assertIn('All saved mandatory PAF coordinate rows',report)
        self.assertEqual(documents[0]['results'][0]['evaluation'],self.record['evaluation'])

    def test_w_review_acceptance_example_keeps_recorded_change_and_cause_separate(self):
        source=load(ROOT/'published/20261104T190455.json')
        record=next(r for r in source['results'] if r['scenario_id']=='s1-w-chromosome' and r['tool']=='flye-meta')
        source['results']=[record]
        details=prepare_document(source)['results'][0]['report_evidence']['failure_details']
        change=details['recorded_change']
        self.assertEqual(change['type']['value'],'duplicated terminal overlap')
        self.assertEqual(change['length_bp']['value'],13)
        self.assertEqual(change['output_intervals']['value'],[[0,13],[4897452,4897465]])
        self.assertEqual(change['length_bp']['source'],'sequence_review.validation.excess_bp')
        self.assertEqual(details['mechanism']['confidence'],'unresolved')
