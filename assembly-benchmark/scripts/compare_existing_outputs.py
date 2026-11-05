#!/usr/bin/env python3
"""Compare existing reference/output files without changing assembly assessments."""
import argparse
import csv
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path


def digest(path):
    checksum=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):checksum.update(chunk)
    return checksum.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def save(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    temporary.replace(path)


def inside(root,relative):
    value=Path(relative)
    if value.is_absolute():raise ValueError('Expected a path relative to the batch')
    result=(root/value).resolve()
    if root.resolve() not in result.parents:raise ValueError('Path escapes batch')
    return result


def inventory(path):
    """Retain identifiers/lengths, never nucleotide strings."""
    records=[];identifier=None;length=0
    with path.open() as stream:
        for line in stream:
            if line.startswith('>'):
                if identifier is not None:records.append({'id':identifier,'length':length})
                identifier=line[1:].split()[0];length=0
            elif line.strip():
                if identifier is None:raise ValueError('Sequence data precede a FASTA identifier')
                length+=len(line.strip())
    if identifier is not None:records.append({'id':identifier,'length':length})
    if not records or len({r['id'] for r in records})!=len(records) or any(r['length']<=0 for r in records):
        raise ValueError('FASTA inventory is empty, duplicated or has empty records')
    return records


def parse_coords(path,references,queries):
    expected_reference={r['id']:r['length'] for r in references}
    expected_query={r['id']:r['length'] for r in queries}
    rows=[]
    with path.open() as stream:
        for number,fields in enumerate(csv.reader(stream,delimiter='\t'),1):
            if not fields:continue
            if len(fields)!=11:raise ValueError(f'Coordinate row {number} is not the expected eleven-column format')
            r1,r2,q1,q2,span_reference,span_query=map(int,fields[:6])
            identity=float(fields[6]);length_reference,length_query=map(int,fields[7:9]);reference,query=fields[9:]
            if expected_reference.get(reference)!=length_reference or expected_query.get(query)!=length_query:
                raise ValueError('Coordinate identifiers/lengths do not match the input inventories')
            if not 1<=min(r1,r2)<=max(r1,r2)<=length_reference or not 1<=min(q1,q2)<=max(q1,q2)<=length_query or not 0<=identity<=100:
                raise ValueError('Coordinate endpoints or identity are invalid')
            if span_reference!=abs(r2-r1)+1 or span_query!=abs(q2-q1)+1:raise ValueError('Coordinate spans disagree with endpoints')
            rows.append({'reference_id':reference,'query_id':query,
                         'reference_interval':[min(r1,r2)-1,max(r1,r2)],'query_interval':[min(q1,q2)-1,max(q1,q2)],
                         'reference_length':length_reference,'query_length':length_query,
                         'strand':'+' if (r2-r1)*(q2-q1)>=0 else '-',
                         'identity_percent':identity,'source_row':number,
                         'original_endpoints_1based_inclusive':[r1,r2,q1,q2]})
    return rows


def prepare_inputs(root,task):
    batch=inside(root,'runs/'+task['batch'])
    execution=inside(batch,task['execution_relative_path']);record=load(execution)
    manifest=inside(batch,'cases/'+task['scenario_id']+'/input.json');inputs=load(manifest)
    if record.get('status') not in ('pass','fail') or record.get('scenario_id')!=task['scenario_id'] or record.get('tool')!=task['tool']:
        raise ValueError('Task does not identify a completed scored execution')
    if inputs.get('status')!='valid' or inputs.get('case',{}).get('id')!=task['scenario_id']:
        raise ValueError('Input manifest is not a valid matching scenario')
    if digest(execution)!=task['execution_sha256']:raise ValueError('Execution metadata differ from the frozen task')
    truth=inside(batch,'cases/'+task['scenario_id']+'/truth.fasta');assembly=inside(batch,record['assembly_file'])
    hashes={'execution_sha256':digest(execution),'input_manifest_sha256':digest(manifest),'truth_sha256':digest(truth),'assembly_sha256':digest(assembly)}
    if hashes['truth_sha256']!=task['truth_sha256'] or hashes['truth_sha256']!=record.get('truth_sha256') or hashes['truth_sha256']!=inputs.get('truth_sha256'):
        raise ValueError('Reference bytes do not match frozen input hashes')
    if hashes['assembly_sha256']!=task['assembly_sha256'] or hashes['assembly_sha256']!=record.get('assembly_sha256'):
        raise ValueError('Assembly bytes do not match the scored output')
    return execution,truth,assembly,hashes,record['status']


def run_task(manifest_path,index,nucmer='nucmer',show_coords='show-coords'):
    manifest_path=Path(manifest_path).resolve();manifest=load(manifest_path);root=Path(manifest['remote_root']).resolve()
    task=manifest['tasks'][index]
    output=inside(root,task['output_relative_path']);output.mkdir(parents=True,exist_ok=True)
    result={'schema_version':1,'status':'running','kind':'reference_vs_existing_assembly','batch_id':task['batch'],
            'scenario_id':task['scenario_id'],'tool':task['tool'],'alignment_source':'NUCmer',
            'coordinate_system':'0-based half-open','original_coordinate_system':'show-coords 1-based inclusive',
            'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
            'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'slurm_array_task_id':os.environ.get('SLURM_ARRAY_TASK_ID'),
            'comparison_manifest_sha256':digest(manifest_path),'comparison_script_sha256':digest(Path(__file__)),
            'nucmer_policy':'Default NUCmer comparison; one worker; no delta filtering or assembly correction',
            'score_scope':'Supplementary coordinate evidence only; original assembly and endpoint score are unchanged'}
    environment=inside(root,manifest['environment_relative_path'])
    result['environment']={'pixi_version':manifest.get('pixi_version'),'manifest_sha256':digest(environment/'pixi.toml'),'lock_sha256':digest(environment/'pixi.lock')}
    save(output/'comparison.json',result)
    try:
        execution,truth,assembly,hashes,score=prepare_inputs(root,task)
        result.update(input_hashes=hashes,original_exact_status=score,
                      references=inventory(truth),queries=inventory(assembly))
        version=subprocess.run([nucmer,'--version'],capture_output=True,text=True,check=True,timeout=30)
        result['mapper_version']=(version.stdout+version.stderr).strip()
        if '4.0.1' not in result['mapper_version']:
            raise ValueError('NUCmer version differs from the pinned comparison environment')
        prefix=output/'alignment'
        command=[nucmer,'--threads','1','--prefix',str(prefix),str(truth),str(assembly)]
        coordinate_command=[show_coords,'-THrl',str(prefix)+'.delta']
        result['command']=command;result['coordinate_command']=coordinate_command
        save(output/'comparison.json',result)
        with (output/'nucmer.stdout.log').open('w') as stdout,(output/'nucmer.stderr.log').open('w') as stderr:
            subprocess.run(command,stdout=stdout,stderr=stderr,check=True,timeout=1200)
        with (output/'coordinates.tsv').open('w') as stdout,(output/'show-coords.stderr.log').open('w') as stderr:
            subprocess.run(coordinate_command,stdout=stdout,stderr=stderr,check=True,timeout=120)
        result['alignments']=parse_coords(output/'coordinates.tsv',result['references'],result['queries'])
        if digest(truth)!=hashes['truth_sha256'] or digest(assembly)!=hashes['assembly_sha256'] or digest(execution)!=hashes['execution_sha256']:
            raise ValueError('Original inputs or execution changed during the comparison')
        result['output_hashes']={name:digest(output/name) for name in ('alignment.delta','coordinates.tsv','nucmer.stdout.log','nucmer.stderr.log','show-coords.stderr.log')}
        result['status']='complete';result['alignment_count']=len(result['alignments'])
    except Exception as error:
        result.update(status='error',error=f'{type(error).__name__}: {error}')
    result['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    save(output/'comparison.json',result)
    print(json.dumps({k:result.get(k) for k in ('batch_id','scenario_id','tool','status','alignment_count','error')}))
    return 0 if result['status']=='complete' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True);parser.add_argument('--index',type=int,required=True)
    parser.add_argument('--nucmer',default='nucmer');parser.add_argument('--show-coords',default='show-coords')
    args=parser.parse_args()
    return run_task(args.manifest,args.index,args.nucmer,args.show_coords)


if __name__=='__main__':raise SystemExit(main())
