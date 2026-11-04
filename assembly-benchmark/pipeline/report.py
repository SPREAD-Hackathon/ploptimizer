"""Generate a static, evidence-backed result matrix and scenario pages."""

import csv
import datetime
import html
import shutil

from .cases import plan
from .assets import ensure_assets
from .reviews import attach_sequence_review
from .assessments import attach_assessment
from .common import ROOT, digest, fingerprint, load, save
from .diagnostics import DEFAULT_POLICY

LABELS = {"flye": "Flye", "flye-meta": "Flye · uneven coverage", "raven": "Raven", "plassembler": "Plassembler long"}
STATUSES = {"pass": "Pass", "fail": "Fail", "not_run": "Not run", "pending": "Queued", "running": "Running", "error": "Job error", "timeout": "Timed out", "invalid_input": "Invalid input"}
CATEGORIES = {
    "S1": ("Error-free recovery", "Chromosome-only controls, individual native plasmids and complete deposited complements. These cases establish the baseline for each reference."),
    "S4": ("Small plasmids and read length", "Compare short, baseline and long read-length targets for small plasmids individually and in their native complements. Achieved read lengths are capped to one molecule circumference; targets describe simulation settings, not nanopore chemistry."),
    "S2": ("Relative plasmid coverage", "Hold chromosome depth and read properties fixed, and vary plasmid depth at 0.8×, 1×, 1.2×, 3× and 5× relative to it. These are coverage ratios, not measured biological copy numbers."),
}


def e(value):
    return html.escape(str(value))


def badge(status):
    return f'<span class="status {e(status)}" data-benchmark-status="{e(status)}">{e(STATUSES[status])}</span>'


def page(title, body, prefix="", active="overview"):
    links = [("overview", "index.html", "Results"), ("scenarios", "scenarios/index.html", "Scenarios"), ("methods", "methods.html", "Methods"), ("history", "history.html", "All batches")]
    nav = "".join(f'<a {"aria-current=page" if key == active else ""} href="{prefix}{url}">{label}</a>' for key, url, label in links)
    return f'''<!doctype html><html lang="en" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · Ploptimizer</title><meta name="description" content="Long-read plasmid assembly benchmark: scenarios, exact recovery outcomes and execution evidence.">
<script>try{{var theme=localStorage.getItem('gx-theme');if(theme==='light'||theme==='dark')document.documentElement.dataset.theme=theme;}}catch{{}}</script>
<link rel="stylesheet" href="{prefix}assets/genomicx.css"><script defer src="{prefix}assets/genomicx.js"></script></head><body><a class="skip" href="#main">Skip to content</a>
<div id="genomicx-nav"><header class="fallback-nav"><a href="{prefix}index.html">Ploptimizer</a><nav aria-label="Main navigation">{nav}</nav></header></div>
<main id="main">{body}</main><footer class="benchmark-footer gx-footer"><div class="gx-footer-inner"><div class="gx-footer-content"><div class="gx-footer-text"><p class="gx-footer-text-title">Ploptimizer</p><p class="gx-footer-text-sub">Assemblies run on BMRC. Results and evidence are published here.</p></div><div class="gx-footer-links"><a class="gx-footer-link" href="https://genomicx.org">GenomicX</a><a class="gx-footer-link" href="https://github.com/SPREAD-Hackathon/ploptimizer/tree/main/assembly-benchmark">Source &amp; specification</a></div></div></div></footer></body></html>'''


