# Methods and evaluation notes

The current [baseline policy](BASELINE_POLICY.md) requires plasmids ≥20 kb in S1–S3 and isolates smaller plasmids in S4. Saved mixed-size runs remain supplementary. Historical profiles and accessions below retain their original provenance; the revised panel is not fully assessed.

Supporting design notes for the [short specification](README.md). Open choices belong in [DECISIONS.md](DECISIONS.md); these notes do not settle numerical settings or admit reference candidates.

## Reference and input provenance

Use the pinned [reference inventory](references/README.md), review supporting evidence and audit sequences before admission. A complete-genome label or RefSeq membership alone does not establish complete, accurate plasmid recovery [1, 2]. Keep native complements, derived subsets and any later artificial cross-reference mixtures explicitly labelled. Reference sequences are evaluation truth and must not be provided to the assembler.

Reference records need species/taxonomy identifiers, assembly and replicon accession versions, chromosome/plasmid roles, lengths, topology, validation evidence and sequence checksums. Scenario records need the exact subset, source/derived status, generator/version, full configuration, seeds, input checksums, target/achieved depth and preprocessing. Missing information stays explicit.

Define depth as reference-derived sequenced bases divided by replicon length, and relative depth as plasmid depth divided by chromosome depth. Record realised values and coverage breadth, not only targets. Preserve chromosome reads across paired coverage comparisons where possible. Absolute depth remains a separate experimental factor.

## Simulation checks

Badread is a candidate for controlled long-read artefacts [3]; a high-quality preset is not an error-free specification. Validate exact sampling independently. For each read set:

- Confirm source membership and exact sequence agreement in error-free mode, including circular boundary crossings.
- Measure per-replicon counts, depth, breadth and read lengths, preferably from generator provenance. Shared repeats can make alignment-only assignments ambiguous.
- Confirm excluded replicons contributed no reads and retained replicons received the intended evidence.
- Check unique read identifiers, quality-score conventions and the chosen sampling tolerance.
- Retain invalid-input diagnostics and keep such cases separate from assembler failures.

Sample both strands. Declare whether reads may traverse circles more than once; do not silently generate tandem copies longer than a small plasmid. Use identical frozen read files across tools, with separate simulation seeds for sampling robustness.

## Tools and run provenance

Flye's standard and uneven-coverage modes are separate configurations of one assembler [5]. Plassembler long-read-only mode uses an initial Flye assembly and Unicycler-based plasmid reconstruction [6]. Its final plasmid FASTA is not a whole-genome assembly: retain its initial chromosome and compare final plasmids with its own initial Flye output. Any combined genome requires an explicit reconciliation policy to prevent duplicate/conflicting plasmids. Raven supplies another standalone baseline [7].

Pin all component versions, environments, databases, settings and internal filtering. Treat tuned settings as separate entries. Record seed/thread support and any chromosome-size priors. Keep database annotations separate from sequence-based evaluation. Score polishing as a separate stage.

Capture commands, logs, exit status, runtime, peak memory, FASTA and graphs when emitted. Distinguish success, crash, timeout, resource exhaustion, unsupported settings, invalid input and evaluator failure. Empty output can be a legitimate no-plasmid result; it is not evidence of plasmid recovery.

## Reproducibility (S3)

Repeat byte-identical inputs with fixed software, configuration, seeds and environment, using isolated output directories. Compare:

1. Raw output checksums, including headers/order.
2. Sequence content after ignoring headers/order, allowing reverse complements and circular rotations where appropriate, while preserving duplicate multiplicity.
3. Recovery, structure and sequence-error outcomes.

Report within-thread repeatability separately from between-thread equivalence. Different files can encode identical assemblies, and identical scores can hide different errors. Read-order changes, assembler-seed changes and independent simulation seeds are separate robustness experiments. Agreement across repeated runs applies only to the tested conditions.

## Evaluation

Align against all truth replicons together to expose chromosome–plasmid joins and ambiguous assignments. Use circular-aware comparison and union reference coverage, counting each reference position once. Keep alternative matches in shared regions. QUAST can supply supplementary measures [4], but does not replace plasmid-specific checks.

