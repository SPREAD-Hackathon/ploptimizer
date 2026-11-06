"""Synchronise this work area and submit a dependency-linked Slurm pilot."""

import datetime
import re
import shlex
import subprocess
from pathlib import Path

from .cases import plan
from .assets import ensure_assets
from .common import ROOT, load, save


def ssh(host, argv):
    return subprocess.check_output(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, shlex.join(argv)], text=True, timeout=180).strip()


def transfer(host, remote_root):
    # Compatible with the macOS system rsync; constrain remote shell path syntax.
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", host) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_root):
        raise ValueError("Use a simple SSH destination and an absolute path without spaces")
    ssh(host, ["mkdir", "-p", remote_root])
    excludes = [".pixi", ".cache", ".tools", ".t", ".vercel", ".env*", "node_modules", "__pycache__", "*.pyc", "runs", "data", "dist", "config/cluster.local.json"]
    argv = ["rsync", "-az"]
    for pattern in excludes:
        argv += ["--exclude", pattern]
    subprocess.run(argv + [str(ROOT) + "/", host + ":" + remote_root + "/"], check=True)


def submit(config, cluster, scenario_id=None, after_job=None, assembly_after_job=None):
    from .determinism import assembly_tasks, repeat_settings
    panel = repeat_settings(config)
    if after_job is not None and not re.fullmatch(r"[1-9][0-9]*", str(after_job)):
        raise ValueError("Dependency job must be a numeric Slurm job ID")
    if assembly_after_job is not None and not re.fullmatch(r"[1-9][0-9]*", str(assembly_after_job)):
        raise ValueError("Assembly dependency must be a numeric Slurm job ID")
    if panel and max(panel["threads"]) > config["threads"]:
        raise ValueError("Determinism thread settings exceed the reserved CPUs")
    ensure_assets(ROOT)
    for key in ("host", "remote_root", "account", "pixi"):
        if not cluster.get(key) or "REPLACE" in cluster[key]:
            raise ValueError(f"Configure the cluster {key} before submitting")
    if not cluster["remote_root"].startswith("/") or "\n" in cluster["remote_root"]:
        raise ValueError("Remote root must be an absolute directory")
    if config["threads"] != cluster["cpus"]:
        raise ValueError("Tool threads must equal requested Slurm CPUs")
    scenarios = [c for c in plan(config) if not scenario_id or c["id"] == scenario_id]
    if panel:
        available = {case["id"] for case in scenarios}
        if not scenario_id and set(panel["scenarios"]) - available:
            raise ValueError("Unknown determinism scenario in configuration")
        scenarios = [case for case in scenarios if case["id"] in panel["scenarios"]]
    if not scenarios:
        raise ValueError("No scenarios selected")
    batch_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    batch = ROOT / "runs" / batch_id
    batch.mkdir(parents=True, exist_ok=False)
    save(batch / "config.json", config)
    tasks = {"simulate": [c["id"] for c in scenarios],
             "assemble": assembly_tasks(config, scenarios)}
    save(batch / "tasks.json", tasks)
    root = Path(cluster["remote_root"])
    remote_batch = root / "runs" / batch_id
    scripts = batch / "slurm"
    scripts.mkdir()
    (batch / "logs").mkdir()
    pixi = shlex.quote(cluster["pixi"])
    prefix = "#!/usr/bin/env bash\nset -euo pipefail\n"
    prefix += f"cd {shlex.quote(str(root))}\n"
    prefix += f'export PATH={shlex.quote(str(Path(cluster["pixi"]).parent))}:"$PATH"\n'
    # Python multiprocessing uses Unix sockets with a short fixed path limit.
    prefix += 'export PIXI_CACHE_DIR="$PWD/.cache/pixi"\nexport XDG_CACHE_HOME="$PWD/.cache"\nexport TMPDIR="$PWD/.t/${SLURM_JOB_ID}"\nmkdir -p "$TMPDIR"\n'
    python = f"{pixi} run --locked -e default python benchmark.py"
    roles = {
        "prepare": f"{pixi} install --locked --all\n{python} prepare --batch {batch_id}\n{pixi} run --locked -e default python -m unittest discover -s tests -v\n",
        "simulate": f'{python} task --batch {batch_id} --kind simulate --index "$SLURM_ARRAY_TASK_ID"\n',
        "assemble": f'{python} task --batch {batch_id} --kind assemble --index "$SLURM_ARRAY_TASK_ID"\n',
        "report": f"{python} report --batch {batch_id}\n",
    }
    if config.get("noisy_panel"):
        roles["assessment"] = f"{pixi} run --locked -e simulator python -m pipeline.assessments --batch {batch_id}\n"
    for role, body in roles.items():
        (scripts / (role + ".sh")).write_text(prefix + body)
    submission = {"batch_id": batch_id, "cluster": cluster, "tasks": tasks, "jobs": {}, "status": "submitting", "after_job": after_job, "assembly_after_job": assembly_after_job}
    save(batch / "submission.json", submission)
    transfer(cluster["host"], cluster["remote_root"])
    ssh(cluster["host"], ["mkdir", "-p", str(remote_batch / "logs")])
    subprocess.run(["rsync", "-az", str(batch) + "/", cluster["host"] + ":" + str(remote_batch) + "/"], check=True)
    for role in (("prepare", "simulate", "assemble", "assessment", "report") if config.get("noisy_panel") else ("prepare", "simulate", "assemble", "report")):
        argv = ["sbatch", "--parsable", "--account", cluster["account"], "--partition", cluster["partition"],
                "--chdir", str(root), "--job-name", f"ploptimizer-{role}",
                "--output", str(remote_batch / "logs" / (role + "-%A_%a.out")),
                "--error", str(remote_batch / "logs" / (role + "-%A_%a.err"))]
        if role == "assemble":
            argv += ["--cpus-per-task", str(cluster["cpus"]), "--mem", cluster["memory"], "--time", cluster["time"]]
        else:
            memory = "8G" if role == "prepare" else "4G" if config.get("noisy_panel") else "2G"
            duration = "02:00:00" if role == "simulate" and config.get("noisy_panel") else "01:00:00" if role in ("prepare", "assessment") else "00:30:00"
            argv += ["--cpus-per-task", "1", "--mem", memory, "--time", duration]
        if role in tasks:
            argv += ["--array", f"0-{len(tasks[role]) - 1}%{cluster['array_concurrency']}"]
        if role == "prepare" and after_job is not None:
            argv += ["--dependency", "afterany:" + str(after_job), "--kill-on-invalid-dep=yes"]
        if role != "prepare":
            preceding = {"simulate": "prepare", "assemble": "simulate", "assessment": "assemble", "report": "assessment" if config.get("noisy_panel") else "assemble"}[role]
            condition = "afterany" if role in ("report", "assessment") else "afterok"
            dependency = condition + ":" + submission["jobs"][preceding]
            if role == "assemble" and assembly_after_job:
                dependency += ",afterany:" + str(assembly_after_job)
            argv += ["--dependency", dependency, "--kill-on-invalid-dep=yes"]
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


