# Backend results bundle

The recommended reporting path is now **export → validate → render**. Export is a
Python metadata calculation over existing frozen snapshots. It
runs no assemblers, mappers, sequence analyses or cluster jobs, and needs neither
Node nor the website. Drawing saved-coordinate figures additionally uses the pinned
Matplotlib dependency in `requirements-reporting.txt`; it performs no sequence
analysis. Render consumes the exported bundle; it does not discover
other source batches or infer new findings/reference origins.

From the repository root (install `requirements-reporting.txt` in your reporting
Python environment first):

```sh
python3 assembly-benchmark/benchmark.py export \
  --batch 20261104T190455 \
  --output assembly-benchmark/.cache/bundles/release-v1

python3 assembly-benchmark/benchmark.py render \
  --bundle assembly-benchmark/.cache/bundles/release-v1 \
  --output assembly-benchmark/dist
```

Use `--replace` on export to rerun into an existing validated generated bundle.
Replacement is staged before swapping directories; invalid inputs do not replace
the previous bundle. Unrecognised or modified destinations are rejected. Use
`--single-batch` for an isolated batch, with its own counting cohort. Without it,
export includes the available frozen publication snapshots, while headline counts
use the explicit cohort in `config/overview.json`. Historical pilots remain
outside the primary counts. A result identity includes batch, scenario, tool and
optional run ID; repeated executions are never silently collapsed.

All CLI bundle/output paths must stay inside `assembly-benchmark/`. The existing
`report`, `snapshot` and `publish` commands remain legacy compatibility paths;
they have not been silently repointed to the new export command. Use `render`
when the website must be driven exclusively by a sealed bundle.

## Bundle layout

```text
manifest.json               version, cohort, source/producer/file hashes
README.md                   readable overall summary and limitations
summary.tsv                 one row per execution, all source batches
molecules.tsv               molecule scores and saved mapping measurements
batches/<batch>.json         source fields plus labelled prepared report evidence
models/<batch>.json          prepared per-batch overview
overview.json               prepared primary-cohort overview
reports/<batch>/<result>.json
reports/<batch>/<result>.md
reports/<batch>/<result>-alignment.svg   only if saved reviewed coordinates exist
reports/<batch>/<result>-alignments.tsv  those same coordinates, unchanged
```

The manifest schema is `schemas/results-bundle-v1.schema.json`. Python validation
also checks identities, source schema versions, assembly/hash associations,
review coordinate bounds, required prepared evidence and every manifested file.
The bundle is deterministic for identical source snapshots, cohort and producer
code. Source timestamps are retained; export does not insert the current time.
Hashes establish integrity and provenance, not independent biological validation.

The original scientific `evaluation`, statuses and graph metadata remain intact.
Derived `report_evidence` contains the outcome description, endpoint molecule
selection, mapping descriptions, whole-segment path associations and plot
availability. Execution errors remain distinct from scientific failures. Export
never reinterprets an unknown measurement as zero or a missing event as a pass.

## Detailed failure example

`20261104T190455 / s1-w-chromosome / flye-meta` has an existing verified review.
The exact output fails; its saved review records a 13 bp duplicated terminal
overlap. The standalone report retains the original criterion and outcome, the
reviewed observation and its input hashes, recorded circularity, command and
unresolved assembler-internal cause.

Its dot plot draws **saved reviewed alignment records**, not a new NUCmer run.
The full-scale view is accompanied by two coordinate windows around the terminal
intervals already present in the review, with 50 bp of display context. Plotting
those coordinates performs no new sequence comparison or breakpoint discovery.
Coordinates in these SVG/TSV products are explicitly 0-based half-open interval
boundaries. The separate development coordinate viewer accepts 1-based inclusive NUCmer
endpoints; it is not mounted on result pages. These formats must not be interchanged.

Most results have no such reviewed coordinate records. Without the explicit
recorded-artifact import below, their reports retain the missing-plot state. General per-base difference-event tables remain uncollected; completed
supplementary NUCmer coordinates are an independent source described below. The schema does not pretend
that every fail has a diagnosed cause or that every graph node has a known origin.

## Website adapter

`pipeline/bundle_render.py` validates the complete bundle before writing pages.
It reuses existing site templates, formatting and graph controls. Prepared
summaries, origin assignments and cohort models come from the bundle. Backend
recomputation is prohibited by tests while rendering. Basic formatting, SVG
layout and display percentages are presentation, not new assessments.

Each result offers its Markdown report. Reviewed-coordinate examples also expose
the backend SVG and raw coordinate TSV. The homepage links a ZIP of the complete
backend bundle plus the two summary tables. The ZIP can be unpacked and inspected
without the site or used as input to a different presentation layer.

## Import already-produced coordinates explicitly

