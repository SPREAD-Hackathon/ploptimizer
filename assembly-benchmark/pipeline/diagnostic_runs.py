"""Run supplementary minimap2 evidence on recorded assemblies, on a compute node."""

import argparse
import datetime
import os
import re
import signal
import subprocess
from pathlib import Path

from .common import ROOT, digest, fasta, fingerprint, load, save
from .diagnostics import DEFAULT_POLICY, minimap2_command, summarise_paf


METRIC_VERSION = "paf-recovery-evidence-v1"
PIXI_PREFIX = ["pixi", "run", "--locked", "-e", "plassembler"]


def batch_directory(identifier):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
        raise ValueError("Use a simple batch identifier, not a path")
    batch = (ROOT / "runs" / identifier).resolve()
    if not batch.is_relative_to(ROOT.resolve()) or not batch.is_dir():
        raise ValueError("Batch must exist inside the benchmark runs directory")
    return batch


def inside(batch, relative):
    value = Path(relative)
    if value.is_absolute():
        raise ValueError("Recorded paths must be relative to the batch")
    path = (batch / value).resolve()
    if not path.is_relative_to(batch.resolve()):
        raise ValueError("Recorded path escapes the batch")
    return path


def cached_digest(path, cache):
    stat = path.stat()
    identity = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if path not in cache or cache[path][0] != identity:
        cache[path] = (identity, digest(path))
    return cache[path][1]


def verified_inputs(batch, execution_path, record, hash_cache):
    if "batch_id" in record and record["batch_id"] != batch.name:
        raise ValueError("Execution belongs to a different batch")
    scenario = record.get("scenario_id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", scenario):
        raise ValueError("Invalid execution scenario identifier")
    input_dir = inside(batch, "cases/" + scenario)
    manifest_path = input_dir / "input.json"
    manifest = load(manifest_path)
    case = manifest["case"]
    case_fingerprint = fingerprint({key: value for key, value in case.items() if key != "fingerprint"})
    if manifest.get("status") != "valid" or case["id"] != scenario or case["fingerprint"] != case_fingerprint or case["fingerprint"] != record.get("scenario_fingerprint"):
        raise ValueError("Input manifest does not match the execution scenario")
    config = load(batch / "config.json")
    if fingerprint(config) != record.get("config_fingerprint"):
        raise ValueError("Execution does not match the frozen batch configuration")
    hashes = {"batch_id_execution_available": "batch_id" in record,
              "execution_sha256": digest(execution_path), "input_manifest_sha256": digest(manifest_path),
              "config_sha256": digest(batch / "config.json")}
    for filename, key in (("truth.fasta", "truth_sha256"), ("reads.fastq.gz", "reads_sha256")):
        path = inside(batch, str((input_dir / filename).relative_to(batch)))
        actual = cached_digest(path, hash_cache)
        if actual != manifest.get(key) or (key in record and actual != record[key]):
            raise ValueError("Recorded input checksum mismatch: " + filename)
        hashes[key] = actual
        hashes[key + "_execution_hash_available"] = key in record
    assembly = inside(batch, record["assembly_file"])
    hashes["assembly_sha256"] = cached_digest(assembly, hash_cache)
    if hashes["assembly_sha256"] != record.get("assembly_sha256"):
        raise ValueError("Recorded assembly checksum mismatch")
    return case, input_dir / "truth.fasta", assembly, hashes


def run_mapper(command, stdout, stderr, timeout):
    process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise


