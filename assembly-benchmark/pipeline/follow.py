"""Collect related batches serially and publish one consistent static site."""

import collections
import os
import time

from .cluster import collect
from .common import ROOT, fingerprint, load, save
from .publication import publish
from .report import build


TERMINAL = {"pass", "fail", "error", "timeout", "invalid_input"}


def selected_rows(document, tasks):
    rows = document.get("determinism", {}).get("executions", document["results"])
    return [row for row in rows if any(
        row["scenario_id"] == task["scenario"] and row["tool"] == task["tool"]
        and all(row.get(key) == task[key] for key in ("run_id", "threads", "repeat") if key in task)
        for task in tasks)]


def progress_fingerprint(document):
    return fingerprint({"results": document["results"], "inputs": document.get("inputs", {}),
                        "determinism": document.get("determinism")})


def follow(batch, interval=60, publish_interval=600, max_hours=8, companion_batches=None):
    if interval < 15 or publish_interval < interval or max_hours <= 0:
        raise ValueError("Use interval >=15 seconds, publish interval >= interval, and a positive time limit")
    config = load(batch / "config.json")
    batches = list(dict.fromkeys([batch, *(companion_batches or [])]))
    task_sets = {item.name: load(item / "tasks.json")["assemble"] for item in batches}
    # A saved snapshot is not evidence that its deployment succeeded.
    published_signature = None
    last_publication = 0
    deadline = time.monotonic() + max_hours * 3600
    last_counts = None
    while time.monotonic() < deadline:
        try:
            documents = {}
            for item in batches:
                collect(item)
                if item != batch:
                    documents[item.name] = publish(load(item / "config.json"), item, make_latest=False)
            build(config, batch)
            documents[batch.name] = load(ROOT / "dist/data/results.json")
            counts = {}
            completed = True
            for item in batches:
                tasks = task_sets[item.name]
                rows = selected_rows(documents[item.name], tasks)
                completed = completed and len(rows) == len(tasks) and all(row["status"] in TERMINAL for row in rows)
                counts[item.name] = dict(collections.Counter(row["status"] for row in rows))
            diagnostic_jobs = {item.name: diagnostic_state(item) for item in batches}
            completed = completed and all(state is None or state.startswith(("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL", "DEADLINE", "PREEMPTED", "DEPENDENCY")) for state in diagnostic_jobs.values())
            signature = fingerprint({key: progress_fingerprint(value) for key, value in documents.items()}) if len(batches) > 1 else progress_fingerprint(documents[batch.name])
            should_publish = signature != published_signature and (published_signature is None or completed or time.monotonic() - last_publication >= publish_interval)
            if should_publish:
                publish(config, batch, deploy=True)
                published_signature = signature
                last_publication = time.monotonic()
            save(batch / "follow.json", {"status": "complete" if completed else "following", "counts": counts,
                 "published_signature": published_signature, "batch_id": batch.name,
                 "updated_at_unix": time.time(), "pid": os.getpid(), "diagnostic_jobs": diagnostic_jobs})
            if counts != last_counts:
                print(f"{batch.name}: {counts}", flush=True)
                last_counts = counts
            if completed:
                return
        except Exception as error:
            save(batch / "follow.json", {"status": "retrying", "batch_id": batch.name,
                 "error": f"{type(error).__name__}: {error}", "updated_at_unix": time.time()})
            print(f"Collector will retry: {type(error).__name__}: {error}", flush=True)
        time.sleep(interval)
    save(batch / "follow.json", {"status": "stopped_at_time_limit", "batch_id": batch.name, "updated_at_unix": time.time()})


def diagnostic_state(batch):
    path = batch / "diagnostic_submission.json"
    if not path.exists():
        return None
    job_id = load(path)["job_id"]
    accounting = batch / "accounting.tsv"
    if accounting.exists():
        for line in accounting.read_text().splitlines():
            fields = line.split("|")
            if len(fields) > 1 and fields[0] == job_id:
                return fields[1]
    return "PENDING"