Frozen snapshots contain mapping summaries and original PAF hashes. When those
small PAF and execution-metadata files are already present locally, export can
verify and package their coordinate columns without running an aligner:

```sh
python3 assembly-benchmark/benchmark.py export \
  --batch 20261104T190455 \
  --recorded-artifacts assembly-benchmark/runs \
  --output assembly-benchmark/.cache/bundles/existing-coordinate-report-v1
```

This is an explicit source adapter, not renderer discovery. It checks batch,
scenario/tool/repeat identity, frozen assembly/reference hashes and the frozen
PAF/execution-file hashes. Missing, invalid, mismatched and oversized evidence
have separate states. A verified empty PAF yields a clearly labelled plot with
no recorded rows; it does not establish biological absence. No optional PAF tags
are decoded or exported. All mandatory coordinate rows are drawn, including rows
that the saved measurement filters may exclude; original filtered measurements
and exact scores remain unchanged.

Each expected reference gets its own panel so small references do not disappear
on a chromosome-sized axis. Query axes use cumulative coordinates of identifiers
present in that reference's saved PAF rows; they do not invent an inventory of
unaligned output contigs. Recorded output/circularity inventories are reported
separately. Plot source labels name the actual recorded mapper, never NUCmer
unless a source explicitly establishes that origin.

`report_evidence.failure_details` follows
`schemas/failure-details-v1.schema.json`. It separates the saved outcome, reviewed
change fields, original interpretation/confidence, supporting pointers,
assembler circularity claims, software-cause confidence and evidence availability.
Unrecorded fields have a status and null value. Literal change labels and recorded
excess lengths may be carried from an existing verified review; no events are
inferred from a length discrepancy or a plot. General per-base event tables stay
explicitly uncollected.

`evidence-availability.tsv` has one row per execution view.
`evidence-coverage.json` counts all source views and the declared primary cohort
separately, including plot availability, verified empty plots, source types and
hash/missing states. Neither table is an assembler-quality score. The normalized
plot document contains reference/query inventories, their lengths, original
0-based half-open intervals and strand, source metadata and input hashes. Other
source adapters can target that display contract without changing the renderer.

## Completed coordinate/provenance sidecars

Export can additionally consume an explicitly selected directory of completed
coordinate sidecars. This imports metadata only; it never starts a comparison:

```sh
python3 assembly-benchmark/benchmark.py export \
  --batch 20261104T190455 \
  --recorded-artifacts assembly-benchmark/runs \
  --coordinate-sidecars assembly-benchmark/runs/20261104T210453/comparisons/20261105-s6-nucmer-v1 \
  --output assembly-benchmark/.cache/bundles/combined-coordinate-report-v1
```

The sidecar adapter checks the source snapshot/task manifest, matching frozen
assembly/reference declarations, execution/input-manifest metadata hashes,
worker/environment metadata hashes, original coordinate-table hash and small
log hashes. It reads neither nucleotide inputs nor external delta products.
Canonical rows must equal an independent normalization of the saved eleven-column
`show-coords -THrl` table. Multiple matching tasks, inconsistencies or missing
provenance remain explicit errors rather than selecting a convenient source.

The completed source is labelled with its actual tool/version and supplementary
scope. Its recorded `identity_percent` is preserved. PAF-only values such as
matches, block length and mapQ are unavailable for this source, never invented.
The public normalized metadata retains the original sidecar SHA-256 but replaces
absolute command paths with `<workdir>`; raw private sidecars/task files are not
copied into the public bundle.

The canonical `*-alignments.tsv` headers explicitly identify 0-based starts and
exclusive ends. The separate `*-original-show-coords.tsv` retains the exact
original bytes and 1-based inclusive endpoints. These supplementary coordinates
do not replace the original exact/tolerant assessments or supply a general
per-base event table. Existing reviewed plots keep their original review scope.

## Publishing the rendered site

Use an archive upload for the complete report to avoid Vercel's individual-file
upload quota. With the existing project link retained in `dist/`, from the
repository root:

```sh
npx --yes vercel@65.11.0 deploy --prod --yes --archive=tgz \
  --cwd assembly-benchmark/dist
```

## Contig reference associations

`report_evidence.contig_origins` supplies the reference-origin column in the web
and standalone contig tables. It joins literal contig identifiers in a final,
assembly-hash-bound tool inventory to saved exact-contig checks and accepted
mapping summaries, with verified coordinate rows as a fallback. It does not match
by name suffix or sequence length. Exact matches take precedence; additional
alignment candidates remain in the evidence. A unique alignment association is
labelled alignment-only, multiple unresolved references stay ambiguous/grey, and
intermediate or unsupported inventories remain unassigned. Reference colours use
the same accession catalogue as the graph and expected-molecule displays.
