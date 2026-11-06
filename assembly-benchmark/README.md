# Long-read plasmid assembly benchmark

**Status:** S1–S6 have implemented benchmark panels and recorded runs. S7
read-order sensitivity is implemented and all 48 executions and backend
comparisons are complete. Its [S7 report is live](https://ploptimizer-assembly-benchmark.vercel.app/scenarios/s7).
Publication evidence is tracked separately. See the [scenario status](SCENARIO_STATUS.md) for the
current distinction between implemented, executed and published work, and
[release results](RELEASE_STATUS.md) for verified production releases.
All code, configurations and reporting work stay inside this folder.

**[Live results website](https://ploptimizer-assembly-benchmark.vercel.app)**:
assembler/scenario matrix, scenario evidence and individual tool-execution pages
with reported circularity, contig measurements, interactive graph inspection and
downloadable provenance. See [graph collection](GRAPH_COLLECTION.md) for source
coverage and limits. Publication snapshots are versioned in `published/`; large
run artefacts stay on BMRC. Simulated reads are temporary working data under
the [read retention policy](READ_RETENTION.md); cleanup awaits verified restoration
and completion of every dependent job.

## Read-order comparison

[S7 · Read-order sensitivity](S7_READ_ORDER.md) is implemented in
`pipeline/read_order.py`, with executable `config/read-order.json` and the
`scripts/read_order.py` controller. Batch `20261106T134415` submits 48 executions:
original order plus three frozen shuffles, three repeats per order and four
assembler configurations. All 48 have completed, using the same complete
read-record multiset in four distinct orders. Outputs are compared independently
of reference recovery. See [S7 results](evidence/read-order-v1/RESULTS.md) and
`evidence/read-order-v1/status.json`. The [live S7 page](https://ploptimizer-assembly-benchmark.vercel.app/scenarios/s7) contains both comparison views, matrices and TSV downloads.

## Aggregate plots

[Aggregate results](https://ploptimizer-assembly-benchmark.vercel.app/aggregate)
add cohort-separated outcome composition, plasmid size/depth, mapped breadth,
recorded identity, runtime/RAM, input distributions and repeatability figures.
SVG/PNG figures and source tables are included in the backend ZIP.
See [metric definitions and the Wick comparison](AGGREGATE_PLOTS.md). Original
Wick figures are linked with attribution; their values are not our measurements.

## Rebuild reporting from frozen evidence

Use the [backend bundle workflow](RESULTS_BUNDLE.md): `benchmark.py export`
produces versioned JSON, TSV, standalone reports and any available saved-coordinate
plots without the website. `benchmark.py render` consumes that validated bundle.
Export does not rerun assemblies or sequence analyses. The website links the
complete downloadable bundle and a detailed report for each result.

## Aim

Assess whether long-read assembly tools recover the correct plasmid sequences and molecule count alongside the chromosome. Detect missing, fragmented, merged, duplicated and incorrectly circularised plasmids. Start with *Klebsiella pneumoniae* and *Escherichia coli*.

## Revised baseline

The [baseline policy](BASELINE_POLICY.md) separates ordinary recovery from small-plasmid challenges:

1. **S1:** chromosome alone, chromosome plus one plasmid ≥20 kb, or multiple plasmids all ≥20 kb.
2. **S2:** larger-plasmid complements, varying only relative coverage.
3. **S3:** repeated execution of one fixed larger-plasmid input across modes and thread settings; recovery is secondary.
4. **S4:** smaller plasmids individually and alongside larger ones.

Existing mixed-size and small-plasmid S1–S3 runs remain supplementary, with their
original references, identifiers and scores. The revised larger-plasmid suite
has completed: eight multiple-plasmid S1 executions, 40 matched-coverage S2
executions and 120 S3 repeats with mode/thread comparisons. Earlier chromosome-only
and single-plasmid controls remain available. See `evidence/large-baseline-v3/`.

## Tools and references

The initial tool panel is **Flye (default)**, **Flye (`--meta`)**, **Plassembler long-read-only mode**, and **Raven**. For the clean baseline, Flye (default) is the primary Flye configuration; `--meta` is an explicit parameter comparison, not a separate assembler. Compare Plassembler's final plasmids with its own initial Flye assembly as well as the standalone baselines. Record component versions and internal filtering; score its retained chromosome separately.

The [reference shortlist](references/README.md) contains accession versions and supporting evidence for:

- *E. coli* MG1655: chromosome-only control.
- *E. coli* W: two plasmids, approximately 5.4 and 102.5 kb.
- *E. coli* SE11: six plasmids, approximately 4.1–100 kb.
- *K. pneumoniae* Ecl8: one plasmid, approximately 204.7 kb.
- *K. pneumoniae* MGH 78578: five plasmids, approximately 3.5–175.9 kb.

All 19 sequence records in these five assemblies passed accession, length and ACGT checks for the S1/S2 run. This checks sequence integrity, not independent biological truth. Two alternatives with metadata-indicated ambiguous bases are held separately. The initial panel has no plasmids below 3,478 bp.

## Outputs and success measures

Produce one row per truth plasmid with recovered sequence fraction, identity, contig count, structural errors, duplication and topology. Report chromosome recovery, unsupported extra outputs, run failures, runtime and peak memory separately. Exact one-molecule recovery is the strict sequence endpoint; circularity needs its own assessment.

Deliver a command-line workflow, a static report and JSON/TSV exports. Keep manifests, configurations and metadata in Git; store large reads and assemblies elsewhere. A successful pilot must reproduce its inputs and scores and retain failed runs.

## Later extensions

Add biologically linear plasmids (S5), realistic nanopore errors, coverage/read-length challenges, shared repeats, filtering effects, and matched real datasets. Autocycler, Myloasm and a hybrid track can follow. The order and admission of these extensions remain design choices.

The [six decision groups](DECISIONS.md) guide the wider study; the first runnable
profile is in `config/pilot.json`. Supporting details and sources are in
[METHODS.md](METHODS.md); accession inventories and metadata are in
[references/](references/README.md).

## Historical execution profiles

These profiles predate the ≥20 kb policy and must not be described as the revised baseline.

`config/next-stages.json` freezes 22 S1 cases across all five references and ten
S2 cases: W/pRK2 and MGH78578/pKPN7 at relative depths 0.8, 1, 1.2, 3 and 5.
Four tool configurations give 128 comparisons. Batch `20261104T190455` has
completed its comparisons and supplementary diagnostics; outcomes are shown on
the site. The earlier single-case pilot remains available under Earlier batches.
The 1× S2 cases deliberately repeat baseline conditions; they are not independent
biological replicates. S3 repeated/thread runs and S4 read-length challenges now have separate runnable
profiles: `config/determinism.json` (80 executions) and
`config/small-plasmids.json` (48 comparisons). They were submitted sequentially
after S1/S2 to keep that historical pilot’s assembly concurrency at four.
Current submissions use the user-authorised cap of 1000 and leave resource
scheduling to Slurm. S4 finished with four separately
recorded tool errors; all 80 S3 executions and final diagnostics completed. All batches are linked
on the site. Supplementary alignment diagnostics explain strict failures without
changing their scores; see [RECOVERY_DIAGNOSTICS.md](RECOVERY_DIAGNOSTICS.md).

## Interpreting the first failures

The [provisional review](FAILURE_REVIEW.md) distinguishes exact sequence errors
from missing supported mappings and chromosome-control failures. One checked
Raven pilot contig has a five-base deletion; its 97% mapped fraction also reflects
an omitted circular-origin alignment segment, rather than a 3% sequence loss.
The site retains that observation only for its matching execution, assembly,
truth and mapping hashes. Per-molecule mapping evidence is downloadable as TSV.

The [next error-bearing read design](REALISTIC_READS.md) proposes matched controls,
three simulation seeds and two error/quality packages. The expanded design remains non-executable in
`config/realistic-reads.proposed.json`. The historical small-plasmid smoke implementation is frozen
in `config/noisy-smoke.json`: three W/pRK2 read sets and 12 assembler comparisons.
The revised S6 excludes small plasmids and has completed 24 executions using
`config/noisy-large.json`, with matched SE11 + pSE11-1 and MGH78578 + pKPN3
inputs. Exact outcomes and continuous recovery/accuracy measurements are reported;
a tolerant binary endpoint remains unscored. The original proposed JSON is
historical. See `S6_LARGE_RUNS.md` and `evidence/s6-large-v1/status.json`.
Its source-paired Badread adapter, admission checks and separate tolerant endpoint
passed Linux tests and real-reference controls. All three read sets passed
admission; all 12 assembly comparisons and separate tolerant assessments completed.
Exact outcomes were three passes and nine fails; tolerant outcomes were six passes
and six fails. These endpoints are reported separately. See [NOISY_ADAPTER.md](NOISY_ADAPTER.md) and
[TOLERANT_ENDPOINT.md](TOLERANT_ENDPOINT.md).

## Benchmark development

[Comparison with Wick and Holt and implementation plan](BENCHMARK_DEVELOPMENT.md) ·
[Linear terminal-repeat candidates](LINEAR_TERMINAL_REPEATS.md) ·
[Standard length metrics](LENGTH_METRICS.md).

[Existing-run integrity audit and missing Raven graphs](INTEGRITY_AUDIT.md): all
audited source checksums matched; historic Raven runs did not request GFA output.

The active S5 profile `config/linear-plasmids.json` selects the three complete
Streptomyces assemblies linked by CP108065.1, CP108676.1 and CP109243.1, including
their native plasmids. Six standard/long inputs define 24 assembly tasks; the
replacement batch `20261106T104655` has 24 terminal outcomes and complete
evidence. Raw Miniasm and Miniasm + Minipolish add six executions each; their
collection/publication checkpoints are separate. SCP1/SLP2 are historical controls. See
[the active S5 reference selection](LINEAR_TERMINAL_REPEATS.md).

Bundle-rendered websites publish pages, plots, compact interactive graph models
and table exports. Full evidence JSON and the backend ZIP remain outside the
Vercel output. See [website packaging](WEB_DOWNLOADS.md) for the retained assets,
separate backend archive and size audit.

[Recorded node interval evidence](NODE_INTERVAL_EVIDENCE.md) · [Scenario readiness and remaining definitions](SCENARIO_ROADMAP.md).

[Static release safeguards and guarded deployment](STATIC_RELEASE.md).

[Reporting saved base-mismatch counts](RECORDED_MISMATCH_COUNTS.md).

[Miniasm integration](MINIASM.md): pinned minimap2 overlap and unpolished miniasm
assembly adapter, graph/FASTA extraction and two-step command provenance.

[Miniasm + Minipolish](MINIPOLISH.md): paired polished workflow, reusing the
frozen reads and raw Miniasm assemblies with separately recorded outcomes.
