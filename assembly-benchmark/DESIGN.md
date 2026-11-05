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

Individual results lead with the endpoint verdict and required molecule names.
Show the saved exact-copy assessment beside total aligned reference coverage;
coverage bars do not depict genomic coordinates. Keep chromosomes outside a
plasmid endpoint as folded supporting context. State an unresolved software cause
plainly on failures, without implying that successful runs need a failure cause.
Run metadata and the original assessment remain available in disclosures.
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
stable by catalogue accession across scenarios. Graph origin strips use only
saved exact-contig matches joined through explicit GFA paths in a complete final
graph bound to the scored assembly. Multiple reference associations and missing
evidence stay grey. The selected segment exposes its exact-match/path evidence.
These are whole-segment path associations, not measured internal alignment
boundaries. The illustrative mixed-origin mock-up is not published as evidence.

Result pages show only saved alignment plots supplied by the backend bundle.
Local file-upload previews do not belong on benchmark result pages. Missing
coordinate evidence remains explicit; synthetic viewer tests are not results.

## Truthful interface

Queued, running, invalid and failed executions remain distinct from scientific
pass/fail. Summary pages show the table and colour key without a counting-rules
block or repeated site footer. Source cohort metadata remains in the downloads.
Past batch results remain accessible without implying that pending runs finished.
