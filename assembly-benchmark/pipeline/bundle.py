"""Export frozen evidence into a versioned, web-independent results bundle.

This stage reads saved metadata only. It never runs assemblers, mappers or jobs.
"""
import copy
import csv
import re
import tempfile
import shlex
from importlib.metadata import version
from pathlib import Path

from .common import ROOT, digest, load, save
from .evidence_model import diagnostic_summary, diagnostic_policy, molecule_explanation, alignment_classification, candidate_labels
from .explanations import explain_result
from .reference_origins import build_reference_origins
from .contig_origins import build_contig_origins
from .result_model import assessed_molecules, verdict
from .identities import result_slug as result_id
from .recorded_coordinates import recorded_paf_plot
from .recorded_sidecars import completed_sidecar_plot
from .failure_details import detail_record, coverage_summary, markdown_detail_sections

VERSION = 1
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


def identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Bundle identifiers must be simple names')
    return value


def checked_document(document):
    if not isinstance(document,dict) or document.get('schema_version') != 1:
        raise ValueError('Unsupported source snapshot schema')
    identifier(document['batch'])
    cases = {identifier(case['id']): case for case in document['scenarios']}
    if len(cases) != len(document['scenarios']):
        raise ValueError('Duplicate scenario identity')
    seen = set()
    for record in document['results']:
        key = result_id(record)
        if key in seen or record['scenario_id'] not in cases:
            raise ValueError('Duplicate execution or unknown scenario')
        seen.add(key)
        review=record.get('sequence_review') or {}
        if review.get('status')=='verified':
            hashes=review.get('hashes') or {}
            if review.get('scenario_id')!=record['scenario_id'] or review.get('tool')!=record['tool'] or any(not record.get(name) or hashes.get(name)!=record[name] for name in ('assembly_sha256','truth_sha256')):
                raise ValueError('Verified review provenance differs from the execution')
        artifact = record.get('graph_artifacts') or {}
        attached = artifact.get('input_hashes', {}).get('assembly_sha256')
        if attached and record.get('assembly_sha256') and attached != record['assembly_sha256']:
            raise ValueError('Graph assembly hash differs from scored assembly')
    return document


def saved_plot(record):
    """Package explicit reviewed coordinates; no coordinate inference or alignment."""
    review = record.get('sequence_review') or {}
    validation = review.get('validation') or {}
    rows = validation.get('alignment_records')
    if review.get('status') != 'verified' or not rows:
        return {'status':'not_collected', 'reason':'No source-bound reviewed alignment coordinates are recorded.', 'nucmer_status':'not_collected'}
    if review.get('scenario_id') != record['scenario_id'] or review.get('tool') != record['tool'] or review.get('strict_status') != record['status']:
        return {'status':'not_collected','reason':'The saved review identifies a different execution or score.','nucmer_status':'not_collected'}
    hashes = review.get('hashes') or {}
    if not record.get('assembly_sha256') or hashes.get('assembly_sha256') != record['assembly_sha256'] or not record.get('truth_sha256') or hashes.get('truth_sha256') != record['truth_sha256']:
        return {'status':'not_collected','reason':'Review input hashes do not match this execution.','nucmer_status':'not_collected'}
    for row in rows:
        for interval_key, length_key in (('query_interval','query_length'),('reference_interval','reference_length')):
            interval, length = row.get(interval_key), row.get(length_key)
            if not isinstance(length,int) or isinstance(length,bool) or length <= 0 or not isinstance(interval,list) or len(interval)!=2 or not all(isinstance(v,int) and not isinstance(v,bool) for v in interval) or not 0 <= interval[0] < interval[1] <= length:
                raise ValueError('Invalid saved review coordinate interval')
        if row.get('strand') not in ('+','-'):
            raise ValueError('Invalid saved alignment strand')
    if len({row['query_length'] for row in rows})!=1 or len({row['reference_length'] for row in rows})!=1:
        return {'status':'not_collected','reason':'Saved review does not identify one consistent reference/query pair.','nucmer_status':'not_collected'}
    return {'status':'available', 'source':'sequence_review.validation.alignment_records',
            'method':'Saved reviewed alignment records; not a NUCmer run',
            'coordinate_system':'0-based half-open intervals', 'nucmer_status':'not_collected',
            'reference_length':rows[0]['reference_length'], 'query_length':rows[0]['query_length'],
            'alignments':copy.deepcopy(rows), 'input_hashes':copy.deepcopy(hashes),
            'review_source':review.get('source_document'),
            'detail':{key:copy.deepcopy(validation[key]) for key in ('query_intervals_0based_half_open','reference_interval_0based_half_open','excess_bp') if key in validation}}