def result_status(record, scheduler_state):
    status = record.get("status", "not_run")
    terminal_errors = ("FAILED", "CANCELLED", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL", "DEADLINE", "PREEMPTED", "DEPENDENCY")
    if status in ("pass", "fail", "error", "timeout", "invalid_input"):
        return status
    if scheduler_state.startswith("TIMEOUT"):
        return "timeout"
    if scheduler_state.startswith(terminal_errors) or scheduler_state.startswith("COMPLETED"):
        return "error"
    if scheduler_state.startswith(("RUNNING", "COMPLETING")):
        return "running"
    if scheduler_state:
        return "pending"
    return status


def collect_records(config, batch):
    accounting = {}
    submission = load(batch / "submission.json") if batch and (batch / "submission.json").exists() else {}
    if batch and (batch / "accounting.tsv").exists():
        for line in (batch / "accounting.tsv").read_text().splitlines():
            fields = line.split("|")
            if len(fields) >= 2:
                accounting[fields[0]] = fields[1]
    tasks = submission.get("tasks", {}).get("assemble", [])
    output = []
    for case in plan(config):
        for tool in config["tools"]:
            path = batch / "results" / case["id"] / tool / "execution.json" if batch else None
            record = load(path) if path and path.exists() else {}
            if record and (record.get("scenario_fingerprint") != case["fingerprint"] or record.get("config_fingerprint") != fingerprint(config)):
                record = {"status": "error", "error": "Result provenance does not match this report configuration"}
            matches = [i for i, task in enumerate(tasks) if task == {"scenario": case["id"], "tool": tool}]
            state = ""
            if matches:
                job = submission.get("jobs", {}).get("assemble", "")
                state = accounting.get(f"{job}_{matches[0]}", accounting.get(job, ""))
                if not state and not record:
                    state = "PENDING"
            record = attach_assessment(attach_sequence_review(attach_diagnostics(record, path), path, batch), path)
            status = result_status(record, state)
            output.append({**record, "scenario_id": case["id"], "tool": tool, "status": status,
                           "scheduler_state": state or None})
    return output


def build(config, batch=None, output=None, document=None, include_history=True):
    if batch is None and document is None and (ROOT / "published/latest.json").exists():
        document = load(ROOT / "published/latest.json")
    if config.get("noisy_panel") or (document and document["config"].get("noisy_panel")):
        from .noisy_report import build_noisy
        return build_noisy(config, batch, output, document, include_history)
    if config.get("determinism") or (document and document["config"].get("determinism")):
        from .repeat_report import build_repeat
        return build_repeat(config, batch, output, document, include_history)
    output = output or ROOT / "dist"
    generated_assets = ensure_assets(ROOT)
    # Rebuild generated content; preserve only the CLI's ignored project-link state.
    for name in ("assets", "scenarios", "data"):
        if (output / name).exists():
            shutil.rmtree(output / name)
    (output / "assets").mkdir(parents=True, exist_ok=True)
    (output / "scenarios").mkdir(exist_ok=True)
    (output / "data").mkdir(exist_ok=True)
    shutil.copytree(generated_assets, output / "assets", dirs_exist_ok=True)
    snapshot = ROOT / "published/latest.json"
    if document is not None or (batch is None and snapshot.exists()):
        document = document or load(snapshot)
        config = document["config"]
        cases = document["scenarios"]
        results = document["results"]
        generated = document["generated_at"]
    else:
        cases = plan(config)
        results = collect_records(config, batch)
        generated = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        for row in results:
            row.pop("host", None)
            row["command"] = ["<workdir>" + x[x.index("/runs/"):] if "/runs/" in x else x for x in row.get("command", [])]
        inputs = {}
        if batch:
            for case in cases:
                path = batch / "cases" / case["id"] / "input.json"
                if path.exists():
                    inputs[case["id"]] = load(path)
        provenance = {}
        if batch:
            for path in (batch / "provenance").glob("*.json"):
                provenance[path.stem] = load(path)
        document = {"schema_version": 1, "generated_at": generated, "batch": batch.name if batch else None,
                    "config": config, "scenarios": cases, "results": results, "inputs": inputs,
                    "provenance": provenance}
    save(output / "data/results.json", document)
    with (output / "data/results.tsv").open("w", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["scenario", "tool", "status", "plasmid_passes", "plasmid_total", "elapsed_seconds", "peak_memory_kb"])
        for row in results:
            score = row.get("evaluation", {})
            writer.writerow([row["scenario_id"], row["tool"], row["status"], score.get("plasmid_passes"), score.get("plasmid_total"), row.get("elapsed_seconds"), row.get("peak_memory_kb")])
    write_diagnostic_tsv(output, cases, results)
    counts = {tool: {status: sum(r["tool"] == tool and r["status"] == status for r in results) for status in STATUSES} for tool in config["tools"]}
    completed = sum(r["status"] in ("pass", "fail") for r in results)
    valid_inputs = sum(item["status"] == "valid" for item in document.get("inputs", {}).values())
    headline = f'{completed} of {len(results)} comparisons scored · {len(cases)} scenarios · {valid_inputs} inputs ready'
    body = f'<div class="page-heading"><h1>Can the assembler recover the plasmid?</h1><p>Error-free reads first. Each cell tests one assembler configuration against one known chromosome–plasmid combination.</p></div><p class="run-summary">Batch total: {headline}</p>'
    body += '<div class="notice"><strong>What counts as a pass?</strong> Every expected plasmid must appear exactly once as a complete, separate sequence. A circular sequence may start anywhere or be reverse-complemented. This first endpoint does not assess topology claims or classify partial recovery.</div>'
    category_options = ''.join(f'<option value="{key}">{key} · {e(CATEGORIES[key][0])}</option>' for key in sorted({c["category"] for c in cases}))
    body += f'<div class="filters"><label>Scenario category<select id="category-filter" disabled><option value="">All categories</option>{category_options}</select></label><label>Species<select id="species-filter" disabled><option value="">All species</option><option value="Escherichia">E. coli</option><option value="Klebsiella">K. pneumoniae</option></select></label><span id="filter-count" aria-live="polite">{len(cases)} scenarios shown</span></div>'
    body += '<div class="table-scroll" role="region" aria-label="Assembler result matrix" tabindex="0"><table class="matrix"><caption>Open a scenario or result to inspect its inputs and evidence. The chromosome-only control uses a separate endpoint.</caption><thead><tr><th scope="col">Scenario</th>'
    for tool in config["tools"]:
        c = counts[tool]
        unresolved = len(cases) - c["pass"] - c["fail"]
        body += f'<th scope="col">{e(LABELS[tool])}<span class="column-summary" data-summary-tool="{tool}">{c["pass"]} pass · {c["fail"]} fail · {unresolved} unscored</span></th>'
    body += '</tr></thead><tbody>'
    for case in cases:
        plasmids = [r for r in case["replicons"] if r["molecule_type"] == "plasmid"]
        sizes = ", ".join(f'{r["length_bp"] / 1000:.1f} kb' for r in plasmids) or "Negative control"
        noun = "plasmid" if len(plasmids) == 1 else "plasmids"
        body += f'<tr data-category="{case["category"]}" data-species="{case["organism"].split()[0]}"><th scope="row"><a href="scenarios/{e(case["id"])}.html">{e(case["title"])}</a><span class="row-summary"><span class="category-label">{case["category"]}</span> · {len(plasmids)} {noun} · {e(sizes)}</span></th>'
        for tool in config["tools"]:
            row = next(r for r in results if r["scenario_id"] == case["id"] and r["tool"] == tool)
            body += f'<td data-tool="{tool}" data-status="{row["status"]}"><a class="result-link" href="scenarios/{e(case["id"])}.html#{tool}">{badge(row["status"])}</a><span class="row-summary">{e(diagnostic_summary(row, case))}</span></td>'
        body += '</tr>'
    body += '</tbody></table></div><p class="legend">Pass and fail are completed sequence assessments. Queued, running, invalid inputs and job errors are unscored; they are never counted as scientific failures.</p>'
    body += f'<div class="downloads"><a href="data/results.json">Download JSON</a><a href="data/results.tsv">Download TSV</a><a href="data/recovery-evidence.tsv">Recovery evidence TSV</a><span>Updated {e(generated)} · Batch {e(document["batch"] or "not submitted")}</span></div>'
    (output / "index.html").write_text(page("Results", body))
    category = '<h1>Scenarios</h1><p class="intro">Controlled cases with known reference molecules. Start with exact reads, then add complexity one factor at a time.</p>'
    for key in sorted({case["category"] for case in cases}):
        name, description = CATEGORIES[key]
        category += f'<h2>{key} · {e(name)}</h2><p>{e(description)}</p><ul class="scenario-list">'
        for case in (c for c in cases if c["category"] == key):
            category += f'<li><a href="{case["id"]}.html">{e(case["title"])}</a><span>{e(case["truth_type"].replace("_", " "))}</span></li>'
        category += '</ul>'
    for case in cases:
        rows = [r for r in results if r["scenario_id"] == case["id"]]
        (output / "scenarios" / (case["id"] + ".html")).write_text(page(case["title"], scenario_page(case, rows, batch, document.get("inputs", {}).get(case["id"]), output, document["batch"]), "../", "scenarios"))
    category += '<h2>Study extensions</h2><p>Repeated/thread runs (S3) and small-plasmid read-length challenges (S4) run as separate batches. See <a href="../history.html">all batches</a> for their settings and progress. Biologically linear plasmids (S5) remain a planned extension.</p>'
    (output / "scenarios/index.html").write_text(page("Scenarios", category, "../", "scenarios"))
    methods = (ROOT / "website/methods.html").read_text()
    (output / "methods.html").write_text(page("Methods", methods, active="methods"))
    about = '<h1>About Ploptimizer</h1><p class="intro">A benchmark for the assembly problems that disappear inside whole-genome summary scores.</p><p>We assess whether long-read assembly workflows recover chromosomes and plasmids correctly, starting with E. coli and K. pneumoniae. Controlled reference subsets, coverage panels and explicit sequence endpoints make individual failures inspectable.</p><p>The results matrix links to the inputs, tool configuration, run evidence and limitations for each scenario. Runs execute on the BMRC cluster using Slurm and Pixi; this site presents static result snapshots.</p><p><a href="methods.html">Read the methods</a> or <a href="https://github.com/SPREAD-Hackathon/ploptimizer/tree/main/assembly-benchmark">inspect the source and brief</a>.</p>'
    (output / "about.html").write_text(page("About", about, active="about"))
    write_history(output, document, include_history)
    save(output / "vercel.json", {"cleanUrls": True})
    (output / ".vercelignore").write_text(".env*\n.vercel\n.gitignore\n")
    if batch:
        destination = batch / "site"
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(output, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".vercel", ".env*", ".gitignore"))
    return output


