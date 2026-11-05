---
name: Ploptimizer assembly benchmark
description: GenomicX result matrix with traceable scientific evidence.
---

## Authority

Use the actual `@genomicx/ui` 0.10.1 package. Import its tokens and component
styles; use native NavBar, theme controls and StatusBadge. Shared IBM Plex fonts
are self-hosted with the compiled package assets. Report-specific layout uses
GenomicX colour, typography and spacing tokens in both themes.

## Layout and semantics

The homepage is a compact scenario-family/assembler matrix of exact pass/fail
counts. Blue/orange tones supplement explicit labels, with unscored outcomes
separate. The table leads without lengthy interpretation or per-record diagnoses.
Family pages list genome/tool/version records linking to individual evidence and
graphs. Existing genome-case URLs remain concise input/result summaries. Use semantic table headers, visible status
text and linked evidence. Prose, navigation and controls fit phone widths; the
matrix scrolls within its labelled region. Shared mobile navigation appears
below 1050 px. Scenario data remains readable if JavaScript is unavailable.
The top-left Scenario family header stays pinned with its row labels while assembler columns scroll.

Individual-run and case-run lists, repeatability groups, and long contig/length
inventories progressively add table navigation. Keep the headline count matrix
unchanged. Place labelled search and relevant distinct-value filters above each
table, outside its horizontal scrolling region; omit filters with only one
available value. Contig and length inventories gain these controls at eight rows.
Use shared GenomicX inputs and a secondary Reset button, wrapping controls on
phones with search on its own row. Preserve the semantic table and result links
when JavaScript is unavailable.

Search all row text case-insensitively, requiring every search term; combine it
with exact-value filters. Sort data columns through labelled header buttons with
visible direction and accessible sort state. Use natural/numeric ordering,
preserve original order for ties, and keep missing values last in both directions.
Show a live visible/total row count and a useful no-match message. Reset clears
search, filters and sorting, restoring source order. Counts describe the visible
table only; filtering never changes the benchmark's scientific totals.

Individual results lead with the endpoint verdict and required molecule names.
Show the saved exact-copy assessment beside total aligned reference coverage;
coverage bars do not depict genomic coordinates. Keep chromosomes outside a
plasmid endpoint as folded supporting context. State an unresolved software cause
plainly on failures, without implying that successful runs need a failure cause.
Run metadata and the original assessment remain available in disclosures.

For failed results, place a compact “Recorded difference” fact list near the
verdict using semantic labels and values, with stacked pairs on phones. Show
only saved review facts bound to the same scenario, tool, scientific status,
assembly checksum and truth checksum. Include recorded excess, reference/output
lengths and existing intervals when available; state that coordinates are
0-based with the end excluded. Keep the source document and individual evidence
fields in a folded “Difference evidence source” disclosure. Use the existing
GenomicX typography, spacing and muted text rather than a separate card or new
visual identity. If no bound review supplies facts, say “Difference location:
not recorded in the saved evidence.” Never invent positions or infer an
assembler mechanism from a measured mismatch. Keep the unresolved internal cause
explicit and the exact-copy verdict separate from aligned coverage; presenting
these facts does not change the scientific score.

Each result also exposes its saved command and descriptions of only the flags
present in that invocation. Command links open the disclosure directly. Preserve
argument order and values, use shell-safe display quoting, and retain the public
work-directory placeholder. Never infer an invocation from a tool label.

The graph section pairs expected reference molecules with the recorded GFA.
Reference circles/lines use declared topology and labelled lengths; their sizes
are schematic. Plassembler's final target contains plasmids only. The observed
graph retains source segments and orientations, with draggable force-layout
positions for small graphs and a complete grid fallback for large graphs.
Reference schematics do not introduce a topology score. Reference colours are
stable by catalogue accession across scenarios. When validated recorded
node-to-reference intervals exist, graph origin strips show those measured
portions by default. Only explicitly supported single-reference portions use
their reference colour; ambiguous portions and gaps without support stay grey,
with distinct text explaining each state. Portion widths follow recorded node
coordinates. A strip click selects the segment and portion directly; the detailed
strip and labelled interval dropdown expose the same evidence, including tiny
portions that are difficult to target. Keep selection and keyboard focus visible.

The selected portion shows candidate references, original node/reference match
spans, strand, recorded quality, and source name/checksum. Coordinates are
0-based with the end excluded. Preserve original alignment rows even when a
display portion covers only part of a match; never interpolate reference
coordinates for display chunks. Alignment endpoints are match boundaries, not
proven biological junctions or an explanation of assembler behaviour. Evidence
tables retain contained horizontal scrolling on phones.

When interval records are absent, retain the existing whole-segment identity and
recorded contig-path association evidence, bound to the scored assembly and its
complete final graph. Path associations require saved exact-contig matches joined
through explicit GFA paths. Do not relabel path associations as
measured internal mapping. Whole-segment identity and path inference remain
visibly distinguished; ambiguous or missing associations stay grey. Frozen
results currently have no direct node interval evidence. Synthetic interval
previews and tests remain outside the deployed benchmark website.

Result pages show only saved alignment plots supplied by the backend bundle.
Local file-upload previews do not belong on benchmark result pages. Missing
coordinate evidence remains explicit; synthetic viewer tests are not results.

## Truthful interface

Queued, running, invalid and failed executions remain distinct from scientific
pass/fail. Summary pages show the table and colour key without a counting-rules
block or repeated site footer. Source cohort metadata remains in the downloads.
Past batch results remain accessible without implying that pending runs finished.
