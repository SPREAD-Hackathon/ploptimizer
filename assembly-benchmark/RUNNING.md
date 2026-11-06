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
reference validation, broader repeat/thread panels, further length challenges,
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

## Determinism, length challenges and diagnostics

```sh
python3 benchmark.py --config config/small-plasmids.json submit --after-job PREVIOUS_REPORT_JOB
python3 benchmark.py --config config/determinism.json submit --after-job LENGTH_REPORT_JOB
python3 benchmark.py diagnose-submit --batch BATCH_ID --after-job ASSEMBLY_JOB
python3 benchmark.py follow --batch PRIMARY_BATCH --also-batch LENGTH_BATCH --also-batch REPEAT_BATCH --interval 60 --publish-interval 600 --max-hours 24
```

Dependencies serialize the experiment batches; each assembly array remains capped
at four concurrent tasks. S3 uses five repeats at one and four tool threads, with
four CPUs reserved per task in either setting. Repeats share a single checksummed
read file and write isolated execution directories. Their report separates byte,
normalised sequence and strict biological agreement; incomplete evidence is never
called identical. See [S4_READ_LENGTHS.md](S4_READ_LENGTHS.md) for the length panel.

The new `config/determinism-modes.json` adds Flye deterministic modes at both
thread counts (120 tasks, not submitted). Existing S3 runs used default mode only.
See [S3_REPEATABILITY.md](S3_REPEATABILITY.md).

`diagnose-submit` submits one CPU/4 GB/one-hour supplementary mapping work on the
compute node; it does not rerun assemblers or modify execution.json. It records
its job ID separately, and the follower waits for diagnostics before stopping.
The collector copies small diagnostic JSON/PAF evidence while large assemblies
remain on BMRC. Mapper failure is independent of a scientific pass or fail.

One follower coordinates all companion batches serially, snapshots them without
replacing the primary view, and deploys the primary report with linked batch pages.
Only one follower should own a site at a time. Restarting forces a publication
attempt so a failed previous deployment cannot masquerade as success. This is
a bounded process on the controller; it requires that machine and its SSH/network
connection to remain available. It records explicit retry and time-limit states.

## Reviewing failures before a batch finishes

```sh
python3 benchmark.py diagnose-submit --batch BATCH_ID --interim
python3 benchmark.py collect --batch BATCH_ID
```

An interim diagnostic job inspects the execution records available when it runs.
It has a separate script and submission record, preserving the queued final
mapping job. Completed evidence is cached; unfinished assembler runs are skipped
and revisited by the final job. Use `--interim --rerun` for another deliberate
review pass. Scheduler state is sampled before copying output records so a newly
completed task cannot appear as an error solely because collection raced its
final write.

The results pages distinguish strict recovery from supplementary mapping
explanations. No retained mapping is evidence under the stated filtering policy,
not proof that DNA is absent. The per-molecule recovery export preserves missing
values and diagnostic errors separately from measured zero recovery.

The next noisy-read design is in `REALISTIC_READS.md`. Its proposed configuration
is deliberately non-executable: the controller rejects `status: proposed`, and
the sampler refuses unknown models instead of silently generating exact reads.

## Historical controlled-error smoke workflow (S6)

These commands reproduce the completed small-plasmid W/pRK2 smoke panel, not
the revised S6 baseline. The replacement is documented in
`config/noisy-large.proposed.json`; it is not executable until larger-plasmid
assessment and truth controls are validated. Existing smoke results remain
supplementary and must not be relabelled as the revised panel.

```sh
python3 benchmark.py --config config/noisy-smoke.json plan
python3 benchmark.py --config config/noisy-smoke.json submit --assemble-after-job PREVIOUS_REPORT_JOB
```

The `simulator` Pixi environment pins Badread 0.4.2 and python-edlib1.3.9.post1.
Preparation freezes installed source/model/RNG binary hashes and checks tolerant
positive/negative controls on the actual references. It then generates identical
clean fragments per case/seed across the three error conditions. Badread transforms
those fragments without resampling geometry; independent final-read alignments
measure actual identity, emitted length and quality calibration. Input holds stop
assembly submission through the existing failed-dependency rule.

S6 adds an assessment job between assembly and reporting. It writes provenance-
matched `tolerant.json` without rewriting exact execution scores. Unresolved
repeat/copy/structural assignment is unscored. The controller waits for this stage
before completing publication. All four pre-existing tool environments retain
the same locked package URLs.

`--assemble-after-job` permits preparation and simulation now while deferring
assemblies, maintaining the four-task assembly budget across studies. Add the new
batch as another `--also-batch` to the single result updater. The three-case smoke
is smaller than the proposed 18-read-set/72-comparison expansion; the latter needs
smoke review before submission. This models controlled error packages, not a
calibrated contemporary nanopore experiment.

## Mechanistic pilot investigations

In a Slurm job with eight CPUs and the existing environments installed:

```sh
pixi run --locked -e simulator python scripts/investigate_causes.py --study-id UNIQUE_ID --tool-threads 4 --timeout 1800
```

This runs two concurrent causal-test chains, each with four tool threads, against
verified frozen pilot reads. Flye compares default and 3,000 bp overlap at the
initial assembly stage, then completes the latter. Raven compares zero, one and
two polishing rounds using independent copies of one fresh pre-polish checkpoint,
including a zero-round resume control. Each command has its own working directory.

Results go to `runs/20261104T183058/investigations/UNIQUE_ID/`, with incremental
JSON, versions, commands, hashes, checkpoints and stage FASTA/GFA. They do not
replace historical benchmark executions. The source-linked conclusions and limits
are in `FLYE_HYPOTHESES.md` and `RAVEN_CAUSE_REVIEW.md`; compact reproducibility
records are versioned under `reviews/evidence/`.

## Complete linear genomes (S5)

`python benchmark.py --config config/linear-plasmids.json plan` expands three
complete Streptomyces assemblies with all native replicons into six standard/long
inputs and 24 assembly tasks. No replacement run has been submitted. The model
requires full breadth and explicit terminal read support; Plassembler uses its
chromosome-aware workflow. Reports stay batch-scoped. Historical isolated
SCP1/SLP2 reproduction uses `config/linear-isolated-legacy.json`.
See [LINEAR_TERMINAL_REPEATS.md](LINEAR_TERMINAL_REPEATS.md) for sequence hashes,
terminal-repeat curation, read models and interpretation limits.
