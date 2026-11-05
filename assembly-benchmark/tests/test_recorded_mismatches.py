"""Saved scalar edit counts must not turn into invented SNP locations."""
import copy
import unittest
from pipeline.recorded_coordinates import parse_coordinate_columns
from pipeline.recorded_mismatches import mismatch_summary
from pipeline.failure_summary import failure_summary
from pipeline.result_summary import failure_facts


class RecordedMismatchTests(unittest.TestCase):
    def setUp(self):
        self.data=(b'q\t100\t0\t60\t+\tr\t100\t40\t100\t58\t60\t60\tNM:i:2\tcg:Z:60M\tcs:Z:DO_NOT_EXPORT\xff\n'
                   b'q\t100\t60\t100\t+\tr\t100\t0\t40\t40\t40\t60\tNM:i:0\tcg:Z:40M\n')
        rows,_=parse_coordinate_columns(self.data,[{'id':'r','length_bp':100}])
        self.record={'scenario_id':'fixture','tool':'plassembler','status':'fail','assembly_sha256':'a','truth_sha256':'t',
                     'diagnostics':{'paf_sha256':'p'},'evaluation':{'replicons':[{'accession':'r','length_bp':100,'molecule_type':'plasmid','status':'fail'}]},
                     'initial_flye_evaluation':{'replicons':[{'accession':'r','status':'pass','exact_contigs':['initial']}]}}
        self.plot={'status':'available','source_kind':'recorded_paf','source':'synthetic saved metadata',
                   'input_hashes':{'assembly_sha256':'a','truth_sha256':'t','paf_sha256':'p'},'alignments':rows}

    def test_complete_rotated_pair_reports_two_mismatches_without_positions(self):
        original=copy.deepcopy((self.record,self.plot));summary=mismatch_summary(self.record,self.plot)
        self.assertIn('2 base mismatches',summary['summary'])
        facts={f['label']:f['value'] for f in summary['facts']}
        self.assertEqual(facts['Base mismatches'],2)
        self.assertEqual(facts['Initial Flye stage'],'Exact match recorded')
        self.assertEqual(summary['location_status'],'not_recorded')
        self.assertEqual(summary['mechanism_confidence'],'unresolved')
        self.assertNotIn('DO_NOT_EXPORT',str(self.plot))
        self.assertEqual(original,(self.record,self.plot))
        self.record['report_evidence']={'failure_summary':failure_summary(self.record,self.plot)}
        body=failure_facts(self.record)
        self.assertIn('Base mismatches',body)
        self.assertIn('Mismatch positions and base changes: not recorded.',body)
        self.assertNotIn('Confirmed by the saved review',body)

    def test_overlapping_incomplete_or_multiquery_rows_do_not_get_unique_counts(self):
        for mutate in [lambda p:p['alignments'].append(copy.deepcopy(p['alignments'][0])),
                       lambda p:p['alignments'][0].update(query_interval=[1,60]),
                       lambda p:p['alignments'][1].update(query_id='another'),
                       lambda p:p['input_hashes'].update(truth_sha256='wrong'),
                       lambda p:p['input_hashes'].update(paf_sha256='wrong')]:
            plot=copy.deepcopy(self.plot);mutate(plot)
            self.assertIsNone(mismatch_summary(self.record,plot))

    def test_missing_or_conflicting_optional_metadata_cannot_prove_substitutions(self):
        for data in [self.data.replace(b'NM:i:2',b'NM:i:1'),self.data.replace(b'cg:Z:60M',b'cg:Z:59M1I'),
                     self.data.replace(b'NM:i:2',b'NM:i:2\tNM:i:2'),self.data.replace(b'NM:i:2',b'NM:i:-2'),
                     self.data.replace(b'cg:Z:60M',b'cg:Z:DO_NOT_DECODE\xff')]:
            rows,_=parse_coordinate_columns(data,[{'id':'r','length_bp':100}])
            plot=copy.deepcopy(self.plot);plot['alignments']=rows
            self.assertIsNone(mismatch_summary(self.record,plot))

    def test_no_positive_mismatch_count_does_not_explain_a_copy_failure(self):
        for row in self.plot['alignments']:row['recorded_mismatches']=0
        self.assertIsNone(mismatch_summary(self.record,self.plot))

    def test_multiple_failed_molecules_or_copy_failures_keep_their_original_explanation(self):
        original=copy.deepcopy(self.record)
        self.record['evaluation']['replicons'].append({'accession':'another','molecule_type':'plasmid','status':'fail'})
        self.assertIsNone(mismatch_summary(self.record,self.plot))
        for key in ('exact_contigs','extra_full_copy_contigs'):
            row=copy.deepcopy(original);row['evaluation']['replicons'][0][key]=['other-contig']
            self.assertIsNone(mismatch_summary(row,self.plot))
