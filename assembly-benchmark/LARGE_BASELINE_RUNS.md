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
arrays use a concurrency cap of 1,000, allowing Slurm to allocate resources.
Future assembly batches are not artificially ordered behind earlier assemblies;
only actual input/environment dependencies remain. S3's original cap was four,
then eight, and was raised to 1,000 at the user’s explicit instruction. Per-run
CPU reservations, thread counts, inputs and modes are unchanged. See
`evidence/large-baseline-v3/scheduler-policy-1000.json`.
No assembler failures are silently retried with changed settings.

Each batch has a dependency-linked evidence job after assembly/report completion.
It collects saved GFA metadata, contig length inventories and graph identities,
runs supplementary minimap2 alignments, freezes a source snapshot, and computes
NUCmer coordinates using the existing locked MUMmer environment. Scores remain
unchanged. A failed coordinate comparison prevents an evidence-complete status.
The controller collects small metadata and coordinates; sequence files and delta
files remain on BMRC. Source snapshots are copied exactly to preserve comparison
manifest hashes.

All 168 executions and their evidence calculations have now completed. The three
frozen snapshots are admitted to the overview cohort after the execution and
provenance checks. Final publication status is tracked in `CURRENT_RELEASE.json`;
completed calculations alone do not establish a verified live deployment.

The first submission attempt was cancelled before any assembly started:
preparation tests caught Python 3.12-only f-string syntax in the reporting layer
under pinned Python 3.11. The compatibility fix was checked with the actual
cluster interpreter (363 tests, 11 optional skips), and a Python 3.11 grammar
regression check was added. Archived job IDs and Slurm accounting with unset
assembly start times are retained in `evidence/large-baseline-v3/attempt-1*`.
Replacement batches use fresh directories; there are no duplicate assembly runs.

## Completed suite results

- S1: 2 exact passes / 6 exact failures, 8 executions.
- S2: 30 exact passes / 10 exact failures, 40 executions.
- S3: 40 exact passes / 80 exact failures, 120 executions; reference recovery is
  separate from repeat agreement.
- Total: 72 exact passes / 96 exact failures; no unscored execution errors.
  All 168 mappings, saved graphs, length inventories and NUCmer comparisons
  completed. No assembly retries or changed scoring parameters were introduced.

All S3 groups have identical recorded input hashes. Normalised sequence signatures
agree in 23/24 within-mode/thread groups and 9/12 across-thread groups. Deterministic
Flye and Flye (`--meta`) modes agree in all 8 within-setting and 4 across-thread
groups. Byte equality and strict biological signatures are reported separately.
See `evidence/large-baseline-v3/s3-repeatability-audit.json` for exact mode/thread
identities and denominators. Non-exact contigs retain their ends during
normalisation, so differing signatures do not by themselves locate a sequence
change or establish a software mechanism.

The report consumes recorded NUCmer coordinate plots and retains separate saved
PAF evidence for mismatch counts. Repeated-run coordinate imports verify the
producer's comparison output path and the separate original `repeats/` execution
metadata path. The readiness gate distinguishes default and deterministic modes;
the source snapshots, reads, assemblies and scientific scores remain unchanged.
