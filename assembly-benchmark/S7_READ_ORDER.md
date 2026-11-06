# S7: read-order sensitivity

Question: does changing only the order of the same reads change an assembler's
output? This is an output-to-output comparison, like S3. Reference recovery is
supporting context and never determines the S7 verdict. Identical wrong assemblies
can show no observed order effect.

Status: **implemented and completed: all 48 executions**, batch `20261106T134415`.
The executable configuration is `config/read-order.json`; the original
`config/read-order.proposed.json` is retained as the historical design.
See `evidence/read-order-v1/status.json` for current execution state.

## Bounded first panel

Reuse the frozen SE11 chromosome + three plasmids ≥20 kb from the completed
larger-plasmid S3 input, rather than simulating new reads. Keep the original order
and make three reproducible shuffled orders. Freeze each order once and reuse
that exact file for three independent assembler repeats.

The first panel uses the existing four configurations at a fixed four-thread
setting and their existing default-mode arguments: 4 orders × 3 repeats ×
4 configurations = **48 executions**, submitted through Slurm on 6 November 2026.
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
The S7 implementation uses its own reference-independent sequence signatures;
its 12 local tests cover rotations, reverse complements, retained duplicate
copies, exact cross-stage topology association, classification and reporting.

## Per-result evidence

The backend bundle should retain source/permutation hashes, exact commands,
versions, mode/thread settings, order IDs, repeat IDs and both comparison levels.
For differing outputs, show contig count, total length, which sequences differ,
and output-to-output coordinate plots or located change events when available.
Graph differences and optional reference-recovery scores remain separate evidence.

Neither a signature difference nor a changed graph layout establishes a software
mechanism. A finite panel also cannot prove that a tool is universally insensitive
to read order. No result is implied by this specification.

## Execution and backend output

Run from `assembly-benchmark`:

```sh
python3 scripts/read_order.py plan
python3 scripts/read_order.py submit
python3 scripts/read_order.py collect
```

`submit` checkpoints job IDs and refuses a changed configuration or duplicate
submission. The isolated remote source root is `assembly-benchmark/.s7`; it does
not replace the main publisher or any prior batch. Preparation installs the
pinned Pixi environments, runs nine S7 tests and admits the four frozen orders.
Four independent 12-task arrays then reuse those orders. The scheduler cap is
1000; Plassembler has a two-hour allocation and the other tools retain four hours.
No source reads are simulated again and no parameters are tuned to outcomes.

The shuffle sorts original record indices by a seeded SHA-256 key, with the
original index breaking ties. It retains a compressed permutation index,
compressed/uncompressed checksums and ordered/multiset record hashes. Repeats
hard-link the same admitted order file. Reference origin rows remain keyed by
read ID rather than reordered by position.

The primary end-sensitive signature ignores contig names, output ordering and
strand, while preserving sequence, length and duplicate-copy differences. A
separate circular-representation signature allows rotations only where the tool
reported topology for every contig; it stays unassessed for unknown topology.
For Plassembler, the comparison includes its final plasmids and hash-verified
retained chromosome. The chromosome’s saved initial Flye circularity label is
associated only by complete sequence identity (including reverse complement);
its name or a reference match is never used. The original end-sensitive
signatures are unchanged and preserved. Byte/checksum and reference-recovery
evidence remain separate.

The report stage writes `summary.json`, `report/index.html`, `report/runs.tsv`
and `report/orders.tsv`. Each tool has within-order summaries, a 12-by-12
pairwise output agreement matrix, commands and execution status. This is a
standalone backend report, ready for the website publisher to consume.
These pairwise matrices compare saved sequence signatures; they are not alignment
dot plots. Output-to-output coordinate alignments/event locations remain a
separate follow-up for differing outputs. All 48 records and input bindings
have now been collected and verified; see `evidence/read-order-v1/RESULTS.md`.

Reads are temporary under `READ_RETENTION.md`; they remain available while
S7 and any dependent diagnostics need them. No automatic cleanup is enabled.

### Submitted jobs

- assemble-flye: `34523670`
- assemble-flye-meta: `34523671`
- assemble-plassembler: `34523674`
- assemble-raven: `34523672`
- prepare: `34523669`
- report: `34523675`

## Completed outcome

All 48 executions completed successfully as software executions. The secondary
reference endpoint has 24 passes and 24 failures; these are not S7 verdicts.

- Flye (default): seven end-sensitive variants, but one circular-normalised
  output across all 12 runs. No order effect observed after allowing the
  recorded circular starts to rotate.
- Flye (`--meta`): seven end-sensitive and three circular-normalised variants.
  Same-order repeats vary, so an order-specific effect is not established.
- Raven: four end-sensitive outputs; all three repeats agree within each
  order. Contig counts differ between four and six, establishing an output
  difference beyond circular starts. No complete circular-label view is available.
- Plassembler: three end-sensitive outputs, all caused by representations of
  the retained chromosome; its final plasmid sequences match across orders.
  Verified inherited chromosome topology yields one circular-normalised output
  across all 12 runs. No sequence order effect observed under that comparison.

Topology review job `34524603` used saved outputs only; no assembler or read
generator was rerun. Its input/output hashes and the unchanged end-sensitive
signatures are verified in `evidence/read-order-v1/release-qa.json`.

The [completed S7 website report](https://ploptimizer-assembly-benchmark.vercel.app/scenarios/s7) includes both comparison views, pairwise matrices and TSV downloads. It is linked from the homepage and Scenarios catalogue.