def scenario_page(case, rows, batch, manifest=None, output=None, batch_id=None):
    settings = case["simulation"]
    category_name, category_description = CATEGORIES[case["category"]]
    body = f'<a class="back" href="index.html">All scenarios</a><h1>{e(case["title"])}</h1><p class="intro">{case["category"]} · {e(category_name)} · {e(case["organism"])}</p><p>{e(category_description)}</p>'
    if batch_id:
        body += f'<p class="muted">Batch <code>{e(batch_id)}</code></p>'
    body += '<h2>What this case tests</h2><p>Can each expected plasmid be recovered once as an exact, dedicated molecule alongside the chromosome? For the chromosome-only control, the endpoint checks the expected chromosome/no-plasmid output instead.</p>'
    body += f'<p>Source: <a href="https://www.ncbi.nlm.nih.gov/datasets/genome/{case["assembly_accession"]}/">{case["assembly_accession"]}</a>. This case is a {e(case["truth_type"].replace("_", " "))}. The reference inventory is sequence-checked during preparation; independent biological validation remains a separate curation task.</p>'
    input_path = batch / "cases" / case["id"] / "input.json" if batch else None
    if manifest is None:
        manifest = load(input_path) if input_path and input_path.exists() else None
    stats = {r["accession"]: r for r in manifest["replicons"]} if manifest else {}
    body += f'<h2>Read generation</h2><p>Exact sequence sampling; lognormal length targets with mean {settings["length_mean"]:,} bp and SD {settings["length_sd"]:,} bp, clipped to {settings["length_min"]:,}–{settings["length_max"]:,} bp and one circumference. Random starts and both strands; no sequencing errors, adapters or chimeras. Q{settings["fastq_phred"]} is a synthetic FASTQ placeholder. Small molecules have a shorter achieved distribution.</p><p>Target chromosome depth {settings["chromosome_depth"]}×; plasmid relative depth {settings["plasmid_relative_depth"]}×. Seed {settings["seed"]}. Sampling stops after the target is reached, allowing up to one read of overshoot per molecule.</p>'
    body += '<div class="table-scroll" tabindex="0" role="region" aria-label="Reference molecules"><table><thead><tr><th scope="col">Molecule</th><th scope="col">Accession</th><th scope="col">Size</th><th scope="col">Achieved depth</th><th scope="col">Breadth</th><th scope="col">Read count</th><th scope="col">Read length mean / range</th></tr></thead><tbody>'
    for r in case["replicons"]:
        observed = stats.get(r["refseq_accession"])
        depth = f'{observed["achieved_depth"]:.2f}×' if observed else "Not generated"
        breadth = f'{observed["breadth"]:.2%}' if observed else "Not generated"
        read_count = f'{observed["read_count"]:,}' if observed else "Not generated"
        lengths = f'{observed["mean_read_length"]:,.0f} / {observed["minimum_read_length"]:,}–{observed["maximum_read_length"]:,} bp' if observed else "Not generated"
        body += f'<tr><th scope="row">{e(r["replicon_name"])}</th><td><a href="https://www.ncbi.nlm.nih.gov/nuccore/{r["refseq_accession"]}">{r["refseq_accession"]}</a></td><td>{r["length_bp"]:,} bp</td><td>{depth}</td><td>{breadth}</td><td>{read_count}</td><td>{lengths}</td></tr>'
    body += '</tbody></table></div><h2>Assembler results</h2>'
    for row in rows:
        body += f'<section class="assembler-result" id="{row["tool"]}"><h3>{e(LABELS[row["tool"]])} {badge(row["status"])}</h3>'
        if row.get("error"):
            body += f'<p>{e(row["error"])}</p>'
        if row.get("version"):
            body += f'<p>Version: <code>{e(row["version"])}</code> · {row.get("threads")} threads · {row.get("elapsed_seconds", 0):.1f} seconds'
            if row.get("peak_memory_kb") is not None:
                body += f' · {row["peak_memory_kb"] / 1024:.1f} MiB peak memory'
            body += '</p>'
        score = row.get("evaluation")
        if score:
            body += f'<p>Pass criterion: {e(score["endpoint"])}.</p><ul>'
            for r in score["replicons"]:
                if row["tool"] == "plassembler" and r["molecule_type"] == "chromosome":
                    continue
                body += f'<li>{e(r["name"])}: {badge(r["status"])} · {e(r["reason"])}</li>'
            body += '</ul><p class="muted">The strict endpoint is unchanged by supplementary mapping. Aligned recovery below can help explain a failure; topology claims are not scored.</p>'
            if row.get("initial_flye_evaluation"):
                initial = row["initial_flye_evaluation"]
                body += f'<p>Paired initial Flye result: {badge(initial["status"])} · {initial["plasmid_passes"]}/{initial["plasmid_total"]} exact plasmids.</p>'
        else:
            body += '<p>No completed sequence assessment is available for this configuration.</p>'
        if row.get("sequence_review"):
            review = row["sequence_review"]
            body += f'<div class="notice"><strong>Checked sequence discrepancy</strong>{e(review["explanation"])} <a href="https://github.com/SPREAD-Hackathon/ploptimizer/blob/main/assembly-benchmark/FAILURE_REVIEW.md">Read the provisional review</a>.</div>'
        if row.get("diagnostics"):
            body += diagnostic_table(row["diagnostics"], plasmid_only=row["tool"] == "plassembler", evaluation=score)
        else:
            body += f'<p class="muted">{e(diagnostic_summary(row, case))}.</p>'
        if row.get("started_at"):
            public = {k: row[k] for k in row if k not in ("host", "assembly_file", "command")}
            public["command"] = [str(x).replace(str(ROOT), "<workdir>") for x in row.get("command", [])]
            name = case["id"] + "-" + row["tool"] + ".json"
            save((output or ROOT / "dist") / "data" / name, public)
            body += f'<p><a href="../data/{name}">Execution and scoring record (JSON)</a></p>'
        body += '</section>'
    if manifest:
        body += f'<h2>Input evidence</h2><p>Input validation: <strong>{e(manifest["status"])}</strong>. Read-file SHA-256:</p><code class="checksum">{manifest["reads_sha256"]}</code>'
    body += '<p><a href="../methods.html">Read the scoring rules and limitations</a></p>'
    return body


