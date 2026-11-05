"""Release guards reject realistic regressions without touching cluster or network."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pipeline.common import digest, save
from pipeline.site_gate import check_site, check_release, write_site_receipt


class SiteGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.site=self.root/'site';self.site.mkdir()
        (self.site/'index.html').write_text('<main id="main"><a href="/case#evidence">Result</a><img src="/plot.svg"></main>')
        (self.site/'case.html').write_text('<base href="/"><h1 id="evidence">Recorded evidence</h1><a href="/#main">Back</a>')
        (self.site/'plot.svg').write_text('<svg></svg>')

    def test_clean_urls_base_paths_and_fragments_work(self):
        report=check_site(self.site)
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['local_links_checked'],3)

    def test_missing_file_and_anchor_fail(self):
        (self.site/'case.html').write_text('<a href="/missing.tsv">Data</a>')
        report=check_site(self.site)
        self.assertEqual(report['status'],'fail')
        self.assertTrue(any('Broken local link' in e for e in report['errors']))
        self.assertTrue(any('Broken local anchor' in e for e in report['errors']))

    def test_budgets_and_bulk_evidence_are_blocking(self):
        (self.site/'data').mkdir();(self.site/'data/results.json').write_text('{}')
        (self.site/'.backend.zip').write_bytes(b'zip')
        report=check_site(self.site,{'max_total_bytes':10,'max_file_bytes':10,'max_files':2})
        for fragment in ('total byte budget','file-count budget','File exceeds','Bulk/backend'):
            self.assertTrue(any(fragment in e for e in report['errors']),fragment)

    def test_external_links_are_not_fetched_and_symlinks_are_rejected(self):
        (self.site/'external.html').write_text('<a href="https://example.invalid/data">External</a>')
        (self.root/'outside.txt').write_text('private fixture')
        (self.site/'escaped.txt').symlink_to(self.root/'outside.txt')
        self.assertTrue(any('symlink' in e for e in check_site(self.site)['errors']))

    def bound_fixture(self):
        bundle=self.root/'bundle';bundle.mkdir();save(bundle/'manifest.json',{})
        sources=self.root/'sources';sources.mkdir()
        row={'scenario_id':'fixture','tool':'flye','status':'fail','assembly_sha256':'a','truth_sha256':'t','evaluation':{'status':'fail'}}
        original={'batch':'fixture','config':{},'scenarios':[],'inputs':{},'results':[row]}
        save(sources/'fixture.json',original)
        manifest={'sources':[{'batch':'fixture','filename':'fixture.json','sha256':digest(sources/'fixture.json')}]}
        save(self.site/'.results-render.json',{'bundle_manifest_sha256':digest(bundle/'manifest.json')})
        write_site_receipt(self.site)
        return bundle,sources,manifest,copy.deepcopy(original)

    def test_source_preservation_and_receipt_detect_score_and_html_changes(self):
        bundle,sources,manifest,document=self.bound_fixture()
        with patch('pipeline.bundle.load_bundle',return_value=(manifest,[document])):
            self.assertEqual(check_release(bundle,self.site,sources)['status'],'pass')
            document['results'][0]['evaluation']['status']='pass'
            self.assertTrue(any('original score' in e for e in check_release(bundle,self.site,sources)['errors']))
            document['results'][0]['evaluation']['status']='fail'
            (self.site/'.vercelignore').write_text('plot.svg')
            self.assertTrue(any('render receipt' in e for e in check_release(bundle,self.site,sources)['errors']))
            (self.site/'.vercelignore').unlink()
            (self.site/'case.html').write_text('<h1 id="evidence">Invented pass</h1>')
            self.assertTrue(any('render receipt' in e for e in check_release(bundle,self.site,sources)['errors']))

    def test_stale_source_plot_and_origin_hashes_fail(self):
        bundle,sources,manifest,document=self.bound_fixture()
        row=document['results'][0]
        row['report_evidence']={'dotplot':{'status':'available','input_hashes':{'assembly_sha256':'wrong','truth_sha256':'t'}}}
        with patch('pipeline.bundle.load_bundle',return_value=(manifest,[document])):
            self.assertTrue(any('plot evidence' in e for e in check_release(bundle,self.site,sources)['errors']))
            row['report_evidence']={'reference_origins':{'nodes':{'x':{}},'source_hashes':{}}}
            self.assertTrue(any('origin evidence' in e for e in check_release(bundle,self.site,sources)['errors']))
            save(sources/'fixture.json',{'changed':True})
            self.assertTrue(any('Snapshot hash changed' in e for e in check_release(bundle,self.site,sources)['errors']))
