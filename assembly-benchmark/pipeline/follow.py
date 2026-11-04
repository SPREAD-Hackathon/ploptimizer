"""A bounded, batch-specific results collector and static-site publisher."""

import collections
import os
import time

from .cluster import collect
from .common import ROOT, fingerprint, load, save
from .publication import publish
from .report import build


TERMINAL = {"pass", "fail", "error", "timeout", "invalid_input"}


def selected_rows(document, tasks):
    selected = {(task["scenario"], task["tool"]) for task in tasks}
    return [row for row in document["results"] if (row["scenario_id"], row["tool"]) in selected]


def progress_fingerprint(document):
    return fingerprint({"results": document["results"], "inputs": document.get("inputs", {})})


def follow(batch, interval=60, publish_interval=600, max_hours=8):
    if interval < 15 or publish_interval < interval or max_hours <= 0:
        raise ValueError("Use interval >=15 seconds, publish interval >= interval, and a positive time limit")
    config = load(batch / "config.json")
    tasks = load(batch / "tasks.json")["assemble"]
    current = ROOT / "published/latest.json"
    previous = load(current) if current.exists() else None
    published_signature = progress_fingerprint(previous) if previous and previous["batch"] == batch.name else None
    last_publication = time.monotonic() if published_signature else 0
    deadline = time.monotonic() + max_hours * 3600
    last_counts = None
    while time.monotonic() < deadline:
        try:
            collect(batch)
            build(config, batch)
            document = load(ROOT / "dist/data/results.json")
            rows = selected_rows(document, tasks)
            completed = len(rows) == len(tasks) and all(row["status"] in TERMINAL for row in rows)
            counts = dict(collections.Counter(row["status"] for row in rows))
            signature = progress_fingerprint(document)
            should_publish = signature != published_signature and (completed or time.monotonic() - last_publication >= publish_interval)
            if should_publish:
                publish(config, batch, deploy=True)
                published_signature = signature
                last_publication = time.monotonic()
            save(batch / "follow.json", {"status": "complete" if completed else "following", "counts": counts,
                 "published_signature": published_signature, "batch_id": batch.name,
                 "updated_at_unix": time.time(), "pid": os.getpid()})
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
