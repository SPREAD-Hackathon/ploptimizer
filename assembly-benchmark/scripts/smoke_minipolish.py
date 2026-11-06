"""Validate the polished adapter using the existing artificial Miniasm fixture."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, load, save
from pipeline.execution import run
from scripts.collect_graph_artifacts import collect_selected, write_sidecars


def smoke(source):
    batch = ROOT / 'runs' / ('minipolish-smoke-' + os.environ.get('SLURM_JOB_ID', 'local'))
    original = source / 'cases/artificial-linear'
    target = batch / 'cases/artificial-linear'
    target.mkdir(parents=True, exist_ok=False)
    for name in ('reads.fastq.gz', 'truth.fasta'):
        os.link(original / name, target / name)
    shutil.copy2(original / 'input.json', target / 'input.json')
    raw = source / 'results/artificial-linear/miniasm'
    retained = batch / 'raw_assemblies/artificial-linear'
    retained.mkdir(parents=True)
    os.link(raw / 'output/assembly.raw.gfa', retained / 'assembly.raw.gfa')
    shutil.copy2(raw / 'execution.json', retained / 'execution.json')
    record = run(load(target / 'input.json')['case'], 'miniasm-plus', batch, {'threads': 2, 'timeout_seconds': 600})
    workflow = record.get('assembly_workflow', {})
    if record['status'] not in ('pass', 'fail') or workflow.get('status') != 'complete':
        raise ValueError(record.get('error', 'Polished smoke workflow incomplete'))
    if len(workflow['steps']) != 3 or workflow['steps'][-1].get('exit_code') != 0:
        raise ValueError('Expected two retained stages and a real successful Minipolish invocation')
    if record['evaluation']['contig_count'] < 1 or record['elapsed_seconds'] < workflow['source_elapsed_seconds']:
        raise ValueError('Unitig or combined-runtime check failed')
    artifact = collect_selected(ROOT, batch.name, ['results/artificial-linear/miniasm-plus/execution.json'])
    write_sidecars(ROOT, batch.name, artifact)
    item = artifact['executions'][0]['artifact']
    if item['graph']['status'] != 'available' or item['assembly_info']['status'] != 'available':
        raise ValueError('Polished graph/inventory unavailable')
    result = {'status': 'pass', 'scope': 'Artificial installation fixture only; excluded from benchmark scores.',
              'versions': workflow['versions'], 'workflow_stages': 3, 'source_stages_reused': 2,
              'unitig_count': record['evaluation']['contig_count'], 'graph_status': item['graph']['status'],
              'elapsed_seconds': record['elapsed_seconds'], 'polishing_elapsed_seconds': record['polishing_elapsed_seconds']}
    save(ROOT / '.cache/miniasm-plus-integration/smoke-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    print(json.dumps(smoke(parser.parse_args().source), indent=2))
