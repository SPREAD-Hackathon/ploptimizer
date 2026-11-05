"""Presentation-only aggregation of frozen exact execution statuses."""
import copy
import html
import re
from pathlib import Path
from .common import ROOT, load, save
from .result_pages import result_href

FAMILIES = {
    "S1": ("Error-free recovery", "Baseline recovery with error-free simulated reads."),
    "S2": ("Relative plasmid coverage", "Recovery across plasmid-to-chromosome coverage ratios."),
    "S3": ("Repeated runs", "Recovery on repeated frozen inputs and different thread settings; repeatability is assessed separately."),
    "S4": ("Small plasmids and read length", "Small-plasmid recovery across read-length targets."),
    "S6": ("Simulated read errors", "Matched controls and simulated error profiles."),
}
TOOLS = {"flye": "Flye", "flye-meta": "Flye · uneven coverage", "raven": "Raven", "plassembler": "Plassembler long"}
ERRORS = {"error", "timeout", "invalid_input"}


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Overview links require simple batch identifiers")
    return value


def _counts(rows):
    counts = {"pass": 0, "fail": 0, "errors": 0, "unscored": 0, "total": 0, "denominator": 0}
    for row in rows:
        status = row["status"]
        key = status if status in {"pass", "fail"} else "errors" if status in ERRORS else "unscored"
        counts[key] += 1
        counts["total"] += 1
    counts["denominator"] = counts["pass"] + counts["fail"]
    counts["pass_fraction"] = counts["pass"] / counts["denominator"] if counts["denominator"] else None
    return counts


def build_overview(documents, *, cohort=None, archived_batch=None, root_batch=None):
    """Derive a display model, without editing reports or scores.

    Supply one document per batch; duplicate batches/executions are rejected.
    Archive mode admits only archived_batch, regardless of the primary cohort.
    """
    cohort = copy.deepcopy(cohort if cohort is not None else load(ROOT / "config/overview.json"))
    if cohort.get("schema_version") != 1:
        raise ValueError("Unsupported overview cohort configuration")
    tools = cohort.get("tools", list(TOOLS))
    families = cohort.get("families", list(FAMILIES))
    if len(set(tools)) != len(tools) or any(t not in TOOLS for t in tools) or len(set(families)) != len(families) or any(f not in FAMILIES for f in families):
        raise ValueError("Overview tools/families must be unique supported identifiers")
    configured = cohort.get("primary_batches", [])
    if len(set(configured)) != len(configured):
        raise ValueError("Primary cohort batch identifiers must be unique")
    selected = [_identifier(archived_batch)] if archived_batch is not None else [_identifier(b) for b in configured]
    root_batch = root_batch or cohort.get("root_batch")
    if root_batch is not None:
        root_batch = _identifier(root_batch)
    by_batch = {}
    for document in documents:
        batch = _identifier(document["batch"])
        if batch in by_batch:
            raise ValueError("Duplicate batch report; refusing to pool duplicate results")
        by_batch[batch] = document
    rows, seen = [], set()
    for batch in selected:
        document = by_batch.get(batch)
        if document is None:
            continue
        cases = {case["id"]: case for case in document["scenarios"]}
        for record in document["results"]:
            case = cases.get(record["scenario_id"])
            if case is None:
                raise ValueError("Result references an unknown scenario")
            family = "S3" if document.get("config", {}).get("determinism") else case.get("category")
            if family not in families or record["tool"] not in tools:
                raise ValueError("Unconfigured family/tool in selected report")
            identity = (batch, record["scenario_id"], record["tool"], record.get("run_id"))
            if identity in seen:
                raise ValueError("Duplicate execution identity; refusing duplicate headline counts")
            seen.add(identity)
            link = result_href(record, "" if archived_batch is not None or batch == root_batch else f"batches/{batch}/")
            rows.append({"batch": batch, "family": family, "scenario_id": record["scenario_id"],
                         "title": case.get("title", case["id"]), "organism": case.get("organism", "Not recorded"),
                         "assembly_accession": case.get("assembly_accession"), "tool": record["tool"],
                         "version": record.get("version") or "Version not recorded", "threads": record.get("threads"),
                         "run_id": record.get("run_id"), "status": record.get("status", "not_run"), "href": link})
    rows.sort(key=lambda r: (families.index(r["family"]), r["organism"], r["assembly_accession"] or "", r["scenario_id"], tools.index(r["tool"]), r["batch"], r["run_id"] or ""))
    family_models = []
    for family in families:
        selected_rows = [r for r in rows if r["family"] == family]
        genomes = sorted({(r["organism"], r["assembly_accession"] or "") for r in selected_rows})
        family_models.append({"id": family, "title": FAMILIES[family][0], "description": FAMILIES[family][1],
                              "href": f"scenarios/{family.lower()}.html", "counts": _counts(selected_rows),
                              "tools": [{"id": tool, "label": TOOLS[tool], **_counts([r for r in selected_rows if r["tool"] == tool])} for tool in tools],
                              "genomes": [{"organism": organism, "assembly_accession": accession or None,
                                           "tools": [{"id": tool, "label": TOOLS[tool], **_counts([r for r in selected_rows if r["organism"] == organism and (r["assembly_accession"] or "") == accession and r["tool"] == tool])} for tool in tools]} for organism, accession in genomes],
                              "records": selected_rows})
    return {"schema_version": 1, "scope": "archived_batch" if archived_batch is not None else "primary_cohort",
            "selected_batches": selected, "included_batches": [b for b in selected if b in by_batch],
            "missing_batches": [b for b in selected if b not in by_batch], "excluded_batches": sorted(set(by_batch) - set(selected)),
            "root_batch": root_batch, "tools": [{"id": t, "label": TOOLS[t]} for t in tools], "families": family_models,
            "counts": _counts(rows), "endpoint": "recorded_exact_status", "denominator": "pass + fail"}