def checked_facts(record):
    review=record.get('sequence_review') or {}
    if review.get('status')!='verified':
        return []
    validation=review.get('validation') or {}
    labels=(('reference_length','Reference length (bp)'),('query_length','Output length (bp)'),
            ('excess_bp','Recorded excess (bp)'),
            ('reference_interval_0based_half_open','Recorded reference interval (0-based, half-open)'),
            ('query_intervals_0based_half_open','Recorded output intervals (0-based, half-open)'),
            ('terminal_sequence','Recorded terminal sequence'),
            ('tool_reported_circularity','Assembler circularity value'))
    return [{'label':label,'value':copy.deepcopy(validation[key]),'source':'sequence_review.validation.'+key} for key,label in labels if key in validation]


def prepare_document(source, artifact_root=None, coordinate_roots=(), snapshot_hash=None):
    document = copy.deepcopy(checked_document(source))
    cases = {case['id']:case for case in document['scenarios']}
    for record in document['results']:
        record.pop('report_evidence',None)
        case = cases[record['scenario_id']]
        if not record.get('explanation'):
            record['explanation'] = explain_result(record, case=case)
        graph = record.get('graph_artifacts') or {'status':'not_collected','reason':'No graph metadata collected.'}
        relevant = [m.get('accession') for m in assessed_molecules(record)]
        heading, description = verdict(record)
        mappings = {row['accession']:row for row in (record.get('diagnostics') or {}).get('evidence',{}).get('replicons',[])}
        policy = diagnostic_policy(record.get('diagnostics') or {})
        molecules = []
        for score in (record.get('evaluation') or {}).get('replicons',[]):
            mapping = mappings.get(score['accession'])
            molecules.append({'exact':copy.deepcopy(score),'required_by_endpoint':score.get('accession') in relevant,
                              'mapping':copy.deepcopy(mapping),
                              'mapping_description':molecule_explanation(mapping,policy,score) if mapping else 'Mapping not collected.',
                              'mapping_kind':alignment_classification(mapping,policy)[0] if mapping else None,
                              'candidate_labels':candidate_labels(mapping) if mapping else []})
        reviewed_plot=saved_plot(record)
        coordinate_plot=recorded_paf_plot(case,record,document['batch'],artifact_root) if artifact_root is not None else None
        plot=reviewed_plot if reviewed_plot['status']=='available' or coordinate_plot is None else coordinate_plot
        sidecar_plot=None
        if plot['status']!='available' and coordinate_roots:
            sidecar_plot=completed_sidecar_plot(case,record,document['batch'],coordinate_roots,artifact_root,snapshot_hash)
            if sidecar_plot['status']!='not_applicable':
                plot=sidecar_plot
        contig_origins=build_contig_origins(case,record,graph,plot)
        record['report_evidence'] = {'schema_version':VERSION, 'heading':heading, 'description':description,
            'summary':diagnostic_summary(record,case), 'required_accessions':relevant, 'molecules':molecules,
            'reference_origins':build_reference_origins(case,record,graph), 'contig_origins':contig_origins, 'dotplot':plot, 'checked_facts':checked_facts(record),
            'failure_details':detail_record(record,molecules,plot,coordinate_plot,sidecar_plot)}
        record['report_evidence']['failure_details']['reported_circularity']['reference_origins']=contig_origins
    if document.get('determinism'):
        document['determinism']['executions'] = document['results']
    document['report_bundle_version'] = VERSION
    return document


