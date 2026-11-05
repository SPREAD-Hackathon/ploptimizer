# S3: repeatability, separately from recovery

Run the exact same frozen reads five times per tool, mode and thread count.
Use fresh execution directories without shared checkpoints. Freeze versions,
dependencies and all other arguments. Record commands and scheduler CPUs.

| Tool | Default 1 thread | Default 4 threads | Deterministic 1 thread | Deterministic 4 threads |
| --- | --- | --- | --- | --- |
| Flye 2.9.6 | 5 | 5 | 5 | 5 |
| Flye uneven coverage 2.9.6 | 5 | 5 | 5 | 5 |
| Raven 1.8.3 | 5 | 5 | Not exposed | Not exposed |
| Plassembler long 1.9.0 | 5 | 5 | Not exposed | Not exposed |

New profile `config/determinism-modes.json`: 120 tasks across the two existing
inputs (80 default, 40 flagged). Not submitted. Original configuration and frozen
80-run batch unchanged. Default means existing benchmark arguments without an
added determinism flag, rather than every upstream default. Flye's flag makes
initial disjointig assembly single-threaded; later stages can use requested threads.
The upstream tracker reports residual variation, so test rather than assume it.

Headline groups: input × tool/version × mode × thread count. Never pool modes.
Identical requires every expected repeat completed, identical verified inputs and
matching normalised signatures. Different requires a complete verified group with
multiple signatures. Missing/error executions, missing signatures or unequal/
unverified inputs are not assessed. Show observed variant counts.

Byte identity is separate: headers, order and wrapping can change file bytes.
Normalisation ignores names, order and strand, retaining duplicates. Circular
rotation is ignored only for exact reference-matched circles; other ends remain
significant. Different signatures alone do not establish base changes, topology
or software cause. Compare thread counts within each mode separately. Compare
default/flagged behaviour only when both have results. The website consumes saved
comparisons without sequence calculations. Reference recovery remains secondary:
identical wrong outputs are repeatable, and different outputs can share a score.

Existing default batch `20261104T193612`: 16/16 within-thread groups agree in
normalised sequences, 15/16 in bytes. Across threads 7/8 agree in normalised
sequences; W/pRK2 Flye uneven coverage differs. All eight agree in recovery
outcomes. No flagged measurements exist. Finite agreement is not a guarantee.

Checked version-pinned capability sources:

- [Flye CLI](https://github.com/mikolmogorov/Flye/blob/2.9.6/flye/main.py): deterministic flag and description.
- [Flye issue 640](https://github.com/mikolmogorov/Flye/issues/640): residual variation.
- [Raven CLI](https://github.com/lbcb-sci/raven/blob/1.8.3/RavenExe/src/main.cc): no direct determinism/seed flag found.
- [Plassembler CLI](https://github.com/gbouras13/plassembler/blob/v1.9.0/src/plassembler/__init__.py): no direct determinism/seed flag found; component changes are separate configurations.
