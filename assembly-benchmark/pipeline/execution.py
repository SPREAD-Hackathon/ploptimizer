"""Run one assembler per Slurm task and persist success or failure evidence."""

import datetime
import os
import platform
import re
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from .common import ROOT, digest, fingerprint, load, save
from .scoring import evaluate

ENVIRONMENTS = {"flye": "flye", "flye-meta": "flye", "raven": "raven", "plassembler": "plassembler"}


def command(tool, reads, output, config):
    threads = str(config["threads"])
    if tool in ("flye", "flye-meta"):
        return ["flye", "--nano-hq", str(reads), "--out-dir", str(output), "--threads", threads] + (["--meta"] if tool == "flye-meta" else [])
    if tool == "raven":
        return ["raven", "-t", threads, str(reads)]
    if tool == "plassembler":
        return ["plassembler", "long", "--longreads", str(reads), "--outdir", str(output),
                "--threads", threads, "--skip_qc", "--skip_mash", "--keep_chromosome",
                "--prefix", "benchmark", "--chromosome", str(config["plassembler_chromosome_threshold"])]
    raise ValueError(f"Unknown assembler: {tool}")


def run(case, tool, batch, config, threads=None, repeat=None):
    from .determinism import biological_signature, execution_id, repeat_settings, sequence_signature
    settings = dict(config)
    settings["threads"] = config["threads"] if threads is None else threads
    panel = repeat_settings(config)
    if repeat is not None:
        if not panel or settings["threads"] not in panel["threads"] or not 1 <= repeat <= panel["repeats"] or case["id"] not in panel["scenarios"]:
            raise ValueError("Execution does not belong to the frozen determinism panel")
    elif threads is not None or panel:
        raise ValueError("Determinism runs require an explicit repeat and configured threads")
    directory = batch / "results" / case["id"] / tool
    if repeat is not None:
        directory = directory / "repeats" / execution_id(settings["threads"], repeat)
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / "execution.json"
    if result_path.exists():
        raise ValueError("Execution already recorded; use a new batch for independent runs")
    record = {"batch_id": batch.name, "scenario_id": case["id"], "scenario_fingerprint": case["fingerprint"], "tool": tool,
              "config_fingerprint": fingerprint(config), "threads": settings["threads"],
              "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
              "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
              "allocated_cpus": int(os.environ.get("SLURM_CPUS_PER_TASK", config["threads"])),
              "host": platform.node(), "status": "running"}
    source_root = Path(__file__).resolve().parent
    record["runtime_source_sha256"] = {"pipeline/" + path.name: digest(path) for path in source_root.glob("*.py")}
    if repeat is not None:
        record.update(repeat=repeat, run_id=execution_id(settings["threads"], repeat))
    save(result_path, record)
    start = time.monotonic()
    try:
        # Fail early if the execution directory cannot support multiprocessing sockets.
        temporary_root = os.environ.get("TMPDIR", str(ROOT / ".t" / str(os.getpid())))
        if not Path(temporary_root).resolve().is_relative_to(ROOT):
            raise ValueError("TMPDIR must stay inside the benchmark work area")
        Path(temporary_root).mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = temporary_root
        with tempfile.TemporaryDirectory(prefix="pymp-", dir=temporary_root) as temporary:
            with socket.socket(socket.AF_UNIX) as probe:
                probe.bind(str(Path(temporary) / "listener-12345678"))
        input_dir = batch / "cases" / case["id"]
        manifest = load(input_dir / "input.json")
        if manifest["status"] != "valid":
            record["status"] = "invalid_input"
            record["error"] = "Input breadth did not meet the configured minimum"
            return record
        if manifest["case"]["fingerprint"] != case["fingerprint"]:
            raise ValueError("Input scenario fingerprint does not match this run")
        reads = input_dir / "reads.fastq.gz"
        if digest(reads) != manifest["reads_sha256"] or digest(input_dir / "truth.fasta") != manifest["truth_sha256"]:
            raise ValueError("Input checksum mismatch")
        record["reads_sha256"] = manifest["reads_sha256"]
        record["truth_sha256"] = manifest["truth_sha256"]
        argv = command(tool, reads, directory / "output", settings)
        record["command"] = argv
        binary = "flye" if tool == "flye-meta" else tool
        version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30)
        record["version"] = (version.stdout + version.stderr).strip()
        if version.returncode:
            raise RuntimeError("Assembler version check failed")
        save(result_path, record)
        # GNU time measures this process tree, rather than a cumulative child high-water mark.
        metrics = directory / "resources.txt"
        timed_argv = ["/usr/bin/time", "-v", "-o", str(metrics)] + argv if platform.system() == "Linux" else argv
        with (directory / "stdout.log").open("w") as stdout, (directory / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(timed_argv, stdout=stdout, stderr=stderr, cwd=ROOT, start_new_session=True)
            try:
                returncode = process.wait(timeout=config["timeout_seconds"])
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                record["status"] = "timeout"
                record["error"] = "Assembler exceeded configured timeout"
                return record
        record["exit_code"] = returncode
        if metrics.exists():
            match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", metrics.read_text())
            record["peak_memory_kb"] = int(match.group(1)) if match else None
        if returncode:
            record.update(status="error", error=f"Assembler exited with code {returncode}")
            return record
        if tool == "raven":
            assembly = directory / "stdout.log"
        elif tool == "plassembler":
            assembly = directory / "output/benchmark_plasmids.fasta"
        else:
            assembly = directory / "output/assembly.fasta"
        if not assembly.exists():
            raise ValueError("Assembler exited successfully but its expected FASTA is missing")
        record["assembly_file"] = str(assembly.relative_to(batch))
        record["assembly_sha256"] = digest(assembly)
        record["evaluation"] = evaluate(case, input_dir / "truth.fasta", assembly, tool == "plassembler")
        record["status"] = record["evaluation"]["status"]
        if repeat is not None:
            signature = sequence_signature(case, input_dir / "truth.fasta", assembly)
            record["normalised_assembly_sha256"] = signature["sha256"]
            record["sequence_normalisation"] = signature
            record["biological_sha256"] = biological_signature(record["evaluation"])
        if tool == "plassembler":
            initial = directory / "output/flye_output/assembly.fasta"
            if initial.exists():
                record["initial_flye_evaluation"] = evaluate(case, input_dir / "truth.fasta", initial)
            chromosome = directory / "output/chromosome.fasta"
            if chromosome.exists():
                record["retained_chromosome_sha256"] = digest(chromosome)
    except Exception as error:
        record.update(status="error", error=f"{type(error).__name__}: {error}")
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        record["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(result_path, record)
    return record
