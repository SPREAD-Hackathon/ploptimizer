# Plasmid benchmark: comparison and next implementation stages

Reviewed 5 November 2026. [Wick and Holt, version 4](https://doi.org/10.12688/f1000research.21782.4)
was read through the [Europe PMC full-text service](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6966772/fullTextXML)
because the publisher endpoint rejected access. The supporting
[repository](https://github.com/rrwick/Long-read-assembler-comparison) was checked at
revision `4bc676c4a5b01602abf1143bfefcaab4cc0dde97`.

## What already exists in Wick's work

The study compared eight assemblers on 500 simulated read sets and 120 real read
sets. Its simulations varied depth, read length, quality and artefacts, including
plasmid depth. Plasmid completion was analysed against size and depth. All
simulated replicons were treated as circular; linear recovery was not tested.
The principal measurement was longest single alignment relative to replicon
length, using tripled circular references. Completion used a 99% threshold;
identity, maximum indels, circularisation, time and RAM were separate measures.
The real-read references used concordant hybrid assemblies, with an acknowledged
selection bias towards easier genomes. These are historical tool versions, not
current rankings.

Plasmid recovery, small plasmids, uneven depth and circularisation errors therefore
are not new topics introduced by this project. See the repository's figures S3,
S5, S6, S8 and S9 and `scripts/assess_assembly.py` for the existing framework.

## How our current scope differs

| Question | Current Ploptimizer position |
| --- | --- |
| Controlled variables | Named, matched scenarios isolate plasmid complement, coverage and read-length changes instead of pooling many randomly varied factors. |
| Endpoint | Exact dedicated-copy recovery is stricter than alignment-based completion. Preserve both questions rather than calling a 99% completion criterion exact. |
| What differs? | Result pages combine saved coordinates, exact-copy evidence, contig inventories and graph provenance. These observations do not generally explain an assembler-internal cause. |
| Repeatability | S3 compares identical frozen inputs within mode/thread groups; reference recovery is secondary. The flagged-mode follow-up is configured, not run. |
| Current limitations | Few curated genomes, mainly idealised reads, no validated real-read panel, and incomplete mechanism/per-base event coverage. This is not yet a broad performance ranking. |

Our current aligned-reference fraction is union coverage under saved filters. It
is **not Wick's longest-alignment contiguity**, and must not be renamed or compared
numerically as though they were the same. A future circular-aware assessment must
version its reference representation and coordinate conversion explicitly.

## Plan and delivery order

1. **Implemented in this update:** standard graph-segment and scored-contig length
   distributions, per-item lengths, complete/missing distinctions, source hashes,
   independent JSON/TSV/Markdown exports and result-page presentation. Existing
   FASTAs supply length metadata only; no assembly or alignment reruns.
2. **Bounded S5 batch completed:** see [S5_RUN_STATUS.md](S5_RUN_STATUS.md).
   Broader linear-reference admission remains separate from these isolated
   controls and from the initial E. coli/Klebsiella cohort.
3. **Next evidence work:** a versioned circular-aware continuity measurement,
   separate from exact sequence and copy recovery; coordinate-level terminal
   excess/loss and indel events; explicit uncertainty for shared-repeat assignment.
4. **Next execution work:** run the configured S3 mode matrix, then select
   additional cases based on measured gaps. Do not silently replace historical
   scores or pool read resampling with computational repeats.
5. **Later validation:** matched real reads with independent reference evidence,
   explicit reference uncertainty and library-specific small-plasmid/terminal
   sampling effects. Keep tool-version comparisons and cohort changes explicit.

The intended contribution is a reproducible diagnostic regression suite focused
on plasmid outcomes, with enough evidence to distinguish a measured discrepancy
from a proposed software explanation.

Current readiness and remaining definitions: [SCENARIO_ROADMAP.md](SCENARIO_ROADMAP.md).
