# Run the assembly benchmark

Everything in this workflow lives under `assembly-benchmark/`. Run commands from
that directory. Python 3.10+ runs the local controller; the pinned Pixi environments
provide Python 3.11 and the assemblers on Linux compute nodes. BMRC's system Python
may be older and is not used to execute the benchmark stages.

## Pilot definition

`config/pilot.json` freezes the first operational profile, `s1-exact-v1`:

- Reference: E. coli W, GCF_000258145.1. Four named S1 cases: chromosome only,
  chromosome plus pRK1, chromosome plus pRK2, and the native two-plasmid complement.
- Error-free sequence sampling, random starts and both strands. A lognormal length
  distribution targets mean 10 kb and SD 5 kb, then clips to 500–50,000 bp and to
  the molecule length. Circular reads can cross coordinate zero once; linear reads
  stay within their physical ends. No multi-circumference tandem reads are created.
- Chromosome depth 30×; plasmid depth 1× relative to it. Each molecule is sampled
  until the target is reached, with at most one read of overshoot. Record achieved
  depth, breadth, count and length statistics. Breadth below 99% invalidates input.
- Seed 20261104 with independent deterministic streams keyed by accession. This
  preserves chromosome reads across derived subsets. FASTQ Q40 is a placeholder.
- Four tool entries, four threads each, four-hour process timeout. This is one
  execution per configuration, not the repeated determinism experiment.

These are explicit pilot choices, not a claim of realistic nanopore chemistry.
Badread/error-profile integration is the next simulation stage. New profiles must
have their own identifiers and configs rather than silently changing old results.

## Install and inspect

The Linux tool versions are specified in `pixi.toml`; `pixi.lock` pins transitive
packages and builds. Default, Flye, Raven and Plassembler have separate environments.
Plassembler also pins Flye 2.9.6 and Unicycler 0.5.1. The pilot skips optional QC and
Mash annotation, so no PLSDB download is required. Keep software version checks and
the package inventories produced during preparation.

```sh
python3 benchmark.py plan
python3 -m unittest discover -s tests -v
```

On a compute node, `pixi install --locked --all` installs the environments. The
automated submission performs installation on a Slurm node, not the login node.
Preparation requires the committed lock; update it deliberately with `pixi lock`
when changing software versions. Temporary files use a short `.t/JOB_ID` path
inside this work area to stay within Python multiprocessing's Unix-socket limit.

## Submit to BMRC

Copy `config/cluster.example.json` to the ignored `config/cluster.local.json` and
set the SSH destination, absolute remote work directory, account and Pixi path.
The destination should end in `ploptimizer/assembly-benchmark`. Source transfer
excludes caches, environments, local cluster settings, data and previous runs; it
does not delete remote files. Tool threads must match the Slurm CPU request.

```sh
python3 benchmark.py submit --scenario s1-w-prk2
```

This **submits real jobs**. It synchronises this work area and creates a timestamped
batch with a frozen config, task list, generated scripts and job IDs. The chain is:

1. **Prepare:** install Pixi environments; fetch exact RefSeq records; check accession,
   length and ACGT alphabet; retain hashes and package/source provenance; run tests.
2. **Simulate array:** generate each selected case's reads, truth FASTA, read-origin
   TSV and input manifest. This stage runs once per case and is shared by all tools.
3. **Assembler array:** one scenario/tool pair per task, bounded by array concurrency.
   Capture command, observed version, logs, exit code, elapsed time and GNU-time peak
   memory; evaluate successful output. Slurm accounting retains scheduler failures.
4. **Report:** run after the assembly array finishes, including failed tasks. A
   failed dependency cancels downstream work rather than leaving it waiting forever.

Run `submit` without `--scenario` to submit all four W cases. Each new submission
gets a new batch; completed executions are not overwritten. First inspect the
small single-plasmid case before expanding the matrix. All five preferred references
can be selected by changing the reference list in a new configuration, but their
sequence audits still run before use.

## Collect results and publish