def markdown_report(case, record, batch):
    evidence = record['report_evidence']
    lines = [f'# {case["title"]} — {record["tool"]}', '', f'**Exact outcome: {record["status"].upper()}**', '',
             evidence['description'], '', '## Recorded outcome', '',
             f'- Batch: `{batch}`', f'- Scenario: `{record["scenario_id"]}`',
             f'- Version: {record.get("version", "Not recorded")}',
             f'- Endpoint: {(record.get("evaluation") or {}).get("endpoint", "Not recorded")}', '']
    for molecule in evidence['molecules']:
        score, mapping = molecule['exact'], molecule['mapping']
        lines += [f'### {score.get("name", score["accession"])} · {score["accession"]}', '',
                  f'- Expected length: {score.get("length_bp", "Not recorded")} bp',
                  f'- Required by endpoint: {molecule["required_by_endpoint"]}',
                  f'- Exact outcome: {score.get("status", "unscored")}',
                  f'- Exact matching contigs: {", ".join(score.get("exact_contigs", [])) or "None recorded"}',
                  f'- Saved reason: {score.get("reason", "Not recorded")}',
                  f'- Mapping: {molecule["mapping_description"]}', '']
    review=record.get('sequence_review') or {}
    validation=review.get('validation') or {}
    if review.get('status')=='verified':
        lines += ['## Checked discrepancy', '', review.get('summary',''), '']
        for fact in evidence['checked_facts']:
            lines.append(f'- {fact["label"]}: `{fact["value"]}`')
        lines.append('')
    lines += markdown_detail_sections(evidence['failure_details'])
    plot=evidence['dotplot']
    lines += ['## Alignment dot plot', '']
    if plot['status']=='available':
        lines += ['![Saved alignment coordinate spans](./'+result_id(record)+'-alignment.svg)', '',
                  f'Source: `{plot["source"]}`. {plot["method"]}. Coordinates: {plot["coordinate_system"]}.', '',
                  ('All saved mandatory PAF coordinate rows are displayed. The saved filtered measurements and exact score are separate; optional tags and individual changed bases are not shown.' if plot.get('source_kind')=='recorded_paf' else plot['display_scope'] if plot.get('source_kind')=='recorded_show_coords' else 'The full-scale plot cannot resolve a few bases. The separate interval panels show only terminal intervals already recorded in the review.'), '']
    else:
        lines += [plot['reason'], '']
    if plot.get('nucmer_status')=='available':
        lines += ['[Original NUCmer table: 1-based inclusive endpoints](./'+result_id(record)+'-original-show-coords.tsv)', '']
    else:
        lines += ['No NUCmer coordinate source is recorded for this result.', '']
    lines += ['A general per-base difference-event table has not been collected.', '', '## Command', '', '```text',
              shlex.join(str(arg) for arg in record.get('command',[])) or 'Not recorded', '```', '', '## Source provenance', '',
              f'- Source result: `../../batches/{batch}.json`', f'- Record identity: `{result_id(record)}`']
    for key in ('assembly_sha256','truth_sha256','reads_sha256'):
        if record.get(key):lines.append(f'- {key}: `{record[key]}`')
    if record.get('sequence_review'):
        lines += [f'- Review: `{record["sequence_review"].get("source_document", "Not recorded")}`',
                  f'- Review scope: {record["sequence_review"].get("scope", "Not recorded")}']
    return '\n'.join(lines)+'\n'


def write_tsv(path, columns, rows):
    with path.open('w',newline='') as stream:
        writer=csv.writer(stream,delimiter='\t');writer.writerow(columns);writer.writerows(rows)


