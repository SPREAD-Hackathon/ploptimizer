"""Pinned minimap2 overlaps → unpolished miniasm unitigs, with saved provenance."""
import argparse
import collections
from pathlib import Path
import re
import subprocess

from .common import digest, save


def extract_unitigs(raw, graph, assembly, require_length_tag=True):
    """Preserve sequences/links; retain miniasm a/x annotations in raw output."""
    seen = set()
    omitted = collections.Counter()
    with raw.open() as source, graph.open('w') as gfa, assembly.open('w') as fasta:
        for line in source:
            if not line.strip():
                continue
            fields = line.rstrip('\n').split('\t')
            kind = fields[0]
            if kind == 'S':
                if (len(fields) < 3 or fields[1] in seen or not re.fullmatch(r'[!-~]+', fields[1])
                        or not re.fullmatch(r'[ACGTRYSWKMBDHVNacgtryswkmbdhvn]+', fields[2])):
                    raise ValueError('Invalid, duplicate or sequence-less miniasm unitig')
                lengths = [f for f in fields[3:] if f.startswith('LN:i:')]
                if len(lengths) > 1 or (require_length_tag and not lengths) or (lengths and int(lengths[0][5:]) != len(fields[2])):
                    raise ValueError('Miniasm sequence and declared length disagree')
                seen.add(fields[1])
                fasta.write('>' + fields[1] + '\n' + fields[2] + '\n')
            elif kind in {'a', 'x'}:
                omitted[kind] += 1
                continue
            elif kind not in {'H', 'L', 'P'}:
                raise ValueError('Unexpected miniasm output record: ' + kind)
            gfa.write(line)
    return {'unitig_count': len(seen), 'raw_annotation_records': dict(omitted),
            'raw_gfa_sha256': digest(raw), 'graph_sha256': digest(graph),
            'assembly_sha256': digest(assembly),
            'conversion': 'FASTA copies S sequences verbatim; standard GFA retains H/S/L/P. Raw a/x annotations retained separately.'}


def run(reads, output, threads):
    if threads < 1:
        raise ValueError('Threads must be positive')
    output.mkdir(parents=True, exist_ok=False)
    overlaps, raw = output / 'overlaps.paf', output / 'assembly.raw.gfa'
    steps = [
        {'name': 'Read-to-read overlaps', 'command': ['minimap2', '-x', 'ava-ont', '-t', str(threads), str(reads), str(reads)], 'stdout_file': str(overlaps)},
        {'name': 'Unpolished unitig assembly', 'command': ['miniasm', '-f', str(reads), str(overlaps)], 'stdout_file': str(raw)},
    ]
    record = {'schema_version': 1, 'status': 'running', 'steps': steps,
              'polishing': 'none', 'reads_sha256': digest(reads), 'versions': {}}
    manifest = output / 'workflow.json'
    save(manifest, record)
    try:
        for binary, flag in [('minimap2', '--version'), ('miniasm', '-V')]:
            version = subprocess.run([binary, flag], capture_output=True, text=True, check=True, timeout=30)
            record['versions'][binary] = (version.stdout + version.stderr).strip()
        for index, step in enumerate(steps):
            save(manifest, record)
            with Path(step['stdout_file']).open('w') as stdout, (output / f'step-{index + 1}.stderr.log').open('w') as stderr:
                completed = subprocess.run(step['command'], stdout=stdout, stderr=stderr)
            step['exit_code'] = completed.returncode
            step['stderr_tail'] = (output / f'step-{index + 1}.stderr.log').read_text(errors='replace')[-4000:]
            if completed.returncode:
                raise RuntimeError(step['name'] + ' failed with exit code ' + str(completed.returncode))
        record['conversion'] = extract_unitigs(raw, output / 'assembly_graph.gfa', output / 'assembly.fasta')
        record['overlaps_sha256'] = digest(overlaps)
        record['status'] = 'complete'
    except Exception as error:
        record.update(status='error', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        save(manifest, record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reads', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, required=True)
    args = parser.parse_args()
    run(args.reads, args.output, args.threads)
