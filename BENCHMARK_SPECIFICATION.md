# Ploptimizer: plasmid assembly benchmark specification

Status: proposed design for discussion, 4 November 2026. This document specifies the platform; it does not report benchmark results. Numerical settings below are proposed starting points, not validated biological or performance thresholds.

## Purpose and scope

Ploptimizer will assess how long-read assembly software reconstructs chromosomes and plasmids, with particular attention to missed, fragmented, duplicated, merged and incorrectly circularised plasmids. The initial species are *Klebsiella pneumoniae* and *Escherichia coli*.

The platform should answer:

- Which plasmids are recovered correctly, and under which input conditions?
- Can an apparently complete chromosome hide poor plasmid recovery?
- Does performance depend on plasmid size, relative coverage, repeats or read properties?
- Are results reproducible across repeated runs and thread counts?
- Do failures arise during read generation, preprocessing, assembly or polishing?

Start with controlled, error-free simulated reads from complete reference assemblies. Add realistic simulated reads next, followed by independently validated real datasets. The first release benchmarks individual-isolate, long-read-only assembly. Hybrid assembly and mixed samples can be separate later tracks. Reference sequences are evaluation truth and must never be supplied to the assembler or used to tune an individual test run.

## Reference panel and truth

### Selecting references

Build a versioned panel from public RefSeq or GenBank assemblies. Use complete assemblies with individually identified chromosome and plasmid records, confirmed species identity, documented topology and traceable provenance. Prefer references with accessible supporting reads and published validation. NCBI Datasets provides assembly metadata and sequence reports for recording these properties [1, 2].

Treat “gold standard” as a project curation decision. A complete-genome label or RefSeq membership alone does not establish that every plasmid was recovered correctly. Review sequence gaps, ambiguous bases, excluded records, available validation and possible reference errors before admission. Freeze accession versions and checksums rather than resolving “latest” during a benchmark.

For the pilot, curate at least two distinct source assemblies per species, increasing the panel where needed to cover plasmid sizes and structures. Report reference diversity and avoid treating scenarios derived from one genome as independent biological samples. Select on assembly properties, not resistance or virulence traits.

Keep these truth types explicit:

1. **Native complement:** the chromosome and recorded plasmids from the same isolate.
2. **Derived subset:** the same chromosome with zero, one or selected native plasmids retained for a controlled computational comparison.
3. **Constructed computational case:** any cross-reference combination, if later needed, labelled as artificial with all component provenance retained. It is not evidence that the complement occurs naturally.

Use native complements and derived subsets first. A chromosome-only derived subset is a known negative control even if the original isolate carried plasmids. Do not assume a deposited assembly lacking plasmids proves biological absence.

### Required manifests

Each reference manifest must record species/taxonomy identifier, source assembly accession and version, BioSample/BioProject where available, source URL, retrieval date, validation evidence, curation decision and file checksums. For every replicon, record accession/version, stable internal identifier, chromosome/plasmid role, length, topology, sequence checksum and relevant size/repeat descriptors.

Each scenario manifest must identify the exact replicon subset, source/derived truth type, simulator and version, full simulation configuration, random seed, read-length/error profile, target and achieved depth per replicon, read counts, coverage breadth, input checksums and any preprocessing. Unknown values must remain explicit.

## Core scenarios

Run the same scenario families for both species, using suitable references rather than forcing every reference into every case. Hold all other factors fixed during the initial comparisons. Maintain a list of omitted or inapplicable cases and the reasons.

### S1. Error-free baseline and plasmid count

For each suitable source assembly, compare:

- Chromosome alone: measures chromosome reconstruction and false plasmid/circular-contig output.
- Chromosome plus one native plasmid: isolates recovery of each selected plasmid.
- Chromosome plus multiple native plasmids: measures interaction and correct separation of replicons.

Initially use equal per-base depth across replicons and one fixed long-read length distribution. “Perfect reads” means error-free sequence sampled from the reference, with no adapters, chimeras or unrelated reads. It does not mean guaranteed complete coverage or guaranteed assembly. Sample both strands and handle circular boundaries correctly.

