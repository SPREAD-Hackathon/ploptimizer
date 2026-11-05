# S5 active backend batch

Batch: **20261105T161510** · profile: `config/linear-plasmids.json`.
Submitted to the existing BMRC cluster3 account on 5 November 2026.

This is a separate panel of isolated SCP1/SLP2 records, with no chromosome or
native-complement claim. Four simulated inputs produce 16 assembly tasks.

## Confirmed checkpoints

- Preparation completed successfully with the corrected Pixi environment.
- All four simulations completed and passed admission: 100% breadth, both ends
  covered by at least two terminal reads, and approximately 30× depth.
- Assembly array started. At the last check, 15 executions had completed with
  strict exact-sequence failures and one was still running. This is preliminary;
  the failures' detailed differences await the diagnostic stage. These are not
  reported as corruption or as established software-internal mechanisms.

## Job chain

| Stage | Slurm job | Dependency |
| --- | --- | --- |
| Prepare and tests | 34425490 | None; completed |
| Four simulations | 34425491 | Preparation; completed |
| Sixteen assemblies | 34425492 | Simulations; started |
| Existing-output alignment diagnostics | 34425764 | Assembly array |
| Graph, length and identity metadata | 34425848 | Diagnostics |
| Standalone batch report | 34425493 | Metadata collection |

The final report dependency was updated before it started, so its graph and
length metadata are collected first. The generated metadata script is retained
under the batch's `slurm/metadata.sh`; producer hashes and counts will be written
in `metadata_collection.json`. These jobs use the existing backend tools and do
not overwrite earlier benchmark results. Publication into the main website cohort
has not happened yet.

The first attempt, **20261105T161001**, failed its preparation tests because the
Pixi default environment lacked Matplotlib. Simulation and assembly dependencies
were cancelled without running. The reference records passed validation in that
attempt. The dependency was pinned and locked in commit `e1e23c1`; the successful
retry uses a fresh batch rather than overwriting the failed attempt.

## Inspect or collect

From assembly-benchmark:

```sh
python benchmark.py collect --batch 20261105T161510
python benchmark.py report --batch 20261105T161510
```

Large reads, assemblies and source graphs stay on BMRC. The normal collector may
also copy newly requested Raven GFA files from execution roots; explicit
metadata-only collection can exclude `*.gfa`, `stdout.log` and `output/` when only
JSON/report artefacts are needed. Read saved job/accounting states before treating
this checkpoint document as current progress.
