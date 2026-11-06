# S7 read-order sensitivity: completed results

Batch `20261106T134415`: **48 successful software executions**, four input
orders × three repeats × four configurations, all at four threads/default mode.
All orders contain the same 15,397 complete FASTQ records, including qualities
and duplicate multiplicities, with distinct verified order fingerprints.

| Configuration | Ends retained | Tool-labelled circular representation |
| --- | --- | --- |
| Flye (default) | Seven variants; same-order repeats vary | One output across all 12 runs; no order effect observed |
| Flye (`--meta`) | Seven variants; same-order repeats vary | Three variants; same-order variation prevents specific attribution to order |
| Raven | Four outputs; each order's three repeats agree | Not available for all contigs; four-versus-six contig counts establish a genuine output difference |
| Plassembler | Three outputs; each order's three repeats agree | One output across all 12 runs; differences are chromosome start representations |

Plassembler's final plasmid sequences match across orders. Its retained
chromosome was linked by exact whole-sequence identity to the saved initial
Flye contig and its circularity label; this comparison never used the reference.
Original end-sensitive results and the prior unknown-topology view are retained.
The reviewed circular normalisation does not change the primary signatures.

Reference recovery is secondary: 24 passes and 24 failures are recorded,
independently of output agreement. Stable but wrong assemblies still count
as agreement in S7. Raven's four outputs have respectively six, four, six
and four contigs; their underlying assembly-internal mechanisms and coordinate
differences have not been investigated here.

## Artefacts

- `report/index.html`: verified compact HTML report with agreement matrices.
- `report/runs.tsv`, `report/orders.tsv`: portable run and input tables.
- `summary.json`: complete backend measurements and per-run provenance.
- `status.json`: job IDs, completion and publication state.
- `input-verification.json`: identical read multiset, distinct orders and shared repeat inputs.
- `release-qa.json`: all 48 execution/signature/hash bindings and all 12 retained-chromosome links.
- `implementation-validation.json`: 12 passing tests and source hashes.
- `public-report-files.json`: exact compact HTML/TSV export hashes and byte counts.
- `source/`: original worker sources and the saved-output topology-review script.

The standalone HTML/TSV report is generated at
`runs/20261106T134415/report/`; a lean public preview is in
`.cache/sites/s7-read-order-preview/`. Neither location is a production URL.
Live-site integration remains with the active publisher; this work does not
overwrite its build or deployment.
