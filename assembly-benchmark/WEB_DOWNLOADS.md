# Presentation-only website

`benchmark.py render` publishes HTML pages, interactive graph models, plot images,
small overview indexes and table exports. It excludes full batch/result/graph
JSON downloads, Markdown duplicates and the complete backend ZIP. Links to those
excluded downloads are removed. The website is a presentation of the backend
output, not a second evidence archive.

The complete validated backend directory remains unchanged. Its portable ZIP is
written beside that directory (`<bundle>.zip`), outside the website output.
Neither the directory nor the archive is uploaded to Vercel. No scientific score,
source record, alignment or provenance value is changed by website packaging.
These backend artefacts can be archived separately when a storage destination is
chosen; this change does not upload them to another service.

Interactive graph JSON includes only the graph, availability and origin evidence
consumed by the viewer. It omits the duplicate contig inventory already displayed
as an HTML table. Existing coordinate evidence is retained. Identical batch CSS,
JavaScript and fonts use the single root asset directory. Plot images and useful
TSV downloads remain available.

`site-manifest.json` records the presentation-only policy, size reduction and
number/size of excluded evidence downloads. Former bulk JSON/ZIP URLs are no
longer served; they are not redirected to an unrelated page. Result page URLs,
images, table downloads and interactive graphs remain intact.

Local acceptance checks use the separate backend directory to verify every
result while checking only the actual published pages/downloads over HTTP:

```sh
node website/test-site.mjs dist .cache/bundles/storage-origin-v1
python3 -m unittest tests.test_web_downloads tests.test_bundle tests.test_publication_verification
```

The publication verifier checks every public file byte-for-byte and reads the
small site manifest when the evidence JSON is intentionally absent. No backend
computation or cluster rerun is required.