def write_history(output, document, include_history=True):
    if include_history:
        shutil.rmtree(output / "batches", ignore_errors=True)
        history = '<h1>All batches</h1><p class="intro">Keep each batch separate: inputs, settings and scenario coverage can differ. Completed, running and queued batches remain separate. Counts below use strict exact recovery; noisy batches show tolerant outcomes on their own page. Open a batch to inspect its settings and progress.</p><ul class="scenario-list">'
        current_pass = sum(row["status"] == "pass" for row in document["results"])
        current_fail = sum(row["status"] == "fail" for row in document["results"])
        current_unscored = len(document["results"]) - current_pass - current_fail
        history += f'<li><a href="index.html">Current · {e(document["config"]["profile_id"])}</a><span>{current_pass} pass · {current_fail} fail · {current_unscored} unscored</span></li>'
        for path in sorted((ROOT / "published").glob("*.json"), reverse=True):
            if path.name == "latest.json":
                continue
            archived = load(path)
            if archived["batch"] == document["batch"]:
                continue
            passes = sum(row["status"] == "pass" for row in archived["results"])
            fails = sum(row["status"] == "fail" for row in archived["results"])
            identifier = archived["batch"]
            build(archived["config"], output=output / "batches" / identifier, document=archived, include_history=False)
            unscored = len(archived["results"]) - passes - fails
            history += f'<li><a href="batches/{identifier}/index.html">{identifier} · {e(archived["config"]["profile_id"])}</a><span>{passes} pass · {fails} fail · {unscored} unscored</span></li>'
        history += '</ul><p><a href="index.html">Return to the current batch</a></p>'
        (output / "history.html").write_text(page("All batches", history, active="history"))
    else:
        # Shared navigation on archive pages returns to the live report's history.
        (output / "history.html").write_text(page("All batches", '<h1>Batch archive</h1><p><a href="/history.html">Browse all earlier batches</a></p>', active="history"))


