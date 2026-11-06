# S7 read-order run checkpoint

Batch **20261106T134415**, completed 6 November 2026: **48/48 executions**. This is a separate
48-execution diagnostic panel, not part of the broad 50-dataset benchmark.

| Stage | Slurm job |
| --- | --- |
| Environment checks and four frozen orders | 34523669 |
| Flye (default), 12 tasks | 34523670 |
| Flye (`--meta`), 12 tasks | 34523671 |
| Raven, 12 tasks | 34523672 |
| Plassembler, 12 tasks | 34523674 |
| Collect comparisons and standalone report | 34523675 |
| Verify retained-chromosome topology from saved outputs | 34524603 |

The input stage completed and admitted **15,397 records per order**. All four
orders have one identical record-multiset fingerprint and four distinct
order-sensitive fingerprints. The original compressed read hash matches the
existing S3 source. All repeats share their order’s identical read bytes.
See `evidence/read-order-v1/input-verification.json`.

Every assembler array is independent after input admission, with no artificial
ordering. Plassembler requests a two-hour allocation; other assemblers retain
four hours. The array cap is 1000. No new reads are simulated and no tool
parameters change between orders/repeats. The remote source root is isolated
at `/well/aanensen/users/rva470/ploptimizer/assembly-benchmark/.s7`.

Use `python3 scripts/read_order.py collect` from `assembly-benchmark` to retrieve
small JSON/TSV/HTML evidence and job metadata; it does not copy sequence files
or rerun assemblies. Actual state is in `evidence/read-order-v1/status.json`.
Repeated `submit` calls return the existing checkpoint rather than creating
new jobs. A changed configuration or partial submission stops for inspection.

## Reporting handoff

The backend produces `runs/20261106T134415/summary.json` and
`runs/20261106T134415/report/` (HTML, JSON and TSV). The report stage completed
after all four assembly arrays; the independent chromosome topology review
also completed without rerunning assemblies. It distinguishes within-order variation
from order-associated differences and keeps reference recovery secondary.

This side work does not overwrite the parent chat’s active S5/broad-performance
publisher, Vercel deployment or shared render functions. The website integration
should consume the completed summary through `pipeline/read_order_report.py`,
call `render(summary, output_directory, public=True)` to retain only HTML/TSV
in public output (backend JSON stays outside Vercel), retain S7 as output
agreement rather than exact-reference pass/fail, and include
its input-order evidence. Production publication is not claimed by this
checkpoint. All existing scored results remain unchanged.

Input FASTQ files and assemblies remain on BMRC while execution and diagnostics
need them. They have not been deleted; the read-retention policy still requires
verified restoration before automatic cleanup.

## Verification and preservation

`evidence/read-order-v1/release-qa.json` verifies all 48 unique execution/input/
signature bindings, fixed four-thread groups and all 12 exact retained-chromosome
links to saved initial Flye metadata. The original normaliser and controller
source bytes are retained under `evidence/read-order-v1/source/`, matching the
submission and input-generator hashes. Reporting refinements did not change the
read permutations, assembler commands, scored outputs or primary end-sensitive
signatures. Original chromosome signatures are retained alongside their reviewed
rotation-aware view. All 12 local regression tests pass.

The ready public report contains HTML and two TSV files, **60,952 bytes** at
verified export.
Backend JSON remains separate. See `public-report-files.json` for exact current
bytes/hashes and `RESULTS.md` for scientific interpretation. No website deployment
was performed by this isolated S7 work.
