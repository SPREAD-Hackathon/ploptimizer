"""Export uses saved metadata; rendering never invokes backend assessments."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.bundle import export_bundle, load_bundle, prepare_document, saved_plot
from pipeline.common import ROOT, load


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=load(ROOT/'published/20261104T190455.json')
        cls.source=copy.deepcopy(source)
        cls.source['scenarios']=[c for c in source['scenarios'] if c['id']=='s1-w-chromosome']
        cls.source['results']=[r for r in source['results'] if r['scenario_id']=='s1-w-chromosome' and r['tool']=='flye-meta']
        cls.source['config']['tools']=['flye-meta']
        cls.cohort={'schema_version':1,'primary_batches':[source['batch']],'families':['S1'],'tools':['flye-meta']}
        (ROOT/'.cache').mkdir(exist_ok=True)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'.cache')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.snapshot=self.root/'snapshot.json'
        self.snapshot.write_text(json.dumps(self.source))

    def export(self,name='bundle'):
        return export_bundle([self.snapshot],self.root/name,primary_batch=self.source['batch'],cohort=self.cohort)

    def test_export_is_deterministic_and_has_no_external_processes_or_score_changes(self):
        before=copy.deepcopy(self.source)
        with patch('subprocess.run',side_effect=AssertionError('Export must not launch software')):
            first=self.export();second=self.export('second')
        a,documents=load_bundle(first);b,_=load_bundle(second)
        self.assertEqual(a,b)
        self.assertEqual(documents[0]['results'][0]['evaluation'],before['results'][0]['evaluation'])
        self.assertEqual(documents[0]['results'][0]['graph_artifacts'],before['results'][0]['graph_artifacts'])
        self.assertEqual(self.source,before)
        self.assertTrue((first/'summary.tsv').exists())
        report=next((first/'reports').rglob('*.md')).read_text()
        self.assertIn('13 bp duplicated terminal overlap',report)
        self.assertIn('Software-internal cause: unresolved',report)
        self.assertTrue(list((first/'reports').rglob('*-alignments.tsv')))

    def test_render_uses_bundle_without_new_findings_origins_or_source_discovery(self):
        bundle=self.export()
        from pipeline.bundle_render import render_bundle
        from pipeline import report
        original_load=report.load
        def frozen_only(path):
            if 'published' in Path(path).parts or 'runs' in Path(path).parts:
                raise AssertionError('Renderer must not discover backend sources')
            return original_load(path)
        with patch('pipeline.report.load',side_effect=frozen_only), \
             patch('pipeline.report.collect_records',side_effect=AssertionError('No collection')), \
             patch('pipeline.explanations.explain_result',side_effect=AssertionError('No new explanations')), \
             patch('pipeline.reference_origins.build_reference_origins',side_effect=AssertionError('No new origin assignments')), \
             patch('pipeline.overview.build_overview',side_effect=AssertionError('No aggregation')), \
             patch('pipeline.expected_output.reference_colour',side_effect=AssertionError('No colour reassignment')), \
             patch('pipeline.report.molecule_explanation',side_effect=AssertionError('No new mapping interpretation')), \
             patch('pipeline.report.alignment_classification',side_effect=AssertionError('No new mapping classification')):
            output=render_bundle(bundle,self.root/'website')
        page=(output/'results/s1-w-chromosome--flye-meta.html').read_text()
        self.assertIn('Saved alignment evidence',page)
        self.assertIn('not a NUCmer run',page)
        self.assertTrue((output/'data/results/s1-w-chromosome--flye-meta-alignment.svg').exists())
        self.assertTrue((output/'data/results-bundle.zip').exists())

    def test_tampering_fails_before_rendering_or_overwriting(self):
        bundle=self.export();(bundle/'summary.tsv').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'integrity'):
            load_bundle(bundle)
        with self.assertRaisesRegex(ValueError,'empty'):
            self.export()

    def test_duplicates_and_coordinate_mismatch_are_rejected(self):
        source=copy.deepcopy(self.source)
        source['results']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate execution'):
            prepare_document(source)
        record=copy.deepcopy(self.source['results'][0]);record['assembly_sha256']='0'*64
        self.assertEqual(saved_plot(record)['status'],'not_collected')
        record=copy.deepcopy(self.source['results'][0])
        record['sequence_review']['validation']['alignment_records'][0]['query_interval'][0]=-1
        with self.assertRaisesRegex(ValueError,'coordinate'):
            saved_plot(record)

    def test_atomic_replacement_retains_the_previous_bundle_if_rebuild_fails(self):
        bundle=self.export();before=(bundle/'manifest.json').read_bytes()
        bad=copy.deepcopy(self.source);bad['results']*=2
        self.snapshot.write_text(json.dumps(bad))
        with self.assertRaisesRegex(ValueError,'Duplicate execution'):
            export_bundle([self.snapshot],bundle,primary_batch=self.source['batch'],cohort=self.cohort,replace=True)
        self.assertEqual((bundle/'manifest.json').read_bytes(),before)
        load_bundle(bundle)

    def test_missing_coordinates_never_turn_into_a_plot(self):
        record=copy.deepcopy(self.source['results'][0]);record.pop('sequence_review')
        self.assertEqual(saved_plot(record)['status'],'not_collected')
