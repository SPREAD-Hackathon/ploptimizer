import React, { useId, useMemo, useRef, useState } from 'react';
import { Alert, FileUpload, StatusBadge } from '@genomicx/ui';
import './graph.css';

export const GRAPH_LIMITS = { segments: 5000, links: 5000, bytes: 20 * 1024 * 1024 };

// Local inspection deliberately retains topology metadata only, never segment bases.
export function parseLocalGfa(text, source = {}) {
  if (/[^\x00-\x7f]/.test(text)) throw Error("GFA1 metadata must contain ASCII only.");
  const nodes = [], edges = [], paths = [], seen = new Set(), pathNames = new Set(), warnings = new Set();
  let pathSteps = 0;
  const validId = id => Boolean(id && id.length <= 256 && !/^[*=]|\s|[\x00-\x20]|\+,|-,/.test(id));
  for (const [index, line] of text.split(/\r?\n/).entries()) {
    if (!line || line.startsWith('#')) continue;
    const fields = line.split('\t'), type = fields[0];
    if (type === 'H') {
      if (fields.some(value => /^VN:Z:2/.test(value))) throw Error('GFA2 is not supported by this local inspector. Use a GFA1 file.');
    } else if (type === 'S') {
      const id = fields[1], sequence = fields[2];
      if (!validId(id) || seen.has(id) || pathNames.has(id) || !sequence) throw Error(`Invalid or duplicate segment on line ${index + 1}.`);
      if (sequence !== '*' && !/^[A-Za-z=.]+$/.test(sequence)) throw Error(`Unsupported GFA1 segment on line ${index + 1}.`);
      const lengthTag = fields.slice(3).find(value => /^LN:i:\d+$/.test(value));
      const taggedLength = lengthTag ? Number(lengthTag.slice(5)) : null;
      if (taggedLength !== null && (!Number.isSafeInteger(taggedLength) || taggedLength < 0)) throw Error(`Unsupported LN length on line ${index + 1}.`);
      const length = sequence === '*' ? taggedLength : sequence.length;
      if (taggedLength !== null && sequence !== '*' && taggedLength !== length) throw Error(`Sequence and LN length disagree on line ${index + 1}.`);
      const coverage = Object.fromEntries(fields.slice(3).filter(value => /^(?:dp|DP|KC|RC):[if]:/.test(value)).map(value => [value.slice(0, 2), value.split(':').slice(2).join(':')]));
      nodes.push({ id, length_bp: length, reported_coverage_tags: coverage }); seen.add(id);
    } else if (type === 'L') {
      if (fields.length < 6 || !validId(fields[1]) || !validId(fields[3]) || !['+', '-'].includes(fields[2]) || !['+', '-'].includes(fields[4]) || !(fields[5] === '*' || /^(?:[0-9]+[MIDNSHPX=])+$/.test(fields[5]))) throw Error(`Invalid link on line ${index + 1}.`);
      edges.push({ source: fields[1], source_orientation: fields[2], target: fields[3], target_orientation: fields[4], overlap: fields[5], is_self_link: fields[1] === fields[3] });
    } else if (type === 'P') {
      if (!validId(fields[1]) || !fields[2] || fields[2] === "*" || fields[2].includes(";") || fields.length < 4 || seen.has(fields[1]) || pathNames.has(fields[1])) throw Error(`Invalid or unsupported path on line ${index + 1}.`);
      if (paths.length >= 1000 || fields[2].length > 50_000 * 257) throw Error("Path data exceed the local inspection limit; nothing was partially displayed.");
      const steps = fields[2].split(',').map(step => {
        if (++pathSteps > 50_000) throw Error("Path steps exceed the local inspection limit; nothing was partially displayed.");
        if (!/[+-]$/.test(step)) throw Error(`Unsupported path step on line ${index + 1}.`);
        return { segment: step.slice(0, -1), orientation: step.slice(-1) };
      });
      if (fields[3] !== '*' && (fields[3].split(',').length !== steps.length - 1 || fields[3].split(',').some(value => !/^(?:[0-9]+[MIDNSHPX=])+$/.test(value)))) throw Error(`Invalid path overlap list on line ${index + 1}.`);
      pathNames.add(fields[1]);
      paths.push({ id: fields[1], steps, overlaps: fields[3] ?? '*' });
    } else warnings.add(`Record type ${type || '(empty)'} is not drawn by this inspector.`);
    if (nodes.length > GRAPH_LIMITS.segments || edges.length > GRAPH_LIMITS.links) throw Error(`This inspector supports at most ${GRAPH_LIMITS.segments} segments and ${GRAPH_LIMITS.links} links. The file was not partially displayed.`);
  }
  if (!nodes.length) throw Error('No GFA1 segment records were found. No graph is displayed.');
  if (edges.some(edge => !seen.has(edge.source) || !seen.has(edge.target)) || paths.some(path => path.steps.some(step => !seen.has(step.segment)))) throw Error('A link or path refers to an unknown segment. No graph is displayed.');
  return { status: 'available', nodes, edges, paths, self_loop_segment_ids: [...new Set(edges.filter(edge => edge.is_self_link).map(edge => edge.source))], complete: !warnings.size,
    warnings: [...warnings], source: { ...source, kind: 'gfa', role: 'local inspection only; not benchmark provenance' } };
}

