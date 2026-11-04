# Raven pRK2: polishing reproduces the failure

**Confirmed causal stage:** the controlled study starts from an exact 5,360 bp
plasmid graph, preserves it through a zero-round resume, then loses sequence when
polishing is enabled. Two polishing rounds reproduce the **entire archived pilot
FASTA byte for byte**, including the 5,355 bp plasmid. The narrower explanation
that a particular Racon coverage-trimming branch causes the loss remains a
source-supported hypothesis pending a window trace or controlled intervention.

## Controlled observations

Study `controlled-20261104T214341`, Slurm job `34391225`, used the frozen
`20261104T183058/s1-w-prk2` input, Raven 1.8.3 and four threads. The Raven chain
finished by 4 November 2026, 21:46:16 UTC. Input reads and truth retained their
archived hashes; all three resumed arms copied the same pre-polish checkpoint
`814859b0c676ff3dedfd37796a3bcb129e3d745c28f6091efc810c57ac85c08b`.

- **Fresh `-p 0`:** pRK2 is 5,360 bp and exactly matches the circular reference;
  its linear sequence begins at reference coordinate 1013.
- **Resume `-p 0`:** pRK2 remains sequence-identical to that fresh zero-round
  result. Checkpoint serialization/resume does not explain the observed loss.
- **Resume `-p 1`:** pRK2 becomes 5,356 bp. Raven rotates this consensus left by
  `floor(0.42 × 5356) = 2249` bases. Undoing that rotation gives **exactly
  `p0_sequence[2:-2]`**: two bases lost from each end, with no other change.
- **Resume `-p 2`:** pRK2 becomes 5,355 bp. Its sequence and the complete output
  FASTA hash equal the historical pilot. The latter SHA256 is
  `57106e2a2d25c7e0e6358ab3c7b5cffd04ecc4d1a01e6b2ea429d764a13d4ad1`.

The first-round base-level path is `3107=1D1=2D1=1D2247=` from reference start
3264; its deletion placements cluster around the previous linear origin 1013.
The two-round path is `3106=2D1=1D2=2D2246=` from start 155, clustering around
3264, the one-round output origin. Equivalent gap placements in short repeats
are not unique: these CIGARs do not contradict the literal end-trimming equality
or the pilot's earlier five-base-deletion representation.

Both positive-round arms independently resumed **p0**, not one another. The
experiment therefore establishes polishing as the causal stage on a fixed graph
and reproduces the historical result; it does not retain p2's own first-round
intermediate to prove every step of its internal trajectory. The old pilot's
intermediates remain unavailable, so its historical execution was reproduced,
not observed retrospectively.

## Evidence and reproduction

The actual automation is [scripts/investigate_causes.py](scripts/investigate_causes.py).
The study directory is
`runs/20261104T183058/investigations/controlled-20261104T214341/`; each Raven arm
retains commands, version, input hashes, logs, GFA, FASTA and checkpoint evidence.
The downloaded summary and direct checks are under
`.cache/cause-study/controlled-20261104T214341/` locally. The small
`raven-direct-proof.json` includes full source-FASTA hashes, sequence hashes,
lengths and direct-equality booleans, **no nucleotide sequences**. All source
FASTA hashes match their execution metadata; all eight checks are true.

The proof tests the complete sequences, not only a mapper's reported coverage.
The original input had 31 exact pRK2 reads, 30.411× achieved depth and 100%
breadth. [FAILURE_REVIEW.md](FAILURE_REVIEW.md) explains why the pilot's 97.015%
aligned fraction alone understated representation at the circular origin.

For a new investigation, run the script only in a Slurm allocation with at least
eight CPUs for its two four-thread chains; use a fresh study identifier:

```sh
python scripts/investigate_causes.py --study-id NEW_STUDY_ID --tool-threads 4
```

This documentation does not submit additional jobs or change the original scores.

## Where boundary trimming occurs in the source

