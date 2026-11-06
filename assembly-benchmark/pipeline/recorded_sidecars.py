"""Read completed show-coords sidecars as metadata; no tools or nucleotide I/O."""
import copy
import hashlib
import json
import math
from pathlib import Path

from .recorded_coordinates import MAX_BYTES, MAX_ROWS, SHA256, _safe_path


class SidecarError(ValueError):
    def __init__(self,status,reason):
        super().__init__(reason);self.status=status


def _read(path, limit=MAX_BYTES):
    if not path.is_file():
        raise SidecarError('missing','Completed sidecar metadata or coordinate file is not present locally.')
    if path.stat().st_size>limit:
        raise SidecarError('unsupported','Completed sidecar metadata exceeds its size limit.')
    data=path.read_bytes()
    if len(data)>limit:
        raise SidecarError('unsupported','Completed sidecar metadata exceeds its size limit.')
    return data


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _verify(path,expected,limit=MAX_BYTES):
    if not isinstance(expected,str) or not SHA256.fullmatch(expected):
        raise SidecarError('provenance_mismatch','Completed sidecar lacks a valid declared metadata checksum.')
    data=_read(path,limit)
    if _hash(data)!=expected:
        raise SidecarError('hash_mismatch','Completed sidecar metadata bytes differ from their declared checksums.')
    return data


def _identifier(value):
    if not isinstance(value,str) or not value or len(value)>256 or any(ord(c)<33 or ord(c)>126 for c in value):
        raise ValueError('Invalid saved coordinate identifier')
    return value


def parse_show_coords(data):
    """Normalize recorded inclusive endpoints, preserving the original endpoints."""
    result=[]
    for index,line in enumerate(data.splitlines(),1):
        if not line.strip():continue
        fields=line.split(b'\t')
        if len(fields)!=11:raise ValueError('Expected eleven saved show-coords -THrl columns')
        try:
            r1,r2,q1,q2,span_r,span_q=map(int,fields[:6])
            identity=float(fields[6]);length_r,length_q=map(int,fields[7:9])
            reference,query=fields[9].decode('ascii'),fields[10].decode('ascii')
        except (ValueError,UnicodeDecodeError) as error:
            raise ValueError('Invalid saved show-coords values') from error
        _identifier(reference);_identifier(query)
        if not (0<min(r1,r2)<=max(r1,r2)<=length_r<=2**53 and 0<min(q1,q2)<=max(q1,q2)<=length_q<=2**53 and span_r>0 and span_q>0 and math.isfinite(identity) and 0<=identity<=100):
            raise ValueError('Saved show-coords values exceed their declared ranges')
        if span_r!=abs(r2-r1)+1 or span_q!=abs(q2-q1)+1:
            raise ValueError('Saved coordinate spans disagree with the inclusive endpoints')
        result.append({'reference_id':reference,'reference_interval':[min(r1,r2)-1,max(r1,r2)],
            'reference_length':length_r,'query_id':query,'query_interval':[min(q1,q2)-1,max(q1,q2)],
            'query_length':length_q,'strand':'+' if (r2-r1)*(q2-q1)>=0 else '-',
            'identity_percent':identity,'original_endpoints_1based_inclusive':[r1,r2,q1,q2],'source_row':index})
        if len(result)>MAX_ROWS:raise ValueError('Saved coordinate rows exceed the display limit; no rows were sampled')
    return result


def _inventory(items):
    result={}
    if not isinstance(items,list) or len(items)>5000:raise ValueError('Unsupported saved coordinate inventory')
    for item in items:
        name=_identifier(item['id']);length=item['length']
        if name in result or not isinstance(length,int) or isinstance(length,bool) or not 0<length<=2**53:
            raise ValueError('Duplicate or invalid saved coordinate inventory entry')
        result[name]=length
    return result


def _known_hash(record,key):
    values=[]
    for field in ('diagnostics','tolerant_assessment'):
        value=(record.get(field) or {}).get('input_hashes',{}).get(key)
        if value:values.append(value)
    value=(record.get('graph_artifacts') or {}).get('input_hashes',{}).get(key)
    if value:values.append(value)
    if len(set(values))!=1:
        raise SidecarError('provenance_mismatch','Frozen metadata has no unique execution/input checksum for this sidecar.')
    return values[0]


