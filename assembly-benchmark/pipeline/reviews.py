"""Attach reviewed sequence observations only to the exact supporting artefacts."""
from .common import ROOT, digest, load


def attach_sequence_review(record, execution_path, batch):
    if not record or not execution_path or not batch or not record.get('diagnostics'):
        return record
    for path in sorted((ROOT / 'reviews').glob('*.json')):
        review = load(path)
        if (review.get('batch_id'), review.get('scenario_id'), review.get('tool')) != (batch.name, record.get('scenario_id'), record.get('tool')):
            continue
        if review.get('status') != 'verified' or review.get('strict_status') != record.get('status'):
            continue
        hashes = review['hashes']
        if (hashes.get('execution_sha256') == digest(execution_path)
                and hashes.get('assembly_sha256') == record.get('assembly_sha256')
                and hashes.get('truth_sha256') == record.get('truth_sha256')
                and hashes.get('paf_sha256') == record['diagnostics'].get('paf_sha256')):
            record['sequence_review'] = review
            break
    return record
