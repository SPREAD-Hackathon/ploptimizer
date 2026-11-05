# Standard graph and final-output length metrics

`recorded-length-distributions-v1` is exported for every result, independently of
its exact score, repeatability group or scenario family. It reports graph segments
and scored-output contigs as separate inventories: count, total bp, minimum,
median, maximum, N50, N90 and individual ID/length rows. No length filtering is
applied; short and unaligned contigs remain included.

N50/N90 are the segment/contig length at which descending cumulative lengths reach
50%/90% of the relevant inventory's total bp. They are not per-record percentiles,
reference-normalised NG statistics, recovery measurements or pass/fail criteria.
A high N50 can accompany a merged or duplicated output. Small-plasmid losses may
barely affect a chromosome-dominated N50; retain molecule-specific recovery.

Graph segments are counted once per GFA S record, regardless of orientation or
path reuse. Their raw sum does not subtract link overlaps or multiply repeated
path traversals. It is not an estimate of unique genome size, nor expected to equal
final FASTA size. Preserve final/intermediate/component source roles; a graph
retained from a stopped execution is not a successful final assembly.

## Backend workflow

After an assembly batch finishes, on the cluster run:

```sh
pixi run --locked -e default python scripts/collect_length_inventories.py --batch runs/BATCH_ID
```

This reads only existing scored FASTAs, emits IDs/lengths and hashes into
`length_inventory.json` beside each original execution, checks the full inventory
against the saved contig count, and leaves sequences/executions unchanged. It
checks the assembly hash before and after collection. An empty scored FASTA is a
verified zero-contig output; a missing file is an error, never zero.

Collect those small sidecars and the existing execution metadata into local
`runs/`, then use the normal backend export:

```sh
python benchmark.py export --batch BATCH_ID --recorded-artifacts runs --output .cache/bundles/RESULT_ID
```

Export validates sidecars against the original execution and scored assembly hash.
A complete source-bound final tool inventory is a fallback when no sidecar exists.
It never infers a complete assembly from the aligned-contig subset. Unknown segment
lengths or incomplete graph parsing suppress full-length aggregate statistics.
Missing evidence is null/not-collected, not zero. Source data remain unmodified.

The backend bundle contains `length-metrics.tsv`, per-result JSON inventories and
Markdown summaries; all are available without the website. The website only
presents this model. Existing bundles without the additive model still render.

## This update's audit

Slurm metadata-collection job **34423267** completed (exit 0, 26 seconds), extracting
268 scored inventories across the four primary batches plus the historical pilot.
No simulations, assemblies or alignments were rerun. There are 284 displayed result
records: 268 complete scored-contig inventories and 16 unavailable (12 historical
unsubmitted cells plus four tool errors). Of 284 graph inventories, 204 are complete
and 80 were not collected. Some saved graphs are intermediate/stopped-run artefacts;
source roles remain explicit. Missing Raven graphs cannot be recreated from contig
FASTA alone; future runs must request a graph if supported.
