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

## Proposed scenario definition; not executed

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
capture bias. None of these proposed cases has been simulated or submitted here.
