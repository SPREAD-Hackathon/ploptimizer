# Study decisions and implementation status

Review date: 4 November 2026. The study question is defined. The previous specification left the following choices open, so it was not yet an executable experiment plan. Recommendations here are proposals, not approvals or completed work.

**Pilot update:** the user requested an executable first case on BMRC, with Pixi,
Python automation and a static site on Vercel. `config/pilot.json` now records the
operational S1 choices: E. coli W, exact lognormal reads at 30×, seed 20261104,
four tool entries/four threads and the strict sequence endpoint. [RUNNING.md](RUNNING.md)
describes that limited pilot. Decisions below still apply to expansion beyond it.

## 1. Pilot scope and reference admission

**Define:** which assemblies pass sequence/provenance checks; exact plasmid subsets; whether linear plasmids are in the first release or a follow-up; whether a <2 kb example is required before the pilot.

**Recommendation:** validate the five preferred references, use native complements and derived subsets, and report S5 as a separate extension. Record the small-plasmid size gap. Hold the two ambiguous-base alternatives until their treatment is settled.

**Record:** admitted accession versions, sequence checksums, exclusions and a finite reference/scenario list.

## 2. Simulation and input policy

**Define:** exact-read generator; absolute chromosome depth; read-length distribution; quality-score convention; coverage tolerance; whether reads may traverse a circular plasmid more than once; and the first realistic nanopore profile.

**Recommendation:** validate exact sampling first, fix one depth and length profile for S1/S2, and use the proposed relative-depth ratios. Declare circle-boundary behaviour. Check per-replicon read counts, depth and breadth. Keep realistic errors in a separate panel.

**Record:** a versioned simulation configuration with explicit seeds and input validation rules. Simulator defaults do not settle these choices.

## 3. Tool configurations and comparison fairness

**Define:** tool/component/database versions, input modes, internal filtering, chromosome-size priors and polishing policy. Decide how any Plassembler whole-genome result reconciles its initial and final outputs.

**Recommendation:** use the four proposed entries with published input-appropriate settings. Retain Plassembler's initial Flye assembly for a paired comparison; report final plasmids separately. Make additional polishing a distinct stage.

**Record:** pinned configurations, including supported thread/seed controls. Database annotations must not substitute for sequence-based truth.

## 4. Repeats, thread counts and run budget

**Define:** simulation seeds/replicate count; executions per fixed read set; supported thread counts; hardware; memory/time limits; and which cases receive repeated execution.

**Recommendation:** assess determinism on a representative subset, using five repeated executions per tested thread setting as the existing proposal. Run the full panel once per independent read set. Calculate the resulting run count and cost before expanding.

**Record:** the run matrix and resource limits. Sampling variation, within-thread repeatability and between-thread differences need separate comparisons.

## 5. Scoring and evaluator validation

**Define:** alignment method/filters; exact recovery and topology rules; tolerant thresholds for realistic reads; treatment of shared sequence, terminal overlap, fragmented/merged contigs and unsupported extras.

**Recommendation:** retain exact one-molecule recovery plus continuous per-plasmid metrics and overlapping error flags. Validate the evaluator on known missing, fragmented, duplicated, falsely joined and rotated/reverse-complemented outputs before comparing tools.

**Record:** versioned metric definitions and computational fixtures. Freeze tolerant thresholds before inspecting comparative results. Linear molecules retain their ends and do not receive circular-rotation equivalence.

## 6. Execution, storage and first deliverable

**Define:** workflow runner, execution host, large-data location, result schema and minimum report.

**Recommendation:** start with a resumable batch workflow and static report backed by JSON/TSV. Capture provenance, failures, runtime and memory; leave interactive UI work for later.

**Record:** storage/retrieval conventions and pilot acceptance criteria: validated references and reads, a frozen run matrix, a checked evaluator and one reproducible report. Later real-data ingestion must retain isolate/read linkage and reference uncertainty.

**S1/S2 expansion update (4 November 2026):** `config/next-stages.json` now freezes the five-reference panel and relative-depth ratios, with 32 cases and 128 comparisons submitted. All 19 input records passed sequence-integrity checks. This does not settle independent biological validation, repeated/thread runs, realistic errors, partial-recovery scoring or linear-plasmid admission. GenomicX shared components now style the Vercel report; a bounded per-batch collector can publish progress automatically.
