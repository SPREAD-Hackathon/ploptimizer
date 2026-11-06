# Reporting release: results and limits

## Current production — revised large-plasmid suite live and verified

https://ploptimizer-assembly-benchmark.vercel.app is live from source `0c306c7`,
deployment `dpl_BLTAw99T8G1U1C3JGWyBGrn5EJfX`. All 1,111 publicly served
pages, assets and downloads match the reviewed build byte-for-byte, with zero
failures. Nine Vercel routing configuration files are not public download targets.
Live browser checks confirm the mobile assembler selector without page overflow,
S3 mode/thread tables, completed NUCmer plots and the retained pKPN5 base changes.

All 168 revised-suite executions and their evidence jobs completed: **72 exact
passes / 96 exact failures**, with no execution errors. All 168 have mappings,
graphs, length inventories and NUCmer plots. S3 repeatability is reported
separately: 23/24 within-setting groups and 9/12 across-thread groups agree in
normalised sequence signatures. Deterministic Flye configurations agree in all
8 within-setting and 4 across-thread groups. All recorded comparison inputs agree
in hash. Signature differences do not by themselves locate a sequence change.

The overview includes the verified new snapshots while retaining historical
supplementary results. The build is 53,679,735 bytes, below the unchanged 64 MiB
budget. Current plus two previous READY deployments are retained. Large backend
files stay outside the deployed presentation build. All 468 source records and
original scores are preserved; no assemblies were retried or tuned during QA.

The existing native 12-slide scientific deck now includes final S3 results and
updated notes. Visual and structural QA pass, preserving the S1/S2 tables and
historical pKPN5 case. See `evidence/large-baseline-v3/`, `LARGE_BASELINE_RUNS.md`
and `CURRENT_RELEASE.json` for source bindings, denominators and verification.

Material limits: many failures still lack reviewed per-base differences or a
confirmed software-internal mechanism; real within-node reference boundaries
remain unmeasured; synthetic cases from two reference complements do not establish
general real-read performance. Exact scores and repeat agreement answer separate
questions. This completes the bounded run/report/presentation release.

## Historical reporting releases and follow-up record

Entries below retain their original dates and describe the release state at that
time. Their pending-work and older production statements are superseded by the
current production entry above.

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

## Path-free final graphs and Plassembler scope (5 November)

The pKPN7 3× Plassembler result was already an exact plasmid pass. Its final GFA
has one segment/self-link but no P record; the old path-only origin model left
that segment incorrectly unassigned in the viewer. Verified whole-segment/contig
sequence hashes now support an origin without inventing a path. Segment `1` and
scored contig `1` match over all 3,478 bp and associate with NC_009653.1. Matching
identity evidence is available when selecting the node. Ambiguous cases stay grey.

Plassembler result pages distinguish input chromosome context from the final
plasmid-only score and graph. The initial Flye chromosome assessment and separately
retained chromosome file are identified when recorded. The tool summary's
chromosome row is explicitly outside the plasmid score. Expected output is labelled
“Expected plasmid output”. Original assessment fields and graph downloads remain
unchanged across all 284 result records.

Metadata collection and provenance are documented in GRAPH_COLLECTION.md. The
complete Python suite ran 310 tests with 11 optional skips and no failures, followed
by expanded focused identity/scope tests. Graph-model checks and HTTP checks for
376 routes/284 result views passed. Browser checks verified the reviewed node
label and selectable whole-segment identity evidence.

## Missing-graph integrity audit (5 November)

Read-only Slurm job 34423949 audited 894 distinct existing files across 272
submitted executions, with zero integrity issues. All 50 input manifests/read
files/truth FASTAs, 268 scored assembly FASTAs and 204 saved graphs matched their
recorded hashes. All 68 completed Raven execution directories contain no GFA;
their recorded commands did not request graph output. The 12 historical unrun
cells are classified separately. See [INTEGRITY_AUDIT.md](INTEGRITY_AUDIT.md) and
its committed machine-readable plan/results/provenance.

