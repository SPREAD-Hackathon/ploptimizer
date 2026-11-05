# Aggregate plots and the Wick comparison

The aggregate export reads existing result/input metadata only. It does not run
simulators, assemblers, aligners or new sequence assessments. The normal backend
`export` stage produces `aggregates/data.json`, TSV source tables, SVG/PNG figures
and `aggregates/index.json`; `render` copies those products into the website.
The complete results ZIP contains the figures independently of the web layer.

## Available figures

Each measured scenario/cohort gets separate outcome composition, plasmid
size-versus-achieved-depth, required-molecule mapped breadth, recorded alignment
identity, runtime/RAM and input-distribution figures. S3 gets its own saved
repeatability-group figure and is excluded from the recovery/resource plots.
Primary and supplementary results are never pooled. Historical pilot records are
excluded. Each observation retains its batch/scenario/tool/repeat identity.

Filled blue points indicate exact recovery and open orange points exact failure.
That symbol convention follows the useful visual idea in Wick's plasmid plots,
but the plotted endpoint is different. Coincident points may overlap; the TSV
retains each observation. Input histograms deduplicate read-hash/replicon records
within each cohort rather than counting one input once per assembler.

Missing values remain missing, with measured counts in the panels/index. Tool
errors remain separate in the execution-outcome figure. Mean read length is not
N50; alignment-weighted identity is not longest-alignment identity; union breadth
is not contiguity. Repeated cases and plasmids sharing an input are not independent
genomes. These descriptive figures have no confidence intervals or overall ranking.

## Dataset design: what to adopt

Wick and Holt used a broad panel with varied read properties and plasmid depth,
plus a separately evaluated real-data panel. Our saved suite is much smaller,
mostly error-free and organised around matched diagnostic controls. The current
coverage/error examples do not reproduce that broad experimental design.
[Study, version 4](https://pmc.ncbi.nlm.nih.gov/articles/PMC6966772/).

| Aspect | Saved Ploptimizer design | Wick and Holt |
| --- | --- | --- |
| Read generation | Exact custom sampler for most cases; bounded error-bearing S6 track | Badread with varied read quality and artefacts |
| Read lengths | Lognormal exact-sampler lengths, clipped to declared limits and one circular traversal | A broad range of read-length conditions |
| Dataset structure | Few curated references and matched diagnostic scenarios | Many reference genomes and varied conditions |
| Topology | Circular controls plus separate isolated linear-record controls | Simulated replicons treated as circular |
| Reference ambiguity | Reject non-ACGT records in exact controls | Ambiguous reference bases replaced during their preparation |

Sources: [study methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6966772/),
[Badread](https://github.com/rrwick/Badread); our recorded simulator and manifests
are the source for the current suite. These are substantive differences, so the
current inputs must not be described as reproducing Wick's simulated dataset.

Adopt the broad design principles as a separate general-evaluation track: a
clearly defined reference population, versioned read-generation provenance,
shared inputs across assemblers, input-distribution plots and independent
real-data validation. Keep exact-read controls and targeted plasmid challenges
in a diagnostic track. Keep computational repeats separate from independently
sampled inputs. The revised ≥20 kb baseline remains the ordinary-recovery control.

Do not silently copy historical versions, change ambiguous reference bases or
present the existing exact sampler as Badread. Reference uncertainty and physical
end curation remain explicit. No generation profile or reference admission was
changed in this reporting update; a broad dataset track remains a design proposal.

## Metric compatibility and original figures

Wick's contiguity uses the longest single alignment relative to reference length,
with a circular-reference representation that accommodates rotated contigs and
end overlaps. Our saved breadth metric unions retained alignment blocks. Neither
can be renamed as the other. Wick-style contiguity, circularisation-gap/overlap
and maximum-indel distributions are not yet measured by this export.
[Study assessment methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6966772/).

The website links all 11 original figure sets, including outcome/accuracy/resource
panels, reference/read-property distributions, circularisation schematics and
plasmid size/depth plots. These are clearly labelled original study results and
pinned to repository revision `4bc676c4a5b01602abf1143bfefcaab4cc0dde97`.
Ryan R. Wick and Kathryn E. Holt, CC BY 4.0. Figure links and attribution are in
`references/wick-figures.json`.
[Original repository](https://github.com/rrwick/Long-read-assembler-comparison).
