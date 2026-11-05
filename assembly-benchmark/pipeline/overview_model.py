"""Backend aggregation of frozen execution statuses; no rescoring."""
import copy
import re
from .common import ROOT, load
from .identities import result_href

FAMILIES = {
    "S1": ("Error-free recovery", "Baseline recovery with error-free simulated reads. Flye (default) is the primary Flye configuration; Flye (--meta) is a parameter comparison."),
    "S2": ("Relative plasmid coverage", "Recovery across plasmid-to-chromosome coverage ratios."),
    "S3": ("Repeated runs", "Agreement between repeated executions on the same frozen input, grouped by mode and thread setting."),
    "S4": ("Small plasmids and read length", "Small-plasmid recovery across read-length targets."),
    "S6": ("Simulated read errors", "Matched controls and simulated error profiles."),
}
TOOLS = {"flye": "Flye (default)", "flye-meta": "Flye (--meta)", "raven": "Raven", "plassembler": "Plassembler long"}
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



def _repeatability_counts(groups):
    counts = {"identical": 0, "different": 0, "not_assessed": 0, "total": len(groups)}
    for group in groups:
        value = group.get("normalised_sequence_identical")
        assessed = group.get("complete") is True and group.get("inputs_identical") is True
        key = "identical" if assessed and value is True else "different" if assessed and value is False else "not_assessed"
        counts[key] += 1
    return counts


def _repeatability_groups(document, cases):
    """Use saved comparisons only; never infer repeatability from exact scores."""
    summary = document.get("determinism", {})
    within = summary.get("within_thread", [])
    across = summary.get("across_threads", [])
    if not within:
        # Missing summary still exposes expected execution groups as unassessed.
        keys = {(r["scenario_id"], r["tool"], r.get("mode", "default"), r.get("threads"))
                for r in document["results"]}
        within = [{"scenario_id": c, "tool": t, "mode": m, "threads": n}
                  for c, t, m, n in sorted(keys, key=str)]
    result = []
    for kind, groups in (("within_thread", within), ("across_threads", across)):
        for group in groups:
            case = cases.get(group["scenario_id"])
            if case is None:
                raise ValueError("Repeatability comparison references an unknown scenario")
            result.append({**copy.deepcopy(group), "comparison": kind, "batch": document["batch"],
                           "mode": group.get("mode", "default"), "title": case.get("title", case["id"]),
                           "organism": case.get("organism", "Not recorded"),
                           "assembly_accession": case.get("assembly_accession")})
    return result


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
    rows, seen, repeatability = [], set(), []
    for batch in selected:
        document = by_batch.get(batch)
        if document is None:
            continue
        cases = {case["id"]: case for case in document["scenarios"]}
        if document.get("config", {}).get("determinism"):
            repeatability.extend(_repeatability_groups(document, cases))
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
        if family == "S3":
            item = family_models[-1]
            item["repeatability_groups"] = repeatability
            within = [g for g in repeatability if g["comparison"] == "within_thread"]
            item["repeatability"] = _repeatability_counts(within)
            for tool in item["tools"]:
                tool["repeatability"] = _repeatability_counts([g for g in within if g["tool"] == tool["id"]])
            for genome in item["genomes"]:
                for tool in genome["tools"]:
                    tool["repeatability"] = _repeatability_counts([g for g in within if g["tool"] == tool["id"]
                        and g["organism"] == genome["organism"] and g["assembly_accession"] == genome["assembly_accession"]])
    return {"schema_version": 1, "scope": "archived_batch" if archived_batch is not None else "primary_cohort",
            "selected_batches": selected, "included_batches": [b for b in selected if b in by_batch],
            "missing_batches": [b for b in selected if b not in by_batch], "excluded_batches": sorted(set(by_batch) - set(selected)),
            "root_batch": root_batch, "tools": [{"id": t, "label": TOOLS[t]} for t in tools], "families": family_models,
            "counts": _counts(rows), "endpoint": "recorded_exact_status", "denominator": "pass + fail"}