The site distinguishes graph output not requested from missing, invalid,
unsupported or unrun evidence, and removes the duplicate generic missing-source
message. Future Raven commands request an isolated `assembly_graph.gfa`; no
historic execution, input, output or score was overwritten, and no assembly was
rerun. Existing historical Raven graphs remain unavailable.

Verification: 316 Python tests ran, 11 optional skips, no failures; graph tests
passed. All 284 original result records remain unchanged outside derived report
fields. Audit plan and producer hashes were checked against the committed sources.

## S5 backend completed (5 November)

The main Python entry point now runs the isolated linear reference controls,
including pinned terminal curation, no-wrap reads with explicit end coverage,
strict linear equivalence, diagnostics and standalone reporting. The successful
cluster batch **20261105T161510** completed all four simulations, 16 assembly
executions, diagnostics, graph/length/identity metadata and report generation.
All required Slurm stages completed with exit 0. All 16 strict sequence outcomes
failed; none are process errors. These are isolated reference-record controls,
not native chromosome/plasmid complements or validated physical-end standards.

See [S5_RUN_STATUS.md](S5_RUN_STATUS.md) for exact observed differences, job IDs,
limitations and reproduction commands. The public cohort adds these 16 records
without changing earlier execution scores. New totals: 284 primary executions,
84 pass, 196 fail, four errors (280 scored), plus the unchanged historical pilot.

S5 publication: deployment `dpl_Egjp23QfLZTYyYtQPXtCbNsqm6hQ`; all 2,266
public files passed byte-for-byte verification, with no failed downloads. The
321-test suite passed with 11 optional skips; eight cohort tests and 6,923 local
links passed. All 300 source records retain their original fields.

## Revised baseline reporting (5 November)

Policy `large-plasmid-baseline-v2` excludes inputs containing any plasmid below
20 kb from S1–S3 headline counts. No reference, read, assembly, alignment or
original score changed. S1 retains 52 eligible executions (35 pass, 17 fail).
The other 36 S1, all 40 S2 and all 80 S3 executions remain supplementary.
The revised multiple-larger-plasmid S1, larger-plasmid S2 and S3 panels are
unassessed. S4–S6 are unchanged. See [BASELINE_POLICY.md](BASELINE_POLICY.md).

Verification: 323 tests ran successfully with 11 optional skips; 6,923 local links
resolve and original source fields are preserved across all 300 result views.
Production deployment `dpl_4WFGpYXj8HRTCMKNeh1FnfnobeLw` passed byte-for-byte
checks for all 2,266 public files, including downloads. Evidence is saved in
`evidence/baseline-v2/`. No reference replacement or new cluster job was performed.

## Aggregate figure reporting (5 November)

The metadata-only backend export now produces 37 aggregate figures across seven
measured scenario/cohort groups: exact outcomes, plasmid size/achieved depth,
recorded breadth and alignment-weighted identity, elapsed time/peak memory,
input distributions, and separate S3 repeatability. SVG/PNG figures, measurement
rows, missingness and original identities are packaged in the backend ZIP.
The website consumes those products at `/aggregate`.

Primary and supplementary groups stay separate; S3 repeats do not enter recovery
or resource distributions. Wick longest-alignment contiguity, compatible terminal
gap/overlap and maximum-indel distributions remain unmeasured. The page links all
11 original Wick figure sets with attribution and a pinned repository revision.
Dataset generation, references and all scientific scores remain unchanged.
See [AGGREGATE_PLOTS.md](AGGREGATE_PLOTS.md) for metric definitions, the simulation
design comparison and the proposed separate general-evaluation track.

Verification: the 326-test suite passed with 11 optional skips; six focused bundle
tests passed after the axis fixes. All 7,492 local links resolve, 74 plot-file hashes
match their indexes, and all 300 frozen source records retain their original
fields. Desktop/phone checks confirm contained figure scrolling; independent
review scored both named axis fixes resolved. Evidence is in `evidence/aggregate-v1/`.

