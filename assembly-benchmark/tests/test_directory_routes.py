"""Resolve links as browsers do for slashless deployed directory-index URLs."""
from html.parser import HTMLParser
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urljoin
from pipeline.common import ROOT
from pipeline.report import write_release_overview


class PageLinks(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.base = None; self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'base': self.base = attrs.get('href')
        elif tag in {'a', 'link', 'script'}:
            target = attrs.get('href') or attrs.get('src')
            if target and not target.startswith('#'): self.links.append(target)


class DirectoryRouteTests(unittest.TestCase):
    def test_directory_indexes_resolve_families_cases_assets_and_results(self):
        document = {'batch':'fixture','config':{'tools':['flye']},
                    'scenarios':[{'id':'case','title':'Saved input','category':'S1'}],
                    'results':[{'scenario_id':'case','tool':'flye','status':'pass','version':'fixture'}]}
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary:
            root=Path(temporary)
            for output, prefix in [(root/'site', ''), (root/'site/batches/fixture', '/batches/fixture')]:
                output.mkdir(parents=True)
                write_release_overview(output,document,include_history=False)
                catalog=PageLinks((output/'scenarios/index.html').read_text())
                for suffix in ['/scenarios','/scenarios/','/scenarios/index.html']:
                    url='https://report.example'+prefix+suffix
                    base=urljoin(url,catalog.base)
                    resolved=[urljoin(base,link) for link in catalog.links]
                    for target in ['/scenarios/s1.html','/scenarios/case.html','/assets/genomicx.css','/assets/genomicx.js']:
                        self.assertIn('https://report.example'+prefix+target,resolved)
                home=PageLinks((output/'index.html').read_text())
                for suffix in ['', '/', '/index.html']:
                    url='https://report.example'+prefix+suffix
                    base=urljoin(url,home.base)
                    resolved=[urljoin(base,link) for link in home.links]
                    self.assertIn('https://report.example'+prefix+'/scenarios/s1.html',resolved)
