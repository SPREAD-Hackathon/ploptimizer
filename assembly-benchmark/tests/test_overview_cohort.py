"""Frozen-cohort and route contracts for the three-level results hierarchy."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from pipeline.common import ROOT, digest, load
from pipeline.overview import build_overview, render_home, render_family, write_overview
from pipeline.result_pages import result_href


class OverviewCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted((ROOT / 'published').glob('2*.json'))
        cls.documents = [load(path) for path in cls.paths]
        cls.by_batch = {document['batch']: document for document in cls.documents}
        cls.cohort = load(ROOT / 'config/overview.json')
        # These assertions describe the original frozen release, independent of
        # later admissions to the live cohort. Full-cohort counts are checked by
        # the source-derived website integration checks.
        cls.cohort['primary_batches'] = ['20261104T190455', '20261104T193551',
                                         '20261104T193612', '20261104T210453',
                                         '20261105T161510']
        cls.cohort['baseline_policy']['families'] = ['S1', 'S2', 'S3']
        cls.model = build_overview(cls.documents, cohort=cls.cohort)

    def test_primary_exact_counts_exclude_historical_pilot(self):
        counts = self.model['counts']
        self.assertEqual({key: counts[key] for key in ('total', 'pass', 'fail', 'errors', 'unscored', 'denominator')},
                         {'total': 128, 'pass': 44, 'fail': 80, 'errors': 4, 'unscored': 0, 'denominator': 124})
        self.assertEqual(self.model['endpoint'], 'recorded_exact_status')
        self.assertEqual(self.model['scope'], 'primary_cohort')
        self.assertEqual(set(self.model['included_batches']), set(self.cohort['primary_batches']))
        self.assertEqual(self.model['missing_batches'], [])
        self.assertIn('20261104T183058', self.model['excluded_batches'])
        self.assertNotIn('20261104T183058', self.model['selected_batches'])
        expected = {'S1': (52, 35, 17, 0), 'S2': (0, 0, 0, 0), 'S3': (0, 0, 0, 0),
                    'S4': (48, 6, 38, 4), 'S5': (16, 0, 16, 0), 'S6': (12, 3, 9, 0)}
        for family in self.model['families']:
            row = family['counts']
            self.assertEqual(tuple(row[key] for key in ('total', 'pass', 'fail', 'errors')), expected[family['id']])
            self.assertEqual(sum(tool['total'] for tool in family['tools']), row['total'])

    def test_every_record_keeps_version_status_identity_and_batch_link(self):
        seen, links = set(), set()
        source = {(document['batch'], row['scenario_id'], row['tool'], row.get('run_id')): row
                  for document in self.documents for row in document['results']}
        for family in self.model['families']:
            for row in family['records']:
                identity = (row['batch'], row['scenario_id'], row['tool'], row['run_id'])
                self.assertNotIn(identity, seen)
                seen.add(identity)
                original = source[identity]
                prefix = '' if row['batch'] == self.cohort.get('root_batch') else f'batches/{row["batch"]}/'
                self.assertEqual(row['href'], result_href(original, prefix))
                self.assertNotIn(row['href'], links)
                links.add(row['href'])
                self.assertEqual(row['status'], original['status'])
                self.assertEqual(row['version'], original['version'])
                self.assertTrue(row['version'].strip())
                self.assertEqual(row['threads'], original['threads'])
        self.assertEqual((len(seen), len(links)), (284, 284))

    def test_repeatability_family_overrides_input_case_category(self):
        family = next(row for row in self.model['families'] if row['id'] == 'S3')
        self.assertEqual(len(family['records']), 80)
        for row in family['records']:
            self.assertEqual(row['batch'], '20261104T193612')
            self.assertEqual(row['family'], 'S3')
            self.assertTrue(row['scenario_id'].startswith('s1-'))
            match = re.fullmatch(r'threads-(1|4)-repeat-([1-5])', row['run_id'])
            self.assertIsNotNone(match)
            self.assertEqual(row['threads'], int(match[1]))
        self.assertEqual(len({(row['tool'], row['scenario_id'], row['run_id']) for row in family['records']}), 80)

    def test_all_unscored_is_neutral_with_errors_separate(self):
        source_case = next(case for case in self.by_batch['20261104T190455']['scenarios'] if case['id'] == 's1-w-prk2')
        records = [{'scenario_id': source_case['id'], 'tool': tool, 'status': status, 'version': 'fixture'}
                   for tool, status in zip(self.cohort['tools'], ['error', 'timeout', 'running', 'not_run'])]
        fixture = {'batch': 'fixture', 'config': {}, 'scenarios': [source_case], 'results': records}
        model = build_overview([fixture], cohort=dict(self.cohort, primary_batches=['fixture'], root_batch='fixture', excluded_historical_batches=[], baseline_policy=None))
        counts = model['counts']
        self.assertEqual(tuple(counts[key] for key in ('pass', 'fail', 'errors', 'unscored', 'denominator')), (0, 0, 2, 2, 0))
        self.assertIsNone(counts['pass_fraction'])
        home = render_home(model)
        self.assertEqual(home.count('class="overview-cell neutral"'), len(self.cohort['families']) * len(self.cohort['tools']))
        self.assertNotIn('class="overview-cell fail"', home)

    def test_archived_overview_never_pools_primary_cohort(self):
        model = build_overview(self.documents, cohort=self.cohort, archived_batch='20261104T183058')
        self.assertEqual(model['scope'], 'archived_batch')
        self.assertEqual(model['included_batches'], ['20261104T183058'])
        counts = model['counts']
        self.assertEqual(tuple(counts[key] for key in ('total', 'pass', 'fail', 'errors', 'unscored')), (16, 1, 3, 0, 12))
        for family in model['families']:
            for row in family['records']:
                self.assertEqual(row['batch'], '20261104T183058')
                self.assertTrue(row['href'].startswith('results/'))
                self.assertNotIn('batches/', row['href'])

    def test_missing_selected_batch_is_explicit_and_never_invents_outcomes(self):
        documents = [document for document in self.documents if document['batch'] != '20261104T210453']
        model = build_overview(documents, cohort=self.cohort)
        self.assertEqual(model['missing_batches'], ['20261104T210453'])
        self.assertEqual(model['counts']['total'], 116)
        self.assertEqual(next(family for family in model['families'] if family['id'] == 'S6')['records'], [])
        self.assertIn('Counts are incomplete', render_home(model))

    def test_views_keep_run_diagnoses_off_home_and_every_family_record_visible(self):
        home = render_home(self.model)
        self.assertIn('overview-heatmap', home)
        self.assertNotIn('results/', home)
        self.assertNotIn('data-assembly-graph', home)
        self.assertNotIn('assembler-result', home)
        self.assertNotIn('W · Chromosome + pRK2', home)
        for family in self.model['families']:
            body = render_family(self.model, family['id'])
            self.assertIn('Assembler / version', body)
            self.assertIn('Exact status', body)
            self.assertNotIn('data-assembly-graph', body)
            for row in family['records']:
                self.assertIn('href="../' + row['href'] + '"', body)
                self.assertIn(row['status'].replace('_', ' ').title(), body)

    def test_derived_views_preserve_frozen_snapshots_and_scientific_downloads(self):
        before_files = {path: digest(path) for path in self.paths}
        before_documents = hashlib.sha256(json.dumps(self.documents, sort_keys=True).encode()).hexdigest()
        (ROOT / '.cache').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / '.cache') as temporary:
            output = Path(temporary)
            (output / 'data').mkdir()
            original_json = b'{"scientific_record":"leave unchanged"}\n'
            original_tsv = b'scientific\tmetrics\n'
            (output / 'data/results.json').write_bytes(original_json)
            (output / 'data/results.tsv').write_bytes(original_tsv)
            write_overview(self.documents, output, cohort=self.cohort)
            self.assertEqual((output / 'data/results.json').read_bytes(), original_json)
            self.assertEqual((output / 'data/results.tsv').read_bytes(), original_tsv)
            self.assertEqual(load(output / 'data/overview.json')['counts']['total'], 128)
        self.assertEqual(before_files, {path: digest(path) for path in self.paths})
        self.assertEqual(before_documents, hashlib.sha256(json.dumps(self.documents, sort_keys=True).encode()).hexdigest())
