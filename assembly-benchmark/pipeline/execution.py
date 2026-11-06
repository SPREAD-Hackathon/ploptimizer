"""Run one assembler per Slurm task and persist success or failure evidence."""

import datetime
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .common import ROOT, digest, fingerprint, load, save
from .scoring import evaluate

ENVIRONMENTS = {"flye": "flye", "flye-meta": "flye", "raven": "raven", "plassembler": "plassembler", "miniasm": "miniasm"}
ENVIRONMENTS['miniasm-plus'] = 'miniasm-plus'


def execution_timeout(tool, config):
    """Cap Plassembler at two hours, honouring any shorter configured limit."""
    configured = config["timeout_seconds"]
    return min(configured, 7200) if tool == "plassembler" else configured


def command(tool, reads, output, config, mode="default"):
    if mode not in ("default", "deterministic") or mode == "deterministic" and tool not in ("flye", "flye-meta"):
        raise ValueError("This tool has no supported deterministic mode")
    threads = str(config["threads"])
    input_mode = config.get("flye_input_mode", "nano-hq")
    if input_mode not in {"nano-hq", "nano-raw"}:
        raise ValueError("Unsupported Flye input mode")
    if tool == 'miniasm-plus':
        return [sys.executable, '-m', 'pipeline.minipolish', '--reads', str(reads),
                '--raw-graph', config['miniasm_source_gfa'], '--source-execution', config['miniasm_source_execution'],
                '--output', str(output), '--threads', threads, '--rounds', '2']
    if tool == 'miniasm':
        return [sys.executable, '-m', 'pipeline.miniasm', '--reads', str(reads), '--output', str(output), '--threads', threads]
    if tool in ("flye", "flye-meta"):
        return ["flye", "--" + input_mode, str(reads), "--out-dir", str(output), "--threads", threads] + (["--meta"] if tool == "flye-meta" else []) + (["--deterministic"] if mode == "deterministic" else [])
    if tool == "raven":
        return ["raven", "-t", threads, "-F", str(output.parent / "assembly_graph.gfa"), str(reads)]
    if tool == "plassembler":
        return ["plassembler", "long", "--longreads", str(reads), "--outdir", str(output),
                "--threads", threads, "--skip_qc", "--skip_mash", *(["--raw_flag"] if config.get("plassembler_raw_flag") else []), *( ["--no_chromosome"] if config.get("plassembler_no_chromosome") else ["--keep_chromosome"] ),
                "--prefix", "benchmark", "--chromosome", str(config["plassembler_chromosome_threshold"])]
    raise ValueError(f"Unknown assembler: {tool}")


