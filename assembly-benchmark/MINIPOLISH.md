# Miniasm + Minipolish

This is the workflow structure called **Miniasm+** in Wick and Holt's comparison:
minimap2 read overlaps, miniasm unitigs and Minipolish polishing. The separate
unpolished Miniasm configuration remains available.

We use current pinned packages, not a reconstruction of the historical 2019
environment: miniasm 0.3-r179, minimap2 2.31-r1302, Minipolish 0.2.1 and Racon
1.5.0. Pixi environment: `miniasm-plus`. Tool ID: `miniasm-plus`. Display label:
**Miniasm + Minipolish**.

Sources: [comparison](https://github.com/rrwick/Long-read-assembler-comparison),
[Minipolish workflow](https://github.com/rrwick/Minipolish/tree/v0.2.1), and
[upstream combined script](https://github.com/rrwick/Minipolish/blob/main/miniasm_and_minipolish.sh).

## Matched continuation

The queued unpolished batch `20261106T111953` supplies the six raw miniasm GFAs,
including the `a` constituent-read annotations. We reuse these assemblies rather
than recomputing read overlaps or miniasm layout. The original frozen S5 reads
are reused byte-for-byte. Before staging, hashes bind each raw GFA, original
execution, original FASTA, case fingerprint, reads and truth to its source.

```sh
minimap2 -x ava-ont -t THREADS reads.fastq.gz reads.fastq.gz > overlaps.paf
miniasm -f reads.fastq.gz overlaps.paf > assembly.raw.gfa
# The first two recorded source stages are reused, not rerun.
minipolish --threads THREADS --rounds 2 reads.fastq.gz assembly.raw.gfa > assembly.polished.gfa
```

No `--skip_initial` is used. Minipolish runs its initial constituent-read Racon
polish and two full Racon rounds, using its default ONT mapping preset. No
reference-based corrections or parameter tuning are applied. Final GFA segment
sequences are copied into the scored FASTA. Raw source and polished graphs are
retained separately. If the raw assembly is empty, the report explicitly records
that polishing was not run and preserves the empty-output recovery failure.

Minipolish documents that inter-unitig overlap CIGARs are retained while sequences
are polished. Those graph link lengths are not new measurements of final overlap.
Node and contig lengths come from the final sequences; sequence assessment and
dot plots use the final FASTA.

Both recorded source commands and the actual polishing command are displayed.
Runtime is the sum of the recorded source Miniasm execution and the polishing
continuation, not just polishing time or scheduler waiting time. Peak memory is
the larger of the two sequential stage peaks. Separate stage times, source
evaluation, versions and hashes remain in the backend record.

## Queued Slurm batch

Batch **20261106T123220**, six additional executions, same six S5 inputs:

| Stage | Job | Dependency |
| --- | --- | --- |
| Verify/reuse reads and raw assemblies | 34522050 | Unpolished evidence job 34520449 succeeds |
| Six polishing continuations and assessments | 34522051 | Input/source reuse succeeds |
| Report | 34522052 | Continuations finish |
| Diagnostics, graphs, lengths and NUCmer plots | 34522053 | Assessments and report finish |

```sh
python3 scripts/miniasm_followup.py submit --tool miniasm-plus
python3 scripts/miniasm_followup.py collect --tool miniasm-plus
```

The durable checkpoint is `evidence/s5-miniasm-plus-v1/status.json`. Submission
does not duplicate an existing batch. Large files and execution stay in an
isolated source root on BMRC; collection retrieves reporting artefacts only.
Collection checks both the input-reuse audit and the six retained raw-assembly
hash bindings against the collected unpolished executions.

When verified, S5 will contain **36 executions: six inputs × six configurations**.
The follow-up monitor covers all three batches, their plots/reports, cohort
admission, release QA and production publication. Pending outcomes are not scored.

## Verification

Slurm installation/integration job **34522038** completed successfully. It ran
real Minipolish on the existing artificial Miniasm fixture, retained one unitig
and produced available graph and unitig metadata. This test is excluded from
benchmark scores. The full suite passes 394 tests with 11 optional skips. Existing
Pixi environment locks are unchanged. Evidence: `evidence/miniasm-plus-integration/`.
