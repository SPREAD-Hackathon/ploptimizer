#!/usr/bin/env python3
"""Freeze collected performance metadata for reporting; no jobs or sequence I/O."""
import datetime
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, digest, load, save
from pipeline.performance_bundle import performance_model, OUTCOMES


def freeze():
    state = load(ROOT / 'evidence/broad-performance-v1/status.json')
    if state.get('input_binding_errors'):
        raise ValueError('Input/execution bindings need review; previous snapshot retained')
    if Path(state['batch_id']).name != state['batch_id']:
        raise ValueError('A simple batch identifier is required')
    batch = ROOT / 'runs' / state['batch_id']
    source = (ROOT / state['result_path']).resolve()
    if batch.resolve() not in source.parents:
        raise ValueError('Results must belong to the recorded broad batch')
    snapshot_path = ROOT / 'performance/snapshot.json'
    snapshot = load(snapshot_path)
    selection = load(ROOT / snapshot['selection'])
    if selection != load(batch / 'selection.json') or digest(batch / 'selection.json') != state['selection_sha256']:
        raise ValueError('Frozen dataset selection changed')
    collected = load(source)
    if collected['batch_id'] != batch.name or len(collected['results']) != snapshot['expected_executions']:
        raise ValueError('Collection does not account for the expected panel')
    expected = {(d['id'], t) for d in selection['datasets'] for t in snapshot['tools']}
    keys = [(r.get('dataset_id'), r.get('tool')) for r in collected['results']]
    if len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError('Collection has missing, duplicate or unknown execution slots')
    if state['status'] == 'complete':
        if (any(r.get('status') != 'complete' for r in collected['results'])
                or state.get('admitted_inputs') != len(selection['datasets'])
                or state.get('verified_execution_input_bindings') != len(expected)
                or state.get('verified_assessment_execution_bindings') != len(expected)
                or state.get('assessment_errors', 0)):
            raise ValueError('Complete release requires every admitted input and terminal assessment binding')
    rows = []
    for record in collected['results']:
        if record['status'] == 'pending':
            continue
        if record['status'] not in ('complete', 'error') or record.get('genome_outcome') not in OUTCOMES:
            raise ValueError('Unrecognised terminal performance outcome')
        execution = (ROOT / record['execution_path']).resolve()
        if (batch.resolve() not in execution.parents or not execution.is_file()
                or record.get('provenance', {}).get('execution_sha256') != digest(execution)):
            raise ValueError('Assessment does not bind the retained execution metadata')
        rows.append(record)
    snapshot.update(results=rows, state='complete' if state['status'] == 'complete' else 'running',
                    batch_id=batch.name, jobs=state['jobs'], source_results_sha256=digest(source),
                    source_selection_sha256=state['selection_sha256'], admitted_inputs=state.get('admitted_inputs'),
                    verified_execution_input_bindings=state.get('verified_execution_input_bindings'),
                    frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    performance_model(snapshot, selection)
    save(snapshot_path, snapshot)
    return {'state': snapshot['state'], 'recorded_results': len(rows), 'expected_results': snapshot['expected_executions']}


if __name__ == '__main__':
    import json
    print(json.dumps(freeze(), indent=2))
