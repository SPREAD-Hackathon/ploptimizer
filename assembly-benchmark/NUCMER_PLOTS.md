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

## Coordinate windows and small changes

The local viewer now accepts explicit 1-based inclusive windows on each axis.
When all sequences are selected, these are cumulative axis positions. Selecting
one reference and query switches to their own coordinates. Each coordinate row
has a focus action with 50 bp of context, and the full row inventory is paginated
in groups of 25 without dropping records. Invalid ranges hide the plot.

The view exposes coordinate offsets that disappear at genome scale; it does not
classify their cause. Individual substitutions, insertion/deletion sequences,
terminal overlaps and exact breakpoint content need separately collected,
source-bound base-level difference evidence. No such new evidence was generated
for this presentation update. A straight diagonal or rounded 100% identity is
not an exact-copy criterion. Existing exact scores are unchanged.
