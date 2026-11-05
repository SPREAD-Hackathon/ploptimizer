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

The graph section pairs expected reference molecules with the recorded GFA.
Reference circles/lines use declared topology and labelled lengths; their sizes
are schematic. Plassembler's final target contains plasmids only. The observed
graph retains source segments and orientations, with draggable force-layout
positions for small graphs and a complete grid fallback for large graphs.
Reference schematics do not introduce a topology score or assign graph segments
to reference molecules.

The NUCmer disclosure explicitly states that benchmark coordinates are not
collected. Its optional local coordinate preview is labelled separately from
benchmark evidence. Synthetic viewer tests must never appear as benchmark plots.

## Truthful interface

Queued, running, invalid and failed executions remain distinct from scientific
pass/fail. Summary pages show the table and colour key without a counting-rules
block or repeated site footer. Source cohort metadata remains in the downloads.
Past batch results remain accessible without implying that pending runs finished.
