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

## Compact release overview — 5 November

The homepage now has five scenario-family rows and four assembler columns, with
labelled exact pass/fail counts and a blue–orange heat scale. Job errors remain
separate. Family pages contain genome summaries and individual tool/version/run
links; explanations, circularity and graphs stay on the individual result pages.
Existing case URLs and downloads remain available. S3 repeatability and S6
tolerant assessments retain their separate batch summaries and detailed evidence.

The explicit cohort in `config/overview.json` contains 268 executions: 84 pass,
180 fail and 4 job errors. The scored denominator is 264. The historical pilot is
excluded from the release overview and remains accessible in the archive. Counts
include repeated executions and are not percentages of unique genomes.

This was a presentation-only rebuild from the saved snapshots. No source snapshot,
exact score, evaluation measurement or configuration changed; no compute or
sequence analysis was run. Verification covered 241 Python tests (11 optional
skips, no failures), graph-model checks, 376 local routes and 284 result views
including the pilot's unsubmitted cells. Browser checks covered the overview,
scenario-to-result navigation, saved graph selection and phone layouts in both
themes. The design detector reported no findings.

Production deployment `dpl_6Wcyk4xszi9V359Yn6qRqhG18fpb` is live at
<https://ploptimizer-assembly-benchmark.vercel.app/>. All 1,291 public files,
including downloads, matched the reviewed build byte-for-byte. One transient DNS
lookup failure passed a targeted retry. The source snapshot timestamp remains
`2026-11-05T07:43:04+00:00`; the presentation rebuild does not imply newer runs.

## Evidence-first individual results

Individual result pages now start with the recorded endpoint verdict, name the
molecules that fail that endpoint, and show exact-copy checks beside saved total
aligned coverage. Chromosomes outside a plasmid endpoint are folded supporting
context. Metadata and the original explanation/mapping report are disclosures;
the contigs, graph and downloads remain available. Successful runs no longer
carry the generic unresolved-failure-cause message.

For SE11 / pSE11-5 / Flye uneven coverage, this reports the existing failure to
recover a dedicated exact plasmid copy and 0% retained plasmid alignment. The
saved chromosome coverage is 99.78% across three contigs. Neither zero retained
alignment nor graph topology establishes where plasmid sequence went or the
software-internal cause. The page explicitly retains that unresolved status.

No sequence analysis, scoring, source snapshot or benchmark configuration changed.
Verification: 246 Python tests (11 skips, no failures), targeted summary checks,
376 local routes/284 result views, and desktop/phone inspection of failing and
passing outcomes. Deployment: `dpl_GZrh5SzxAzinc4k3GnNMDXx6Ryym`.
All published HTML, shared CSS and six example result/graph downloads matched
the reviewed build byte-for-byte: 387 files, no failures.