Production deployment `dpl_ixNY2CitKwnNsCjEc1m9kb1PTpMY` passed byte-for-byte
checks for all 2,347 public files. One initial DNS lookup failure passed a targeted
retry; both initial and final verification records are retained. Live browser
checks confirmed the aggregate navigation, baseline cohort and loaded figures.

## History page removed (5 November)

Removed the history index and its navigation/about/scenario references. Old root
and archived history URLs redirect to the results overview. Archived result
routes and downloads remain generated; all 300 result pages remain present.
Eight focused report tests passed and 7,031 local links resolve.

## Presentation-only storage and graph-origin evidence (5 November)

Ready locally and source-tested; **not yet published**. The compact website is
47,068,824 bytes (47.1 MB), down from the original 314,876,802 bytes (85% smaller).
It retains all 300 result views, plots, tables and interactive graphs. Full batch,
result and graph JSON downloads, duplicate Markdown reports and the backend ZIP
are excluded from Vercel. Shared batch CSS/JS/fonts use one root asset directory.
The full validated backend remains unchanged; its 1,280-member archive is written
beside the source bundle, outside the website. See [WEB_DOWNLOADS.md](WEB_DOWNLOADS.md).

Graph nodes distinguish whole-segment identity, saved exact-contig-path inference
and ambiguous/unassigned evidence. Saved contig/reference spans are displayed
when bound to the same source hashes. No new alignment or internal boundary
measurement is implied. This is repackaging existing evidence; no cluster job,
simulation, sequence analysis or assembly rerun was performed.

Verification: 330 Python tests passed with 11 optional skips; the final 10
focused packaging/bundle/publication tests and graph tests passed. Four
publication tests also verify the presentation-only manifest fallback. HTTP checks
cover 398 routes and 300 result views across six batch reports. Original scores
and source records are preserved. All 1,280 archive members match their backend
files. Earlier gzip-only size evidence is superseded by the lean verification.

Storage cleanup is complete: 63 old deployments removed using explicit deployment
IDs and Vercel's safe mode. Three READY versions remain: live plus two rollback
versions. The canonical deployment remains `dpl_88jLqrtApY8UA4WHC6Q314RFnuRB`;
live overview, scenarios, W result and aggregate pages returned HTTP 200 after
cleanup. Exact team-billed storage usage was not available and is not claimed.

Publishing is blocked by Vercel's separate daily upload quota (`api-upload-free`,
CLI: more than 5,000; retry in 24 hours). A stalled archive attempt was removed;
the old production remains live. Do not claim the compact build or new graph
labels are live until deployment and byte-for-byte verification succeed. Evidence
and the publishing checkpoint are in `evidence/storage-origin-v1/`.

## Recorded node intervals and table navigation (5 November)

Implemented locally; production publication remains blocked by Vercel's existing
`api-upload-free` daily upload quota. No cluster jobs or sequence analyses were
performed. All 300 original source records and scores remain unchanged.

The metadata-only backend validates optional source-bound graph-node/reference
interval records and exports partitioned display spans. Different-reference
overlap and explicitly ambiguous support stay grey; uncovered spans have no
recorded support. Original alignment rows remain intact without interpolating
reference coordinates. The viewer exposes coloured portions by default, with
direct selection, an accessible dropdown and source/quality evidence. Whole-node
and path fallback remains when intervals are missing. **None of the frozen real
records currently supplies direct node intervals.** Synthetic previews prove the
interface only and are excluded from Vercel. See
[NODE_INTERVAL_EVIDENCE.md](NODE_INTERVAL_EVIDENCE.md).

Individual runs and case summaries have progressive search, relevant dropdown
filters, natural/numeric header sorting, reset, live counts and empty results.
Repeatability groups and long contig/length inventories also gain controls. Small
headline matrices remain unchanged; no-JavaScript tables retain all their rows.