export function schematicLayout(nodes) {
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  return { width: Math.max(400, columns * 180 + 80), height: Math.max(300, Math.ceil(nodes.length / columns) * 140 + 80),
    positions: new Map(nodes.map((node, index) => [node.id, { x: 110 + index % columns * 180, y: 90 + Math.floor(index / columns) * 140 }])) };
}

export function coverageDescription(tags) {
  if (Array.isArray(tags)) return tags.map(tag => `${tag.tag}=${tag.value} (${String(tag.meaning ?? 'reported tag').replaceAll('_', ' ')})`).join(', ');
  return Object.entries(tags ?? {}).map(([key, value]) => `${key}=${value}`).join(', ');
}

function edgePath(edge, positions) {
  const start = positions.get(edge.source), end = positions.get(edge.target);
  if (!start || !end) return '';
  if (edge.source === edge.target) return `M ${start.x - 30} ${start.y - 32} C ${start.x - 110} ${start.y - 105}, ${start.x + 110} ${start.y - 105}, ${start.x + 30} ${start.y - 32}`;
  const dx = end.x - start.x, dy = end.y - start.y;
  const boundary = 1 / Math.max(Math.abs(dx) / 68, Math.abs(dy) / 32);
  return `M ${start.x + dx * boundary} ${start.y + dy * boundary} L ${end.x - dx * boundary} ${end.y - dy * boundary}`;
}

