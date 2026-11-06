# S7: read-order sensitivity

Question: does changing only the order of the same reads change an assembler's
output? This is an output-to-output comparison, like S3. Reference recovery is
supporting context and never determines the S7 verdict. Identical wrong assemblies
can show no observed order effect.

Status: **specified, not implemented or run**. The design record is
`config/read-order.proposed.json`; it is not an executable configuration.

## Bounded first panel

Reuse the frozen SE11 chromosome + three plasmids ≥20 kb from the completed
larger-plasmid S3 input, rather than simulating new reads. Keep the original order
and make three reproducible shuffled orders. Freeze each order once and reuse
that exact file for three independent assembler repeats.

The first panel uses the existing four configurations at a fixed four-thread
setting and their existing default-mode arguments: 4 orders × 3 repeats ×
4 configurations = **48 proposed executions**. No jobs have been submitted.
Keep versions, environments, input content and all other arguments fixed. Use
fresh output directories without shared checkpoints. One-thread and explicit
deterministic-mode comparisons are a later extension, not part of this pilot.

## Input checks

- Shuffle complete FASTQ records, never individual lines or bases. Preserve read
  identifiers, sequences, quality strings, duplicate records and total read count.
- Record an order-insensitive digest of the complete record multiset, retaining
  multiplicities. It must match the original for every input file. Matching read
  names or total bases alone is insufficient.
- Also record an order-sensitive record digest, compressed-file checksum, shuffle
  seed, implementation version and permutation provenance. Confirm the four
  orders are genuinely distinct. Compression-byte changes alone are not evidence
  that read order changed.
- Do not reshuffle for each repeat. Repeats within an order use identical frozen
  input bytes; between orders the record multiset must remain identical.

## Comparison and verdicts

Group by frozen read set × assembler/version × mode × thread setting. Show both
agreement among repeats of each fixed order and agreement between different
orders. Never pool modes or thread counts.

| Observation | Report |
| --- | --- |
| Every completed run has the same normalised assembly | No order effect observed in these runs. |
| Repeats agree within every order, but outputs differ between orders | Order-associated output difference. |
| Repeats differ even with a fixed order | Within-order variability; an order-specific effect is not established by between-order differences alone. |
| Missing runs, failed execution, or unverified input equivalence | Not assessed, with the missing evidence or execution error shown separately. |

Compare contig sequences as a multiset: ignore contig names, output order and
strand, but retain duplicate contigs and sequence differences. Keep byte equality
as a separate measurement. Report observed variant counts and an output-agreement
matrix indexed by input order and repeat.

The primary comparison must not use a reference match to decide equivalence.
For assembler-labelled circular contigs, report circular-representation
equivalence independently of the reference, allowing rotated starts and reverse
complements. Retain the ordinary end-sensitive comparison as well. Missing or
conflicting circularity information leaves start-position equivalence unresolved;
it must not silently establish a sequence change or physical topology.

The current S3 signature canonicalises rotations only for exact reference-matched
circles. **Do not reuse that truth-dependent rule as the S7 primary endpoint.**
Implement and validate the independent comparison before running this panel.

## Per-result evidence

The backend bundle should retain source/permutation hashes, exact commands,
versions, mode/thread settings, order IDs, repeat IDs and both comparison levels.
For differing outputs, show contig count, total length, which sequences differ,
and output-to-output coordinate plots or located change events when available.
Graph differences and optional reference-recovery scores remain separate evidence.

Neither a signature difference nor a changed graph layout establishes a software
mechanism. A finite panel also cannot prove that a tool is universally insensitive
to read order. No result is implied by this specification.