Verification: 335 Python tests passed (11 optional skips), graph/table helper
tests passed, and HTTP checks cover 398 routes / 300 result views. Browser checks
verified combined filters, reset, sorting and all interval evidence states.
A caught pointer-capture issue was fixed and direct portion clicks rechecked.
Evidence: `evidence/node-intervals-tables-v1/local-verification.json`.

[SCENARIO_ROADMAP.md](SCENARIO_ROADMAP.md) records revised S1/S2/S3 gaps and the
bounded completed S5/S6 panels. This readiness review does not implement or submit
a new biological scenario panel.

Independent finish review: **ship** for the locally reviewed dark-mode desktop/phone
UI. Documentation updated; no claim of light-theme visual verification or live
publication is implied.

## Horizontal matrix scrolling (5 November)

Fixed the top-left Scenario family header so it stays pinned with the scenario
row labels while assembler columns scroll horizontally. It uses the existing
opaque header surface and a higher stacking order. No result, count or score
changed. Browser checks at 390 px verified aligned header/body positions at a
partial swipe and the far-right end, in dark and light themes; desktop was also
checked at 1440 px. See `evidence/heatmap-scroll-v1/local-verification.json`.
This fix remains in the local build pending the previously quota-blocked publish.

## Failure facts and guarded static releases (5 November)

Implemented and verified locally; no cluster work, sequence analyses or deployment
attempts. Production remains unchanged after the previously reported Vercel quota
block. The new bundle is `.cache/bundles/failure-release-v2`.

Near-verdict failure facts now show recorded excess, reference/output lengths and
existing coordinate intervals when the saved review matches scenario, tool, exact
status and assembly/truth hashes. The same binding protects verdict descriptions,
confidence wording, detail records and exported checked facts. Unbound verified
flags cannot earn a checked mismatch claim. Four saved failure reviews support
confirmed observations; 195 other failure views remain unresolved. No mechanism
or missing sequence event is invented, and all 300 original records/scores remain
unchanged. The reviewer approved the scoped desktop/phone UI after the shared
binding fix; DESIGN.md documents the distinction.

`render` automatically checks local links/anchors, build-size budgets and forbidden
backend artefacts, then records generated-file hashes. `check-site` additionally
checks the render receipt, source snapshots, original fields and plot/origin
bindings. `deploy-site` requires that gate and uses the configured Vercel project
with an archive upload. Direct legacy deployment is rejected before rebuilding
or mutating snapshots. See [STATIC_RELEASE.md](STATIC_RELEASE.md).

Verification: 347 Python tests passed (11 optional skips), followed by 26 focused
checks and HTTP verification of 398 routes / 300 result views. The static gate
checked 8,005 links/anchors, preserved all 300 source records, and passed at
47,278,887 bytes against a 64 MiB budget. Negative tests cover broken links, large
files, changed scores, stale evidence, changed HTML/ignore rules and blocked
deployment. Evidence: `evidence/failure-release-v2/`.

## Phone matrix replacement — published and verified

The earlier sticky-corner fix did not solve partial-column clipping. It has been
replaced on narrow screens with an assembler selector and two fitting columns.
All original assembler cells, values and evidence links remain in the source;
desktop keeps the full matrix. The caption and long repeatability counts wrap
without being chopped. Source data and scores are unchanged.

Reviewed at 320/390 px in dark/light themes, 800 px and1440 px; all four choices
were exercised at390 px. Production verification passed all1086 published files,
and browser checks confirmed the new selector and no clipped cells. Current plus
two previous READY deployments remain. Evidence: `evidence/mobile-matrix-v2/`.

## Saved mismatch counts — published and verified

The pKPN5/Plassembler page now explicitly reports two base mismatches from its
saved alignment, equal 88,582 bp reference/output lengths, no gap operations in
those saved rows and an exact initial Flye assessment. Mismatch positions, from/to
bases and assembler-internal cause remain unknown. The same scalar-count summary
is exported in JSON/Markdown; coordinate TSV edit counts are retained. No new
alignment or sequence analysis was performed, and original scores are unchanged.

