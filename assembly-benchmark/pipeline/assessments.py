"""Supplementary tolerant assessment without changing archived exact scores."""
import argparse
import importlib.metadata
from .common import ROOT, load, save, digest, fingerprint, fasta
from .diagnostic_runs import verified_inputs


def assess_batch(batch):
    from .tolerant import evaluate_tolerant
    config=load(batch/'config.json');counts={};cache={}
    for path in sorted((batch/'results').rglob('execution.json')):
        record=load(path)
        if record.get('status') not in ('pass','fail'):
            continue
        result={'status':'error'}
        try:
            case,truth,assembly,hashes=verified_inputs(batch,path,record,cache)
            runtime={'edlib':importlib.metadata.version('edlib'), 'evaluator_sha256':digest(ROOT/'pipeline/tolerant.py')}
            signature=fingerprint({'inputs':hashes,'runtime':runtime,'policy':config.get('tolerant_policy')})
            target=path.parent/'tolerant.json'
            previous=load(target) if target.exists() else {}
            if previous.get('cache_fingerprint')==signature and previous.get('status')!='error':
                result=previous
            else:
                result=evaluate_tolerant(case,truth,assembly,record['tool']=='plassembler',config.get('tolerant_policy'))
                result.update(input_hashes=hashes,runtime=runtime,cache_fingerprint=signature)
                save(target,result)
        except Exception as error:
            result.update(error=f'{type(error).__name__}: {error}',input_hashes={'execution_sha256':digest(path),'assembly_sha256':record.get('assembly_sha256')})
            save(path.parent/'tolerant.json',result)
        counts[result['status']]=counts.get(result['status'],0)+1
    return counts


def attach_assessment(record,path):
    target=path.parent/'tolerant.json' if path else None
    if record and target and target.exists():
        assessment=load(target);hashes=assessment.get('input_hashes',{})
        if record.get('assembly_sha256') and hashes.get('execution_sha256') and hashes.get('execution_sha256')==digest(path) and hashes.get('assembly_sha256')==record.get('assembly_sha256'):
            record['tolerant_assessment']=assessment
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch',required=True)
    args=parser.parse_args()
    from benchmark import batch_path
    print(assess_batch(batch_path(args.batch)))


def truth_controls(config,batch):
    """Admit real reference sequences before interpreting any assembler outcomes."""
    from .cases import plan
    from .common import write_fasta
    from .tolerant import evaluate_tolerant
    controls=[];seen=set()
    audit={row['refseq_accession']:row for row in load(ROOT/'data/references/audit.json')['replicons']}
    for case in plan(config):
        key=tuple(row['refseq_accession'] for row in case['replicons'])
        if key in seen:continue
        seen.add(key);sequences={}
        for replicon in case['replicons']:
            accession=replicon['refseq_accession'];path=ROOT/'data/references'/(accession+'.fasta')
            if digest(path)!=audit[accession]['file_sha256']:raise ValueError('Reference audit changed before tolerant controls')
            sequences.update(fasta(path))
        folder=batch/'validation'/case['source_case_id'];folder.mkdir(parents=True,exist_ok=True)
        truth=folder/'truth.fasta';write_fasta(truth,sequences)
        plasmids=[r for r in case['replicons'] if r['molecule_type']=='plasmid']
        if len(plasmids)!=1:raise ValueError('Smoke controls require exactly one plasmid')
        accession=plasmids[0]['refseq_accession'];reference=sequences[accession]
        mutated=dict(sequences);mutated[accession]=reference[:100]+reference[105:]
        duplicate={**sequences,'extra-plasmid-copy':reference}
        tandem=dict(sequences);tandem[accession]=reference+reference
        cases=[('exact-reference',sequences,'pass'),('five-base-deletion',mutated,'pass'),('duplicate',duplicate,'not-pass'),('tandem',tandem,'not-pass')]
        for label,assembly,wanted in cases:
            path=folder/(label+'.fasta');write_fasta(path,assembly)
            result=evaluate_tolerant(case,truth,path,False,config.get('tolerant_policy'))
            admitted=result['status']=='pass' if wanted=='pass' else result['status']!='pass'
            controls.append({'source_case_id':case['source_case_id'],'fixture':label,'expected':wanted,'admitted':admitted,'result':result,'truth_sha256':digest(truth),'assembly_sha256':digest(path)})
    document={'controls':controls,'admitted':bool(controls) and all(row['admitted'] for row in controls),'evaluator_sha256':digest(ROOT/'pipeline/tolerant.py')}
    save(batch/'provenance/tolerant-truth-controls.json',document)
    if not document['admitted']:raise ValueError('Tolerant endpoint failed real-reference truth controls; inspect provenance/tolerant-truth-controls.json')
    return document


if __name__=='__main__':
    main()
