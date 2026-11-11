#!/usr/bin/env python3
"""Recover missing failure reports from terminal metadata; never read sequence files."""
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, digest, load, save
from pipeline.performance.assessment import assess
from scripts.broad_performance import accounting_states


def reconcile(batch):
    batch = Path(batch).resolve()
    submission = load(batch / 'submission.json')
    if digest(batch / 'selection.json') != submission['selection_sha256']:
        raise ValueError('Frozen selection changed')
    states = accounting_states((batch / 'accounting.tsv').read_text())
    recovered = []
    for index, case in enumerate(load(batch / 'cases.json')):
        manifest_path = batch / 'cases' / case['id'] / 'input.json'
        if not manifest_path.exists():
            continue
        manifest = load(manifest_path)
        for tool in submission['reported_tools']:
            directory = batch / 'results' / case['id'] / tool
            execution = directory / 'execution.json'
            target = directory / 'performance.json'
            if target.exists() or not execution.exists():
                continue
            record = load(execution)
            if record.get('status') not in ('error', 'timeout', 'invalid_input'):
                continue
            if (manifest.get('status') != 'valid' or manifest.get('case') != case
                    or record.get('scenario_id') != case['id']
                    or record.get('scenario_fingerprint') != case['fingerprint']
                    or record.get('tool') != tool
                    or any(record.get(key) != manifest.get(key) for key in ('reads_sha256', 'truth_sha256'))):
                raise ValueError('Failure record does not bind the frozen input')
            job = submission['jobs']['assemble-' + tool] + '_' + str(index)
            accounting = states.get(job)
            if not accounting or not accounting[1].startswith(('COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'BOOT_FAIL', 'DEADLINE', 'PREEMPTED')):
                raise ValueError('Failure record lacks terminal scheduler evidence: ' + job)
            before = digest(execution)
            # A reporting-only repair must fail closed if sequence work is attempted.
            with patch('pipeline.performance.assessment._map_saved', side_effect=AssertionError('No new mapping authorised by this repair')), patch('pipeline.performance.assessment.fasta', side_effect=AssertionError('No sequence reads authorised by this repair')):
                result = assess(case, execution, batch)
            if result['status'] != 'complete' or result['genome_outcome'] not in ('execution_error', 'did_not_complete') or digest(execution) != before:
                raise ValueError('Unexpected metadata-only reconciliation outcome')
            result['failure_scope'] = 'execution'
            result['scheduler_evidence'] = accounting
            result['provenance'].update(accounting_file='accounting.tsv', accounting_sha256=digest(batch / 'accounting.tsv'), reporting_repair_source_sha256=digest(Path(__file__)))
            save(target, result)
            recovered.append({'dataset_id': case['id'], 'tool': tool, 'index': index,
                              'execution_sha256': before, 'performance_file': str(target.relative_to(batch)),
                              'performance_sha256': digest(target), 'outcome': result['genome_outcome']})
    return recovered


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    if Path(args.batch).name != args.batch:
        raise ValueError('A simple existing batch identifier is required')
    print(json.dumps(reconcile(ROOT / 'runs' / args.batch), indent=2))
