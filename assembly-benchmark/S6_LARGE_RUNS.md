# S6: larger-plasmid matched read-error panel

`config/noisy-large.json` contains the authorised 24 executions: two chromosome
plus single-plasmid subsets, three read conditions and four existing assembler
configurations. The other native plasmids are excluded. This is separate from
the historical small-plasmid S6 smoke panel and the proposed S7 experiment.

- SE11 chromosome + pSE11-1, 100,021 bp.
- MGH78578 chromosome + pKPN3, 175,879 bp.
- Matched error-free, generic simulated errors, and historical ONT-shaped errors.
- Flye default, Flye (`--meta`), Raven and Plassembler; existing four-thread
  settings and tool parameters retained.

## Frozen source reuse

The clean fragments are copied from the completed S2 batch `20261106T042108`,
at relative plasmid depth 1. The configuration binds the original manifest,
FASTQ, truth and read-origin hashes. Preparation verifies those files, scenario
fingerprints, replicon inventories and fragment geometry. Simulation copies
the admitted clean inputs rather than regenerating them. Every error condition
uses identical clean bytes for its corresponding reference subset. Source
manifests and read files remain on BMRC.

The existing error-model/runtime freezing and source-paired transformation are
unchanged. All original and emitted reads, input manifests, model hashes and
read-origin/audit records are retained in the new batch. Statistical input holds
remain holds rather than assembler failures.

## Assessments

Exact dedicated-molecule scoring is unchanged. Supplementary Minimap2 and NUCmer
evidence report coverage, identity, continuity, lengths and graph/contig data.

This panel explicitly uses `continuous-evidence-v1`: tolerant binary outcomes
are **unscored**. The original small-plasmid evaluator, thresholds, accession
allowlist and 64-marker copy-exclusion bounds are unchanged. They are not silently
extended to larger references. The continuous mode validates frozen input
provenance and emits source-bound unscored records instead of pretending that a
larger-plasmid pass/fail endpoint has been validated. Actual assemblies and
continuous evidence can therefore proceed without an invented binary result.

Compare each noisy condition with its own clean control. An exact failure on a
clean control cannot be attributed to read errors. Exact scores are not a
replacement for continuous accuracy/continuity evidence on noisy reads.

## Controller and status

```sh
python3 scripts/noisy_large.py plan
python3 scripts/noisy_large.py submit
python3 scripts/noisy_large.py collect
```

The controller creates one fresh batch, records all job IDs and queues a
dependency-linked evidence job. The ignored
`.cache/s6-large-v1/checkpoint.json` prevents duplicate assembly/evidence
submission. The committed operational record is
`evidence/s6-large-v1/status.json`. Collection retrieves only small artefacts;
reads, assembly FASTAs and NUCmer delta files stay on BMRC.

Arrays use the user's 1,000-task cap and let Slurm allocate resources. There are
no cross-study assembly dependencies or parameter changes to improve scores.
Retain original outputs and scientific failures. Do not rerun a terminal task
silently. Publish only after accounting for all 24 executions and validating
their source-fragment hashes and completed evidence.
