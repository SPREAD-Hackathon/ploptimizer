# Long-read plasmid assembly benchmark

**Status:** design in progress, 4 November 2026. Reference metadata has been collected; sequence validation and benchmark runs have not started. Numerical settings remain proposals until recorded in the [decision list](DECISIONS.md).

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

The proposed tool panel is **Flye**, **Flye uneven-coverage mode**, **Plassembler long-read-only mode**, and **Raven**. Compare Plassembler's final plasmids with its own initial Flye assembly as well as the standalone baselines. Record component versions and internal filtering; score its retained chromosome separately.

The [reference shortlist](references/README.md) contains accession versions and supporting evidence for:

- *E. coli* MG1655: chromosome-only control.
- *E. coli* W: two plasmids, approximately 5.4 and 102.5 kb.
- *E. coli* SE11: six plasmids, approximately 4.1–100 kb.
- *K. pneumoniae* Ecl8: one plasmid, approximately 204.7 kb.
- *K. pneumoniae* MGH 78578: five plasmids, approximately 3.5–175.9 kb.

These are candidates pending sequence checks and an admission decision. Two alternatives with metadata-indicated ambiguous bases are held separately. The initial panel has no plasmids below 3,478 bp.

## Outputs and success measures

Produce one row per truth plasmid with recovered sequence fraction, identity, contig count, structural errors, duplication and topology. Report chromosome recovery, unsupported extra outputs, run failures, runtime and peak memory separately. Exact one-molecule recovery is the strict sequence endpoint; circularity needs its own assessment.

Deliver a command-line workflow, a static report and JSON/TSV exports. Keep manifests, configurations and metadata in Git; store large reads and assemblies elsewhere. A successful pilot must reproduce its inputs and scores and retain failed runs.

## Later extensions

Add biologically linear plasmids (S5), realistic nanopore errors, coverage/read-length challenges, shared repeats, filtering effects, and matched real datasets. Autocycler, Myloasm and a hybrid track can follow. The order and admission of these extensions remain design choices.

Before implementation, resolve the [six decision groups](DECISIONS.md). Supporting details and sources are in [METHODS.md](METHODS.md); exact accession inventories and metadata are in [references/](references/README.md).
