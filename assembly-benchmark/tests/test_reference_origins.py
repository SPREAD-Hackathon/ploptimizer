"""Presentation associations use frozen exact results and explicit paths only."""
import copy
import unittest
from pipeline.reference_origins import build_reference_origins, reference_colour


class ReferenceOriginTests(unittest.TestCase):
    def setUp(self):
        self.case = {'replicons': [{'refseq_accession':'fixture-a','replicon_name':'A','molecule_type':'plasmid'}, {'refseq_accession':'fixture-b','replicon_name':'B','molecule_type':'plasmid'}]}
        self.record = {'tool':'flye','assembly_sha256':'a'*64,'evaluation':{'replicons':[{'accession':'fixture-a','exact_contigs':['contig-a']}]}}
        self.artifact = {'input_hashes':{'assembly_sha256':'a'*64},'graph':{'status':'available','complete':True,'source':{'role':'final','file_sha256':'b'*64},'nodes':[{'id':'segment-a'}],'paths':[{'id':'contig-a','steps':[{'segment':'segment-a','orientation':'-'}]}]}}

    def test_explicit_path_association_preserves_inputs_and_has_no_invented_intervals(self):
        before = copy.deepcopy((self.case,self.record,self.artifact))
        result = build_reference_origins(self.case,self.record,self.artifact)
        self.assertEqual(result['nodes']['segment-a']['reference_id'],'fixture-a')
        self.assertEqual(result['nodes']['segment-a']['evidence_class'],'path_inferred')
        self.assertEqual(result['nodes']['segment-a']['evidence'][0]['orientation'],'-')
        self.assertNotIn('intervals',result['nodes']['segment-a'])
        self.assertEqual(before,(self.case,self.record,self.artifact))

    def test_shared_segment_is_ambiguous(self):
        self.record['evaluation']['replicons'].append({'accession':'fixture-b','exact_contigs':['contig-b']})
        self.artifact['graph']['paths'].append({'id':'contig-b','steps':[{'segment':'segment-a','orientation':'+'}]})
        result=build_reference_origins(self.case,self.record,self.artifact)['nodes']['segment-a']
        self.assertEqual(result['status'],'ambiguous')
        self.assertIsNone(result['reference_id'])
        self.assertEqual(len(result['evidence']),2)

    def test_missing_paths_and_intermediate_unbound_graphs_remain_unassigned(self):
        variants=[]
        for changes in ({'paths':[]},{'source':{'role':'initial_flye'}},{'complete':False}):
            variant=copy.deepcopy(self.artifact);variant['graph'].update(changes);variants.append(variant)
        variant=copy.deepcopy(self.artifact);variant['input_hashes']['assembly_sha256']='c'*64;variants.append(variant)
        for artifact in variants:
            self.assertFalse(build_reference_origins(self.case,self.record,artifact)['nodes'])

    def test_whole_segment_identity_supports_origin_without_any_path(self):
        self.artifact['graph']['paths'] = []
        identities = {'file_sha256':'d'*64,'associations':[{'segment_id':'segment-a','contig_id':'contig-a','orientation':'+','length_bp':6,'sequence_sha256':'e'*64}]}
        result = build_reference_origins(self.case,self.record,self.artifact,identities)
        node = result['nodes']['segment-a']
        self.assertEqual(node['reference_id'],'fixture-a')
        self.assertEqual(node['evidence_class'],'verified_whole_segment')
        self.assertEqual(node['evidence'][0]['association_kind'],'whole_segment_sequence_identity')
        self.assertEqual(node['evidence'][0]['identity_source_sha256'],'d'*64)
        self.assertNotIn('path_id',node['evidence'][0])
        self.artifact['graph']['source']['role'] = 'initial_flye'
        self.assertFalse(build_reference_origins(self.case,self.record,self.artifact,identities)['nodes'])


    def test_saved_coordinates_require_matching_sources_and_never_project_path_segments(self):
        self.record['truth_sha256'] = 'f'*64
        plot = {'status':'available','source_kind':'recorded_paf',
                'input_hashes':{'assembly_sha256':'a'*64,'truth_sha256':'f'*64},
                'alignments':[{'query_id':'contig-a','reference_id':'fixture-a','query_interval':[0,20],
                               'reference_interval':[100,120],'strand':'-'}]}
        before=copy.deepcopy((self.record,self.artifact,plot))
        result=build_reference_origins(self.case,self.record,self.artifact,recorded_plot=plot)
        coordinates=result['contig_alignments']['contig-a']
        self.assertEqual(coordinates['scope'],'output_contig_to_reference')
        self.assertEqual(coordinates['rows'][0]['reference_interval'],[100,120])
        self.assertNotIn('reference_interval',result['nodes']['segment-a'])
        self.assertEqual(result['internal_boundaries_status'],'not_measured')
        self.assertEqual(before,(self.record,self.artifact,plot))
        plot['input_hashes']['truth_sha256']='different'
        self.assertEqual(build_reference_origins(self.case,self.record,self.artifact,recorded_plot=plot)['contig_alignments'],{})

    def test_colour_is_stable_when_other_references_are_not_selected(self):
        molecule={'refseq_accession':'NC_017662.1','molecule_type':'plasmid'}
        colour=reference_colour(molecule)
        self.assertEqual(colour,reference_colour(dict(molecule,replicon_name='renamed')))
        self.assertNotEqual(colour,reference_colour({'refseq_accession':'NC_017665.1'}))
