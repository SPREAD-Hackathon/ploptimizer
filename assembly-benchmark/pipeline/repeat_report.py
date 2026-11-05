"""Static S3 pages that separate repeatability from biological correctness."""

import collections
import copy
import csv
import datetime
import shutil

from .assets import ensure_assets
from .cases import plan
from .common import ROOT, load, save
from .result_pages import enrich_graph_artifacts, result_href, write_result_pages
from .determinism import assembly_tasks, collect_summary
from .report import LABELS, badge, batch_progress, e, execution_evidence, explained_records, finding_panel, interpretation_guide, page, write_history


METRICS = (("byte", "File bytes"), ("normalised_sequence", "Normalised sequences"), ("biological", "Biological outcomes"))


def comparison(value):
    return "Identical" if value is True else "Different" if value is False else "Not assessed"


def summary_table(groups, cases, across=False, prefix="scenarios/"):
    titles = {case["id"]: case["title"] for case in cases}
    heading = "Across thread settings" if across else "Within each thread setting"
    body = f'<h2>{heading}</h2><div class="table-scroll" role="region" aria-label="{heading}" tabindex="0"><table><caption>Identical describes observed repeatability. It does not mean the plasmid was assembled correctly. Missing runs or unequal/unverified inputs are not assessed.</caption><thead><tr><th scope="col">Scenario</th><th scope="col">Assembler</th><th scope="col">Threads</th>'
    if not across:
        body += '<th scope="col">Sequence assessments</th>'
    body += '<th scope="col">Frozen inputs</th>'
    body += ''.join(f'<th scope="col">{title}</th>' for _, title in METRICS) + '</tr></thead><tbody>'
    for group in groups:
        case_id = group["scenario_id"]
        threads = ', '.join(map(str, group["threads"])) if across else str(group["threads"])
        body += f'<tr><th scope="row"><a href="{prefix}{e(case_id)}.html#{e(group["tool"])}">{e(titles[case_id])}</a></th><td>{e(LABELS[group["tool"]])}</td><td>{threads}</td>'
        if not across:
            body += f'<td>{group["scored_runs"]} / {group["expected_runs"]}</td>'
        body += f'<td>{comparison(group.get("inputs_identical"))}</td>'
        body += ''.join(f'<td>{comparison(group.get(key + "_identical"))}</td>' for key, _ in METRICS) + '</tr>'
    return body + '</tbody></table></div>'


def unrun_summary(config, cases):
    """A plan preview has no evidence of repeatability or sequence correctness."""
    tasks = assembly_tasks(config, cases)
    executions = [{**task, "scenario_id": task["scenario"], "status": "not_run"} for task in tasks]
    within = [{"scenario_id": case["id"], "tool": tool, "threads": threads,
               "expected_runs": config["determinism"]["repeats"], "scored_runs": 0,
               "complete": False, "inputs_identical": None}
              for case in cases for tool in config["tools"] for threads in config["determinism"]["threads"]]
    across = [{"scenario_id": case["id"], "tool": tool, "threads": config["determinism"]["threads"],
               "complete": False, "inputs_identical": None} for case in cases for tool in config["tools"]]
    return {"category": "S3", "expected_runs": len(executions), "executions": executions,
            "within_thread": within, "across_threads": across, "status_counts": {"not_run": len(executions)},
            "limitations": "Observed repeatability on one frozen read set is not a guarantee of determinism."}