### S2. Relative plasmid coverage

Fix chromosome depth and vary one plasmid's per-base depth relative to it using the initial panel **0.8×, 1×, 1.2×, 3× and 5×**. Keep read-length and error profiles fixed. Extend to lower-depth challenge cases after the baseline works.

Define `relative_depth = plasmid_depth / chromosome_depth`, where depth is sequenced reference-derived bases divided by replicon length. Record target and realised values separately. Call this a relative coverage panel: library preparation and sampling can make observed depth differ from biological copy number.

Begin with one plasmid at a time. Then use selected multiple-plasmid cases with unequal depths to test whether one well-covered plasmid masks loss of another. Preserve the chromosome read file across paired comparisons where possible. Also vary absolute chromosome depth in a separate panel: the same ratio can describe very different amounts of evidence.

### S3. Determinism and thread sensitivity

Use byte-identical reads, fixed configuration, pinned software and the same machine/environment. Start with five independent executions at one thread, then five at each of two supported multi-thread settings. Keep assembler seeds fixed when exposed; record tools that provide no seed control or do not support a requested thread count. Isolate each run so caches and existing outputs cannot substitute for execution.

Compare three levels:

1. Raw output checksums, including FASTA ordering and headers.
2. Normalised sequence content: ignore headers/order; account for reverse complements and rotations of validated circular sequences; preserve duplicate contig multiplicity.
3. Biological outcomes: replicon recovery, fragmentation, joins, copy expansion and sequence errors.

Different raw files can encode the same assembly. Conversely, equal summary scores can hide different sequence or structural errors. Report within-thread repeatability and between-thread equivalence separately. Varying simulation seeds or assembler seeds is a separate robustness experiment, not this determinism test. Repeated agreement is evidence for the tested conditions, not proof of universal determinism.

### S4. Small plasmids

Select naturally occurring plasmids spanning the smallest available sizes. Use reporting bands such as <2 kb, 2–5 kb, 5–10 kb and larger controls; populate only bands supported by curated references and report gaps.

Test each selected small plasmid with its chromosome and, where available, within its native multiple-plasmid complement. Include read-length distributions shorter than, comparable to and longer than the plasmid. Keep small-plasmid input availability separate from assembler recovery.

Specify whether the simulator permits reads to traverse a circular molecule more than once. Such reads must be explicitly labelled; compare a model that limits reads to one circumference rather than silently using long artificial tandem copies. Badread supports circular references and a small-plasmid bias model, but those capabilities require validation against the intended scenario [3].

## Additional scenarios, in priority order

1. **Absolute coverage and sampling variation.** Compare selected low, medium and higher depths at fixed relative coverage, using independent simulated read sets. Record zero-read and incomplete-coverage cases rather than scoring them as unexplained assembler loss.
2. **Read length and preprocessing.** Compare length distributions and unfiltered versus declared filtering/subsampling policies. Measure retained reads and breadth for each plasmid before assembly. This identifies whether a pipeline discards the evidence needed for small-plasmid recovery.
3. **Realistic sequencing errors.** Add documented nanopore error profiles, including a separate assessment of homopolymer-associated errors. Pin simulator models and distinguish sequence accuracy from structural recovery. Error-free results alone cannot establish real-data performance.
4. **Shared repeats.** Use naturally occurring repeat structures shared between plasmids or between a plasmid and chromosome. Assess false joins, repeat collapse and uncertain assignment. Describe repeat length relative to read length and whether distinguishing evidence exists in the input.
5. **Similar co-resident plasmids.** Where supported by natural references, test whether distinct but similar plasmids remain separate. Score both sequence recovery and correct molecule count; shared sequence alone cannot establish which plasmid was recovered.
6. **Circularisation and copy expansion.** Check retained terminal overlap, false closure, missing sequence at the join and whole-plasmid tandem duplication. Report circularity claimed by the assembler separately from sequence support. Include contigs with unknown topology in evaluation without assuming they are circular.
7. **Uneven within-replicon coverage.** Add a labelled challenge panel with local coverage variation. Determine whether failure reflects missing evidence or handling of uneven support.
8. **Read artefacts.** Later, introduce controlled chimeric, adapter-containing or unrelated reads as separate factors. Evaluate incorrect joins and extra contigs before combining artefacts into a realistic profile.
9. **Input ordering and pipeline stages.** Test read-order sensitivity separately from identical-input determinism, and compare raw assembly with any polished output. Keep stage-specific results so a later step cannot hide an earlier failure.
10. **Real-data transfer.** Revisit representative baseline and difficult conditions using real reads with independent reference validation and documented library preparation.

