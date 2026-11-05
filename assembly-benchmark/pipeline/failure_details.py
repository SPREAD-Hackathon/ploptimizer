"""Consistent detail records from saved observations; no new change inference."""
import copy

CONFIDENCES = {'confirmed','suspected','unresolved'}


def _field(value=None, source=None, status='not_recorded'):
    return {'status':status,'value':copy.deepcopy(value),'source':source}


def recorded_change(record):
    """Normalize literal review wording, never infer events from lengths/spans."""
    review=record.get('sequence_review') or {}
    result={'status':'not_recorded','description':None,'source':None,'confidence':'unresolved',
            'type':_field(),'length_bp':_field(),'reference_intervals':_field(),'output_intervals':_field(),
            'coordinate_system':'0-based half-open intervals',
            'difference_event_table':{'status':'not_collected','records':None}}
    if review.get('status')!='verified':
        return result
    summary=review.get('summary','')
    result.update(status='reviewed',description=summary,source='sequence_review.summary',confidence='confirmed')
    for phrase in ('duplicated terminal overlap','deletions','deletion'):
        if phrase in summary.lower():
            result['type']=_field(phrase,'sequence_review.summary','reported')
            break
    validation=review.get('validation') or {}
    if 'excess_bp' in validation:
        result['length_bp']=_field(validation['excess_bp'],'sequence_review.validation.excess_bp','reported_excess')
    for key in ('reference_interval_0based_half_open','reference_deletion_interval_0based_half_open'):
        if key in validation:
            result['reference_intervals']=_field([validation[key]],'sequence_review.validation.'+key,'recorded')
            break
    if 'query_intervals_0based_half_open' in validation:
        result['output_intervals']=_field(validation['query_intervals_0based_half_open'],'sequence_review.validation.query_intervals_0based_half_open','recorded')
    return result


def detail_record(record, molecules, plot, recorded_coordinates=None, coordinate_sidecar=None):
    finding=record.get('explanation') or {}
    confidence=finding.get('confidence') if finding.get('confidence') in CONFIDENCES else 'unresolved'
    required=[m['exact'] for m in molecules if m['required_by_endpoint']]
    graph=(record.get('graph_artifacts') or {}).get('graph') or {}
    info=(record.get('graph_artifacts') or {}).get('assembly_info') or {}
    log=record.get('explanation_log') or {}
    availability={
        'exact_assessment':{'status':'available' if record.get('evaluation') else 'not_collected','source':'evaluation'},
        'mapping_summary':{'status':(record.get('diagnostics') or {}).get('status','not_collected'),'source':'diagnostics'},
        'graph_metadata':{'status':graph.get('status','not_collected'),'source':'graph_artifacts.graph'},
        'reported_circularity':{'status':info.get('status','not_collected'),'source':'graph_artifacts.assembly_info'},
        'saved_log_observations':{'status':'available' if log else 'not_collected','source':'explanation_log'},
        'review':{'status':(record.get('sequence_review') or {}).get('status','not_collected'),'source':'sequence_review'},
        'dot_plot':{'status':plot['status'],'source':plot.get('source'),'reason':plot.get('reason')},
        'difference_events':{'status':'not_collected','source':None,'reason':'No general base-level difference-event table is recorded.'}}
    if recorded_coordinates is not None:
        availability['recorded_coordinate_file']={'status':recorded_coordinates['status'],
            'source':recorded_coordinates.get('source'),'reason':recorded_coordinates.get('reason')}
    if coordinate_sidecar is not None:
        availability['completed_coordinate_sidecar']={'status':coordinate_sidecar['status'],'source':coordinate_sidecar.get('source'),'reason':coordinate_sidecar.get('reason')}
    circularity={'status':info.get('status','not_collected'),'source':copy.deepcopy(info.get('source')),
                 'contigs':copy.deepcopy(info.get('contigs',[])),
                 'scope':'Assembler-reported claims for the labelled workflow stage; not physical topology validation.'}
    mechanism=finding.get('mechanism_confidence')
    return {'schema_version':1,
        'outcome':{'execution_status':record['status'],'endpoint':(record.get('evaluation') or {}).get('endpoint'),
                   'failed_required_accessions':[m['accession'] for m in required if m.get('status')=='fail'],
                   'source':'evaluation.replicons'},
        'recorded_change':recorded_change(record),
        'interpretation':{'confidence':confidence,'summary':finding.get('summary'),
                          'text':finding.get('interpretation'),'source':'explanation',
                          'scope':finding.get('confidence_scope') or finding.get('scope')},
        'supporting_evidence':copy.deepcopy(finding.get('evidence',[])),
        'mechanism':{'confidence':mechanism if mechanism in CONFIDENCES else 'unresolved',
                     'source':'explanation.mechanism_confidence',
                     'scope':'No new software-internal cause is assigned. Saved review claims retain their original scope.'},
        'reported_circularity':circularity,'availability':availability}