def export_bundle(snapshots, output, *, primary_batch, cohort, replace=False, artifact_root=None, coordinate_roots=()):
    """Rebuild metadata products into a new directory; never overwrite arbitrary files."""
    from .bundle_plot import alignment_svg
    from .overview_model import build_overview
    output=Path(output)
    if output.exists() and any(output.iterdir()):
        if not replace:
            raise ValueError('Export destination must be empty; use --replace for a validated generated bundle')
        load_bundle(output)
        with tempfile.TemporaryDirectory(dir=output.parent, prefix='.bundle-staging-') as temporary:
            staging=Path(temporary)
            replacement=export_bundle(snapshots,staging/'next',primary_batch=primary_batch,cohort=cohort,artifact_root=artifact_root,coordinate_roots=coordinate_roots)
            previous=staging/'previous';output.rename(previous)
            try:
                replacement.rename(output)
            except OSError:
                previous.rename(output)
                raise
        return output
    documents=[]; sources=[]
    for path in snapshots:
        path=Path(path);source=checked_document(load(path))
        sources.append({'filename':path.name,'sha256':digest(path),'batch':source['batch']})
        documents.append(prepare_document(source,artifact_root=artifact_root,coordinate_roots=coordinate_roots,snapshot_hash=digest(path)))
    if len({d['batch'] for d in documents})!=len(documents) or primary_batch not in {d['batch'] for d in documents}:
        raise ValueError('Bundle needs unique batches and its declared primary batch')
    # Build before writing: invalid cohorts/duplicate identities leave no partial bundle.
    overview=build_overview(documents,cohort=cohort,root_batch=primary_batch)
    models={}
    for document in documents:
        families=['S3'] if document['config'].get('determinism') else list(dict.fromkeys(c['category'] for c in document['scenarios']))
        local={'schema_version':1,'primary_batches':[document['batch']],'families':families,'tools':document['config']['tools']}
        models[document['batch']]=build_overview([document],cohort=local,archived_batch=document['batch'])
    output.mkdir(parents=True,exist_ok=True)
    summary=[]; molecules=[]; availability=[]
    for document in documents:
        batch=document['batch'];save(output/'batches'/f'{batch}.json',document)
        save(output/'models'/f'{batch}.json',models[batch])
        cases={case['id']:case for case in document['scenarios']}
        for index,record in enumerate(document['results']):
            slug=result_id(record);base=output/'reports'/batch;base.mkdir(parents=True,exist_ok=True)
            evidence=record['report_evidence']
            save(base/f'{slug}.json',{'schema_version':VERSION,'batch':batch,'scenario':cases[record['scenario_id']],
                'source_document':f'../../batches/{batch}.json','record_index':index,'evidence':evidence,
                'finding':record.get('explanation'),'sequence_review':record.get('sequence_review'),
                'execution':{k:record[k] for k in ('scenario_id','tool','run_id','status','version','command','assembly_sha256','truth_sha256','reads_sha256','evaluation') if k in record}})
            (base/f'{slug}.md').write_text(markdown_report(cases[record['scenario_id']],record,batch))
            if evidence['dotplot']['status']=='available':
                (base/f'{slug}-alignment.svg').write_text(alignment_svg(evidence['dotplot']))
                write_tsv(base/f'{slug}-alignments.tsv',['reference_id','reference_length_bp','reference_start_0based','reference_end_exclusive','query_id','query_length_bp','query_start_0based','query_end_exclusive','strand','identity_percent_recorded','matches_recorded','block_length_recorded','edit_distance_recorded','mapq_recorded'],
                    [[row.get('reference_id','reviewed_reference'),row['reference_length'],*row['reference_interval'],row.get('query_id','reviewed_output'),row['query_length'],*row['query_interval'],row['strand'],row.get('identity_percent'),row.get('matches'),row.get('block_length'),row.get('edit_distance'),row.get('mapq')] for row in evidence['dotplot']['alignments']])
                if evidence['dotplot'].get('nucmer_status')=='available':
                    (base/f'{slug}-original-show-coords.tsv').write_bytes(evidence['dotplot']['original_coordinates_tsv'].encode('ascii'))
            availability.append([batch,record['scenario_id'],record['tool'],record.get('run_id',''),record['status'],evidence['dotplot']['status'],evidence['dotplot'].get('source_kind','reviewed_coordinates') if evidence['dotplot']['status']=='available' else '',evidence['dotplot'].get('alignment_count',len(evidence['dotplot'].get('alignments',[]))),evidence['dotplot'].get('empty',False),evidence['failure_details']['recorded_change']['status'],evidence['failure_details']['mechanism']['confidence'],evidence['dotplot'].get('reason','')])
            summary.append([batch,record['scenario_id'],record['tool'],record.get('run_id',''),record['status'],record.get('version',''),record.get('elapsed_seconds',''),evidence['summary']])
            for row in evidence['molecules']:
                score=row['exact'];mapping=row['mapping'] or {}
                molecules.append([batch,record['scenario_id'],record['tool'],record.get('run_id',''),score['accession'],row['required_by_endpoint'],score.get('status'),score.get('length_bp'),','.join(score.get('exact_contigs',[])),mapping.get('recovered_fraction'),mapping.get('alignment_identity'),mapping.get('contig_count')])
    save(output/'overview.json',overview)
    write_tsv(output/'summary.tsv',['batch','scenario','tool','run','exact_status','version','elapsed_seconds','recorded_summary'],summary)
    write_tsv(output/'molecules.tsv',['batch','scenario','tool','run','accession','required_by_endpoint','exact_status','expected_length_bp','exact_contigs','aligned_reference_fraction','alignment_identity','aligned_contig_count'],molecules)
    write_tsv(output/'evidence-availability.tsv',['batch','scenario','tool','run','exact_status','plot_status','plot_source','recorded_alignment_rows','verified_empty_plot','reviewed_change_status','mechanism_confidence','plot_reason'],availability)
    save(output/'evidence-coverage.json',coverage_summary(documents,cohort.get('primary_batches',[])))
    counts=overview['counts']
    (output/'README.md').write_text(f'# Benchmark results bundle\n\nSchema: {VERSION}. Primary batch: {primary_batch}.\n\nHeadline cohort: {counts["pass"]} pass; {counts["fail"]} fail; {counts["errors"]} execution errors; {counts["unscored"]} unscored.\n\nSee summary.tsv, molecules.tsv and reports/<batch>/<result>.md. Tables include all source batches; headline counts use only the declared manifest cohort.\n\nExport repackages existing recorded evidence; it does not run assemblies, alignments or new assessments. Missing measurements stay missing.\n')
    files={str(path.relative_to(output)):digest(path) for path in sorted(output.rglob('*')) if path.is_file()}
    save(output/'manifest.json',{'schema_version':VERSION,'kind':'ploptimizer-results-bundle','primary_batch':primary_batch,'batches':[d['batch'] for d in documents],
        'sources':sources,'cohort':cohort,'coordinate_conventions':{'saved_review':'0-based half-open','human_labels':'explicitly labelled per view'},
        'producer':{'name':'metadata-export-v1','plotting_version':version('matplotlib') if any(r['report_evidence']['dotplot']['status']=='available' for d in documents for r in d['results']) else None,'entrypoint_sha256':digest(ROOT/'benchmark.py'),'manifest_schema_sha256':digest(ROOT/'schemas/results-bundle-v1.schema.json'),'sources':{p.name:digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}},'files':files})
    return output


