# Assembly benchmark

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

User-approved static results website hosted on Vercel. Actual @genomicx/ui components supply navigation, themes and status badges. Python generates pages
from benchmark records. Python also automates BMRC Slurm jobs; Pixi provides
isolated Linux software environments.

## Users

Researchers comparing long-read assembly software across published simulated
datasets and controlled plasmid scenarios.

## Product Purpose

Show broad assembly completion, sequence accuracy and resource use alongside
exact plasmid recovery in controlled scenarios. Let readers inspect the inputs,
methods and recorded evidence behind each outcome.

## Operating Context

The homepage leads with a separate general-performance completion summary for
50 published datasets and four primary workflows (200 expected executions),
followed by the compact diagnostic scenario-family-by-assembler matrix with
exact pass/fail counts. The two tracks retain separate denominators and scoring
endpoints. Unrecorded broad results remain awaiting results; diagnostic unscored
outcomes remain separate. Diagnostic family rows aggregate the explicit
active release cohort; historical pilots are excluded. A family page contains
all genome, tool/version and execution summaries. Each record links to its
individual result with explanations, measurements, circularity and graph.
Compute runs on Cluster3/BMRC via Slurm; the website consumes saved records and
explicit execution state. General-performance datasets, plots and methods have
separate pages; diagnostic plots remain accessible from Scenarios. See
[BROAD_PERFORMANCE.md](BROAD_PERFORMANCE.md) for this ordinary extension's scope.

## Capabilities and Constraints

All source, configuration, environments, generated data and website work must
remain within assembly-benchmark/. Keep the rest of the repository clear for
other work. The diagnostic baseline uses error-free reads and exact plasmid
recovery using
Flye (default), Flye (`--meta`), Raven and Plassembler long-read-only mode. Default Flye is primary for the clean baseline; `--meta` is an explicit parameter comparison.
The separate general-performance panel reuses published Badread read files
byte-for-byte, rather than generating new reads. Its alignment-based completion
endpoint does not replace the diagnostic exact-copy endpoint.

## Evidence on Hand

Pinned RefSeq inventories and metadata exist in references/. All 19 records in the five preferred references passed sequence-integrity checks; independent biological evidence review remains separate. No assembler result is implied by
the design or by a generated website. Missing, running, invalid and failed jobs
must remain distinct from completed scientific pass/fail results.

## Product Principles

- Lead with the general-performance summary, then the diagnostic family-level count matrix; keep diagnostic prose out of matrix cells.
- Keep broad completion and diagnostic exact-copy results separate in summaries, plots and methods.
- Use three levels for diagnostics: family overview, genome/tool summaries, individual execution evidence.
- Keep every outcome traceable to its dataset or scenario and execution record.
- Explain the scoring endpoint and its limits.
- Never fill missing results with demonstrations or assumed passes.
