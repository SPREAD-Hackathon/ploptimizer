#!/usr/bin/env python3
"""Submit/collect the separate 50-dataset, 200-result performance benchmark."""
import argparse
import datetime
import json
import re
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, digest, load, save
from pipeline.cluster import ssh, transfer
from pipeline.performance.inputs import cases

STATUS = ROOT / 'evidence/broad-performance-v1/status.json'
CONFIG = ROOT / 'config/performance-wick-50.json'
TOOLS = ('flye', 'raven', 'plassembler', 'miniasm-plus')


def submit(inputs_only=False):
    if STATUS.exists() and load(STATUS).get('batch_id'):
        raise ValueError('Durable submission already exists; use release or collect instead of duplicating jobs')
    config = load(CONFIG); selection = load(ROOT / config['selection']); planned = cases(selection)
    index = load(ROOT / config['reads_index'])
    if index['status'] != 'complete' or len(index['members']) != 500 or index['archive'] != selection['archives']['reads']:
        raise ValueError('Expected the complete pinned 500-member archive index')
    if config['tools'] != list(TOOLS) or len(planned) != 50:
        raise ValueError('Authorisation is fifty inputs and four reported workflows')
    cluster = load(ROOT / 'config/cluster.local.json')
    if cluster['array_concurrency'] != 1000 or cluster['cpus'] != 4:
        raise ValueError('Preserve authorised resource settings')
    cluster['cache_root'] = cluster['remote_root'] + '/.cache/pixi'
    cluster['remote_root'] = str(Path(cluster['remote_root']) / '.b')
    ssh(cluster['host'], ['test', '!', '-e', cluster['remote_root']])
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    batch = ROOT / 'runs' / identifier
    (batch / 'slurm').mkdir(parents=True, exist_ok=False); (batch / 'logs').mkdir()
    for name, document in [('config.json', config), ('selection.json', selection), ('reads-index.json', index), ('cases.json', planned)]:
        save(batch / name, document)
    record = {'schema_version': 1, 'batch_id': identifier, 'track': 'broad-performance', 'panel_id': config['profile_id'], 'cluster': cluster, 'jobs': {}, 'status': 'submitting', 'selection_sha256': digest(batch / 'selection.json'), 'reported_tools': list(TOOLS), 'intermediate_tools': ['miniasm'], 'dataset_count': 50, 'expected_reported_executions': 200, 'expected_intermediate_executions': 50}
    save(batch / 'submission.json', record)
    state = {'schema_version': 1, 'status': 'submission_started', 'batch_id': identifier, 'remote_root': cluster['remote_root'], 'dataset_count': 50, 'expected_reported_executions': 200, 'expected_intermediate_executions': 50, 'selection_sha256': record['selection_sha256'], 'jobs': {}}
    save(STATUS, state)
    transfer(cluster['host'], cluster['remote_root'])
    return queue(batch, inputs_only)


