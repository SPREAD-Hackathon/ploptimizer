"""Website templates for backend overview models."""
import html
from pathlib import Path
from .common import save
from .overview_model import FAMILIES, TOOLS, ERRORS, build_overview


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


def write_overview(documents, output, *, cohort=None, archived_batch=None, root_batch=None, model=None):
    """Write navigation views and separate derived JSON; preserve scientific files."""
    from .report import page
    output = Path(output)
    (output / "scenarios").mkdir(parents=True, exist_ok=True)
    (output / "data").mkdir(parents=True, exist_ok=True)
    if model is None:
        model = build_overview(documents, cohort=cohort, archived_batch=archived_batch, root_batch=root_batch)
    (output / "index.html").write_text(page("Results", render_home(model)))
    for family in model["families"]:
        (output / family["href"]).write_text(page(family["title"], render_family(model, family["id"]), prefix="../", active="scenarios"))
    save(output / "data/overview.json", model)
    return model
