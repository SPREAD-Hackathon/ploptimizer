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

## Miniasm-only extension

The user authorised Miniasm on the same frozen S5 reads after this batch returns.
Six additional executions are queued as `20261106T111953`; no original assembler
is rerun and no new reads are generated. See `MINIASM.md` and
`evidence/s5-miniasm-v1/status.json` for the dependency chain. Once verified,
the raw Miniasm extension adds six outcomes. The subsequent Minipolish
extension adds six more: **36 outcomes across six configurations** in total.
See `MINIPOLISH.md` for the polishing continuation and separate provenance.

## User-requested stop and future time limit

Task `34519371_23` (long S. albidoflavus Plassembler) was cancelled at the
user’s request after 2:11:30 on 6 November 2026. This was a manual stop under
the original four-hour allocation, not an automatic two-hour timeout. The
original running record is retained alongside its terminal record. See
`evidence/plassembler-two-hour-limit/` for accounting and the stop provenance.
No assembly is rerun and no final sequence verdict is inferred.

The report displays **Fail — did not complete** and includes this execution
in failure counts. The stored execution status remains `timeout`, with
`execution_outcome: did_not_complete`, so the cause remains distinguishable
from a completed sequence mismatch. Historical records are unchanged.
Future Plassembler workers cap execution at two hours (or a shorter configured
limit), lower their own Slurm allocation to that limit, and reserve cleanup
time to write the terminal record. Other assemblers retain their limits.
