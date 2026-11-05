"""Reference labels use explicit source-bound contig names, never size guesses."""
import copy
import unittest
from pipeline.contig_origins import build_contig_origins
from pipeline.result_pages import contig_section


class ContigOriginTests(unittest.TestCase):
    def setUp(self):
        self.case={'replicons':[{'refseq_accession':'fixture-chr','replicon_name':'chromosome','molecule_type':'chromosome'},
                                {'refseq_accession':'fixture-p','replicon_name':'Plasmid P','molecule_type':'plasmid'}]}
        self.record={'assembly_sha256':'a'*64,'truth_sha256':'b'*64,'tool':'flye','evaluation':{'replicons':[{'accession':'fixture-chr','exact_contigs':['c1']}]}}
        self.artifact={'input_hashes':{'assembly_sha256':'a'*64},'assembly_info':{'status':'available','source':{'role':'final'},'contigs':[{'id':'c1','length_bp':100},{'id':'c2','length_bp':50}]}}
        self.plot={'status':'available','input_hashes':{'assembly_sha256':'a'*64,'truth_sha256':'b'*64},'alignments':[{'query_id':'c2','query_length':50,'reference_id':'fixture-p'}]}

    def build(self):
        return build_contig_origins(self.case,self.record,self.artifact,self.plot)

    def test_exact_and_alignment_only_are_distinct_and_do_not_edit_sources(self):
        before=copy.deepcopy((self.case,self.record,self.artifact,self.plot))
        model=self.build()
        self.assertEqual(model['c1']['status'],'exact')
        self.assertEqual(model['c1']['references'][0]['name'],'chromosome')
        self.assertEqual(model['c2']['status'],'aligned')
        self.assertEqual(model['c2']['references'][0]['name'],'Plasmid P')
        self.assertEqual(before,(self.case,self.record,self.artifact,self.plot))

    def test_multiple_mapped_references_stay_ambiguous(self):
        self.plot['alignments'].append({'query_id':'c2','query_length':50,'reference_id':'fixture-chr'})
        model=self.build()['c2']
        self.assertEqual(model['status'],'ambiguous')
        self.assertEqual(len(model['references']),2)
        self.assertIn('shared sequence',model['reason'])

    def test_exact_sequence_association_retains_other_shared_alignment_evidence(self):
        self.plot['alignments'].append({'query_id':'c1','query_length':100,'reference_id':'fixture-p'})
        model=self.build()['c1']
        self.assertEqual(model['status'],'exact')
        self.assertEqual([r['id'] for r in model['references']],['fixture-chr'])
        self.assertEqual(model['candidate_reference_ids'],['fixture-chr','fixture-p'])

    def test_intermediate_or_unbound_inventory_receives_no_final_origin(self):
        for mutation in ('role','hash'):
            artifact=copy.deepcopy(self.artifact)
            if mutation=='role':artifact['assembly_info']['source']['role']='initial_flye'
            else:artifact['input_hashes']['assembly_sha256']='x'*64
            result=build_contig_origins(self.case,self.record,artifact,self.plot)
            self.assertTrue(all(row['status']=='unassigned' for row in result.values()))

    def test_no_name_suffix_or_length_guessing_and_no_mismatched_plot(self):
        self.plot['alignments'][0]['query_id']='other-c2'
        self.assertEqual(self.build()['c2']['status'],'unassigned')
        self.plot['alignments'][0]['query_id']='c2';self.plot['input_hashes']['assembly_sha256']='x'*64
        self.assertEqual(self.build()['c2']['status'],'unassigned')

    def test_table_shows_reference_names_and_match_evidence(self):
        self.record['report_evidence']={'contig_origins':self.build()}
        html=contig_section(self.record,self.artifact)
        for text in ('Reference origin','chromosome','Plasmid P','Exact sequence match','Alignment only','Matching evidence'):
            self.assertIn(text,html)
