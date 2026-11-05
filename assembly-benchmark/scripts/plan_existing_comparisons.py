#!/usr/bin/env python3
"""Freeze comparison tasks from completed execution metadata, without running tools."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan(batch,label,cluster_path):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',batch) or not re.fullmatch(r'[A-Za-z0-9_-]+',label):
        raise ValueError('Batch and comparison label must be simple identifiers')
    source=ROOT/'published'/f'{batch}.json';document=json.loads(source.read_text())
    cluster=json.loads(Path(cluster_path).read_text());tasks=[]
    if document.get('batch')!=batch:raise ValueError('Snapshot batch differs from the selected batch')
    for record in document['results']:
        if record.get('status') not in ('pass','fail'):continue
        scenario,tool=record['scenario_id'],record['tool']
        if not all(re.fullmatch(r'[A-Za-z0-9_.-]+',v) for v in (scenario,tool)):
            raise ValueError('Invalid execution identifier')
        relative=Path('results')/scenario/tool
        if record.get('run_id'):
            if not re.fullmatch(r'[A-Za-z0-9_.-]+',record['run_id']):raise ValueError('Invalid run identity')
            relative=relative/'repeats'/record['run_id']
        execution=ROOT/'runs'/batch/relative/'execution.json'
        actual=json.loads(execution.read_text())
        for key in ('scenario_id','tool','status','assembly_sha256','truth_sha256'):
            if not record.get(key) or record[key]!=actual.get(key):
                raise ValueError(f'Frozen snapshot differs from the actual execution: {key}')
        output=Path('runs')/batch/'comparisons'/label/scenario/tool
        if record.get('run_id'):output=output/record['run_id']
        tasks.append({'batch':batch,'scenario_id':scenario,'tool':tool,'run_id':record.get('run_id'),
                      'execution_relative_path':str(relative/'execution.json'),'execution_sha256':digest(execution),
                      'assembly_sha256':record['assembly_sha256'],'truth_sha256':record['truth_sha256'],
                      'output_relative_path':str(output)})
    if not tasks:raise ValueError('No completed scored executions are available for comparison')
    return {'schema_version':1,'remote_root':cluster['remote_root'],
            'source_snapshot_sha256':digest(source),'environment_relative_path':'environments/coordinate-comparison',
            'pixi_version':'0.73.0','tasks':tasks}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True);parser.add_argument('--label',required=True)
    parser.add_argument('--cluster',default=str(ROOT/'config/cluster.local.json'))
    parser.add_argument('--output',required=True)
    args=parser.parse_args();destination=Path(args.output).resolve()
    if ROOT not in destination.parents:raise ValueError('Task manifest must stay inside assembly-benchmark')
    result=plan(args.batch,args.label,args.cluster)
    content=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if destination.exists() and destination.read_text()!=content:
        raise ValueError('Existing manifest differs; choose a new comparison label/output')
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(content)
    print(f'Prepared {len(result["tasks"])} existing-output comparison tasks: {destination}')


if __name__=='__main__':main()
