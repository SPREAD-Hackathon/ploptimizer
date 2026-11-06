"""Submit/collect only the authorised 24-execution larger-plasmid S6 panel."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.cases import plan
from pipeline.cluster import collect, ssh, submit
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.determinism import assembly_tasks
from scripts.large_baseline import queue_evidence

CONFIG = ROOT/'config/noisy-large.json'
CHECKPOINT = ROOT/'.cache/s6-large-v1/checkpoint.json'
STATUS = ROOT/'evidence/s6-large-v1/status.json'
COMPARISON_LABEL = 's6-large-v1'


def panel_plan():
    config=load(CONFIG)
    cases=plan(config)
    tasks=assembly_tasks(config,cases)
    if len(cases)!=6 or len(tasks)!=24 or config.get('assessment_mode')!='continuous-evidence-v1':
        raise ValueError('The authorised S6 panel must contain six inputs and 24 executions')
    for case in cases:
        plasmids=[r for r in case['replicons'] if r['molecule_type']=='plasmid']
        if len(plasmids)!=1 or plasmids[0]['length_bp']<20000 or not case.get('frozen_source'):
            raise ValueError('S6 requires one larger plasmid and a declared frozen source per input')
    return {'schema_version':1,'status':'ready_not_submitted','config':str(CONFIG.relative_to(ROOT)),
            'config_sha256':digest(CONFIG),'config_fingerprint':fingerprint(config),
            'input_count':6,'assembly_count':24,'scenario_ids':[c['id'] for c in cases],
            'assessment_mode':config['assessment_mode'],
            'binary_tolerant_endpoint':'Unscored; continuous evidence and exact scores reported separately.',
            'source_fragments':config['noisy_panel']['frozen_sources']}


def checkpoint(state):
    state['updated_at']=datetime.now(timezone.utc).isoformat()
    save(CHECKPOINT,state)
    save(STATUS,state)
    return state


def submit_panel():
    planned=panel_plan()
    cluster=load(ROOT/'config/cluster.local.json')
    if cluster.get('array_concurrency')!=1000:
        raise ValueError('Use the authorised 1000-task cap; let Slurm schedule resources')
    ssh(cluster['host'],['true'])
    state=load(CHECKPOINT) if CHECKPOINT.exists() else planned
    if state['config_fingerprint']!=planned['config_fingerprint']:
        raise ValueError('Configuration differs from the existing S6 checkpoint; inspect before proceeding')
    if not state.get('batch_id'):
        before=set((ROOT/'runs').iterdir())
        try:
            record=submit(load(CONFIG),cluster)
        except Exception as error:
            created=set((ROOT/'runs').iterdir())-before
            if len(created)==1:state['batch_id']=created.pop().name
            state.update(status='submission_needs_review',error=str(error))
            checkpoint(state)
            raise
        state.update(batch_id=record['batch_id'],source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        checkpoint(state)
    batch=ROOT/'runs'/state['batch_id']
    record=load(batch/'submission.json')
    if record['status']!='submitted':
        raise ValueError('Partial submission requires inspection; no duplicate assembly tasks will be created')
    if not record['jobs'].get('evidence'):
        queue_evidence(batch,cluster,comparison_label=COMPARISON_LABEL)
        record=load(batch/'submission.json')
    state.update(jobs=record['jobs'],status='submitted')
    return checkpoint(state)


def input_audit(batch):
    expected={case['id']:case for case in plan(load(batch/'config.json'))}
    rows=[]
    for scenario,case in expected.items():
        path=batch/'cases'/scenario/'input.json'
        if not path.exists():continue
        manifest=load(path);source=case['frozen_source']
        matched=all(manifest.get(generated)==source[original] for generated,original in
                    [('source_fragments_sha256','reads_sha256'),('source_truth_sha256','truth_sha256'),('source_origins_sha256','origins_sha256')])
        if case['error_profile']['id']=='matched-exact':
            matched=matched and manifest.get('reads_sha256')==source['reads_sha256']
        matched=matched and manifest.get('case')==case and manifest.get('status')=='valid'
        rows.append({'scenario_id':scenario,'status':manifest.get('status'),'source_hashes_match':matched,
                     'input_manifest_sha256':digest(path),'reads_sha256':manifest.get('reads_sha256'),
                     'source_fragments_sha256':manifest.get('source_fragments_sha256')})
    result={'schema_version':1,'batch_id':batch.name,'expected_inputs':6,
            'status':'complete' if len(rows)==6 and all(r['source_hashes_match'] for r in rows) else 'needs_review' if any(not r['source_hashes_match'] for r in rows) else 'pending',
            'inputs':rows,'scope':'Recorded manifest and frozen-source hash equivalence; source reads are retained on BMRC.'}
    save(ROOT/'evidence/s6-large-v1/input-audit.json',result)
    return result


def collect_panel():
    state=load(CHECKPOINT)
    batch=ROOT/'runs'/state['batch_id']
    collect(batch)
    record=load(batch/'submission.json');cluster=record['cluster']
    remote=Path(cluster['remote_root'])
    state['input_audit']=input_audit(batch)
    try:
        ssh(cluster['host'],['test','-f',str(remote/'runs'/batch.name/'evidence_status.json')])
        available=True
    except subprocess.CalledProcessError as error:
        if error.returncode!=1:raise
        available=False
    if available:
        subprocess.run(['rsync','-az',cluster['host']+':'+str(remote/'runs'/batch.name/'evidence_status.json'),str(batch)+'/'],check=True)
        state['evidence']=load(batch/'evidence_status.json')
        if state['evidence']['status']=='complete':
            subprocess.run(['rsync','-az','--exclude=*.delta',cluster['host']+':'+str(remote/'runs'/batch.name/'comparisons')+'/',str(batch/'comparisons')+'/'],check=True)
            subprocess.run(['rsync','-az',cluster['host']+':'+str(remote/'published'/(batch.name+'.json')),str(ROOT/'published')+'/'],check=True)
    failed_states={'FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','BOOT_FAIL','DEADLINE'}
    scheduler_failure=any(len(fields)>1 and fields[1].strip() and fields[1].split()[0].rstrip('+') in failed_states
                          for fields in (line.split('|') for line in (batch/'accounting.tsv').read_text().splitlines()))
    if state.get('evidence',{}).get('status')=='complete' and state['input_audit']['status']=='complete':
        state['status']='evidence_complete'
    elif scheduler_failure or state['input_audit']['status']=='needs_review' or state.get('evidence',{}).get('status')=='needs_review':
        state['status']='needs_review'
    else:
        state['status']='running'
    return checkpoint(state)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','submit','collect'])
    action=parser.parse_args().action
    print(json.dumps({'plan':panel_plan,'submit':submit_panel,'collect':collect_panel}[action](),indent=2))
