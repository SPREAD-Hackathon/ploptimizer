#!/usr/bin/env python3
"""Release only original frozen slots which never produced an execution record."""
import datetime
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, digest, load, save
from pipeline.cluster import ssh
from scripts.broad_performance import TOOLS


def missing_plan(batch):
    planned = load(batch / 'cases.json')
    inputs = [i for i, case in enumerate(planned) if not (batch / 'cases' / case['id'] / 'input.json').exists()]
    phases = {}
    for tool in (*TOOLS, 'miniasm'):
        phases[tool] = [i for i, case in enumerate(planned)
                       if not (batch / 'results' / case['id'] / tool / 'execution.json').exists()]
    return {'inputs': inputs, 'assemblies': phases}


def recover():
    state = load(ROOT / 'evidence/broad-performance-v1/status.json')
    batch = ROOT / 'runs' / state['batch_id']
    submission = load(batch / 'submission.json'); cluster = submission['cluster']
    host, remote = cluster['host'], cluster['remote_root']
    remote_batch = str(Path(remote) / 'runs' / batch.name)
    path = batch / 'missing-slot-recovery.json'
    with (batch / '.missing-slot-recovery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if path.exists():
            raise ValueError('Durable repair already exists; collect and inspect it, never resubmit blindly')
        if digest(batch / 'selection.json') != submission['selection_sha256']:
            raise ValueError('Frozen selection changed')
        original_jobs = list(submission['jobs'].values())
        assessment_path = batch / 'assessment-recovery.json'
        if assessment_path.exists():
            original_jobs += list(load(assessment_path)['jobs'].values())
        if ssh(host, ['squeue', '-r', '-h', '-j', ','.join(original_jobs), '-o', '%i|%T']):
            raise ValueError('Prior suite tasks remain active; collect first')
        plan = missing_plan(batch); cases = load(batch / 'cases.json')
        config_hashes = {n: digest(batch / n) for n in ('config.json', 'selection.json', 'cases.json', 'reads-index.json')}
        manifests = {i: digest(batch / 'cases' / c['id'] / 'input.json') for i, c in enumerate(cases)
                     if i not in plan['inputs']}
        guard = "import hashlib\nfrom pathlib import Path\nb=Path(" + repr(remote_batch) + ")\nplan=" + repr(plan) + "\ncases=" + repr([c['id'] for c in cases]) + "\n"
        guard += "for n,h in " + repr(config_hashes) + ".items():\n assert hashlib.sha256((b/n).read_bytes()).hexdigest()==h, 'Frozen configuration changed'\n"
        guard += "for i,h in " + repr(manifests) + ".items():\n assert hashlib.sha256((b/'cases'/cases[i]/'input.json').read_bytes()).hexdigest()==h, 'Input manifest changed'\n"
        guard += "for i in plan['inputs']:\n d=b/'cases'/cases[i]\n assert not (d/'input.json').exists() and not (d/'reads.fastq.gz').exists(), 'Input already downloaded or admitted'\n"
        guard += "for tool,indices in plan['assemblies'].items():\n for i in indices:\n  d=b/'results'/cases[i]/tool\n  assert not (d/'execution.json').exists(), 'Execution already exists'\n  assert not any(p.is_file() and p.stat().st_size for p in d.rglob('*')), 'Partial output needs review'\n  if tool=='miniasm-plus':\n   assert not (b/'raw_assemblies'/cases[i]).exists(), 'Staged raw source needs review'\nprint('Verified absent execution slots, no partial outputs, frozen configuration and admitted manifests')\n"
        subprocess.run(['ssh', '-o', 'BatchMode=yes', host, 'python3 -'], input=guard, text=True, check=True, timeout=60)
        recovery = {'schema_version': 1, 'batch_id': batch.name, 'plan': plan, 'jobs': {},
                    'task_job_overrides': {}, 'config_hashes': config_hashes,
                    'existing_input_manifest_hashes': manifests,
                    'policy': 'Only previously unexecuted canonical slots; original attempts and settings unchanged; no simulation.'}
        save(path, recovery)

        def submit(label, role, indices, tool=None, dependency=None):
            if not indices:
                return None
            script = batch / 'slurm' / ('recover-missing-' + label + '.sh')
            body = '#!/usr/bin/env bash\nset -euo pipefail\ncd ' + shlex.quote(remote) + '\n'
            body += 'export PATH=/users/aanensen/rva470/.pixi/bin:$PATH\nexport PIXI_CACHE_DIR=' + shlex.quote(cluster['cache_root']) + '\n'
            body += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
            environment = tool if role == 'assemble' else 'miniasm' if role == 'assess' else 'default'
            # The canonical worker checks input bytes and refuses an existing execution.
            body += shlex.quote(cluster['pixi']) + ' run --locked -e ' + environment + ' python scripts/broad_performance.py worker --batch ' + batch.name + ' --role ' + role
            if tool:
                body += ' --tool ' + tool
            body += ' --index "$SLURM_ARRAY_TASK_ID"\n'
            script.write_text(body)
            subprocess.run(['rsync', '-az', str(script), host + ':' + remote_batch + '/slurm/'], check=True)
            args = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'],
                    '--chdir', remote, '--job-name', 'ploptimizer-recover-' + label,
                    '--array', ','.join(map(str, indices)) + '%1000',
                    '--output', remote_batch + '/logs/recover-' + label + '-%A_%a.out',
                    '--error', remote_batch + '/logs/recover-' + label + '-%A_%a.err']
            if role == 'assemble':
                args += ['--cpus-per-task', '4', '--mem', '16G', '--time', '02:00:00' if tool == 'plassembler' else '04:00:00']
            else:
                args += ['--cpus-per-task', '1', '--mem', '4G', '--time', '02:00:00' if role == 'inputs' else '01:00:00']
            if dependency:
                args += ['--dependency', dependency, '--kill-on-invalid-dep=yes']
            recovery['submission_intent'] = {'label': label, 'indices': indices, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            save(path, recovery)
            job = ssh(host, args + [str(Path(remote_batch) / 'slurm' / script.name)]).split(';')[0]
            if not job.isdigit():
                raise ValueError('Uncertain scheduler response; inspect durable intent')
            recovery['jobs'][label] = job
            key = role + ('-' + tool if tool else '')
            recovery['task_job_overrides'].update({key + ':' + str(i): job + '_' + str(i) for i in indices})
            recovery.pop('submission_intent'); save(path, recovery)
            subprocess.run(['rsync', '-az', str(path), host + ':' + remote_batch + '/'], check=True)
            return job

        input_job = submit('inputs', 'inputs', plan['inputs'])
        producer = {}
        for tool in ('flye', 'raven', 'plassembler', 'miniasm', 'miniasm-plus'):
            for needs_input in (False, True):
                indices = [i for i in plan['assemblies'][tool] if (i in plan['inputs']) == needs_input]
                if not indices:
                    continue
                dependency = 'aftercorr:' + input_job if needs_input else None
                if tool == 'miniasm-plus':
                    raw_jobs = {producer[('miniasm', i)] for i in indices if ('miniasm', i) in producer}
                    if len(raw_jobs) != 1:
                        raise ValueError('Raw source groups require explicit review')
                    dependency = 'afterany:' + next(iter(raw_jobs))
                job = submit('assemble-' + tool + ('-input' if needs_input else '-admitted'), 'assemble', indices, tool, dependency)
                for i in indices:
                    producer[(tool, i)] = job
        for tool in TOOLS:
            for job in sorted({producer[(tool, i)] for i in plan['assemblies'][tool]}):
                indices = [i for i in plan['assemblies'][tool] if producer[(tool, i)] == job]
                submit('assess-' + tool + '-' + job, 'assess', indices, tool, 'afterany:' + job)
        recovery['status'] = 'submitted'; save(path, recovery)
        subprocess.run(['rsync', '-az', str(path), host + ':' + remote_batch + '/'], check=True)
        return recovery


if __name__ == '__main__':
    print(json.dumps(recover(), indent=2))