```sh
python3 benchmark.py collect --batch BATCH_ID
python3 benchmark.py report --batch BATCH_ID
python3 benchmark.py publish --batch BATCH_ID
python3 -m http.server 8844 --bind 127.0.0.1 --directory dist
```

Collection uses rsync/SSH and Slurm accounting. It retrieves small records, logs,
package provenance and the input manifests, leaving reads and assembly intermediates
on BMRC. It then generates `dist/`: overview matrix, category index, one page per
scenario, methods, JSON and TSV.
The site is static and must be regenerated/redeployed to show later results.
`snapshot --batch BATCH_ID` saves the small public report in `published/` without
deployment; `publish --batch BATCH_ID` saves it and deploys to the linked Vercel
project. Commit publication snapshots so a fresh checkout can rebuild results:
`report` without a batch uses `published/latest.json` when present. Without a
snapshot it shows only unrun cases. Cluster collection is explicit and precedes
publication; publishing does not fetch newer cluster states automatically.

Deploy **only `dist/`** to the Vercel project. The live site does not need access to
BMRC or credentials. Vercel CLI caches/link state must stay inside this work area;
do not publish `data/`, `runs/`, environments or cluster configuration.
`config/vercel-project.json` contains only project/organisation identifiers, not
credentials, so publication from a fresh checkout still targets the intended site.
The local Vercel CLI must already be authenticated to an account with project access.

## Scores and limits

The first endpoint is exact dedicated-molecule recovery, allowing circular rotation
and reverse complement. Every expected plasmid must have exactly one matching contig;
duplicate/tandem-expanded outputs do not qualify. Identifiable extra full copies
also fail uniqueness. Chromosome recovery is recorded separately. Negative controls
have explicit tool-appropriate endpoints, as explained on the website.

A scientific fail means no unique exact molecule, not necessarily zero sequence
recovery. Partial recovery, general structural-error classification and topology
claims are not yet scored. Unclassified extra contigs are retained. Job errors,
timeouts and invalid inputs are separate from pass/fail counts. A killed Slurm task
may lack a final execution record; collection uses accounting to expose that failure.

The sequence audit checks input integrity, not independent biological truth. Independent biological
reference validation, S3 repeat/thread panels, S4 length challenges,
S5 linear references, realistic error models and matched real reads remain later work.

## Expanded S1/S2 panel and automatic updates

```sh
python3 benchmark.py --config config/next-stages.json plan
python3 benchmark.py --config config/next-stages.json submit
python3 benchmark.py follow --batch BATCH_ID --interval 60 --publish-interval 600 --max-hours 8
```

The expanded profile includes all five preferred references, 22 S1 cases and ten
S2 cases (32 inputs, 128 comparisons). Chromosome depth, seed, read lengths, tools
and resources match the pilot. Only plasmid depth changes in S2. Each versioned
config remains frozen with its batch. `follow` collects once per minute, deploys
changed results at most every ten minutes and publishes immediately when every
selected task is terminal. It stops after the configured time limit, records
its checkpoint in `runs/BATCH_ID/follow.json`, and retries collection/deployment
errors. Run it on a persistent controller with SSH and Vercel access; it does not
run assemblers locally or commit snapshots automatically. A stopped controller
can restart the same command. Scheduler and scientific failures remain separate.

## Website build

The controller needs Node.js/npm for the shared `@genomicx/ui` React shell.
`report` and `submit` install the exact declared frontend versions when needed
and compile cached assets under `website/generated/`. These compiled assets
are transferred to BMRC, where report generation needs only Python. Node modules
and compiled bundles are ignored; their package versions, source hashes and
asset hashes are included in the generated site's build metadata.

```sh
npm --prefix website run build
npm --prefix website run test:e2e
```

The static site supports category/species filtering, shared GenomicX navigation,
themes and status badges. Earlier versioned snapshots get their own pages under
Earlier batches. Public snapshots must be committed separately after collection
if they are to survive a fresh checkout.
