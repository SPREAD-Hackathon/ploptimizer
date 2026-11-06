"""Queue six Miniasm tasks after S5, reusing its frozen reads byte-for-byte."""
import argparse
import datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.cases import plan
from pipeline.cluster import ssh, transfer
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.determinism import assembly_tasks
from scripts.large_baseline import queue_evidence
from scripts.native_linear import collect_panel

STATUS = ROOT / 'evidence/s5-miniasm-v1/status.json'
CONFIG = ROOT / 'config/miniasm-linear.json'


def validate_input(source, case):
    manifest = load(source / 'input.json')
    if manifest.get('status') != 'valid' or manifest.get('case') != case:
        raise ValueError('Frozen S5 input does not match the Miniasm case: ' + case['id'])
    for filename, key in [('reads.fastq.gz', 'reads_sha256'),
                          ('truth.fasta', 'truth_sha256'), ('read_origins.tsv.gz', 'origins_sha256')]:
        if digest(source / filename) != manifest[key]:
            raise ValueError('Frozen S5 input bytes changed: ' + filename)
    return manifest


def stage(batch):
    """Validate every source first; then hard-link the immutable input files."""
    submission = load(batch / 'submission.json')
    source = Path(submission['input_source_root']) / 'runs' / submission['input_source_batch']
    evidence = load(source / 'evidence_status.json')
    if evidence.get('status') != 'complete' or evidence.get('expected_executions') != 24:
        raise ValueError('Original S5 evidence is incomplete; do not start follow-up')
    config = load(batch / 'config.json')
    cases = plan(config)
    manifests = [validate_input(source / 'cases' / case['id'], case) for case in cases]
    raw_sources = []
    if submission.get('raw_source_batch'):
        raw_batch = Path(submission['raw_source_root']) / 'runs' / submission['raw_source_batch']
        raw_evidence = load(raw_batch / 'evidence_status.json')
        if raw_evidence.get('status') != 'complete' or raw_evidence.get('expected_executions') != 6:
            raise ValueError('Unpolished Miniasm evidence is incomplete')
        for case, manifest in zip(cases, manifests):
            execution = raw_batch / 'results' / case['id'] / 'miniasm' / 'execution.json'
            record = load(execution)
            graph = execution.parent / 'output/assembly.raw.gfa'
            if (record.get('tool') != 'miniasm' or record.get('status') not in ('pass', 'fail')
                    or record.get('scenario_fingerprint') != case['fingerprint']
                    or any(record.get(key) != manifest[key] for key in ('reads_sha256', 'truth_sha256'))
                    or record.get('assembly_workflow', {}).get('status') != 'complete'
                    or record['assembly_workflow']['conversion']['raw_gfa_sha256'] != digest(graph)
                    or record['assembly_sha256'] != digest(raw_batch / record['assembly_file'])):
                raise ValueError('Unpolished Miniasm source differs from its frozen record')
            raw_sources.append((case['id'], execution, graph))
    audit = []
    for case, manifest in zip(cases, manifests):
        original = source / 'cases' / case['id']
        target = batch / 'cases' / case['id']
        target.mkdir(parents=True, exist_ok=False)
        for name in ('reads.fastq.gz', 'truth.fasta', 'read_origins.tsv.gz'):
            os.link(original / name, target / name)
        shutil.copy2(original / 'input.json', target / 'input.json')
        audit.append({'scenario_id': case['id'], 'source_manifest_sha256': digest(original / 'input.json'),
                      'copied_manifest_sha256': digest(target / 'input.json'),
                      **{key: manifest[key] for key in ('reads_sha256', 'truth_sha256', 'origins_sha256')},
                      'method': 'Hard links to frozen files; input manifest copied verbatim; no simulation.'})
    provenance = batch / 'provenance'
    provenance.mkdir()
    for name in ('pixi.toml', 'pixi.lock'):
        shutil.copy2(ROOT / name, provenance / name)
    save(batch / 'input_reuse.json', {'status': 'complete', 'source_batch': source.name,
         'source_evidence_sha256': digest(source / 'evidence_status.json'), 'inputs': audit})
    if raw_sources:
        raw_audit = []
        for case_id, execution, graph in raw_sources:
            target = batch / 'raw_assemblies' / case_id
            target.mkdir(parents=True)
            os.link(graph, target / 'assembly.raw.gfa')
            shutil.copy2(execution, target / 'execution.json')
            raw_audit.append({'scenario_id': case_id, 'source_execution_sha256': digest(execution),
                              'raw_gfa_sha256': digest(graph)})
        save(batch / 'raw_assembly_reuse.json', {'status': 'complete', 'source_batch': raw_batch.name, 'assemblies': raw_audit})


