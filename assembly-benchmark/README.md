# Long-read plasmid assembly benchmark

**Status:** the first benchmark reporting release is complete. S1/S2, S3, S4 and
the bounded S6 smoke batch have finished; documented uncertainties remain.
See the [release results and limitations](RELEASE_STATUS.md). Python automation generates
error-free reads, submits BMRC Slurm jobs through Pixi environments and builds a
static results website. See [RUNNING.md](RUNNING.md) for the explicit pilot settings
and commands. Broader study choices remain in the [decision list](DECISIONS.md).

**[Live results website](https://ploptimizer-assembly-benchmark.vercel.app)**:
assembler/scenario matrix, scenario evidence and methods. Small publication
snapshots are versioned in `published/`; large run artefacts stay on BMRC.

## Aim

Assess whether long-read assembly tools recover the correct plasmid sequences and molecule count alongside the chromosome. Detect missing, fragmented, merged, duplicated and incorrectly circularised plasmids. Start with *Klebsiella pneumoniae* and *Escherichia coli*.

## First benchmark

Use error-free simulated long reads from curated complete references. Test four scenario families, changing one factor at a time:

1. **Plasmid count (S1):** chromosome alone, chromosome plus one native plasmid, and chromosome plus multiple native plasmids.
2. **Relative coverage (S2):** plasmid depth at 0.8×, 1×, 1.2×, 3× and 5× chromosome depth. Fix chromosome depth; these ratios describe read coverage, not measured biological copy number.
3. **Reproducibility (S3):** repeat the same input/configuration at one thread and selected multi-thread settings. Compare file identity, normalised sequences and biological outcomes separately.
4. **Small plasmids (S4):** test small plasmids with their chromosome and within their native complement. Check that reads were present before calling an assembly failure.

Use the same frozen reads for all tools. Keep simulation replicates separate from repeated executions on identical reads. Label computational subsets as derived cases rather than natural plasmid complements.

## Tools and references

The initial tool panel is **Flye**, **Flye uneven-coverage mode**, **Plassembler long-read-only mode**, and **Raven**. Compare Plassembler's final plasmids with its own initial Flye assembly as well as the standalone baselines. Record component versions and internal filtering; score its retained chromosome separately.

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

## Current expansion

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
