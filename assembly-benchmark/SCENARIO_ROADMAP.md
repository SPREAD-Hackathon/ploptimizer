# Next work after the revised baseline

Updated 6 November 2026. All work stays inside `assembly-benchmark`.
Current execution state is in `evidence/large-baseline-v3/status.json` and the
ignored suite checkpoint. The initial 168-execution suite is complete. New
scenario designs below are proposals, not evidence of further execution.

## 1. Completed revised-baseline release

All 168 executions and their evidence jobs completed. S1: 2 exact passes / 6
failures; S2: 30 passes / 10 failures; S3: 40 passes / 80 failures, separately
from repeat agreement. All 168 have saved mapping, graphs, length inventories and
NUCmer comparisons. S3 agreement is verified for all 24 within-setting and 12
across-thread groups; the report and scientific slides were published and
verified. See `CURRENT_RELEASE.json` and `evidence/large-baseline-v3/`.

Historical small-plasmid results remain available separately. Later reporting
scope corrections do not change the original outputs or scores. New proposed
panels do not imply new simulations, assemblies or job submissions.

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

## S7 — read-order sensitivity

The requested [S7 specification](S7_READ_ORDER.md) keeps the read multiset fixed
and compares assembler outputs across original and shuffled input orders. Repeats
within each order distinguish ordinary variability from between-order differences.
The bounded first proposal is 48 executions on one existing larger-plasmid input:
four orders, three repeats, four configurations at fixed threads/default modes.
`config/read-order.proposed.json` records the source provenance and design.

Input multiset checks must retain duplicate records and quality strings. Primary
output comparison must be reference-independent, including its treatment of
circular starts; exact recovery remains supporting context. Permutation admission,
independent comparison and grouping/reporting need validation before execution.
No S7 read shuffles or assembly jobs have been generated.

## S5 reference replacement — native linear genomes

The active S5 selection is now the three complete assemblies linked by
CP108065.1, CP108676.1 and CP109243.1. Their five deposited replicons are all
annotated linear. Standard/long read arms define six inputs and 24 executions;
no replacement jobs have been submitted. Exact terminal repeat coordinates/type
remain unassigned, so long reads are not labelled repeat-spanning. See
`LINEAR_TERMINAL_REPEATS.md` and `references/streptomyces-linear-panel.json`.
The isolated SCP1/SLP2 profile and original scores remain historical.