Metadata eligibility requires matching input/PAF hashes, a single failed required
molecule/pair, full disjoint spans, consistent gap-free count fields, and no exact
copy/assignment-failure ambiguity. Arbitrary sequence-bearing tags remain ignored.
See [RECORDED_MISMATCH_COUNTS.md](RECORDED_MISMATCH_COUNTS.md).

Verification: 352 Python tests passed (11 optional skips); 22 focused checks and
HTTP checks of 398 routes/300 results passed. Production byte checks covered all
1,086 published files. One initial DNS lookup failure passed an exact-byte retry;
both initial and final evidence are retained. Desktop/phone UI review approved
the reporting scope. Current plus two previous READY deployments are retained.
Evidence: `evidence/mismatch-counts-v2/`.

## 2026-11-06 — Saved post-Flye process history published

Source `44ab2d8`, deployment `dpl_AzEuTLfdWVyGust6LHufoDKdz93o`. The pKPN5 report now explains that additional read processing and separate plasmid reconstruction followed the exact initial Flye assessment. The note is bound to saved execution, assembly, reference and log hashes. The report does not identify a causal substep, changed positions or nucleotide changes. No sequence analysis or cluster jobs were performed.

QA: 353 tests passed (11 optional skips), local gate 399 pages / 8,005 links / 300 original records preserved; target production page and site manifest matched local bytes. Current static build is 47,328,355 bytes.

## 2026-11-06 — pKPN5 base changes directly verified and published

The earlier count-only limitation is superseded for this case. Routine comparison of existing saved FASTAs confirms NC_009651.1 substitutions 39,984 T → C and 77,230 A → G (1-based reference-forward coordinates), at final output positions 11,045 and 48,291. Both molecules are 88,582 bp; the exact score remains fail.

Initial Flye is directly verified exact. Unicycler graph 004 also has exact circular reference equivalence. Graph 006 and the saved Unicycler final FASTA match the final Plassembler sequence. Graph bridging/cleanup occurs between the saved graph checkpoints; the particular responsible operation remains unresolved. See `BASE_REVIEW.md`, the hash-bound review in `reviews/bases/`, and the retained Unicycler log in `reviews/evidence/`.

Source c0f2334 deployed as dpl_DAup8G3GKC6scMu3qm8k6Wb4Mi2q. QA: 358 tests (11 optional skips), 11 focused checks, HTTP E2E 398 routes / 300 result views; final gate 399 HTML / 8,005 links / 300 original source records preserved. All 1,086 published files verified byte-for-byte. Build 47,329,638 bytes; current plus two previous READY deployments retained. No assembly or alignment reruns and no cluster jobs were submitted.

## 2026-11-06 — Revised baseline suite running (not a completed release)

The authorised 168-execution replacement suite is submitted with source
`fa47838`. Current batches and assembly/evidence job IDs:

- S1 `20261106T042103`: 8 assemblies, array `34499379`, evidence `34499381`.
- S2 `20261106T042108`: 40 assemblies, array `34499388`, evidence `34499390`.
- S3 `20261106T042113`: 120 assemblies, array `34499396`, evidence `34499398`.

Preparation passed 364 tests under the actual pinned Python 3.11 interpreter
(11 optional skips), and read generation is running. Assembly arrays are ordered
across batches and limited to four active tasks. Evidence jobs collect saved
graphs/lengths, run supplementary mapping, freeze source snapshots and run NUCmer.
The current live release and headline cohort remain unchanged while these jobs
are pending. Detailed status and the cancelled pre-assembly compatibility attempt
are retained in `evidence/large-baseline-v3/`; see `LARGE_BASELINE_RUNS.md`.