def collect(batch, include_site=True):
    submission = load(batch / "submission.json")
    cluster = submission["cluster"]
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", cluster["host"]) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", cluster["remote_root"]):
        raise ValueError("Invalid SSH destination/path in submission record")
    remote_batch = Path(cluster["remote_root"]) / "runs" / batch.name
    # Sample scheduler state before copying outputs, avoiding false terminal errors.
    job_ids = list(submission["jobs"].values())
    diagnostics = batch / "diagnostic_submission.json"
    if diagnostics.exists():
        job_ids.append(load(diagnostics)["job_id"])
    review = batch / "diagnostic_review_submission.json"
    if review.exists():
        job_ids.append(load(review)["job_id"])
    accounting = ssh(cluster["host"], ["sacct", "--array", "-n", "-P", "-j", ",".join(job_ids),
                                      "--format=JobID,State,ExitCode,Elapsed,MaxRSS"])
    # Results and provenance only: avoid copying reads and large assembly intermediates.
    def exists(folder):
        return subprocess.run(["ssh", "-o", "BatchMode=yes", cluster["host"], shlex.join(["test", "-d", str(remote_batch / folder)])], capture_output=True).returncode == 0
    folders = ("results", "site", "logs", "provenance") if include_site else ("results", "logs", "provenance")
    for folder in folders:
        if exists(folder):
            target = batch / folder
            target.mkdir(exist_ok=True)
            excludes = ["--exclude=output", "--exclude=stdout.log", "--exclude=raven.cereal"] if folder == "results" else []
            subprocess.run(["rsync", "-az"] + excludes + [cluster["host"] + ":" + str(remote_batch / folder) + "/", str(target) + "/"], check=True)
    # Copy small input manifests without the read files.
    if exists("cases"):
        subprocess.run(["rsync", "-az", "--include=*/", "--include=input.json", "--exclude=*", cluster["host"] + ":" + str(remote_batch / "cases") + "/", str(batch / "cases") + "/"], check=True)
    (batch / "accounting.tsv").write_text(accounting + "\n")
    return accounting


