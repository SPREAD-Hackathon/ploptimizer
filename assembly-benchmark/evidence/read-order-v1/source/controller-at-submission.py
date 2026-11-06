"""Plan, submit, run and collect the isolated 48-execution S7 panel."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT,digest,fingerprint,load,save
from pipeline.cluster import ssh
from pipeline.read_order import stage_inputs,summarise,output_signature
from pipeline.read_order_report import render
STATE=ROOT/'evidence/read-order-v1/status.json'
CONFIG=ROOT/'config/read-order.json'


def plan():
    config=load(CONFIG);panel=config['read_order']
    if config['tools']!=['flye','flye-meta','raven','plassembler'] or config['threads']!=4 or panel['repeats_per_order']!=3 or panel['expected_executions']!=48:
        raise ValueError('Only the authorised 48-execution S7 panel is supported')
    if panel['orders']!=[{'id':'original','shuffle_seed':None},{'id':'shuffle-1','shuffle_seed':1},{'id':'shuffle-2','shuffle_seed':2},{'id':'shuffle-3','shuffle_seed':3}]:
        raise ValueError('Input orders differ from the frozen design')
    return {'schema_version':1,'category':'S7','status':'ready_not_submitted','config_fingerprint':fingerprint(config),'config_sha256':digest(CONFIG),'expected_executions':48,'input_orders':4,'repeats_per_order':3,'tools':config['tools'],'source':panel['source']}


def stage(batch):
    submission=load(batch/'submission.json');config=load(batch/'config.json');source=config['read_order']['source']
    result=stage_inputs(batch,Path(submission['source_root'])/'runs'/source['batch']/'cases'/source['case_id'])
    print(json.dumps({'status':result['status'],'orders':len(result['orders']),'records_per_order':result['orders'][0]['record_count']}))


def execute(batch,tool,index):
    from pipeline.execution import run
    config=load(batch/'config.json');tasks=[t for t in load(batch/'tasks.json')['assemble'] if t['tool']==tool];task=tasks[index]
    case=next(c for c in load(batch/'cases.json') if c['id']==task['scenario'])
    if int(os.environ.get('SLURM_CPUS_PER_TASK',config['threads']))!=config['threads']:raise ValueError('Slurm allocation differs from frozen threads')
    record=run(case,tool,batch,config);directory=batch/'results'/case['id']/tool
    result={'schema_version':1,'status':'skipped','execution_sha256':digest(directory/'execution.json'),'order_id':task['order_id'],'repeat':task['repeat']}
    if record['status'] in ('pass','fail'):
        try:result.update(status='complete',signature=output_signature(directory,record))
        except Exception as error:result.update(status='error',error=f'{type(error).__name__}: {error}')
    else:result['error']=record.get('error','Assembler execution did not complete')
    save(directory/'read_order_signature.json',result)
    print(json.dumps({'scenario':case['id'],'tool':tool,'execution':record['status'],'signature':result['status']}))
    return 0 if record['status'] in ('pass','fail') and result['status']=='complete' else 1


def report(batch):
    submission=load(batch/'submission.json')
    accounting=subprocess.check_output(['sacct','--array','-n','-P','-j',','.join(submission['jobs'].values()),'--format=JobID,State,ExitCode,Elapsed,MaxRSS'],text=True)
    (batch/'accounting.tsv').write_text(accounting)
    result=summarise(batch);save(batch/'summary.json',result);render(result,batch/'report')
    print(json.dumps({'complete':result['complete'],'status_counts':result['status_counts'],'verdicts':{t['tool']:t['end_sensitive']['verdict'] for t in result['tools']}}))
    return result


def sync_file(host,remote,path):
    subprocess.run(['rsync','-az',str(path),host+':'+remote],check=True)


def submit():
    planned=plan()
    if STATE.exists():
        state=load(STATE)
        if state['config_fingerprint']!=planned['config_fingerprint']:raise ValueError('S7 configuration changed; do not submit duplicates')
        if state['status'] not in ('submitted','results_complete','running_or_needs_review'):raise ValueError('Partial submission exists; inspect checkpoint')
        return state
    config=load(CONFIG);cluster=load(ROOT/'config/cluster.local.json')
    if cluster['array_concurrency']!=1000 or cluster['cpus']!=4:raise ValueError('Keep the authorised cap and thread count')
    source_root=cluster['remote_root'];cluster['remote_root']=source_root+'/.s7';remote_root=cluster['remote_root'];host=cluster['host']
    try:
        ssh(host,['test','!','-e',remote_root])
    except subprocess.CalledProcessError:
        owner=json.loads(ssh(host,['cat',remote_root+'/s7-owner.json']))
        if owner.get('config_fingerprint')!=planned['config_fingerprint']:
            raise ValueError('Existing source root does not belong to this frozen S7 panel')
    ssh(host,['mkdir','-p',remote_root+'/pipeline',remote_root+'/scripts',remote_root+'/tests'])
    owner=ROOT/'.cache/s7-owner.json';save(owner,{'config_fingerprint':planned['config_fingerprint'],'panel':'S7'})
    sync_file(host,remote_root+'/',owner)
    subprocess.run(['rsync','-az','--exclude=__pycache__','--exclude=performance',str(ROOT/'pipeline')+'/',host+':'+remote_root+'/pipeline/'],check=True)
    for name in ('pixi.toml','pixi.lock'):sync_file(host,remote_root+'/',ROOT/name)
    sync_file(host,remote_root+'/scripts/',ROOT/'scripts/read_order.py')
    sync_file(host,remote_root+'/tests/',ROOT/'tests/test_read_order.py')
    identifier=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S');batch=ROOT/'runs'/identifier
    (batch/'slurm').mkdir(parents=True,exist_ok=False);(batch/'logs').mkdir();save(batch/'config.json',config)
    tasks=[]
    for tool in config['tools']:
        index=0
        for order in config['read_order']['orders']:
            for repeat in range(1,4):
                tasks.append({'scenario':f"s7-se11-{order['id']}-repeat-{repeat}",'tool':tool,'order_id':order['id'],'repeat':repeat,'tool_index':index});index+=1
    save(batch/'tasks.json',{'assemble':tasks})
    record={'batch_id':identifier,'cluster':cluster,'source_root':source_root,'jobs':{},'status':'submitting',
            'runtime_source_sha256':{str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'pipeline').glob('*.py')},'worker_sha256':digest(ROOT/'scripts/read_order.py')}
    save(batch/'submission.json',record)
    state={**planned,'batch_id':identifier,'status':'submitting','jobs':{},'remote_root':remote_root};save(STATE,state)
    prefix='#!/usr/bin/env bash\nset -euo pipefail\ncd '+shlex.quote(remote_root)+'\nexport PATH=/users/aanensen/rva470/.pixi/bin:$PATH\n'
    prefix+='export PIXI_CACHE_DIR='+shlex.quote(source_root+'/.cache/pixi')+'\nexport TMPDIR="$PWD/.t/$SLURM_JOB_ID"\nmkdir -p "$TMPDIR"\n'
    pixi=shlex.quote(cluster['pixi'])
    roles={'prepare':''.join(f'{pixi} install --locked -e {env}\n' for env in ('default','flye','raven','plassembler'))+f'{pixi} run --locked -e default python -m unittest discover -s tests -p test_read_order.py\n{pixi} run --locked -e default python scripts/read_order.py stage --batch {identifier}\n'}
    for tool in config['tools']:
        env='flye' if tool=='flye-meta' else tool
        roles['assemble-'+tool]=f'{pixi} run --locked -e {env} python scripts/read_order.py execute --batch {identifier} --tool {tool} --index "$SLURM_ARRAY_TASK_ID"\n'
    roles['report']=f'{pixi} run --locked -e default python scripts/read_order.py report --batch {identifier}\n'
    for role,body in roles.items():(batch/'slurm'/f'{role}.sh').write_text(prefix+body)
    remote_batch=remote_root+'/runs/'+identifier;ssh(host,['mkdir','-p',remote_batch])
    subprocess.run(['rsync','-az',str(batch)+'/',host+':'+remote_batch+'/'],check=True)
    for role in roles:
        args=['sbatch','--parsable','--account',cluster['account'],'--partition',cluster['partition'],'--chdir',remote_root,'--job-name','ploptimizer-s7-'+role,'--output',remote_batch+'/logs/'+role+'-%A_%a.out','--error',remote_batch+'/logs/'+role+'-%A_%a.err']
        if role.startswith('assemble-'):
            args+=['--cpus-per-task','4','--mem',cluster['memory'],'--time','02:00:00' if role=='assemble-plassembler' else cluster['time'],'--array','0-11%1000','--dependency','afterok:'+record['jobs']['prepare'],'--kill-on-invalid-dep=yes']
        elif role=='prepare':args+=['--cpus-per-task','1','--mem','8G','--time','01:00:00']
        else:args+=['--cpus-per-task','1','--mem','4G','--time','00:30:00','--dependency','afterany:'+':'.join(record['jobs']['assemble-'+t] for t in config['tools']),'--kill-on-invalid-dep=yes']
        job=ssh(host,args+[remote_batch+'/slurm/'+role+'.sh']).split(';')[0]
        if not job.isdigit():raise ValueError('Unexpected Slurm job identifier')
        record['jobs'][role]=job;state['jobs']=record['jobs'].copy();save(batch/'submission.json',record);save(STATE,state)
        sync_file(host,remote_batch+'/',batch/'submission.json')
    record['status']='submitted';state['status']='submitted';save(batch/'submission.json',record);save(STATE,state);sync_file(host,remote_batch+'/',batch/'submission.json')
    return state


def collect():
    state=load(STATE);batch=ROOT/'runs'/state['batch_id'];record=load(batch/'submission.json');cluster=record['cluster'];host=cluster['host'];source=cluster['remote_root']+'/runs/'+batch.name+'/'
    args=['rsync','-az','--max-size=2m','--include=*/']
    for name in ('input.json','input_orders.json','cases.json','execution.json','read_order_signature.json','summary.json','accounting.tsv','stderr.log','*.out','*.err','index.html','runs.tsv','orders.tsv'):args+=['--include='+name]
    subprocess.run(args+['--exclude=*',host+':'+source,str(batch)+'/'],check=True)
    accounting=ssh(host,['sacct','--array','-n','-P','-j',','.join(record['jobs'].values()),'--format=JobID,State,ExitCode,Elapsed,MaxRSS']);(batch/'accounting.tsv').write_text(accounting)
    if (batch/'input_orders.json').exists():
        summary=summarise(batch);save(batch/'summary.json',summary);render(summary,batch/'report')
        state.update(status='results_complete' if summary['complete'] else 'running_or_needs_review',status_counts=summary['status_counts'],verdicts={r['tool']:r['end_sensitive']['verdict'] for r in summary['tools']},report=str((batch/'report').relative_to(ROOT)))
    save(STATE,state);return state


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['plan','submit','stage','execute','report','collect']);parser.add_argument('--batch');parser.add_argument('--tool');parser.add_argument('--index',type=int);args=parser.parse_args()
    if args.action in ('plan','submit','collect'):print(json.dumps({'plan':plan,'submit':submit,'collect':collect}[args.action](),indent=2))
    else:
        if not args.batch or Path(args.batch).name!=args.batch:raise ValueError('Use a simple batch identifier')
        batch=ROOT/'runs'/args.batch
        if args.action=='stage':stage(batch)
        elif args.action=='execute':raise SystemExit(execute(batch,args.tool,args.index))
        else:report(batch)
