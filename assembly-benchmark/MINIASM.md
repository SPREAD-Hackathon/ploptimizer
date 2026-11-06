# Miniasm integration

The backend supports **Miniasm (unpolished)** using the pinned Pixi `miniasm`
environment: miniasm **0.3-r179** and minimap2 **2.31-r1302**. It implements the
[upstream workflow](https://github.com/lh3/miniasm#readme) for Nanopore reads:

```sh
minimap2 -x ava-ont -t THREADS reads.fastq.gz reads.fastq.gz > overlaps.paf
miniasm -f reads.fastq.gz overlaps.paf > assembly.raw.gfa
```

The overlap step receives the requested threads; miniasm layout is single-threaded.
The ordinary execution time/memory measurement includes both processes and
FASTA extraction. Both commands, versions, exit codes, log tails, input/output
hashes and conversion details are saved in `assembly_workflow` inside the
execution record. The website and standalone Markdown report show both commands.

Miniasm has no consensus/polishing step. Unitig sequences are copied verbatim
from GFA `S` records into the scored `assembly.fasta`. This is distinct from
polished workflows, particularly with noisy reads. No extra polishing, parameter
tuning or deterministic flag is added.

The original GFA, including miniasm's `a` read-layout and `x` summary annotations,
remains on the cluster. A standard GFA copy retains H/S/L/P records for the graph
viewer; source hashes and annotation counts are retained. Graph lengths and
contig lengths use those same unitig sequences. Reported circularity comes from
miniasm's `utgNNNNNNc/l` identifiers, as emitted by its
[unitig writer](https://github.com/lh3/miniasm/blob/master/asm.c); no coverage is
invented from read counts. Normal alignment diagnostics and NUCmer comparison
jobs consume the extracted FASTA through the existing evidence pipeline.

## Configuration and status

`miniasm` is a supported tool ID and execution environment. The optional
`config/miniasm-linear.json` profile selects the same three native Streptomyces
reference complements and standard/long settings, with miniasm alone. Planning
it produces six input cases and six executions. It has **not been submitted**.

```sh
pixi install --locked -e miniasm
python3 benchmark.py --config config/miniasm-linear.json plan
```

Existing frozen batches retain their original four configurations and scores.
The running 24-execution native S5 batch is unchanged. New tool outcomes should
enter the overview only after their outputs and evidence have been verified.

## Installation verification

Installation and a real two-step smoke test ran through Slurm on cluster3 in an
isolated source/environment directory, without changing the active S5 runtime.
The final test used artificial random DNA, produced one unitig, and verified
both graph metadata and the unitig circularity inventory. It is an installation
test, not a benchmark result; its outcome is excluded from scientific counts.
Evidence: `evidence/miniasm-integration/`.
