"""Versioned length distributions from recorded metadata, without sequence analysis."""
import copy
import statistics
from pathlib import Path
from .common import digest, load
from .identities import result_slug

METRICS = ('count', 'known_count', 'unknown_count', 'total_bp', 'minimum_bp', 'median_bp', 'maximum_bp', 'n50_bp', 'n90_bp')


def distribution(rows, complete=True):
    ids = [row['id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate length inventory identifiers')
    lengths = [row.get('length_bp') for row in rows]
    if any(value is not None and (type(value) is not int or value < 0) for value in lengths):
        raise ValueError('Lengths must be nonnegative integers or unknown')
    known = sorted((value for value in lengths if value is not None), reverse=True)
    assessed = complete and len(known) == len(rows)
    total = sum(known)
    def nx(percent):
        cumulative = 0
        for value in known:
            cumulative += value
            if cumulative * 100 >= total * percent:
                return value if total else None
        return None
    return {'status': 'complete' if assessed else 'partial', 'count': len(rows),
            'known_count': len(known), 'unknown_count': len(rows)-len(known),
            'known_total_bp': total, 'total_bp': total if assessed else None,
            'minimum_bp': min(known) if assessed and known else None,
            'median_bp': statistics.median(known) if assessed and known else None,
            'maximum_bp': max(known) if assessed and known else None,
            'n50_bp': nx(50) if assessed else None, 'n90_bp': nx(90) if assessed else None,
            'items': copy.deepcopy(rows)}


def _missing(reason):
    return {'status': 'not_collected', 'reason': reason, **{key: None for key in METRICS}, 'items': []}


def saved_inventory(record, batch, artifact_root):
    if artifact_root is None:
        return None
    result_slug(record)  # Validate all path components before locating the sidecar.
    directory = Path(artifact_root)/batch/'results'/record['scenario_id']/record['tool']
    if record.get('run_id'):
        directory = directory/'repeats'/record['run_id']
    path = directory/'length_inventory.json'
    if not path.is_file():
        return None
    if Path(artifact_root).resolve() not in path.resolve().parents or path.stat().st_size > 8*1024*1024:
        raise ValueError('Length inventory exceeds its source boundary')
    value = load(path)
    if value.get('schema_version') != 1 or value.get('kind') != 'scored_fasta_lengths' or value.get('status') != 'complete':
        raise ValueError('Unsupported length inventory')
    execution = directory/'execution.json'
    if (not record.get('assembly_sha256') or value.get('assembly_sha256') != record['assembly_sha256']
            or not execution.is_file() or value.get('execution_sha256') != digest(execution)):
        raise ValueError('Length inventory provenance mismatch')
    current = load(execution)
    for key in ('assembly_sha256', 'scenario_id', 'tool', 'run_id', 'status'):
        if current.get(key) != record.get(key):
            raise ValueError('Length inventory execution differs from frozen result')
    rows = value['contigs']
    if any(set(row) != {'id', 'length_bp'} for row in rows):
        raise ValueError('Unexpected field in sequence-free length inventory')
    if len(rows) != (record.get('evaluation') or {}).get('contig_count'):
        raise ValueError('Length inventory differs from saved scored contig count')
    result = distribution(rows)
    if result['status'] != 'complete':
        raise ValueError('Final FASTA length inventory must be complete')
    result['source'] = {'kind': 'scored_fasta_lengths', 'role': 'scored_output',
                        'file_sha256': digest(path), 'assembly_sha256': value['assembly_sha256'],
                        'execution_sha256': value['execution_sha256'], 'producer_sha256': value['producer_sha256']}
    return result


def build_length_metrics(record, artifact, batch, artifact_root=None):
    graph = artifact.get('graph') or {}
    if graph.get('status') == 'available':
        segments = distribution([{'id': row['id'], 'length_bp': row.get('length_bp')} for row in graph.get('nodes', [])], graph.get('complete') is True)
        segments['source'] = copy.deepcopy(graph.get('source', {}))
    else:
        segments = _missing('No complete GFA segment inventory was collected for this execution.')
    contigs = saved_inventory(record, batch, artifact_root)
    if contigs is None:
        info = artifact.get('assembly_info') or {}
        bound = bool(record.get('assembly_sha256')) and (artifact.get('input_hashes') or {}).get('assembly_sha256') == record['assembly_sha256']
        rows = info.get('contigs', [])
        if (bound and info.get('status') == 'available' and info.get('source', {}).get('role') == 'final'
                and not artifact.get('failed_execution_provenance') and len(rows) == (record.get('evaluation') or {}).get('contig_count')):
            contigs = distribution([{'id': row['id'], 'length_bp': row.get('length_bp')} for row in rows])
            contigs['source'] = {**copy.deepcopy(info.get('source', {})), 'assembly_sha256': record['assembly_sha256']}
        else:
            contigs = _missing('No complete, source-bound scored-contig length inventory was collected.')
    return {'schema_version': 1, 'method': 'recorded-length-distributions-v1',
            'graph_segments': segments, 'scored_contigs': contigs,
            'scope': 'Raw segment and scored-output lengths. Graph totals do not subtract overlaps or account for path multiplicity. N50/N90 are length statistics, not recovery or correctness scores.'}
