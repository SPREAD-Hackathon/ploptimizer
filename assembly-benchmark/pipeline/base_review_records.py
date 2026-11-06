"""Package source-bound, previously computed base reviews without analysing sequences."""
import copy
from pathlib import Path

from .common import ROOT, digest, load
from .recorded_coordinates import _safe_path


def attach_base_review(summary, record, batch, artifact_root, plot):
    if not summary or summary.get('evidence_kind') != 'saved_alignment_counts' or artifact_root is None:
        return
    for path in sorted((ROOT / 'reviews' / 'bases').glob('*.json')):
        review = load(path)
        if (review.get('batch_id'), review.get('scenario_id'), review.get('tool'), review.get('strict_status')) != (batch, record['scenario_id'], record['tool'], record['status']):
            continue
        hashes = review.get('hashes') or {}
        if (review.get('status') != 'verified' or any(not record.get(k) or hashes.get(k) != record[k] for k in ('assembly_sha256', 'truth_sha256'))
                or hashes.get('paf_sha256') != summary['source_sha256']
                or not plot or review.get('alignment_records') != plot.get('alignments')):
            continue
        try:
            execution = _safe_path(Path(artifact_root) / batch, Path('results') / record['scenario_id'] / record['tool'] / 'execution.json')
            if digest(execution) != hashes.get('execution_sha256'):
                continue
        except (OSError, ValueError):
            continue
        events = review.get('events') or []
        counts = [f['value'] for f in summary['facts'] if f['label'] == 'Base mismatches']
        if counts != [len(events)] or not events:
            continue
        valid = all(event.get('type') == 'substitution' and event.get('reference_id') == review['reference_id']
                    and event.get('query_id') == review['query_id']
                    and all(type(event.get(k)) is int and 1 <= event[k] <= review[length]
                            for k,length in [('reference_position_1based','reference_length'), ('query_position_1based','query_length')])
                    and event.get('reference_base') in ('A','C','G','T')
                    and event.get('output_base_reference_forward') in ('A','C','G','T')
                    and event['reference_base'] != event['output_base_reference_forward'] for event in events)
        if not valid or len({e['reference_position_1based'] for e in events}) != len(events):
            continue
        summary.update(evidence_kind='direct_saved_sequence_comparison', location_status='recorded',
                       base_changes_status='recorded', events=copy.deepcopy(events),
                       base_review_source=str(path.relative_to(ROOT)), base_review_sha256=digest(path),
                       stage_comparisons=copy.deepcopy(review.get('stage_comparisons', {})),
                       graph_checkpoints=copy.deepcopy(review.get('graph_checkpoints', [])),
                       scope=review['method'], summary=f'Full-length contig with {len(events)} directly confirmed base substitutions.')
        stages = review.get('stage_comparisons') or {}
        if stages.get('initial', {}).get('exact_reference_contigs') and stages.get('reconstructed', {}).get('exact_final_contigs'):
            summary['facts'].append({'label':'Direct stage comparison', 'kind':'text',
                'value':'The saved initial Flye plasmid matches the reference exactly. The saved Unicycler reconstruction matches the final Plassembler sequence, including both substitutions.',
                'source':summary['base_review_source'] + ' · stage_comparisons'})
        checkpoints = {item['filename']:item for item in review.get('graph_checkpoints', [])}
        early = checkpoints.get('004_long_read_assembly.gfa', {}).get('segments', [])
        late = checkpoints.get('006_final_clean.gfa', {}).get('segments', [])
        if len(early) == len(late) == 1 and early[0]['exact_reference'] and late[0]['exact_final']:
            summary['facts'].append({'label':'Internal reconstruction checkpoints', 'kind':'text',
                'value':'Unicycler’s saved long-read assembly graph (004) still matches the reference exactly. Its final clean graph (006), after graph bridging and cleanup, contains the same substitutions as the final output. This narrows the discrepancy to graph reconstruction between these saved checkpoints; it does not establish the responsible operation.',
                'source':summary['base_review_source'] + ' · graph_checkpoints'})
        return
