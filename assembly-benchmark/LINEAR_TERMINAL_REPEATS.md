# S5: complete linear Streptomyces genomes

The active panel replaces the isolated SCP1/SLP2 controls with the three complete
assemblies selected by the user. It includes every deposited replicon in each
assembly, rather than attaching a plasmid to an unrelated chromosome.

| Species / strain | Requested chromosome | Chromosome length | Native plasmid | Plasmid length | RefSeq assembly |
| --- | --- | --- | --- | --- | --- |
| S. canus NBC_00277 | [CP108065.1](https://www.ncbi.nlm.nih.gov/nuccore/CP108065.1/) | 10,691,412 bp | CP108066.1 | 134,326 bp | GCF_036177905.1 |
| S. prunicolor NBC_01021 | [CP108676.1](https://www.ncbi.nlm.nih.gov/nuccore/CP108676.1/) | 10,948,847 bp | None deposited | — | GCF_045162825.1 |
| S. albidoflavus NBC 01661 | [CP109243.1](https://www.ncbi.nlm.nih.gov/nuccore/CP109243.1/) | 7,135,774 bp | CP109244.1 | 172,072 bp | GCF_045210185.1 |

NCBI annotates all five records as linear. The pinned assembly reports link the
requested GenBank records to identical-version RefSeq records (`NZ_CP…`). The
backend uses those RefSeq accessions and retains the requested GenBank aliases.
The reference inventory and sequence hashes are in
[references/streptomyces-linear-panel.json](references/streptomyces-linear-panel.json).
Unmodified NCBI metadata responses are retained under
`references/ncbi/streptomyces-linear-20261106/`.

## Active backend configuration

`config/linear-plasmids.json` now selects the three complete assemblies through
`pipeline/linear_cases.py`. Two read-length profiles produce six inputs and
24 assembler executions: standard target lengths (10 kb mean, 50 kb ceiling) and
long target lengths (100 kb mean, 200 kb ceiling), each with the existing four
assembler configurations. Submission status and job identifiers are recorded in `evidence/s5-native-v2/status.json`.

Each input contains its complete deposited chromosome/plasmid complement.
Plassembler uses its ordinary chromosome-aware workflow, retaining chromosome
output; the old `--no_chromosome` mode is not used for these genomes.

The existing exact per-tool endpoints remain unchanged: plasmid recovery decides
plasmid-containing cases; chromosome-only recovery is assessed for ordinary
assemblers, while Plassembler has its separate no-plasmid control. Per-molecule
chromosome and plasmid results must be shown separately. A plasmid pass alone
must not be described as exact recovery of the complete genome.

## Input and terminal checks

All five pinned sequences passed accession, length and ACGT-only checks. The
reference preparer rechecks their sequence hashes and recorded terminal evidence.
The error-free linear simulator retains fixed ends and never wraps reads across
them. Two terminal reads cover each end, one per orientation; full breadth is required.
The standard and long arms retain their declared 10 kb / 120 kb terminal-read
lengths, capped to molecule length. These are the existing ideal-data controls.

The pinned references have now been compared between complete left and right
halves with NUCmer 4.0.1 (`--maxmatch --nosimplify --threads 1`, no delta filtering).
The leading left-terminal inverted alignments are below. Coordinates are
**1-based inclusive**; identity is rounded by `show-coords`.

| Molecule | Left interval | Right interval | Aligned lengths (left / right) | Identity | Right-tip offset |
| --- | --- | --- | --- | --- | --- |
| CP108065.1 chromosome | 1–15,164 | 10,676,251–10,691,412 | 15,164 / 15,162 bp | 99.99% | 0 bp |
| CP108066.1 plasmid | 1–502 | 133,817–134,326 | 502 / 510 bp | 86.13% | 0 bp |
| CP108676.1 chromosome | 1–65,571 | 10,883,283–10,948,847 | 65,571 / 65,565 bp | 99.99% | 0 bp |
| CP109243.1 chromosome | 1–25,460 | 7,109,024–7,134,484 | 25,460 / 25,461 bp | 99.99% | 1,290 bp |
| CP109244.1 plasmid | — | — | No inter-arm alignment in this run | — | — |

These are **inverted** alignments, not tandem arrays. The S. albidoflavus
chromosome has an offset right-hand match; the remaining 1,290 bp stays visible
in interpretation. The S. canus plasmid match has lower identity than the
chromosome repeats. These boundaries are alignment endpoints. All 832 unfiltered
inter-arm alignment rows, commands and sequence hashes are retained in
`evidence/s5-native-v2/reference-repeat-alignments.json` (0-based half-open).

The existing 10 kb / 100 kb mean read profiles are unchanged. They remain
standard and long: the native genomes differ in repeat structure.

Linear exact equivalence permits reverse complementation, not rotation. Sequence
recovery, end truncation, repeat copy structure and reported circularity should
remain distinguishable in the report. Repeat-specific mechanism claims require
curated intervals in these exact versions.

## Historical controls

SCP1 and SLP2 are no longer active reference selections. Their original 16 runs,
commands and scores remain historical/supplementary. Their exact configuration is
retained as `config/linear-isolated-legacy.json`; their curation is in
[LINEAR_ISOLATED_LEGACY.md](LINEAR_ISOLATED_LEGACY.md) and
[references/linear-panel.json](references/linear-panel.json).

Plan from `assembly-benchmark` with:

```sh
python3 benchmark.py --config config/linear-plasmids.json plan
```

Planning does not simulate reads or submit jobs. The submitted native batch is
`20261106T104655`; job IDs and collection commands are in `S5_NATIVE_RUNS.md`.
Do not overwrite the historical S5 batch or resubmit this native panel.
