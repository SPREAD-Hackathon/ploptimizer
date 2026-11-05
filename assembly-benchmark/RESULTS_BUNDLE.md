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
overview.json            prepared primary-cohort overview
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
boundaries. The optional browser NUCmer viewer accepts a different format with
1-based inclusive endpoints; these formats must not be interchanged.

Most results have no such reviewed coordinate records. Their standalone reports
state that plotting evidence is missing. General per-base difference-event tables
and benchmark NUCmer coordinates remain uncollected. The schema does not pretend
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
