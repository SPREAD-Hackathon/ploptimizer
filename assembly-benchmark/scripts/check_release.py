#!/usr/bin/env python3
"""Read-only release gate using frozen tasks, publication snapshots and accounting.

No collection, sequence analysis, experiments, build, commit or deployment.
"""
import argparse
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'pass', 'fail', 'error', 'timeout', 'invalid_input'}
SCHEDULER_TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'BOOT_FAIL', 'DEADLINE', 'PREEMPTED'}


def load(path):
    return json.loads(Path(path).read_text())


def task_key(row):
    repeated = row.get('run_id') or row.get('repeat') is not None
    return (row.get('scenario_id', row.get('scenario')), row.get('tool'), row.get('run_id'),
            row.get('threads') if repeated else None, row.get('repeat') if repeated else None)


def job_state(batch, job, expected_count=None):
    path = batch / 'accounting.tsv'
    if not job or not path.exists():
        return {'state': 'unknown', 'finished': False, 'successful': False}
    states = {}
    for line in path.read_text().splitlines():
        fields = line.split('|')
        if len(fields) >= 2 and fields[1].strip():
            states[fields[0]] = fields[1].split()[0].rstrip('+')
    if str(job) in states:
        found = [states[str(job)]]
    else:
        array = {int(key.rsplit('_', 1)[1]): state for key, state in states.items() if re.fullmatch(re.escape(str(job)) + r'_[0-9]+', key)}
        found = list(array.values())
        if expected_count is not None and set(array) != set(range(expected_count)):
            return {'state': 'incomplete_accounting', 'observed_tasks': len(found), 'expected_tasks': expected_count,
                    'missing_indices': sorted(set(range(expected_count)) - set(array)),
                    'unexpected_indices': sorted(set(array) - set(range(expected_count))),
                    'finished': False, 'successful': False}
    finished = bool(found) and all(state in SCHEDULER_TERMINAL for state in found)
    successful = bool(found) and all(state == 'COMPLETED' for state in found)
    state = 'COMPLETED' if successful else 'terminal_with_errors' if finished else 'pending_or_running' if found else 'unknown'
    return {'state': state, 'state_counts': dict(collections.Counter(found)), 'finished': finished, 'successful': successful}


def explanation(row):
    if row['status'] in {'error', 'timeout', 'invalid_input'}:
        return row.get('error') or row.get('reason')
    evaluation = row.get('evaluation') or {}
    reasons = [item.get('reason') for item in evaluation.get('replicons', []) if item.get('status') == 'fail' and item.get('reason')]
    return '; '.join(reasons) or evaluation.get('endpoint')


