#!/usr/bin/env python3
"""Entry point for the benchmark; invoke from any directory with Python >=3.10."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from pipeline.cases import find_case, plan
from pipeline.common import ROOT, digest, load, save


def batch_path(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Use a simple batch identifier, not a path")
    return ROOT / "runs" / value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "config/pilot.json"))
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("plan")
    for action in ("prepare", "simulate", "run", "task", "report", "collect", "snapshot", "publish", "follow"):
        sub = commands.add_parser(action)
        sub.add_argument("--batch", required=action not in ("prepare", "report"))
        if action in ("simulate", "run"):
            sub.add_argument("--scenario", required=True)
        if action == "run":
            sub.add_argument("--tool", choices=("flye", "flye-meta", "raven", "plassembler"), required=True)
        if action == "task":
            sub.add_argument("--kind", choices=("simulate", "assemble"), required=True)
            sub.add_argument("--index", required=True, type=int)
        if action == "follow":
            sub.add_argument("--interval", type=int, default=60)
            sub.add_argument("--publish-interval", type=int, default=600)
            sub.add_argument("--max-hours", type=float, default=8)
    sub = commands.add_parser("submit")
    sub.add_argument("--cluster", default=str(ROOT / "config/cluster.local.json"))
    sub.add_argument("--scenario", help="Limit the first pilot to one scenario")
    args = parser.parse_args(argv)
    batch = batch_path(args.batch) if getattr(args, "batch", None) else None
    config = load(batch / "config.json") if batch and (batch / "config.json").exists() else load(args.config)
    if args.action == "plan":
        print(json.dumps(plan(config), indent=2))
    elif args.action == "prepare":
        from pipeline.reads import prepare
        audit = prepare(config)
        if batch:
            provenance = batch / "provenance"
            provenance.mkdir(parents=True, exist_ok=True)
            save(provenance / "references.json", audit)
            shutil.copy2(ROOT / "pixi.lock", provenance / "pixi.lock")
            for env in ("default", "flye", "raven", "plassembler"):
                result = subprocess.check_output(["pixi", "list", "-e", env, "--json"], cwd=ROOT, text=True)
                (provenance / (env + ".json")).write_text(result)
            sources = [ROOT / "benchmark.py", ROOT / "pixi.toml"] + list((ROOT / "pipeline").glob("*.py"))
            save(provenance / "source.json", {str(p.relative_to(ROOT)): digest(p) for p in sources})
            for source in sources:
                target = provenance / "source" / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        print(f"Audited {len(audit)} reference records")
    elif args.action == "simulate":
        from pipeline.reads import simulate
        result = simulate(find_case(config, args.scenario), batch)
        print(result["status"])
        return 0 if result["status"] == "valid" else 1
    elif args.action == "run":
        from pipeline.execution import run
        result = run(find_case(config, args.scenario), args.tool, batch, config)
        print(result["status"])
        # A scientific fail is completed work; execution/validation errors fail the job.
        return 0 if result["status"] in ("pass", "fail") else 1
    elif args.action == "task":
        tasks = load(batch / "tasks.json")[args.kind]
        if not 0 <= args.index < len(tasks):
            raise ValueError("Array task index is out of range")
        selected = tasks[args.index]
        if args.kind == "simulate":
            return main(["simulate", "--batch", args.batch, "--scenario", selected])
        from pipeline.execution import ENVIRONMENTS
        env = ENVIRONMENTS[selected["tool"]]
        allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", config["threads"]))
        if allocated != config["threads"]:
            raise ValueError("Allocated Slurm CPUs do not match the frozen tool configuration")
        return subprocess.run(["pixi", "run", "--locked", "-e", env, "python", "benchmark.py", "run", "--batch", args.batch,
                               "--scenario", selected["scenario"], "--tool", selected["tool"]], cwd=ROOT).returncode
    elif args.action == "submit":
        from pipeline.cluster import submit
        result = submit(config, load(args.cluster), args.scenario)
        print(json.dumps(result, indent=2))
    elif args.action == "collect":
        from pipeline.cluster import collect
        print(collect(batch))
        from pipeline.report import build
        build(config, batch)
    elif args.action == "report":
        from pipeline.report import build
        print(build(config, batch))
    elif args.action in ("snapshot", "publish"):
        from pipeline.publication import publish
        publish(config, batch, deploy=args.action == "publish")
        print("Saved publication snapshot for " + batch.name)
    elif args.action == "follow":
        from pipeline.follow import follow
        follow(batch, args.interval, args.publish_interval, args.max_hours)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
