"""Display associations from existing exact-contig results and recorded GFA paths.

No sequence alignment, new scoring or within-segment coordinate inference.
"""

import csv
import hashlib
from functools import lru_cache

from .common import ROOT

CHROMOSOME = ("#72a9e8", "#326eae")
PLASMIDS = [("#d8974e", "#9c5a15"), ("#58bcae", "#1c7d70"),
            ("#b89ce4", "#7551a6"), ("#e38bb1", "#a34670"),
            ("#c9b755", "#7f6e11"), ("#78bbdf", "#276e97"),
            ("#97b06e", "#57772d")]


@lru_cache(maxsize=1)
def _catalogue_colours():
    colours, ranks = {}, {}
    with (ROOT / "references/replicons.tsv").open() as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            assembly = row["assembly_accession"]
            if row["molecule_type"] == "chromosome":
                colours[row["refseq_accession"]] = CHROMOSOME
            else:
                rank = ranks.get(assembly, 0)
                colours[row["refseq_accession"]] = PLASMIDS[rank % len(PLASMIDS)]
                ranks[assembly] = rank + 1
    return colours


def reference_colour(molecule):
    accession = molecule.get("refseq_accession") or molecule.get("accession")
    if accession in _catalogue_colours():
        return _catalogue_colours()[accession]
    if molecule.get("molecule_type") == "chromosome":
        return CHROMOSOME
    key = accession or molecule.get("replicon_name") or molecule.get("name") or "unknown"
    rank = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % len(PLASMIDS)
    return PLASMIDS[rank]


def build_reference_origins(case, record, artifact):
    molecules = [m for m in case.get("replicons", []) if record.get("tool") != "plassembler" or m.get("molecule_type") == "plasmid"]
    references = []
    for molecule in molecules:
        colour, light = reference_colour(molecule)
        references.append({"id": molecule.get("refseq_accession"), "name": molecule.get("replicon_name", "Reference molecule"), "length_bp": molecule.get("length_bp"), "colour": colour, "light_colour": light})
    graph = artifact.get("graph") or {}
    result = {"schema_version": 1, "method": "saved_exact_contig_gfa_path_v1", "references": references, "nodes": {},
              "scope": "Whole-segment association through a saved exact contig and its recorded GFA path; not a new segment alignment or within-node coordinate map.",
              "unassigned_reason": "No saved exact-contig-to-GFA-path association is available for this segment.",
              "source_hashes": {"assembly_sha256": record.get("assembly_sha256"), "gfa_sha256": graph.get("source", {}).get("file_sha256")}}
    attached_hash = artifact.get("input_hashes", {}).get("assembly_sha256")
    if not record.get("assembly_sha256") or attached_hash != record["assembly_sha256"] or artifact.get("failed_execution_provenance") or graph.get("source", {}).get("role") != "final" or graph.get("status") != "available" or graph.get("complete") is not True:
        result["unassigned_reason"] = "A complete final graph bound to the scored assembly is required; no final-reference colours are assigned here."
        return result
    node_ids = {n["id"] for n in graph.get("nodes", [])}
    paths, repeated_paths = {}, set()
    for path in graph.get("paths", []):
        if path["id"] in paths:
            repeated_paths.add(path["id"])
        paths[path["id"]] = path
    allowed_refs = {r["id"] for r in references}
    candidates = {}
    for index, molecule in enumerate((record.get("evaluation") or {}).get("replicons", [])):
        accession = molecule.get("accession")
        if accession not in allowed_refs:
            continue
        for contig in molecule.get("exact_contigs", []):
            path = paths.get(contig)
            if not path or contig in repeated_paths or not path.get("steps") or any(s.get("segment") not in node_ids or s.get("orientation") not in {"+", "-"} for s in path["steps"]):
                continue
            for step in path["steps"]:
                evidence = {"reference_id": accession, "contig_id": contig, "path_id": path["id"], "orientation": step["orientation"],
                            "exact_source": f"evaluation.replicons[{index}].exact_contigs", "path_source": "graph_artifacts.graph.paths"}
                entries = candidates.setdefault(step["segment"], [])
                if evidence not in entries:
                    entries.append(evidence)
    for node, evidence in candidates.items():
        ids = sorted({entry["reference_id"] for entry in evidence})
        result["nodes"][node] = {"status": "supported" if len(ids) == 1 else "ambiguous", "reference_id": ids[0] if len(ids) == 1 else None, "candidate_reference_ids": ids, "evidence": evidence}
    return result
