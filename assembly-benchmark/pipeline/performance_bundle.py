"""Freeze broad-performance metadata independently of diagnostic scenario results."""
import copy
import re
from pathlib import Path
from .common import ROOT, load, save

TOOLS = {'flye': 'Flye', 'raven': 'Raven', 'plassembler': 'Plassembler', 'miniasm-plus': 'Miniasm + Minipolish'}
OUTCOMES = {'fully_complete': 'All molecules complete', 'chromosome_complete': 'Chromosome complete; plasmids incomplete',
            'incomplete': 'Incomplete assembly', 'empty': 'Empty assembly', 'did_not_complete': 'Did not complete',
            'execution_error': 'Execution or assessment error'}
DATASET_ID = re.compile(r'\d{3}_GCF_\d{9}\.\d+\Z')


def performance_model(snapshot, selection):
    """Count saved broad endpoints in the backend export, never in the browser."""
    if snapshot.get('schema_version') != 1 or snapshot.get('track') != 'broad-performance':
        raise ValueError('Unsupported broad-performance snapshot')
    datasets = copy.deepcopy(snapshot.get('datasets') or selection.get('datasets', []))
    identities = [d['id'] for d in datasets]
    if not identities or len(set(identities)) != len(identities) or any(not DATASET_ID.fullmatch(i) for i in identities):
        raise ValueError('Broad datasets require unique published identifiers')
    tools = [t['id'] if isinstance(t, dict) else t for t in snapshot['tools']]
    if tools != list(TOOLS):
        raise ValueError('Broad performance reports only the four declared primary workflows')
    if snapshot.get('dataset_count') != len(datasets) or snapshot.get('expected_executions') != len(datasets) * len(tools):
        raise ValueError('Broad panel size differs from its declared denominator')
    records = copy.deepcopy(snapshot.get('results', [])); seen = set()
    for row in records:
        key = (row.get('dataset_id'), row.get('tool'))
        if key in seen or key[0] not in identities or key[1] not in tools:
            raise ValueError('Duplicate or unknown broad execution')
        seen.add(key)
        if row.get('genome_outcome') not in OUTCOMES:
            raise ValueError('Broad record has an unknown completion outcome')
    counts = []
    for tool in tools:
        rows = [r for r in records if r['tool'] == tool]
        totals = {key: sum(r['genome_outcome'] == key for r in rows) for key in OUTCOMES}
        counts.append({'id': tool, 'label': TOOLS[tool], 'expected': len(datasets), 'recorded': len(rows),
                       'pending': len(datasets) - len(rows), **totals})
    records.sort(key=lambda r: (identities.index(r['dataset_id']), tools.index(r['tool'])))
    return {'schema_version': 1, 'track': 'broad-performance', 'panel_id': snapshot.get('panel_id'),
            'state': snapshot.get('state', 'preparing'), 'dataset_count': len(datasets),
            'expected_executions': len(datasets) * len(tools), 'recorded_executions': len(records),
            'sampling_balance': copy.deepcopy(snapshot.get('sampling_balance', {})),
            'completion_threshold': snapshot.get('completion_threshold', .99), 'tools': counts,
            'outcomes': [{'id': key, 'label': label} for key, label in OUTCOMES.items()],
            'datasets': datasets, 'results': records, 'sources': copy.deepcopy(selection.get('sources', {})),
            'source_pool_note': selection.get('source_pool_note'), 'source_revision': selection.get('source_revision')}


def freeze_performance(source, output):
    """Copy a source snapshot, selection and precomputed plots into the bundle."""
    snapshot = load(Path(source).resolve()); relative = Path(snapshot.get('selection', ''))
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Performance selection must be a repository-relative path')
    selection_path = (ROOT / relative).resolve()
    if ROOT.resolve() not in selection_path.parents or not selection_path.is_file():
        raise ValueError('Performance selection is unavailable inside the benchmark')
    selection = load(selection_path); model = performance_model(snapshot, selection); output = Path(output)
    save(output / 'snapshot.json', snapshot); save(output / 'selection.json', selection); save(output / 'model.json', model)
    from .performance.plotting import write_performance_plots
    index = write_performance_plots({**snapshot, 'datasets': model['datasets']}, output / 'plots')
    save(output / 'plots/index.json', index)
    return model
