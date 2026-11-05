"""Aggregate frozen measurements for plotting; no reads, alignments or rescoring."""
import math
from .identities import result_href

METRIC_NOTES = {
    'exact': 'Saved dedicated-copy sequence assessment; not alignment completion.',
    'breadth': 'Union of retained reference alignment blocks, with the saved mapping filters.',
    'identity': 'Recorded alignment-weighted identity across retained alignments; not longest-alignment identity.',
    'resources': 'Recorded elapsed wall seconds and GNU time maximum resident set size in KiB; workflow scopes differ.',
    'inputs': 'Achieved depth and mean read length from saved input manifests, deduplicated by read hash and accession.',
    'unavailable': ['Wick longest-single-alignment contiguity on tripled circular references',
                    'Circularisation gap/overlap distribution under that assessment',
                    'Maximum indel within the longest alignment'],
}


def number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None


def aggregate_data(documents, overview):
    lookup = {(r['batch'], r['scenario_id'], r['tool'], r.get('run_id')): r
              for family in overview['families'] for r in family['records']}
    executions, molecules, inputs = [], [], {}
    groups = {}
    for document in documents:
        batch = document['batch']
        cases = {c['id']: c for c in document['scenarios']}
        for record in document['results']:
            identity = (batch, record['scenario_id'], record['tool'], record.get('run_id'))
            row = lookup.get(identity)
            if row is None:
                continue
            case = cases[record['scenario_id']]
            group_id = row['family'].lower() + '-' + row.get('cohort_role', 'primary')
            group = groups.setdefault(group_id, {'id': group_id, 'family': row['family'],
                'cohort_role': row.get('cohort_role', 'primary'), 'execution_count': 0})
            group['execution_count'] += 1
            common = {k: row.get(k) for k in ('batch', 'family', 'cohort_role', 'scenario_id', 'tool', 'run_id', 'threads', 'version', 'href')}
            common.update(group_id=group_id, execution_status=record.get('status'),
                          assembly_sha256=record.get('assembly_sha256'), reads_sha256=record.get('reads_sha256'))
            executions.append({**common, 'elapsed_seconds': number(record.get('elapsed_seconds')),
                'peak_memory_kib': number(record.get('peak_memory_kb'))})
            manifest = document.get('inputs', {}).get(case['id']) or {}
            input_rows = {r.get('accession'): r for r in manifest.get('replicons', [])}
            mappings = {r['accession']: r for r in (record.get('diagnostics') or {}).get('evidence', {}).get('replicons', [])}
            expected = {r['refseq_accession']: r for r in case.get('replicons', [])}
            required = (record.get('report_evidence') or {}).get('required_accessions')
            if required is None:
                required = [r['accession'] for r in (record.get('evaluation') or {}).get('replicons', [])]
            for score in (record.get('evaluation') or {}).get('replicons', []):
                accession = score['accession']
                reference, measured, mapping = expected.get(accession, {}), input_rows.get(accession, {}), mappings.get(accession, {})
                molecules.append({**common, 'accession': accession, 'molecule_type': score.get('molecule_type'),
                    'topology': reference.get('topology'), 'length_bp': score.get('length_bp'),
                    'required_by_endpoint': accession in required, 'exact_status': score.get('status'),
                    'achieved_depth': number(measured.get('achieved_depth')),
                    'aligned_reference_fraction': number(mapping.get('recovered_fraction')),
                    'alignment_identity': number(mapping.get('alignment_identity')),
                    'diagnostic_status': (record.get('diagnostics') or {}).get('status')})
            # Input distribution counts an input/replicon once, not once per assembler or repeat.
            if row['family'] != 'S3':
                read_hash = manifest.get('reads_sha256') or record.get('reads_sha256')
                for accession, measured in input_rows.items():
                    reference = expected.get(accession, {})
                    key = (group_id, read_hash or (batch + ':' + case['id']), accession)
                    inputs.setdefault(key, {'group_id': group_id, 'batch': batch, 'scenario_id': case['id'],
                        'reads_sha256': read_hash, 'accession': accession, 'molecule_type': reference.get('molecule_type'),
                        'length_bp': reference.get('length_bp'), 'achieved_depth': number(measured.get('achieved_depth')),
                        'mean_read_length_bp': number(measured.get('mean_read_length'))})
    comparisons = []
    for family in overview['families']:
        for group in family.get('repeatability_groups', []):
            comparisons.append({**group, 'group_id': 's3-' + group.get('cohort_role', 'primary')})
    return {'schema_version': 1, 'scope': 'Current selected source batches; primary and supplementary remain separate. Historical pilot excluded.',
            'metric_notes': METRIC_NOTES, 'tools': overview['tools'], 'groups': sorted(groups.values(), key=lambda g: g['id']),
            'executions': executions, 'molecules': molecules, 'inputs': list(inputs.values()), 'repeatability': comparisons}
