# Native linear-genome S5 run

Batch: **20261106T104655**. Six frozen inputs and 24 assembler tasks were
submitted on cluster3 through Slurm on 6 November 2026. The scheduler array
cap is 1000; no artificial assembly ordering is imposed.

The three complete Streptomyces genomes and their native plasmids are defined
in `config/linear-plasmids.json`. Reference repeat boundaries were checked first
using NUCmer 4.0.1 in Slurm job **34519324**. All five input sequence hashes
matched the admitted versions. The complete 832 inter-arm alignments are in
`evidence/s5-native-v2/reference-repeat-alignments.json`; selected intervals and
interpretation are in `LINEAR_TERMINAL_REPEATS.md`.

| Stage | Slurm job |
| --- | --- |
| Preparation, reference validation and tests | 34519368 |
| Six read-generation tasks | 34519370 |
| 24 assembler tasks | 34519371 |
| Standalone report | 34519372 |
| Diagnostics, graphs, lengths and NUCmer plots | 34519373 |

Preparation gates simulation; all simulations gate the assembly array. The
evidence job waits for assemblies and reporting. The same input FASTQ is reused
by all four configurations for each case. Reads, assemblies and full graphs
remain on BMRC; collection retrieves the small reporting artefacts.

The standard and long read profiles, assembler parameters and exact endpoints
are frozen before execution. Linear exact equivalence allows reverse
complementation but not rotation. Plasmid-containing headline endpoints and
chromosome assessments remain separately labelled. Repeat boundaries are
alignment endpoints: the offset S. albidoflavus chromosome end and the weaker
S. canus plasmid match are retained in the per-result reference table.

## Automation

Run from `assembly-benchmark`:

```sh
python3 scripts/native_linear.py plan
python3 scripts/native_linear.py submit
python3 scripts/native_linear.py collect
```

`submit` uses the committed checkpoint and refuses changed configurations or
partial submissions. Repeating it does not submit duplicate assembly arrays.
`collect` reads scheduler accounting and retrieves existing evidence. It does
not rerun assemblies. Current state and job IDs are recorded in
`evidence/s5-native-v2/status.json`.

Only after all 24 execution records and their evidence are verified should the
snapshot enter the overview cohort. Export/render must use the completed
`runs/20261106T104655/comparisons/s5-native-v2` root. Publish through the compact
site gate and verify live result pages, plots and downloads. Historical isolated
SCP1/SLP2 runs remain supplementary with their original scores.
