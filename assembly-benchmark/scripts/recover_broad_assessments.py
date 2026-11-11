#!/usr/bin/env python3
"""Resume absent assessments of retained executions without rerunning assemblers."""
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
from scripts.broad_performance import accounting_states, TOOLS


def recover():
    state = load(ROOT / 'evidence/broad-performance-v1/status.json')
    batch = ROOT / 'runs' / state['batch_id']
    submission = load(batch / 'submission.json')
    cluster = submission['cluster']; host = cluster['host']; remote = cluster['remote_root']
    if digest(batch / 'selection.json') != submission['selection_sha256']:
        raise ValueError('Frozen selection changed')
    recovery_path = batch / 'assessment-recovery.json'
    lock = (batch / '.assessment-recovery.lock').open('a')
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        recovery = load(recovery_path) if recovery_path.exists() else {'schema_version': 1, 'batch_id': batch.name, 'jobs': {}, 'task_job_overrides': {}}
        if recovery.get('submission_intent'):
            raise ValueError('Unresolved submission intent; inspect scheduler before retrying')
        all_jobs = list(submission['jobs'].values()) + list(recovery['jobs'].values())
        if ssh(host, ['squeue', '-r', '-h', '-j', ','.join(all_jobs), '-o', '%i|%T']):
            raise ValueError('Original or recovery jobs remain active; collect before recovery')
        accounting = accounting_states((batch / 'accounting.tsv').read_text())
        plans = {}
        for index, case in enumerate(load(batch / 'cases.json')):
            for tool in TOOLS:
                directory = batch / 'results' / case['id'] / tool
                execution = directory / 'execution.json'
                if (directory / 'performance.json').exists() or not execution.exists():
                    continue
                record = load(execution)
                if record.get('status') not in ('pass', 'fail'):
                    continue
                job = submission['jobs']['assemble-' + tool] + '_' + str(index)
                own = accounting.get(job)
                if not own or not own[1].startswith('COMPLETED'):
                    raise ValueError('Saved output lacks successful terminal worker accounting: ' + job)
                plans.setdefault(tool, []).append({'index': index, 'dataset_id': case['id'],
                    'execution_sha256': digest(execution)})
        if recovery['jobs'] and plans:
            raise ValueError('A recovery attempt already exists; inspect its reports instead of duplicating it')
        remote_batch = str(Path(remote) / 'runs' / batch.name)
        guard = "import hashlib,json\nfrom pathlib import Path\nb=Path(" + repr(remote_batch) + ")\np=" + repr(plans) + "\nfor tool,rows in p.items():\n for row in rows:\n  d=b/'results'/row['dataset_id']/tool\n  assert not (d/'performance.json').exists(), 'Report already exists'\n  assert hashlib.sha256((d/'execution.json').read_bytes()).hexdigest()==row['execution_sha256'], 'Execution changed'\nprint('preflight verified')\n"
        subprocess.run(['ssh', '-o', 'BatchMode=yes', host, 'python3 -'], input=guard, text=True, check=True, timeout=60)
        recovery.update(plan=plans, selection_sha256=submission['selection_sha256'])
        save(recovery_path, recovery)
        for tool, rows in plans.items():
            role = 'assess-' + tool
            script = batch / 'slurm' / ('recover-' + role + '.sh')
            plan_path = batch / 'slurm' / ('recover-' + role + '.json')
            save(plan_path, {str(r['index']): r for r in rows})
            body = '#!/usr/bin/env bash\nset -euo pipefail\ncd ' + shlex.quote(remote) + '\n'
            body += 'export PATH=/users/aanensen/rva470/.pixi/bin:$PATH\nexport PIXI_CACHE_DIR=' + shlex.quote(cluster['cache_root']) + '\n'
            body += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
            body += shlex.quote(cluster['pixi']) + ' run --locked -e miniasm python - <<\'CHECK\'\n'
            body += "import hashlib,json,os\nfrom pathlib import Path\np=json.loads(Path(" + repr(str(Path('runs') / batch.name / 'slurm' / plan_path.name)) + ").read_text())[os.environ['SLURM_ARRAY_TASK_ID']]\nd=Path(" + repr(str(Path('runs') / batch.name / 'results')) + ")/p['dataset_id']/" + repr(tool) + "\nassert not (d/'performance.json').exists(), 'Assessment already exists'\nassert hashlib.sha256((d/'execution.json').read_bytes()).hexdigest()==p['execution_sha256'], 'Execution changed'\nCHECK\n"
            body += shlex.quote(cluster['pixi']) + ' run --locked -e miniasm python scripts/broad_performance.py worker --batch ' + batch.name + ' --role assess --tool ' + tool + ' --index "$SLURM_ARRAY_TASK_ID"\n'
            script.write_text(body)
            subprocess.run(['rsync', '-az', str(script), str(plan_path), host + ':' + remote_batch + '/slurm/'], check=True)
            args = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'],
                    '--cpus-per-task', '1', '--mem', '4G', '--time', '01:00:00',
                    '--array', ','.join(str(r['index']) for r in rows) + '%1000',
                    '--job-name', 'ploptimizer-recover-' + role, '--chdir', remote,
                    '--output', remote_batch + '/logs/recover-' + role + '-%A_%a.out',
                    '--error', remote_batch + '/logs/recover-' + role + '-%A_%a.err',
                    str(Path(remote_batch) / 'slurm' / script.name)]
            recovery['submission_intent'] = {'role': role, 'indices': [r['index'] for r in rows],
                'at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            save(recovery_path, recovery)
            job = ssh(host, args).split(';')[0]
            if not job.isdigit():
                raise ValueError('Unexpected scheduler reply; inspect saved intent')
            recovery['jobs'][role] = job
            recovery['task_job_overrides'].update({role + ':' + str(r['index']): job + '_' + str(r['index']) for r in rows})
            recovery.pop('submission_intent')
            save(recovery_path, recovery)
            subprocess.run(['rsync', '-az', str(recovery_path), host + ':' + remote_batch + '/'], check=True)
        return recovery


if __name__ == '__main__':
    print(json.dumps(recover(), indent=2))
