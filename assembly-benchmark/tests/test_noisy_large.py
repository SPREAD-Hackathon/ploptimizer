"""Large S6 orchestration reuses bytes and keeps unsupported binary claims unscored."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.assessments import assessment_mode, assess_batch, truth_controls, CONTINUOUS_MODE
from pipeline.cases import plan
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.noisy_workflow import simulate_noise, source_case, verified_frozen_source
from pipeline.reads import exact_reads


class NoisyLargeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache')
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.batch=self.root/'runs/new-batch'
        self.original=self.root/'runs/old-batch/cases/s2-toy-depth-1'
        settings=dict(load(ROOT/'config/noisy-smoke.json')['simulation'],
                      chromosome_depth=2, length_mean=100, length_sd=0,
                      length_min=100, length_max=100, minimum_breadth=0)
        old={'id':'s2-toy-depth-1','title':'Toy fixture','category':'S2',
             'simulation':settings, 'replicons':[
                 {'refseq_accession':'toy-chromosome','replicon_name':'chromosome',
                  'molecule_type':'chromosome','topology':'circular','length_bp':400},
                 {'refseq_accession':'toy-plasmid','replicon_name':'toy plasmid',
                  'molecule_type':'plasmid','topology':'circular','length_bp':100}]}
        old['fingerprint']=fingerprint(old)
        manifest=exact_reads(old,{'toy-chromosome':'ACGT'*100,'toy-plasmid':'TGCA'*25},self.original)
        self.case=copy.deepcopy(old)
        self.case.update(id='s6-toy-matched-exact',category='S6',source_case_id='s1-toy',
                         profile_id='fixture-s6',error_profile={'id':'matched-exact'})
        self.case['simulation']['model']='matched-error-v1'
        self.case['frozen_source']={'batch':'old-batch','scenario_id':'s2-toy-depth-1',
                                    'input_manifest_sha256':digest(self.original/'input.json'),
                                    **{key:manifest[key] for key in ('reads_sha256','origins_sha256','truth_sha256')}}
        self.case['fingerprint']=fingerprint({k:v for k,v in self.case.items() if k!='fingerprint'})
        self.config={'assessment_mode':CONTINUOUS_MODE}

    def test_large_profile_has_only_six_inputs_and_twenty_four_executions(self):
        config=load(ROOT/'config/noisy-large.json')
        cases=plan(config)
        self.assertEqual(len(cases),6)
        self.assertEqual(len(cases)*len(config['tools']),24)
        self.assertEqual({c['error_profile']['id'] for c in cases},{'matched-exact','generic-stress','ont2023-shaped'})
        for case in cases:
            self.assertEqual(sum(r['molecule_type']=='chromosome' for r in case['replicons']),1)
            plasmids=[r for r in case['replicons'] if r['molecule_type']=='plasmid']
            self.assertEqual(len(plasmids),1)
            self.assertGreaterEqual(plasmids[0]['length_bp'],20000)
            self.assertEqual(case['frozen_source']['batch'],'20261106T042108')
            self.assertEqual(case['simulation']['seed'],20261106)

    def test_matched_control_copies_frozen_input_without_calling_sampler(self):
        before={p.name:digest(p) for p in self.original.iterdir()}
        with patch('pipeline.reads.exact_reads',side_effect=AssertionError('Do not regenerate frozen reads')):
            result=simulate_noise(self.case,{},self.batch,self.batch/'cases'/self.case['id'])
        self.assertEqual(result['reads_sha256'],self.case['frozen_source']['reads_sha256'])
        self.assertEqual(result['reads_sha256'],result['source_fragments_sha256'])
        self.assertEqual(before,{p.name:digest(p) for p in self.original.iterdir()})
        clean=self.batch/'cases'/self.case['id']/'clean'
        self.assertEqual(digest(clean/'source-input.json'),self.case['frozen_source']['input_manifest_sha256'])
        self.assertEqual(load(clean/'input.json')['case'],source_case(self.case))

    def test_reuse_rejects_changed_geometry_file_or_source_path(self):
        changed=copy.deepcopy(self.case)
        changed['simulation']['chromosome_depth']=3
        with self.assertRaisesRegex(ValueError,'geometry'):
            verified_frozen_source(source_case(changed),self.batch)
        changed=copy.deepcopy(self.case)
        changed['frozen_source']['batch']='../old-batch'
        with self.assertRaisesRegex(ValueError,'identifiers'):
            verified_frozen_source(source_case(changed),self.batch)
        with (self.original/'reads.fastq.gz').open('ab') as out:out.write(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):
            verified_frozen_source(source_case(self.case),self.batch)

    def test_continuous_controls_admit_inputs_without_certifying_tolerant_endpoint(self):
        with patch('pipeline.cases.plan',return_value=[self.case,self.case]):
            result=truth_controls(self.config,self.batch)
        self.assertTrue(result['admitted'])
        self.assertEqual(len(result['controls']),1)
        self.assertFalse(result['binary_endpoint_validated'])
        self.assertEqual(result['kind'],'continuous-input-controls')

    def test_continuous_assessment_is_source_bound_unscored_and_never_calls_small_evaluator(self):
        save(self.batch/'config.json',self.config)
        path=self.batch/'results/toy/flye/execution.json'
        save(path,{'status':'pass','tool':'flye','assembly_sha256':'a'*64})
        hashes={'execution_sha256':digest(path),'assembly_sha256':'a'*64}
        with patch('pipeline.assessments.verified_inputs',return_value=(self.case,Path('truth'),Path('assembly'),hashes)), \
             patch('pipeline.tolerant.evaluate_tolerant',side_effect=AssertionError('Small-only evaluator cannot grade large inputs')):
            self.assertEqual(assess_batch(self.batch),{'unscored':1})
        result=load(path.parent/'tolerant.json')
        self.assertEqual(result['status'],'unscored')
        self.assertEqual(result['input_hashes'],hashes)
        self.assertFalse(result['binary_endpoint_validated'])
        self.assertEqual(result['endpoint_version'],CONTINUOUS_MODE)
        self.assertEqual(load(path)['status'],'pass')

    def test_unknown_assessment_mode_cannot_silently_fall_back(self):
        self.assertEqual(assessment_mode({}),'small-plasmid-tolerant-v1')
        with self.assertRaises(ValueError):assessment_mode({'assessment_mode':'unknown'})

    def test_submission_checkpoint_does_not_duplicate_assemblies_or_evidence(self):
        from scripts import noisy_large
        config_path=self.root/'config/noisy-large.json'
        save(config_path,load(ROOT/'config/noisy-large.json'))
        save(self.root/'config/cluster.local.json',{'host':'fixture','array_concurrency':1000})
        calls={'submit':0,'evidence':0}
        def submit_once(config,cluster):
            calls['submit']+=1
            batch=self.root/'runs/submitted-batch'
            batch.mkdir()
            record={'status':'submitted','batch_id':batch.name,'jobs':{'assemble':'101','report':'102'}}
            save(batch/'submission.json',record)
            return record
        def evidence_once(batch,cluster,comparison_label):
            calls['evidence']+=1
            self.assertEqual(comparison_label,'s6-large-v1')
            record=load(batch/'submission.json');record['jobs']['evidence']='103'
            save(batch/'submission.json',record)
        with patch.object(noisy_large,'ROOT',self.root), patch.object(noisy_large,'CONFIG',config_path), \
             patch.object(noisy_large,'CHECKPOINT',self.root/'.cache/checkpoint.json'), \
             patch.object(noisy_large,'STATUS',self.root/'evidence/status.json'), \
             patch.object(noisy_large,'ssh'),patch.object(noisy_large,'submit',side_effect=submit_once), \
             patch.object(noisy_large,'queue_evidence',side_effect=evidence_once), \
             patch.object(noisy_large.subprocess,'check_output',return_value='fixture-commit\n'):
            first=noisy_large.submit_panel()
            second=noisy_large.submit_panel()
            self.assertEqual(first['batch_id'],second['batch_id'])
            self.assertEqual(calls,{'submit':1,'evidence':1})
            changed=load(config_path);changed['threads']=1;save(config_path,changed)
            with self.assertRaisesRegex(ValueError,'checkpoint'):noisy_large.submit_panel()
            self.assertEqual(calls,{'submit':1,'evidence':1})
