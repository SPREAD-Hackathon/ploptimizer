#!/usr/bin/env python3
"""Repair only socket-preflight failures proven to precede any tool invocation."""
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


def eligible(record):
    return (record.get('status') == 'error'
            and record.get('error') == 'OSError: AF_UNIX path too long'
            and not any(record.get(k) for k in ('command', 'version', 'reads_sha256',
                        'truth_sha256', 'assembly_file', 'evaluation')))


def recover():
    state = load(ROOT / 'evidence/broad-performance-v1/status.json')
    batch = ROOT / 'runs' / state['batch_id']
    submission = load(batch / 'submission.json'); cluster = submission['cluster']
    host, remote = cluster['host'], cluster['remote_root']
    remote_batch = str(Path(remote) / 'runs' / batch.name)
    receipt_path = batch / 'preflight-recovery.json'
    with (batch / '.preflight-recovery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if receipt_path.exists():
            raise ValueError('Repair checkpoint already exists; inspect it rather than resubmitting')
        jobs = list(submission['jobs'].values())
        for n in ('assessment-recovery.json', 'missing-slot-recovery.json'):
            jobs += list(load(batch / n)['jobs'].values())
        if ssh(host, ['squeue', '-r', '-h', '-j', ','.join(jobs), '-o', '%i|%T']):
            raise ValueError('Existing suite jobs remain active; do not repair concurrently')
        plan = []
        for index, case in enumerate(load(batch / 'cases.json')):
            for tool in submission['reported_tools']:
                d = batch / 'results' / case['id'] / tool
                p = d / 'execution.json'
                if not p.exists() or not eligible(load(p)):
                    continue
                plan.append({'index': index, 'dataset_id': case['id'], 'tool': tool,
                    'execution_sha256': digest(p), 'assessment_sha256': digest(d / 'performance.json'),
                    'input_manifest_sha256': digest(batch / 'cases' / case['id'] / 'input.json'),
                    'archived_directory': 'infrastructure_attempts/' + case['id'] + '/' + tool + '/socket-preflight-1'})
        if not plan:
            return {'status': 'nothing_to_repair'}
        if len(plan) != len(state['input_binding_errors']):
            raise ValueError('Not every binding error is an eligible preflight failure; inspect separately')
        recovery = {'schema_version': 1, 'batch_id': batch.name, 'plan': plan, 'jobs': {}, 'task_job_overrides': {},
            'policy': 'Original preflight attempts archived byte-for-byte before their first assembler invocation. Frozen inputs, parameters and resource limits unchanged.',
            'selection_sha256': submission['selection_sha256'], 'status': 'preflight_started'}
        save(receipt_path, recovery)
        code = "import hashlib,json,os,socket,tempfile\nfrom pathlib import Path\nb=Path(" + repr(remote_batch) + ")\nplan=" + repr(plan) + "\n"
        code += "tmp=Path(" + repr(remote) + ")/'.t'/'00000000'\ntmp.mkdir(parents=True,exist_ok=True)\nwith tempfile.TemporaryDirectory(prefix='pymp-',dir=str(tmp)) as d:\n with socket.socket(socket.AF_UNIX) as s:s.bind(str(Path(d)/'listener-12345678'))\n"
        code += "for row in plan:\n d=b/'results'/row['dataset_id']/row['tool'];e=json.loads((d/'execution.json').read_text())\n assert e.get('status')=='error' and e.get('error')=='OSError: AF_UNIX path too long'\n assert not any(e.get(k) for k in ('command','version','reads_sha256','truth_sha256','assembly_file','evaluation'))\n assert set(p.name for p in d.iterdir()) <= {'execution.json','performance.json'}, 'Unexpected output: tool may have run'\n assert hashlib.sha256((d/'execution.json').read_bytes()).hexdigest()==row['execution_sha256']\n assert hashlib.sha256((d/'performance.json').read_bytes()).hexdigest()==row['assessment_sha256']\n assert hashlib.sha256((b/'cases'/row['dataset_id']/'input.json').read_bytes()).hexdigest()==row['input_manifest_sha256']\n assert not (b/row['archived_directory']).exists()\n"
        code += "for row in plan:\n d=b/'results'/row['dataset_id']/row['tool'];a=b/row['archived_directory'];a.parent.mkdir(parents=True,exist_ok=True);os.rename(str(d),str(a))\n assert hashlib.sha256((a/'execution.json').read_bytes()).hexdigest()==row['execution_sha256']\nprint('Preserved all preflight attempts and verified shorter socket path')\n"
        subprocess.run(['ssh', '-o', 'BatchMode=yes', host, 'python3 -'], input=code, text=True, check=True, timeout=60)
        # Keep the local mirror in the same layout; archives retain original bytes.
        for row in plan:
            d = batch / 'results' / row['dataset_id'] / row['tool']
            archive = batch / row['archived_directory']; archive.parent.mkdir(parents=True, exist_ok=True)
            d.rename(archive)
        recovery['status'] = 'attempts_archived'; save(receipt_path, recovery)
        remote_receipt = host + ':' + remote_batch + '/'
        subprocess.run(['rsync', '-az', str(receipt_path), remote_receipt], check=True)

        def submit(role, tool, indices, dependency=None):
            label = role + '-' + tool
            script = batch / 'slurm' / ('recover-preflight-' + label + '.sh')
            env = tool if role == 'assemble' else 'miniasm'
            body = '#!/usr/bin/env bash\nset -euo pipefail\ncd ' + shlex.quote(remote) + '\n'
            body += 'export PATH=/users/aanensen/rva470/.pixi/bin:$PATH\nexport PIXI_CACHE_DIR=' + shlex.quote(cluster['cache_root']) + '\n'
            body += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
            body += shlex.quote(cluster['pixi']) + ' run --locked -e ' + env + ' python scripts/broad_performance.py worker --batch ' + batch.name + ' --role ' + role + ' --tool ' + tool + ' --index "$SLURM_ARRAY_TASK_ID"\n'
            script.write_text(body)
            subprocess.run(['rsync', '-az', str(script), host + ':' + remote_batch + '/slurm/'], check=True)
            args = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'],
                    '--chdir', remote, '--job-name', 'ploptimizer-preflight-' + label,
                    '--array', ','.join(map(str, indices)) + '%1000',
                    '--cpus-per-task', '4' if role == 'assemble' else '1',
                    '--mem', '16G' if role == 'assemble' else '4G',
                    '--time', ('02:00:00' if tool == 'plassembler' else '04:00:00') if role == 'assemble' else '01:00:00',
                    '--output', remote_batch + '/logs/preflight-' + label + '-%A_%a.out',
                    '--error', remote_batch + '/logs/preflight-' + label + '-%A_%a.err']
            if dependency: args += ['--dependency', dependency]
            recovery['submission_intent'] = {'role': label, 'indices': indices, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}; save(receipt_path, recovery)
            job = ssh(host, args + [str(Path(remote_batch) / 'slurm' / script.name)]).split(';')[0]
            if not job.isdigit(): raise ValueError('Uncertain scheduler response; inspect durable intent')
            recovery['jobs'][label] = job
            recovery['task_job_overrides'].update({label + ':' + str(i): job + '_' + str(i) for i in indices})
            recovery.pop('submission_intent'); save(receipt_path, recovery)
            subprocess.run(['rsync', '-az', str(receipt_path), remote_receipt], check=True)
            return job
        for tool in sorted({r['tool'] for r in plan}):
            indices = [r['index'] for r in plan if r['tool'] == tool]
            job = submit('assemble', tool, indices)
            submit('assess', tool, indices, 'afterany:' + job)
        recovery['status'] = 'submitted'; save(receipt_path, recovery)
        subprocess.run(['rsync', '-az', str(receipt_path), remote_receipt], check=True)
        return recovery


if __name__ == '__main__':
    print(json.dumps(recover(), indent=2))