For each truth plasmid, report recovered fraction, aligned identity with an explicit denominator, substitutions/indels, contributing contigs, missing/extra sequence, joins, duplicated intervals, whole-molecule expansion, claimed/evaluated topology and assignment certainty.

Exact one-molecule sequence recovery permits reverse complements and rotations of circular truth, with no missing/extra sequence or duplicate expansion. Topology is a separate endpoint: an unlabelled contig may encode the exact sequence while circular status remains unknown. Tolerant thresholds for realistic reads must be defined and frozen before tool comparisons.

Record absent/partial/complete sequence recovery alongside overlapping fragmentation, merge, duplication, structural-error and ambiguity flags. Shared sequence coverage alone does not establish a correctly resolved molecule. Keep chromosome recovery separate and avoid a single chromosome-length-dominated score.

For chromosome-only controls, plasmid recall is not applicable; assess unsupported plasmid-like outputs without treating every extra contig as a plasmid. Report failures in end-to-end completion denominators and conditional accuracy among completed runs separately. Biological references, simulation replicates and repeated executions are distinct replication levels.

Validate the evaluator with exact, rotated/reverse-complemented, missing, fragmented, falsely joined, duplicated, tandem-expanded and ambiguous outputs. Add linear-end fixtures for S5.

## Linear plasmids (S5)

See the [terminal-repeat scenario specification](LINEAR_TERMINAL_REPEATS.md) for
short- and long-TIR candidates, accession versions and admission requirements.

Add a separate topology panel. A naturally linear plasmid is different from a circular plasmid represented by an unfinished linear contig. Linear truth must retain its physical ends: do not simulate circular wraparound, rotate sequences during equivalence checks or reward circularisation. Reverse-complement equivalence still applies. Basic sequence simulation does not model terminal proteins or library-specific behaviour at physical ends; document those limitations.

Measure whole-molecule recovery, left/right terminal sequence recovery, terminal truncation, terminal repeat collapse, false end-to-end joins, inappropriate circularity claims, fragmentation and chromosome–plasmid merges. Report sequence correctness separately from topology: an unlabelled linear FASTA contig alone does not prove the biological topology. Use validated circular controls to detect an evaluator that simply favours one topology.

Use a small *Streptomyces* extension panel before claiming broad performance on linear plasmids. These are candidate reference records, not an already curated gold-standard dataset. NCBI nucleotide metadata checked on 4 November 2026 identifies each record below as linear:

- **Small:** *S. clavuligerus* ATCC 27064, León isolate, pSCL1, **NZ_CP045848.1**, **11,696 bp**. A useful candidate for small linear-plasmid recovery. The original pSCL1 sequence study independently describes its linear structure [10]. Review the modern record and its source assembly before admission; the validation study for the León assembly also discusses limitations in terminal-sequence representation [11].
- **Small/medium:** *S. rochei* 7434AN4, pSLA2-S, **NC_024971.1**, **17,526 bp**. A RefSeq candidate for a native linear-plasmid complement [12].
- **Medium:** *S. lividans* 1326, SLP2, **NC_004933.1**, **50,410 bp**. Its published characterisation makes it a candidate for a separate shared chromosome–plasmid sequence challenge [13].
- **Larger:** *S. rochei* 7434AN4, pSLA2-L, **NC_004808.2**, **210,614 bp**. Its linear structure and complete sequence are described in the primary literature [12, 14].