def coverage_summary(documents, primary_batches):
    def count(selected):
        statuses={};sources={};coordinate_statuses={};sidecar_statuses={};failure_plot_statuses={};total=0;empty=0;failures=0
        for document in selected:
            for record in document['results']:
                total+=1;failures+=record['status']=='fail'
                evidence=record['report_evidence'];plot=evidence['dotplot']
                statuses[plot['status']]=statuses.get(plot['status'],0)+1
                if record['status']=='fail':
                    failure_plot_statuses[plot['status']]=failure_plot_statuses.get(plot['status'],0)+1
                if plot['status']=='available':
                    kind=plot.get('source_kind','reviewed_coordinates')
                    sources[kind]=sources.get(kind,0)+1
                    empty+=bool(plot.get('empty'))
                coordinate=evidence['failure_details']['availability'].get('recorded_coordinate_file',{})
                state=coordinate.get('status','not_requested')
                coordinate_statuses[state]=coordinate_statuses.get(state,0)+1
                sidecar=evidence['failure_details']['availability'].get('completed_coordinate_sidecar',{})
                state=sidecar.get('status','not_requested')
                sidecar_statuses[state]=sidecar_statuses.get(state,0)+1
        return {'execution_views':total,'scientific_failures':failures,'plot_status_counts':statuses,
                'plot_source_counts':sources,'verified_empty_coordinate_plots':empty,
                'recorded_coordinate_file_status_counts':coordinate_statuses,'failure_plot_status_counts':failure_plot_statuses,'completed_sidecar_status_counts':sidecar_statuses}
    return {'schema_version':1,'scope':'Availability of already-produced evidence, not an assembly-quality score',
            'all_source_views':count(documents),
            'primary_cohort':count([d for d in documents if d['batch'] in primary_batches]),
            'primary_batches':list(primary_batches)}


def markdown_detail_sections(details):
    status=details['outcome']['execution_status']
    lines=['## Failure detail' if status=='fail' else '## Assessment detail', '']
    failed=details['outcome']['failed_required_accessions']
    missing='None; saved endpoint passes.' if status=='pass' else 'No completed molecule-level assessment for this execution.' if status not in ('pass','fail') else 'None listed; inspect the saved scenario-level failure reason.'
    lines += ['- Required molecules failing the saved endpoint: '+(', '.join(failed) if failed else missing), '']
    change=details['recorded_change']
    lines += ['### Recorded difference', '']
    if change['status']=='reviewed':
        lines += [change['description'], '', '- Confidence: confirmed within the saved review scope.']
    else:
        lines += [('No reviewed sequence change is recorded. An exact failure does not locate a difference or identify its type.' if status=='fail' else 'No separate reviewed change record is attached to this outcome.'), '']
    for key,label in (('type','Recorded type'),('length_bp','Recorded length/excess (bp)'),('reference_intervals','Reference intervals'),('output_intervals','Output intervals')):
        field=change[key]
        lines.append(f'- {label}: `{field["value"]}` · source `{field["source"]}`' if field['status']!='not_recorded' else f'- {label}: not recorded.')
    lines += ['- Coordinate convention: 0-based half-open intervals.', '- General per-base difference-event table: not collected.', '', '### Interpretation and confidence', '']
    interpretation=details['interpretation']
    lines += [f'- Saved interpretation confidence: {interpretation["confidence"]}.',
              f'- Saved summary: {interpretation.get("summary") or "Not recorded"}',
              f'- Saved interpretation: {interpretation.get("text") or "Unresolved"}',
              f'- Saved confidence scope: {interpretation.get("scope") or "Not recorded"}',
              *([f'- Software-internal cause: {details["mechanism"]["confidence"]}. {details["mechanism"]["scope"]}'] if status=='fail' else []), '']
    if details['supporting_evidence']:
        lines += ['### Supporting evidence', '']
        for item in details['supporting_evidence']:
            lines.append(f'- {item.get("text","")} · source `{item.get("source","not recorded")}`' if isinstance(item,dict) else '- '+str(item))
        lines.append('')
    circularity=details['reported_circularity']
    lines += ['### Reported output and circularity', '', f'Saved report status: **{circularity["status"]}**. {circularity["scope"]}', '']
    source=circularity.get('source') or {}
    if source:
        lines += [f'Source: `{source.get("filename","not recorded")}` · workflow role: `{source.get("role","not recorded")}`.', '']
    if circularity['contigs']:
        lines += ['| Reported contig | Reference origin | Length (bp) | Circularity claim | Graph path |','| --- | --- | ---: | --- | --- |']
        for row in circularity['contigs']:
            origin=circularity.get('reference_origins',{}).get(row['id'],{})
            names=' / '.join(ref['name'] for ref in origin.get('references',[])) or 'Unassigned'
            description=names+' ('+origin.get('status','unassigned')+')'
            lines.append(f'| {row["id"]} | {description} | {row.get("length_bp","Not recorded")} | {row.get("reported_circularity","unknown")} ({row.get("reported_circularity_raw","source token unavailable")}) | {row.get("reported_graph_path","Not recorded")} |')
        lines.append('')
    lines += ['### Evidence availability', '', '| Evidence | Recorded status | Source / reason |','| --- | --- | --- |']
    for name,item in details['availability'].items():
        reference=item.get('source') or item.get('reason') or 'Not recorded'
        lines.append(f'| {name.replace("_"," ")} | {item["status"]} | {reference} |')
    return lines+['']