def load_bundle(path):
    """Validate the complete bundle before a renderer writes any output."""
    path=Path(path);manifest=load(path/'manifest.json')
    if not isinstance(manifest,dict) or manifest.get('kind')!='ploptimizer-results-bundle' or manifest.get('schema_version')!=VERSION:
        raise ValueError('Unsupported results bundle')
    if not {'primary_batch','batches','sources','cohort','producer','files'} <= set(manifest):
        raise ValueError('Bundle manifest is incomplete')
    if not isinstance(manifest.get('files'),dict) or not manifest['files'] or not isinstance(manifest.get('batches'),list) or not manifest['batches']:
        raise ValueError('Bundle manifest is incomplete')
    for batch in manifest['batches']:
        identifier(batch)
    required={'README.md','summary.tsv','molecules.tsv','overview.json'}
    for batch in manifest['batches']:
        required.update({f'batches/{batch}.json',f'models/{batch}.json'})
    if not required <= set(manifest['files']):
        raise ValueError('Bundle manifest omits required files')
    for name,expected in manifest['files'].items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts or (path/relative).is_symlink() or not (path/relative).is_file() or digest(path/relative)!=expected:
            raise ValueError(f'Bundle file failed integrity validation: {name}')
    expected_files=set(manifest['files'])|{'manifest.json'}
    if {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()}!=expected_files:
        raise ValueError('Bundle contains unmanifested files')
    documents=[checked_document(load(path/'batches'/f'{identifier(batch)}.json')) for batch in manifest['batches']]
    if manifest['primary_batch'] not in manifest['batches'] or len(set(manifest['batches']))!=len(manifest['batches']):
        raise ValueError('Invalid bundle batch identities')
    for batch,document in zip(manifest['batches'],documents):
        if document['batch']!=batch:
            raise ValueError('Bundle document batch identity mismatch')
        if document.get('report_bundle_version')!=VERSION or any(r.get('report_evidence',{}).get('schema_version')!=VERSION for r in document['results']):
            raise ValueError('Bundle lacks prepared report evidence')
        for record in document['results']:
            slug=result_id(record)
            required={f'reports/{batch}/{slug}.json',f'reports/{batch}/{slug}.md'}
            if record['report_evidence']['dotplot']['status']=='available':
                required.update({f'reports/{batch}/{slug}-alignment.svg',f'reports/{batch}/{slug}-alignments.tsv'})
                if record['report_evidence']['dotplot'].get('nucmer_status')=='available':
                    required.add(f'reports/{batch}/{slug}-original-show-coords.tsv')
            if not required <= set(manifest['files']):
                raise ValueError('Bundle omits a result report or plot')
    return manifest,documents