def _public_argument(value):
    value=str(value)
    if value.startswith('--') and '=' in value:
        name,argument=value.split('=',1)
        return name+'='+_public_argument(argument)
    if '/runs/' in value:return '<workdir>/runs/'+value.split('/runs/',1)[1]
    if value.startswith('/'):return '<workdir>/'+Path(value).name
    return value


def completed_sidecar_plot(case,record,batch,roots,artifact_root,snapshot_hash):
    """Select an explicit completed source, never discover or generate comparisons."""
    unavailable={'status':'not_applicable','reason':'No completed sidecar task was supplied for this execution.',
                 'source_kind':'recorded_show_coords','nucmer_status':'not_collected'}
    matches=[]
    try:
        for supplied in roots:
            root=Path(supplied);manifest_bytes=_read(root/'tasks.json',1024*1024)
            manifest=json.loads(manifest_bytes)
            for task in manifest.get('tasks',[]):
                if (task.get('batch'),task.get('scenario_id'),task.get('tool'),task.get('run_id'))==(batch,record['scenario_id'],record['tool'],record.get('run_id')):
                    matches.append((root,manifest_bytes,manifest,task))
        if not matches:return unavailable
        if len(matches)!=1:raise SidecarError('provenance_mismatch','Multiple completed sidecar tasks identify this execution; no source was selected.')
        return _completed_plot(case,record,batch,*matches[0],artifact_root,snapshot_hash)
    except SidecarError as error:
        return {**unavailable,'status':error.status,'reason':str(error)}
    except (OSError,ValueError,TypeError,KeyError) as error:
        return {**unavailable,'status':'invalid','reason':str(error)}


