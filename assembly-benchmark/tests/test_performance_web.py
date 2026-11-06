"""Broad reporting is independent of scenario exact scores and pending inputs."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import ROOT, load
from pipeline.performance_bundle import performance_model
from pipeline.performance_pages import summary_fragment, performance_page, methods_page, performance_aggregate_page


class PerformanceWebTests(unittest.TestCase):
    def setUp(self):
        self.selection = load(ROOT/'references/performance-wick/selection-50.json')
        self.snapshot = {'schema_version':1,'track':'broad-performance','panel_id':'fixture',
            'state':'preparing','dataset_count':50,'expected_executions':200,
            'tools':['flye','raven','plassembler','miniasm-plus'],'results':[]}

    def test_pending_results_are_counts_not_fake_measurements(self):
        model = performance_model(self.snapshot,self.selection)
        self.assertEqual(model['recorded_executions'],0)
        self.assertEqual([t['pending'] for t in model['tools']],[50]*4)
        self.assertIn('0 of 200 results recorded', summary_fragment(model))
        text = performance_aggregate_page(model,{'figures':[]})
        self.assertIn('No benchmark measurements',text)
        self.assertNotIn('S1',text)

    def test_completion_is_separate_from_exact_recovery(self):
        self.snapshot['results']=[{'dataset_id':self.selection['datasets'][0]['id'],'tool':'flye',
                                  'status':'complete','genome_outcome':'chromosome_complete','replicons':[]}]
        model = performance_model(self.snapshot,self.selection)
        self.assertEqual(model['tools'][0]['chromosome_complete'],1)
        self.assertEqual(model['tools'][0]['pending'],49)
        self.assertIn('Chromosome complete; plasmids incomplete',summary_fragment(model))
        self.assertNotIn('Exact status',performance_page(model))

    def test_unknown_or_duplicate_execution_is_rejected(self):
        row={'dataset_id':self.selection['datasets'][0]['id'],'tool':'flye','genome_outcome':'fully_complete'}
        self.snapshot['results']=[row,row]
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            performance_model(self.snapshot,self.selection)
        self.snapshot['results']=[dict(row,tool='miniasm')]
        with self.assertRaisesRegex(ValueError,'unknown'):
            performance_model(self.snapshot,self.selection)

    def test_dataset_and_tool_links_reach_detail_and_commands(self):
        identifier=self.selection['datasets'][0]['id']
        self.snapshot['results']=[{'dataset_id':identifier,'tool':'flye','genome_outcome':'fully_complete',
            'command':['flye','--nano-raw','<workdir>/reads.fastq.gz'],'replicons':[{'accession':'fixture',
             'contiguity':1.01,'identity':None,'max_indel_bp':None}]}]
        text=performance_page(performance_model(self.snapshot,self.selection))
        self.assertIn(f'id="{identifier}--flye"',text)
        self.assertIn(f'href="#{identifier}--flye"',text)
        self.assertIn('101.00%',text)
        self.assertIn('Commands and provenance',text)
        self.assertIn('Not measured',text)
        self.assertNotIn('0.0000%',text)
        self.assertIn('&lt;workdir&gt;',text)

    def test_methods_retain_original_simulation_assumptions(self):
        model=performance_model(self.snapshot,self.selection)
        text=methods_page(model)
        self.assertIn('tripled references',text)
        self.assertIn('99%',text)
        self.assertIn('254/246',text)
        self.assertIn('every reference molecule as circular',text)

    def test_execution_failure_reason_is_visible_without_opening_provenance(self):
        self.snapshot['results'] = [{'dataset_id':self.selection['datasets'][0]['id'],
            'tool':'raven','status':'complete','genome_outcome':'execution_error',
            'reason':'Assembler exited with code 139','replicons':[]}]
        text = performance_page(performance_model(self.snapshot,self.selection))
        self.assertIn('<p>Assembler exited with code 139</p>', text)
