"""Reproduce a base review of existing FASTAs and an existing gap-free PAF."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.base_review import circular_equivalence, review_gapfree_pair
from pipeline.common import digest, fasta, load, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('truth', 'assembly', 'paf', 'execution', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    for name in ('initial', 'reconstructed'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--checkpoint-gfa', type=Path, action='append', default=[])
    args = parser.parse_args()
    execution = load(args.execution)
    hashes = {key:digest(path) for key,path in [('truth_sha256',args.truth), ('assembly_sha256',args.assembly),
                                             ('paf_sha256',args.paf), ('execution_sha256',args.execution)]}
    if any(hashes[key] != execution[key] for key in ('truth_sha256', 'assembly_sha256')):
        raise ValueError('FASTA bytes differ from the recorded run')
    truth, assembly = fasta(args.truth), fasta(args.assembly)
    result = review_gapfree_pair(truth, assembly, args.paf.read_bytes())
    result.update(schema_version=1, status='verified', batch_id=execution['batch_id'],
                  scenario_id=execution['scenario_id'], tool=execution['tool'],
                  strict_status=execution['status'], hashes=hashes, stage_comparisons={})
    if args.initial:
        reference = truth[result['reference_id']]
        matches = [name for name, seq in fasta(args.initial).items() if circular_equivalence(reference, seq) is not None]
        result['stage_comparisons']['initial'] = {'sha256':digest(args.initial), 'exact_reference_contigs':matches}
    if args.reconstructed:
        query = assembly[result['query_id']]
        matches = [name for name, seq in fasta(args.reconstructed).items() if circular_equivalence(query, seq) is not None]
        result['stage_comparisons']['reconstructed'] = {'sha256':digest(args.reconstructed), 'exact_final_contigs':matches}
    result['graph_checkpoints'] = []
    for path in args.checkpoint_gfa:
        segments = [fields for line in path.read_text().splitlines()
                    if (fields := line.split('\t'))[0] == 'S']
        result['graph_checkpoints'].append({'filename':path.name, 'sha256':digest(path),
            'segments':[{'id':fields[1], 'length_bp':len(fields[2]),
                         'exact_reference':circular_equivalence(truth[result['reference_id']], fields[2]) is not None,
                         'exact_final':circular_equivalence(assembly[result['query_id']], fields[2]) is not None}
                        for fields in segments]})
    save(args.output, result)


if __name__ == '__main__':
    main()
