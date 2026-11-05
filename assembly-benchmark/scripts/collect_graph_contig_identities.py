#!/usr/bin/env python3
"""Record whole-segment/contig identity hashes from existing final output files."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fasta_hashes(path):
    rows=[]
    with path.open('rb') as stream:
        for line in stream:
            if line.startswith(b'>'):
                rows.append({'id':line[1:].split()[0].decode('ascii'),'length_bp':0,'digest':hashlib.sha256()})
            elif line.strip():
                if not rows: raise ValueError('Invalid FASTA order')
                sequence=line.strip().upper();rows[-1]['digest'].update(sequence);rows[-1]['length_bp']+=len(sequence)
    if len({row['id'] for row in rows})!=len(rows): raise ValueError('Duplicate contig identifiers')
    return [{'id':r['id'],'length_bp':r['length_bp'],'sha256':r['digest'].hexdigest()} for r in rows]


def identities(assembly, graph):
    by_hash={}
    for contig in fasta_hashes(assembly):by_hash.setdefault((contig['sha256'],contig['length_bp']),[]).append(contig['id'])
    result=[];seen=set()
    with graph.open('rb') as stream:
        for line in stream:
            if not line.startswith(b'S\t'):continue
            fields=line.rstrip(b'\r\n').split(b'\t');name=fields[1].decode('ascii')
            if name in seen:raise ValueError('Duplicate segment identifiers')
            seen.add(name)
            if fields[2]==b'*':continue
            sequence=fields[2].upper();value=hashlib.sha256(sequence).hexdigest()
            for contig in by_hash.get((value,len(sequence)),[]):
                result.append({'segment_id':name,'contig_id':contig,'length_bp':len(sequence),'sequence_sha256':value,'orientation':'+'})
    return result


def collect(batch, metadata_root=None):
    batch=batch.resolve();count=0;matches=0
    for execution in sorted((batch/'results').rglob('execution.json')):
        record=json.loads(execution.read_text())
        sidecar=(Path(metadata_root)/batch.name/execution.relative_to(batch).parent/'graph_artifacts.json') if metadata_root else execution.parent/'graph_artifacts.json'
        if record.get('status') not in ('pass','fail') or not sidecar.is_file():continue
        artifact=json.loads(sidecar.read_text());graph=artifact.get('graph',{});source=graph.get('source',{})
        if graph.get('status')!='available' or graph.get('complete') is not True or source.get('role')!='final':continue
        candidates=[r for r in artifact.get('collection',{}).get('candidate_files',[]) if r.get('kind')=='gfa' and r.get('role')=='final' and r.get('status')=='available' and Path(r['relative_path']).name==source['filename']]
        if len(candidates)!=1:raise ValueError('Cannot identify final GFA source')
        assembly=(batch/record['assembly_file']).resolve();gfa=(execution.parent/candidates[0]['relative_path']).resolve()
        if batch not in assembly.parents or batch not in gfa.parents:raise ValueError('Input leaves source batch')
        if digest(assembly)!=record['assembly_sha256'] or digest(gfa)!=source['file_sha256']:raise ValueError('Original output hash mismatch')
        rows=identities(assembly,gfa)
        if digest(assembly)!=record['assembly_sha256'] or digest(gfa)!=source['file_sha256']:raise ValueError('Output changed during collection')
        data={'schema_version':1,'method':'whole_segment_contig_sha256_v1','assembly_sha256':record['assembly_sha256'],'gfa_sha256':source['file_sha256'],'execution_sha256':digest(execution),'producer_sha256':digest(Path(__file__)),'associations':rows}
        target=execution.parent/'graph_contig_identity.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');tmp.replace(target)
        count+=1;matches+=len(rows)
    return {'inventories':count,'identity_pairs':matches}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,action='append',required=True);p.add_argument('--metadata-root',type=Path)
    args=p.parse_args()
    for batch in args.batch:print(batch.name,collect(batch,args.metadata_root))