def _completed_plot(case,record,batch,root,manifest_bytes,manifest,task,artifact_root,snapshot_hash):
    if record['status'] not in ('pass','fail') or manifest.get('schema_version')!=1 or manifest.get('source_snapshot_sha256')!=snapshot_hash:
        raise SidecarError('provenance_mismatch','Completed comparison does not identify the frozen scored snapshot.')
    relative=Path(record['scenario_id'])/record['tool']
    execution=Path('results')/record['scenario_id']/record['tool']
    if record.get('run_id'):
        # Comparison output uses the run ID directly; original assembly
        # metadata lives under repeats/, as declared by the producer manifest.
        relative=relative/record['run_id'];execution=execution/'repeats'/record['run_id']
    expected_output=Path('runs')/batch/'comparisons'/root.name/relative
    if task.get('output_relative_path')!=str(expected_output) or task.get('execution_relative_path')!=str(execution/'execution.json'):
        raise SidecarError('provenance_mismatch','Completed comparison paths do not identify this execution.')
    directory=_safe_path(root,relative)
    sidecar_bytes=_read(directory/'comparison.json')
    sidecar=json.loads(sidecar_bytes)
    if sidecar.get('schema_version')!=1 or sidecar.get('status') not in ('complete','not_applicable') or sidecar.get('kind')!='reference_vs_existing_assembly' or sidecar.get('alignment_source')!='NUCmer':
        raise SidecarError('invalid','Unsupported or incomplete comparison sidecar.')
    if any(sidecar.get(key)!=value for key,value in (('batch_id',batch),('scenario_id',record['scenario_id']),('tool',record['tool']),('original_exact_status',record['status']))):
        raise SidecarError('provenance_mismatch','Completed sidecar identity/outcome differs from this frozen execution.')
    if sidecar.get('comparison_manifest_sha256')!=_hash(manifest_bytes):
        raise SidecarError('hash_mismatch','Completed sidecar task-manifest checksum does not match.')
    inputs=sidecar.get('input_hashes') or {}
    for key in ('assembly_sha256','truth_sha256'):
        if not record.get(key) or inputs.get(key)!=record[key] or task.get(key)!=record[key]:
            raise SidecarError('provenance_mismatch','Completed sidecar input declarations differ from the frozen assembly/reference hashes.')
    for key in ('execution_sha256','input_manifest_sha256'):
        if inputs.get(key)!=_known_hash(record,key):
            raise SidecarError('provenance_mismatch','Completed sidecar execution/input metadata differs from frozen provenance.')
    if task.get('execution_sha256')!=inputs['execution_sha256'] or artifact_root is None:
        raise SidecarError('provenance_mismatch','Explicit original execution metadata are required to verify this completed sidecar.')
    metadata_root=Path(artifact_root)/batch
    _verify(_safe_path(metadata_root,execution/'execution.json'),inputs['execution_sha256'],1024*1024)
    _verify(_safe_path(metadata_root,Path('cases')/record['scenario_id']/'input.json'),inputs['input_manifest_sha256'],1024*1024)
    environment=sidecar.get('environment') or {}
    _verify(root/'provenance/compare_existing_outputs.py',sidecar.get('comparison_script_sha256'),1024*1024)
    _verify(root/'provenance/pixi.toml',environment.get('manifest_sha256'),1024*1024)
    _verify(root/'provenance/pixi.lock',environment.get('lock_sha256'),1024*1024)
    if sidecar['status'] == 'not_applicable':
        if inputs['assembly_sha256'] != hashlib.sha256(b'').hexdigest() or sidecar.get('queries') != [] or sidecar.get('alignments') != []:
            raise SidecarError('invalid','Not-applicable comparison must identify a hash-verified empty assembly.')
        return {'status':'not_applicable','source_kind':'recorded_show_coords','nucmer_status':'not_applicable',
                'reason':'Final assembly FASTA is empty; NUCmer was not run.',
                'input_hashes':copy.deepcopy(inputs)}
    outputs=sidecar.get('output_hashes') or {}
    coordinate_bytes=_verify(directory/'coordinates.tsv',outputs.get('coordinates.tsv'))
    for filename in ('nucmer.stdout.log','nucmer.stderr.log','show-coords.stderr.log'):
        _verify(directory/filename,outputs.get(filename),1024*1024)
    rows=parse_show_coords(coordinate_bytes)
    if sidecar.get('coordinate_system')!='0-based half-open' or sidecar.get('original_coordinate_system')!='show-coords 1-based inclusive' or sidecar.get('alignments')!=rows or sidecar.get('alignment_count')!=len(rows):
        raise SidecarError('invalid','Canonical sidecar rows differ from the recorded original coordinate table.')
    references=_inventory(sidecar['references']);queries=_inventory(sidecar['queries'])
    expected={m['refseq_accession']:m['length_bp'] for m in case['replicons']}
    if references!=expected or any(row['reference_id'] not in references or row['reference_length']!=references[row['reference_id']] or row['query_id'] not in queries or row['query_length']!=queries[row['query_id']] for row in rows):
        raise SidecarError('provenance_mismatch','Saved coordinate inventories differ from the declared reference/query records.')
    mapper_version=_identifier(sidecar['mapper_version'])
    named={m['refseq_accession']:m for m in case['replicons']}
    return {'status':'available','source_kind':'recorded_show_coords','source':f'completed_comparisons/{batch}/{root.name}/{relative}/comparison.json',
        'method':f'Recorded NUCmer {mapper_version} show-coords spans; supplementary comparison of existing outputs',
        'coordinate_system':'0-based half-open intervals','original_coordinate_system':'show-coords 1-based inclusive',
        'nucmer_status':'available','difference_events_status':'not_collected','alignment_count':len(rows),'empty':not rows,
        'references':[{'id':key,'name':named[key].get('replicon_name',key),'length_bp':length,'molecule_type':named[key].get('molecule_type')} for key,length in references.items()],
        'queries':[{'id':key,'length_bp':length} for key,length in queries.items()],'alignments':rows,
        'display_scope':'All recorded show-coords rows are displayed. This supplementary source has its own mapper/settings; original exact and tolerant scores remain unchanged.',
        'query_inventory_scope':'Query metadata reported by the completed comparison sidecar; each plot panel uses only queries with recorded spans for that reference.',
        'input_hashes':copy.deepcopy(inputs),'source_coordinate_sha256':outputs['coordinates.tsv'],
        'original_coordinates_tsv':coordinate_bytes.decode('ascii'),
        'source_metadata':{'batch':batch,'label':root.name,'relative_path':str(relative/'comparison.json'),
            'sidecar_sha256':_hash(sidecar_bytes),'coordinate_bytes':len(coordinate_bytes),'mapper_version':mapper_version,
            'comparison_manifest_sha256':_hash(manifest_bytes),'comparison_script_sha256':sidecar['comparison_script_sha256'],
            'environment':copy.deepcopy(environment),'finished_at':sidecar.get('finished_at'),
            'command':[_public_argument(value) for value in sidecar.get('command',[])],
            'coordinate_command':[_public_argument(value) for value in sidecar.get('coordinate_command',[])],
            'policy':sidecar.get('nucmer_policy'),
            'verified_metadata':['frozen snapshot','task manifest','execution metadata','input manifest','worker source','environment manifest/lock','coordinate TSV','small tool logs']}}
