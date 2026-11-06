# Direct review of the two pKPN5 substitutions

The earlier count-only report has been superseded for this saved result. Routine
comparison of the existing final assembly with its frozen public reference
confirms two substitutions, rather than merely two aggregate alignment edits.
No assembler or aligner was rerun, and no output sequence was corrected.

Coordinates below are **1-based**. Base changes are **reference → output**, in
the reference-forward orientation, against pKPN5 **NC_009651.1**.

| Reference position | Change | Final contig | Final position |
| --- | --- | --- | --- |
| 39,984 | T → C | 1 | 11,045 |
| 77,230 | A → G | 1 | 48,291 |

The circular output starts at a different reference position; reference and
output coordinates therefore differ. Both molecules are 88,582 bp. Saved PAF
rows completely partition both sequences in one consistent circular rotation.
Direct comparison of every aligned base agrees with the recorded mismatch
counts. There are no gaps in those saved spans. The original exact score remains
**fail**.

## Where the differences appear in the saved workflow

- Initial Flye `contig_2`: exact circular reference equivalence, directly checked.
- Unicycler `004_long_read_assembly.gfa`: its single 88,582 bp segment also has
  exact circular reference equivalence.
- Unicycler `006_final_clean.gfa`: its single segment matches the final
  Plassembler sequence, including the two substitutions.
- Unicycler `assembly.fasta`: circularly equivalent to final
  `benchmark_plasmids.fasta`.

The saved Unicycler log records graph bridging and cleanup between checkpoints
004 and 006. These comparisons narrow the discrepancy to reconstruction of the
final graph between those saved checkpoints. They do **not** establish a
particular code operation, a read-correction error, a polishing error or a
specific repeat-resolution mechanism. The exact long-read branch was not simply
copied verbatim into the final plasmid output. Reference rotation alone cannot
explain the two substitutions.

## Reproducibility and provenance

The review script reads existing files and never invokes assembly, read
correction or alignment software:

```bash
python3 scripts/review_saved_gapfree_pair.py \
  --truth PATH/truth.fasta --assembly PATH/benchmark_plasmids.fasta \
  --initial PATH/flye_output/assembly.fasta \
  --reconstructed PATH/unicycler_output/assembly.fasta \
  --checkpoint-gfa PATH/unicycler_output/004_long_read_assembly.gfa \
  --checkpoint-gfa PATH/unicycler_output/006_final_clean.gfa \
  --paf PATH/alignment.paf --execution PATH/execution.json \
  --output PATH/review.json
```

The committed review is
`reviews/bases/20261104T190455-pkpn5-plassembler.json`. It retains input hashes,
alignment spans, per-base events, intermediate hashes and exact equivalence
checks. The assembly and truth hashes must match the original execution record.
Report export binds the review to the batch, scenario, assembler, exact status,
execution, assembly, truth and PAF hashes, and checks the event count against the
existing recorded count. Sequence files remain outside the static website.

The web-independent JSON and Markdown report and the result page all consume the
same prepared event records. A mismatch location is a verified observation;
the software-internal cause remains unresolved.

The retained `reviews/evidence/20261104T190455-pkpn5-unicycler.log` supplies
the checkpoint order and bridging/cleanup log context. Its checksum and relevant
line numbers are recorded in `evidence/base-review-v1/checkpoint-log.json`.
