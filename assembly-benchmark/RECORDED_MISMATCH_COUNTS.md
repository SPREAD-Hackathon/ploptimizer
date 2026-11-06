# Reporting saved base-mismatch counts

For the pKPN5 acceptance case, the later [direct base review](BASE_REVIEW.md)
now supplies verified positions and base changes. The count-only behaviour below
still applies to records without such a review.


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
initial Flye result. The original count-only report left positions and from/to bases unresolved.
The later source-bound direct review resolves those two fields for this result;
the software-internal cause remains unresolved. Two mismatching bases do not by
themselves identify two separate biological SNP events.

This is metadata reporting. No new sequence analysis, simulation, assembly or
cluster job is required or performed.

## Saved process history for pKPN5

A source-bound process note now accompanies the count facts. The saved run log
records additional read processing and a separate plasmid reconstruction after
initial Flye. The final plasmid therefore was not simply the initial exact Flye
contig copied to the output. The note is bound to the execution, final assembly,
reference and log hashes. It appears in backend JSON, standalone Markdown and
the website, with the log hash in its evidence disclosure.

This explains why the initial and final assessments describe different outputs.
It does not identify a causal substep or the coordinates and nucleotide changes.
Those remain unresolved. No new alignment, variant extraction, sequence analysis
or cluster rerun was performed for this reporting change.
