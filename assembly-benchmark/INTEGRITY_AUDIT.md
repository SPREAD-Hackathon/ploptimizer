# Existing-run integrity and missing graphs: 5 November 2026

## Finding

No file-integrity mismatch was found. A read-only Slurm audit (job **34423949**,
38 seconds, exit 0) checked **894 distinct files across 272 submitted executions**:

- 272 original execution records.
- 50 frozen input datasets: input manifest, read file and truth FASTA for each.
- All 268 scored assembly FASTAs, including five verified empty outputs.
- All 204 available saved GFA sources, including retained intermediate graphs.

Every checked file matched its previously recorded checksum. Input manifests
retain valid admission status and their read/truth hashes match execution records.
The four tool errors remain errors; the historical pilot's 12 unsubmitted cells
were excluded. This checks unchanged bytes and saved admission metadata, not the
scientific validity of every simulator assumption or reference genome.

## Why some graphs are unavailable

Every completed record without a collected graph is a Raven execution: **68 runs**
(67 exact failures and one exact pass). All 68 execution directories were inspected
for GFA files; none was present. Their recorded commands contain neither graph
output option. Raven 1.8.3 exposes `-F` for assembly GFA and `-U` for unitig GFA:
[version-pinned command definitions](https://github.com/lbcb-sci/raven/blob/1.8.3/RavenExe/src/main.cc).

This is an omission in the original output-capture setup, not an observed checksum
failure. Assembly FASTA and graph availability are independent. These graphs
cannot be inferred from the contig FASTA. Producing them requires a separately
recorded graph-generating execution or a validated checkpoint-export workflow;
this audit did not run either and did not overwrite historical results.

The report now distinguishes graph output not requested, graph not collected,
unsupported/invalid graph metadata and unsubmitted runs. It no longer repeats the
vague “Source not collected” message in two places. Future standalone Raven
commands explicitly request `assembly_graph.gfa` in each isolated execution
directory. The historical command records and scientific scores are unchanged.

## Evidence and reproduction

[evidence/integrity-audit-20261105/plan.json](evidence/integrity-audit-20261105/plan.json)
freezes the expected metadata checksums and execution inventory.
[results.json](evidence/integrity-audit-20261105/results.json) records each check,
source-plan hash and auditing-script hash. Neither contains nucleotide sequences.

On the cluster, from assembly-benchmark:

```sh
pixi run --locked -e default python scripts/audit_saved_artifacts.py \
  --root . --plan evidence/integrity-audit-20261105/plan.json \
  --output .cache/integrity-audit-results.json
```

The audit reads existing files and returns nonzero for missing files, mismatched
checksums or unreadable records. It never runs assemblers, parses Raven checkpoints
or changes input/output files.