def diagnose_execution(batch, execution_path, threads=1, timeout=600, hash_cache=None):
    """Persist sibling evidence; never mutate the assembler's execution record."""
    batch = batch.resolve()
    if not batch.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Batch must stay inside the benchmark runs directory")
    execution_path = execution_path.resolve()
    if not execution_path.is_relative_to(batch.resolve()) or not execution_path.is_relative_to((batch / "results").resolve()):
        raise ValueError("Execution record must be under this batch's results")
    directory = execution_path.parent
    target = directory / "diagnostics.json"
    result = {"schema_version": 1, "metric_version": METRIC_VERSION, "batch_id": batch.name,
              "policy": dict(DEFAULT_POLICY), "status": "running"}
    try:
        record = load(execution_path)
        result.update(scenario_id=record.get("scenario_id"), tool=record.get("tool"),
                      run_id=record.get("run_id"), strict_status=record.get("status"))
        if record.get("status") not in ("pass", "fail"):
            result.update(status="skipped", reason="Assembler execution has no successful final assessment")
            return result
        case, truth, assembly, hashes = verified_inputs(batch, execution_path, record, hash_cache if hash_cache is not None else {})
        result["input_hashes"] = hashes
        result["command"] = PIXI_PREFIX + minimap2_command(truth, assembly, threads)
        version_command = PIXI_PREFIX + ["minimap2", "--version"]
        version = subprocess.run(version_command, capture_output=True, text=True, timeout=60, cwd=ROOT)
        result["mapper_version_command"] = version_command
        result["mapper_version"] = (version.stdout + version.stderr).strip()
        if version.returncode:
            raise RuntimeError("Minimap2 version check failed")
        # Include the installed mapper and parser source so code/tool changes cannot reuse stale evidence.
        signature = fingerprint({"input_hashes": hashes, "metric_version": METRIC_VERSION,
                                 "policy": DEFAULT_POLICY, "command": result["command"],
                                 "mapper_version": result["mapper_version"],
                                 "parser_sha256": digest(ROOT / "pipeline/diagnostics.py"),
                                 "runner_sha256": digest(Path(__file__))})
        result["cache_fingerprint"] = signature
        if target.exists():
            previous = load(target)
            if previous.get("status") == "complete" and previous.get("metric_version") == METRIC_VERSION and previous.get("cache_fingerprint") == signature:
                paf = directory / "alignment.paf"
                stderr = directory / "alignment.stderr.log"
                if paf.exists() and stderr.exists() and digest(paf) == previous.get("paf_sha256") and digest(stderr) == previous.get("stderr_sha256"):
                    return previous
        sequences = fasta(assembly)
        lengths = {name: len(sequence) for name, sequence in sequences.items()}
        paf_path = directory / "alignment.paf"
        stderr_path = directory / "alignment.stderr.log"
        result["paf_file"] = str(paf_path.relative_to(batch))
        result["stderr_file"] = str(stderr_path.relative_to(batch))
        result["mapper_invoked"] = bool(lengths)
        result["exit_code"] = None
        if lengths:
            with paf_path.open("w") as stdout, stderr_path.open("w") as stderr:
                result["exit_code"] = run_mapper(result["command"], stdout, stderr, timeout)
            if result["exit_code"]:
                raise RuntimeError(f"Minimap2 exited with code {result['exit_code']}")
        else:
            paf_path.write_text("")
            stderr_path.write_text("Empty assembly; no mapper invocation needed.\n")
            result.update(exit_code=None, mapper_invoked=False)
        result["paf_file"] = str(paf_path.relative_to(batch))
        result["stderr_file"] = str(stderr_path.relative_to(batch))
        result["paf_sha256"] = digest(paf_path)
        result["stderr_sha256"] = digest(stderr_path)
        result["evidence"] = summarise_paf(case, paf_path, assembly_lengths=lengths)
        if result["evidence"]["metric_version"] != METRIC_VERSION:
            raise ValueError("Diagnostic runner/parser metric versions disagree")
        result.update(status="complete", mapper_invoked=bool(lengths))
    except Exception as error:
        result.update(status="error", error=f"{type(error).__name__}: {error}")
    finally:
        # A cache hit returns its existing object and does not rewrite it here.
        if result["status"] != "running":
            for file_key, hash_key in (("paf_file", "paf_sha256"), ("stderr_file", "stderr_sha256")):
                if file_key in result and (batch / result[file_key]).exists():
                    result[hash_key] = digest(batch / result[file_key])
            result["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            save(target, result)
    return result


def run_batch(batch, threads=1, timeout=600):
    if not isinstance(threads, int) or isinstance(threads, bool) or threads < 1 or timeout <= 0:
        raise ValueError("Use positive alignment threads and timeout")
    batch = batch.resolve()
    if not batch.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Batch must stay inside the benchmark runs directory")
    counts, hash_cache = {}, {}
    for execution_path in sorted((batch / "results").rglob("execution.json")):
        result = diagnose_execution(batch, execution_path, threads, timeout, hash_cache)
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    print(run_batch(batch_directory(args.batch), args.threads, args.timeout))


if __name__ == "__main__":
    main()