Start with pSCL1 and the pSLA2-S/pSLA2-L pair after curation, using their respective source-isolate complements. Keep these results separate from the initial *K. pneumoniae*/*E. coli* panel because species, GC composition and repeat structure also change. Never present cross-species computational mixtures as native complements.

Linear plasmids have also been experimentally reported in *Klebsiella* and other Enterobacteriaceae [15]. Their presence in the target group justifies a later native-species panel, but this document does not yet nominate a validated target-species reference accession. Review evidence for complete termini and topology before selecting one. Neither RefSeq membership nor a complete-sequence label alone establishes gold-standard terminal accuracy.

## Later challenge panels

Extend the pilot with absolute coverage and sampling variation; read length and filtering/subsampling; realistic nanopore errors and homopolymers; naturally shared repeats and similar co-resident plasmids; terminal overlap/false closure/copy expansion; uneven within-replicon coverage; and controlled chimeric, adapter-containing or unrelated reads.

Compare one factor at a time before selected interactions, such as small size plus low depth or repeats plus short reads. Publish a finite scenario list rather than expanding every factor into a full Cartesian product. Add Autocycler as a consensus workflow with all constituent runs and costs recorded [8]; Myloasm is an exploratory modern-read candidate [9]. Keep hybrid assembly in a separate track.

## Reporting and real datasets

Start with a static report and versioned JSON/TSV exports. Include input evidence per replicon, configuration, per-plasmid and chromosome outcomes, determinism, failures and resource use, linked to logs and artefacts. Cache/resume by input checksums and full configuration. Keep large data outside Git with retrieval information.

Use the same result model for simulated and real reads, with explicit data origin. Real-data records need read accessions/checksums, isolate/culture linkage, platform/chemistry, basecaller, library preparation, filtering and reference evidence. A same-strain name or shared BioProject is insufficient to establish matched material.

Prefer orthogonal validation. References produced only by a tested assembler are not independent truth. Preserve unresolved reference/culture differences and do not infer biological absence from missing long-read evidence. Report real data separately from simulations.

## Sources

These sources support data provenance and candidate tool capabilities. The scenario panel and acceptance criteria above are project proposals.

1. [NCBI Datasets: download a genome data package](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genomes/download-genome/).
2. [NCBI Datasets: genome assembly report](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/data-reports/genome-assembly/) and [NCBI genome files and assembly reports](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/policies-annotation/genomeftp/).
3. [Badread documentation](https://github.com/rrwick/Badread), including circular references, per-reference depth and small-plasmid bias. Defaults and high-quality presets should not be treated as an exact-read specification.
4. [QUAST documentation and source](https://github.com/ablab/quast).
5. [Flye usage and supported input modes](https://github.com/mikolmogorov/Flye/blob/flye/docs/USAGE.md), including the uneven-coverage mode.
6. [Plassembler documentation](https://github.com/gbouras13/plassembler) and [long-read-only mode](https://plassembler.readthedocs.io/en/latest/long/).
7. [Raven documentation and source](https://github.com/lbcb-sci/raven).
8. [Autocycler documentation and source](https://github.com/rrwick/Autocycler).
9. [Myloasm documentation](https://myloasm-docs.github.io/).
10. [Wu and Roy, 1993: complete sequence and linear structure of pSCL1](https://pubmed.ncbi.nlm.nih.gov/8416908/); candidate [RefSeq NZ_CP045848.1](https://www.ncbi.nlm.nih.gov/nuccore/NZ_CP045848.1).
11. [Genome editing reveals that pSCL4 is required for chromosome linearity in Streptomyces clavuligerus](https://pmc.ncbi.nlm.nih.gov/articles/PMC8743545/), including reference-assembly and terminal-sequence limitations.
12. [The genome sequence of Streptomyces rochei 7434AN4](https://pmc.ncbi.nlm.nih.gov/articles/PMC6662830/); candidate RefSeq records [pSLA2-S NC_024971.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_024971.1) and [pSLA2-L NC_004808.2](https://www.ncbi.nlm.nih.gov/nuccore/NC_004808.2).
13. [Huang et al., 2003: linear plasmid SLP2](https://pubmed.ncbi.nlm.nih.gov/12622812/); candidate [RefSeq NC_004933.1](https://www.ncbi.nlm.nih.gov/nuccore/NC_004933.1).
14. [Mochizuki et al., 2003: complete sequence of pSLA2-L](https://pubmed.ncbi.nlm.nih.gov/12791134/).
15. [Linear plasmids in Klebsiella and other Enterobacteriaceae](https://pmc.ncbi.nlm.nih.gov/articles/PMC9453081/).
