"""Expand the pinned inventory into finite baseline and relative-depth scenarios."""

import copy

from .common import ROOT, fingerprint, load

LABELS = {
    "GCF_000005845.2": "MG1655",
    "GCF_000258145.1": "W",
    "GCF_000010385.1": "SE11",
    "GCF_024397815.1": "Ecl8",
    "GCF_000016305.1": "MGH78578",
}


def plan(config):
    inventory = load(ROOT / "references/panel.json")["assemblies"]
    selected = config["references"]
    known = {entry["assembly"]["assembly_accession"] for entry in inventory}
    if set(selected) - known:
        raise ValueError("Unknown reference accession in configuration")
    result = []
    for entry in inventory:
        assembly = entry["assembly"]
        accession = assembly["assembly_accession"]
        if accession not in selected:
            continue
        if assembly["selection_status"] != "preferred_candidate":
            raise ValueError(f"Reference is held, not a preferred candidate: {accession}")
        replicons = entry["replicons"]
        chromosome = [r for r in replicons if r["molecule_type"] == "chromosome"]
        plasmids = [r for r in replicons if r["molecule_type"] == "plasmid"]
        if len(chromosome) != 1:
            raise ValueError("Pilot requires one chromosome")
        subsets = [("chromosome", [], "Chromosome only")]
        subsets += [(r["replicon_name"].lower(), [r], "Chromosome + " + r["replicon_name"]) for r in plasmids]
        if len(plasmids) > 1:
            subsets.append(("native", plasmids, "Chromosome + all native plasmids"))
        for suffix, subset, title in subsets:
            case = {
                "id": f"s1-{LABELS[accession].lower()}-{suffix}",
                "title": f"{LABELS[accession]} · {title}",
                "category": "S1",
                "assembly_accession": accession,
                "organism": assembly["organism"],
                "truth_type": "native_complement" if len(subset) == len(plasmids) else "derived_subset",
                "replicons": chromosome + subset,
                "simulation": config["simulation"],
                "profile_id": config["profile_id"],
            }
            case["fingerprint"] = fingerprint(case)
            result.append(case)
    for target in config.get("coverage_panel", {}).get("targets", []):
        source = next((case for case in result if case["category"] == "S1" and case["assembly_accession"] == target["assembly"]
                       and [r["refseq_accession"] for r in case["replicons"] if r["molecule_type"] == "plasmid"] == [target["plasmid"]]), None)
        if source is None:
            raise ValueError("Coverage targets must identify one native plasmid in a selected reference")
        for ratio in config["coverage_panel"]["ratios"]:
            if ratio <= 0:
                raise ValueError("Coverage ratios must be positive")
            case = copy.deepcopy(source)
            label = format(ratio, "g")
            case["id"] = source["id"].replace("s1-", "s2-", 1) + "-depth-" + label.replace(".", "p")
            case["title"] = source["title"] + f" · {label}× relative depth"
            case["category"] = "S2"
            case["simulation"]["plasmid_relative_depth"] = ratio
            case["fingerprint"] = fingerprint({key: value for key, value in case.items() if key != "fingerprint"})
            result.append(case)
    if len({case["id"] for case in result}) != len(result):
        raise ValueError("The configuration produces duplicate scenario identifiers")
    return result


def find_case(config, case_id):
    return next((c for c in plan(config) if c["id"] == case_id), None) or _missing(case_id)


def _missing(case_id):
    raise ValueError(f"Unknown scenario: {case_id}")
