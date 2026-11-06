"""Plan, submit and collect the bounded 168-execution replacement panels."""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.cases import plan
from pipeline.cluster import collect, ssh, submit
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.determinism import assembly_tasks

PROFILES = [('S1','baseline-large',8), ('S2','coverage-large',40), ('S3','repeatability-large',120)]
CHECKPOINT = ROOT / '.cache/large-baseline-v3/checkpoint.json'


def suite_plan():
    panels = []
    for family, name, count in PROFILES:
        path = ROOT / 'config' / (name + '.json')
        config = load(path)
        cases = plan(config)
        tasks = assembly_tasks(config, cases)
        if len(tasks) != count:
            raise ValueError('Unexpected task count: ' + name)
        panels.append({'family':family, 'config':str(path.relative_to(ROOT)),
                       'config_sha256':digest(path), 'config_fingerprint':fingerprint(config),
                       'input_count':len(cases), 'assembly_count':len(tasks),
                       'scenario_ids':[case['id'] for case in cases]})
    return {'schema_version':1,'status':'ready_not_submitted','panels':panels,'assembly_count':168}


def queue_evidence(batch, cluster, previous_evidence):
    record = load(batch / 'submission.json')
    directory = Path(cluster['remote_root']) / 'runs' / batch.name
    pixi = shlex.quote(cluster['pixi'])
    body = '#!/usr/bin/env bash\nset -euo pipefail\n'
    body += f'cd {shlex.quote(cluster["remote_root"])}\n'
    body += f'export PATH={shlex.quote(str(Path(cluster["pixi"]).parent))}:"$PATH"\n'
    body += 'export PIXI_CACHE_DIR="$PWD/.cache/pixi"\nexport XDG_CACHE_HOME="$PWD/.cache"\n'
    body += 'export TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
    body += f'{pixi} install --locked --manifest-path environments/coordinate-comparison/pixi.toml\n'
    body += f'{pixi} run --locked --manifest-path environments/coordinate-comparison/pixi.toml python scripts/finish_batch_evidence.py --batch {batch.name}\n'
    script = batch / 'slurm/evidence.sh'
    script.write_text(body)
    subprocess.run(['rsync','-az',str(script),cluster['host']+':'+str(directory / 'slurm')+'/'],check=True)
    dependencies = [record['jobs']['assemble'],record['jobs']['report']]
    if previous_evidence:dependencies.append(previous_evidence)
    job = ssh(cluster['host'], ['sbatch','--parsable','--account',cluster['account'],
        '--partition',cluster['partition'],'--chdir',cluster['remote_root'],
        '--job-name','ploptimizer-evidence','--cpus-per-task','1','--mem','8G','--time','04:00:00',
        '--dependency','afterany:'+':'.join(dependencies),'--kill-on-invalid-dep=yes',
        '--output',str(directory / 'logs/evidence-%j.out'),'--error',str(directory / 'logs/evidence-%j.err'),
        str(directory / 'slurm/evidence.sh')]).split(';')[0]
    if not job.isdigit():raise ValueError('Unexpected evidence job identifier')
    record['jobs']['evidence'] = job
    save(batch / 'submission.json',record)
    subprocess.run(['rsync','-az',str(batch / 'submission.json'),cluster['host']+':'+str(directory)+'/'],check=True)
    return job


def submit_suite():
    planned = suite_plan()
    cluster = load(ROOT / 'config/cluster.local.json')
    # Authenticate before creating any run directory or submitting any task.
    ssh(cluster['host'], ['true'])
    state = load(CHECKPOINT) if CHECKPOINT.exists() else planned
    if [(p['config'],p['config_fingerprint']) for p in state['panels']] != [(p['config'],p['config_fingerprint']) for p in planned['panels']]:
        raise ValueError('Checkpoint configurations changed; inspect the existing suite before proceeding')
    previous = None
    for panel in state['panels']:
        if not panel.get('batch_id'):
            before = set((ROOT / 'runs').iterdir())
            try:
                record = submit(load(ROOT / panel['config']), cluster,
                                after_job=previous['jobs']['prepare'] if previous else None)
            except Exception:
                created = set((ROOT / 'runs').iterdir()) - before
                if len(created) == 1:panel['batch_id'] = created.pop().name
                state['status'] = 'submission_needs_review'
                save(CHECKPOINT,state)
                raise
            panel['batch_id'] = record['batch_id']
            save(CHECKPOINT,state)
        batch = ROOT / 'runs' / panel['batch_id']
        record = load(batch / 'submission.json')
        if record['status'] != 'submitted':
            raise ValueError('Partial submission requires inspection; refusing duplicate tasks')
        if not record['jobs'].get('evidence'):
            queue_evidence(batch,cluster,previous['jobs'].get('evidence') if previous else None)
            record = load(batch / 'submission.json')
        panel['jobs'] = record['jobs']
        previous = record
        save(CHECKPOINT,state)
    state['status'] = 'submitted'
    save(CHECKPOINT,state)
    return state


def collect_suite():
    state = load(CHECKPOINT)
    for panel in state['panels']:
        if not panel.get('batch_id'):continue
        batch = ROOT / 'runs' / panel['batch_id']
        collect(batch)
        record = load(batch / 'submission.json')
        cluster = record['cluster']
        remote = Path(cluster['remote_root'])
        try:
            ssh(cluster['host'],['test','-f',str(remote / 'runs' / batch.name / 'evidence_status.json')])
            available = True
        except subprocess.CalledProcessError as error:
            if error.returncode != 1:raise
            available = False
        if available:
            subprocess.run(['rsync','-az',cluster['host']+':'+str(remote / 'runs' / batch.name / 'evidence_status.json'),str(batch)+'/'],check=True)
            evidence = load(batch / 'evidence_status.json')
            panel['evidence'] = evidence
            if evidence['status'] == 'complete':
                subprocess.run(['rsync','-az','--exclude=*.delta',cluster['host']+':'+str(remote / 'runs' / batch.name / 'comparisons')+'/',str(batch / 'comparisons')+'/'],check=True)
                subprocess.run(['rsync','-az',cluster['host']+':'+str(remote / 'published' / (batch.name+'.json')),str(ROOT / 'published')+'/'],check=True)
    state['status'] = 'evidence_complete' if all(p.get('evidence',{}).get('status') == 'complete' for p in state['panels']) else 'running_or_needs_review'
    save(CHECKPOINT,state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','submit','collect'])
    action = parser.parse_args().action
    print(json.dumps({'plan':suite_plan,'submit':submit_suite,'collect':collect_suite}[action](),indent=2))
