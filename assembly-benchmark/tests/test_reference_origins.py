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

    def test_colour_is_stable_when_other_references_are_not_selected(self):
        molecule={'refseq_accession':'NC_017662.1','molecule_type':'plasmid'}
        colour=reference_colour(molecule)
        self.assertEqual(colour,reference_colour(dict(molecule,replicon_name='renamed')))
        self.assertNotEqual(colour,reference_colour({'refseq_accession':'NC_017665.1'}))