def check_batch(root, batch_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', batch_id):
        raise ValueError('Batch identifiers cannot be paths')
    batch = root / 'runs' / batch_id
    blockers, review_items = [], []
    tasks_path, snapshot_path = batch / 'tasks.json', root / 'published' / (batch_id + '.json')
    if not tasks_path.exists() or not snapshot_path.exists():
        return {'batch': batch_id, 'executions_finished': False, 'jobs_finished': False, 'release_ready': False,
                'blockers': ['Frozen task list or publication snapshot is missing'], 'review_items': []}
    tasks_document, document = load(tasks_path), load(snapshot_path)
    tasks = tasks_document['assemble']
    if document.get('batch') != batch_id:
        blockers.append('Snapshot batch identifier differs from requested batch')
    expected_keys = [task_key(task) for task in tasks]
    if not tasks or len(set(expected_keys)) != len(expected_keys):
        blockers.append('Frozen assembly task list is empty or has duplicate identities')
    rows = (document.get('determinism') or {}).get('executions', document.get('results', []))
    by_key = collections.defaultdict(list)
    for row in rows:
        by_key[task_key(row)].append(row)
    selected = []
    for key in expected_keys:
        matches = by_key[key]
        if len(matches) != 1:
            blockers.append(f'{key}: expected one snapshot execution, found {len(matches)}')
            continue
        row = matches[0]
        selected.append(row)
        if row.get('status') not in TERMINAL:
            blockers.append(f'{key}: execution is {row.get("status", "missing")}')
        if row.get('status') in TERMINAL - {'pass'}:
            finding = row.get('explanation') or {}
            fields = ('summary', 'symptom', 'interpretation', 'confidence_scope')
            if (finding.get('confidence') not in {'confirmed', 'suspected', 'unresolved'}
                    or not all(isinstance(finding.get(field), str) and finding[field].strip() for field in fields)
                    or not finding.get('evidence')):
                blockers.append(f'{key}: structured failure explanation or its evidence is missing')
            reason = explanation(row)
            if not reason:
                blockers.append(f'{key}: terminal outcome has no recorded explanation')
            review_items.append({'task': list(key), 'status': row['status'], 'explanation': reason,
                                 'finding': finding,
                                 'scope': 'Recorded endpoint/exit explanation; not necessarily a confirmed mechanism'})
    expected_set = set(expected_keys)
    extras = [row for row in rows if task_key(row) not in expected_set]
    if any(row.get('status') != 'not_run' for row in extras):
        blockers.append('Active/scored snapshot executions are absent from the frozen task list')
    counts = dict(collections.Counter(row.get('status', 'missing') for row in selected))
    executions_finished = len(selected) == len(tasks) and all(row.get('status') in TERMINAL for row in selected)
    stages = {}
    submission_path = batch / 'submission.json'
    submission = load(submission_path) if submission_path.exists() else {}
    if not submission.get('jobs'):
        blockers.append('Submission job metadata is missing')
    for name, job in submission.get('jobs', {}).items():
        count = len(tasks_document[name]) if name in {'simulate', 'assemble'} else None
        stages[name] = job_state(batch, job, count)
        if not stages[name]['finished']:
            blockers.append(f'{name}: scheduler work is unfinished or accounting unavailable')
        elif name != 'assemble' and not stages[name]['successful']:
            blockers.append(f'{name}: required scheduler stage did not complete successfully')
    diagnostic_plan = batch / 'diagnostic_submission.json'
    if diagnostic_plan.exists():
        stages['diagnostics'] = job_state(batch, load(diagnostic_plan).get('job_id'))
        if not stages['diagnostics']['successful']:
            blockers.append('diagnostics: final job is not successfully complete')
    cases = {case['id']: case for case in document.get('scenarios', [])}
    config_hash = hashlib.sha256(json.dumps(document.get('config', {}), sort_keys=True).encode()).hexdigest()
    diagnostics = collections.Counter()
    assessments = collections.Counter()
    needs_assessment = bool(document.get('config', {}).get('noisy_panel'))
    for row in selected:
        if row.get('status') not in {'pass', 'fail'}:
            continue
        key = task_key(row)
        admitted = (document.get('inputs') or {}).get(key[0]) or {}
        if (row.get('evaluation') or {}).get('status') != row['status'] or not (row.get('evaluation') or {}).get('endpoint'):
            blockers.append(f'{key}: matching strict evaluation is missing')
        case_fingerprint = (cases.get(key[0]) or {}).get('fingerprint')
        if not case_fingerprint or row.get('config_fingerprint') != config_hash or row.get('scenario_fingerprint') != case_fingerprint:
            blockers.append(f'{key}: execution configuration/scenario provenance is missing or mismatched')
        for field in ('reads_sha256', 'truth_sha256'):
            if not row.get(field) or row.get(field) != admitted.get(field):
                blockers.append(f'{key}: execution {field} differs from admitted input')
        diagnostic = row.get('diagnostics') or {}
        diagnostics[diagnostic.get('status', 'missing')] += 1
        if diagnostic_plan.exists():
            hashes = diagnostic.get('input_hashes') or {}
            if diagnostic.get('status') != 'complete' or not diagnostic.get('evidence'):
                blockers.append(f'{key}: required diagnostic is missing or not complete')
            elif not row.get('assembly_sha256') or hashes.get('assembly_sha256') != row['assembly_sha256']:
                blockers.append(f'{key}: diagnostic assembly provenance is missing or mismatched')
            for field in ('reads_sha256', 'truth_sha256'):
                if row.get(field) and hashes.get(field) != row[field]:
                    blockers.append(f'{key}: diagnostic {field} differs from execution')
        if needs_assessment:
            assessment = row.get('tolerant_assessment') or {}
            status = assessment.get('status', 'missing')
            assessments[status] += 1
            hashes = assessment.get('input_hashes') or {}
            if status not in {'pass', 'fail', 'unscored'}:
                blockers.append(f'{key}: tolerant assessment is missing or erroneous')
            elif not row.get('assembly_sha256') or hashes.get('assembly_sha256') != row['assembly_sha256'] or not hashes.get('execution_sha256'):
                blockers.append(f'{key}: tolerant assessment provenance is missing or mismatched')
            elif status == 'unscored':
                review_items.append({'task': list(key), 'status': 'tolerant_unscored', 'explanation': assessment.get('reason'),
                                     'scope': 'Unscored uncertainty must remain visible and outside pass/fail denominators'})
                if not assessment.get('reason'):
                    blockers.append(f'{key}: unscored tolerant assessment has no reason')
    inputs = document.get('inputs') or {}
    for scenario in sorted({key[0] for key in expected_keys}):
        if (inputs.get(scenario) or {}).get('status') != 'valid':
            blockers.append(f'{scenario}: valid admitted input manifest is missing')
    if document.get('config', {}).get('determinism'):
        summary = document.get('determinism') or {}
        for kind, positions in [('within_thread', (0, 1, 3)), ('across_threads', (0, 1))]:
            expected_groups = {tuple(key[index] for index in positions) for key in expected_keys}
            fields = ('scenario_id', 'tool', 'threads') if kind == 'within_thread' else ('scenario_id', 'tool')
            groups = summary.get(kind, [])
            actual = [tuple(row.get(field) for field in fields) for row in groups]
            if len(actual) != len(set(actual)) or set(actual) != expected_groups:
                blockers.append(f'{kind}: repeatability group identities are missing or duplicated')
            for group in groups:
                if not group.get('complete') or group.get('inputs_identical') is not True:
                    blockers.append(f'{kind}: incomplete repeats or unequal frozen inputs')
                for field in ('byte_identical', 'normalised_sequence_identical', 'biological_identical'):
                    if type(group.get(field)) is not bool:
                        blockers.append(f'{kind}: {field} is unavailable')
    jobs_finished = bool(stages) and all(stage['finished'] for stage in stages.values())
    return {'batch': batch_id, 'snapshot_generated_at': document.get('generated_at'),
            'submitted_executions': len(tasks), 'matched_snapshot_executions': len(selected), 'unsubmitted_not_run_rows': sum(row.get('status') == 'not_run' for row in extras),
            'status_counts': counts, 'diagnostic_counts': dict(diagnostics), 'assessment_counts': dict(assessments),
            'executions_finished': executions_finished, 'jobs_finished': jobs_finished,
            'release_ready': executions_finished and jobs_finished and not blockers,
            'stages': stages, 'blockers': sorted(set(blockers)), 'review_items': review_items}


def check_release(root, batches):
    results = [check_batch(Path(root), batch) for batch in batches]
    ready = bool(results) and all(row['release_ready'] for row in results)
    finished = bool(results) and all(row['jobs_finished'] for row in results)
    return {'schema_version': 1, 'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'status': 'ready' if ready else 'blocked' if finished else 'in_progress', 'release_ready': ready,
            'jobs_finished': finished, 'batches': results,
            'scope': 'Evidence readiness only. Recorded scientific fails/tool errors can be reported; this does not certify scientific truth, frontend QA, deployment or a Git commit.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', action='append', required=True, help='Explicit batch ID; repeat for companion batches')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check_release(args.root, args.batch)
    content = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content, end='')
    return int(not result['release_ready'])


if __name__ == '__main__':
    raise SystemExit(main())
