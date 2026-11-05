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

## Expected output and interactive graph comparison

Result pages now pair the frozen reference inventory with the recorded GFA.
Chromosomes and plasmids show their declared topology, names and lengths;
Plassembler's final target contains plasmids only. Unknown topology is not drawn
as circular. Reference sizes are schematic, and graph shape introduces no new
score or reference-to-segment assignment.

Graphs up to 300 segments use a deterministic bounded force layout. Segments can
be dragged, the background panned, and the view fitted or reset. Larger graphs
retain every segment in a grid; the existing 2,102-segment example was checked.
Source nodes, link orientations, paths, provenance and all scientific outcomes
remain unchanged. Tests cover reference inventory/topology, immutable graph
records, force geometry and the large-graph fallback.

NUCmer benchmark plots are **not generated**. No NUCmer jobs or new sequence
alignments were run. A separate, explicitly labelled local viewer accepts
existing eleven-column coordinate tables; only toy coordinates were used for
parser and browser rendering tests. It does not attach local previews to a run
or substitute them for benchmark evidence. See [NUCMER_PLOTS.md](NUCMER_PLOTS.md).

Verification: 251 Python tests (11 skips, no failures), graph and coordinate
parser tests, 376 local routes/284 result views, node drag/reset, responsive
comparison and local toy-file rendering. Production deployment:
`dpl_A68vNQs7S6igPLrT2CEoM6CpsWJQ`.
All published HTML, shared CSS/JS and six example result/graph downloads matched
the reviewed build byte-for-byte: 392 files, no failures.

## Recorded commands

Each result now exposes its saved invocation, recorded tool version and brief
descriptions of the flags actually present. The command link opens this section
directly; paths retain the public `<workdir>` placeholder. Descriptions cite
Flye 2.9.6, Plassembler 1.9.0 and Raven documentation. No defaults or extra flags
are inserted into the saved command.

All 272 recorded commands matched their published execution metadata. The 12
unsubmitted cells explicitly have no recorded command. Four command-view tests
and the 376-route/284-result HTTP checks passed; desktop and phone layouts were
checked. Six representative live pages/assets matched the reviewed build,
including the one-thread repeat view. Deployment:
`dpl_EP1BReR9bBggUEX84DjngiQLtyFb`. Scientific snapshots remain unchanged.

## Reference origin strips and coordinate inspection

The approved origin-strip display is now generated for every result graph.
Reference colours are keyed by accession using the full catalogue, so selecting
a subset of plasmids does not change their colours. Reference schematics use the
same palette. Each coloured strip is supported by a saved exact-contig match and
an explicit GFA path in a complete final graph bound to that scored assembly.
Clicking a node shows the accession, contig, path and orientation. Associations
with multiple references and nodes without supporting paths remain grey.
Intermediate/failed graphs receive no final-reference assignment.

These are whole-segment path associations. Measured internal origin boundaries
are not available, and the mixed-origin demonstration from the local mock-up is
not published as benchmark evidence. Original graph JSON downloads are preserved;
derived associations and their source hashes are separate in result JSON.

The optional local NUCmer coordinate viewer has explicit coordinate windows,
per-alignment focus with 50 bp context, and a paginated table retaining every
alignment row. Coordinate windows are 1-based inclusive. Browser verification
used a toy table only. Benchmark NUCmer coordinates and per-base difference
records remain uncollected. This update does not establish changed bases,
insertion/deletion content or causes of assembly failure.

Validation: 259 Python tests (11 skips, no failures), graph and coordinate tests,
376 routes/284 result views, desktop/dark and phone/light inspections, and toy
coordinate focus. All 128 primary-batch views retain their original exact scores
and graph metadata. No source snapshot, scientific score or scenario changed.

Production deployment: `dpl_5VNLN21i6UPUZhzrXeVzD27HrnMC`. The live W graph
selection was checked, and ten representative public pages, assets and downloads
matched the reviewed build byte-for-byte.

## Separate backend bundle and website renderer

`benchmark.py export` now builds a versioned bundle from existing frozen
publication snapshots. It performs metadata joins and produces JSON, summary and
molecule TSVs, a standalone Markdown report per result, source/producer hashes,
prepared cohort models and available saved-coordinate SVG/TSV artefacts.
Matplotlib is pinned separately in `requirements-reporting.txt`. Export does not
launch assemblies, alignments, sequence analyses or cluster work. `--replace`
stages an updated bundle before replacing a validated generated destination.

`benchmark.py render` validates the bundle and consumes its prepared findings,
origin associations and cohort models. It does not discover runs or publication
snapshots. The existing `report`/`snapshot`/`publish` commands remain compatibility
paths; the production site for this update was built with `render`. A ZIP of the
complete backend output and standalone report downloads are linked from the site.
See [RESULTS_BUNDLE.md](RESULTS_BUNDLE.md).

The W chromosome-only Flye uneven-coverage failure has the sole available
source-bound reviewed coordinate plot in these snapshots. Its full-scale plot
and two terminal windows draw the existing review records. Orange bands mark
intervals already recorded in that review. The page and standalone report show
expected/output lengths, the recorded 13 bp excess, interval convention,
reported circularity, command, source hashes and unresolved internal cause.
This is explicitly not a NUCmer run. Most results still have no reviewed plot;
general base-level difference-event tables and benchmark NUCmer outputs remain
uncollected. Original source fields across all 284 executions are preserved.

Verification: 265 Python tests (11 skips), including deterministic metadata
export, atomic replacement failure, tamper rejection and rendering with backend
collection/interpretation functions blocked. All 376 routes/284 result views
passed; desktop/phone layouts and live example/downloads were checked. The
primary cohort remains 84 pass, 180 fail and 4 errors. Fourteen live pages/assets/
downloads matched the build, and every file inside the downloaded bundle ZIP
matched its manifest. Production: `dpl_HBPT58p33o3TNYmzg5SffPHS7nnM`.

