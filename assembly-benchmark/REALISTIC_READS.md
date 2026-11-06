# Proposed error-bearing read panel

Status: **historical small-plasmid smoke complete; larger-plasmid S6 proposed**.
`config/noisy-smoke.json` retains the completed W/pRK2 experiment (three read
sets, 12 executions). Its original scores and evidence remain supplementary.
The revised S6 uses chromosome plus a plasmid ≥20 kb to separate read errors
from small-plasmid recovery. `config/noisy-large.proposed.json` records SE11 +
pSE11-1 and MGH78578 + pKPN3; it is a design record, not a runnable configuration.
The current tolerant evaluator is restricted to small pRK2/pKPN7 references;
larger-plasmid assessment and truth-control validation must precede execution.

`config/realistic-reads.proposed.json` remains the separate, non-executable
expanded 18-read-set design. Adapter and historical bounded-endpoint details are
in NOISY_ADAPTER.md and TOLERANT_ENDPOINT.md.

## Controlled stress before empirical calibration

Start by asking how recovery changes when known fragments acquire sequence
errors and model-generated qualities. A named Nanopore model does not establish
fidelity to a present-day flowcell, kit, basecaller or isolate. A calibrated
Nanopore panel follows only after suitable real reads and metadata are available.

Badread is intended for controlled read-problem testing; its documentation lists
`nanopore2023` as trained on R10.4.1 reads from 2023. Treat that as model provenance,
not validation against our samples or a current basecaller.
[Badread documentation](https://github.com/rrwick/Badread/tree/v0.4.2#readme)

Badread 0.4.2 accepts error models `nanopore2018`, `nanopore2020`,
`nanopore2023`, `pacbio2016`, `pacbio2021`, `random`, or a model filename.
Quality models use those named options plus `ideal` or a filename. The selected
models below are only a subset; naming a model does not calibrate the requested
identity distribution or our library preparation.
[Tagged CLI source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/__main__.py)

## Initial matrix

Use the admitted derived single-plasmid cases W/pRK2 (`GCF_000258145.1`,
`NC_017662.1`, 5,360 bp) and MGH78578/pKPN7 (`GCF_000016305.1`, `NC_009653.1`,
3,478 bp), each with its chromosome. Use three independent fragment seeds:
**20261105, 20261106, 20261107**. Retain identical clean fragments within each
case/seed for these conditions:

| Condition | Error model | Quality model | Interpretation |
| --- | --- | --- | --- |
| Matched exact control | None | Existing Q40 placeholder | Geometry baseline |
| Generic stress | Badread `random` | Badread `ideal` | Synthetic errors with deliberately informative qualities |
| Named ONT model | Badread `nanopore2023` | Badread `nanopore2023` | Historical ONT-shaped package, uncalibrated here |

Both noisy conditions use an identity beta distribution with **mean 98%, maximum
99.5%, SD 1 percentage point**. These are proposed experimental choices. The
comparison changes an error/quality package; it does not isolate error structure
from quality-score effects. A later quality-model swap can separate those factors.
This gives **18 read sets and 72 assembler executions** for four configurations.
These are simulation replicates, not repeated executions on identical reads or
independent biological isolates. Report each seed without precise population
success-rate claims from three replicates.

## Preserve fragment geometry

Keep chromosome source-fragment depth 30×, plasmid relative depth 1×, lognormal
length targets 10,000/5,000 bp, clipping 500–50,000 bp and at most one source
circumference. Random starts and both strands match the exact sampler.

A direct Badread CLI call with `--length 10000,5000` would change the distribution:
Badread uses gamma lengths. Instead, propose feeding existing clean fragments to
a version-pinned adapter around Badread's `sequence_fragment` routine. The bounded
adapter now exists and passed compute-node tests against Badread 0.4.2. This
internal interface requires fixtures and frozen source/model hashes;
it is not a stable public API.
[Length source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/fragment_lengths.py),
[sequencing source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/simulate.py)

Start with serial generation in manifest order. Record independent fragment,
identity and error RNG streams with a documented hash-to-integer convention.
Derive error-stream seeds from case, fragment seed, profile and read ID. Verify
repeatability of decompressed FASTQ/origin records and serial/parallel equivalence
before enabling parallel simulation.

Keep adapters, chimeras, junk/random reads, glitches and small-plasmid loss off;
these become separate later factors. Do not enable Badread defaults silently.
Indels change emitted lengths: do not clip noisy outputs to one circumference or
discard outputs below 500 bp. The cap describes source traversal, not final length.

## Truth and input admission

Clean fragments and origin records are truth. FASTQ qualities are simulated
observations, never measured truth or constant Q40 replacements. Recompute final
read identity against its clean fragment, including indels. Badread's routine
computes its returned identity before trimming internal padding, so independently
validate the final trimmed output and retain the upstream diagnostic separately.
[Sequencing source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/simulate.py),
[quality source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/qscore_model.py)

Publish per-replicon source/emitted bases and depth, source breadth, read count,
length min/mean/SD/N50/quantiles, actual identity distribution, substitution/
insertion/deletion counts, quality distribution and quality-to-error calibration.
Preserve per-read origin, clean-fragment hash, original/emitted length, target/
achieved identity and RNG provenance. Stop by clean source bases; measure emitted
depth separately. Do not resample to force an observed length or quality profile.

Invalidate before assembly for changed truth/models, unknown origins, sequence/
quality length mismatch, non-ACGT or empty generated reads, incorrect source cap/
depth policy, or any replicon below 99% source breadth. Place a validation hold on
noisy replicons whose achieved base-weighted mean identity falls outside
`98 ± max(0.5, 4 / sqrt(n_eff))` percentage points, with
`n_eff = (sum source_lengths)^2 / sum(source_lengths^2)`.
Resolve this through simulator/input review before looking at assembler outcomes.
A hold is not an assembler fail. Read-to-genome mapping is supplementary; known
fragment origins remain truth despite mapping ambiguity.

## Assembly and scoring to freeze

Retain the existing pinned panel: Flye 2.9.6 `--nano-hq`, Flye `--nano-hq --meta`,
Raven 1.8.3 and Plassembler 1.9.0 `long`, four threads each. Retain current
Plassembler QC/Mash exclusions, chromosome threshold 1 Mb, initial Flye output,
retained chromosome and internal polishing. No external polishing, truth-assisted
corrections or per-result tuning. Copy full commands and environment-lock hashes
into a new profile; leave old configs unchanged. Flye documents separate modes
for older/noisier data, so a later 5–15% error panel needs predeclared tool modes.
[Flye 2.9.6 manual](https://github.com/mikolmogorov/Flye/blob/2.9.6/docs/USAGE.md)

Keep exact dedicated-molecule recovery as a secondary endpoint. It cannot stand
in for noisy recovery: a structurally correct consensus with one substitution
fails exact identity.

Propose a separately versioned tolerant endpoint: one dedicated contig with at
least **99% reference coverage**, **99.5% alignment identity**, and length within
**98–102%** of truth; no second contig with at least 95% recovery of that molecule;
no supported non-homologous join to another replicon. Scenario pass requires all
expected plasmids. Report chromosome metrics separately. Allow circular rotation/
reverse complement while keeping terminal duplication and tandem copies visible.
Quality scores do not enter assembly-to-truth identity.

These thresholds are proposed study choices, not biological cut-offs. Current
supplementary PAF flags cannot implement this endpoint. The separate bounded
evaluator now handles pRK2/pKPN7 with conservative uncertainty; validate expansion with mutated, rotated, terminal-overlap, fragmented, tandem, duplicate,
joined and ambiguous-repeat fixtures. Require collinear base-level alignment,
competing-copy checks and unscored ambiguity when assignment cannot be resolved.
Outside the admitted bounded endpoint, publish continuous evidence with **no tolerant pass/fail claim**. The bounded implementation has passed synthetic fixtures and real-reference controls; unresolved assignments remain unscored.
Freeze thresholds, alignment/filter policy and fixture results before comparing
tools; later changes require a new metric/profile version.

## Later empirical calibration

Require isolate/reference linkage, raw-read accession, flowcell/pore, library kit,
basecaller/model/version, simplex/duplex status, filtering and adapter handling.
Fit models on a calibration subset, then assess held-out reads and independent
isolates for lengths, error spectra, homopolymers, quality calibration and
per-plasmid coverage. Archive inputs and model hashes. Badread supports custom
error/quality models, but support does not establish fidelity to a new chemistry.
[Error-model source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/error_model.py),
[quality-model source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/qscore_model.py)

Expansion gates: resolve exact failures; lock Badread/model assets; validate the adapter and
admissions; validate the tolerant evaluator; freeze the new profile; submit via
Slurm. The official tagged source reports Badread 0.4.2. Verify the actual Pixi
build includes selected models before pinning it; a mutable branch is not a pin.
[Version source](https://github.com/rrwick/Badread/blob/v0.4.2/badread/version.py)

## Smoke validation record

The pinned simulator environment passed 139 tests on BMRC in Slurm job34389631
without skipped dependency tests. Real-reference controls for W/pRK2 then passed:
exact truth and a five-base deletion meet the tolerant endpoint; duplicate and
tandem controls fail. Their hashes and results are retained with smoke batch
`20261104T210453`. This validates the bounded checks, not empirical read fidelity
or whole-study assembler performance. The existing four assembler environments
retained identical locked package URLs when the simulator environment was added.
