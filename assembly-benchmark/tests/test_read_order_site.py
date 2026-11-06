"""Read-order evidence stays separate from exact-reference counts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import ROOT, load, save
from pipeline.read_order_site import freeze_read_order, headline_row, install_read_order

class ReadOrderSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary=load(ROOT/'evidence/read-order-v1/summary.json')

    def test_completed_summary_freezes_without_sequence_tools(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary, patch('subprocess.run',side_effect=AssertionError('No tools')):
            result=freeze_read_order(ROOT/'evidence/read-order-v1/status.json',Path(temporary)/'read_order')
            self.assertEqual(result,self.summary)
            self.assertEqual(sum(len(t['runs']) for t in result['tools']),48)

    def test_changed_summary_hash_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary:
            path=Path(temporary)/'status.json';state=load(ROOT/'evidence/read-order-v1/status.json')
            state['summary_sha256']='0'*64;save(path,state)
            save(path.parent/'summary.json',self.summary)
            with self.assertRaisesRegex(ValueError,'bindings'):freeze_read_order(path,Path(temporary)/'output')

    def test_headline_uses_agreement_and_explicit_comparison_basis(self):
        tools=load(ROOT/'config/overview.json')['tools'];row=headline_row(self.summary,tools)
        self.assertEqual(row.count('<td'),len(tools))
        for text in ['No order effect observed','Within-order variability','Order-associated difference','Ends retained; circular view unavailable','Not assessed']:
            self.assertIn(text,row)
        self.assertNotIn('24 pass',row)

    def test_install_is_idempotent_and_publishes_html_tsv_only(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary:
            root=Path(temporary);bundle=root/'bundle';output=root/'site';save(bundle/'read_order/summary.json',self.summary)
            (output/'scenarios').mkdir(parents=True)
            (output/'index.html').write_text('<table class="overview-heatmap"><thead><tr><th>Scenario</th></tr></thead><tbody><tr><th>S1</th></tr></tbody></table>')
            (output/'scenarios/index.html').write_text('<main><h1>Scenarios</h1></main>')
            for _ in range(2):install_read_order(bundle,output,load(ROOT/'config/overview.json')['tools'])
            self.assertEqual((output/'index.html').read_text().count('data-read-order="true"'),1)
            page=(output/'scenarios/s7.html').read_text()
            for text in ['genomicx-nav','/data/read-order/runs.tsv','Ends-retained pairwise output agreement']:
                self.assertIn(text,page)
            for text in ['href="summary.json"','<style>','/gpfs3/']:
                self.assertNotIn(text,page)
            self.assertIn('Configuration: Flye (--meta) · 4 threads',page)
            self.assertNotIn('Default mode',page)
            self.assertEqual({p.suffix for p in (output/'data/read-order').iterdir()},{'.tsv'})
            self.assertIn('48 completed executions',(output/'scenarios/index.html').read_text())
