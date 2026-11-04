#!/usr/bin/env python3
"""Read-only provisional audit of submitted benchmark results and PAF evidence.

No simulation, assembly, alignment, submission or publication is performed.
Use --verify-pilot-remotely for a small, explicit read-only SSH sequence check.
"""

import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.common import digest, load
from pipeline.diagnostics import read_paf
from pipeline.report import result_status


def submitted_rows(batch_id):
    batch = ROOT / 'runs' / batch_id
    published = ROOT / 'published' / (batch_id + '.json')
    if not batch.exists() and not published.exists():
        raise ValueError(f'Unknown batch: {batch_id}')
    snapshot = load(published) if published.exists() else {}
    tasks_path = batch / 'tasks.json'
    tasks = load(tasks_path)['assemble'] if tasks_path.exists() else [
        {'scenario': row['scenario_id'], 'tool': row['tool'], **({'run_id': row['run_id']} if row.get('run_id') else {})}
        for row in snapshot.get('results', []) if row['status'] != 'not_run']
    published_rows = {(row['scenario_id'], row['tool'], row.get('run_id')): row for row in snapshot.get('results', [])}
    submission_path = batch / 'submission.json'
    submission = load(submission_path) if submission_path.exists() else {}
    job = submission.get('jobs', {}).get('assemble', '')
    accounting = {}
    if (batch / 'accounting.tsv').exists():
        for line in (batch / 'accounting.tsv').read_text().splitlines():
            fields = line.split('|')
            if len(fields) >= 2:
                accounting[fields[0]] = fields[1]
    rows = []
    for index, task in enumerate(tasks):
        directory = batch / 'results' / task['scenario'] / task['tool']
        if task.get('run_id'):
            directory = directory / 'repeats' / task['run_id']
        execution_path = directory / 'execution.json'
        key = (task['scenario'], task['tool'], task.get('run_id'))
        record = load(execution_path) if execution_path.exists() else published_rows.get(key, {})
        state = accounting.get(f'{job}_{index}', accounting.get(job, ''))
        if not state and not record and submission:
            state = 'PENDING'
        row = {'scenario_id': task['scenario'], 'tool': task['tool'], 'run_id': task.get('run_id'),
               'status': result_status(record, state), 'published_status': published_rows.get(key, {}).get('status'),
               'strict_evaluation': record.get('evaluation'), 'diagnostic_status': None}
        diagnostic_path = directory / 'diagnostics.json'
        diagnostic = load(diagnostic_path) if diagnostic_path.exists() else record.get('diagnostics', {})
        if diagnostic:
            row['diagnostic_status'] = diagnostic.get('status')
            row['alignment_evidence'] = diagnostic.get('evidence')
        if execution_path.exists():
            row['execution_file'] = str(execution_path.relative_to(ROOT))
            row['execution_sha256'] = digest(execution_path)
        if diagnostic_path.exists():
            row['diagnostic_file'] = str(diagnostic_path.relative_to(ROOT))
            row['diagnostic_sha256'] = digest(diagnostic_path)
            expected_execution = diagnostic.get('input_hashes', {}).get('execution_sha256')
            row['diagnostic_execution_hash_matches'] = row.get('execution_sha256') == expected_execution if expected_execution else None
        paf_path = directory / 'alignment.paf'
        if paf_path.exists():
            row['paf_file'] = str(paf_path.relative_to(ROOT))
            row['paf_sha256'] = digest(paf_path)
            row['diagnostic_paf_hash_matches'] = row['paf_sha256'] == diagnostic.get('paf_sha256') if diagnostic.get('paf_sha256') else None
            row['paf_queries'] = [{key: alignment[key] for key in ('query', 'query_length', 'query_start', 'query_end', 'target', 'target_length', 'target_start', 'target_end', 'matches', 'block_length', 'mapq')}
                                  for alignment in read_paf(paf_path)]
        rows.append(row)
    inputs = {}
    for scenario in sorted({task['scenario'] for task in tasks}):
        path = batch / 'cases' / scenario / 'input.json'
        manifest = load(path) if path.exists() else snapshot.get('inputs', {}).get(scenario)
        if manifest:
            inputs[scenario] = {'status': manifest['status'], 'reads_sha256': manifest['reads_sha256'],
                                'replicons': manifest['replicons']}
    return {'batch_id': batch_id, 'submitted_executions': len(rows), 'inputs': inputs,
            'status_counts': dict(collections.Counter(row['status'] for row in rows)),
            'completed_diagnostics': sum(row['diagnostic_status'] == 'complete' for row in rows),
            'published_snapshot_sha256': digest(published) if published.exists() else None,
            'executions': rows}