Raven 1.8.3 configures its Racon polisher with 500 bp windows and
`trim_consensus=true`. After each accepted circular consensus, Raven changes the
linear origin by rotating 42% of the current length. That rotation changes which
physical reference bases lie at the next round's linear ends.
[Raven polishing source](https://github.com/lbcb-sci/raven/blob/1.8.3/RavenLib/src/polish.cc)

Racon's `Polisher::Polish` makes consecutive **linear** windows, passes
`trim_consensus` into each window, then concatenates their consensus strings.
Its mapping code retains the longest overlap per read. It does not pass a
circular-topology flag into window construction, so origin-crossing support is
not explicitly wrapped through that interface.
[Racon polisher source](https://github.com/lbcb-sci/racon/blob/e0c761da58f41184887978e775e1e87dd6ea8fcb/src/polisher.cpp)

The explicit cropping is in **`Window::GenerateConsensus`**, after SPOA produces
consensus and per-base coverages. When the window is TGS and trimming is enabled,
it scans inward from both consensus ends until coverage reaches
`floor(number_of_read_layers / 2)`, then takes that retained substring. This
operates on every window, not a special circular-plasmid branch. It is distinct
from consensus generation itself: a shorter consensus could arise before that
explicit crop, which is why final sequence equality cannot identify the branch
alone.
[Racon window source](https://github.com/lbcb-sci/racon/blob/e0c761da58f41184887978e775e1e87dd6ea8fcb/src/window.cpp)

Raven's dependency configuration requests Racon 3.0.4 or the `library` branch.
The reviewed Racon commit above identifies itself as 3.0.4 and predates the
package build; the exact embedded dependency commit was not independently
recovered from the binary. The pinned installed binary, rather than a rebuilt
current branch, produced the controlled results.
[Dependency configuration](https://github.com/lbcb-sci/raven/blob/1.8.3/Raven.deps.cmake)

**Interpretation:** exact two-base losses at each pre-rotation end, followed by
loss near the new origin, strongly support a circular-boundary/linear-window
handling mechanism. They do not yet distinguish explicit low-coverage cropping
from endpoint effects during read alignment or POA consensus.

## Smallest next causal test

Instrument the first and last plasmid windows on the same p0 checkpoint: retain
backbone length, raw consensus length, coverage vector, crop begin/end offsets
and final consensus length. Ask whether those windows explicitly crop two bases
at the outer ends. This gives a direct branch-level observation.

Then compare the same graph/read input with only `trim_consensus` changed from
true to false in a controlled, versioned build. If cropping disappears and all
5,360 bases remain, that isolates the trimming mechanism; if sequence is already
short before cropping, investigate POA/alignment endpoints instead. The public
Raven CLI exposes polishing-round count but not that trimming boolean, so do not
claim a zero-round comparison alone isolates this particular option. Preserve
compiler/dependency provenance and avoid changing window length or scoring
simultaneously. Such instrumentation/build experiments have not run here.

## Checkpoint isolation and historical validity

The old pilot wrapper used a shared process working directory. Raven writes a
fixed relative `raven.cereal`, so parallel runs could overwrite checkpoints.
Normal execution reads that file only with `--resume`; the pilot had no resume
flag or “loaded previous run” log entry. This is a retention/resume-safety defect,
not evidence that ordinary historical assemblies consumed another run's graph.
[Checkpoint I/O](https://github.com/lbcb-sci/raven/blob/1.8.3/RavenLib/src/binary.cc),
[resume control flow](https://github.com/lbcb-sci/raven/blob/1.8.3/RavenExe/src/main.cc)

Future Raven executions now run and check versions in their isolated execution
directory, recorded relative to the batch. Commands, flags and scoring are
unchanged; the regression test confirms separate checkpoint writes and unchanged
Flye working-directory behaviour. The controlled study also used isolated
checkpoints. No general tool ranking, physical-topology claim or real-read
performance conclusion follows from this one mechanism investigation.