def diagnostic_policy(diagnostic):
    return {**DEFAULT_POLICY, **diagnostic.get("policy", {}), **diagnostic.get("evidence", {}).get("policy", {})}


def alignment_classification(row, policy):
    fraction = row["recovered_fraction"]
    if fraction <= 0 or row.get("candidate_flags", {}).get("no_supported_alignment"):
        return "none", "No retained alignment"
    if fraction >= 1 - 1e-9:
        return "full", "Full aligned recovery"
    if fraction >= policy["complete_fraction"]:
        return "near_full", "Near-full aligned recovery"
    return "partial", "Partial aligned recovery"


def candidate_labels(row):
    flags = row.get("candidate_flags", {})
    return [label for key, label in (("fragmented", "fragmentation"), ("duplicated", "duplication"), ("joined", "join")) if flags.get(key)]


def diagnostic_state(diagnostic):
    if not diagnostic:
        return "Recovery diagnostics not available"
    status = diagnostic.get("status")
    if status in ("running", "pending", "queued"):
        return "Recovery mapping pending" if status != "running" else "Recovery mapping running"
    if status == "error":
        return "Mapper diagnostic error"
    if status == "skipped":
        return "Recovery mapping skipped"
    return "Recovery diagnostics not available"


def diagnostic_summary(record, case):
    """A compact mapping explanation, never a replacement for strict pass/fail."""
    if record.get("sequence_review"):
        return record["sequence_review"]["summary"]
    diagnostic = record.get("diagnostics")
    if not diagnostic or diagnostic.get("status") != "complete":
        if not diagnostic and record["status"] in ("not_run", "pending", "running"):
            return "Awaiting assembly assessment"
        return diagnostic_state(diagnostic)
    plasmids = {row["refseq_accession"] for row in case["replicons"] if row["molecule_type"] == "plasmid"}
    if not plasmids and record["tool"] == "plassembler":
        return "Final plasmid output only; chromosome assessed separately"
    expected = plasmids or {row["refseq_accession"] for row in case["replicons"]}
    rows = [row for row in diagnostic["evidence"]["replicons"] if row["accession"] in expected]
    failed = {row["accession"] for row in record.get("evaluation", {}).get("replicons", [])
              if row["status"] == "fail" and row["accession"] in expected}
    if failed:
        rows = [row for row in rows if row["accession"] in failed]
    if not rows:
        return "No matching molecule evidence collected"
    labels = list(dict.fromkeys(alignment_classification(row, diagnostic_policy(diagnostic))[1] for row in rows))
    flags = list(dict.fromkeys(label for row in rows for label in candidate_labels(row)))
    summary = "; ".join(labels)
    if record["status"] == "fail" and any(alignment_classification(row, diagnostic_policy(diagnostic))[0] in ("full", "near_full") for row in rows):
        summary += "; exact recovery failed"
    if any(alignment_classification(row, diagnostic_policy(diagnostic))[0] == "none" for row in rows):
        summary += "; absence not established"
    if flags:
        summary += "; candidate " + ", ".join(flags)
    return summary


