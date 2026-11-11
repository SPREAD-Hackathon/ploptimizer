# General-performance surface

This is an ordinary extension of the incumbent GenomicX report, alongside the
controlled diagnostic suite. It preserves the shared navigation, themes,
typography, tables, controls and status semantics documented in DESIGN.md.
It does not establish a replacement visual direction.

## Track and endpoint

The frozen selection contains 50 published Wick and Holt simulated datasets:
25 genomes with plasmids and 25 without, containing 50 plasmids in total.
Published Badread read files are reused byte-for-byte, without resimulation or
reordering. The published recipe and reference metadata remain available as
provenance. Four primary workflows produce 200 expected reported executions:
Flye, Raven, Plassembler, and Miniasm + Minipolish. Raw Miniasm is an intermediate,
not a fifth workflow or an additional reported comparison.

General-performance completion uses the Wick-style longest single alignment to
a tripled reference. Contiguity is its reference span divided by the original
molecule length and may exceed 100%; a molecule is complete at contiguity of at
least 99%. A fully complete dataset has all chromosomes and plasmids complete.
Chromosome-complete results have every chromosome complete with at least one
incomplete plasmid. Identity and maximum indel are separate recorded measures,
subject to the methods page's alignment-length requirement.

This endpoint is distinct from the controlled diagnostic exact-copy assessment.
Never combine their outcome counts, denominators or plots, or describe broad
completion as exact plasmid recovery. Empty assemblies, incomplete assemblies,
non-completion and execution/assessment errors remain explicit categories.

## Surface map

| Surface | Purpose |
| --- | --- |
| `/` | General-performance completion summary above the diagnostic matrix; separate captions and counts. |
| `/performance` | Broad summary, individual recorded executions, input dataset table and folded dataset/provenance details. |
| `/aggregate` | Broad completion, accuracy and resource plots, with source tables and SVG/PNG links when measured data exist. |
| `/performance-methods` | Input provenance, completion and accuracy definitions, workflows, resource accounting and sources. |
| `/diagnostic-plots` | Existing controlled-scenario plots, linked from Scenarios. |

The generator writes static `.html` files for these routes. General-performance
links sit beside its summary, so readers can reach its methods without confusing
them with the diagnostic Methods page. The backend export supplies counts and
recorded measurements; the browser does not invent or rescore scientific data.

## Collection and publication

Batch `20261106T134511` contains 50 datasets and 200 reported workflows.
Preparation validates the published reference archive; each admitted input
releases its own assembler tasks through Slurm. Raw Miniasm is an intermediate,
not an additional reported workflow. The four primary arrays are recorded in
`evidence/broad-performance-v1/status.json`.

The frozen reporting input now accounts for all 200 outcomes and all 50 admitted
inputs, with verified execution/input and assessment/execution bindings. Completed
sequence outcomes remain separate from software/resource failures. Freezing is
not deployment: `CURRENT_RELEASE.json` identifies the actual live publication.

From this directory, collect existing small metadata and freeze the report input:

```sh
python3 scripts/broad_performance.py collect
python3 scripts/freeze_performance.py
```

The freeze excludes pending placeholders and rejects changed execution hashes,
input-binding errors, unknown slots and changed selection metadata. It retains
the source results checksum and timestamps. Export/render then consumes this
snapshot; it does not run assemblers or calculate new sequence alignments.
Workflow wall time includes input verification and exact assessment; downloads
and scheduler waiting are excluded. Peak RAM refers to the assembler process
tree. These scope labels accompany the measurements.

## Delivery and retained design

The broad website payload contains metadata, source tables and plot images;
large reads, assemblies and intermediate compute files stay outside that
payload. Preserve the compact release budget of 64 MiB and 1,500 files.
This document records a local implementation and review, not a deployment.

Source evidence: `pipeline/performance_pages.py`,
`pipeline/performance_bundle.py`, `pipeline/bundle_render.py`,
`config/performance-wick-50.json`, `website/shell.jsx` and `website/site.css`.
The shell imports actual `@genomicx/ui` tokens and components; report CSS maps
semantic colours to `--gx-*` tokens and retains the existing body and heading
scale. No new palette, type scale, component vocabulary or motion rule is
introduced here.

The supplied reviewer disposition reports no P1/P2 findings in eight homepage
and dataset screenshots at 1440/390 px in dark/light themes under
`.impeccable/review/broad/`. Aggregate and methods coverage was source review
only. A separate direction contract and QUALITYBAR card review were not supplied;
this pass is bounded to preserving the inherited system. Existing DESIGN.md
format and sidecar schema/responsive-description drift are not repaired or
promoted into new design rules by this extension.
