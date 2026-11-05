# S5 completed backend batch

Batch: **20261105T161510** · profile: `config/linear-plasmids.json`.
Run on BMRC cluster3 on 5 November 2026. All required jobs completed with exit 0.

This separate panel simulates isolated SCP1/SLP2 reference records. It does not
claim a native chromosome context or independently verified physical termini.
Four simulated inputs produced 16 assembly tasks: Flye (default), Flye (`--meta`),
Raven and Plassembler, each on standard and long-read profiles for both plasmids.

## Verified outcomes

- All four inputs passed admission: complete reference breadth, at least two
  reads touching each end, and approximately 30× depth. Linear reads never wrap.
- All 16 tools finished successfully as processes; all 16 strict sequence
  outcomes failed. A sequence failure is distinct from a tool crash.
- Flye (default) on SLP2, in both profiles: one 50,409 bp contig versus the
  50,410 bp reference. Saved PAF aligns the whole contig exactly to reference
  positions 1–50,409, leaving the last reference base outside the alignment.
  This locates the discrepancy; it does not establish the internal reason.
- Flye (default) on SCP1: two contigs in both profiles, rather than one complete
  356,023 bp molecule. Standard output lengths are 251,519 and 74,447 bp;
  long-read output lengths are 67,778 and 205,792 bp. Repeat alignments have
  MAPQ 0 and are retained in the plot evidence, not treated as unique placement.
- Raven and Plassembler produce no scored contigs for the SLP2 long-read input.
  Their processes exited 0; this is an empty-output sequence failure.
- Saved diagnostics, scored-contig length inventories and graph sidecars exist
  for every execution. An empty assembly has no alignment lines; no plot is
  invented for it. Software-internal causes remain unresolved.

The long SLP2 profile clips reads at the 50,410 bp molecule length; many reads
therefore span the entire record. Both profiles deliberately add terminal reads
and are ideal sequence-recovery controls, not realistic library preparations.
Terminal-repeat curation and its limitations are in LINEAR_TERMINAL_REPEATS.md.

## Completed job chain

| Stage | Slurm job | State |
| --- | --- | --- |
| Prepare and tests | 34425490 | COMPLETED, 0:0 |
| Four simulations | 34425491 | All COMPLETED, 0:0 |
| Sixteen assemblies | 34425492 | All COMPLETED, 0:0 |
| Alignment diagnostics | 34425764 | COMPLETED, 0:0 |
| Graph, length and identity metadata | 34425848 | COMPLETED, 0:0 |
| Standalone batch report | 34425493 | COMPLETED, 0:0 |

The final report waited for metadata collection. Large reads, assemblies and GFA
sources remain on BMRC; small result/provenance/diagnostic artefacts were collected.
The metadata collector recorded 16 graph sidecars, 16 scored length inventories
and 16 identity inventories (17 identity pairs).

The first attempt, **20261105T161001**, failed preparation because the Pixi
default environment lacked Matplotlib. Simulation and assembly were cancelled
without running. References passed validation. The pinned dependency fix is
commit `e1e23c1`; the successful retry uses a fresh batch.

## Reproduce through the backend

From assembly-benchmark:

```sh
python benchmark.py --config config/linear-plasmids.json plan
python benchmark.py --config config/linear-plasmids.json submit
python benchmark.py collect --batch 20261105T161510
python benchmark.py report --batch 20261105T161510
```

Submission creates a new batch; collection/reporting consume the named batch.
The immutable publication snapshot preserves exact scores and source provenance.

## Publication

[S5 results](https://ploptimizer-assembly-benchmark.vercel.app/scenarios/s5)
are published in production deployment `dpl_Egjp23QfLZTYyYtQPXtCbNsqm6hQ`.
All 16 outcomes have saved coordinate evidence; two empty assemblies correctly
have empty coordinate plots. The downloadable backend bundle includes all six
saved batches, with 300 result views and unchanged original source fields.

Verification: the 321-test Python suite passed with 11 optional skips; eight
cohort tests passed, and 6,923 local links resolve. Earlier results and scores
were preserved field by field across all 300 source records.

Live verification compared all 2,266 public files byte for byte with the local
build: no differences or failed downloads. Saved verification and scheduler
accounting are in `evidence/s5-20261105/`.