def molecule_explanation(row, policy, strict=None):
    kind, label = alignment_classification(row, policy)
    if kind == "none":
        molecule = "plasmid" if row["molecule_type"] == "plasmid" else "chromosome"
        text = f"No retained alignment under this mapping policy. This is not evidence of {molecule} absence: filtering or alignment heuristics can hide short, shared or repetitive sequence."
    else:
        text = f'{label}: {row["aligned_reference_bp"]:,}/{row["length_bp"]:,} reference bases ({row["recovered_fraction"]:.2%}) are covered by retained alignments'
        if row.get("alignment_identity") is not None:
            text += f', with {row["alignment_identity"]:.3%} alignment identity'
        text += "."
        if strict and strict["status"] == "fail":
            text += " The exact endpoint still fails; mapped coverage does not establish an exact, unique dedicated molecule."
        elif strict and strict["status"] == "pass":
            text += " The separate strict sequence endpoint passes."
    labels = candidate_labels(row)
    if labels:
        text += " Candidate " + ", ".join(labels) + " evidence needs review; these flags can overlap and are not confirmed structural errors."
    return text


def diagnostic_table(diagnostic, plasmid_only=False, evaluation=None):
    if diagnostic.get("status") != "complete":
        body = f'<p>{e(diagnostic_state(diagnostic))}. Supplementary recovery evidence is unavailable; the strict score is unchanged.</p>'
        if diagnostic.get("error") or diagnostic.get("reason"):
            body += f'<p class="muted">{e(diagnostic.get("error") or diagnostic["reason"])}</p>'
        return body
    policy = diagnostic_policy(diagnostic)
    body = '<h4>Aligned recovery evidence</h4><p class="muted">Supplementary mapping evidence; the exact pass/fail score is unchanged. Candidate flags need review and do not establish topology or a structural error.</p>'
    if plasmid_only:
        body += '<p class="muted">Final plasmid output only; retained chromosome recovery is assessed separately.</p>'
    rows = [row for row in diagnostic["evidence"]["replicons"] if not (plasmid_only and row["molecule_type"] == "chromosome")]
    scores = {row["accession"]: row for row in (evaluation or {}).get("replicons", [])}
    if rows:
        body += '<ul>'
        for row in rows:
            body += f'<li><strong>{e(row["name"])}</strong>: {e(molecule_explanation(row, policy, scores.get(row["accession"])))}</li>'
        body += '</ul>'
    else:
        body += '<p>No plasmids are expected in this control. The final plasmid output does not assess chromosome recovery.</p>' if plasmid_only else '<p>No molecule-level mapping evidence has been collected.</p>'
    body += '<div class="table-scroll" role="region" aria-label="Aligned recovery evidence" tabindex="0"><table><thead><tr><th scope="col">Molecule</th><th scope="col">Aligned reference</th><th scope="col">Alignment identity</th><th scope="col">Supporting contigs</th><th scope="col">Candidate evidence</th></tr></thead><tbody>'
    for row in rows:
        identity = f'{row["alignment_identity"]:.3%}' if row["alignment_identity"] is not None else "Not estimated"
        labels = candidate_labels(row)
        flags = "Candidate " + ", ".join(labels) if labels else "No retained alignment" if alignment_classification(row, policy)[0] == "none" else "No flags under this policy"
        body += f'<tr><th scope="row">{e(row["name"])}</th><td>{row["aligned_reference_bp"]:,}/{row["length_bp"]:,} bp ({row["recovered_fraction"]:.2%})</td><td>{identity}</td><td>{row["contig_count"]}</td><td>{e(flags)}</td></tr>'
    body += '</tbody></table></div>'
    body += f'<p class="muted">Retained alignments require mapQ ≥{policy["minimum_mapq"]}, at least {policy["minimum_aligned_bp"]} aligned reference bases and identity ≥{policy["minimum_identity"]:.0%}; secondary, ambiguous-base and non-base-aligned records are excluded. Near-full means ≥{policy["complete_fraction"]:.0%} aligned reference coverage, not exact recovery. Candidate fragmentation requires multiple contigs, best-contig coverage below {policy["complete_fraction"]:.0%} and a union gain of at least {policy["fragmentation_gain_fraction"]:.0%}; candidate duplication requires overlapping reference coverage ≥{policy["duplication_fraction"]:.0%}; candidate joins use distinct reference molecules on query segments overlapping by at most {policy["maximum_query_overlap_fraction"]:.0%}. These flags do not establish a structural error.</p>'
    body += f'<p class="muted">Mapper: {e(diagnostic.get("mapper_version", "unknown"))}. {e(diagnostic["evidence"]["limitations"])}</p>'
    return body


