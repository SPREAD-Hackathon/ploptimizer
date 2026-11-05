import React from 'react';
import { StatusBadge } from '@genomicx/ui';

export function originEvidenceClass(match) {
  if (match?.status === 'ambiguous') return 'ambiguous';
  if (match?.status !== 'supported') return 'unresolved';
  if (['verified_whole_segment', 'path_inferred'].includes(match.evidence_class)) return match.evidence_class;
  if (match.evidence?.some(item => item.association_kind === 'whole_segment_sequence_identity')) return 'verified_whole_segment';
  return match.evidence?.some(item => item.path_id && item.exact_source) ? 'path_inferred' : 'unresolved';
}

export const originLabels = {verified_whole_segment: 'Verified whole-segment identity', path_inferred: 'Inferred through contig path', ambiguous: 'Ambiguous reference association', unresolved: 'Unresolved origin'};
export const originShortLabels = {verified_whole_segment: 'Identity verified', path_inferred: 'Via contig path', ambiguous: 'Ambiguous', unresolved: 'Unresolved'};
const spanLabel = span => Array.isArray(span) && span.length === 2 ? span.map(value => value.toLocaleString()).join('–') : 'Not recorded';

export function OriginEvidence({ origin, node, origins }) {
  const kind = originEvidenceClass(origin.match);
  const evidence = origin.match?.evidence ?? [];
  const identity = evidence.find(item => item.association_kind === 'whole_segment_sequence_identity');
  return <div className="origin-evidence" style={{'--reference-colour':origin.reference?.colour,'--reference-light':origin.reference?.light_colour}}>
    <h4>Reference origin: {origin.reference?.name ?? 'Unresolved'}</h4>
    <p><StatusBadge variant={kind === 'verified_whole_segment' ? 'success' : kind === 'path_inferred' ? 'info' : 'muted'}>{originLabels[kind]}</StatusBadge></p>
    {kind === 'verified_whole_segment' && identity && <>
      <div className="origin-track">Whole segment · {origin.reference?.name}</div>
      <div className="origin-axis"><span>0 bp</span><span>{identity.length_bp.toLocaleString()} bp</span></div>
      <p>Segment and contig cover the same full interval: {spanLabel([0,identity.length_bp])} bp, 0-based and end excluded.</p>
    </>}
    {kind === 'path_inferred' && <p>Reference association comes from an exact-matching contig's recorded path. Segment-to-reference coordinates are not recorded.</p>}
    {kind === 'ambiguous' && <p>Saved evidence associates this segment with multiple references.</p>}
    {kind === 'unresolved' && <p>{origins?.unassigned_reason ?? 'No saved reference association is available.'}</p>}
    {evidence.length > 0 && <ul className="origin-proof-list">{evidence.map((item,index) => {
      const saved = origins?.contig_alignments?.[item.contig_id];
      const rows = saved?.rows?.filter(row => row.reference_id === item.reference_id) ?? [];
      return <li key={index}>
        <p><strong>{item.association_kind === 'whole_segment_sequence_identity' ? 'Verified sequence identity' : 'Recorded path association'}</strong></p>
        <p>Segment <code>{node.id}</code> → contig <code>{item.contig_id}</code> → reference <code>{item.reference_id}</code> (saved exact match).</p>
        {item.association_kind === 'whole_segment_sequence_identity' ? <>
          <p>Segment and contig have identical sequence hashes across {item.length_bp.toLocaleString()} bp, orientation {item.orientation}.</p>
          <details><summary>Identity evidence</summary><p>Source: <code>{item.identity_source}</code></p><code>{item.sequence_sha256}</code></details>
        </> : <p>GFA path <code>{item.path_id}</code> contains segment <code>{node.id}{item.orientation}</code>.</p>}
        {rows.length > 0 ? <details className="origin-coordinates"><summary>Saved contig/reference coordinates ({rows.length} displayed)</summary>
          <p>These spans describe the output contig. Coordinates are 0-based; the end is excluded.{kind === 'path_inferred' ? ' A position for this graph segment within the contig is not recorded.' : ''}</p>
          <div className="table-scroll"><table><thead><tr><th>Contig interval (bp)</th><th>Reference interval (bp)</th><th>Strand</th></tr></thead><tbody>{rows.map((row,i)=><tr key={i}><td>{spanLabel(row.query_interval)}</td><td>{spanLabel(row.reference_interval)}</td><td>{row.strand}</td></tr>)}</tbody></table></div>
          {saved.total_rows > saved.rows.length && <p>Showing a subset of {saved.total_rows} saved rows. Full coordinates remain in the alignment downloads.</p>}
        </details> : <p className="muted">Contig/reference coordinates: not recorded in this origin summary.</p>}
      </li>;
    })}</ul>}
  </div>;
}
