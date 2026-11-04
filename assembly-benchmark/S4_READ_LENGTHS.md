# S4: small plasmids and the read-length distribution

`config/small-plasmids.json` defines 12 scenarios and 48 assembler comparisons:

- E. coli W, pRK2 (`NC_017662.1`, 5,360 bp), alone with its chromosome and within
  the two-plasmid deposited complement (`GCF_000258145.1`).
- K. pneumoniae MGH78578, pKPN7 (`NC_009653.1`, 3,478 bp), alone with its chromosome
  and within the five-plasmid deposited complement (`GCF_000016305.1`).
- Three whole-input read-length profiles per context: short, baseline and long.

| Profile | Lognormal mean | Lognormal SD | Minimum | Maximum before molecule clipping |
| --- | ---: | ---: | ---: | ---: |
| Short | 1,500 bp | 500 bp | 500 bp | 2,500 bp |
| Baseline | 10,000 bp | 5,000 bp | 500 bp | 50,000 bp |
| Long | 25,000 bp | 10,000 bp | 500 bp | 100,000 bp |

Chromosome depth stays at 30× and plasmid relative depth at 1×. The seed,
error-free model, tools, four threads and strict endpoint match the earlier
profiles. Each selected profile applies to every retained replicon, so the
chromosome length distribution changes with the plasmid distribution. It is a
controlled whole-input read-length challenge, not a test that holds chromosome
reads fixed while changing only plasmid reads.

Short reads cannot span either target small plasmid in one read. Baseline and
long distributions are clipped to each molecule's length, with at most one
circular traversal and no tandem-concatemer reads. Consequently, small-plasmid
reads in the baseline and long cases may have very similar achieved lengths.
The long cases test the consequences of this declared clipping policy; their
25 kb target does not describe the achieved length on a 3.5 kb plasmid. This
panel cannot represent real nanopore library retention, extraction or
size-selection losses, which need separate evidence and simulations.

The existing simulator records count, sequenced bases, target/achieved depth,
breadth and mean/minimum/maximum read lengths for each replicon in `input.json`.
Read origins retain the individual lengths. Inputs must reach 99% breadth before
assembly failure is interpreted. Sampling may overshoot the target by one read.
All tools receive the same frozen FASTQ for a case. Per-accession random streams
also preserve the reads of a shared replicon between individual and native
contexts within the same length profile. The baseline S4 conditions repeat S1
conditions intentionally and do not constitute an independent replicate.

No target is below 2 kb: the shortest reference here is pKPN7 at 3,478 bp. A
sub-2-kb case still needs a separately admitted reference. Neither simulated
read generation nor complete RefSeq status independently validates the deposited
biological molecule structure.

## Configuration and integration

`read_length_panel.targets` identifies the native small plasmid in each selected
assembly, `contexts` selects `individual` and/or `native`, and `profiles` declares
all four length settings with a stable ID and title. The panel expands from S1
reference subsets without mutating them. Optional `scenario_categories: ["S4"]`
selects only the 12 new cases for this batch; existing configs without the field
retain their current plans and fingerprints.

The report includes S4 and describes this length challenge. The standard `prepare`, `simulate`, `run`, and `submit`
commands then use these cases through the existing interfaces:

```sh
python3 benchmark.py --config config/small-plasmids.json plan
python3 benchmark.py --config config/small-plasmids.json submit
```

The current S4 batch is queued after the S1/S2 report; consult the live site
for execution status. Five focused tests check panel size, length bounds,
actual achieved input evidence, invalid definitions and unchanged S1/S2 cases.