def attach_diagnostics(record, path):
    diagnostic_path = path.parent / "diagnostics.json" if path else None
    if record and diagnostic_path and diagnostic_path.exists():
        diagnostic = load(diagnostic_path)
        hashes = diagnostic.get("input_hashes", {})
        if hashes.get("execution_sha256") == digest(path) and hashes.get("assembly_sha256") == record.get("assembly_sha256"):
            record["diagnostics"] = {key: value for key, value in diagnostic.items() if key != "command"}
    return record


def write_diagnostic_tsv(output, cases, results):
    """Export molecule-level mapping evidence with explicit unavailable states."""
    by_id = {case["id"]: case for case in cases}
    fields = ("scenario_id", "tool", "accession", "molecule_name", "molecule_type", "strict_status", "diagnostics_status",
              "aligned_reference_fraction", "alignment_identity", "contig_count", "candidate_fragmentation", "candidate_duplication",
              "candidate_join", "no_retained_alignment", "minimum_mapq", "minimum_aligned_bp", "minimum_identity", "near_full_fraction")
    with (output / "data/recovery-evidence.tsv").open("w", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(fields)
        for record in results:
            diagnostic = record.get("diagnostics") or {}
            available = diagnostic.get("status") == "complete"
            observed = {row["accession"]: row for row in diagnostic.get("evidence", {}).get("replicons", [])} if available else {}
            scores = {row["accession"]: row["status"] for row in record.get("evaluation", {}).get("replicons", [])}
            policy = diagnostic_policy(diagnostic)
            for molecule in by_id[record["scenario_id"]]["replicons"]:
                if record["tool"] == "plassembler" and molecule["molecule_type"] == "chromosome":
                    continue
                accession = molecule["refseq_accession"]
                row = observed.get(accession, {})
                flags = row.get("candidate_flags", {})
                writer.writerow([record["scenario_id"], record["tool"], accession, molecule["replicon_name"], molecule["molecule_type"],
                                 scores.get(accession), diagnostic.get("status", "not_available"), row.get("recovered_fraction"),
                                 row.get("alignment_identity"), row.get("contig_count"), flags.get("fragmented"), flags.get("duplicated"),
                                 flags.get("joined"), flags.get("no_supported_alignment"),
                                 *[policy[key] if available else None for key in ("minimum_mapq", "minimum_aligned_bp", "minimum_identity", "complete_fraction")]])
