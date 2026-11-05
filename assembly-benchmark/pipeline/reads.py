"""Fetch pinned records and sample exact reads with a declared length model."""

import gzip
import hashlib
import io
import math
import random
import time
import urllib.parse
import urllib.request

from .cases import plan
from .common import ROOT, digest, fasta, load, reverse_complement, save, write_fasta


def prepare(config):
    directory = ROOT / "data/references"
    directory.mkdir(parents=True, exist_ok=True)
    replicons = {r["refseq_accession"]: r for c in plan(config) for r in c["replicons"]}
    audits = []
    for accession, replicon in replicons.items():
        path = directory / (accession + ".fasta")
        if not path.exists():
            query = urllib.parse.urlencode({"db": "nuccore", "id": accession, "rettype": "fasta", "retmode": "text"})
            url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + query
            with urllib.request.urlopen(url, timeout=120) as response:
                content = response.read()
            temp = path.with_suffix(".download")
            temp.write_bytes(content)
            records = fasta(temp)
            if list(records) != [accession]:
                temp.unlink()
                raise ValueError(f"NCBI did not return the exact requested accession: {accession}")
            temp.replace(path)
            time.sleep(0.4)
        records = fasta(path)
        if list(records) != [accession]:
            raise ValueError(f"Unexpected cached accession: {accession}")
        sequence = records[accession]
        if len(sequence) != replicon["length_bp"] or set(sequence) - set("ACGT"):
            raise ValueError(f"Reference failed length/unambiguous-base audit: {accession}")
        if replicon.get("sequence_sha256") and hashlib.sha256(sequence.encode()).hexdigest() != replicon["sequence_sha256"]:
            raise ValueError(f"Reference differs from admitted sequence: {accession}")
        if replicon.get("admission_scope") == "isolated_linear_reference_record":
            from .linear_cases import validate_terminal_reference
            validate_terminal_reference(replicon, sequence)
        audits.append({**replicon, "file_sha256": digest(path), "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest()})
    save(directory / "audit.json", {"status": "sequence_inventory_checked", "replicons": audits,
         "limitation": "This checks accession, length and alphabet, not independent biological validation."})
    return audits


def covered_bases(intervals):
    end = total = 0
    for start, stop in sorted(intervals):
        if stop > end:
            total += stop - max(start, end)
            end = stop
    return total


def exact_reads(case, sequences, directory):
    """Random starts/strands; lognormal lengths clipped to one molecule traversal."""
    directory.mkdir(parents=True, exist_ok=True)
    settings = case["simulation"]
    if settings.get("model") not in {"exact-lognormal-v1", "exact-linear-anchored-v1"}:
        raise ValueError("Only supported exact simulation models can run; unknown models cannot fall back to exact reads")
    for key in ("chromosome_depth", "length_mean", "length_min", "length_max"):
        if settings[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if settings["length_sd"] < 0 or settings["length_min"] > settings["length_max"]:
        raise ValueError("Invalid length distribution")
    if settings["circular_read_limit"] != "one_circumference":
        raise ValueError("Only the declared one-circumference model is implemented")
    if not 0 <= settings["fastq_phred"] <= 93:
        raise ValueError("Invalid FASTQ Phred score")
    anchored = settings["model"] == "exact-linear-anchored-v1"
    if anchored and (any(r.get("topology") != "linear" for r in case["replicons"]) or settings.get("linear_terminal_reads_per_end") != 2 or type(settings.get("linear_terminal_read_length")) is not int or settings["linear_terminal_read_length"] <= 0):
        raise ValueError("Anchored linear reads require linear references and two declared reads at each end")
    sigma = math.sqrt(math.log1p((settings["length_sd"] / settings["length_mean"]) ** 2))
    mu = math.log(settings["length_mean"]) - sigma * sigma / 2
    fastq_path = directory / "reads.fastq.gz"
    origin_path = directory / "read_origins.tsv.gz"
    stats = []
    with fastq_path.open("wb") as raw, origin_path.open("wb") as origin_raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped, gzip.GzipFile(filename="", fileobj=origin_raw, mode="wb", mtime=0) as origin_zipped:
            with io.TextIOWrapper(zipped) as fastq_out, io.TextIOWrapper(origin_zipped) as origins:
                origins.write("read_id\treplicon\tstart_0based\tlength\tstrand\n")
                for replicon in case["replicons"]:
                    accession = replicon["refseq_accession"]
                    sequence = sequences[accession]
                    length = len(sequence)
                    if not length or set(sequence) - set("ACGT"):
                        raise ValueError("Exact sampling needs nonempty ACGT references")
                    circular = replicon["topology"] == "circular"
                    sampling_sequence = sequence + sequence if circular else sequence
                    multiplier = settings["plasmid_relative_depth"] if replicon["molecule_type"] == "plasmid" else 1
                    target = length * settings["chromosome_depth"] * multiplier
                    if target <= 0:
                        raise ValueError("Retained replicons require positive coverage")
                    # Per-replicon streams preserve chromosome reads across subsets.
                    rng = random.Random(f"{settings['seed']}:{accession}")
                    bases = count = 0
                    left_end = right_end = 0
                    anchor_length = min(length, settings.get("linear_terminal_read_length", length))
                    anchors = [(0, "+"), (0, "-"), (length-anchor_length, "+"), (length-anchor_length, "-")] if anchored else []
                    intervals = []
                    read_lengths = []
                    while bases < target or count < len(anchors):
                        if count < len(anchors):
                            start, strand = anchors[count]
                            read_length = anchor_length
                        else:
                            read_length = min(length, settings["length_max"], max(settings["length_min"], round(rng.lognormvariate(mu, sigma))))
                            start = rng.randrange(length if circular else length - read_length + 1)
                            strand = "-" if rng.getrandbits(1) else "+"
                        read = sampling_sequence[start:start + read_length]
                        if not circular:
                            left_end += int(start == 0)
                            right_end += int(start + read_length == length)
                        if strand == "-":
                            read = reverse_complement(read)
                        count += 1
                        read_id = f"{accession}_{count:08d}"
                        fastq_out.write(f"@{read_id}\n{read}\n+\n{chr(settings['fastq_phred'] + 33) * read_length}\n")
                        origins.write(f"{read_id}\t{accession}\t{start}\t{read_length}\t{strand}\n")
                        stop = start + read_length
                        intervals.append((start, min(stop, length)))
                        if stop > length:
                            intervals.append((0, stop - length))
                        bases += read_length
                        read_lengths.append(read_length)
                    breadth = covered_bases(intervals) / length
                    stats.append({"accession": accession, "target_depth": target / length,
                                  "achieved_depth": bases / length, "breadth": breadth,
                                  "read_count": count, "sequenced_bases": bases,
                                  "mean_read_length": bases / count, "minimum_read_length": min(read_lengths),
                                  "maximum_read_length": max(read_lengths),
                                  **({"left_terminal_read_count":left_end,"right_terminal_read_count":right_end,"terminal_anchor_length_bp":anchor_length} if anchored else {})})
    write_fasta(directory / "truth.fasta", sequences)
    valid = all(r["breadth"] >= settings["minimum_breadth"] for r in stats)
    if anchored:
        valid = valid and all(r["left_terminal_read_count"] >= 2 and r["right_terminal_read_count"] >= 2 for r in stats)
    manifest = {"case": case, "model": settings["model"], "status": "valid" if valid else "invalid_input",
                "limitation": "Error-free sequence sampling, not a chemistry/basecaller error model. Q40 is a synthetic placeholder.",
                "replicons": stats, "reads_sha256": digest(fastq_path), "origins_sha256": digest(origin_path),
                "truth_sha256": digest(directory / "truth.fasta"), "length_policy": "Stop after reaching depth; overshoot is at most one read per replicon."}
    if anchored:
        manifest["limitation"] += " Includes two declared synthetic reads anchored at each linear end; not an empirical terminal-capture model."
    save(directory / "input.json", manifest)
    return manifest


def simulate(case, batch):
    directory = batch / "cases" / case["id"]
    if (directory / "input.json").exists():
        previous = load(directory / "input.json")
        if previous["case"]["fingerprint"] != case["fingerprint"]:
            raise ValueError("Scenario changed; use a new batch")
        for filename, key in [("reads.fastq.gz", "reads_sha256"), ("truth.fasta", "truth_sha256"), ("read_origins.tsv.gz", "origins_sha256")]:
            if digest(directory / filename) != previous[key]:
                raise ValueError("Cached input checksum changed; use a new batch")
        if case["simulation"]["model"] == "matched-error-v1":
            from .noisy_workflow import source_case
            clean_manifest = load(directory / "clean/input.json")
            if clean_manifest.get("case") != source_case(case) or clean_manifest.get("status") != "valid" or clean_manifest.get("model") != "exact-lognormal-v1":
                raise ValueError("Cached clean source manifest provenance changed; use a new batch")
            for filename,key in (("reads.fastq.gz","source_fragments_sha256"),("read_origins.tsv.gz","source_origins_sha256"),("truth.fasta","source_truth_sha256")):
                clean_key = {"source_fragments_sha256":"reads_sha256", "source_origins_sha256":"origins_sha256", "source_truth_sha256":"truth_sha256"}[key]
                if not previous.get(key) or clean_manifest.get(clean_key) != previous[key] or digest(directory / "clean" / filename) != previous[key]:
                    raise ValueError("Cached clean source fragments changed; use a new batch")
        return previous
    sequences = {}
    audit = {r["refseq_accession"]: r for r in load(ROOT / "data/references/audit.json")["replicons"]}
    for replicon in case["replicons"]:
        accession = replicon["refseq_accession"]
        path = ROOT / "data/references" / (accession + ".fasta")
        if accession not in audit or digest(path) != audit[accession]["file_sha256"]:
            raise ValueError("Reference changed since preparation; repeat the source audit")
        sequences.update(fasta(path))
    if case["simulation"]["model"] == "matched-error-v1":
        from .noisy_workflow import simulate_noise
        return simulate_noise(case, sequences, batch, directory)
    return exact_reads(case, sequences, directory)
