"""Package already-produced PAF coordinate columns with frozen input provenance.

No alignment software is invoked. Optional tags, including sequence-bearing tags,
are neither decoded nor exported. Every saved row is retained for display; the
original filtered measurements and exact outcomes remain separate.
"""
import hashlib
import re
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 50_000
MAX_LINE_BYTES = 1024 * 1024
SHA256 = re.compile(r'[a-f0-9]{64}\Z')


def _unavailable(status, reason):
    return {'status':status, 'reason':reason, 'nucmer_status':'not_collected',
            'source_kind':'recorded_paf', 'difference_events_status':'not_collected'}


def _safe_path(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Recorded artifact path must stay inside its batch')
    path = root / relative
    if root.resolve() not in path.resolve().parents:
        raise ValueError('Recorded artifact path leaves its batch')
    return path


def parse_coordinate_columns(data, references):
    """Read only PAF's twelve mandatory fields; never decode optional tags."""
    rows, queries = [], {}
    expected = {reference['id']:reference['length_bp'] for reference in references}
    for line_number, line in enumerate(data.splitlines(), 1):
        if not line:
            continue
        if len(line) > MAX_LINE_BYTES:
            raise ValueError('A recorded PAF line exceeds the metadata limit')
        fields = line.split(b'\t', 12)[:12]
        if len(fields) != 12:
            raise ValueError(f'Invalid PAF coordinate columns on line {line_number}')
        try:
            query, reference = fields[0].decode('ascii'), fields[5].decode('ascii')
            strand = fields[4].decode('ascii')
            qlength,qstart,qend = map(int,fields[1:4])
            rlength,rstart,rend,matches,block,mapq = map(int,fields[6:12])
        except (ValueError,UnicodeDecodeError) as error:
            raise ValueError(f'Invalid PAF coordinate values on line {line_number}') from error
        if not query or len(query)>256 or any(c.isspace() or ord(c)<33 for c in query) or reference not in expected:
            raise ValueError(f'Unknown or invalid PAF identifier on line {line_number}')
        if strand not in ('+','-') or not (0<=qstart<qend<=qlength<=2**53) or not (0<=rstart<rend<=rlength==expected[reference]) or not (0<=matches<=block and block>0 and 0<=mapq<=255):
            raise ValueError(f'Out-of-range PAF coordinates on line {line_number}')
        if query in queries and queries[query] != qlength:
            raise ValueError('Conflicting query lengths in recorded PAF')
        queries[query] = qlength
        rows.append({'query_id':query,'query_length':qlength,'query_interval':[qstart,qend],
                     'reference_id':reference,'reference_length':rlength,'reference_interval':[rstart,rend],
                     'strand':strand,'matches':matches,'block_length':block,'mapq':mapq})
        if len(rows)>MAX_ROWS:
            raise ValueError('Recorded coordinates exceed the display limit; no rows were sampled')
    return rows,[{'id':name,'length_bp':length} for name,length in queries.items()]


def recorded_paf_plot(case, record, batch, artifact_root):
    """Return a provenance-bound display product from an existing small PAF."""
    if artifact_root is None:
        return _unavailable('not_collected','No explicit recorded-artifact directory was supplied to export.')
    diagnostic = record.get('diagnostics') or {}
    if diagnostic.get('status') != 'complete':
        return _unavailable('not_collected','No completed saved mapping record identifies coordinate evidence.')
    for key,value in (('scenario_id',record['scenario_id']),('tool',record['tool']),('strict_status',record['status']),('batch_id',batch)):
        if diagnostic.get(key) != value:
            return _unavailable('provenance_mismatch','Saved mapping identity does not match this execution.')
    if diagnostic.get('run_id') != record.get('run_id'):
        return _unavailable('provenance_mismatch','Saved mapping repeat identity does not match this execution.')
    hashes = diagnostic.get('input_hashes') or {}
    if any(not record.get(key) or hashes.get(key)!=record[key] for key in ('assembly_sha256','truth_sha256')):
        return _unavailable('provenance_mismatch','Saved mapping input hashes do not match this assembly/reference pair.')
    directory = Path('results')/record['scenario_id']/record['tool']
    if record.get('run_id'):
        directory = directory/'repeats'/record['run_id']
    relative = directory/'alignment.paf'
    if diagnostic.get('paf_file') != str(relative):
        return _unavailable('provenance_mismatch','Recorded coordinate path does not match the execution directory.')
    paf_hash = diagnostic.get('paf_sha256')
    execution_hash = hashes.get('execution_sha256')
    if not isinstance(paf_hash,str) or not SHA256.fullmatch(paf_hash) or not isinstance(execution_hash,str) or not SHA256.fullmatch(execution_hash):
        return _unavailable('provenance_mismatch','Frozen coordinate or execution hash is unavailable.')
    try:
        root = Path(artifact_root)/batch
        path = _safe_path(root,relative)
        execution = _safe_path(root,directory/'execution.json')
        if not path.is_file() or not execution.is_file():
            return _unavailable('missing','The existing coordinate or execution metadata file is not present locally.')
        if execution.stat().st_size > 1024*1024:
            return _unavailable('unsupported','Recorded execution metadata exceeds its size limit.')
        if path.stat().st_size > MAX_BYTES:
            return _unavailable('unsupported','Recorded coordinate file exceeds the 20 MiB metadata limit.')
        data = path.read_bytes()
        if len(data)>MAX_BYTES:
            return _unavailable('unsupported','Recorded coordinate file exceeds the 20 MiB metadata limit.')
        if hashlib.sha256(data).hexdigest()!=paf_hash or hashlib.sha256(execution.read_bytes()).hexdigest()!=execution_hash:
            return _unavailable('hash_mismatch','Local coordinate or execution bytes differ from their frozen hashes.')
        references = [{'id':m['refseq_accession'],'name':m.get('replicon_name',m['refseq_accession']),
                       'length_bp':m['length_bp'],'molecule_type':m.get('molecule_type')} for m in case.get('replicons',[])]
        rows,queries = parse_coordinate_columns(data,references)
    except (OSError,ValueError) as error:
        return _unavailable('invalid',str(error))
    return {'status':'available','source_kind':'recorded_paf','source':f'run_artifacts/{batch}/{relative}',
            'method':f'Saved minimap2 PAF coordinate columns (recorded mapper {diagnostic.get("mapper_version","version unavailable")}); no new alignment run',
            'coordinate_system':'0-based half-open intervals','nucmer_status':'not_collected',
            'difference_events_status':'not_collected','references':references,'queries':queries,
            'alignments':rows,'alignment_count':len(rows),'empty':not rows,
            'display_scope':'All mandatory coordinate rows in the saved PAF, including rows that may be excluded from the saved scoring filters. No optional tags are exported.',
            'query_inventory_scope':'Query identifiers present in the saved PAF only; unaligned output contigs are not inferred.',
            'input_hashes':{'assembly_sha256':record['assembly_sha256'],'truth_sha256':record['truth_sha256'],
                            'paf_sha256':paf_hash,'execution_sha256':execution_hash},
            'source_metadata':{'batch':batch,'relative_path':str(relative),'bytes':len(data),'mapper_version':diagnostic.get('mapper_version')},
            'saved_filter_policy':diagnostic.get('policy') or {}}
