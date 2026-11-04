"""Synchronise this work area and submit a dependency-linked Slurm pilot."""

import datetime
import re
import shlex
import subprocess
from pathlib import Path

from .cases import plan
from .common import ROOT, load, save


def ssh(host, argv):
    return subprocess.check_output(["ssh", "-o", "BatchMode=yes", host, shlex.join(argv)], text=True).strip()


def transfer(host, remote_root):
    # Compatible with the macOS system rsync; constrain remote shell path syntax.
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", host) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_root):
        raise ValueError("Use a simple SSH destination and an absolute path without spaces")
    ssh(host, ["mkdir", "-p", remote_root])
    excludes = [".pixi", ".cache", ".tools", ".t", ".vercel", "__pycache__", "*.pyc", "runs", "data", "dist", "config/cluster.local.json"]
    argv = ["rsync", "-az"]
    for pattern in excludes:
        argv += ["--exclude", pattern]
    subprocess.run(argv + [str(ROOT) + "/", host + ":" + remote_root + "/"], check=True)


def submit(config, cluster, scenario_id=None):
    for key in ("host", "remote_root", "account", "pixi"):
        if not cluster.get(key) or "REPLACE" in cluster[key]:
            raise ValueError(f"Configure the cluster {key} before submitting")
    if not cluster["remote_root"].startswith("/") or "\n" in cluster["remote_root"]:
        raise ValueError("Remote root must be an absolute directory")
    if config["threads"] != cluster["cpus"]:
        raise ValueError("Tool threads must equal requested Slurm CPUs")
    scenarios = [c for c in plan(config) if not scenario_id or c["id"] == scenario_id]
    if not scenarios:
        raise ValueError("No scenarios selected")
    batch_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    batch = ROOT / "runs" / batch_id
    batch.mkdir(parents=True, exist_ok=False)
    save(batch / "config.json", config)
    tasks = {"simulate": [c["id"] for c in scenarios],
             "assemble": [{"scenario": c["id"], "tool": tool} for c in scenarios for tool in config["tools"]]}
    save(batch / "tasks.json", tasks)
    root = Path(cluster["remote_root"])
    remote_batch = root / "runs" / batch_id
    scripts = batch / "slurm"
    scripts.mkdir()
    (batch / "logs").mkdir()
    pixi = shlex.quote(cluster["pixi"])
    prefix = "#!/usr/bin/env bash\nset -euo pipefail\n"
    prefix += f"cd {shlex.quote(str(root))}\n"
    # Python multiprocessing uses Unix sockets with a short fixed path limit.
    prefix += 'export PIXI_CACHE_DIR="$PWD/.cache/pixi"\nexport XDG_CACHE_HOME="$PWD/.cache"\nexport TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
    python = f"{pixi} run --locked -e default python benchmark.py"
    roles = {
        "prepare": f"{pixi} install --locked --all\n{python} prepare --batch {batch_id}\n{pixi} run --locked -e default python -m unittest discover -s tests -v\n",
        "simulate": f'{python} task --batch {batch_id} --kind simulate --index "$SLURM_ARRAY_TASK_ID"\n',
        "assemble": f'{python} task --batch {batch_id} --kind assemble --index "$SLURM_ARRAY_TASK_ID"\n',
        "report": f"{python} report --batch {batch_id}\n",
    }
    for role, body in roles.items():
        (scripts / (role + ".sh")).write_text(prefix + body)
    submission = {"batch_id": batch_id, "cluster": cluster, "tasks": tasks, "jobs": {}, "status": "submitting"}
    save(batch / "submission.json", submission)
    transfer(cluster["host"], cluster["remote_root"])
    ssh(cluster["host"], ["mkdir", "-p", str(remote_batch / "logs")])
    subprocess.run(["rsync", "-az", str(batch) + "/", cluster["host"] + ":" + str(remote_batch) + "/"], check=True)
    for role in ("prepare", "simulate", "assemble", "report"):
        argv = ["sbatch", "--parsable", "--account", cluster["account"], "--partition", cluster["partition"],
                "--chdir", str(root), "--job-name", f"ploptimizer-{role}",
                "--output", str(remote_batch / "logs" / (role + "-%A_%a.out")),
                "--error", str(remote_batch / "logs" / (role + "-%A_%a.err"))]
        if role == "assemble":
            argv += ["--cpus-per-task", str(cluster["cpus"]), "--mem", cluster["memory"], "--time", cluster["time"]]
        else:
            argv += ["--cpus-per-task", "1", "--mem", "8G" if role == "prepare" else "2G", "--time", "01:00:00" if role == "prepare" else "00:30:00"]
        if role in tasks:
            argv += ["--array", f"0-{len(tasks[role]) - 1}%{cluster['array_concurrency']}"]
        if role != "prepare":
            preceding = {"simulate": "prepare", "assemble": "simulate", "report": "assemble"}[role]
            condition = "afterany" if role == "report" else "afterok"
            argv += ["--dependency", condition + ":" + submission["jobs"][preceding], "--kill-on-invalid-dep=yes"]
        argv += [str(remote_batch / "slurm" / (role + ".sh"))]
        try:
            job_id = ssh(cluster["host"], argv).split(";")[0]
            if not job_id.isdigit():
                raise ValueError("Unexpected sbatch job identifier: " + job_id)
            submission["jobs"][role] = job_id
        except Exception:
            submission["status"] = "partially_submitted"
            save(batch / "submission.json", submission)
            raise
        save(batch / "submission.json", submission)
        subprocess.run(["rsync", "-az", str(batch / "submission.json"), cluster["host"] + ":" + str(remote_batch) + "/"], check=True)
    submission["status"] = "submitted"
    save(batch / "submission.json", submission)
    subprocess.run(["rsync", "-az", str(batch / "submission.json"), cluster["host"] + ":" + str(remote_batch) + "/"], check=True)
    return submission


def collect(batch):
    submission = load(batch / "submission.json")
    cluster = submission["cluster"]
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", cluster["host"]) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", cluster["remote_root"]):
        raise ValueError("Invalid SSH destination/path in submission record")
    remote_batch = Path(cluster["remote_root"]) / "runs" / batch.name
    # Results and provenance only: avoid copying reads and large assembly intermediates.
    def exists(folder):
        return subprocess.run(["ssh", "-o", "BatchMode=yes", cluster["host"], shlex.join(["test", "-d", str(remote_batch / folder)])], capture_output=True).returncode == 0
    for folder in ("results", "site", "logs", "provenance"):
        if exists(folder):
            target = batch / folder
            target.mkdir(exist_ok=True)
            excludes = ["--exclude=output", "--exclude=stdout.log"] if folder == "results" else []
            subprocess.run(["rsync", "-az"] + excludes + [cluster["host"] + ":" + str(remote_batch / folder) + "/", str(target) + "/"], check=True)
    # Copy small input manifests without the read files.
    if exists("cases"):
        subprocess.run(["rsync", "-az", "--include=*/", "--include=input.json", "--exclude=*", cluster["host"] + ":" + str(remote_batch / "cases") + "/", str(batch / "cases") + "/"], check=True)
    accounting = ssh(cluster["host"], ["sacct", "--array", "-n", "-P", "-j", ",".join(submission["jobs"].values()),
                                      "--format=JobID,State,ExitCode,Elapsed,MaxRSS"])
    (batch / "accounting.tsv").write_text(accounting + "\n")
    return accounting
