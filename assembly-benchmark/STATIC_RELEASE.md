# Static release safeguards

All commands run from `assembly-benchmark/` or through its absolute entry point.
They do not submit jobs or run sequence analyses.

```sh
python3 benchmark.py check-site --bundle .cache/bundles/failure-release-v2 --output dist --report .cache/release-check.json
```

The gate checks:

- Every local page/image/table link and HTML fragment, including clean URLs and base paths.
- Maximum 64 MiB total, 5 MiB per public file and 1,500 public files.
- No bulk evidence JSON, backend ZIP, duplicate Markdown, raw sequence or GFA artefacts in the presentation build.
- Bundle manifest integrity, the website's bundle binding and its render receipt.
- Every original execution field and identity against the frozen snapshot, with source checksums.
- Available plot, origin and internal-interval hashes against their recorded inputs.

`render` automatically runs the static-site checks and writes `.site-files.json`.
That hidden receipt fingerprints the generated public files, including pages, assets and deployment ignore rules. The full gate rejects later edits, stale/copied files, changed snapshots
or mismatched evidence. Re-render after changing presentation sources; do not
manually edit generated pages or copy assets into a reviewed build.

The existing `scripts/check_release.py` remains a separate check of saved job and
batch evidence. Static validation does not certify biological truth, fill missing
measurements, or turn a scientific fail into a pass.

## Production path

After the offline gate passes, the already-authorised project can be deployed with:

```sh
python3 benchmark.py deploy-site --bundle .cache/bundles/failure-release-v2 --output dist
```

This command requires the scoped `assembly-benchmark/dist`, re-runs the full gate,
uses the configured Vercel project and uploads one archive. It does not collect
outputs, update snapshots, re-run calculations or build the site. A successful
upload is not a verified release: use `scripts/verify_publication.py` for the
existing byte-for-byte live-page/download verification and inspect the live UI.

The old direct `publish` deployment path is disabled before it can rebuild or
mutate snapshots. Non-deploying snapshot collection is retained. An old automated
publisher must switch to the explicit export/render/check/deploy path; it cannot
silently publish a bulky legacy build. No live legacy publisher process was
found during this change. No deployment was attempted while the previously
reported Vercel daily upload quota remained the known blocker.

## Failure summaries

Source-bound review facts appear beside the failure verdict: recorded excess,
reference/output lengths and saved coordinate intervals, with their source fields.
They are also exported as `report_evidence.failure_summary` in the backend bundle.
An unreviewed failure keeps its original score and explicitly has no localised
reviewed difference. Alignment breadth and a length difference alone do not
manufacture a change event or a software-internal explanation.
