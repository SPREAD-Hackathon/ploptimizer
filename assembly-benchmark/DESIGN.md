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

The assembler/scenario matrix is the main content. Category and species filters
update visible counts and tool totals. Use semantic table headers, visible status
text and linked evidence. Prose, navigation and controls fit phone widths; the
matrix scrolls within its labelled region. Shared mobile navigation appears
below 1050 px. Scenario data remains readable if JavaScript is unavailable.

## Truthful interface

Queued, running, invalid and failed executions remain distinct from scientific
pass/fail. The footer uses shared footer styles with accurate BMRC wording; the
package's browser-processing/WASM claim would be incorrect for this platform.
Past batch results remain accessible without implying that pending runs finished.
