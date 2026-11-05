# Scenario coverage and remaining definitions

Reviewed against the saved release records and existing specifications on
5 November 2026. This is a reporting/readiness review, not a new executable
biological scenario panel. Original scores and cohorts remain unchanged.

The priority is to complete the existing promises before adding more families.

| Priority | Family | Current evidence | Definition or reporting still needed |
| --- | --- | --- | --- |
| 1 | S1 ordinary recovery | 52 eligible saved executions; chromosome-only and individual larger-plasmid controls | The chromosome plus multiple plasmids, all ≥20 kb, baseline remains unassessed. Keep it separate from saved mixed-size supplementary cases. |
| 1 | S2 relative coverage | 40 saved executions, all supplementary under the revised size policy | The larger-plasmid matched panel is unassessed. A coverage comparison must retain the other declared input properties. |
| 1 | S3 repeatability | 80 historical executions; supplementary fixed-input comparisons | The larger-plasmid default/deterministic-mode matrix is unassessed. `determinism-modes.json` still names the historical small-plasmid cases, so it is not ready to represent the revised baseline. Define agreement within each mode/thread group and separately across thread settings; reference recovery is secondary. |
| 2 | S4 small plasmids | Saved read-length challenge panel | Clearly distinguish target read length from achieved distributions and document the simulation's molecule-length cap. Avoid presenting it as a real library validation. |
| 2 | S5 linear terminal repeats | Completed bounded batch, 16 assembly tasks; see S5_RUN_STATUS.md | Keep physical-end/reference uncertainty and the isolated-control scope visible. Existing broad development notes describing S5 as entirely unrun are stale. |
| 2 | S6 noisy reads | Completed bounded smoke panel, 12 comparisons | Preserve separate exact and tolerant endpoints. The proposed broader design and real-read validation are not completed. |

## Cross-scenario acceptance criteria

Before interpreting any category as covered, declare its endpoint, comparison
unit, expected output scope, source identity and unavailable measurements. Distinct
questions need distinct fields:

- Recovery: which expected molecules have a dedicated exact copy?
- Continuity: what recorded span is reconstructed in a single output segment?
- Repeatability: do repeated executions on identical inputs agree?
- Origin evidence: which recorded node intervals support each reference?
- Output overlap: which output intervals repeat or overlap one another?
- Execution outcome: did the tool finish, fail, time out or produce an invalid result?

These should not be collapsed into one pass/fail score. Plassembler's final
plasmid-only scope must remain explicit. Absence of a graph is an evidence gap,
not corruption or a scientific recovery failure by itself.

## Useful later additions

A tool-version regression comparison and matched real-data validation would add
value after the existing coverage gaps are addressed. Both require independently
declared comparisons and reference uncertainty. They are proposals, not new
implemented or submitted experiments. No new biological runs or sequence
analyses were performed for this review.
