"""Validate recorded whole-segment identity metadata against frozen output sources."""
from pathlib import Path
import re
from .common import digest, load
from .identities import result_slug


def load_graph_contig_identity(record, artifact, batch, root, lengths):
    if root is None:return None
    result_slug(record)
    directory=Path(root)/batch/'results'/record['scenario_id']/record['tool']
    if record.get('run_id'):directory=directory/'repeats'/record['run_id']
    path=directory/'graph_contig_identity.json'
    if not path.is_file():return None
    if Path(root).resolve() not in path.resolve().parents or path.stat().st_size>8*1024*1024:raise ValueError('Invalid graph identity source path/size')
    value=load(path);graph=artifact.get('graph') or {};execution=directory/'execution.json'
    if value.get('schema_version')!=1 or value.get('method')!='whole_segment_contig_sha256_v1':raise ValueError('Unsupported graph identity metadata')
    if (not record.get('assembly_sha256') or value.get('assembly_sha256')!=record['assembly_sha256']
            or value.get('gfa_sha256')!=graph.get('source',{}).get('file_sha256')
            or not execution.is_file() or value.get('execution_sha256')!=digest(execution)):
        raise ValueError('Graph identity source hash mismatch')
    current=load(execution)
    if any(current.get(k)!=record.get(k) for k in ('assembly_sha256','scenario_id','tool','run_id','status')):raise ValueError('Graph identity execution differs from frozen record')
    nodes={row['id']:row.get('length_bp') for row in graph.get('nodes',[])}
    contigs={row['id']:row['length_bp'] for row in lengths.get('scored_contigs',{}).get('items',[])}
    for row in value['associations']:
        if set(row)!={'segment_id','contig_id','orientation','length_bp','sequence_sha256'}:raise ValueError('Unexpected graph identity fields')
        if (row['segment_id'] not in nodes or row['contig_id'] not in contigs
                or type(row['length_bp']) is not int or row['length_bp']<=0
                or nodes[row['segment_id']]!=row['length_bp'] or contigs[row['contig_id']]!=row['length_bp']
                or row['orientation']!='+' or not re.fullmatch('[a-f0-9]{64}',row['sequence_sha256'])):
            raise ValueError('Graph identity association differs from saved inventories')
    return {**value,'file_sha256':digest(path)}
