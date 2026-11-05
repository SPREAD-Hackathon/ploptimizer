# S5: linear plasmids with terminal repeats

## Terminology and candidate examples

The well-supported examples below have **terminal inverted repeats (TIRs)**:
related sequences at opposite ends in opposite orientation. These are distinct
from tandem repeats (adjacent repeated units in the same direction). Do not label
the two structures interchangeably. This review did not establish a natural
linear-plasmid example with terminal tandem arrays suitable for admission.

| Candidate | Pinned record | Record length | Documented terminal structure |
| --- | --- | --- | --- |
| Streptomyces coelicolor A3(2), SCP1 | [NC_003903.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_003903.1) | 356,023 bp | Long TIRs, approximately 81 kb in the cited physical/sequence study. |
| Streptomyces lividans 1326, SLP2 | [NC_004933.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_004933.1) | 50,410 bp | Short 44 bp TIRs; chromosome-shared terminal sequence is an additional confounder. |

Sources: [SCP1 terminal-repeat study](https://doi.org/10.1016/0147-619X(91)90052-X),
[SLP2 characterisation](https://pubmed.ncbi.nlm.nih.gov/12622812/), and
[SLP2/chromosome terminal homology](https://doi.org/10.1099/00221287-146-4-911).
The literature repeat lengths are not new measurements of these exact RefSeq
versions. NCBI summary metadata checked on 5 November 2026 confirm the pinned
lengths and linear topology; the saved snapshot is
`references/ncbi/linear-terminal-repeat-candidates.esummary.json`.
These remain **candidates, not newly admitted gold standards**. SLP2 was already
listed in METHODS.md; SCP1 adds a substantially longer terminal-repeat candidate.

## Native-context extension; not yet executed

Use a curated native reference complement. Keep reference ends fixed; linear
reads must not wrap between ends. Contrast a short-TIR case with a long-TIR case,
recording species, GC composition and chromosome context as confounders. A
synthetic non-biological linear control can validate scoring independently.
Do not mix unrelated species and label the result a native genome.

Expected output is a linear sequence/path retaining both terminal copies and
the correct interior, without an artificial end-to-end join. A graph may contain
shared repeat segments, so its visual shape need not be one straight line.
Graph segment count or a repeated traversal alone cannot establish repeat collapse.

Assess separately:

- Full sequence, length, dedicated-copy recovery and orientation-aware ends.
- Left/right terminal recovery and truncation, with versioned terminal intervals.
- Repeat multiplicity, retained orientation, fragmentation and candidate false joins.
- Assembler-reported circularity versus expected linear topology.
- Raw graph segment and final contig length distributions.

Before admission, verify terminal completeness, ambiguous bases, accession/version
and strain provenance, including repeat coordinates in that exact sequence.
Reverse complements remain equivalent; circular rotation does not. Sequence
simulation does not reproduce terminal proteins, hairpin chemistry or library
capture bias. The native-context extension has not been simulated or submitted here.

## First executable backend profile

`config/linear-plasmids.json` is now wired into `benchmark.py` through
`pipeline/linear_cases.py`, the shared simulator, task runner and Slurm submitter.
It defines **four isolated-plasmid controls and 16 assembly tasks**: both plasmids
with standard (10 kb mean / 50 kb maximum) and repeat-spanning (100 kb mean /
200 kb maximum) read profiles, each assessed with Flye (default), Flye (`--meta`),
Raven and Plassembler long. This initial execution scope supersedes the earlier
unexecuted proposal above for these controls only; native-complement tests remain
pending.

The first batch contains no chromosome. The commonly used coelicolor M145
chromosome is a plasmid-cured derivative, so combining it with SCP1 and claiming a
native complement would be misleading ([original genome paper](https://doi.org/10.1038/417141a)).
Plassembler explicitly uses `--no_chromosome`; in version 1.9.0 this skips its
initial Flye stage and uses an artificial workflow placeholder. That placeholder
is not an input reference, a retained biological chromosome or part of scoring.

### Pinned-record curation

Both exact accession versions were downloaded and passed length and ACGT-only
checks. Their sequence hashes and literal terminal-window comparisons are frozen
in [references/linear-panel.json](references/linear-panel.json). Preparation checks
these admitted sequence hashes again before simulation.

- SCP1: 356,023 bp, with an exact terminal inverted prefix of **75,122 bp** in this
  record. Comparing the literature-sized 81,000 bp terminal windows position by
  position gives 4,321 differences. The historical approximate 81 kb claim is not
  relabelled as a perfect repeat in this version.
- SLP2: 50,410 bp, with an exact terminal inverted prefix of **14 bp**. Its
  literature-sized 44 bp windows differ at eight positions. The published short
  TIR is imperfect, rather than a 44 bp exact duplicate.

These are ungapped, literal sequence comparisons at the fixed record ends, not
independent physical-end validation or a reassembly of the original isolate.
The admitted scope is **isolated linear reference-record simulation**.

### Input admission and interpretation

The versioned `exact-linear-anchored-v1` simulator never wraps linear ends. Two
synthetic reads are anchored at each physical end, one per orientation: 10 kb
for standard cases and 120 kb for spanning cases, clipped to molecule length.
Remaining reads use random starts/strands and the declared lognormal profile.
All reads are error-free; Q40 is a placeholder. The target depth is 30×. Full
reference breadth and at least two reads touching each end are required before
assembly. These deliberate anchors create ideal, end-complete inputs; they do
not model terminal protein chemistry or library capture.

The standard SCP1 read-length ceiling does not span its exact terminal repeat;
the spanning case includes end reads longer than the repeat. Keep these conditions
separate when interpreting a failure. SLP2 spanning reads are capped at its shorter
molecule length. Exact linear scoring permits reverse complements but rejects
rotation, terminal loss, extra copies and sequence changes. Tool-reported topology
remains separate from the strict sequence endpoint.

Run from assembly-benchmark:

```sh
python benchmark.py --config config/linear-plasmids.json plan
python benchmark.py --config config/linear-plasmids.json submit
```

Pixi environments and the Slurm account/concurrency come from the existing cluster
configuration. Each batch freezes its config, task list, source provenance, input
admission and original execution files. Its initial report is batch-scoped;
joining an expanded public cohort is a later explicit publication step.
