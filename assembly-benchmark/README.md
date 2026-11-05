# Long-read plasmid assembly benchmark

**Status:** the first benchmark reporting release is complete. S1/S2, S3, S4 and
the bounded S6 smoke batch have finished; documented uncertainties remain.
See the [release results and limitations](RELEASE_STATUS.md). Python automation generates
error-free reads, submits BMRC Slurm jobs through Pixi environments and builds a
static results website. See [RUNNING.md](RUNNING.md) for the explicit pilot settings
and commands. Broader study choices remain in the [decision list](DECISIONS.md).

**[Live results website](https://ploptimizer-assembly-benchmark.vercel.app)**:
assembler/scenario matrix, scenario evidence and individual tool-execution pages
with reported circularity, contig measurements, interactive graph inspection and
downloadable provenance. See [graph collection](GRAPH_COLLECTION.md) for source
coverage and limits. Publication snapshots are versioned in `published/`; large
run artefacts stay on BMRC.

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
original references, identifiers and scores. The revised baseline currently has
chromosome-only and single larger-plasmid S1 controls. Multiple-larger-plasmid S1,
larger-plasmid S2 and revised S3 are not assessed. This reporting change does not
replace references or submit new biological computation.

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
after S1/S2 to keep assembly concurrency at four. S4 finished with four separately
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
`config/realistic-reads.proposed.json`. The bounded implementation is now frozen
in `config/noisy-smoke.json`: three W/pRK2 read sets and 12 assembler comparisons.
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

The first runnable S5 profile is `config/linear-plasmids.json`: four isolated
linear-plasmid controls, 16 assembly tasks, with explicit terminal anchors and
standard/spanning read profiles. See [the S5 execution details](LINEAR_TERMINAL_REPEATS.md#first-executable-backend-profile).