def check_pilot_sequences(evidence):
    """Verify the specific archived Raven PAF explanation by direct equality."""
    query, reference = evidence['query'], evidence['reference']
    return {'query_length': len(query), 'reference_length': len(reference),
            'query_sequence_sha256': hashlib.sha256(query.encode()).hexdigest(),
            'reference_sequence_sha256': hashlib.sha256(reference.encode()).hexdigest(),
            'circular_tail_155bp_matches_reference_origin': query[5200:5355] == reference[:155] and len(query) == 5355 and len(reference) == 5360,
            'query_equals_reference_rotation_with_5bp_deletion': query == reference[155:3261] + reference[3266:] + reference[:155] and len(query) == 5355 and len(reference) == 5360,
            'reference_deletion_interval_0based_half_open': [3261, 3266],
            'scope': 'Direct sequence equality for this archived contig; not a general alignment algorithm.'}


def verify_pilot_remotely():
    cluster = load(ROOT / 'config/cluster.local.json')
    host, remote_root = cluster['host'], cluster['remote_root']
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+', host) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', remote_root):
        raise ValueError('Use a simple SSH destination and absolute work directory')
    # Read existing 5 kb contig/reference records; file hashes link the extracted
    # sequences to the archived execution. No mapper or assembler is invoked.
    script = '''import hashlib,json
from pathlib import Path
root=Path(%r)
batch=root/'runs/20261104T183058'
assembly=batch/'results/s1-w-prk2/raven/stdout.log'
truth=batch/'cases/s1-w-prk2/truth.fasta'
def record(path,name):
    found=False; chunks=[]
    with path.open() as stream:
        for line in stream:
            if line.startswith('>'):
                if found: break
                found=line[1:].split()[0]==name
            elif found: chunks.append(line.strip())
    return ''.join(chunks).upper()
def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''): value.update(chunk)
    return value.hexdigest()
print(json.dumps({'query':record(assembly,'Utg2196'),'reference':record(truth,'NC_017662.1'),'assembly_sha256':sha(assembly),'truth_sha256':sha(truth)}))
''' % remote_root
    response = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host,
                                        shlex.join(['python3', '-c', script])], text=True, timeout=60)
    evidence = json.loads(response)
    execution = load(ROOT / 'runs/20261104T183058/results/s1-w-prk2/raven/execution.json')
    if evidence['assembly_sha256'] != execution['assembly_sha256'] or evidence['truth_sha256'] != execution['truth_sha256']:
        raise ValueError('Remote pilot files differ from their archived execution hashes')
    return {**check_pilot_sequences(evidence), 'assembly_sha256': evidence['assembly_sha256'],
            'truth_sha256': evidence['truth_sha256'], 'archived_file_hashes_verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', action='append', help='Submitted batch ID; default is every versioned publication')
    parser.add_argument('--verify-pilot-remotely', action='store_true', help='Read existing pilot sequences over configured SSH; no compute jobs')
    args = parser.parse_args()
    batch_ids = args.batch or [path.stem for path in sorted((ROOT / 'published').glob('2*.json'))]
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', value) for value in batch_ids):
        raise ValueError('Batch identifiers cannot be paths')
    result = {'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
              'scope': 'Submitted executions only; planned but unsubmitted snapshot rows are excluded.',
              'limitations': 'Provisional read-only audit. Local accounting/collection may lag live jobs. Diagnostic coverage is incomplete. No tool ranking or topology conclusions.',
              'batches': [submitted_rows(batch_id) for batch_id in batch_ids]}
    if args.verify_pilot_remotely:
        result['pilot_raven_sequence_check'] = verify_pilot_remotely()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
