# First reporting release: results and limits

**Final evidence audit: 5 November 2026, 01:58 UTC (02:58 CET).** All existing
submitted batches, required diagnostics and tolerant assessments have finished.
The metadata completion gate passes for all four release batches. This completes
the bounded run/report delivery; it does **not** establish a mechanism for every
assembly failure. Unresolved causes remain explicitly unresolved.

[Published results](https://ploptimizer-assembly-benchmark.vercel.app/) ·
[All batches](https://ploptimizer-assembly-benchmark.vercel.app/history.html)

## Final outcomes

- **S1/S2 — `20261104T190455`:** 128 comparisons; 55 exact passes, 73 exact fails.
  All 128 diagnostics completed. Totals include chromosome-only controls with
  separate endpoints; they are not a general assembler ranking.
- **S4 — `20261104T193551`:** 48 comparisons; six exact passes, 38 exact fails and
  four unscored tool errors. All 44 scored outputs have completed diagnostics.
- **S3 — `20261104T193612`:** all 80 executions and final diagnostics completed;
  20 exact passes and 60 exact fails. All 16 within-thread and eight across-thread
  comparison groups have complete, identical-input evidence.
- **S6 smoke — `20261104T210453`:** all three inputs admitted and 12 comparisons
  assessed. Exact endpoint: three passes, nine fails. Separate tolerant endpoint:
  six passes, six fails. These endpoints must not be combined.

The four release batches contain **268 submitted executions**: 84 exact passes,
180 exact fails and four unscored errors. The historical pilot adds four submitted
comparisons (one pass, three fails); its 12 never-submitted cells remain `not_run`
and are excluded from execution totals.

## Failure explanations and remaining uncertainty

Every terminal non-pass has a structured symptom, interpretation, confidence,
scope and supporting evidence in downloadable JSON. The original exact score
remains unchanged. A mapping description is an observation, not a proven cause.

The four S4 Plassembler errors report “No chromosome was identified”. This is an
observed stopping condition, not proof of insufficient depth or missing chromosome
sequence. Their underlying mechanisms remain unresolved, and they stay outside
scientific pass/fail counts.

Existing controlled pilot findings are documented in [FLYE_HYPOTHESES.md](FLYE_HYPOTHESES.md)
and [RAVEN_CAUSE_REVIEW.md](RAVEN_CAUSE_REVIEW.md). Those findings apply to their
reviewed artefacts; they do not establish causes for every Klebsiella or other
panel failure. No new sequence analysis or scientific experiment was run during
this release finalisation.

Other limits remain material:

- Exact failure can reflect a small sequence difference, copy ambiguity or loss;
  the label alone does not distinguish them.
- Mapping can miss short, repeated or circular-origin sequence. No retained
  alignment does not prove physical absence. Candidate structural flags need review.
- Tolerant assessment is bounded to the supported small-plasmid cases. It does
  not establish chromosome recovery or physical topology.
- This release does not establish real-read, chemistry-specific or linear-plasmid
  performance. The larger proposed panels remain unsubmitted.

## Observed repeatability

All 16 within-thread groups agreed in normalised sequence and strict outcome
across five repeats. Fifteen also agreed byte-for-byte; one had differing file
bytes with matching normalised sequences.

Across one and four threads, all eight groups agreed in strict outcome. Seven
agreed in normalised sequence; W/pRK2 Flye-meta differed. File-byte agreement is
reported separately. A consistent failure remains a failure, and these runs do
not prove determinism for other inputs. Only exact truth-matched circles receive
rotation normalisation; a differing normalised hash alone does not identify a
biological or algorithmic cause.

## Verification and reproduction

- Metadata gate: all four batches evidence-ready, with no blockers.
- Reporting code: 181 Python tests ran with 11 optional-dependency skips and no
  failures. This describes the original reporting build; the later graph follow-up
  has separate checks below.
- Final HTTP checks: 78 routes and 284 matrix cells across five published batches;
  all local links resolved. Matrix cells include the pilot's 12 unsubmitted cells.
- Final repeatability and noisy-result headlines matched their saved outcomes.
- Production build generated at `2026-11-05T01:32:05+00:00`: all 408 public files
  matched the local build byte-for-byte. Earlier browser QA checked explanation
  wording and narrow-screen overflow; the finalisation changed results and docs.

```sh
python3 scripts/check_release.py \
  --batch 20261104T190455 --batch 20261104T193551 \
  --batch 20261104T193612 --batch 20261104T210453
npm --prefix website run test:e2e
python3 scripts/verify_publication.py \
  https://ploptimizer-assembly-benchmark.vercel.app
```

The metadata gate requires the frozen task lists and collected accounting under
ignored `runs/`. [RUNNING.md](RUNNING.md) describes collection/reproduction; source,
configuration, package versions and checksums are retained. Large reads,
assemblies, graphs and checkpoints remain on BMRC. The bounded publisher finished
successfully and exited; it does not itself commit snapshots to Git.

## Per-result graphs and circularity follow-up

Every matrix result now opens an individual tool/execution page, linked from its
scenario. These pages separate the exact score, assembler-reported circularity,
contig inventory and interactive GFA topology. Repeated executions retain their
thread/repeat identity. Source roles and checksums are visible; initial graphs
from stopped jobs do not become final-assembly claims.

All 272 submitted executions were checked for existing artefacts. There are 204
collected GFAs, including five empty no-plasmid outputs; the 68 original Raven
runs have no saved GFA. All four stopped Plassembler jobs retain their initial
Flye graphs. Five empty final control summaries provide no circularity claims.
Long inventories collapse so the graph stays findable; graphs can be panned,
zoomed and inspected by segment. Local-file inspection is explicitly separate
from benchmark provenance. No assemblies or alignments were rerun.

The W chromosome-only Flye-meta finding is now directly checked against the saved
FASTA files: `GTCCTGTAGCGGG` occurs at both ends, and excluding either terminal
copy restores exact circular reference equivalence. The original exact fail is
preserved. Flye reports `circ.=Y`; its final graph contains the same overlong
single segment with self-links. This explains the mismatch, not the internal
software mechanism. See [FAILURE_REVIEW.md](FAILURE_REVIEW.md).

Follow-up verification: 228 Python tests ran with 11 optional-dependency skips
and no failures; graph-model tests passed. HTTP checks covered 362 routes and
284 matrix cells. Browser checks covered the real W result, selection/zoom,
phone layout, a 2,102-segment stopped-run graph, and the collected-empty state.
All original scientific status values were checked against the preceding
version and remain unchanged. See [GRAPH_COLLECTION.md](GRAPH_COLLECTION.md)
for collection/reproduction and bounds.

The production build generated at `2026-11-05T07:43:04+00:00` was verified
byte-for-byte across all 1,260 public files, with no mismatches.
