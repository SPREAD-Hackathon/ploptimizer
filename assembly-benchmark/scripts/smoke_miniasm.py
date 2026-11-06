"""Exercise the installed adapter using artificial random DNA, not a genome."""
import json
from pathlib import Path
import random
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.common import ROOT, digest, fingerprint, reverse_complement, save
from pipeline.execution import run
from scripts.collect_graph_artifacts import collect_selected, write_sidecars


def smoke():
    batch = ROOT / 'runs' / ('miniasm-install-smoke-' + os.environ.get('SLURM_JOB_ID', 'local'))
    if batch.exists():
        raise ValueError('Smoke output already exists; inspect it instead of overwriting')
    inputs = batch / 'cases' / 'artificial-linear'
    inputs.mkdir(parents=True)
    rng = random.Random(739)
    sequence = ''.join(rng.choice('ACGT') for _ in range(40000))
    truth = inputs / 'truth.fasta'
    truth.write_text('>artificial\n' + sequence + '\n')
    # The backend hashes the input file; the assembler accepts plain FASTQ too.
    reads = inputs / 'reads.fastq.gz'
    import gzip
    with gzip.open(reads, 'wt') as stream:
        count = 0
        for start in range(0, len(sequence) - 8000 + 1, 250):
            read = sequence[start:start + 8000]
            if rng.getrandbits(1):
                read = reverse_complement(read)
            stream.write(f'@artificial_{count}\n{read}\n+\n' + 'I' * len(read) + '\n')
            count += 1
    case = {'id': 'artificial-linear', 'category': 'fixture',
            'replicons': [{'refseq_accession': 'artificial', 'replicon_name': 'artificial',
                          'molecule_type': 'chromosome', 'topology': 'linear', 'length_bp': len(sequence)}]}
    case['fingerprint'] = fingerprint(case)
    save(inputs / 'input.json', {'case': case, 'status': 'valid', 'reads_sha256': digest(reads), 'truth_sha256': digest(truth)})
    record = run(case, 'miniasm', batch, {'threads': 2, 'timeout_seconds': 300})
    if record['status'] not in ('pass', 'fail'):
        raise RuntimeError(record)
    if record['evaluation']['contig_count'] < 1:
        raise ValueError('Artificial fixture produced no unitigs')
    path = 'results/artificial-linear/miniasm/execution.json'
    artifacts = collect_selected(ROOT, batch.name, [path])
    write_sidecars(ROOT, batch.name, artifacts)
    artifact = artifacts['executions'][0]['artifact']
    if artifact['graph']['status'] != 'available' or artifact['assembly_info']['status'] != 'available':
        raise ValueError('Graph or unitig inventory failed: ' + str(artifact))
    if record['assembly_workflow']['status'] != 'complete' or len(record['assembly_workflow']['steps']) != 2:
        raise ValueError('Two-step provenance incomplete')
    result = {'status': 'pass', 'scope': 'Installation/integration test on artificial random DNA; not a benchmark result.',
              'versions': record['assembly_workflow']['versions'],
              'graph_status': artifact['graph']['status'], 'unitig_inventory_status': artifact['assembly_info']['status'],
              'unitig_count': record['evaluation']['contig_count'], 'workflow_steps': 2}
    save(ROOT / '.cache/miniasm-integration/smoke-result.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(smoke(), indent=2))
