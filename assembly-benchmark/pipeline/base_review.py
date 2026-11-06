"""Directly check saved gap-free alignment spans against their original FASTAs.

This does not assemble, correct sequences or invoke an aligner. Coordinates are
reported in the reference-forward orientation, with original output coordinates.
"""
from .recorded_coordinates import parse_coordinate_columns


def reverse_complement(sequence):
    if set(sequence) - set('ACGTN'):
        raise ValueError('Only unambiguous DNA and N are supported')
    return sequence.translate(str.maketrans('ACGTN', 'TGCAN'))[::-1]


def circular_equivalence(reference, query):
    if len(reference) != len(query) or not reference:
        return None
    for strand, oriented in [('+', query), ('-', reverse_complement(query))]:
        offset = (reference + reference).find(oriented)
        if 0 <= offset < len(reference):
            return {'strand':strand, 'reference_offset_0based':offset}
    return None


def review_gapfree_pair(references, queries, paf_bytes):
    rows, _ = parse_coordinate_columns(paf_bytes, [{'id':name, 'length_bp':len(seq)} for name, seq in references.items()])
    if not rows or len({(r['reference_id'], r['query_id'], r['strand']) for r in rows}) != 1:
        raise ValueError('Review requires one saved reference/query pair and orientation')
    reference_id, query_id = rows[0]['reference_id'], rows[0]['query_id']
    reference, query = references[reference_id], queries[query_id]
    if len(reference) != len(query):
        raise ValueError('Review requires equal lengths')
    for key in ('reference_interval', 'query_interval'):
        cursor = 0
        for start, end in sorted(row[key] for row in rows):
            if start != cursor:
                raise ValueError('Saved spans must partition both sequences without gaps or overlaps')
            cursor = end
        if cursor != len(reference):
            raise ValueError('Saved spans must cover both complete sequences')
    events = []
    offsets = set()
    for row in rows:
        qs, qe = row['query_interval']
        rs, re = row['reference_interval']
        if row.get('gap_free_aligned_bp') != qe - qs or row['query_length'] != len(query):
            raise ValueError('A saved row is not a verified gap-free span')
        forward = query[qs:qe] if row['strand'] == '+' else reverse_complement(query[qs:qe])
        offsets.add((rs - (qs if row['strand'] == '+' else len(query) - qe)) % len(reference))
        count = 0
        for index, (expected, observed) in enumerate(zip(reference[rs:re], forward)):
            if expected != observed:
                if expected not in 'ACGT' or observed not in 'ACGT':
                    raise ValueError('Ambiguous base differences require separate review')
                count += 1
                query_position = qs + index if row['strand'] == '+' else qe - index - 1
                events.append({'type':'substitution', 'reference_id':reference_id, 'query_id':query_id,
                               'reference_position_1based':rs + index + 1,
                               'query_position_1based':query_position + 1,
                               'reference_base':expected, 'output_base_reference_forward':observed,
                               'strand':row['strand']})
        if count != row.get('recorded_mismatches'):
            raise ValueError('Direct comparison disagrees with saved mismatch counts')
    if len(offsets) != 1:
        raise ValueError('Saved rows are not one consistent circular rotation')
    return {'reference_id':reference_id, 'query_id':query_id, 'reference_length':len(reference),
            'query_length':len(query), 'events':sorted(events, key=lambda event:event['reference_position_1based']),
            'alignment_records':rows, 'all_query_bases_aligned':True,
            'method':'Direct saved FASTA comparison along hash-bound saved gap-free PAF spans; no assembly or alignment rerun'}
