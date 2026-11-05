"""Website adapter for validated bundles; no cluster or sequence-analysis stage."""
import shutil
import zipfile
from pathlib import Path

from .bundle import load_bundle, result_id
from .common import load


def render_bundle(bundle, output):
    bundle,output=Path(bundle).resolve(),Path(output).resolve()
    if output==bundle or bundle in output.parents or output in bundle.parents:
        raise ValueError('Bundle and website destinations must be separate directories')
    if output.exists() and any(output.iterdir()) and not (output/'.results-render.json').exists():
        from .common import ROOT
        if output != ROOT/'dist':
            raise ValueError('Render destination must be empty or a previously generated bundle website')
    manifest,documents=load_bundle(bundle)
    context={'documents':{d['batch']:d for d in documents},'overview':load(bundle/'overview.json'),
             'models':{d['batch']:load(bundle/'models'/f'{d["batch"]}.json') for d in documents}}
    primary=context['documents'][manifest['primary_batch']]
    # Import the website only after the complete input bundle has passed validation.
    from .report import build
    build(primary['config'],output=output,document=primary,include_history=True,render_context=context)
    for document in documents:
        batch=document['batch'];destination=output if batch==manifest['primary_batch'] else output/'batches'/batch
        for record in document['results']:
            slug=result_id(record);source=bundle/'reports'/batch
            target=destination/'data/results';target.mkdir(parents=True,exist_ok=True)
            report=(source/f'{slug}.md').read_text().replace(f'../../batches/{batch}.json','../results.json')
            (target/f'{slug}-report.md').write_text(report)
            if record['report_evidence']['dotplot']['status']=='available':
                shutil.copy2(source/f'{slug}-alignment.svg',target/f'{slug}-alignment.svg')
                shutil.copy2(source/f'{slug}-alignments.tsv',target/f'{slug}-alignments.tsv')
                if record['report_evidence']['dotplot'].get('nucmer_status')=='available':
                    shutil.copy2(source/f'{slug}-original-show-coords.tsv',target/f'{slug}-original-show-coords.tsv')
    for name in ('summary.tsv','molecules.tsv','evidence-availability.tsv','evidence-coverage.json'):
        if (bundle/name).is_file():
            shutil.copy2(bundle/name,output/'data'/name)
    home=output/'index.html'
    content=home.read_text().replace('</main>','<div class="downloads"><a href="data/results-bundle.zip">Backend results bundle (ZIP)</a><a href="data/summary.tsv">Execution summary TSV</a><a href="data/molecules.tsv">Molecule evidence TSV</a></div></main>')
    if (bundle/'evidence-availability.tsv').is_file():
        content=content.replace('Molecule evidence TSV</a>','Molecule evidence TSV</a><a href="data/evidence-availability.tsv">Evidence availability TSV</a>')
    home.write_text(content)
    from .common import save, digest
    save(output/'.results-render.json',{'schema_version':1,'bundle_manifest_sha256':digest(bundle/'manifest.json')})
    # A portable, complete backend deliverable is available independently of HTML.
    with zipfile.ZipFile(output/'data/results-bundle.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                entry=zipfile.ZipInfo(str(path.relative_to(bundle)),date_time=(1980,1,1,0,0,0))
                entry.compress_type=zipfile.ZIP_DEFLATED
                entry.external_attr=0o100644 << 16
                archive.writestr(entry,path.read_bytes())
    return output