def submit_followup(tool='miniasm'):
    config_path = CONFIG if tool == 'miniasm' else ROOT / 'config/miniasm-plus-linear.json'
    status_path = STATUS if tool == 'miniasm' else ROOT / 'evidence/s5-miniasm-plus-v1/status.json'
    config = load(config_path)
    cases = plan(config)
    source_state = load(ROOT / 'evidence/s5-native-v2/status.json')
    source_config = load(ROOT / 'runs' / source_state['batch_id'] / 'config.json')
    if config['tools'] != [tool] or len(cases) != 6 or cases != plan(source_config):
        raise ValueError('Follow-up must use exactly the six frozen S5 cases and the requested configuration only')
    if status_path.exists():
        state = load(status_path)
        if state['config_fingerprint'] != fingerprint(config):
            raise ValueError('Recorded follow-up configuration changed')
        if state['status'] not in {'queued_after_s5', 'evidence_complete'}:
            raise ValueError('Inspect the existing partial submission; do not submit duplicates')
        return state
    cluster = load(ROOT / 'config/cluster.local.json')
    source_root = cluster['remote_root']
    cluster['remote_root'] = source_root + '/.cache/' + tool + '-integration/source'
    if cluster['array_concurrency'] != 1000:
        raise ValueError('Keep the authorised Slurm cap')
    ssh(cluster['host'], ['true'])
    identifier = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
    batch = ROOT / 'runs' / identifier
    batch.mkdir(exist_ok=False)
    (batch / 'slurm').mkdir()
    (batch / 'logs').mkdir()
    save(batch / 'config.json', config)
    save(batch / 'tasks.json', {'simulate': [], 'assemble': assembly_tasks(config, cases)})
    record = {'batch_id': identifier, 'cluster': cluster, 'status': 'submitting', 'jobs': {},
              'input_source_root': source_root, 'input_source_batch': source_state['batch_id']}
    dependency_job = source_state['jobs']['evidence']
    if tool == 'miniasm-plus':
        raw_state = load(STATUS)
        raw_submission = load(ROOT / 'runs' / raw_state['batch_id'] / 'submission.json')
        record.update(raw_source_root=raw_submission['cluster']['remote_root'], raw_source_batch=raw_state['batch_id'])
        dependency_job = raw_state['jobs']['evidence']
    save(batch / 'submission.json', record)
    state = {'schema_version': 1, 'status': 'submission_needs_review', 'batch_id': identifier,
             'config_fingerprint': fingerprint(config), 'input_source_batch': source_state['batch_id'],
             'after_job': dependency_job, 'input_count': 6, 'assembly_count': 6,
             'scenario_ids': [case['id'] for case in cases]}
    if tool == 'miniasm-plus':
        state['raw_source_batch'] = record['raw_source_batch']
    save(status_path, state)  # Durable before external actions: partial submission cannot duplicate.
    transfer(cluster['host'], cluster['remote_root'])
    remote = Path(cluster['remote_root']) / 'runs' / identifier
    prefix = '#!/usr/bin/env bash\nset -euo pipefail\ncd ' + shlex.quote(cluster['remote_root']) + '\n'
    prefix += 'export PATH=/users/aanensen/rva470/.pixi/bin:$PATH\nexport PIXI_CACHE_DIR=' + shlex.quote(source_root + '/.cache/pixi') + '\n'
    prefix += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
    python = shlex.quote(cluster['pixi']) + f' run --locked -e {tool} python '
    roles = {
        'reuse_inputs': shlex.quote(cluster['pixi']) + f' install --locked -e {tool}\n' + python + f'scripts/miniasm_followup.py stage --batch {identifier}\n',
        'assemble': python + f'benchmark.py task --batch {identifier} --kind assemble --index "$SLURM_ARRAY_TASK_ID"\n',
        'report': python + f'benchmark.py report --batch {identifier}\n'}
    for role, body in roles.items():
        (batch / 'slurm' / (role + '.sh')).write_text(prefix + body)
    subprocess.run(['rsync', '-az', str(batch) + '/', cluster['host'] + ':' + str(remote) + '/'], check=True)
    previous = dependency_job
    for role in roles:
        dependency = ('afterany:' if role == 'report' else 'afterok:') + previous
        args = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'],
                '--cpus-per-task', str(cluster['cpus'] if role == 'assemble' else 1),
                '--mem', cluster['memory'] if role == 'assemble' else '4G',
                '--time', cluster['time'] if role == 'assemble' else '00:30:00',
                '--job-name', 'ploptimizer-' + tool + '-' + role, '--dependency', dependency, '--kill-on-invalid-dep=yes',
                '--output', str(remote / 'logs' / (role + '-%A_%a.out')),
                '--error', str(remote / 'logs' / (role + '-%A_%a.err'))]
        if role == 'assemble':
            args += ['--array', '0-5%1000']
        job = ssh(cluster['host'], args + [str(remote / 'slurm' / (role + '.sh'))]).split(';')[0]
        if not job.isdigit():
            raise ValueError('Unexpected job identifier')
        record['jobs'][role] = previous = job
        save(batch / 'submission.json', record)
        subprocess.run(['rsync', '-az', str(batch / 'submission.json'), cluster['host'] + ':' + str(remote) + '/'], check=True)
    queue_evidence(batch, cluster, comparison_label='s5-' + tool + '-v1')
    record = load(batch / 'submission.json')
    record['status'] = 'submitted'
    save(batch / 'submission.json', record)
    subprocess.run(['rsync', '-az', str(batch / 'submission.json'), cluster['host'] + ':' + str(remote) + '/'], check=True)
    state.update(status='queued_after_s5', jobs=record['jobs'])
    save(status_path, state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['submit', 'stage', 'collect'])
    parser.add_argument('--batch')
    parser.add_argument('--tool', choices=['miniasm', 'miniasm-plus'], default='miniasm')
    args = parser.parse_args()
    if args.action == 'stage':
        if not args.batch or Path(args.batch).name != args.batch:
            raise ValueError('A simple batch ID is required')
        stage(ROOT / 'runs' / args.batch)
    elif args.action == 'collect':
        print(collect_panel(STATUS if args.tool == 'miniasm' else ROOT / 'evidence/s5-miniasm-plus-v1/status.json'))
    else:
        print(submit_followup(args.tool))