def run(case, tool, batch, config, threads=None, repeat=None, mode=None):
    from .determinism import biological_signature, execution_id, repeat_settings, sequence_signature
    settings = dict(config)
    if config.get("plassembler_no_chromosome") and any(r.get("molecule_type") == "chromosome" for r in case["replicons"]):
        raise ValueError("No-chromosome mode requires an input without a chromosome")
    settings["threads"] = config["threads"] if threads is None else threads
    panel = repeat_settings(config)
    if mode is not None and (not panel or mode not in panel.get("modes", {}).get(tool, [])):
        raise ValueError("Execution mode does not belong to the frozen determinism panel")
    if panel and panel.get("modes") and mode is None:
        raise ValueError("This determinism panel requires an explicit execution mode")
    if repeat is not None:
        if not panel or settings["threads"] not in panel["threads"] or not 1 <= repeat <= panel["repeats"] or case["id"] not in panel["scenarios"]:
            raise ValueError("Execution does not belong to the frozen determinism panel")
    elif threads is not None or panel:
        raise ValueError("Determinism runs require an explicit repeat and configured threads")
    directory = batch / "results" / case["id"] / tool
    if repeat is not None:
        directory = directory / "repeats" / execution_id(settings["threads"], repeat, mode)
    directory.mkdir(parents=True, exist_ok=True)
    working_directory = directory if tool == "raven" else ROOT
    result_path = directory / "execution.json"
    if result_path.exists():
        raise ValueError("Execution already recorded; use a new batch for independent runs")
    record = {"batch_id": batch.name, "scenario_id": case["id"], "scenario_fingerprint": case["fingerprint"], "tool": tool,
              "config_fingerprint": fingerprint(config), "threads": settings["threads"],
              "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
              "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
              "allocated_cpus": int(os.environ.get("SLURM_CPUS_PER_TASK", config["threads"])),
              "host": platform.node(), "status": "running",
              "timeout_seconds": execution_timeout(tool, config)}
    if tool == "plassembler" and config.get("plassembler_no_chromosome"):
        record["workflow_mode"] = "plasmid_only_no_chromosome"
    if mode is not None:
        record["mode"] = mode
    if tool == "raven":
        record["working_directory"] = str(directory.relative_to(batch))
        record["working_directory_base"] = "batch"
    source_root = Path(__file__).resolve().parent
    record["runtime_source_sha256"] = {"pipeline/" + path.name: digest(path) for path in source_root.glob("*.py")}
    if repeat is not None:
        record.update(repeat=repeat, run_id=execution_id(settings["threads"], repeat, mode))
    save(result_path, record)
    start = time.monotonic()
    try:
        if tool == "plassembler" and os.environ.get("SLURM_JOB_ID"):
            # Lower only this array element's allocation, never the other tools.
            array_job = os.environ.get("SLURM_ARRAY_JOB_ID")
            array_task = os.environ.get("SLURM_ARRAY_TASK_ID")
            job = f"{array_job}_{array_task}" if array_job and array_task else os.environ["SLURM_JOB_ID"]
            limit = max(1, int(record["timeout_seconds"] // 60))
            subprocess.run(["scontrol", "update", f"JobId={job}", f"TimeLimit={limit}"],
                           check=True, capture_output=True, text=True, timeout=30)
            record["slurm_time_limit_minutes"] = limit
        # Fail early if the execution directory cannot support multiprocessing sockets.
        temporary_root = os.environ.get("TMPDIR", str(ROOT / ".t" / str(os.getpid())))
        if not Path(temporary_root).resolve().is_relative_to(ROOT):
            raise ValueError("TMPDIR must stay inside the benchmark work area")
        Path(temporary_root).mkdir(parents=True, exist_ok=True)
        os.environ["TMPDIR"] = temporary_root
        if tool not in ('miniasm', 'miniasm-plus'):  # These workflows do not create multiprocessing sockets.
            with tempfile.TemporaryDirectory(prefix="pymp-", dir=temporary_root) as temporary:
                with socket.socket(socket.AF_UNIX) as probe:
                    probe.bind(str(Path(temporary) / "listener-12345678"))
        input_dir = batch / "cases" / case["id"]
        manifest = load(input_dir / "input.json")
        if manifest["status"] != "valid":
            record["status"] = "invalid_input"
            record["error"] = manifest.get("validation_summary", "Input admission did not pass; inspect input.json")
            return record
        if manifest["case"]["fingerprint"] != case["fingerprint"]:
            raise ValueError("Input scenario fingerprint does not match this run")
        reads = input_dir / "reads.fastq.gz"
        if digest(reads) != manifest["reads_sha256"] or digest(input_dir / "truth.fasta") != manifest["truth_sha256"]:
            raise ValueError("Input checksum mismatch")
        record["reads_sha256"] = manifest["reads_sha256"]
        record["truth_sha256"] = manifest["truth_sha256"]
        if tool == 'miniasm-plus':
            source_directory = batch / 'raw_assemblies' / case['id']
            settings['miniasm_source_gfa'] = str(source_directory / 'assembly.raw.gfa')
            settings['miniasm_source_execution'] = str(source_directory / 'execution.json')
        argv = command(tool, reads, directory / "output", settings, mode or "default")
        record["command"] = argv
        binary = 'minipolish' if tool == 'miniasm-plus' else "flye" if tool == "flye-meta" else tool
        version_cwd = {"cwd": working_directory} if tool == "raven" else {}
        version = subprocess.run([binary, "-V" if tool == 'miniasm' else "--version"], capture_output=True, text=True, timeout=30, **version_cwd)
        record["version"] = (version.stdout + version.stderr).strip()
        if version.returncode:
            raise RuntimeError("Assembler version check failed")
        save(result_path, record)
        # GNU time measures this process tree, rather than a cumulative child high-water mark.
        metrics = directory / "resources.txt"
        timed_argv = ["/usr/bin/time", "-v", "-o", str(metrics)] + argv if platform.system() == "Linux" else argv
        with (directory / "stdout.log").open("w") as stdout, (directory / "stderr.log").open("w") as stderr:
            process = subprocess.Popen(timed_argv, stdout=stdout, stderr=stderr, cwd=working_directory, start_new_session=True)
            try:
                remaining = record["timeout_seconds"]
                if record.get("slurm_time_limit_minutes"):
                    # Leave time to terminate children and persist the terminal record.
                    remaining = max(0, remaining - (time.monotonic() - start) - 30)
                returncode = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                record["status"] = "timeout"
                record["execution_outcome"] = "did_not_complete"
                record["error"] = f'Assembler did not complete within the {record["timeout_seconds"] / 3600:g}-hour limit.'
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
            if chromosome.exists() and not config.get("plassembler_no_chromosome"):
                record["retained_chromosome_sha256"] = digest(chromosome)
    except Exception as error:
        record.update(status="error", error=f"{type(error).__name__}: {error}")
    finally:
        if tool in ('miniasm', 'miniasm-plus') and (directory / 'output/workflow.json').exists():
            record['assembly_workflow'] = load(directory / 'output/workflow.json')
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        if tool == 'miniasm-plus' and record.get('assembly_workflow', {}).get('source_elapsed_seconds') is not None:
            workflow = record['assembly_workflow']
            record['polishing_elapsed_seconds'] = record['elapsed_seconds']
            record['elapsed_seconds'] = round(record['elapsed_seconds'] + workflow['source_elapsed_seconds'], 3)
            record['initial_miniasm_evaluation'] = workflow['source_evaluation']
            record['resource_scope'] = workflow['resource_scope']
            peaks = [p for p in (record.get('peak_memory_kb'), workflow.get('source_peak_memory_kb')) if p is not None]
            if peaks:
                record['peak_memory_kb'] = max(peaks)
            versions = workflow['versions']
            record['version'] = f'Miniasm {versions.get("miniasm", "unknown")} + {versions.get("minipolish", "Minipolish unknown")}'
        record["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(result_path, record)
    return record
