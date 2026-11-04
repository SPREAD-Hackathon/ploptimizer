"""Batch coordination checks with local fixtures and mocked collection/rendering."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import load, save
from pipeline.follow import follow, selected_rows


class StopAfterCycle(Exception):
    pass


def repeat_task(number, threads=1):
    return {"scenario": "s1-w-prk2", "tool": "flye", "threads": threads,
            "repeat": number, "run_id": f"threads-{threads}-repeat-{number}"}


def repeat_row(number, status, threads=1):
    task = repeat_task(number, threads)
    return {**task, "scenario_id": task["scenario"], "status": status}


class FollowBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.primary = self.root / "runs/primary"
        self.companion = self.root / "runs/repeats"
        save(self.primary / "config.json", {"profile_id": "baseline"})
        save(self.primary / "tasks.json", {"assemble": [{"scenario": "base", "tool": "flye"}]})
        save(self.companion / "config.json", {"profile_id": "repeat-profile"})
        save(self.companion / "tasks.json", {"assemble": [repeat_task(1), repeat_task(2)]})
        self.primary_document = {"batch": "primary", "results": [{"scenario_id": "base", "tool": "flye", "status": "pass"}]}

    def run_cycle(self, executions):
        events = []
        companion = {"batch": "repeats", "results": executions, "determinism": {"executions": executions}}

        def collect(batch):
            events.append(("collect", batch.name))

        def render(config, batch):
            events.append(("build", batch.name))
            save(self.root / "dist/data/results.json", self.primary_document)

        def publish(config, batch, **kwargs):
            events.append(("publish", batch.name, kwargs))
            return companion if batch == self.companion else self.primary_document

        with patch("pipeline.follow.ROOT", self.root), \
             patch("pipeline.follow.collect", side_effect=collect), \
             patch("pipeline.follow.build", side_effect=render), \
             patch("pipeline.follow.publish", side_effect=publish), \
             patch("pipeline.follow.time.monotonic", return_value=1000), \
             patch("pipeline.follow.time.sleep", side_effect=StopAfterCycle):
            try:
                follow(self.primary, companion_batches=[self.companion, self.companion])
            except StopAfterCycle:
                pass
        return load(self.primary / "follow.json"), events

    def test_companions_are_snapshotted_once_before_primary_deployment(self):
        checkpoint, events = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "running")])
        self.assertEqual(events, [("collect", "primary"), ("collect", "repeats"),
                                 ("publish", "repeats", {"make_latest": False}),
                                 ("build", "primary"), ("publish", "primary", {"deploy": True})])
        self.assertEqual(checkpoint["status"], "following")

    def test_completion_waits_for_every_repeat_even_when_primary_has_finished(self):
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "running")])
        self.assertEqual(checkpoint["status"], "following")
        self.assertEqual(checkpoint["counts"]["repeats"], {"pass": 1, "running": 1})

    def test_terminal_repeat_errors_finish_collection_without_claiming_pass(self):
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "error")])
        self.assertEqual(checkpoint["status"], "complete")
        self.assertEqual(checkpoint["counts"]["repeats"], {"pass": 1, "error": 1})

    def test_repeat_evidence_takes_precedence_over_aggregate_result(self):
        running = repeat_row(2, "running")
        document = {"results": [{"scenario_id": "s1-w-prk2", "tool": "flye", "status": "pass"}],
                    "determinism": {"executions": [repeat_row(1, "pass"), running]}}
        self.assertEqual(selected_rows(document, [repeat_task(2)]), [running])

    def test_missing_repeat_keeps_finished_primary_following(self):
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass")])
        self.assertEqual(checkpoint["status"], "following")
        self.assertEqual(checkpoint["counts"]["repeats"], {"pass": 1})

    def test_completion_waits_for_supplementary_diagnostic_job(self):
        save(self.primary / "diagnostic_submission.json", {"job_id": "123"})
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "error")])
        self.assertEqual(checkpoint["status"], "following")
        (self.primary / "accounting.tsv").write_text("123|COMPLETED|0:0|\n")
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "error")])
        self.assertEqual(checkpoint["status"], "complete")
        self.assertEqual(checkpoint["diagnostic_jobs"]["primary"], "COMPLETED")

    def test_completion_waits_for_tolerant_assessment_stage(self):
        save(self.primary / "submission.json", {"jobs":{"assessment":"124"}})
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "error")])
        self.assertEqual(checkpoint["status"], "following")
        (self.primary / "accounting.tsv").write_text("124|COMPLETED|0:0|\n")
        checkpoint, _ = self.run_cycle([repeat_row(1, "pass"), repeat_row(2, "error")])
        self.assertEqual(checkpoint["status"], "complete")
        self.assertEqual(checkpoint["assessment_jobs"]["primary"], "COMPLETED")

    def test_repeat_selection_uses_run_identity_threads_and_repeat(self):
        wanted = repeat_row(1, "pass")
        document = {"results": [wanted, repeat_row(2, "running"), repeat_row(1, "pass", threads=4)]}
        self.assertEqual(selected_rows(document, [repeat_task(1)]), [wanted])
        for field, value in (("run_id", "wrong-run"), ("repeat", 99), ("threads", 8)):
            task = {**repeat_task(1), field: value}
            self.assertEqual(selected_rows(document, [task]), [])


if __name__ == "__main__":
    unittest.main()
