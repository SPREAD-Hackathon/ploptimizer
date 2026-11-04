#!/usr/bin/env python3
"""Fixed pilot cause study: Flye overlap threshold and independent Raven polishing."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
import datetime
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.common import digest, fasta, fingerprint, load, reverse_complement, save
from pipeline.scoring import evaluate

PILOT = "20261104T183058"
SCENARIO = "s1-w-prk2"
PLASMID = "NC_017662.1"
EXEC_IN_DIRECTORY = "import os,sys; os.chdir(sys.argv[1]); os.execvp(sys.argv[2],sys.argv[2:])"


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def checked_inputs():
    batch = ROOT / "runs" / PILOT
    folder = batch / "cases" / SCENARIO
    manifest = load(folder / "input.json")
    case = manifest["case"]
    if manifest.get("status") != "valid" or case.get("id") != SCENARIO:
        raise ValueError("The fixed pilot input is not admitted")
    if case["fingerprint"] != fingerprint({key: value for key, value in case.items() if key != "fingerprint"}):
        raise ValueError("Pilot scenario fingerprint changed")
    hashes = {"manifest_sha256": digest(folder / "input.json"), "case_fingerprint": case["fingerprint"],
              "config_sha256": digest(batch / "config.json")}
    for filename, key in (("reads.fastq.gz", "reads_sha256"), ("truth.fasta", "truth_sha256"), ("read_origins.tsv.gz", "origins_sha256")):
        hashes[key] = digest(folder / filename)
        if hashes[key] != manifest.get(key):
            raise ValueError("Pilot input checksum mismatch: " + filename)
    publication = ROOT / "published" / (PILOT + ".json")
    if publication.exists():
        frozen = load(publication)["inputs"][SCENARIO]
        if any(frozen.get(key) != hashes[key] for key in ("reads_sha256", "truth_sha256", "origins_sha256")):
            raise ValueError("Pilot inputs disagree with the versioned publication")
        hashes["publication_sha256"] = digest(publication)
    with gzip.open(folder / "read_origins.tsv.gz", "rt") as stream:
        origins = {row["read_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
    counts = {r["refseq_accession"]: {"read_count": 0, "source_bases": 0, "reads_gt_6000": 0,
              "reads_gt_3000": 0, "minimum_length": None, "maximum_length": None} for r in case["replicons"]}
    lengths, seen = [], set()
    with gzip.open(folder / "reads.fastq.gz", "rt") as stream:
        while True:
            header = stream.readline()
            if not header:
                break
            sequence, plus, quality = (stream.readline().strip() for _ in range(3))
            name = header.strip()[1:]
            if not header.startswith("@") or name not in origins or name in seen or plus != "+" or len(sequence) != len(quality):
                raise ValueError("Pilot FASTQ/origin mismatch")
            origin = origins[name]
            size = len(sequence)
            if size != int(origin["length"]):
                raise ValueError("Pilot source length mismatch")
            row = counts[origin["replicon"]]
            row["read_count"] += 1
            row["source_bases"] += size
            row["reads_gt_6000"] += size > 6000
            row["reads_gt_3000"] += size > 3000
            row["minimum_length"] = min(size, row["minimum_length"]) if row["minimum_length"] is not None else size
            row["maximum_length"] = max(size, row["maximum_length"]) if row["maximum_length"] is not None else size
            lengths.append(size)
            seen.add(name)
    if set(origins) != seen or set(counts) != set(fasta(folder / "truth.fasta")):
        raise ValueError("Pilot read/replicon inventory mismatch")
    total = sum(lengths)
    nx = {}
    for fraction in (0.5, 0.9):
        cumulative = 0
        for length in sorted(lengths, reverse=True):
            cumulative += length
            if cumulative > total * fraction:
                nx[str(fraction)] = length
                break
    return folder, case, {**hashes, "per_replicon_read_lengths": counts, "read_N50": nx["0.5"], "read_N90": nx["0.9"]}


def circular_inspection(assembly, truth):
    """Small candidates only: HW against each doubled orientation, then NW window."""
    import edlib
    reference = fasta(truth)[PLASMID]
    length = len(reference)
    result = []
    for name, query in fasta(assembly).items():
        if not 0.7 * length <= len(query) <= 2 * length:
            continue
        candidates, attempts = [], []
        for strand, sequence in (("+", reference), ("-", reverse_complement(reference))):
            doubled = sequence + sequence
            alignment = edlib.align(query, doubled, mode="HW", task="path", k=1000)
            attempts.append({"strand": strand, "edit_distance": alignment["editDistance"],
                             "location_count": len(alignment.get("locations", []))})
            if alignment["editDistance"] < 0:
                continue
            for start, end in alignment["locations"]:
                if start is not None and 0 <= start <= end < len(doubled):
                    candidates.append((alignment["editDistance"], abs((end - start + 1) - len(query)), strand, start, end, doubled))
        row = {"contig": name, "length_bp": len(query), "query_truth_length_ratio": len(query) / length,
               "hw_attempts": attempts, "status": "no_hit_within_1000_edits"}
        if candidates:
            _, _, strand, start, end, doubled = min(candidates)
            window = doubled[start:end + 1]
            alignment = edlib.align(query, window, mode="NW", task="path", k=1000)
            if alignment["editDistance"] < 0 or not alignment.get("cigar"):
                raise ValueError("A selected HW window did not yield a valid NW alignment")
            parts = re.findall(r"([1-9][0-9]*)([=XID])", alignment["cigar"])
            if "".join(size + op for size, op in parts) != alignment["cigar"]:
                raise ValueError("Invalid extended Edlib CIGAR")
            counts = {op: sum(int(size) for size, code in parts if code == op) for op in "=XID"}
            if counts["="] + counts["X"] + counts["I"] != len(query) or counts["="] + counts["X"] + counts["D"] != len(window):
                raise ValueError("NW CIGAR does not consume the query/window")
            row.update(status="aligned", strand=strand, doubled_reference_start=start,
                       doubled_reference_end_exclusive=end + 1, reference_window_length_bp=len(window),
                       reference_window_span_fraction=len(window) / length, edit_distance=alignment["editDistance"],
                       identity=counts["="] / sum(counts.values()), matches=counts["="], substitutions=counts["X"],
                       insertions=counts["I"], deletions=counts["D"], cigar=alignment["cigar"])
        result.append(row)
    return {"method": "HW to doubled truth in both orientations with k=1000, then NW to best optimal HW window",
            "edlib_version": importlib.metadata.version("edlib"), "candidate_length_ratio": [0.7, 2.0], "candidates": result,
            "limitation": "Diagnostic only, not a new score or topology call. Window span can exceed one circumference; no-hit is limited by k=1000. Chromosome-sized contigs are excluded."}


def gfa_summary(path):
    segments, self_links, links = [], [], 0
    if not path.exists():
        return None
    with path.open() as stream:
        for line in stream:
            fields = line.rstrip().split("\t")
            if fields[0] == "S" and len(fields) >= 3:
                segments.append({"id": fields[1], "length_bp": len(fields[2]) if fields[2] != "*" else None})
            elif fields[0] == "L" and len(fields) >= 6:
                links += 1
                if fields[1] == fields[3]:
                    self_links.append(fields[1:6])
    return {"file_sha256": digest(path), "segments": segments, "link_count": links, "self_links": self_links}


class Study:
    def __init__(self, folder, input_folder, case, audit, timeout, threads=1):
        self.folder, self.input, self.case, self.timeout = folder, input_folder, case, timeout
        self.threads = threads
        self.lock = threading.Lock()
        self.pixi = os.environ.get("PIXI_EXE") or shutil.which("pixi") or str(Path.home() / ".pixi/bin/pixi")
        if not Path(self.pixi).is_file():
            raise ValueError("Pixi executable was not found")
        self.env = {**os.environ, "OMP_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
        self.summary = {"schema_version": 1, "study_id": folder.name, "pilot_batch": PILOT, "scenario": SCENARIO,
                        "status": "running", "started_at": timestamp(), "root": str(ROOT), "study_root": str(folder),
                        "host": platform.node(), "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "tool_threads": threads,
                        "maximum_concurrent_tool_chains": 2, "input_audit": audit,
                        "source_sha256": {"scripts/investigate_causes.py": digest(Path(__file__)),
                                          "pipeline/scoring.py": digest(ROOT / "pipeline/scoring.py"),
                                          "pixi.lock": digest(ROOT / "pixi.lock")}, "phases": {}, "chains": {}}
        self.update()

    def update(self, phase=None, record=None, chain=None, status=None):
        with self.lock:
            if phase:
                self.summary["phases"][phase] = copy.deepcopy(record)
            if chain:
                self.summary["chains"][chain] = status
            self.summary["updated_at"] = timestamp()
            save(self.folder / "summary.json", self.summary)

    def command(self, environment, directory, argv):
        # Explicit chdir after Pixi activation also protects against any Pixi task cwd default.
        return [self.pixi, "run", "--locked", "-e", environment, "python", "-c", EXEC_IN_DIRECTORY, str(directory)] + argv

    def phase(self, name, environment, directory, argv, assembly, gfa=None, extra=None):
        directory.mkdir(parents=True, exist_ok=True)
        record = {"name": name, "status": "running", "started_at": timestamp(), "cwd": str(directory),
                  "tool_command": argv, "command": self.command(environment, directory, argv),
                  "input_hashes": self.summary["input_audit"], **(extra or {})}
        stdout_path = directory / (name + (".stdout.fasta" if argv[0] == "raven" else ".stdout.log"))
        stderr_path = directory / (name + ".stderr.log")
        record.update(stdout_file=str(stdout_path.relative_to(self.folder)), stderr_file=str(stderr_path.relative_to(self.folder)))
        self.update(phase=name, record=record)
        started = time.monotonic()
        try:
            version_command = self.command(environment, directory, [argv[0], "--version"])
            version = subprocess.run(version_command, cwd=directory, env=self.env, capture_output=True, text=True, timeout=60)
            record.update(version_command=version_command, version=(version.stdout + version.stderr).strip())
            expected_version = {"flye": "2.9.6", "raven": "1.8.3"}[environment]
            if version.returncode or not re.search(r"(?<![0-9.])" + re.escape(expected_version) + r"(?![0-9.])", record["version"]):
                raise RuntimeError("Tool version does not match the pinned cause study")
            with stdout_path.open("w") as stdout, stderr_path.open("w") as stderr:
                process = subprocess.Popen(record["command"], cwd=directory, env=self.env, stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    record["exit_code"] = process.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise
            if record["exit_code"]:
                raise RuntimeError("Tool exited with code " + str(record["exit_code"]))
            assembly = stdout_path if assembly is None else assembly
            if not assembly.exists():
                raise ValueError("Expected stage FASTA was not produced")
            record.update(assembly_file=str(assembly.relative_to(self.folder)), assembly_sha256=digest(assembly),
                          evaluation=evaluate(self.case, self.input / "truth.fasta", assembly),
                          small_contig_inspection=circular_inspection(assembly, self.input / "truth.fasta"),
                          contig_lengths={key: len(value) for key, value in fasta(assembly).items()}, status="complete")
            if gfa:
                if not gfa.exists():
                    raise ValueError("Expected stage GFA was not produced")
                record["gfa"] = gfa_summary(gfa)
                record["gfa_file"] = str(gfa.relative_to(self.folder))
        except Exception as error:
            record.update(status="error", error=f"{type(error).__name__}: {error}")
        finally:
            for path, key in ((stdout_path, "stdout_sha256"), (stderr_path, "stderr_sha256")):
                if path.exists():
                    record[key] = digest(path)
            record.update(elapsed_seconds=round(time.monotonic() - started, 3), finished_at=timestamp())
            save(directory / (name + ".json"), record)
            self.update(phase=name, record=record)
        if record["status"] != "complete":
            raise RuntimeError(name + ": " + record["error"])
        return record

    def flye(self):
        for label, overlap in (("default", None), ("min3000", 3000)):
            directory = self.folder / "flye" / label
            output = directory / "output"
            argv = ["flye", "--nano-hq", str(self.input / "reads.fastq.gz"), "--threads", str(self.threads), "--out-dir", str(output)]
            if overlap:
                argv += ["--min-overlap", str(overlap)]
            self.phase("flye_" + label + "_draft", "flye", directory, argv + ["--stop-after", "assembly"],
                       output / "00-assembly/draft_assembly.fasta")
            if overlap:
                self.phase("flye_min3000_final", "flye", directory, argv + ["--resume"], output / "assembly.fasta", output / "assembly_graph.gfa")

    def raven(self):
        initial = self.folder / "raven" / "p0"
        argv = ["raven", "-t", str(self.threads), "-p", "0", "--graphical-fragment-assembly", str(initial / "graph.gfa"), str(self.input / "reads.fastq.gz")]
        self.phase("raven_p0", "raven", initial, argv, None, initial / "graph.gfa")
        checkpoint = initial / "raven.cereal"
        if not checkpoint.exists():
            raise ValueError("Raven p0 did not retain raven.cereal")
        initial_hash = digest(checkpoint)
        errors = []
        for label, rounds in (("resume0", 0), ("p1", 1), ("p2", 2)):
            directory = self.folder / "raven" / label
            directory.mkdir(parents=True, exist_ok=False)
            copied = directory / "raven.cereal"
            shutil.copyfile(checkpoint, copied)
            if digest(checkpoint) != initial_hash or digest(copied) != initial_hash:
                raise ValueError("Independent Raven checkpoint copy hash mismatch")
            extra = {"initial_checkpoint_sha256": initial_hash, "copied_checkpoint_sha256_before_resume": digest(copied),
                     "checkpoint_source": str(checkpoint.relative_to(self.folder)), "checkpoint_copy": str(copied.relative_to(self.folder))}
            argv = ["raven", "-t", str(self.threads), "-p", str(rounds), "--resume", "--graphical-fragment-assembly", str(directory / "graph.gfa"), str(self.input / "reads.fastq.gz")]
            try:
                self.phase("raven_" + label, "raven", directory, argv, None, directory / "graph.gfa", extra)
            except RuntimeError as error:
                errors.append(str(error))
        if digest(checkpoint) != initial_hash:
            raise ValueError("Initial Raven checkpoint was modified")
        if errors:
            raise RuntimeError("; ".join(errors))

    def chain(self, name, function):
        self.update(chain=name, status="running")
        try:
            function()
            self.update(chain=name, status="complete")
        except Exception as error:
            self.update(chain=name, status={"status": "error", "error": f"{type(error).__name__}: {error}"})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--timeout", type=int, default=7200, help="Maximum seconds per tool phase")
    parser.add_argument("--tool-threads", type=int, default=1)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.study_id) or args.timeout <= 0 or args.tool_threads < 1:
        raise ValueError("Use a simple study identifier and positive timeout")
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 2 * args.tool_threads:
        raise ValueError("Run this two-chain investigation in a Slurm job with at least twice the tool thread count allocated")
    input_folder, case, audit = checked_inputs()
    folder = ROOT / "runs" / PILOT / "investigations" / args.study_id
    folder.mkdir(parents=True, exist_ok=False)
    study = Study(folder, input_folder, case, audit, args.timeout, args.tool_threads)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(study.chain, "flye", study.flye), executor.submit(study.chain, "raven", study.raven)]
        for future in futures:
            future.result()
    after_folder, after_case, after_audit = checked_inputs()
    study.summary["inputs_unchanged"] = after_audit == audit
    if after_audit != audit:
        study.summary["chains"]["input_verification"] = {"status": "error", "error": "Frozen pilot inputs changed during study"}
    study.summary.update(status="complete" if all(value == "complete" for value in study.summary["chains"].values()) else "error", finished_at=timestamp())
    study.update()
    print(json.dumps({"study": str(folder), "status": study.summary["status"], "chains": study.summary["chains"]}, indent=2))
    return 0 if study.summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
