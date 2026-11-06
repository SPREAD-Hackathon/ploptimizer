# Next work after the revised baseline

Updated 6 November 2026. All work stays inside `assembly-benchmark`.
Current execution state is in `evidence/large-baseline-v3/status.json` and the
ignored suite checkpoint. These priorities do not authorise additional panels or
assembly retries beyond the current 168-execution suite.

## 1. Finish and publish the running suite

S1's two multiple-large-plasmid inputs are complete: eight executions, two exact
passes and six exact failures. S2's larger-plasmid coverage panel is complete:
40 executions, 30 exact passes and ten exact failures. Both have verified saved
graphs, length inventories, mapping evidence and NUCmer coordinates. S3's 120
repeatability executions are running, including explicit Flye deterministic
modes at one and four threads. The scheduler cap is now 1,000 at the user's
instruction; Slurm allocates resources.

Account for all 168 terminal outcomes, preserve any execution errors separately,
verify input hashes and complete repeat groups, and check agreement within each
mode/thread group and across thread settings. Add the verified snapshots to the
headline cohort while retaining historical small-plasmid runs as supplementary.
Export/render the compact report, enforce its byte/file budgets, verify mobile
navigation and downloads, deploy, and verify production bytes before completion.

## 2. Make every failure explain its measured differences

The pKPN5 substitution review establishes the minimum useful example: what was
expected, what came out, exact reference/output coordinates, reference-to-output
base changes and the saved stage where the difference is already present.
Apply a consistent backend format to other failures:

- Substitutions and insertion/deletion events, with lengths and coordinates.
- Missing sequence, extra copies, duplicated circular boundaries, fragmentation
  and joined molecules as distinct observations with supporting evidence.
- Reference-to-output alignments, graph-segment origin intervals and output
  self-alignments as separate comparisons answering separate questions.
- Explicit ambiguous placements when repeats support more than one origin.
- A compact result explanation linked to the event table, relevant plot region,
  graph node and original evidence source.

Retain the exact endpoint and show continuity/sequence-accuracy measurements
alongside it. A two-base substitution failure should be distinguishable from a
missing plasmid. Graph circularity claims remain separate from sequence identity.

## 3. Trace representative failures through saved stages

Start with a representative S1 failure from each assembler/configuration. Compare
existing intermediates and logs, locating the earliest retained output with the
observed discrepancy. Keep three labels distinct: confirmed difference, suspected
mechanism and unresolved cause. Do not diagnose correction, polishing, trimming
or repeat resolution from the final contig alone.

A developer-facing case should include frozen inputs, tool version and exact
command, resource measurements, relevant log excerpts, discrepancy records and
source hashes. Prepare reviewable issue material; do not contact tool authors
without instruction. Identical wrong repeat outputs are repeatable; differing
outputs with the same exact score still need discrepancy-level comparison.

## 4. Make diagnostics part of the normal backend

Preserve one reproducible path from frozen inputs through execution, assessment,
diagnostics and a versioned JSON/TSV results bundle. The website consumes that
bundle. Expand the existing per-base review beyond the hand-reviewed acceptance
case, validating unique alignment assignment before publishing event positions.
Add synthetic fixtures for substitutions, indels, circular rotations, terminal
overlap, missing molecules, duplicated copies and ambiguous repeat placements.
Keep stages independently rerunnable without overwriting scored assemblies.

## Later scenario choices

Select the next bounded panel after inspecting the current failures. Candidate
priorities are shared sequence between molecules, a more focused read-length /
small-plasmid panel, curated linear-end cases with appropriate chromosome context,
and calibrated error profiles followed by matched real reads. State what each
case isolates and keep other input properties fixed.

Existing S4 read-length challenges, S5 isolated linear controls and S6 noisy-read
smoke tests remain available. Broader linear cases require terminal-reference
curation; broader error modelling and real-data validation are not completed.
New scenarios remain proposals until their scope, endpoints, inputs and finite
job counts are explicitly defined and authorised.

## S6 scope correction — separate noise from small-plasmid recovery

Read-error comparisons should use chromosome plus one plasmid ≥20 kb, with no
small plasmids in the selected input. Proposed controls reuse SE11 + pSE11-1 and
MGH78578 + pKPN3 from S2; `config/noisy-large.proposed.json` binds their accessions
and lengths. They are derived subsets, not complete native complements.

The 12 historical W/pRK2 noise runs combine two challenges and remain
supplementary with their original evidence. They do not assess the revised S6.
The replacement has not been run. The current tolerant evaluator only supports
small pRK2/pKPN7 references; larger-plasmid assessment and truth-control validation
are required before converting the proposal into an executable configuration.
Exact recovery alone must not be used as a substitute for noisy-read accuracy and
continuity. Matched clean failures must remain visible rather than being
attributed to noise.