def queue(batch, inputs_only=False):
    record = load(batch / 'submission.json'); state = load(STATUS)
    if digest(batch / 'selection.json') != record['selection_sha256']:
        raise ValueError('Selection changed after durable submission checkpoint')
    if record.get('submission_intent'):
        raise ValueError('A Slurm submission has an unresolved intent; inspect accounting before any retry')
    cluster = record['cluster']; host = cluster['host']; remote_root = cluster['remote_root']
    remote_batch = str(Path(remote_root) / 'runs' / batch.name)
    prefix = '#!/usr/bin/env bash\nset -euo pipefail\ncd ' + shlex.quote(remote_root) + '\n'
    prefix += 'export PATH=/users/aanensen/rva470/.pixi/bin:$PATH\nexport PIXI_CACHE_DIR=' + shlex.quote(cluster['cache_root']) + '\n'
    prefix += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
    pixi = shlex.quote(cluster['pixi'])
    def worker(environment, role, tool=''):
        return f'{pixi} run --locked -e {environment} python scripts/broad_performance.py worker --batch {batch.name} --role {role}' + (f' --tool {tool}' if tool else '') + ' --index "${SLURM_ARRAY_TASK_ID:-0}"\n'
    roles = [('prepare', f'{pixi} install --locked --all\n' + worker('default', 'prepare'), False, None), ('inputs', worker('default', 'inputs'), True, 'afterok:prepare')]
    if not inputs_only:
        if not (ROOT / 'pipeline/performance/assessment.py').is_file():
            raise ValueError('Tested assessment module must exist before releasing assemblers')
        for tool in ('flye', 'raven', 'plassembler', 'miniasm'):
            roles.append(('assemble-' + tool, worker(tool, 'assemble', tool), True, 'aftercorr:inputs'))
        roles.append(('assemble-miniasm-plus', worker('miniasm-plus', 'assemble', 'miniasm-plus'), True, 'aftercorr:assemble-miniasm'))
        for tool in TOOLS:
            roles.append(('assess-' + tool, worker('miniasm', 'assess', tool), True, 'aftercorr:assemble-' + tool))
    for role, body, _, _ in roles:
        (batch / 'slurm' / (role + '.sh')).write_text(prefix + body)
    ssh(host, ['mkdir', '-p', remote_batch + '/logs'])
    subprocess.run(['rsync', '-az', str(batch) + '/', host + ':' + remote_batch + '/'], check=True)
    for role, _, array, dependency in roles:
        if role in record['jobs']:
            continue
        args = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'], '--chdir', remote_root, '--job-name', 'ploptimizer-broad-' + role, '--output', remote_batch + '/logs/' + role + '-%A_%a.out', '--error', remote_batch + '/logs/' + role + '-%A_%a.err']
        if role.startswith('assemble-'):
            args += ['--cpus-per-task', '4', '--mem', '16G', '--time', '02:00:00' if role == 'assemble-plassembler' else '04:00:00']
        else:
            args += ['--cpus-per-task', '1', '--mem', '8G' if role == 'prepare' else '4G', '--time', '02:00:00' if role in ('prepare', 'inputs') else '01:00:00']
        if array:
            args += ['--array', '0-49%1000']
        if dependency:
            kind, previous = dependency.split(':', 1)
            args += ['--dependency', kind + ':' + record['jobs'][previous], '--kill-on-invalid-dep=yes']
        record['submission_intent'] = {'role': role, 'job_name': 'ploptimizer-broad-' + role,
                                       'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        save(batch / 'submission.json', record)
        state['submission_intent'] = record['submission_intent']
        save(STATUS, state)
        job = ssh(host, args + [remote_batch + '/slurm/' + role + '.sh']).split(';')[0]
        if not job.isdigit():
            raise ValueError('Unexpected Slurm ID; inspect partial durable submission')
        record.pop('submission_intent', None); state.pop('submission_intent', None)
        record['jobs'][role] = state['jobs'][role] = job
        save(batch / 'submission.json', record); save(STATUS, state)
        subprocess.run(['rsync', '-az', str(batch / 'submission.json'), host + ':' + remote_batch + '/'], check=True)
    record['status'] = state['status'] = 'inputs_submitted' if inputs_only else 'submitted'
    save(batch / 'submission.json', record); save(STATUS, state)
    subprocess.run(['rsync', '-az', str(batch / 'submission.json'), host + ':' + remote_batch + '/'], check=True)
    return state


def release(inputs_only=False):
    state = load(STATUS); batch = ROOT / 'runs' / state['batch_id']; record = load(batch / 'submission.json')
    if record['status'] not in ('inputs_submitted', 'submitting'):
        raise ValueError('Only the frozen staged submission can release its remaining tasks')
    transfer(record['cluster']['host'], record['cluster']['remote_root'])
    return queue(batch, inputs_only)



def accounting_states(accounting):
    """Expand Slurm's condensed pending/cancelled array IDs for bounded lookups."""
    states = {}
    for line in accounting.splitlines():
        fields = line.split('|')
        if len(fields) < 4:
            continue
        states[fields[0]] = fields
        match = re.fullmatch(r'(\d+)_\[([0-9,%-]+)\]', fields[0])
        if not match:
            continue
        for span in match[2].split('%', 1)[0].split(','):
            first, _, last = span.partition('-')
            low, high = int(first), int(last or first)
            if high - low > 1000:
                raise ValueError('Unexpected oversized Slurm array range')
            for index in range(low, high + 1):
                states[f'{match[1]}_{index}'] = fields
    return states


def collect():
    state = load(STATUS); batch = ROOT / 'runs' / state['batch_id']; submission = load(batch / 'submission.json')
    cluster = submission['cluster']; host = cluster['host']; remote = Path(cluster['remote_root']) / 'runs' / batch.name
    recovery = {'jobs': {}, 'task_job_overrides': {}}
    for name in ('assessment-recovery.json', 'missing-slot-recovery.json'):
        path = batch / name
        if path.exists():
            saved = load(path)
            recovery['jobs'].update({name + ':' + k: v for k, v in saved.get('jobs', {}).items()})
            recovery['task_job_overrides'].update(saved.get('task_job_overrides', {}))
    job_ids = list(submission['jobs'].values()) + list(recovery['jobs'].values())
    accounting = ssh(host, ['sacct', '-j', ','.join(job_ids), '--parsable2', '--noheader', '--format=JobID,State,Elapsed,ExitCode,MaxRSS'])
    (batch / 'accounting.tsv').write_text(accounting + '\n')
    include = ['--include=*/', '--include=execution.json', '--include=performance.json', '--include=workflow.json', '--include=input.json', '--include=input_error.json', '--include=read-download.json', '--include=preparation.json', '--include=reference-archive.json', '--include=reuse.json', '--include=resources.txt', '--exclude=*']
    subprocess.run(['rsync', '-az', '--prune-empty-dirs'] + include + [host + ':' + str(remote) + '/', str(batch) + '/'], check=True)
    states = accounting_states(accounting)
    results = []
    admitted = 0
    bindings = 0
    binding_errors = []
    assessment_bindings = 0
    for index, case in enumerate(load(batch / 'cases.json')):
        manifest_path = batch / 'cases' / case['id'] / 'input.json'
        manifest = load(manifest_path) if manifest_path.exists() else {}
        admitted_case = (manifest.get('status') == 'valid' and manifest.get('case') == case
                         and all(re.fullmatch(r'[0-9a-f]{64}', manifest.get(key, '')) for key in ('reads_sha256', 'truth_sha256')))
        admitted += bool(admitted_case)
        for tool in TOOLS:
            directory = batch / 'results' / case['id'] / tool
            result = load(directory / 'performance.json') if (directory / 'performance.json').exists() else {'dataset_id': case['id'], 'tool': tool, 'status': 'pending', 'genome_outcome': 'pending'}
            if result['status'] == 'pending':
                assembly_job = submission['jobs'].get('assemble-' + tool)
                assessment_job = submission['jobs'].get('assess-' + tool)
                assembly_id = recovery['task_job_overrides'].get('assemble-' + tool + ':' + str(index), f'{assembly_job}_{index}')
                assembly_state = states.get(assembly_id, [])
                assessment_id = recovery.get('task_job_overrides', {}).get('assess-' + tool + ':' + str(index), f'{assessment_job}_{index}')
                assessment_state = states.get(assessment_id, [])
                input_state = states.get(f"{submission['jobs'].get('inputs')}_{index}", [])
                terminal = ('FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'BOOT_FAIL', 'DEADLINE', 'PREEMPTED')
                if assessment_state and assessment_state[1].startswith(terminal):
                    timed_out = bool(assembly_state and assembly_state[1].startswith('TIMEOUT'))
                    result.update(status='error', failure_scope='infrastructure', genome_outcome='did_not_complete' if timed_out else 'execution_error',
                                  execution_status='timeout' if timed_out else 'error',
                                  reason='Scheduler ended a required stage before a completed assessment.', replicons=[],
                                  scheduler_evidence={'input': input_state, 'assembly': assembly_state, 'assessment': assessment_state},
                                  provenance={'accounting_file': str((batch / 'accounting.tsv').relative_to(ROOT)),
                                              'accounting_sha256': digest(batch / 'accounting.tsv')})
            execution = load(directory / 'execution.json') if (directory / 'execution.json').exists() else {}
            if execution and admitted_case and all(execution.get(k) == manifest[k] for k in ('reads_sha256', 'truth_sha256')):
                bindings += 1
            elif result['status'] == 'complete':
                binding_errors.append({'dataset_id': case['id'], 'tool': tool, 'reason': 'No verified same-input execution binding'})
            if result['status'] == 'complete':
                if execution and result.get('provenance', {}).get('execution_sha256') == digest(directory / 'execution.json'):
                    assessment_bindings += 1
                else:
                    binding_errors.append({'dataset_id': case['id'], 'tool': tool, 'reason': 'Assessment does not bind retained execution metadata'})
            result['execution_path'] = str((directory / 'execution.json').relative_to(ROOT)); results.append(result)
    save(batch / 'performance-results.json', {'schema_version': 1, 'batch_id': batch.name, 'results': results})
    complete = sum(row['status'] == 'complete' for row in results); errors = sum(row['status'] == 'error' for row in results)
    state.update(status='complete' if complete == 200 and admitted == 50 and bindings == 200 and assessment_bindings == 200 and not binding_errors else 'needs_review' if complete + errors == 200 else 'running', admitted_inputs=admitted, verified_assessment_execution_bindings=assessment_bindings, verified_execution_input_bindings=bindings, input_binding_errors=binding_errors, assessed_results=complete, assessment_errors=errors, result_path=str((batch / 'performance-results.json').relative_to(ROOT)))
    save(STATUS, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['submit', 'release', 'collect', 'worker'])
    parser.add_argument('--inputs-only', action='store_true'); parser.add_argument('--batch'); parser.add_argument('--role', choices=['prepare', 'inputs', 'assemble', 'assess']); parser.add_argument('--tool', choices=list(TOOLS) + ['miniasm']); parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    if args.action == 'worker':
        from pipeline.performance import worker
        if not args.batch or Path(args.batch).name != args.batch:
            raise ValueError('A simple existing batch ID is required')
        batch = ROOT / 'runs' / args.batch
        functions = {'prepare': lambda: worker.prepare(batch), 'inputs': lambda: worker.fetch(batch, args.index), 'assemble': lambda: worker.assemble(batch, args.index, args.tool), 'assess': lambda: worker.assess_result(batch, args.index, args.tool)}
        result = functions[args.role](); print(json.dumps(result))
        # A terminal execution error is a recorded result; infrastructure exceptions still fail the task.
        return 0
    result = submit(args.inputs_only) if args.action == 'submit' else release(args.inputs_only) if args.action == 'release' else collect()
    print(json.dumps(result, indent=2)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
