# Alignment recovery evidence

`pipeline/diagnostics.py` adds supplementary evidence for strict exact-sequence
failures. It does not change the strict endpoint or convert an alignment match
into a pass. Candidate flags guide inspection; they are not confirmed structural
errors or claims about plasmid topology.

## Integration

```python
from pipeline.diagnostics import minimap2_command, summarise_paf
from pipeline.common import fasta

command = minimap2_command(truth_fasta, assembly_fasta, threads=1)
# Run command on a compute node, writing stdout to mapping.paf. Preserve the
# minimap2 version, command, input hashes, stderr and exit code separately.
lengths = {name: len(sequence) for name, sequence in fasta(assembly_fasta).items()}
evidence = summarise_paf(case, "mapping.paf", assembly_lengths=lengths)
```

`truth_fasta` is the reference target and `assembly_fasta` contains query contigs.
Only call the parser after a successful alignment. An empty successful PAF means
no supported mapping; a failed command is a diagnostic execution error, not zero
recovery. An empty assembly may be recorded without invoking the mapper.
Store the evidence separately from the original execution/scoring record so that
post-hoc diagnostics do not rewrite a historical strict assessment.

The command uses `-x asm5 -c --secondary=yes --seed 11`. The upstream manual
specifies assembly mapping presets, base alignments with CIGAR, and secondary
alignment output. `asm5` is intended for close assemblies, so this first profile
is suitable for inspecting the error-free benchmark, not a general noisy-data
scorer. Capture the installed version because preset internals can change.
[Minimap2 manual](https://github.com/lh3/minimap2/blob/master/minimap2.1)

The parser uses PAF's original-target coordinates, half-open intervals and
matches/block-length identity. A `cg` CIGAR is required because columns 10–11
can be approximate without base alignment. Mapping quality 255 is unavailable,
not high confidence. [PAF specification](https://github.com/lh3/miniasm/blob/master/PAF.md)

## Frozen first evidence policy

Defaults are named in `DEFAULT_POLICY` and copied into every returned record:

- Retain primary or inversion mappings (`tp` P or I), mapQ at least 20,
  alignment identity at least 0.90 and at least 200 aligned reference bases.
- Exclude secondary/unclassified, low-confidence, short or low-identity rows.
  Mappings containing ambiguous bases (`nn` > 0) are excluded. Identical PAF rows are counted once. Exclusion counts remain visible.
- Require reference names/lengths to match the case; when assembly lengths are
  supplied, validate query names/lengths too. Reject malformed PAF/CIGAR rather
  than producing a score from a mismatched input.

These are supplementary evidence thresholds, not tolerant pass/fail thresholds.
Shared or repetitive sequences may have low mapping quality and be excluded.
Their absence in supported mappings does not establish absence from the assembly.

## Metrics

For each truth replicon, `recovered_fraction` is the union of reference positions
aligned to query bases divided by reference length. CIGAR deletions are excluded;
substituted positions are counted as aligned and reflected in identity. Overlaps
and repeated copies cannot raise this value above one. Per-contig recovery and
best-contig recovery use the same union rule.

`alignment_identity` is the sum of matching bases divided by the sum of alignment
block lengths for retained base alignments. It is alignment-weighted and includes
gaps. Overlapping alignments contribute repeatedly to this statistic; it is not
an identity estimate for a uniquely selected reference tiling. No retained
alignment gives recovery zero and identity `null`, rather than invented identity.

The candidate flags are independent and can overlap:

- **Fragmented:** at least two supporting contigs, no contig covers 95%, and their
  combined reference coverage exceeds the best contig by at least 5%.
- **Duplicated:** at least 20% of reference positions have evidence from different
  contigs or from substantially distinct query intervals on the same contig.
  Query intervals may overlap by at most 20% of the shorter interval. This detects
  a candidate tandem as well as multiple contigs; it does not estimate copy number.
- **Joined:** one contig has accepted alignments to different replicons on query
  intervals overlapping by at most 20% of the shorter interval. Shared sequence
  mapping onto the same query interval is not sufficient evidence for this flag.
- **No supported alignment:** no mapping survives this policy. This is not a
  definitive missing-sequence classification.

## Limits and validation

Circular-origin splits can be combined by the interval union, but the mapper's
heuristics may miss a short split; circular references are not doubled. Ends and
physical topology are not inferred. Repeats, low complexity and multi-mapping
can hide recovery or create candidate flags requiring inspection. The mapper is
not exhaustive, so duplication evidence is a lower-bound observation, not proof
that unflagged outputs are unique. All results retain `topology_status` as
`not_assessed`; strict rotation/reverse-complement equivalence remains separate.

Fifteen synthetic PAF tests cover missing sequence, partial fragments, overlapping
coverage, multiple full copies, a tandem, joined molecules, shared query sequence,
reverse strands, circular-origin splits, CIGAR deletions, weighted identity,
ambiguous/secondary mappings, duplicate records and invalid inventories. These
validate the evidence parser. Compute-node mapping has now been checked against
the archived pilot outputs; the provisional review in FAILURE_REVIEW.md records
representative findings and their limits. The expanded batch receives interim
and final diagnostic jobs.

The upstream formatter distinguishes primary inversion `I` from secondary
inversion `i`, so the latter is excluded. Minimap2 excludes ambiguous bases from
its PAF block length; the parser accounts for `nn` when validating CIGAR, then
conservatively excludes such alignments from these first evidence metrics.
[Formatter source](https://github.com/lh3/minimap2/blob/master/format.c),
[alignment source](https://github.com/lh3/minimap2/blob/master/align.c).

## Batch runner

On a compute node, run `python -m pipeline.diagnostic_runs --batch BATCH_ID`.
It recursively visits executions, including determinism repeats, invokes
`pixi run --locked -e plassembler minimap2`, and saves sibling `diagnostics.json`,
`alignment.paf` and `alignment.stderr.log`. Pixi must be on the job's PATH.
The original `execution.json` stays immutable; diagnostic errors remain separate.

Every successful input audit checks the frozen config/case fingerprints, actual
reads/truth hashes against the input manifest, and the assembly hash against its
execution record. Older executions omitted duplicated reads/truth hashes in the
execution record: these are allowed only after manifest validation, and explicit
`*_execution_hash_available` flags in `input_hashes` record that provenance limit.
A present execution hash that disagrees always fails. This retrospective check
cannot independently prove that an older manifest was unchanged since execution.

Only a completed diagnostic with matching input hashes, mapper version, commands,
policy, metric version and source hashes can be cached; retained PAF/stderr hashes
are checked too. Missing or changed assemblies produce independent diagnostic
errors. Non-successful assembler executions are skipped. The runner does not
submit jobs, copy large files, or publish results.

Early execution records can also omit `batch_id`. The runner permits absence only
when the record is physically under the requested batch's `results/` directory
and the frozen configuration/scenario and all available input/assembly hash
checks pass. `input_hashes.batch_id_execution_available` records this limitation.
A present batch ID must match; an absent field never overrides a contradictory
configuration, scenario, input or assembly checksum.

Checked sequence observations live in `reviews/` and are separate from automated
mapping evidence. The report attaches an observation only when its batch, case,
tool, strict status and execution/assembly/truth/PAF hashes match. This avoids
applying a representative explanation to another run. The first annotation is
specific to the archived Raven/pRK2 contig and its verified five-base discrepancy;
it does not revise the archived mapping or generalise across tools or scenarios.
