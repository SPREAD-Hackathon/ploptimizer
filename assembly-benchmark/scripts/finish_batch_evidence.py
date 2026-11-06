"""Compute-node postprocessing for a newly completed benchmark batch."""
import argparse
import collections
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, load, save
from pipeline.diagnostic_runs import batch_directory, run_batch
from pipeline.publication import publish
from scripts.collect_graph_artifacts import collect_selected, write_sidecars
from scripts.collect_graph_contig_identities import collect as collect_identities
from scripts.collect_length_inventories import collect as collect_lengths
from scripts.compare_existing_outputs import run_task
from scripts.plan_existing_comparisons import plan as comparison_plan


def finish(identifier, comparison_label='large-baseline-v3'):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', comparison_label):
        raise ValueError('Comparison label must be a simple identifier')
    batch = batch_directory(identifier)
    diagnostic_counts = run_batch(batch)
    executions = [str(path.relative_to(batch)) for path in sorted((batch / 'results').rglob('execution.json'))
                  if load(path).get('status') in ('pass','fail')]
    graph_counts = collections.Counter()
    for start in range(0, len(executions), 8):
        document = collect_selected(ROOT, batch.name, executions[start:start+8])
        graph_counts.update(row['artifact']['status'] for row in document['executions'])
        write_sidecars(ROOT, batch.name, document)
    lengths = collect_lengths(batch)
    identities = collect_identities(batch)
    config = load(batch / 'config.json')
    snapshot = publish(config, batch, deploy=False, make_latest=False)
    comparison_root = batch / 'comparisons' / comparison_label
    comparison_root.mkdir(parents=True, exist_ok=True)
    provenance = comparison_root / 'provenance'
    provenance.mkdir(exist_ok=True)
    for source in [ROOT / 'environments/coordinate-comparison/pixi.toml',
                   ROOT / 'environments/coordinate-comparison/pixi.lock',
                   ROOT / 'scripts/compare_existing_outputs.py']:
        shutil.copy2(source, provenance / source.name)
    cluster = comparison_root / 'source-root.json'
    save(cluster, {'remote_root':str(ROOT)})
    manifest = comparison_root / 'tasks.json'
    comparison_counts = collections.Counter()
    if executions:
        if manifest.exists():
            raise ValueError('Comparison manifest already exists; inspect it instead of silently overwriting a run')
        save(manifest, comparison_plan(batch.name, comparison_label, cluster))
        for index in range(len(load(manifest)['tasks'])):
            code = run_task(manifest, index)
            task = load(manifest)['tasks'][index]
            outcome = load(ROOT / task['output_relative_path'] / 'comparison.json')
            comparison_counts['not_applicable' if code == 0 and outcome.get('status') == 'not_applicable'
                              else 'complete' if code == 0 else 'error'] += 1
    expected = len(load(batch / 'tasks.json')['assemble'])
    status_counts = collections.Counter(row['status'] for row in snapshot['results'])
    complete = len(snapshot['results']) == expected and sum(status_counts.get(s,0) for s in ('pass','fail','error','timeout','invalid_input')) == expected
    status = 'complete' if complete and not diagnostic_counts.get('error') and not comparison_counts.get('error') and not graph_counts.get('invalid') else 'needs_review'
    result = {'status':status, 'expected_executions':expected, 'outcomes':dict(status_counts),
              'diagnostics':diagnostic_counts, 'graphs':dict(graph_counts), 'length_inventories':lengths,
              'graph_identities':identities, 'coordinate_comparisons':dict(comparison_counts),
              'comparison_root':str(comparison_root.relative_to(batch)),
              'source_snapshot':str((ROOT / 'published' / (batch.name + '.json')).relative_to(ROOT))}
    save(batch / 'evidence_status.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--comparison-label', default='large-baseline-v3')
    args = parser.parse_args()
    print(finish(args.batch,args.comparison_label))
