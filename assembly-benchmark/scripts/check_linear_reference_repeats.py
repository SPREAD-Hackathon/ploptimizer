#!/usr/bin/env python3
"""Locate repeats between complete left/right halves of pinned linear references."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import load, save
from scripts.compare_existing_outputs import inventory, parse_coords


def original_intervals(row, split, length):
    left = row['reference_interval']
    right = [x + split for x in row['query_interval']]
    return {'left_interval': left, 'right_interval': right,
            'orientation': 'inverted' if row['strand'] == '-' else 'direct',
            'aligned_left_bp': left[1] - left[0],
            'aligned_right_bp': right[1] - right[0],
            'identity_percent': row['identity_percent'],
            'left_terminal_offset_bp': left[0],
            'right_terminal_offset_bp': length - right[1],
            'source_row': row['source_row']}


def run(panel_path, sequence_dir, output, nucmer, show_coords):
    panel = load(panel_path)
    output.mkdir(parents=True, exist_ok=False)
    version = subprocess.check_output([nucmer, '--version'], text=True,
                                      stderr=subprocess.STDOUT).strip()
    if '4.0.1' not in version:
        raise ValueError('Use pinned NUCmer 4.0.1')
    result = {'schema_version': 1, 'method': 'nucmer-inter-arm-v1',
              'coordinate_system': '0-based half-open on the original reference',
              'scope': 'All alignments between complete left and right halves; not a tandem-array census.',
              'mapper_version': version, 'references': []}
    for assembly in panel['assemblies']:
        for reference in assembly['replicons']:
            accession = reference['refseq_accession']
            source = sequence_dir / (accession + '.fasta')
            if len(inventory(source)) != 1:
                raise ValueError('Expected one reference sequence')
            sequence = ''.join(line.strip() for line in source.read_text().splitlines()
                               if not line.startswith('>')).upper()
            digest = hashlib.sha256(sequence.encode()).hexdigest()
            if (set(sequence) - set('ACGT') or digest != reference['sequence_sha256']
                    or len(sequence) != reference['length_bp']):
                raise ValueError('Pinned sequence differs: ' + accession)
            directory = output / accession
            directory.mkdir()
            split = len(sequence) // 2
            left, right = directory / 'left.fasta', directory / 'right.fasta'
            left.write_text('>left\n' + sequence[:split] + '\n')
            right.write_text('>right\n' + sequence[split:] + '\n')
            prefix = directory / 'inter-arm'
            command = [nucmer, '--maxmatch', '--nosimplify', '--threads', '1',
                       '--prefix', str(prefix), str(left), str(right)]
            with (directory / 'nucmer.log').open('w') as log:
                subprocess.run(command, stdout=log, stderr=log, check=True, timeout=1800)
            coordinate_command = [show_coords, '-THrl', str(prefix) + '.delta']
            coordinates = directory / 'coordinates.tsv'
            with coordinates.open('w') as stream:
                subprocess.run(coordinate_command, stdout=stream, check=True, timeout=120)
            rows = parse_coords(coordinates, inventory(left), inventory(right))
            intervals = [original_intervals(row, split, len(sequence)) for row in rows]
            intervals.sort(key=lambda r: (-min(r['aligned_left_bp'], r['aligned_right_bp']),
                                          r['left_terminal_offset_bp'] + r['right_terminal_offset_bp']))
            record = {'accession': accession, 'length_bp': len(sequence),
                      'sequence_sha256': digest, 'split_position': split,
                      'command': command, 'coordinate_command': coordinate_command,
                      'alignment_count': len(intervals), 'alignments': intervals,
                      'coordinates_sha256': hashlib.sha256(coordinates.read_bytes()).hexdigest()}
            save(directory / 'report.json', record)
            result['references'].append(record)
    save(output / 'report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', type=Path, required=True)
    parser.add_argument('--sequence-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--nucmer', default='nucmer')
    parser.add_argument('--show-coords', default='show-coords')
    args = parser.parse_args()
    run(args.panel, args.sequence_dir, args.output, args.nucmer, args.show_coords)