Do not expand every factor into a full Cartesian product. Establish one-factor comparisons first, then select interactions such as small size plus reduced coverage, repeats plus shorter reads, and unequal plasmid depths plus filtering. Publish the scenario list before comparing tools.

## Simulation requirements

Use a simulator adapter so the benchmark is not tied to one program. Badread is a candidate for controlled long-read artefacts [3]; validate exact-mode behaviour rather than assuming a high-quality preset is error-free. Store complete configurations and explicit seeds. A separately validated exact sequence sampler is acceptable for S1.

Before dispatching an assembly, validate the generated dataset against its scenario:

- Confirm reads match the intended source in exact mode, including circular boundary crossings.
- Calculate read counts, length distributions, achieved per-replicon depth and breadth using simulator provenance where possible. Alignments alone can misassign reads in shared repeats.
- Confirm absent replicons contributed no reads and requested present replicons received the intended evidence.
- Check input identifiers are unique and record quality-score conventions.
- Mark scenarios that miss configured sampling tolerances as invalid inputs, preserving their diagnostics.

Use the same frozen read files for every assembler in a comparison. Repeat simulation with independent seeds to measure sampling variability separately from repeated execution on fixed reads. Never infer simulator truth from an assembler's output.

## Platform workflow

Implement a command-line batch workflow first, with a generated static HTML report and machine-readable exports. An interactive application can consume the same results later.

The workflow comprises reference validation, scenario expansion, simulation or real-data ingestion, input validation, isolated assembler execution, evaluation and reporting. Separate these stages so adding real reads does not require changes to the evaluator.

Assembler adapters must declare the executable/version, environment or container digest, supported input type, command/configuration, seed support, thread settings, resource limits and expected output files. Capture standard output/error, exit status, elapsed time and peak memory. Preserve FASTA and assembly graphs when emitted. Do not assume all assemblers expose the same options.

Start with published recommended settings appropriate to the declared read type. Record any deviations. Treat tuned settings as a distinct benchmark entry and retain a held-out reference panel for final comparisons. Assembler selection and versions remain an implementation decision; this specification makes no performance recommendation.

Cache by checksums and full configuration, support resumption, and distinguish success, crash, timeout, resource exhaustion, unsupported configuration, invalid input and evaluation failure. An empty assembly is an observed outcome, not a successful recovery. Retain unsuccessful runs in the report.

## Evaluation and outcome definitions

Evaluate against **all truth replicons together** to detect chromosome–plasmid joins and ambiguous matches. Use circular-aware alignments, union reference coverage and explicit contig-to-replicon relationships. Preserve alternative matches in shared regions rather than forcing a unique assignment. QUAST can provide supplementary assembly metrics [4]; plasmid-specific checks are still required.

For each truth plasmid, report:

- Fraction of reference bases recovered, counting each reference position once.
- Aligned identity, substitutions and indels, with denominator and alignment filters stated.
- Number of contributing contigs and whether a dedicated contig represents one complete molecule.
- Structural disagreements, false joins and sequence assigned to other replicons.
- Missing sequence, extra sequence, duplicated intervals and whole-molecule expansion.
- Claimed circularity and independently evaluated circular consistency.
- Assignment certainty, with reasons for ambiguity.