export function GraphViewer({ artifact = {} }) {
  const [local, setLocal] = useState(null), [files, setFiles] = useState([]), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(''), [view, setView] = useState(null), [showLabels, setShowLabels] = useState(true);
  const svg = useRef(null), pan = useRef(null), marker = useId().replace(/:/g, '');
  const graph = local ?? artifact.graph ?? {}, nodes = graph.nodes ?? [], edges = graph.edges ?? [];
  const layout = useMemo(() => schematicLayout(nodes), [nodes]);
  const activeView = view ?? { x: 0, y: 0, width: layout.width, height: layout.height };
  const selectedNode = nodes.find(node => node.id === selected);
  const tooLarge = nodes.length > GRAPH_LIMITS.segments || edges.length > GRAPH_LIMITS.links;
  const ready = graph.status === 'available' && nodes.length > 0 && !tooLarge;
  const related = edges.filter(edge => edge.source === selected || edge.target === selected);
  function reset() { setView(null); setSelected(''); }
  function zoom(factor) {
    const width = Math.min(layout.width * 20, Math.max(80, activeView.width * factor)), ratio = width / activeView.width;
    setView({ x: activeView.x + activeView.width * (1 - ratio) / 2, y: activeView.y + activeView.height * (1 - ratio) / 2, width, height: activeView.height * ratio });
  }
  function select(id) {
    setSelected(id);
    if (!id) { setView(null); return; }
    const point = layout.positions.get(id);
    if (point) {
      const width = Math.min(560, layout.width, Math.max(240, svg.current?.getBoundingClientRect().width ?? 560));
      const height = width * 360 / 560;
      setView({ x: point.x - width / 2, y: point.y - height / 2, width, height });
    }
  }
  async function openFiles(next) {
    setFiles(next); setError(''); setLocal(null);
    if (!next.length) { setLocal(null); reset(); return; }
    const file = next[0];
    if (file.size > GRAPH_LIMITS.bytes) { setError('The local file exceeds 20 MiB. Nothing was loaded.'); return; }
    setLoading(true);
    try {
      const bytes = await file.arrayBuffer();
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2, '0')).join('');
      setLocal(parseLocalGfa(new TextDecoder('utf-8', { fatal: true }).decode(bytes), { filename: file.name, file_sha256: hash })); reset();
    } catch (failure) { setLocal(null); setError(failure.message); }
    finally { setLoading(false); }
  }
  function pointerDown(event) {
    if (event.button !== 0 || event.target.closest('[data-graph-node]')) return;
    pan.current = { clientX: event.clientX, clientY: event.clientY, view: activeView };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event) {
    if (!pan.current) return;
    const bounds = svg.current.getBoundingClientRect(), start = pan.current;
    if (!bounds.width || !bounds.height) return;
    setView({ ...start.view, x: start.view.x - (event.clientX - start.clientX) * start.view.width / bounds.width, y: start.view.y - (event.clientY - start.clientY) * start.view.height / bounds.height });
  }
  function keyboard(event) {
    if (['+', '='].includes(event.key)) { event.preventDefault(); zoom(.8); }
    if (event.key === '-') { event.preventDefault(); zoom(1.25); }
    const shifts = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (shifts[event.key]) { event.preventDefault(); const [x, y] = shifts[event.key]; setView({ ...activeView, x: activeView.x + x * activeView.width / 10, y: activeView.y + y * activeView.height / 10 }); }
  }
  return <div className="assembly-graph" role="region" aria-label="Assembly graph viewer">
    {local ? <Alert variant="warning">Local inspection: {graph.source?.filename}. This file is not attached to the benchmark result. Its contents stay in this browser.</Alert>
      : !ready && <Alert variant="info">{tooLarge ? 'This graph exceeds the interactive display limit; no partial graph is drawn.' : graph.status === 'available' && !nodes.length ? 'The collected GFA contains no segment records. This is an empty recorded graph, not missing graph data.' : artifact.reason || graph.reason || 'No assembly graph was collected for this result. Missing graph data do not imply a graph with no links or a linear molecule.'}</Alert>}
    {local && <button className="gx-btn gx-btn-secondary gx-btn-sm" onClick={() => { setLocal(null); setFiles([]); setError(''); reset(); }}>Return to benchmark graph</button>}
    {error && <Alert variant="error">{error}</Alert>}
    {loading && <p role="status">Reading the local GFA…</p>}
    {ready && <>
      <p><StatusBadge variant="info">{local ? 'Local file' : 'Recorded GFA'}</StatusBadge> {nodes.length.toLocaleString()} segments · {edges.length.toLocaleString()} link records. Source: {graph.source?.filename ?? 'not recorded'}; role: {graph.source?.role ?? 'not recorded'}.</p>
      {graph.source?.file_sha256 && <details><summary>Graph source SHA-256</summary><code className="checksum">{graph.source.file_sha256}</code></details>}
      {graph.complete === false && <Alert variant="warning">The source graph includes unsupported or omitted records. This view is not a complete representation of the source file.</Alert>}
      {graph.warnings?.length > 0 && <details><summary>Graph parsing notes</summary><ul>{graph.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
      <div className="graph-controls">
        <button className="gx-btn gx-btn-secondary gx-btn-sm" onClick={() => zoom(.8)}>Zoom in</button>
        <button className="gx-btn gx-btn-secondary gx-btn-sm" onClick={() => zoom(1.25)}>Zoom out</button>
        <button className="gx-btn gx-btn-secondary gx-btn-sm" onClick={reset}>Fit graph</button>
        <label>Select segment<select className="gx-input" value={selected} onChange={event => select(event.target.value)}><option value="">Whole graph</option>{nodes.map(node => <option key={node.id} value={node.id}>{node.id}</option>)}</select></label>
        <label className="graph-checkbox"><input type="checkbox" checked={showLabels} onChange={event => setShowLabels(event.target.checked)} /> Show labels</label>
      </div>
      <p className="muted">Schematic layout; node positions and widths are not genomic coordinates or sequence scale. Drag the background to pan. Use zoom buttons, or focus the graph and use arrow keys and +/−. Arrows follow GFA link records; orientations are shown in the selected segment’s links.</p>
      <svg ref={svg} className="graph-canvas" viewBox={`${activeView.x} ${activeView.y} ${activeView.width} ${activeView.height}`} role="group" aria-label="Schematic GFA topology" tabIndex="0" onKeyDown={keyboard} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={() => { pan.current = null; }} onPointerCancel={() => { pan.current = null; }}>
        <defs><marker id={marker} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="currentColor" /></marker></defs>
        {edges.map((edge, index) => <path key={index} className={`graph-edge ${selected && (edge.source === selected || edge.target === selected) ? 'selected' : ''}`} d={edgePath(edge, layout.positions)} markerEnd={`url(#${marker})`}><title>{`${edge.source}${edge.source_orientation} → ${edge.target}${edge.target_orientation}; overlap ${edge.overlap}`}</title></path>)}
        {nodes.map(node => { const point = layout.positions.get(node.id); return <g key={node.id} className={`graph-node ${node.id === selected ? 'selected' : ''}`} data-graph-node={node.id} role="button" tabIndex="0" aria-label={`Segment ${node.id}; ${node.length_bp == null ? 'length unknown' : `${node.length_bp} bases`}`} aria-pressed={node.id === selected} onClick={() => select(node.id)} onKeyDown={event => { if (['Enter', ' '].includes(event.key)) { event.preventDefault(); event.stopPropagation(); select(node.id); } }}>
          <rect x={point.x - 58} y={point.y - 22} width="116" height="44" rx="4" />
          {showLabels && <text x={point.x} y={point.y + 5} textAnchor="middle">{node.id.length > 16 ? node.id.slice(0, 14) + '…' : node.id}</text>}
          <title>{`${node.id}; ${node.length_bp == null ? 'length unknown' : node.length_bp + ' bp'}`}</title>
        </g>; })}
      </svg>
      <p className="muted">A self-link or closed GFA path is graph evidence, not confirmation of a physical circular molecule. {local ? "The benchmark contig claims above do not apply to this local file." : "Assembler-reported circularity and its source are listed separately on this result page."}</p>
      {selectedNode && <div className="graph-selection" aria-live="polite"><h3>Segment {selectedNode.id}</h3><p>Length: {selectedNode.length_bp == null ? 'not reported' : `${selectedNode.length_bp.toLocaleString()} bp`}. Recorded GFA coverage/count tags: {coverageDescription(selectedNode.reported_coverage_tags) || 'none collected'}.</p>
        <p>{graph.self_loop_segment_ids?.includes(selectedNode.id) ? 'An explicit GFA self-link was recorded for this segment.' : 'No explicit GFA self-link was recorded for this segment.'} This does not validate molecular topology.</p>
        <details open><summary>Incident link records ({related.length})</summary>{related.length ? <ul>{related.map((edge, index) => <li key={index}><code>{edge.source}{edge.source_orientation} → {edge.target}{edge.target_orientation}</code>; overlap {edge.overlap}</li>)}</ul> : <p>No incident link records.</p>}</details>
      </div>}
      {graph.paths?.length > 0 && <details><summary>Recorded GFA paths ({graph.paths.length})</summary><ul>{graph.paths.map((path, index) => <li key={index}><strong>{path.id}</strong>: <code>{path.steps.map(step => step.segment + step.orientation).join(', ')}</code></li>)}</ul></details>}
    </>}
    <details className="graph-local"><summary>Inspect a local GFA separately</summary><p>This optional inspection does not change the benchmark result or its evidence. The selected file is processed only in this browser; it is never uploaded.</p><FileUpload files={files} onFilesChange={openFiles} multiple={false} accept=".gfa,.gfa1,text/plain" label="Choose a local GFA1 file" hint="Up to 20 MiB. Segment bases are not displayed or retained in the parsed graph." disabled={loading} /></details>
  </div>;
}
