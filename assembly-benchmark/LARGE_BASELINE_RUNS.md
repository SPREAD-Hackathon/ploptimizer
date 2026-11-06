# Revised large-plasmid benchmark runs

The bounded replacement suite contains 168 assembly executions. Operational
state, batch identifiers and Slurm job IDs are recorded in
`evidence/large-baseline-v3/status.json`; no submission is implied by this document.

- S1: SE11 chromosome with pSE11-1/-2/-3, and MGH78578 chromosome with
  pKPN3/-4/-5. All three plasmids per input are ≥20 kb. Two inputs, four
  configurations: 8 executions.
- S2: SE11 with pSE11-1 and MGH78578 with pKPN3; relative plasmid depths
  0.8, 1, 1.2, 3 and 5. Ten inputs, four configurations: 40 executions.
- S3: the same two multiple-large-plasmid complements as S1. Frozen reads,
  five independent repeats at 1 and 4 threads; default and deterministic modes
  for both Flye configurations, default modes for Raven and Plassembler.
  120 executions. Repeatability is separate from reference recovery.

Configurations are `config/baseline-large.json`, `coverage-large.json` and
`repeatability-large.json`. The exact-read model, pinned tools and scoring remain
unchanged; the new simulation seed is 20261106. S2 uses independent per-accession
random streams: changing plasmid depth does not change chromosome sampling.
These are derived reference subsets, not complete native plasmid complements.
Old snapshots and original scientific scores remain unchanged.

## Automation

```bash
python3 scripts/large_baseline.py plan
python3 scripts/large_baseline.py submit
python3 scripts/large_baseline.py collect
```

The ignored `.cache/large-baseline-v3/checkpoint.json` prevents duplicate suite
submissions. Authentication is checked before creating runs. Partial submissions
require inspection. Every repeat has a fresh execution directory. Preparation
jobs are ordered to avoid concurrent environment installation, and assembly
arrays are ordered across batches. The initial limit was four active assembly
tasks; the S3 limit was raised to eight on 6 November following the user’s speed
request. Per-run CPU reservations, tool thread counts, inputs and modes were
unchanged. See `evidence/large-baseline-v3/scheduler-adjustment.json`.
No assembler failures are silently retried with changed settings.

Each batch has a dependency-linked evidence job after assembly/report completion.
It collects saved GFA metadata, contig length inventories and graph identities,
runs supplementary minimap2 alignments, freezes a source snapshot, and computes
NUCmer coordinates using the existing locked MUMmer environment. Scores remain
unchanged. A failed coordinate comparison prevents an evidence-complete status.
The controller collects small metadata and coordinates; sequence files and delta
files remain on BMRC. Source snapshots are copied exactly to preserve comparison
manifest hashes.

The current live report remains a verified release while jobs are pending. Add
new batches to the headline cohort only after checking their frozen snapshots,
execution outcomes and evidence; then export/render, run the release gate and
publish the compact site. Pending work must not be called complete.

The first submission attempt was cancelled before any assembly started:
preparation tests caught Python 3.12-only f-string syntax in the reporting layer
under pinned Python 3.11. The compatibility fix was checked with the actual
cluster interpreter (363 tests, 11 optional skips), and a Python 3.11 grammar
regression check was added. Archived job IDs and Slurm accounting with unset
assembly start times are retained in `evidence/large-baseline-v3/attempt-1*`.
Replacement batches use fresh directories; there are no duplicate assembly runs.
