#!/usr/bin/env python3
"""Read-only checksum and graph-file audit of explicitly listed existing executions."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def audit(root, plan):
    root=root.resolve();cache={};rows=[]
    def checked(path,expected):
        path=path.resolve()
        if root not in path.parents:raise ValueError('Audit input leaves benchmark work area')
        if not expected or not path.is_file():return 'missing'
        stat=path.stat();key=(str(path),stat.st_size,stat.st_mtime_ns)
        if key not in cache:cache[key]=digest(path)
        return 'match' if cache[key]==expected else 'mismatch'
    for task in plan['executions']:
        batch=root/'runs'/task['batch'];directory=batch/'results'/task['scenario_id']/task['tool']
        if task.get('run_id'):directory=directory/'repeats'/task['run_id']
        execution=directory/'execution.json';checks={};graph_files=[]
        try:
            checks['execution']=checked(execution,task['execution_sha256'])
            record=json.loads(execution.read_text())
            input_dir=batch/'cases'/task['scenario_id'];manifest_path=input_dir/'input.json'
            checks['input_manifest']=checked(manifest_path,task['input_manifest_sha256'])
            manifest=json.loads(manifest_path.read_text())
            checks['input_admission']='match' if manifest.get('status')=='valid' else 'mismatch'
            for key,filename in [('reads_sha256','reads.fastq.gz'),('truth_sha256','truth.fasta')]:
                checks[key]=checked(input_dir/filename,manifest[key])
                checks[key+'_record']='match' if record.get(key)==manifest[key] else 'mismatch'
            if task.get('assembly_sha256'):
                checks['assembly']=checked(batch/record['assembly_file'],task['assembly_sha256'])
                checks['assembly_record']='match' if record.get('assembly_sha256')==task['assembly_sha256'] else 'mismatch'
            if task.get('graph'):
                graph=task['graph'];checks['graph']=checked(directory/graph['relative_path'],graph['sha256'])
            if task['tool']=='raven':
                graph_files=sorted(str(p.relative_to(directory)) for p in directory.rglob('*.gfa') if p.is_file())
            issues=[key for key,status in checks.items() if status!='match']
            result={'checks':checks,'issues':issues,'raven_gfa_files':graph_files}
        except (OSError,ValueError,KeyError) as error:
            result={'checks':checks,'issues':['audit_error'],'error':str(error),'raven_gfa_files':graph_files}
        rows.append({**{k:task[k] for k in ('batch','scenario_id','tool','run_id','status')},**result})
    return {'schema_version':1,'method':'existing-file-checksums-v1','execution_count':len(rows),
            'unique_files_hashed':len(cache),'records_with_issues':sum(bool(r['issues']) for r in rows),
            'executions':rows,'limitation':'Checks unchanged bytes and saved admission metadata; does not revalidate simulation biology or rerun assemblies.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    plan=json.loads(args.plan.read_text());result=audit(args.root,plan);result['plan_sha256']=digest(args.plan);result['producer_sha256']=digest(Path(__file__))
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='executions'},sort_keys=True))
    raise SystemExit(1 if result['records_with_issues'] else 0)
