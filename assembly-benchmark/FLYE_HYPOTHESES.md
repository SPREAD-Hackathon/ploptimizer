# Why Flye missed pRK2 in the exact-read pilot

The pilot has a source-backed explanation for the **initial loss**: Flye 2.9.6
selected a 6,000 bp overlap threshold and uses that threshold as a hard minimum
read length for its assembly module. Every pRK2 read was shorter. The controlled rerun below restores plasmid sequence when the threshold is
lowered, but its final output is overextended to 9,769 bp rather than one 5,360 bp
molecule. Thus initial read exclusion is explained, while a downstream
repeat/circular-boundary problem remains to be localized.

## Observed evidence

Batch `20261104T183058`, scenario `s1-w-prk2`:

- The admitted pRK2 input (`NC_017662.1`, 5,360 bp) has 31 reads, lengths
  3,463–5,360 bp, achieved depth 30.4108× and 100% source breadth.
- Flye and Flye-meta both log N50/N90 11,074/6,053 bp, then minimum overlap
  6,000 bp. Both saved `min_overlap: 6000` and `min_read_length: 0` in `params.json`.
- Both produced one initial disjointig. Their logs report zero contained
  disjointigs removed, zero low-coverage paths removed, zero short/long tips
  clipped and zero final contigs filtered.
- Supplementary alignment records show full chromosome coverage/identity and no
  supported pRK2 alignment in either final assembly. Thus this endpoint failure
  is missing plasmid recovery, not merely one residual consensus substitution.

Evidence files live below `runs/20261104T183058/`: `cases/s1-w-prk2/input.json` and
`results/s1-w-prk2/{flye,flye-meta}/diagnostics.json`, plus each tool's
`output/flye.log` and `output/params.json` on BMRC. These are observations from
this batch, not a general claim about Flye performance.

## Pinned source explains the threshold

