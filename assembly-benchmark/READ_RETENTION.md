# Read retention policy

Simulated FASTQ files are temporary working data, not permanent benchmark
archives. Generate each input once, share that frozen file across its consumers,
and remove the large read files after the results and all dependent work are
complete and verified. Do not regenerate reads independently for each assembler.

## Keep permanently

- Original input manifests, seeds, all simulation settings and input order.
- Pinned reference versions and hashes, with the small reference truth files.
- Simulator source revision, runtime and environment locks, and frozen error models.
- Original read hashes, read counts and summary statistics.
- Assembly outputs, logs, commands, assessments, plots and result provenance.
- A cleanup receipt listing removed paths, sizes, hashes and verification evidence.

For shuffled inputs, retain the shuffle algorithm, version and seed as well as
source and shuffled hashes. For published datasets, retain the immutable archive
identifier, selected member location and checksum: these inputs are retrieved
again from their original archive rather than recreated by our simulator.

## Before removing working reads

1. All consumers must be terminal: assemblers, repeated/shuffled runs, polishing,
   read-based diagnostics and any queued follow-ups using the same inputs.
2. Reporting and release checks must be complete. Results must have been
   collected and their retained artefacts verified.
3. Exact restoration must be demonstrated for the relevant generator/runtime
   before treating its reads as disposable. Keep the verification receipt.
   A seed on its own is insufficient evidence.
4. Check shared paths and hard links across batches. Remove only approved read
   working files, preserving manifests, references and results. Reclaiming a
   hard-linked file's storage requires removing every approved link.

Regeneration must write to a new temporary location and match the original
recorded hashes before any assembler consumes it. A mismatch must stop reuse;
it must never silently replace an input or overwrite an existing result.
Compressed hashes also depend on compression/runtime details. Keep a content
hash alongside the existing compressed-file hash for future inputs so a changed
gzip wrapper can be distinguished from changed read records or order.

## Implementation status

This policy replaces indefinite read retention. Automatic deletion and verified
restore are not implemented yet. The current cache path requires existing read
files when an input manifest exists; simply deleting FASTQ files would break
that path. Add an explicit verified-restore path and cleanup receipts before
enabling automatic removal. No existing reads were removed by this policy
change. The active S5, Miniasm and Minipolish dependency chain still needs its
shared inputs.