The follow-up `finish-large-plasmid-benchmark-panels` will collect and verify the
suite before updating the live report. Publication must consume the completed
NUCmer comparison roots for the new cases; ensure the plots actually select those
NUCmer coordinates while preserving saved PAF evidence for mismatch counts. The
specific software causes must not be inferred from recovery scores alone. Never
silently relabel pending/error outcomes as passes or rerun with tuned parameters.

### 6 November, 04:50 UTC follow-up — S1 complete; suite still running

S1 `20261106T042103` completed all 8 executions (2 exact pass, 6 exact fail),
8 supplementary mappings, 8 saved graphs, 8 length inventories and 8 NUCmer
comparisons. Its frozen snapshot is retained unchanged in `published/`.
S2 is assembling; S3 remains dependency-queued. No new biological runs or retries
were submitted during this follow-up, and the live release remains unchanged.

Repaired comparison provenance packaging: copied existing environment manifests
and the unchanged comparison script into S1's provenance directory and updated
the evidence worker to package them for subsequent batches. No alignments or
assemblies were rerun. Export now selects explicitly supplied, validated completed
NUCmer coordinates for plotting while retaining separate PAF evidence for mismatch
counts and direct base reviews. Invalid NUCmer sidecars retain a valid saved PAF
fallback. Regression checks cover this separation.

S1-only QA: all 8 plots consume recorded NUCmer coordinates; 17 HTML pages / 308
local links pass the release gate, preserving all 8 original records. The updated
365-test suite passes with 11 optional skips. See
`evidence/large-baseline-v3/s1-qa.json`. Publish only after the whole suite and final
compact-site budget are verified.

### 6 November, 06:20 UTC follow-up — S2 complete; S3 running

S2 `20261106T042108` completed all 40 executions (30 exact pass, 10 exact fail)
and its evidence job completed 40 mappings, graphs, length inventories and NUCmer
comparisons. Its unchanged frozen snapshot is retained in `published/`.
S2-only export selects all 40 recorded NUCmer plots; QA passes 57 HTML pages,
1,132 links and all 40 preserved source records. Matched coverage controls and
S1/S3 frozen input hashes are recorded in `input-audit.json`.

S3 has started its independent repeats and remains incomplete. No duplicate runs,
parameter changes or retries were submitted. The production report and headline
cohort remain unchanged until the complete suite passes final QA, including the
compact website's byte and file-count budgets. See
`evidence/large-baseline-v3/s2-qa.json`.

### 6 November — S3 scheduler concurrency increased

Following the user’s request to accelerate progress, S3 array `34499396` was
raised from four to eight simultaneous existing tasks. Slurm verified eight
active tasks; every task still reserves four CPUs / 16 GB and retains its
configured one- or four-thread assembler setting. No new tasks, input changes,
parameter changes or assembly retries were introduced. The scheduler adjustment
and verification are retained in `evidence/large-baseline-v3/scheduler-adjustment.json`.

### 6 November — scheduler policy corrected to the user’s 1,000-job cap

At the user’s explicit instruction, S3 array `34499396` now has a verified
`ArrayTaskThrottle=1000`. Slurm allocates nodes according to account, partition
and resource availability; the controller no longer imposes a low running-task
cap. Four CPUs / 16 GB remain reserved per task, and each assembler retains its
fixed one- or four-thread setting. No tasks were duplicated or biological
settings changed. The eight-job adjustment above is superseded.

The controller cluster configuration and example now use 1,000. Future suite
submissions also omit artificial cross-batch assembly ordering, retaining input
and environment-preparation dependencies. Actual scheduler verification and
running-task count are in `evidence/large-baseline-v3/scheduler-policy-1000.json`.

### 6 November, 07:53 UTC follow-up — final five S3 runs active; compact-site preparation

S3 has 115 completed execution records and five one-thread Plassembler runs still
active. A scheduler resource check confirms active CPU consumption; no execution
failure or user action is indicated. The evidence job remains dependency-queued.
No runs or alignments were duplicated and no benchmark parameters changed.

