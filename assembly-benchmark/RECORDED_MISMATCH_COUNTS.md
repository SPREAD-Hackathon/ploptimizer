# Reporting saved base-mismatch counts

The report now retains numeric `NM` counts and validates a restricted, gap-free
`cg` operation count from already-produced PAF files. It does not run an aligner,
inspect sequence letters, decode sequence-bearing tags or call variants.

The [minimap2 output specification](https://lh3.github.io/minimap2/minimap2.html)
defines NM as the mismatch/gap count and cg as the CIGAR field. The adapter only
classifies gap-free rows represented by a single M run when its size agrees with
query span, reference span and block length, and NM agrees with block minus
matching-base counts. Missing, duplicate, conflicting or unsupported optional
metadata cannot establish a substitution-only result. Arbitrary optional tags,
including cs/MD sequence-bearing fields, are ignored and never exported.

A headline count requires one query/reference pair with equal expected lengths,
complete non-overlapping partitions of both coordinate spaces, matching frozen
assembly/reference/PAF hashes, and a failed required molecule. Overlapping,
partial or multi-query mappings are not summed into a unique mismatch claim.
The existing exact score is preserved.

The JSON backend exports the summary and scalar evidence. The standalone Markdown
report includes the same facts, and coordinate TSVs retain the recorded edit
distance. The website consumes the prepared summary. If the saved initial Flye
assessment contains an exact match for the same molecule, that recorded stage
result is displayed separately. It is not a claim identifying which later
substep introduced a difference.

The pKPN5/Plassembler acceptance case has two recorded mismatches over a complete
88,582 bp output, no gap operations in those saved alignments, and an exact
initial Flye result. The report explicitly leaves mismatch positions, from/to
bases and software-internal cause unresolved. Two mismatching bases do not by
themselves identify two separate biological SNP events.

This is metadata reporting. No new sequence analysis, simulation, assembly or
cluster job is required or performed.
