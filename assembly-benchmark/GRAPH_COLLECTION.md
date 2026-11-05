# Collecting existing graph metadata

`scripts/collect_graph_artifacts.py` creates sibling `graph_artifacts.json`
sidecars for explicitly selected existing executions. It does not rerun tools,
change parameters, submit jobs, install software, rewrite execution records or
publish a site. Remote helpers only read existing files and return sequence-free
JSON; the controller writes derived sidecars inside `assembly-benchmark/`.

## Existing BMRC outputs

From `assembly-benchmark/`, select at most eight executions per call:

```sh
python3 scripts/collect_graph_artifacts.py \
  --ssh-host rva470@cluster3.bmrc.ox.ac.uk \
  --source-root /well/aanensen/users/rva470/ploptimizer/assembly-benchmark \
  --batch 20261104T190455 \
  --execution results/s1-w-prk2/flye/execution.json \
  --execution results/s1-w-prk2/flye-meta/execution.json \
  --execution results/s1-w-prk2/plassembler/execution.json
```

Repeat executions use their precise path, for example
`results/s1-w-prk2/flye/repeats/threads-1-repeat-1/execution.json` in the S3 batch.
There is no whole-cluster or recursive discovery. SSH uses existing agent
credentials with `BatchMode=yes`; it cannot prompt for interactive login or
reauthentication. The default remote interpreter is the already installed Pixi
`default/bin/python`, requiring Python 3.10+. `--remote-python` may name another
existing interpreter. The helper/parser are streamed into Python memory; no
remote source file is written or installed.

For a local mounted copy or fixture, omit `--ssh-host` and set `--source-root`.
`--output-root` chooses a separate local destination inside this work area;
the default is this benchmark root. `--emit` returns topology-only JSON without
writing sidecars. Exit 1 flags invalid/unsupported collection; missing outputs
are recorded availability states. Inspect individual statuses.

## Selection and provenance

For assessed outputs, the collector verifies execution identity, raw execution
hash and the actual recorded primary assembly hash before parsing metadata. Raw source graph/table
hashes are retained. This associates sources with an execution; it does not prove
a one-to-one relation between graph nodes and final FASTA contigs. Reads/truth
are not re-audited or compared here.

- Flye: `output/assembly_graph.gfa` and `output/assembly_info.txt`.
- Plassembler: prefer `output/<recorded --prefix>_plasmids.gfa` and
  `output/<prefix>_summary.tsv`, labelled final. Prefix comes from its command,
  not a guess. Final graphs never borrow initial Flye metadata.
- If final Plassembler sources are absent, retained `output/flye_output/` sources
  are `initial_flye`; retained root Flye files use that role too.
  `output/unicycler_output/assembly.gfa` is a component fallback. One sidecar uses
  one source role.
- Raven: retained `graph.gfa`, `assembly_graph.gfa` or an in-directory graph path
  from its command. Original executions without emitted GFA remain missing;
  opaque `raven.cereal` is never opened or exported.

A final Plassembler summary may include a retained chromosome alongside plasmids
while its plasmid GFA contains only plasmid segments. Keep those tool claims
separate; do not invent matching graph nodes or label component graphs final.

Paths and symlink targets must stay inside the selected execution directory.
Checksum mismatches, unsupported formats and limits are explicit. No neighbouring
run is searched for replacement evidence. Terminal error/timeout records can
retain initial or partial graphs: these bind to the exact failed execution and
source hashes, explicitly carry no verified primary assembly hash, and never
change the scientific status. Empty final placeholder files in stopped jobs do
not hide a non-empty earlier graph; assessed empty no-plasmid outputs remain final.

## Export bounds and verification

The parser exports GFA1 identifiers, lengths, oriented links, overlap CIGARs,
paths, numeric coverage/count tags and tool circularity claims. Segment sequences
and arbitrary optional tags/URIs are removed. A self-link is a graph observation;
a circularity token is a tool claim. Neither establishes physical topology,
sequence accuracy or a benchmark pass.

