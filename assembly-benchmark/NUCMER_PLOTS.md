# NUCmer coordinate plotting

Benchmark NUCmer plots have **not been generated**. No NUCmer jobs were submitted,
and no new reference/assembly or self-alignments were performed for this change.
The results pages retain an explicit missing-data state.

Each result has an optional local viewer for an existing `show-coords -THrl`
table: eleven tab-separated fields containing reference/query endpoints, spans,
identity, sequence lengths and reference/query identifiers. Coordinates remain
1-based and inclusive in the parsed records. The drawing places base positions
on cumulative reference/query axes and preserves both orientations. Reference
and query filters isolate sequence pairs. No alignment rows are silently sampled.

Files stay in the browser and are not uploaded or attached to the benchmark.
Local previews do not change scores. Only sequence identifiers present in the
coordinate file appear on the axes; unaligned molecules cannot be inferred from
this format alone. These coordinate spans do not display individual mismatches.
Inputs are bounded to 20 MiB, 50,000 alignment rows and 5,000 sequences per axis.
Unsupported formats, conflicting lengths and out-of-range coordinates are rejected.

The supplied workbook performs assembly self-alignment and uses additional
contig-specific repeat-unit analysis. That analysis was not incorporated into the
report. Reference-versus-assembly and assembly-versus-itself are distinct views
and must retain their actual input identities and source provenance.

Validation uses toy coordinate tables, not benchmark sequence data:

```sh
npm --prefix website run test:dotplot
```
