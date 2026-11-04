# Matched-fragment Badread adapter

`pipeline/noisy_reads.py` adds Badread errors and qualities to frozen exact
fragments. It does not resample fragments, run assemblers, fit a chemistry or
implement a tolerant assembly endpoint.

## Integration

```python
from pipeline.noisy_reads import inspect_runtime, transform_fragments
# Preparation records this complete audit and freezes its hash once.
audit = inspect_runtime(profile)
# Simulation receives that admitted hash; never automatically accept a new one.
profile = {**profile, "expected_runtime_sha256": frozen_runtime_sha256}
manifest = transform_fragments(clean_fastq, clean_origins, output_dir, profile, case)
```

Profiles require `id`, `error_model`, `qscore_model`, `identity_beta_percent`
(`mean`, `maximum`, `sd`, in percent), and `expected_runtime_sha256`. Supported
pairs: `random`/`ideal` and `nanopore2023`/`nanopore2023`. Additional read-problem
flags must be absent or false. Clean and noisy cases must share replicons and
fragment geometry/seed; their IDs/models may differ. Both fingerprints are checked.

The clean FASTQ's directory must also contain its admitted `input.json` and
`truth.fasta`. Origins may be plain TSV or gzip, with the exact sampler's five
columns and matching read order/hash. Paths must resolve inside the benchmark
work area. Sources remain unchanged.

Outputs are `reads.fastq.gz`, preserved `read_origins.tsv.gz`, `truth.fasta`, a
per-read `read_audit.tsv.gz`, and `noisy-input.json`. The returned manifest has
standard case/status/hash fields plus runtime, clean-input provenance and detailed
replicon statistics. The parent publishes it as `input.json` after checking status.
Existing outputs are not overwritten; exceptions remove partial compressed files.
Statistical holds retain reviewable data marked `invalid_input`.

## Provenance and deterministic streams

Badread must be 0.4.2. Runtime inspection hashes its source files, selected model
assets, this adapter, the Edlib binary and NumPy RNG binary; it records Python,
NumPy and Edlib versions. Missing assets or a missing/mismatched expected hash
fail closed. Sources/models and clean inputs are rechecked after transformation.
Generic algorithmic models are covered by source hashes.

The internal `sequence_fragment` routine receives existing fragments; Badread's
CLI gamma length sampler is bypassed to preserve the benchmark's lognormal
geometry. No adapters, chimeras, junk/random reads, glitches or plasmid loss are
added. Source limits do not trim indel-altered final read lengths.
[Sequencing source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/simulate.py),
[length source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/fragment_lengths.py)

SHA256 keys distinguish identity and error streams for each clean-case fingerprint
and read ID. Identity keys omit profile ID to pair targets across models; error
keys include it. The parent must preserve canonical clean-case metadata across
profiles. Identity uses a local Python RNG; Badread uses the full Python seed and
all eight uint32 words for NumPy. Both global states are restored after calls.
Residual model probabilities are initialised once to avoid lazy read-order state.
Generation is serial; concurrent threads sharing process-global RNGs are unsupported.
Gzip uses empty filenames, `mtime=0` and fixed compression settings.

## Measurements and admission

Final emitted reads are globally aligned to their clean fragments with Edlib.
Identity, extended-CIGAR consumption, edit distance and match/mismatch bases are
checked independently of Badread's padded-read diagnostics, which are retained
separately. Error counts describe a minimal-edit alignment, not a uniquely known
history of mutation events; homopolymer placements may be ambiguous.
[Badread source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/simulate.py),
[Edlib Python contract](https://github.com/Martinsos/edlib/blob/master/bindings/python/edlib.pyx)

Source coverage uses origins. Emitted reference breadth projects final aligned
blocks through those origins, handling reverse strands/circular wrap and excluding
deletions. Insertions contribute to emitted depth but have no reference positions.
Statistics include source/emitted depth, breadth, length SD/N50/quantiles, identity
distribution, alignment errors and quality calibration. Quality error rates cover
emitted substitutions/insertions; deletions have no emitted score. Model qualities
are simulated observations, never truth or evidence of empirical calibration.

Corrupt provenance, origins, sequences, qualities or alignments raise. Source depth
must stop on the first read reaching target, and breadth must meet the frozen
minimum. A replicon is held if weighted mean identity differs from target by more
than `max(0.5, 4*SD/sqrt(n_eff))` percentage points, where
`n_eff=(sum source lengths)^2/sum(source lengths squared)`. Holds invalidate inputs;
they never count as assembler failures.

## Verification

Run `python -m unittest discover -s tests -p test_noisy_reads.py -v`. Fake-backend
tests cover bytes/streams, pairing, indels/qualities, origin projection, validation
holds, hashes/paths, asset drift and RNG restoration. Two installed-backend tests
skip explicitly without Badread/Edlib. Run them under the Linux Pixi simulator
environment on Slurm; they exercise both models and the writer on a tiny 30× set,
including repeated-byte equality. They do not replace the admitted chromosome-plus-
plasmid smoke cases.
