# Release status and completion checklist

Audit: **5 November 2026, 00:07 UTC** (01:07 CET). Counts below are
a dated snapshot, not a claim that the whole study has finished. This QA used
existing metadata, logs and tests; no new sequence analysis or experiment ran.

## Completed and pending

1. **Pilot — `20261104T183058`: complete.** Four submitted comparisons: one strict
   pass, three strict fails and four completed diagnostics. Twelve additional
   `not_run` snapshot cells were never submitted and are excluded.
2. **S1/S2 — `20261104T190455`: complete.** All 128 comparisons scored: 55 strict
   passes and 73 strict fails, with 128 completed diagnostics. Final report and
   diagnostic jobs completed successfully. Totals include chromosome controls;
   they are not a tool ranking or a plasmid-only recovery rate.
3. **S4 — `20261104T193551`: terminal.** Six passes, 38 strict fails and four
   execution errors across 48 comparisons. All 44 scored executions have completed
   diagnostics. Report and diagnostic jobs completed successfully.
4. **S3 — `20261104T193612`: running.** Audited local snapshot: 40/80 executions
   scored, four running and 36 pending. Final diagnostics wait for assembly.
5. **S6 — `20261104T210453`: inputs ready.** Three read sets passed admission.
   Twelve comparisons wait behind S3; tolerant assessment/reporting must follow.
   No noisy-read comparison or tolerant outcome was available at this audit.

The S4 errors are Plassembler's short-length cases: W/pRK2, W/native,
MGH78578/pKPN7 and MGH78578/native. Logs show initial Flye completion followed by
“No chromosome was identified”. This establishes the exit condition, not the
underlying cause. Keep these unscored errors visible; do not silently alter
parameters or count them as strict fails.

Live JSON endpoints were accessible. S1/S2 and S4 matched terminal counts; live
S3 showed a one-cycle publication lag during the audit. Collected scheduler metadata
confirmed S3 running and S6 waiting. The bounded publisher reported `following`.
Later snapshots can legitimately differ from this dated audit.

## What the scores establish

- Strict pass means every expected plasmid is recovered exactly once as a
  dedicated molecule, allowing circular rotation/reverse complement.
  Chromosome-only controls use separate endpoints.
- Strict fail is an assessed sequence outcome, not necessarily complete plasmid
  loss. Errors, timeouts, invalid inputs and unfinished jobs remain unscored.
- Alignment diagnostics are supplementary, with mapping/repeat/origin limits;
  their thresholds do not define tolerant recovery or establish physical topology.
- Tolerant recovery is separate, bounded to supported small pRK2/pKPN7 cases;
  ambiguous assignments remain unscored and exact scores are preserved.

See [RECOVERY_DIAGNOSTICS.md](RECOVERY_DIAGNOSTICS.md),
[TOLERANT_ENDPOINT.md](TOLERANT_ENDPOINT.md),
[RAVEN_CAUSE_REVIEW.md](RAVEN_CAUSE_REVIEW.md) and
[FLYE_HYPOTHESES.md](FLYE_HYPOTHESES.md). Pilot causal evidence does not establish
general real-read or linear-plasmid performance.

## Partial repeatability findings

At the audit, eight of 16 within-thread groups had all five executions scored on
identical inputs; all eight agreed at byte, normalised-sequence and strict-outcome
levels. Four of eight across-thread groups were complete, all W/pRK2:

- Flye: bytes differed; normalised sequence and strict outcome agreed.
- Flye uneven coverage: bytes and normalised sequence differed; strict outcome
  agreed.
- Raven and Plassembler: all three signatures agreed.

Incomplete agreement flags remain null. Repeatability can mean consistent failure;
one fixed read set does not establish guaranteed determinism. Only exact
truth-matched circles receive rotation normalisation, so differing normalised
hashes are not automatically classified biological errors.

## Machine-readable completion gate

```sh
python3 scripts/check_release.py \
  --batch 20261104T190455 --batch 20261104T193551 \
  --batch 20261104T193612 --batch 20261104T210453 \
  --output .cache/release/status-check.json
```

This reads fixed `runs/BATCH/tasks.json`, publication snapshots and collected
accounting only. It does not collect, rerun, build, commit or deploy. Exit 0 means
evidence-ready; exit 1 means pending or blocked. `jobs_finished` is separate from
`release_ready`: completed jobs with missing diagnostics/assessments are not ready.
Task matching includes repeat identity, threads and repeat number. Planned but
unsubmitted `not_run` rows are excluded. Terminal tool errors retain their exit
explanations and review items; they are never converted into strict fails.
Unscored tolerant outcomes can be reported with a reason and matching provenance.

The current check reports S1/S2 and S4 ready, S3/S6 in progress. It checks input
admission, required stage completion, evidence availability/provenance, repeat
summary completeness and recorded failure explanations. A recorded endpoint/exit
explanation is not automatically a confirmed biological cause. Evidence-ready
also does not mean frontend QA, publication or a source commit has completed.
Each terminal non-pass also requires a structured symptom, interpretation,
confidence/scope and supporting evidence. Repeating the exact-pass criterion alone
does not satisfy the failure-explanation gate; an explicitly unresolved cause does.

## Remaining release work

- [x] S1/S2 and S4 terminal records/diagnostics collected, with four S4 errors
  preserved outside strict pass/fail counts.
- [x] S6 input admission complete; pending results remain explicitly pending.
- [x] Reporting integration: 181 Python tests pass, with 11 explicit skips for
  unavailable optional dependencies; eight metadata-only release-gate tests pass.
  HTTP checks cover 78 routes and 284 comparison cells across five batches.
  The live build generated at `2026-11-05T00:09:42+00:00` matched all 408 public
  files byte-for-byte. Browser checks confirmed failure explanations and no page
  overflow in the narrow results pane. This verifies that reporting build, not
  the unfinished S3/S6 scientific outcomes.
- [ ] Complete S3, final diagnostics and every repeatability group.
- [ ] Complete S6 assembly and provenance-matched tolerant assessment; preserve
  uncertainty and separate strict/tolerant outcomes.
- [ ] Recollect, freeze final snapshots and pass the evidence gate above.
- [ ] Run integration/frontend/browser QA, publish, then verify every served
  public file against the chosen static build:

```sh
python3 scripts/verify_publication.py \
  https://ploptimizer-assembly-benchmark.vercel.app \
  --output .cache/release/live-verification.json
```

- [ ] Commit the intended source, docs and small snapshots after final review.
  The publisher collects/snapshots/deploys; it does **not** commit source itself.

One bounded publisher owns this site and requires the controller's SSH/network
session. A separate 30-minute completion heartbeat checks meaningful progress
and final reporting/QA, staying quiet while pending state is unchanged; it is
not permission to start new scientific experiments. [RUNNING.md](RUNNING.md)
describes restart and collection. Large reads/assemblies remain on BMRC;
configuration, package/source provenance and hashes retain the reproducibility
trail. Final completion requires both evidence readiness and verified publication,
not simply an empty scheduler queue or a successful local build.
