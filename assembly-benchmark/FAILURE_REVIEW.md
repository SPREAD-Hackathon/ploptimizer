# Provisional failure review

Reviewed 4 November 2026 at 20:02 UTC. This is an inspection of individual
completed runs, not a tool ranking. Strict scores remain unchanged.

**Controlled follow-up:** Flye's initial read exclusion and Raven's polishing-stage
sequence loss now have causal evidence. Read the [Flye review](FLYE_HYPOTHESES.md)
and [Raven review](RAVEN_CAUSE_REVIEW.md) for the interventions and remaining limits.

The local audit contained 44 scored executions out of 128 in S1/S2 batch
`20261104T190455`: 25 strict passes and 19 strict failures, with four running and
80 pending. The interim alignment job supplied 43 completed diagnostics. Some
assemblies finished after that diagnostic traversal; later results therefore
need their own diagnostic pass. The S4 and S3 batches were still queued. The
older pilot (`20261104T183058`) has four submitted executions: one strict pass
and three strict failures. Its other 12 snapshot cells were never submitted and
must not enter the pilot denominator.

## A strict failure can contain almost the entire plasmid

The pilot Raven output for W/pRK2 is a concrete example:

- Truth pRK2 (`NC_017662.1`) is 5,360 bp; contig `Utg2196` is 5,355 bp.
- The retained PAF alignment reports 5,200 aligned reference bases: **97.015%**
  reference coverage and **99.904%** alignment identity. Its CIGAR is
  `3106M5D2094M`, from query `[0,5200)` to reference `[155,5360)`.
- This does **not** establish that 160 bp are absent. Direct sequence equality,
  using the archived assembly and truth files with matching execution hashes,
  confirms that the unaligned 155 bp query suffix equals reference `[0,155)`.
  That suffix crosses the reference's arbitrary circular coordinate origin.
- The whole query equals
  `reference[155:3261] + reference[3266:] + reference[:155]`.
  Thus this contig can be represented as the rotated reference with a **5 bp
  deletion**, not a 160 bp loss. Deletion coordinates are zero-based, half-open;
  this representation does not establish a unique breakpoint in repetitive
  sequence. The 155 bp origin segment was present but omitted by this mapping.

The strict failure is correct: rotation/reverse complement cannot repair the
five-base length difference. The approximate 97% recovery figure understates
sequence representation in this example because the mapper missed a short
origin split. Do not silently change the archived diagnostic or treat aligned
reference fraction as an exhaustive deletion measurement.

The input contained 31 pRK2 reads, achieved depth 30.411× and 100% reference
breadth. Missing input reads are therefore not the explanation for this case.
At the initial review, these observations did not identify the causal stage.
The controlled follow-up below now attributes the reproduced loss to polishing.

The same distinction is visible in the expanded batch's Raven outputs for
SE11/pSE11-1, pSE11-3 and pSE11-4. Their retained alignments cover respectively
100,020/100,021, 60,549/60,555 and 6,926/6,929 reference bases; the PAF CIGARs
contain 1 bp, 6 bp and 3 bp deletions. These are near-complete, high-identity
sequence recoveries that still fail the exact-molecule endpoint. They should
not be described as complete plasmid losses. This is alignment evidence, not
an investigation of each assembler's internal cause.

## Different failures need different descriptions

For the pilot's standalone Flye and Flye uneven-coverage outputs, the retained
PAF contains chromosome mappings and no supported pRK2 mapping; each final
assembly contains only one chromosome contig. In expanded S1 cases, both modes
also lack a supported pRK2 mapping when W's native two-plasmid complement is
provided, while pRK1 has full aligned reference coverage. These observations
support “no dedicated exact pRK2 recovered; no supported pRK2 alignment under
this policy”, rather than the Raven example's small sequence discrepancy.

A second small-plasmid example is SE11/pSE11-5 (`NC_011408.1`, 5,366 bp): both
Flye modes have no supported plasmid alignment in the inspected outputs. Its
input had 31 plasmid reads, 30.220× achieved depth and 100% breadth. This is
another valid-input failure example, not evidence that every small plasmid or
both species behave alike. Raven's corresponding contig aligns 5,361/5,366 bp,
which again distinguishes near-complete recovery from no supported alignment.