## Alignment plots and detailed reports across completed outputs

The combined backend bundle now includes source-bound plots for every completed
scored output: 264/268 current-cohort executions, including all 180 scientific
failures. Across the historical plus active views, 268/284 have plots. The other
16 views are 12 historical unsubmitted cells and four execution errors.
Five verified empty coordinate files produce explicitly empty plots, rather than
an inferred claim that the biological sequence is absent.

Sources are labelled separately: 255 saved minimap2 PAF displays, one existing
reviewed-coordinate display, and 12 completed NUCmer 4.0.1 show-coords displays.
The NUCmer comparison stage used the existing S6 reference/assembly outputs and
retained its isolated Pixi environment, input/source/output hashes and logs.
Its 966 coordinate rows and all 12 original inclusive TSV downloads verified.
No original assembly, endpoint, execution record or source snapshot was changed.

Generic metadata import checks frozen input identities, execution/input-manifest
hashes, task/snapshot binding, worker/environment hashes, coordinate files and
small logs. It normalizes only recorded coordinates, keeps source metrics in
their original units and sanitizes public command paths. Canonical tables are
0-based half-open; original show-coords downloads remain 1-based inclusive.
Plot panels separate references so small molecules remain visible. The site
consumes the sealed bundle and offers standalone detailed reports and downloads.

Detailed records now separate saved exact outcomes, reported changes and their
confidence/source pointers, circularity claims, supporting evidence and software
cause. General per-base difference-event tables and most software-internal causes
remain unresolved; coordinate spans do not supply those conclusions.

Validation: 285 Python tests (11 skips), 376 routes/284 result views, all original
fields across 284 records unchanged, zero coordinate provenance/hash/parse errors,
and desktop/phone inspection of a newly supplied NUCmer report. The primary
headline remains 84 pass, 180 fail and four errors. See RESULTS_BUNDLE.md and
COMPARISON_BACKEND.md for the separate metadata-export and comparison stages.

Production deployment: `dpl_5yn337MbfX2wkmVVq4ipaGAZGnCW`. All 268 published
SVG plots and 12 representative pages/assets/downloads matched the reviewed build
byte-for-byte. Every file in the downloaded backend ZIP matched its manifest.
Vercel's individual-file upload quota rejected the first attempt; its supported
`--archive=tgz` deployment completed successfully and should be used for this site.

## Reference origin in contig inventories

Contig tables now include accession-coloured chromosome/plasmid names, exact
versus alignment-only labels and expandable source pointers. Ambiguous and
unsupported rows stay grey; final-assembly associations are not applied to
intermediate reports. The same backend metadata is retained in result JSON and
standalone tables. Six focused association tests, existing bundle/result-page
tests and all 376 routes/284 result views passed. Every original source field
across 284 records remained unchanged. Desktop and phone table layouts and
matching-evidence expansion were checked.

Production: `dpl_4mzUBjWMXMxSXFMiwwUCLSvWhdTq`. The live SE11 inventory and its
JSON, standalone report and shared styles matched the reviewed build.

## S3 repeatability and result-page simplification (5 November)

S3 overview cells now count identical/different/not-assessed repeat groups using
saved normalised-sequence comparisons, rather than reference-recovery scores.
Within-setting and across-thread comparisons are separate, with mode labels;
reference recovery remains available under its own disclosure. Original exact
scores and source fields are unchanged for all 284 historical/current views.

`config/determinism-modes.json` adds the requested default/explicit-deterministic
matrix at one/four threads, with five repeats per setting (120 tasks). Only direct
Flye configurations receive the verified `--deterministic` flag. No new jobs were
submitted: published S3 evidence still covers default mode only. See
[S3_REPEATABILITY.md](S3_REPEATABILITY.md) for definitions and capability sources.

Result pages now show a single outcome headline, without the duplicate exact
status badge. Command, flag descriptions and run provenance share one collapsed
section. Reporting verification: 301 Python tests ran with 11 optional-dependency
skips and no failures; HTTP checks passed for 376 routes and 284 result views.

## Standard length metrics and benchmark review (5 November)

Reviewed Wick/Holt version 4 and its supporting repository. The comparison and
prioritised plan are in [BENCHMARK_DEVELOPMENT.md](BENCHMARK_DEVELOPMENT.md).
[LINEAR_TERMINAL_REPEATS.md](LINEAR_TERMINAL_REPEATS.md) adds pinned SCP1/SLP2
candidates with terminal inverted repeats, explicitly distinct from tandem repeats.
They remain proposed and unadmitted; no new biological scenarios were run.

Metadata-only Slurm job 34423267 completed in 26 seconds with exit 0, collecting
268 complete scored FASTA length inventories from the existing five batches.
No assemblies, simulations or alignments were rerun. The backend now exports
length statistics independently of the web layer, including all unaligned and
short contigs. Of 284 displayed records, 268 have scored-contig inventories and
204 have graph-segment inventories; missing evidence remains unavailable. Saved
graph roles retain final/intermediate distinctions. Five empty scored outputs
are measured zeros rather than missing inventories. Definitions and reproduction
are in [LENGTH_METRICS.md](LENGTH_METRICS.md).

Verification: 307 Python tests ran, 11 optional-dependency skips, no failures;
HTTP checks passed for 376 routes and 284 result views. All original source-result
fields were preserved across 284 records. The TSV has 568 inventory rows (two per
result). Browser inspection covered the length table and phone-width overflow.