Use two strict simulation endpoints: exact one-molecule sequence recovery, allowing rotation/reverse complement for circular truth, and exact recovery with correct topology supported. A contig without a circularity claim can satisfy the first while topology remains unknown. Realistic-read panels must also report continuous metrics and use versioned, predeclared tolerance-based categories. Freeze those tolerances after evaluator validation and before tool comparisons; do not label approximate recovery as exact.

Report sequence recovery as absent, partial or complete under the declared rule. Record fragmentation, merges, duplication, structural errors and ambiguity as additional flags, since failures can overlap. Define a correctly resolved plasmid as a complete dedicated molecule meeting the declared sequence and structural criteria, without a false join or copy expansion. Shared sequence coverage by itself does not meet this definition.

At dataset level, report correctly resolved plasmids / truth plasmids, chromosome recovery separately, and unsupported extra plasmid-like outputs. For chromosome-only controls, plasmid recall is not applicable; report false-positive output instead. Do not equate every extra contig with a plasmid. Avoid a single overall score dominated by chromosome length or high-copy plasmids.

Aggregate by species, reference, scenario, size and coverage. Present both pooled counts and per-reference summaries. Keep biological references, independent read simulations and repeated assembler executions as separate replication levels. Include failures in denominators for end-to-end completion and provide conditional accuracy among completed runs separately.

## Reports and storage

The report must show the scenario configuration, input evidence per replicon, per-plasmid outcomes, chromosome outcomes, failures, resource use and determinism comparisons. Provide filters for species, reference, tool/version, scenario, plasmid size and achieved depth. Link each result to logs, configuration and output artefacts.

Export versioned JSON and TSV with stable identifiers for reference, scenario, read set, tool configuration, execution and replicon result. Store large reads and assemblies outside Git; retain manifests, checksums and retrieval instructions in the repository. Record schema and evaluator versions so results can be regenerated and compared after evaluator changes.

## Real datasets

Use the same scenario and result model with `data_origin` identifying simulated or real data. For real data, record raw-read accessions/checksums, isolate linkage, platform/chemistry, basecaller and version where available, library preparation, filtering and reference validation evidence. Mark unavailable metadata explicitly.

Prefer orthogonal validation and matched isolate material. A reference built only by the assembler being assessed is not independent truth. Account for biological differences between cultures and reference uncertainty; adjudicate disagreements rather than automatically calling every difference an assembly error. Do not claim biological plasmid absence solely from missing long-read coverage. Report real-data results separately from simulations and retain unresolved cases.

## First implementation and acceptance criteria

The first milestone should deliver:

1. Curated, pinned reference manifests for both species and a documented selection review.
2. S1–S4 scenario manifests, including their controls and explicit unsupported combinations.
3. Validated exact-read generation and per-replicon input checks.
4. At least two assembler adapters, selected and versioned before execution.
5. A circular-aware evaluator checked against simple computational fixtures: exact recovery, rotated/reverse-complemented circles, missing plasmids, fragments, false joins, duplicate contigs, tandem copies and ambiguous shared sequence.
6. Determinism comparisons that distinguish file differences from sequence and outcome differences.
7. A reproducible report and machine-readable results that retain failures.

Numerical recovery thresholds, simulation profiles, the final reference list, assembler versions and resource budgets must be agreed and frozen before comparative runs. They are configuration decisions, not implied completed work. Realistic-error panels and real-data ingestion follow after the core evaluator and input checks pass.

## Sources

These sources support data provenance and candidate tool capabilities. The scenario panel and acceptance criteria above are project proposals.

1. [NCBI Datasets: download a genome data package](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/how-tos/genomes/download-genome/).
2. [NCBI Datasets: genome assembly report](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/data-reports/genome-assembly/) and [NCBI genome files and assembly reports](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/data-processing/policies-annotation/genomeftp/).
3. [Badread documentation](https://github.com/rrwick/Badread), including circular references, per-reference depth and small-plasmid bias. Defaults and high-quality presets should not be treated as an exact-read specification.
4. [QUAST documentation and source](https://github.com/ablab/quast).
