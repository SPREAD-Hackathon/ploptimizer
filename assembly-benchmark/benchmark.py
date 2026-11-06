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
    for action in ("prepare", "simulate", "run", "task", "report", "collect", "snapshot", "publish", "follow", "diagnose-submit"):
        sub = commands.add_parser(action)
        sub.add_argument("--batch", required=action not in ("prepare", "report"))
        if action in ("simulate", "run"):
            sub.add_argument("--scenario", required=True)
        if action == "run":
            sub.add_argument("--tool", choices=("flye", "flye-meta", "raven", "plassembler", "miniasm", "miniasm-plus"), required=True)
            sub.add_argument("--threads", type=int)
            sub.add_argument("--repeat", type=int)
            sub.add_argument("--mode", choices=("default", "deterministic"))
        if action == "task":
            sub.add_argument("--kind", choices=("simulate", "assemble"), required=True)
            sub.add_argument("--index", required=True, type=int)
        if action == "diagnose-submit":
            sub.add_argument("--after-job")
            sub.add_argument("--rerun", action="store_true")
            sub.add_argument("--interim", action="store_true", help="Inspect completed outputs now without replacing the final diagnostic job")
        if action == "follow":
            sub.add_argument("--interval", type=int, default=60)
            sub.add_argument("--publish-interval", type=int, default=600)
            sub.add_argument("--max-hours", type=float, default=8)
            sub.add_argument("--also-batch", action="append", default=[])
    sub = commands.add_parser("export", help="Package existing frozen metadata; no assemblies or analyses")
    sub.add_argument("--batch", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--single-batch", action="store_true")
    sub.add_argument("--coordinate-sidecars", action="append", default=[], help="Explicit completed coordinate-sidecar root; metadata ingestion only")
    sub.add_argument("--recorded-artifacts", help="Explicit local run-metadata root for importing already-produced, hash-bound PAF coordinate columns")
    sub.add_argument("--replace", action="store_true", help="Atomically replace an existing validated generated bundle")
    sub = commands.add_parser("render", help="Render a validated results bundle")
    sub.add_argument("--bundle", required=True)
    sub.add_argument("--output", default=str(ROOT / "dist"))
    for action in ("check-site", "deploy-site"):
        sub = commands.add_parser(action, help="Validate a static release" if action == "check-site" else "Deploy only a validated presentation build")
        sub.add_argument("--bundle", required=True)
        sub.add_argument("--output", default=str(ROOT / "dist"))
        sub.add_argument("--report")
    sub = commands.add_parser("submit")
    sub.add_argument("--cluster", default=str(ROOT / "config/cluster.local.json"))
    sub.add_argument("--scenario", help="Limit the submitted profile to one scenario")
    sub.add_argument("--after-job", help="Queue preparation after this numeric Slurm job ID finishes")
    sub.add_argument("--assemble-after-job", help="Generate inputs now but queue assemblies after this Slurm job")
    args = parser.parse_args(argv)
    if args.action in ("export", "render", "check-site", "deploy-site"):
        def scoped(value):
            path = Path(value).resolve()
            if path == ROOT or ROOT not in path.parents:
                raise ValueError("Bundle and render paths must stay inside assembly-benchmark")
            return path
        if args.action == "deploy-site":
            from pipeline.publication import deploy_site
            report = deploy_site(scoped(args.bundle), scoped(args.output))
            print(json.dumps(report, indent=2))
            return 0
        if args.action == "check-site":
            from pipeline.site_gate import check_release
            report = check_release(scoped(args.bundle), scoped(args.output))
            if args.report:
                save(scoped(args.report), report)
            print(json.dumps(report, indent=2))
            return 0 if report["status"] == "pass" else 1
        if args.action == "export":
            from pipeline.bundle import export_bundle
            source = ROOT / "published" / (args.batch + ".json")
            batch_path(args.batch)
            snapshots = [source] if args.single_batch else sorted(p for p in (ROOT / "published").glob("*.json") if p.name != "latest.json")
            cohort = load(ROOT / "config/overview.json")
            if args.single_batch:
                document = load(source)
                cohort = {"schema_version":1,"primary_batches":[args.batch],"families":["S3"] if document["config"].get("determinism") else list(dict.fromkeys(c["category"] for c in document["scenarios"])),"tools":document["config"]["tools"]}
            print(export_bundle(snapshots, scoped(args.output), primary_batch=args.batch, cohort=cohort, replace=args.replace, artifact_root=scoped(args.recorded_artifacts) if args.recorded_artifacts else None, coordinate_roots=[scoped(path) for path in args.coordinate_sidecars], performance_source=(ROOT / "performance/snapshot.json") if (ROOT / "performance/snapshot.json").is_file() and not args.single_batch else None))
        else:
            from pipeline.bundle_render import render_bundle
            print(render_bundle(scoped(args.bundle), scoped(args.output)))
        return 0
    batch = batch_path(args.batch) if getattr(args, "batch", None) else None
    config = load(batch / "config.json") if batch and (batch / "config.json").exists() else load(args.config)
    if config.get("status") == "proposed":
        raise ValueError("This profile is a design proposal and cannot run; see REALISTIC_READS.md for admission criteria")
    if args.action == "plan":
        cases = plan(config)
        if config.get("determinism"):
            from pipeline.determinism import repeat_settings
            selected = repeat_settings(config)["scenarios"]
            cases = [case for case in cases if case["id"] in selected]
        print(json.dumps(cases, indent=2))
    elif args.action == "prepare":
        from pipeline.reads import prepare
        audit = prepare(config)
        if batch:
            provenance = batch / "provenance"
            provenance.mkdir(parents=True, exist_ok=True)
            save(provenance / "references.json", audit)
            shutil.copy2(ROOT / "pixi.lock", provenance / "pixi.lock")
            from pipeline.execution import ENVIRONMENTS
            environments = list(dict.fromkeys(['default'] + [ENVIRONMENTS[t] for t in config['tools']] + (['simulator'] if config.get('noisy_panel') else [])))
            for env in environments:
                result = subprocess.check_output(["pixi", "list", "-e", env, "--json"], cwd=ROOT, text=True)
                (provenance / (env + ".json")).write_text(result)
            sources = [ROOT / "benchmark.py", ROOT / "pixi.toml"] + list((ROOT / "pipeline").glob("*.py"))
            save(provenance / "source.json", {str(p.relative_to(ROOT)): digest(p) for p in sources})
            for source in sources:
                target = provenance / "source" / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        if config.get("noisy_panel"):
            if not batch:
                raise ValueError("Noisy preparation requires a frozen batch")
            subprocess.run(["pixi", "run", "--locked", "-e", "simulator", "python", "-m", "pipeline.noisy_workflow", "freeze", "--batch", batch.name], cwd=ROOT, check=True)
        print(f"Audited {len(audit)} reference records")
    elif args.action == "simulate":
        from pipeline.reads import simulate
        result = simulate(find_case(config, args.scenario), batch)
        print(result["status"])
        return 0 if result["status"] == "valid" else 1
    elif args.action == "run":
        from pipeline.execution import run
        result = run(find_case(config, args.scenario), args.tool, batch, config, args.threads, args.repeat, args.mode)
        print(result["status"])
        # A scientific fail is completed work; execution/validation errors fail the job.
        return 0 if result["status"] in ("pass", "fail") else 1
    elif args.action == "task":
        tasks = load(batch / "tasks.json")[args.kind]
        if not 0 <= args.index < len(tasks):
            raise ValueError("Array task index is out of range")
        selected = tasks[args.index]
        if args.kind == "simulate":
            if find_case(config, selected)["simulation"]["model"] == "matched-error-v1":
                return subprocess.run(["pixi", "run", "--locked", "-e", "simulator", "python", "benchmark.py", "simulate", "--batch", args.batch, "--scenario", selected], cwd=ROOT).returncode
            return main(["simulate", "--batch", args.batch, "--scenario", selected])
        from pipeline.execution import ENVIRONMENTS
        env = ENVIRONMENTS[selected["tool"]]
        allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", config["threads"]))
        requested = selected.get("threads", config["threads"])
        if allocated != config["threads"] or requested > allocated:
            raise ValueError("Allocated Slurm CPUs do not match the frozen reservation")
        extra = ["--threads", str(requested), "--repeat", str(selected["repeat"])] if "repeat" in selected else []
        if "mode" in selected:
            extra += ["--mode", selected["mode"]]
        return subprocess.run(["pixi", "run", "--locked", "-e", env, "python", "benchmark.py", "run", "--batch", args.batch,
                               "--scenario", selected["scenario"], "--tool", selected["tool"]] + extra, cwd=ROOT).returncode
    elif args.action == "submit":
        from pipeline.cluster import submit
        result = submit(config, load(args.cluster), args.scenario, args.after_job, args.assemble_after_job)
        print(json.dumps(result, indent=2))
    elif args.action == "diagnose-submit":
        from pipeline.cluster import submit_diagnostics
        print(json.dumps(submit_diagnostics(batch, args.after_job, args.rerun, args.interim), indent=2))
    elif args.action == "collect":
        from pipeline.cluster import collect
        print(collect(batch))
        from pipeline.report import build
        build(config, batch)
    elif args.action == "report":
        from pipeline.report import build
        print(build(config, batch, include_history=config.get("report_scope") != "single_batch"))
    elif args.action in ("snapshot", "publish"):
        from pipeline.publication import publish
        publish(config, batch, deploy=args.action == "publish")
        print("Saved publication snapshot for " + batch.name)
    elif args.action == "follow":
        from pipeline.follow import follow
        follow(batch, args.interval, args.publish_interval, args.max_hours, [batch_path(value) for value in args.also_batch])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