def _e(value):
    return html.escape(str(value), quote=True)


def _cell(counts, href=None):
    tone = "neutral" if counts["denominator"] == 0 else "pass" if counts["fail"] == 0 else "fail" if counts["pass"] == 0 else "mixed"
    text = f'<strong>{counts["pass"]} pass · {counts["fail"]} fail</strong>'
    if href:
        text = f'<a href="{_e(href)}">{text}</a>'
    extra = ([f'{counts["errors"]} errors'] if counts["errors"] else []) + ([f'{counts["unscored"]} unscored'] if counts["unscored"] else [])
    if extra:
        text += '<small>' + ' · '.join(extra) + '</small>'
    heat = "" if counts["pass_fraction"] is None else f' heat-{min(4, int(counts["pass_fraction"] * 5))}'
    return f'<td class="overview-cell {tone}{heat}" data-pass="{counts["pass"]}" data-fail="{counts["fail"]}" data-denominator="{counts["denominator"]}">{text}</td>'


def render_home(model, prefix=""):
    """Body fragment; caller retains its existing page shell and assets."""
    body = f'<h1>Assembly benchmark</h1><p class="overview-intro">Exact recovery · {model["counts"]["total"]} run records · {len(model["tools"])} assembler configurations</p>'
    if model["missing_batches"]:
        body += '<p class="notice">Some selected batches are unavailable. Counts are incomplete.</p>'
    body += '<div class="table-scroll" role="region" aria-label="Scenario family outcomes" tabindex="0"><table class="overview-heatmap"><caption>Exact pass/fail counts by scenario family and assembler</caption><thead><tr><th scope="col">Scenario family</th>'
    body += ''.join(f'<th scope="col">{_e(t["label"])}</th>' for t in model["tools"]) + '</tr></thead><tbody>'
    for family in model["families"]:
        if model["scope"] == "archived_batch" and not family["counts"]["total"]:
            continue
        href = prefix + family["href"]
        body += f'<tr><th scope="row"><a href="{_e(href)}">{family["id"]} · {_e(family["title"])}</a></th>'
        body += ''.join(_cell(tool, href) for tool in family["tools"]) + '</tr>'
    return body + '</tbody></table></div><p class="overview-legend"><span>Orange: more failures</span><span>Blue: more passes</span></p>'


def render_family(model, family, prefix="../"):
    """Concise family summary and run links, without explanations or graphs."""
    item = next((f for f in model["families"] if f["id"] == family), None)
    if item is None:
        raise ValueError("Unknown scenario family")
    body = f'<p><a href="{_e(prefix)}index.html">All scenario families</a></p><h1>{family} · {_e(item["title"])}</h1><p>{_e(item["description"])}</p>'
    if family in {"S3", "S6"}:
        metric = "Repeatability" if family == "S3" else "Tolerant recovery"
        body += f'<p>{metric} is a separate endpoint. The tables below show exact status only; individual result links retain the detailed evidence.</p>'
    body += '<div class="table-scroll"><table><caption>Exact outcomes for each reference genome</caption><thead><tr><th scope="col">Genome</th>'
    body += ''.join(f'<th scope="col">{_e(t["label"])}</th>' for t in model["tools"]) + '</tr></thead><tbody>'
    for genome in item["genomes"]:
        body += f'<tr><th scope="row">{_e(genome["organism"])}<small>{_e(genome["assembly_accession"] or "Accession not recorded")}</small></th>'
        body += ''.join(_cell(t) for t in genome["tools"]) + '</tr>'
    body += '</tbody></table></div><h2>Individual runs</h2><div class="table-scroll"><table><thead><tr><th scope="col">Genome / case</th><th scope="col">Assembler / version</th><th scope="col">Threads / repeat</th><th scope="col">Exact status</th></tr></thead><tbody>'
    for row in item["records"]:
        run = f'{row["threads"] if row["threads"] is not None else "Not recorded"} threads · {row["run_id"] or "Single run"}'
        body += f'<tr data-batch="{_e(row["batch"])}"><th scope="row">{_e(row["organism"])}<small>{_e(row["title"])}</small></th><td><a href="{_e(prefix + row["href"])}">{_e(TOOLS[row["tool"]])}<small>{_e(row["version"])}</small></a></td><td>{_e(run)}</td><td><span class="status {_e(row["status"])}">{_e(row["status"].replace("_", " ").title())}</span></td></tr>'
    if not item["records"]:
        body += '<tr><td colspan="4">No runs in this selected cohort.</td></tr>'
    return body + '</tbody></table></div>'


def write_overview(documents, output, *, cohort=None, archived_batch=None, root_batch=None):
    """Write navigation views and separate derived JSON; preserve scientific files."""
    from .report import page
    output = Path(output)
    (output / "scenarios").mkdir(parents=True, exist_ok=True)
    (output / "data").mkdir(parents=True, exist_ok=True)
    model = build_overview(documents, cohort=cohort, archived_batch=archived_batch, root_batch=root_batch)
    (output / "index.html").write_text(page("Results", render_home(model)))
    for family in model["families"]:
        (output / family["href"]).write_text(page(family["title"], render_family(model, family["id"]), prefix="../", active="scenarios"))
    save(output / "data/overview.json", model)
    return model
