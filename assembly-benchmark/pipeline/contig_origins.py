"""Contig/reference associations from existing exact checks and saved mappings."""
from .reference_origins import reference_colour


def build_contig_origins(case, record, artifact, plot):
    references={}
    for molecule in case.get('replicons',[]):
        colour,light=reference_colour(molecule)
        accession=molecule['refseq_accession']
        references[accession]={'id':accession,'name':molecule.get('replicon_name',accession),
                               'colour':colour,'light_colour':light}
    info=artifact.get('assembly_info') or {}
    bound=bool(record.get('assembly_sha256')) and (artifact.get('input_hashes') or {}).get('assembly_sha256')==record['assembly_sha256']
    final=bound and not artifact.get('failed_execution_provenance') and info.get('source',{}).get('role')=='final'
    exact={};aligned={}
    for index,molecule in enumerate((record.get('evaluation') or {}).get('replicons',[])):
        accession=molecule.get('accession')
        if accession not in references:continue
        for name in molecule.get('exact_contigs',[]):
            exact.setdefault(name,[]).append({'reference_id':accession,'kind':'exact',
                'source':f'evaluation.replicons[{index}].exact_contigs'})
    diagnostic=record.get('diagnostics') or {}
    hashes=diagnostic.get('input_hashes') or {}
    summary_bound=diagnostic.get('status')=='complete' and all(record.get(key) and hashes.get(key)==record[key] for key in ('assembly_sha256','truth_sha256'))
    if summary_bound:
        for index,molecule in enumerate(diagnostic.get('evidence',{}).get('replicons',[])):
            accession=molecule.get('accession')
            if accession not in references:continue
            for name in molecule.get('contigs',[]):
                aligned.setdefault(name,[]).append({'reference_id':accession,'kind':'accepted_alignment',
                    'source':f'diagnostics.evidence.replicons[{index}].contigs'})
    elif plot.get('status')=='available' and all(record.get(key) and plot.get('input_hashes',{}).get(key)==record[key] for key in ('assembly_sha256','truth_sha256')):
        lengths={row['id']:row['length_bp'] for row in info.get('contigs',[]) if row.get('length_bp') is not None}
        for index,row in enumerate(plot.get('alignments',[])):
            name=row.get('query_id');accession=row.get('reference_id')
            if name not in lengths or accession not in references or row.get('query_length')!=lengths[name]:continue
            item={'reference_id':accession,'kind':'recorded_alignment','source':f'report_evidence.dotplot.alignments[{index}]'}
            aligned.setdefault(name,[]).append(item)
    result={}
    for contig in info.get('contigs',[]):
        name=contig['id'];evidence=exact.get(name,[])+aligned.get(name,[]) if final else []
        exact_ids=sorted({row['reference_id'] for row in exact.get(name,[])}) if final else []
        alignment_ids=sorted({row['reference_id'] for row in aligned.get(name,[])}) if final else []
        selected=exact_ids or alignment_ids
        status='ambiguous' if len(selected)>1 else 'exact' if exact_ids else 'aligned' if alignment_ids else 'unassigned'
        reason=('Intermediate or unbound output: final-reference evidence is not assigned.' if not final else
                'Multiple reference associations; shared sequence alone does not establish a mixed contig.' if status=='ambiguous' else
                'Saved exact sequence match.' if status=='exact' else
                'Saved alignment association only; exact identity is not established.' if status=='aligned' else
                'No source-bound reference match is recorded for this contig identifier.')
        result[name]={'status':status,'references':[references[key] for key in selected],
                      'candidate_reference_ids':sorted(set(exact_ids+alignment_ids)),
                      'evidence':evidence,'reason':reason}
    return result