The Python configurator rounds the input N90 to the nearest 1,000 bp and clamps
it to the configured range; for `--nano-hq` that range is 1,000–10,000 bp. N90
6,053 therefore selects 6,000. Meta mode caps the upper bound at 10,000, so it
does not alter this pilot's selection. Explicit `--min-overlap` bypasses automatic
selection. [Configurator](https://github.com/mikolmogorov/Flye/blob/2.9.6/flye/config/configurator.py#L69-L82),
[range configuration](https://github.com/mikolmogorov/Flye/blob/2.9.6/flye/config/py_cfg.py#L25-L32)

The wrapper passes the selected overlap value to the assembly module. Its
`min_read_length: 0` only means that no separate longest-read downsampling cutoff
was selected; it does **not** mean every read reaches assembly.
[Wrapper](https://github.com/mikolmogorov/Flye/blob/2.9.6/flye/assembly/assemble.py#L55-L58),
[downsampling configuration](https://github.com/mikolmogorov/Flye/blob/2.9.6/flye/config/configurator.py#L88-L100)

The C++ module replaces its minimum read length with the larger of that value
and minimum overlap before loading reads. The loader retains reads only when
their length is **strictly greater** than the cutoff. Therefore **0/31 pRK2 reads
enter the initial assembly read container** at 6,000 bp. This happens before
its k-mer index and disjointig construction. The same loader applies with `--meta`.
[Assembly-module loading](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/assemble/main_assemble.cpp#L243-L263),
[loader condition](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/sequence/sequence_container.cpp#L81-L107)

Overlap detection independently rejects alignments with either overlap span below
the selected minimum. Thus merely retaining shorter reads without changing the
overlap threshold would not remove the constraint.
[Overlap test](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/sequence/overlap.cpp#L28-L37)

## Other mechanisms are secondary questions here

Containment, extension reliability and duplicate-disjointig heuristics exist, but
they cannot explain the first loss of reads never loaded. The extender also limits
starting-read eligibility by the selected overlap and has inner-read rejection
logic. We should inspect these only if the lower-threshold run admits plasmid
reads but still loses the plasmid.
[Seed eligibility](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/assemble/extender.cpp#L256-L265),
[extension/inner-read checks](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/assemble/extender.cpp#L300-L334)

Do not infer active filtering from a configuration name alone: the
`min_reads_in_disjointig` rejection block and singleton-rescue block are commented
out in this release. Their presence in logged defaults is insufficient evidence
that they removed or could rescue pRK2.
[Commented blocks](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/assemble/extender.cpp#L312-L318),
[singleton block](https://github.com/mikolmogorov/Flye/blob/2.9.6/src/assemble/extender.cpp#L403-L442)

The logged zero graph/tip/final filtering counts also argue against describing
this pilot as a plasmid removed by coverage filtering, circular-tip cleanup or
polishing. They do not establish that those mechanisms never affect other cases.

## Discriminating rerun: change only minimum overlap

Use the **same frozen FASTQ bytes**, Flye 2.9.6 environment, `--nano-hq`, four
threads and default internal polishing in two fresh output directories:

1. Repeat the original default-overlap command as control.
2. Add only **`--min-overlap 3000`** to the otherwise identical command.

Both initial runs stop after the assembly stage for a matched-stage comparison.
The 3,000 bp arm then resumes through the full pipeline; the original historical
default final output remains unchanged. This is a documented user-level option,
not a source patch or a new read set.
All 31 pRK2 reads exceed 3,000 bp, so they become eligible for loading. Keep meta
mode unchanged within a pair; testing `--meta` simultaneously would add a factor.
[Flye 2.9.6 option documentation](https://github.com/mikolmogorov/Flye/blob/2.9.6/docs/USAGE.md#L179-L190)

Predeclare the observations: unchanged input hash; logged cutoff 6,000 versus
3,000; predicted eligible pRK2 reads 0 versus 31; first stage at which pRK2-aligned
sequence appears (`00-assembly`, `10-consensus`, graph edges, contigs and polished
output); then exact/dedicated recovery and continuous evidence.

If pRK2 appears immediately in the lower-threshold draft and survives to the final
assembly, the rerun supports the threshold as the sufficient practical explanation
for this case. If it appears early but disappears later, there is an additional
stage-specific mechanism to trace. If it is still absent from the draft despite
admission, investigate extension/overlap geometry next; do not claim threshold
rescue succeeded. A fragmented or tandem output is also informative but is not
an exact-recovery pass.

The one-circumference simulator cap guarantees plasmid reads cannot outgrow their
molecule. Combined with a threshold chosen mainly from chromosome read lengths,
this exposes a default-parameter limitation for this synthetic case. It does not
show that the plasmid is biologically unassemblable or that all real-read datasets
have the same failure.

## Independent runtime cross-check

The hashed origin table contains 147,090,328 input bases. Summing only reads
strictly longer than 6,000 bp gives **132,974,713 bases**, exactly the total
reported for Flye's initial assembly index. Every one of those retained bases
belongs to chromosome reads; pRK2 contributes zero. This checks the observed
binary behaviour against the source-supported loader rule. Counts and evidence
hashes are recorded in `reviews/evidence/flye-pilot-read-filter.json`.

## Controlled intervention result

Study `controlled-20261104T214341` (Slurm job 34391225) used the
same frozen input and four tool threads. The default draft contained one
chromosome disjointig and no plasmid disjointig. At `--min-overlap 3000`, the
draft gained a 21,440 bp disjointig, verified by literal sequence comparison to
be four exact tandem copies of the circular pRK2 sequence.

The resumed full run did **not** produce an exact final plasmid: its second
contig was 9,769 bp and aligned without any edits across 1.823 circumferences
of pRK2. The final GFA reports this edge with a self-link. This is duplicated
periodic sequence, not the earlier absence of plasmid sequence. The lower cutoff
therefore rescues initial representation but is not a complete assembly fix.
The graph/repeat-resolution or circular-boundary mechanism producing the
overextended final edge remains to be localized; do not attribute it to the
initial filter or call it a successful final rescue.

Small phase metrics, hashes and direct checks are retained in
`reviews/evidence/pilot-causal-interventions.json`; historical default scores
are unchanged. The diagnostic inspection initially selects contigs of 0.7–2.0
reference lengths, so its draft no-hit cannot establish absence of the longer
four-copy disjointig. The independent literal check resolves that limitation.

## Panel-wide read-exclusion check

A separate metadata audit of collected S1/S2 Flye/Flye-meta outputs found 47
failed per-plasmid assessments with a logged cutoff; in 40, every source-labelled
read for that plasmid was at or below the cutoff. This identifies a repeated
input-exclusion condition, not a complete stage-by-stage proof for all cases.
Shared homology from other molecules can affect later sequence recovery.
The counts and per-case hashes are in
`reviews/evidence/flye-panel-read-filter-audit.json`.
