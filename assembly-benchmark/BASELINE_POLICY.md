# Revised baseline: ordinary recovery before small-plasmid challenges

Policy ID: `large-plasmid-baseline-v2`. Boundary: **20,000 bp inclusive**.
This is a reporting policy over saved metadata; it does not change reference
sequences, frozen input manifests, execution commands or scientific scores.

| Family | Required scope |
| --- | --- |
| S1 | Error-free reads: chromosome only; chromosome plus one plasmid ≥20 kb; chromosome plus multiple plasmids, each ≥20 kb. |
| S2 | The larger-plasmid baseline complement, changing only plasmid coverage relative to the chromosome. |
| S3 | One fixed larger-plasmid input; compare repeats within mode/thread groups and across thread settings. Recovery against the reference remains secondary. |
| S4 | Plasmids below 20 kb, individually and with larger plasmids; label read-length and other changes explicitly. |

A mixed complement with even one plasmid below 20 kb is outside the S1–S3
baseline. Size eligibility alone does not prove that other experimental factors
are controlled. Compare frozen manifests when interpreting matched cases.
A subset of a native complement remains a derived subset, not a new native genome.

## Existing references and results

Reference accessions and molecule lengths remain as originally recorded. The
report checks every plasmid in a saved input, rather than assigning an entire
reference genome to the large- or small-plasmid category. A genome can supply
both eligible saved controls and supplementary mixed-size results.

- S1: 52 eligible executions (35 pass, 17 fail), covering chromosome-only and
  individual larger-plasmid controls. No existing all-large multiple-plasmid case
  fulfils the revised complement requirement.
- S1 supplementary: 36 executions containing small plasmids (10 pass, 26 fail).
- S2: all 40 existing executions use small plasmids. They remain supplementary;
  the revised larger-plasmid coverage panel is **not assessed**.
- S3: all 80 existing executions use small plasmids. Their saved repeatability
  comparisons remain supplementary; the revised fixed larger-plasmid case is
  **not assessed**. Deterministic-mode execution is not implied.
- S4, S5 and S6 retain their existing scopes and results.

Supplementary runs keep their original scenario identifiers, detailed pages,
commands, plots, downloads and scores. They are not relabelled as new S4 runs or
silently pooled into revised baseline counts. Archived batch views retain their
historical cohort; the current overview applies the new reporting policy.

## Backend and website contract

`config/overview.json` versions the reporting policy. `pipeline/cohort_policy.py`
classifies saved cases from molecule type and length metadata. Missing length or
chromosome context cannot earn baseline eligibility. The derived overview exports
`cohort_role` and `cohort_reason` for every record, plus separate primary,
supplementary and all-record counts. Frozen publication snapshots remain unchanged.
The backend bundle exports this model; the website consumes it and places
supplementary result links in a separate disclosure.

This change does not select replacement reference genomes, produce new simulated
reads or submit new assembly jobs. The unassessed complement/coverage/repeatability
gaps remain explicit rather than being presented as completed baseline coverage.
