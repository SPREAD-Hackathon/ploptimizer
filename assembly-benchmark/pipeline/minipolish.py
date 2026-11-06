"""Minipolish continuation of a verified, retained Miniasm assembly."""
import argparse
import copy
import math
from pathlib import Path
import subprocess

from .common import digest, load, save
from .miniasm import extract_unitigs


def run(reads, raw_graph, source_execution, output, threads, rounds=2):
    if threads < 1 or rounds != 2:
        raise ValueError('This profile requires positive threads and the upstream default two rounds')
    source = load(source_execution)
    workflow = source.get('assembly_workflow', {})
    if (source.get('tool') != 'miniasm' or source.get('status') not in ('pass', 'fail')
            or workflow.get('status') != 'complete' or source.get('reads_sha256') != digest(reads)
            or workflow.get('conversion', {}).get('raw_gfa_sha256') != digest(raw_graph)):
        raise ValueError('Raw Miniasm assembly and reads do not match their frozen provenance')
    elapsed = source.get('elapsed_seconds')
    if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Missing valid source workflow timing')
    output.mkdir(parents=True, exist_ok=False)
    polished = output / 'assembly.polished.gfa'
    step = {'name': 'Minipolish (initial constituent-read polish and two full rounds)',
            'command': ['minipolish', '--threads', str(threads), '--rounds', str(rounds), str(reads), str(raw_graph)],
            'stdout_file': str(polished)}
    steps = copy.deepcopy(workflow['steps'])
    for entry in steps:
        entry['reused_source_stage'] = True
    record = {'schema_version': 1, 'status': 'running', 'steps': steps + [step],
              'polishing': 'Minipolish: initial constituent-read polish plus two full Racon rounds; default ONT mapping preset.',
              'reads_sha256': digest(reads), 'source_raw_gfa_sha256': digest(raw_graph),
              'source_execution_sha256': digest(source_execution), 'source_batch_id': source.get('batch_id'),
              'source_evaluation': source['evaluation'], 'source_elapsed_seconds': elapsed,
              'source_peak_memory_kb': source.get('peak_memory_kb'),
              'resource_scope': 'Sequential pipeline total: recorded Miniasm workflow plus this polishing continuation; memory is the larger stage peak.',
              'versions': copy.deepcopy(workflow['versions'])}
    manifest = output / 'workflow.json'
    save(manifest, record)
    try:
        for binary in ('minipolish', 'racon', 'minimap2'):
            version = subprocess.run([binary, '--version'], capture_output=True, text=True, check=True, timeout=30)
            record['versions'][binary] = version.stdout.strip() or version.stderr.strip()
            if version.stdout.strip() and version.stderr.strip():
                record.setdefault('version_check_stderr', {})[binary] = version.stderr.strip()
        if not workflow['conversion']['unitig_count']:
            polished.write_text('')
            step['status'] = 'not_run_empty_source_assembly'
            record['empty_source_reason'] = 'Miniasm produced no unitigs to polish; empty sequence output is retained.'
        else:
            save(manifest, record)
            stderr_path = output / 'minipolish.stderr.log'
            with polished.open('w') as stdout, stderr_path.open('w') as stderr:
                result = subprocess.run(step['command'], stdout=stdout, stderr=stderr)
            step['exit_code'] = result.returncode
            step['stderr_tail'] = stderr_path.read_text(errors='replace')[-4000:]
            if result.returncode:
                raise RuntimeError('Minipolish failed with exit code ' + str(result.returncode))
        record['conversion'] = extract_unitigs(polished, output / 'assembly_graph.gfa', output / 'assembly.fasta', require_length_tag=False)
        record['status'] = 'complete'
    except Exception as error:
        record.update(status='error', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        save(manifest, record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reads', type=Path, required=True)
    parser.add_argument('--raw-graph', type=Path, required=True)
    parser.add_argument('--source-execution', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--threads', type=int, required=True)
    parser.add_argument('--rounds', type=int, default=2)
    args = parser.parse_args()
    run(args.reads, args.raw_graph, args.source_execution, args.output, args.threads, args.rounds)
