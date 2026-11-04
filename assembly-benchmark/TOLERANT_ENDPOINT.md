# Tolerant small-plasmid endpoint, version 1

`pipeline.tolerant.evaluate_tolerant(case, truth_path, assembly_path,
plasmid_only=False, policy=None)` returns a separate result with `status` equal
to `pass`, `fail` or `unscored`. Its identifier is
`small-plasmid-tolerant-v1`; the complete policy and its fingerprint accompany
every result. It neither calls nor changes the strict evaluator. This is an
initial bounded implementation, not a validated replacement for exact recovery.

The initial supported targets are circular pRK2 (`NC_017662.1`) and pKPN7
(`NC_009653.1`). Other plasmids and biologically linear molecules are unscored.
Chromosome-only controls are also outside this release. Chromosome assembly
quality remains a separate endpoint; a long chromosome does not exceed the
plasmid reference-size cap.

## Frozen default criteria

For each supported plasmid, require exactly one dedicated contig with:

- At least 99% of reference bases aligned to query bases.
- Alignment identity at least 99.5%, including gap columns in its denominator.
- Whole-contig length between 0.98 and 1.02 times the reference length.
- A certified single-traversal, collinear alignment of the entire contig.
- No second near-complete copy (at least 95% reference coverage, at least 99.5%
  identity), and no unresolved copy/embedded/join assignment.

Reference coverage counts both matching and substituted reference positions;
query gaps in the alignment do not count as covered. Identity is matches divided
by matches, substitutions, insertions and deletions. Unaligned target ends are
not identity columns and remain visible through reference coverage. Every query
base, including terminal extensions, participates in its whole-contig alignment.
This endpoint does not trim terminal overlaps, polish sequences or combine
fragments to make a dedicated molecule.

The supplementary PAF thresholds are not used. In particular, its 95% candidate
flag threshold does not become a tolerant pass threshold. These criteria are a
new, explicitly versioned endpoint; historical exact outcomes remain intact.

## Alignment and equivalent representations

For a candidate contig, Edlib aligns the whole query in infix (`HW`) mode against
the doubled circular reference, in both strands, with an identity-derived edit
bound. Target coordinates are converted from Edlib's inclusive endpoints. The
bounded selected reference window is then aligned globally (`NW`, `task=path`)
to recover an extended CIGAR. The chromosome is never a global-alignment query
or target. Candidate reference windows cannot traverse more than one circle;
extra-circumference or excessive placement ambiguity is unscored.

The upstream Python API documents the `HW`, `NW`, `locations`, `path` and `k`
parameters. Its extended CIGAR consumes query bases for `I` and target bases for
`D`; the implementation checks those consumptions and the edit distance rather
than assuming a SAM-style argument orientation.
[Official Edlib Python binding](https://github.com/Martinsos/edlib/blob/master/bindings/python/edlib.pyx)

Contig order/names, reverse complement and arbitrary circular coordinate origins
do not change sequence recovery. One returned optimal CIGAR does not establish
a unique placement of every gap in repetitive sequence. To avoid relying on that
choice, a pass also requires conservative identity and coverage bounds over
optimal edit paths with the selected spans. With edit distance `d`, query length
`Q` and target-window length `T`, identity is at least `1-d/max(Q,T)` and target
aligned bases are at least `T-floor((d-(Q-T))/2)`. Metrics from the returned paths
and these bounds are both retained. Unresolved threshold ambiguity is unscored.
The result makes no physical topology or circularity claim.

## Copies, joins and repetitive assignments

Every other assembly contig is inspected. Bounded near-full small contigs receive
the same base-level comparison at the 95% copy coverage threshold. A second
qualifying copy makes the result fail. Multiple qualifying primary candidates
also fail.

A long joined contig, a fragmented copy or shared repeat may prevent a definitive
copy assignment. A conservative screen looks for spaced exact 32 bp reference
anchors in both orientations on every competing contig. Its guard is lower than
the surviving-anchor bound for a contiguous collinear near-copy under the stated
coverage/identity policy. A triggered screen without a resolved base-level copy
is **unscored**, not proof of a duplication and never permission to pass. The
anchor policy and matching counts are recorded. Repetitive references without
a distinct supported anchor set are unscored. This first release deliberately
leaves some correct assemblies unscored rather than label unresolved structure
as a pass.

A dedicated candidate must itself align collinearly to one reference traversal;
large foreign additions therefore cannot be rescued by soft clipping. Sequence
identity cannot determine the biological origin of a tiny variant or distinguish
physically different molecules with identical sequences. “No unresolved join”
here concerns the supported sequence assignment, not a physical-topology claim.
Low-identity homology and arbitrary complex rearrangements are outside the copy
exclusion guarantee.

## Bounds, outputs and tests

Hard limits are 10,000 bp per scored plasmid reference, 256 assembly contigs and
20 million assembled bases. They may be lowered through `policy` but not raised
in this release. Ambiguous bases, unsupported reference length/topology,
insufficiently informative repeats, missing Edlib and invalid input files produce
`unscored`. An invalid policy raises `ValueError`. Evidence reports supported
plasmids only; it does not implicitly give unsupported plasmids a pass.

The response includes schema/endpoint versions, policy/fingerprint, Edlib
version, per-plasmid status, dedicated candidates, base-level paths and bounds,
competing-copy evidence, ambiguity reasons, counts and limitations. Overall
status is fail when any assessed plasmid fails, otherwise unscored when any
plasmid is unresolved, otherwise pass. An unscored result must be excluded from
pass/fail denominators.

```sh
pixi run --locked -e simulator python -m unittest discover -s tests -p test_tolerant.py -v
```

Fixtures independently exercise circle rotation, reverse strands, a chromosome
larger than the plasmid cap, tolerated small indels/substitutions, insufficient
identity, fragmented/incomplete recovery, duplicated and near-full second copies,
terminal overlap, tandems, joined copies, repetitive assignment and unsupported
inputs. Tests requiring Edlib skip when that optional dependency is absent;
the compute-node simulator environment must run those tests before publication.
Thresholds and runtime bounds still need validation against broader adversarial
and real assemblies before expanding the supported reference panel.
