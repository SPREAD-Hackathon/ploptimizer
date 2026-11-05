#!/usr/bin/env python3
"""Extract IDs/lengths from existing scored FASTAs; never emit sequence content."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def inventory(path):
    rows, seen = [], set()
    with path.open('rb') as stream:
        for line in stream:
            if line.startswith(b'>'):
                name = line[1:].split()[0].decode('ascii')
                if name in seen:
                    raise ValueError('Duplicate FASTA identifier')
                seen.add(name)
                rows.append({'id': name, 'length_bp': 0})
            elif line.strip():
                if not rows:
                    raise ValueError('Sequence before FASTA identifier')
                rows[-1]['length_bp'] += len(line.strip())
    if any(row['length_bp'] <= 0 for row in rows):
        raise ValueError('Empty FASTA record')
    return rows


def collect(batch):
    batch = batch.resolve()
    count = 0
    for execution in sorted((batch / 'results').rglob('execution.json')):
        record = json.loads(execution.read_text())
        if record.get('status') not in {'pass', 'fail'}:
            continue
        assembly = (batch / record['assembly_file']).resolve()
        if batch not in assembly.parents or not assembly.is_file():
            raise ValueError('Scored assembly must exist within the original batch')
        before = digest(assembly)
        if before != record['assembly_sha256']:
            raise ValueError('Scored assembly hash mismatch')
        rows = inventory(assembly)
        if digest(assembly) != before:
            raise ValueError('Assembly changed during inventory collection')
        if len(rows) != record['evaluation']['contig_count']:
            raise ValueError('Inventory count differs from saved scored count')
        result = {'schema_version': 1, 'status': 'complete', 'kind': 'scored_fasta_lengths',
                  'assembly_sha256': before, 'execution_sha256': digest(execution),
                  'producer_sha256': digest(Path(__file__)), 'contigs': rows}
        target = execution.parent / 'length_inventory.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
        temporary.replace(target)
        count += 1
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, action='append', required=True)
    args = parser.parse_args()
    for batch in args.batch:
        print(batch.name, collect(batch))