def build_repeat(config, batch=None, output=None, document=None, include_history=True):
    document = copy.deepcopy(document) if document is not None else None
    output = output or ROOT / "dist"
    generated_assets = ensure_assets(ROOT)
    for name in ("assets", "scenarios", "data"):
        if (output / name).exists():
            shutil.rmtree(output / name)
    for name in ("assets", "scenarios", "data"):
        (output / name).mkdir(parents=True, exist_ok=True)
    shutil.copytree(generated_assets, output / "assets", dirs_exist_ok=True)
    snapshot = ROOT / "published/latest.json"
    if document is None and batch is None and snapshot.exists():
        candidate = load(snapshot)
        if candidate["config"].get("determinism"):
            document = candidate
    if document is None:
        cases = [case for case in plan(config) if case["id"] in config["determinism"]["scenarios"]]
        summary = copy.deepcopy(collect_summary(config, batch) if batch else unrun_summary(config, cases))
        for row in summary["executions"]:
            row.pop("host", None)
            row["command"] = ["<workdir>" + str(value)[str(value).index("/runs/"):] if "/runs/" in str(value)
                              else str(value) for value in row.get("command", [])]
        from .explanations import attach_explanation
        by_id = {case["id"]: case for case in cases}
        summary["executions"] = [attach_explanation(row,
            execution_path=batch / "results" / row["scenario_id"] / row["tool"] / "repeats" / row["run_id"] / "execution.json" if batch else None,
            case=by_id[row["scenario_id"]]) if row["status"] not in ("pending", "running", "not_run") else row
            for row in summary["executions"]]
        inputs, provenance = {}, {}
        if batch:
            for case in cases:
                path = batch / "cases" / case["id"] / "input.json"
                if path.exists():
                    inputs[case["id"]] = load(path)
            for path in (batch / "provenance").glob("*.json"):
                provenance[path.stem] = load(path)
        document = {"schema_version": 1, "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                    "batch": batch.name if batch else None, "config": config, "scenarios": cases,
                    "results": summary["executions"], "determinism": summary, "inputs": inputs, "provenance": provenance}
    config, cases = document["config"], document["scenarios"]
    summary, results = document["determinism"], document["results"]
    results = explained_records(results, cases)
    document["results"] = results
    document["determinism"]["executions"] = results
    document = enrich_graph_artifacts(document, batch)
    results = document["results"]
    save(output / "data/results.json", document)
    fields = ("scenario_id", "tool", "threads", "repeat", "run_id", "status", "reads_sha256", "truth_sha256",
              "assembly_sha256", "normalised_assembly_sha256", "biological_sha256", "elapsed_seconds", "peak_memory_kb")
    with (output / "data/results.tsv").open("w", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(fields)
        writer.writerows([[row.get(field) for field in fields] for row in results])
    write_result_pages(document, output, batch)
    scored = sum(row["status"] in ("pass", "fail") for row in results)
    counts = collections.Counter(row["status"] for row in results)
    panel = config["determinism"]
    intro = '<div class="page-heading"><h1>Does the assembler repeat its result?</h1><p>S3 runs the same frozen input repeatedly at each thread setting. File identity, normalised sequence identity and biological outcomes answer separate questions.</p></div>'
    body = intro + f'<p class="run-summary">{scored} of {len(results)} executions assessed · {len(cases)} frozen read sets · {panel["repeats"]} repeats per thread setting</p>'
    body += f'<p class="run-summary">{e(batch_progress(results, "executions"))}</p>' + interpretation_guide()
    body += '<div class="notice"><strong>Repeatable can still be wrong.</strong> Pass/fail describes exact dedicated-plasmid recovery. Identical/different describes agreement between executions. Incomplete groups and unequal or unverified inputs receive no repeatability conclusion.</div>'
    body += '<p>' + ' · '.join(f'{count} {e(status.replace("_", " "))}' for status, count in sorted(counts.items())) + '</p>'
    body += summary_table(summary["within_thread"], cases)
    body += summary_table(summary["across_threads"], cases, across=True)
    body += f'<p class="muted">{e(summary["limitations"])}</p><div class="downloads"><a href="data/results.json">Download JSON</a><a href="data/results.tsv">Download TSV</a><span>Updated {e(document["generated_at"])} · Batch {e(document["batch"] or "not submitted")}</span></div>'
    (output / "index.html").write_text(page("Repeatability results", body))
    scenarios = '<h1>S3 · Repeated runs and threads</h1><p class="intro">Each scenario shares one fixed read file across all tools, repeats and thread settings. Open a case for individual execution outcomes and input hashes.</p><ul class="scenario-list">'
    for case in cases:
        scenarios += f'<li><a href="{e(case["id"])}.html">{e(case["title"])}</a><span>{e(case["organism"])}</span></li>'
        content = repeat_scenario(case, document, output)
        (output / "scenarios" / (case["id"] + ".html")).write_text(page(case["title"] + " · repeats", content, "../", "scenarios"))
    (output / "scenarios/index.html").write_text(page("Repeated-run scenarios", scenarios + '</ul>', "../", "scenarios"))
    methods = (ROOT / "website/methods.html").read_text()
    methods += '<h2>Reading S3 repeatability</h2><p>File bytes preserve headers and output ordering. Normalised sequences ignore names, order and strand; rotation is ignored only for exact matches to known circular truth molecules. Other contig ends are preserved and duplicates remain present. Biological signatures compare the strict endpoint and molecule counts. Input hashes must agree before a repeatability conclusion is shown.</p>'
    (output / "methods.html").write_text(page("Methods", methods, active="methods"))
    (output / "about.html").write_text(page("About", '<h1>About this repeatability panel</h1><p>Ploptimizer compares plasmid assembly outcomes using frozen simulated reads and recorded execution evidence. These S3 results assess observed repeatability, with BMRC Slurm execution and Pixi environments.</p><p><a href="methods.html">Methods and limitations</a> · <a href="history.html">All batches</a></p>', active="about"))
    write_history(output, document, include_history)
    save(output / "vercel.json", {"cleanUrls": True})
    (output / ".vercelignore").write_text(".env*\n.vercel\n.gitignore\n")
    if batch:
        shutil.rmtree(batch / "site", ignore_errors=True)
        shutil.copytree(output, batch / "site", dirs_exist_ok=True, ignore=shutil.ignore_patterns(".vercel", ".env*", ".gitignore"))
    return output


def repeat_scenario(case, document, output):
    summary, config = document["determinism"], document["config"]
    rows = [row for row in document["results"] if row["scenario_id"] == case["id"]]
    body = f'<a class="back" href="index.html">All repeated-run scenarios</a><h1>{e(case["title"])}</h1><p class="intro">S3 · Fixed-input repeats and thread sensitivity</p><p>Batch <code>{e(document["batch"] or "not submitted")}</code> · {e(case["organism"])}</p>'
    body += f'<p>Source assembly: <a href="https://www.ncbi.nlm.nih.gov/datasets/genome/{case["assembly_accession"]}/">{e(case["assembly_accession"])}</a>. The same error-free input is reused for {config["determinism"]["repeats"]} executions at each of {e(config["determinism"]["threads"])} threads. Input sampling is not repeated.</p>'
    manifest = document.get("inputs", {}).get(case["id"])
    body += '<h2>Frozen input evidence</h2>'
    if manifest:
        body += f'<p>Input validation: {e(manifest["status"])}. Read-file SHA-256:</p><code class="checksum">{e(manifest["reads_sha256"])}</code><p>Truth-file SHA-256:</p><code class="checksum">{e(manifest["truth_sha256"])}</code>'
        body += '<div class="table-scroll" role="region" aria-label="Input molecules" tabindex="0"><table><thead><tr><th scope="col">Accession</th><th scope="col">Achieved depth</th><th scope="col">Breadth</th><th scope="col">Read count</th><th scope="col">Mean / range of read lengths</th></tr></thead><tbody>'
        for row in manifest.get("replicons", []):
            body += f'<tr><th scope="row">{e(row["accession"])}</th><td>{row["achieved_depth"]:.2f}×</td><td>{row["breadth"]:.2%}</td><td>{row["read_count"]:,}</td><td>{row["mean_read_length"]:,.0f} / {row["minimum_read_length"]:,}–{row["maximum_read_length"]:,} bp</td></tr>'
        body += '</tbody></table></div>'
    else:
        body += '<p>No frozen input has been collected yet. No repeatability conclusion is available.</p>'
    body += summary_table([row for row in summary["within_thread"] if row["scenario_id"] == case["id"]], [case], prefix="")
    body += summary_table([row for row in summary["across_threads"] if row["scenario_id"] == case["id"]], [case], across=True, prefix="")
    for tool in config["tools"]:
        selected = [row for row in rows if row["tool"] == tool]
        body += f'<section class="assembler-result" id="{e(tool)}"><h2>{e(LABELS[tool])} · individual executions</h2><p>Pass/fail below describes biological correctness; an identical signature can occur for either outcome.</p><div class="table-scroll" role="region" aria-label="{e(LABELS[tool])} repeated executions" tabindex="0"><table><thead><tr><th scope="col">Threads / repeat</th><th scope="col">Sequence assessment</th><th scope="col">Elapsed</th><th scope="col">Evidence</th></tr></thead><tbody>'
        for row in selected:
            name = f'{case["id"]}-{tool}-{row["run_id"]}.json'
            save(output / "data" / name, execution_evidence(row, case))
            elapsed = f'{row["elapsed_seconds"]:.1f} s' if row.get("elapsed_seconds") is not None else "Not available"
            explanation = finding_panel(row, case, compact=True) if row["status"] not in ("pass", "pending", "running", "not_run") else ""
            body += f'<tr><th scope="row">{row["threads"]} / {row["repeat"]}</th><td>{badge(row["status"])} · exact endpoint</td><td>{elapsed}</td><td><a href="{e(result_href(row, "../"))}">Result details and graph</a> · <a href="../data/{e(name)}">Execution JSON</a>{explanation}</td></tr>'
            if row.get("error"):
                body += f'<tr><td colspan="4">{e(row["error"])}</td></tr>'
        body += '</tbody></table></div></section>'
    return body + '<p><a href="../methods.html">Methods and normalisation limits</a></p>'