def submit_diagnostics(batch, after_job=None, rerun=False, interim=False):
    """Queue supplementary evidence separately, preserving strict executions."""
    record_name = 'diagnostic_review_submission.json' if interim else 'diagnostic_submission.json'
    previous_path = batch / record_name
    previous = load(previous_path) if previous_path.exists() else None
    if previous and not rerun:
        raise ValueError('Diagnostics already submitted; use --rerun for a new attempt')
    submission = load(batch / 'submission.json')
    cluster = submission['cluster']
    if after_job is not None and not re.fullmatch(r'[1-9][0-9]*', str(after_job)):
        raise ValueError('Dependency job must be a numeric Slurm job ID')
    root = Path(cluster['remote_root'])
    remote_batch = root / 'runs' / batch.name
    pixi = shlex.quote(cluster['pixi'])
    script_name = 'diagnostics-review.sh' if interim else 'diagnostics.sh'
    script = batch / 'slurm' / script_name
    script.parent.mkdir(exist_ok=True)
    script.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
                      + f'cd {shlex.quote(str(root))}\n'
                      + f'export PATH={shlex.quote(str(Path(cluster["pixi"]).parent))}:"$PATH"\n'
                      + 'export PIXI_CACHE_DIR="$PWD/.cache/pixi"\nexport XDG_CACHE_HOME="$PWD/.cache"\n'
                      + f'{pixi} run --locked -e default python -m pipeline.diagnostic_runs --batch {batch.name}\n')
    transfer(cluster['host'], cluster['remote_root'])
    subprocess.run(['rsync', '-az', str(script), cluster['host'] + ':' + str(remote_batch / 'slurm') + '/'], check=True)
    argv = ['sbatch', '--parsable', '--account', cluster['account'], '--partition', cluster['partition'],
            '--chdir', str(root), '--job-name', 'ploptimizer-diagnostics-review' if interim else 'ploptimizer-diagnostics', '--cpus-per-task', '1',
            '--mem', '4G', '--time', '01:00:00',
            '--output', str(remote_batch / ('logs/diagnostics-review-%j.out' if interim else 'logs/diagnostics-%j.out')),
            '--error', str(remote_batch / ('logs/diagnostics-review-%j.err' if interim else 'logs/diagnostics-%j.err'))]
    if after_job:
        argv += ['--dependency', 'afterany:' + str(after_job), '--kill-on-invalid-dep=yes']
    argv += [str(remote_batch / 'slurm' / script_name)]
    job = ssh(cluster['host'], argv).split(';')[0]
    if not job.isdigit():
        raise ValueError('Unexpected diagnostic job ID: ' + job)
    record = {'batch_id': batch.name, 'job_id': job, 'after_job': after_job, 'interim': interim,
              'previous_job_ids': ([*previous.get('previous_job_ids', []), previous['job_id']] if previous else [])}
    save(previous_path, record)
    subprocess.run(['rsync', '-az', str(previous_path), cluster['host'] + ':' + str(remote_batch) + '/'], check=True)
    return record