Bounds are 64 MiB/source, 16 MiB/line, 10,000 nodes, 20,000 links, 10,000 paths,
50,000 path steps and 8 MiB/sidecar. Primary assembly hash verification is capped
at 256 MiB. Raw GFA, FASTA and checkpoints are not published. Reporting must use
the parser's checked sidecar attachment API, verifying schema and hashes.

Flye output paths and assembly-info meaning follow its
[2.9.6 manual](https://github.com/fenderglass/Flye/blob/2.9.6/docs/USAGE.md#flye-output).
Graph edge sequences can differ from extended final contigs; identifier matching
does not establish sequence equivalence.

```sh
python3 -m unittest discover -s tests -p test_graph_collection.py -v
```

Synthetic tests cover unchanged source files, removal of sequence/tag payloads,
missing graphs, checksum mismatches, path/symlink bounds, separate output roots,
the streamed read-only helper, component roles and final Plassembler preference
without cross-stage mixing, failed-output provenance and empty final placeholders.

After SSH access was restored, the route was exercised on archived pilot
`20261104T183058`, case `s1-w-prk2`:

- Flye: final graph/table available, one segment and two oriented links.
- Plassembler: final graph/summary available, one segment, one link and two tool
  claims (retained chromosome and plasmid).
- Raven: graph explicitly missing; that execution did not emit a GFA.

Only local derived sidecars were written. No jobs, new biological analyses or
remote mutations were started. These checks do not change scientific outcomes.

## Collected result coverage

All 272 submitted executions across the pilot and four completed batches were
checked. There are 204 collected GFAs; the 68 Raven executions have no saved GFA.
The four stopped Plassembler runs retain initial Flye graphs under their original
error outcomes. Five passing no-plasmid controls have empty final summary files,
so their final circularity claims remain unavailable. Raw source files and
scientific scores were preserved.

## Whole-segment origin association without GFA paths

A final GFA can have S/L records but no P records. That does not mean its plasmid
is unassembled. In the reviewed `s2-mgh78578-pkpn7-depth-3` Plassembler result,
the final scored contig `1` is an exact pKPN7 match, while the previous viewer left
segment `1` grey because it required an explicit path.

`scripts/collect_graph_contig_identities.py` now records sequence hashes for whole
GFA segments and whole scored FASTA contigs from existing files. Both file hashes
are checked before and after reading. Comparison ignores letter case and FASTA
line wrapping; it does not rotate, reverse-complement, align or trim sequences.
Names and lengths alone never establish identity. Sequences are not exported.
The output is `graph_contig_identity.json` beside the original execution.

When graph sidecars are held locally rather than on the cluster, supply their
frozen directory tree as `--metadata-root ROOT` (ROOT/BATCH/results/.../
graph_artifacts.json). The graph source must still match its recorded SHA-256.
After collecting the small identity sidecars into local `runs/`, normal backend
export with `--recorded-artifacts runs` validates execution, assembly, graph,
segment and contig provenance. A whole-segment identity plus the saved exact
reference match can support a node colour without a GFA path. The derived model
records the association type, matching hash and source checksum. Ambiguous
reference assignments remain grey. This adds no within-node origin boundaries.

Collection job 34423757 completed successfully in 41 seconds: 200 final-graph
inventories, containing 18,290 whole-segment/contig identity pairs. The preceding
probe job 34423537 found no colocated graph sidecars and produced zero inventories;
only the explicitly supplied frozen graph metadata were used by the successful
collection. No assembly or alignment was rerun. Original graph downloads and
scientific scores remain unchanged.

## Missing Raven graph audit

[INTEGRITY_AUDIT.md](INTEGRITY_AUDIT.md) records the complete checksum and file
inventory audit. The 68 completed Raven executions did not request graph output
and have no GFA files. Future commands request `assembly_graph.gfa` explicitly;
historical graph gaps are labelled independently of sequence recovery.
