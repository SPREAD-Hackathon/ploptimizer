"""Metadata-only imports preserve source coordinates, provenance and scores."""
import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import ROOT
from pipeline.recorded_sidecars import completed_sidecar_plot,parse_show_coords
from pipeline.bundle import export_bundle,load_bundle
from pipeline.failure_details import detail_record,markdown_detail_sections


def sha(data):return hashlib.sha256(data).hexdigest()


class RecordedSidecarTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache');self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.runs=self.root/'runs';self.batch='fixture-batch';self.label='fixture-coordinates'
        self.source_root=self.runs/self.batch/'comparisons'/self.label
        self.directory=self.source_root/'fixture/flye';self.directory.mkdir(parents=True)
        self.case={'id':'fixture','title':'Synthetic sidecar fixture','category':'S1','organism':'Synthetic fixture','assembly_accession':'fixture-assembly',
            'replicons':[{'refseq_accession':'fixture-ref','replicon_name':'Fixture reference','molecule_type':'chromosome','length_bp':100}]}
        execution=b'{"status":"fail"}\n';inputs=b'{"status":"valid"}\n'
        path=self.runs/self.batch/'results/fixture/flye/execution.json';path.parent.mkdir(parents=True);path.write_bytes(execution)
        path=self.runs/self.batch/'cases/fixture/input.json';path.parent.mkdir(parents=True);path.write_bytes(inputs)
        self.hashes={'assembly_sha256':'a'*64,'truth_sha256':'b'*64,'execution_sha256':sha(execution),'input_manifest_sha256':sha(inputs)}
        self.record={'scenario_id':'fixture','tool':'flye','status':'fail','assembly_sha256':'a'*64,'truth_sha256':'b'*64,
            'explanation':{'confidence':'unresolved','summary':'Synthetic exact failure','interpretation':'No new cause.'},
            'evaluation':{'status':'fail','endpoint':'Synthetic fixture endpoint','replicons':[{'accession':'fixture-ref','name':'Fixture reference','molecule_type':'chromosome','length_bp':100,'status':'fail','exact_contigs':[]}]},
            'tolerant_assessment':{'input_hashes':copy.deepcopy(self.hashes)}}
        document={'schema_version':1,'batch':self.batch,'scenarios':[self.case],'results':[self.record],'config':{'profile_id':'fixture','tools':['flye']}}
        self.snapshot=self.root/'snapshot.json';self.snapshot.write_text(json.dumps(document));self.snapshot_hash=sha(self.snapshot.read_bytes())
        task={'batch':self.batch,'scenario_id':'fixture','tool':'flye','assembly_sha256':'a'*64,'truth_sha256':'b'*64,'execution_sha256':sha(execution),
            'execution_relative_path':'results/fixture/flye/execution.json','output_relative_path':f'runs/{self.batch}/comparisons/{self.label}/fixture/flye'}
        manifest={'schema_version':1,'source_snapshot_sha256':self.snapshot_hash,'tasks':[task]}
        (self.source_root/'tasks.json').write_text(json.dumps(manifest))
        provenance=self.source_root/'provenance';provenance.mkdir()
        for name in ('pixi.toml','pixi.lock','compare_existing_outputs.py'):(provenance/name).write_bytes(b'Synthetic metadata only.\n')
        self.coords=b'1\t10\t20\t11\t10\t10\t99.5\t100\t110\tfixture-ref\tfixture-query\n'
        (self.directory/'coordinates.tsv').write_bytes(self.coords)
        outputs={'coordinates.tsv':sha(self.coords)}
        for name in ('nucmer.stdout.log','nucmer.stderr.log','show-coords.stderr.log'):
            (self.directory/name).write_bytes(b'');outputs[name]=sha(b'')
        self.sidecar={'schema_version':1,'status':'complete','kind':'reference_vs_existing_assembly','alignment_source':'NUCmer',
            'batch_id':self.batch,'scenario_id':'fixture','tool':'flye','original_exact_status':'fail','mapper_version':'4.0.1',
            'comparison_manifest_sha256':sha((self.source_root/'tasks.json').read_bytes()),'comparison_script_sha256':sha((provenance/'compare_existing_outputs.py').read_bytes()),
            'input_hashes':copy.deepcopy(self.hashes),'output_hashes':outputs,
            'environment':{'manifest_sha256':sha((provenance/'pixi.toml').read_bytes()),'lock_sha256':sha((provenance/'pixi.lock').read_bytes())},
            'command':['nucmer','--threads','1','--prefix','/private/user/project/runs/result','/private/user/project/runs/truth.fasta'],
            'coordinate_command':['show-coords','-THrl','/private/user/project/runs/alignment.delta'],
            'coordinate_system':'0-based half-open','original_coordinate_system':'show-coords 1-based inclusive',
            'references':[{'id':'fixture-ref','length':100}],'queries':[{'id':'fixture-query','length':110}],
            'alignment_count':1,'alignments':[{'reference_id':'fixture-ref','reference_interval':[0,10],'reference_length':100,
                'query_id':'fixture-query','query_interval':[10,20],'query_length':110,'strand':'-',
                'identity_percent':99.5,'original_endpoints_1based_inclusive':[1,10,20,11],'source_row':1}]}
        self.write_sidecar()

    def write_sidecar(self):(self.directory/'comparison.json').write_text(json.dumps(self.sidecar))

    def plot(self):return completed_sidecar_plot(self.case,self.record,self.batch,[self.source_root],self.runs,self.snapshot_hash)

    def test_import_preserves_values_and_sanitizes_public_arguments(self):
        before=(self.directory/'comparison.json').read_bytes()
        with patch('subprocess.run',side_effect=AssertionError('No tools')):plot=self.plot()
        self.assertEqual(plot['status'],'available');self.assertEqual(plot['alignments'],self.sidecar['alignments'])
        self.assertEqual(plot['source_metadata']['sidecar_sha256'],sha(before))
        self.assertEqual(plot['original_coordinates_tsv'].encode('ascii'),self.coords)
        self.assertNotIn('/private/user',json.dumps(plot));self.assertNotIn('matches',plot['alignments'][0]);self.assertNotIn('mapq',plot['alignments'][0])
        self.assertEqual((self.directory/'comparison.json').read_bytes(),before)

    def test_checksum_mismatch_is_not_a_plot(self):
        (self.directory/'coordinates.tsv').write_bytes(self.coords+b'changed');self.assertEqual(self.plot()['status'],'hash_mismatch')

    def test_repeat_comparison_uses_producer_output_path_and_original_metadata(self):
        run_id='mode-default-threads-1-repeat-1'
        self.record['run_id']=run_id
        original=self.runs/self.batch/'results/fixture/flye/execution.json'
        repeated=original.parent/'repeats'/run_id/'execution.json'
        repeated.parent.mkdir(parents=True)
        original.rename(repeated)
        old_directory=self.directory
        self.directory=old_directory/run_id
        self.directory.mkdir()
        for path in list(old_directory.iterdir()):
            if path.is_file():path.rename(self.directory/path.name)
        manifest_path=self.source_root/'tasks.json'
        manifest=json.loads(manifest_path.read_text())
        task=manifest['tasks'][0]
        task.update(run_id=run_id,execution_relative_path=f'results/fixture/flye/repeats/{run_id}/execution.json',
                    output_relative_path=f'runs/{self.batch}/comparisons/{self.label}/fixture/flye/{run_id}')
        manifest_path.write_text(json.dumps(manifest))
        self.sidecar['comparison_manifest_sha256']=sha(manifest_path.read_bytes())
        self.write_sidecar()
        self.assertEqual(self.plot()['status'],'available')
        task['run_id']='mode-default-threads-1-repeat-2'
        manifest_path.write_text(json.dumps(manifest))
        self.assertEqual(self.plot()['status'],'not_applicable')

    def test_explicit_completed_nucmer_plot_preserves_separate_paf_count_evidence(self):
        from pipeline.bundle import prepare_document
        paf = copy.deepcopy(self.plot())
        paf['source_kind'] = 'recorded_paf'
        document = json.loads(self.snapshot.read_text())
        original = copy.deepcopy(document)
        with patch('pipeline.bundle.recorded_paf_plot',return_value=paf), patch('pipeline.failure_summary.failure_summary',return_value=None) as count_summary:
            prepared = prepare_document(document,artifact_root=self.runs,coordinate_roots=[self.source_root],snapshot_hash=self.snapshot_hash)
        evidence = prepared['results'][0]['report_evidence']
        self.assertEqual(evidence['dotplot']['source_kind'],'recorded_show_coords')
        self.assertEqual(count_summary.call_args.args[1],paf)
        self.assertEqual(document,original)
        (self.directory/'coordinates.tsv').write_bytes(self.coords+b'changed')
        with patch('pipeline.bundle.recorded_paf_plot',return_value=paf):
            prepared = prepare_document(document,artifact_root=self.runs,coordinate_roots=[self.source_root],snapshot_hash=self.snapshot_hash)
        self.assertEqual(prepared['results'][0]['report_evidence']['dotplot']['source_kind'],'recorded_paf')

    def test_inconsistent_canonical_rows_are_rejected(self):
        self.sidecar['alignments'][0]['query_interval']=[0,10];self.write_sidecar();self.assertEqual(self.plot()['status'],'invalid')

    def test_source_snapshot_mismatch_is_rejected(self):
        self.assertEqual(completed_sidecar_plot(self.case,self.record,self.batch,[self.source_root],self.runs,'0'*64)['status'],'provenance_mismatch')

    def test_export_keeps_inclusive_source_and_labels_canonical_fields(self):
        cohort={'schema_version':1,'primary_batches':[self.batch],'families':['S1'],'tools':['flye']}
        bundle=export_bundle([self.snapshot],self.root/'bundle',primary_batch=self.batch,cohort=cohort,artifact_root=self.runs,coordinate_roots=[self.source_root])
        _,documents=load_bundle(bundle);base=bundle/'reports'/self.batch;slug='fixture--flye'
        self.assertEqual((base/f'{slug}-original-show-coords.tsv').read_bytes(),self.coords)
        with (base/f'{slug}-alignments.tsv').open() as stream:
            rows=list(csv.DictReader(stream,delimiter='\t'))
        self.assertEqual(rows[0]['reference_start_0based'],'0');self.assertEqual(rows[0]['identity_percent_recorded'],'99.5')
        self.assertEqual(rows[0]['matches_recorded'],'');self.assertEqual(rows[0]['mapq_recorded'],'')
        report=(base/f'{slug}.md').read_text();self.assertIn('Recorded NUCmer 4.0.1',report)
        self.assertNotIn('No NUCmer coordinate source',report);self.assertNotIn('saved PAF',report)
        for path in bundle.rglob('*'):
            if path.is_file():self.assertNotIn(b'/private/user',path.read_bytes())
        self.assertEqual(documents[0]['results'][0]['evaluation'],self.record['evaluation'])

    def test_outcome_wording_keeps_pass_and_unscored_distinct(self):
        details=detail_record(self.record,[],{'status':'not_collected'});details['outcome']['execution_status']='pass'
        text='\n'.join(markdown_detail_sections(details));self.assertIn('## Assessment detail',text)
        self.assertIn('None; saved endpoint passes.',text);self.assertNotIn('Software-internal cause:',text)
        details['outcome']['execution_status']='not_run';text='\n'.join(markdown_detail_sections(details))
        self.assertIn('No completed molecule-level assessment',text);self.assertNotIn('saved endpoint passes',text)

    def test_inclusive_parser_bounds_and_strand(self):
        self.assertEqual(parse_show_coords(self.coords)[0]['strand'],'-')
        for data in (b'invalid\n',self.coords.replace(b'1\t10\t',b'0\t10\t',1),self.coords.replace(b'99.5',b'101')):
            with self.assertRaises(ValueError):parse_show_coords(data)