Prepared public-asset deduplication for the larger report: byte-identical SVG/PNG
figures and TSV tables share a content-addressed static file, while each result
page, source binding and backend record remain distinct. Links are rewritten
using their own base URL; external links and inert graph JSON are preserved.
This is a presentation-only storage change, not a new biological calculation.

An unpublished preflight containing the 348 historical/S1/S2 source records
passes the gate: 48,813,775 bytes, 969 public files, 471 HTML pages, 9,439 local
links, no errors. Sharing removes 359 duplicate files / 3,814,484 bytes. All 366
Python tests pass (11 optional skips), plus HTTP E2E checks over 470 routes and
348 result views. The HTTP checks now derive expected counts from the declared
cohort and frozen source records and accept explicit repeat-mode identities,
instead of hard-coding the original release totals. Production and its cohort
remain unchanged until the complete suite and updated presentation are verified.
See `evidence/large-baseline-v3/shared-assets-preflight.json`.

### 6 November, 08:32 UTC follow-up — all assemblies finished; evidence processing pending

All 168 revised-suite executions now have terminal scientific outcomes: 72 exact
passes and 96 exact failures, with no execution errors. S3 contributes 40 passes
and 80 failures; these reference scores remain separate from repeatability.
Slurm reports assembly array 34499396 completed successfully. Its evidence job
34499398 is running; the source snapshot, coordinate export, release QA and
publication are not yet complete.

The saved S3 execution records account for all 120 repeats. All 24 within-thread
and 12 across-thread groups have identical recorded input hashes. Normalised
sequence signatures agree in 23/24 within-thread groups and 9/12 across-thread
groups. The within-thread exception is SE11 Flye (`--meta`), default mode, four
threads. Across-thread exceptions are MGH78578 Flye default mode, MGH78578 Flye
(`--meta`) default mode, and SE11 Flye (`--meta`) default mode. All four Flye
configuration/input groups in deterministic mode agree across one and four
threads. Every group agrees in the recorded strict biological signature.

These are comparisons of existing recorded signatures, not a localisation of
sequence differences. Non-exact circular outputs retain their ends during
normalisation; differing signatures alone do not establish the type or cause of
a change. Byte agreement remains a separate metric. The source-file hashes and
mode/thread denominators are retained in `s3-repeatability-audit.json`.
The live report and presentation remain unchanged pending final evidence QA.

### 6 November — completed suite ready for publication

All 168 authorised executions and evidence calculations completed without tool
execution errors: S1 2 pass / 6 fail; S2 30 pass / 10 fail; S3 40 pass / 80 fail.
Every new execution has recorded mapping, graph, length inventory and NUCmer
coordinates. The unchanged snapshots are admitted to the overview cohort; the
earlier small-plasmid baseline inputs remain supplementary. S3 headlines show
repeat agreement, separately from exact reference recovery.

Final local QA passes 368 Python tests (11 optional skips), graph/coordinate
parser checks, 598 HTTP routes / 468 result views across nine batch views,
599 HTML pages and 12,476 local links. All 468 original source records are
preserved. The compact build is 53,679,735 bytes / 1,120 public files, below
the unchanged 64 MiB / 1,500-file budgets. Mobile checks exercise all four
assembler selectors without page overflow; repeated-run pages use the completed
NUCmer plots, and the reviewed pKPN5 substitutions remain present.

The existing 12-slide scientific presentation now includes the complete S3
assessment. Its two changed visible slides were visually reviewed; the other
ten are pixel-identical to the reviewed delivery. Native issue checks report
zero findings. Source, review and QA hashes are retained in `presentation-qa.json`.

Two generic reporting issues were repaired: the readiness gate now distinguishes
repeat modes, and the coordinate importer follows the producer's repeated-run
output layout while separately verifying original execution metadata. Regression
checks cover both. No assemblies or alignments were rerun during release QA.
Production is not declared updated until the deployment and public byte checks
finish; see the current production entry and `CURRENT_RELEASE.json`.
