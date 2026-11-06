# Scenario implementation and execution status

Updated 6 November 2026. Execution and production publication are distinct.
Use the linked evidence checkpoints for live collection state; older proposed
configurations are retained as historical design records.

| Scenario | Implementation / execution | Evidence |
| --- | --- | --- |
| S1: error-free recovery | Implemented and run, including eight revised all-large multiple-plasmid executions and earlier controls. | `evidence/large-baseline-v3/status.json` |
| S2: relative plasmid coverage | Implemented; 40 revised larger-plasmid executions complete. | `evidence/large-baseline-v3/status.json` |
| S3: repeated execution | Implemented; 120 revised runs, mode/thread grouping and agreement assessment complete. | `evidence/large-baseline-v3/status.json` |
| S4: small plasmids / read length | Implemented and run. Original results include execution errors explicitly. | `published/20261104T193551.json` |
| S5: native linear genomes | Implemented. Original 24 outcomes/evidence complete; raw and polished Miniasm follow-ups have six runs each, tracked separately from publication. | `evidence/s5-native-v2/status.json`, `evidence/s5-miniasm-v1/status.json`, `evidence/s5-miniasm-plus-v1/status.json` |
| S6: read errors, larger plasmids | Implemented; 24 executions/evidence complete. Continuous measurements reported; tolerant binary endpoint remains unscored. | `evidence/s6-large-v1/status.json` |
| S7: shuffled input order | Implemented; all 48 executions and backend comparisons complete in `20261106T134415`. Standalone report verified; live publication separate. | `evidence/read-order-v1/status.json` |

Separate from these scenarios, the 50-dataset broad-performance study is a
distinct workstream; its active state is `performance/snapshot.json`.
Shared-repeat challenges, empirically calibrated error profiles and matched
real-read validation remain future proposals, not executed scenarios.

S7's completed design checks were not shuffle/assembly execution. Actual S7
submission and subsequent measurements are now recorded in its own checkpoint.
The original design-only evidence is preserved with its original scope.