Plassembler's pilot final plasmid FASTA contains an exact pRK2 molecule and
passes the strict endpoint; its two origin-split PAF records jointly cover all
5,360 bp at identity 1. This is a useful positive cross-check for the evaluator
and mapping convention. Its initial Flye assembly remains separate paired
evidence. One pilot success does not establish superiority across the panel.

Chromosome-only controls use a different endpoint. For example, the expanded
SE11 Flye uneven-coverage control reports three chromosome contigs and fails;
this is not a plasmid loss. Keep those controls distinct from plasmid recovery
summaries.

## Limits and next interpretation steps

Results are incomplete and selected by job completion order. Species, plasmid
size, count, depth and execution time are confounded in a partial table. Compare
configurations on completed matched scenarios before drawing overall conclusions;
keep queued, failed jobs, diagnostic errors and scientific failures separate.

The diagnostic filters and circular-origin limitations are recorded in
[RECOVERY_DIAGNOSTICS.md](RECOVERY_DIAGNOSTICS.md). No supported alignment is not
proof that every plasmid-derived base is absent; an unflagged output is not proof
of structural correctness. The 95% diagnostic flag threshold is not a tolerant
pass criterion. Circularity, physical topology, realistic-error performance,
real-data performance and determinism cannot be concluded from these S1 examples.

The useful next summary separates exact recovery, high-coverage sequence
inaccuracy, no supported mapping and candidate structural problems. It should
retain the measured fractions and reference lengths, rather than replace the
strict endpoint with a post-hoc threshold selected from these results.

## Reproduce the audit

From `assembly-benchmark/`:

```sh
python3 scripts/review_results.py > .cache/failure-review.json
python3 scripts/review_results.py --batch 20261104T183058 --verify-pilot-remotely
python3 -m unittest discover -s tests -p test_review_results.py -v
```

The first command only reads local snapshots, submitted task lists, execution
records, accounting and existing diagnostics/PAF. It never runs a mapper. The
optional SSH check reads existing archived sequence files through the ignored
local cluster configuration; it verifies their full-file hashes before testing
the specific sequence equality above. It emits lengths, hashes and boolean
checks, not nucleotide sequences. The `.cache/` directory must exist before
redirecting output there. A new audit reflects newer collected records, so its
counts can differ from this dated review.

Evidence paths are under `runs/BATCH/results/SCENARIO/TOOL/`: `execution.json`,
`diagnostics.json` and `alignment.paf`. The pilot Raven PAF SHA256 is
`290397f201bb6a1e00d96fe750379ee59e7dcd1d894eea2ce5494db909cb71b9`.
The verified assembly-file SHA256 is
`57106e2a2d25c7e0e6358ab3c7b5cffd04ecc4d1a01e6b2ea429d764a13d4ad1`;
the corresponding truth-file SHA256 is
`2c1270532b4c5acf9b8cab877fd6a0c3f949f579e2ceae2e160face2811a189f`.
These large run artefacts stay on BMRC; the public snapshots retain small
execution/diagnostic evidence. The audit records local source-file hashes and
checks diagnostic execution/PAF hashes when those fields are available.

## Follow-up: a confirmed Flye input-filter mechanism

The initial no-mapping description now has a source- and runtime-backed cause
for the pilot Flye cases. Their automatic minimum overlap was 6,000 bp, and the
initial assembly loader excludes reads at or below that length. All 31 pRK2
reads are 3,463–5,360 bp. None entered the initial assembly container. The sum of
retained read bases exactly matches the recorded index total, 132,974,713 bp.
See [the Flye cause review](FLYE_HYPOTHESES.md) for evidence and the controlled
lower-threshold test. This identifies initial read exclusion, not a guarantee
that every downstream graph/consensus issue is resolved by changing one flag.

For Raven, controlled checkpoint-clone tests now reproduce the full historical
output byte for byte: zero polishing rounds give the exact plasmid; one round
loses four bases; two rounds reproduce the five-base loss. Zero-round resume
controls exclude serialization as the explanation. Polishing is therefore the
causal stage in this reproduced case. The specific Racon end-cropping branch is
still a hypothesis awaiting direct intervention or tracing. The [Raven cause
review](RAVEN_CAUSE_REVIEW.md) records source links and sequence checks. Future
runs also isolate checkpoint files, correcting a provenance defect without
claiming prior non-resume assemblies consumed shared checkpoints.
