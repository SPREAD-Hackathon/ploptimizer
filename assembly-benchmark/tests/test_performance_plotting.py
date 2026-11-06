"""Broad performance plots consume small recorded metrics, never sequence data."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.performance.plotting import write_performance_plots


class PerformancePlotTests(unittest.TestCase):
    def test_preparing_panel_has_tables_and_no_invented_figures(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            with patch('pipeline.performance.plotting._draw',side_effect=AssertionError('No measurements')):
                index=write_performance_plots({'tools':['flye','raven'],'datasets':[], 'results':[]},output)
            self.assertEqual(index['figures'],[])
            self.assertEqual(index['state'],'awaiting_results')
            self.assertEqual(index['assessed_executions'],0)
            self.assertEqual(len(index['tables']),3)
            self.assertTrue(all((output/table['file']).is_file() for table in index['tables']))

    def test_counts_use_broad_outcomes_and_keep_timeouts_and_unmeasured_separate(self):
        rows=[{'dataset_id':'fixture','tool':'flye','status':'complete','execution_status':'fail',
               'genome_outcome':'fully_complete','replicons':[
                   {'accession':'p','molecule_type':'plasmid','length_bp':100,
                    'contiguity':1.01,'identity':None,'identity_measured':False,'max_indel_bp':None}]},
              {'dataset_id':'fixture2','tool':'flye','status':'complete','execution_status':'timeout',
               'genome_outcome':'did_not_complete','replicons':[]},
              {'dataset_id':'fixture3','tool':'flye','status':'error','genome_outcome':None}]
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            with patch('pipeline.performance.plotting._draw'):
                index=write_performance_plots({'tools':['flye'],'datasets':[],'results':rows},output)
            summary=index['tool_summary'][0]
            self.assertEqual(summary['fully_complete'],1)
            self.assertEqual(summary['did_not_complete'],1)
            self.assertEqual(summary['assessment_errors'],1)
            with (output/'replicon-metrics.tsv').open() as stream:
                molecule=next(csv.DictReader(stream,delimiter='\t'))
            self.assertEqual(molecule['contiguity'],'1.01')
            self.assertEqual(molecule['identity'],'')
            self.assertEqual(molecule['max_indel_bp'],'')

    def test_historical_resource_values_receive_truthful_table_labels_only(self):
        record={'dataset_id':'fixture','tool':'miniasm-plus','status':'complete',
            'genome_outcome':'incomplete','elapsed_seconds':123,'peak_memory_kb':456,
            'resource_scope':'Old ambiguous label','replicons':[]}
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            with patch('pipeline.performance.plotting._draw'):
                write_performance_plots({'tools':['miniasm-plus'],'datasets':[],'results':[record]},output)
            with (output/'execution-metrics.tsv').open() as stream:
                measured=next(csv.DictReader(stream,delimiter='\t'))
        self.assertEqual(measured['elapsed_seconds'],'123')
        self.assertEqual(measured['peak_memory_kb'],'456')
        self.assertIn('input verification and exact assessment',measured['elapsed_scope'])
        self.assertIn('raw assembly and polishing',measured['elapsed_scope'])
        self.assertIn('assembler process tree',measured['memory_scope'])
        self.assertNotIn('elapsed_scope',record)
