# Comparisons of existing outputs

The existing S6 batch `20261104T210453` now has supplementary NUCmer coordinate
evidence for all 12 completed executions. These comparisons use the existing
reference and assembly files. They do not regenerate reads, rerun assemblers,
edit contigs or replace the original strict/tolerant assessments.

The isolated environment in `environments/coordinate-comparison/` pins
MUMmer4 4.0.1 and retains its Pixi lockfile. The worker records the actual NUCmer
version and arguments, input execution/reference/assembly hashes, environment and
worker hashes, original endpoint outcome, and output checksums. Input hashes are
checked before and after comparison; original execution metadata are not written.

## Task planning

From the repository root, select a fresh label to retain previous comparisons:

```sh
python3 assembly-benchmark/scripts/plan_existing_comparisons.py \
  --batch 20261104T210453 \
  --label s6-nucmer-comparison-v2 \
  --output assembly-benchmark/.cache/comparisons/s6-nucmer-comparison-v2/tasks.json
```

The planner binds the frozen snapshot to actual completed execution metadata. It
does not run tools or submit jobs. Transfer the generated manifest, worker and
pinned environment together to the configured BMRC working directory. Install
the isolated environment before running its locked worker in a Slurm job with
one CPU per task:

```text
pixi run --locked --manifest-path environments/coordinate-comparison/pixi.toml \
  python scripts/compare_existing_outputs.py --manifest <task-manifest> \
  --index <Slurm-array-index>
```

The worker uses ordinary default NUCmer comparison settings with one worker,
followed by `show-coords -THrl`. There is no delta filtering, assembly correction,
new endpoint scoring or software-cause inference.

## Completed artefacts

Results are under
`runs/20261104T210453/comparisons/20261105-s6-nucmer-v1/`. Each scenario/tool has
`comparison.json`, `coordinates.tsv`, and small stdout/stderr logs. Root task and
submission records identify the run; `provenance/` retains the exact worker and
environment files used. Original nucleotide files and delta products remain on
BMRC, outside Git and publication.

All 12 comparisons completed, producing 966 coordinate rows. Setup job:
`34418603`; checked example: `34418636_0`; remaining tasks: `34418659_1–11`, capped
at four concurrent jobs. Approximately 0.6 MB of small artefacts were collected.
All source/input, coordinate-file, worker and environment-lock hashes passed
verification. The original execution records and exact scores remain unchanged.

The original table retains 1-based inclusive endpoints. Canonical JSON rows use
explicitly labelled 0-based half-open intervals and retain reference/query IDs,
lengths, strand and recorded identity percentage. Do not interchange conventions.

These are NUCmer alignment spans, not a per-base difference-event table. They do
not establish exact recovery, molecular topology or an assembler-internal cause.
Their settings differ from the older minimap2 PAF evidence, so keep the actual
mapper and policy labels. Reporting must bind each sidecar to its matching
batch/scenario/tool and input hashes before displaying it.
