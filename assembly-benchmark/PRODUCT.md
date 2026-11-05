# Assembly benchmark

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

User-approved static results website hosted on Vercel. Actual @genomicx/ui components supply navigation, themes and status badges. Python generates pages
from benchmark records. Python also automates BMRC Slurm jobs; Pixi provides
isolated Linux software environments.

## Users

Researchers comparing long-read assembly software on controlled plasmid scenarios.

## Product Purpose

Show which assembler configurations recover plasmids correctly, explain each
scenario, and let readers inspect the evidence behind a pass or fail.

## Operating Context

The homepage is a compact scenario-family-by-assembler matrix with exact pass/fail
counts. Unscored outcomes remain separate. Family rows aggregate the explicit
active release cohort; historical pilots are excluded. A family page contains
all genome, tool/version and execution summaries. Each record links to its
individual result with explanations, measurements, circularity and graph.
Compute runs on Cluster3/BMRC via Slurm; the website consumes completed records.

## Capabilities and Constraints

All source, configuration, environments, generated data and website work must
remain within assembly-benchmark/. Keep the rest of the repository clear for
other work. First implement error-free reads and exact plasmid recovery using
Flye, its uneven-coverage mode, Raven and Plassembler long-read-only mode.
Broader read-error and scoring models follow later.

## Evidence on Hand

Pinned RefSeq inventories and metadata exist in references/. All 19 records in the five preferred references passed sequence-integrity checks; independent biological evidence review remains separate. No assembler result is implied by
the design or by a generated website. Missing, running, invalid and failed jobs
must remain distinct from completed scientific pass/fail results.

## Product Principles

- Make the family-level count matrix the homepage content; keep diagnostic prose out of its cells.
- Use three levels: family overview, genome/tool summaries, individual execution evidence.
- Keep every outcome traceable to its scenario and execution record.
- Explain the scoring endpoint and its limits.
- Never fill missing results with demonstrations or assumed passes.
