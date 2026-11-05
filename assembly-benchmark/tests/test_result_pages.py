"""Generic graph fixtures exercise result URLs, provenance and honest missing data."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import ROOT, digest, load, save, write_fasta
from pipeline.graph_artifacts import build_graph_artifacts
from pipeline.result_pages import contig_section, enrich_graph_artifacts, graph_artifact, result_href, result_slug, write_result_pages


class ResultPageTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root / "runs/synthetic-fixture"
        self.case = {"id": "generic-fixture", "title": "Generic synthetic GFA fixture; not a benchmark observation", "replicons": []}
        self.record = {"scenario_id": self.case["id"], "tool": "flye", "status": "fail", "threads": 1,
                       "explanation": {"summary": "Synthetic presentation fixture", "symptom": "Synthetic presentation fixture", "confidence": "unresolved", "evidence": [], "interpretation": "No benchmark conclusion is supplied by this fixture."},
                       "evaluation": {"status": "fail", "endpoint": "Synthetic endpoint fixture", "contig_count": 2, "replicons": [], "unclassified_contigs": ["a", "b"]}}
        self.document = {"batch": self.batch.name, "config": {"tools": ["flye"]}, "scenarios": [self.case], "results": [self.record]}
        self.output = self.root / "site"

    def make_sidecar(self):
        directory = self.batch / "results" / self.case["id"] / self.record["tool"]
        directory.mkdir(parents=True)
        assembly = directory / "assembly.fa"
        write_fasta(assembly, {"a": "AACCTTGG", "b": "ACGTACGTACGT"})
        self.record["assembly_sha256"] = digest(assembly)
        execution = directory / "execution.json"
        save(execution, self.record)
        gfa = directory / "synthetic.gfa"
        gfa.write_text("H\tVN:Z:1.0\nS\ta\tAACCTTGG\tdp:f:12\nS\tb\t*\tLN:i:12\nL\ta\t+\tb\t-\t0M\nL\ta\t+\ta\t+\t0M\nP\tsynthetic-path\ta+,b-\t0M\n")
        info = directory / "synthetic-assembly-info.txt"
        info.write_text("#seq_name\tlength\tcov.\tcirc.\n" + "a\t8\t12\tY\n" + "b\t12\t6\tN\n")
        artifact = build_graph_artifacts(execution, assembly, gfa, info, source_role="synthetic_fixture")
        save(directory / "graph_artifacts.json", artifact)
        return execution, artifact

    def test_stable_urls_distinguish_thread_repeats_and_reject_path_injection(self):
        a = {**self.record, "run_id": "threads-1-repeat-1"}
        b = {**self.record, "run_id": "threads-4-repeat-1"}
        self.assertNotEqual(result_href(a), result_href(b))
        self.assertEqual(result_href(a, "../"), "../results/generic-fixture--flye--threads-1-repeat-1.html")
        for key in ("scenario_id", "tool", "run_id"):
            with self.assertRaises(ValueError):
                result_slug({**self.record, key: "../outside"})

    def test_missing_graph_and_circularity_are_unknown_not_manufactured(self):
        write_result_pages(self.document, self.output)
        html = (self.output / result_href(self.record)).read_text()
        self.assertNotIn("Exact endpoint:", html)
        self.assertIn("Run details, command and provenance</summary>", html)
        self.assertNotIn('<details class="command-used">', html)
        self.assertIn('data-exact-status="fail"', html)
        self.assertIn("Graph unavailable", html)
        self.assertIn("Circularity is <strong>unknown</strong>", html)
        self.assertIn("not labelled linear", html)
        self.assertIn("partial name inventory", html)
        metadata = load(self.output / "data/results" / (result_slug(self.record) + "-graph.json"))
        self.assertEqual(metadata["status"], "not_collected")
        self.assertNotIn("nodes", metadata)
        self.assertNotIn("reported_circularity", metadata)
        self.assertIn("data-assembly-graph", html)

    def test_tool_claims_keep_source_role_and_n_is_not_reported_circular(self):
        _, artifact = self.make_sidecar()
        html = contig_section(self.record, artifact)
        self.assertIn("synthetic-assembly-info.txt", html)
        self.assertIn("synthetic_fixture", html)
        self.assertIn("Reported circular (source value: Y)", html)
        self.assertIn("Not reported circular (source value: N)", html)
        self.assertNotIn("Reported linear", html)
        self.assertIn("not physical validation", html)
        self.assertIn("intermediate contigs are not automatically final outputs", html)

    def test_checked_runtime_sidecar_survives_archive_rebuild_without_source_files(self):
        execution, artifact = self.make_sidecar()
        before = copy.deepcopy(self.document)
        execution_hash = digest(execution)
        enriched = enrich_graph_artifacts(self.document, self.batch)
        self.assertEqual(self.document, before)
        self.assertEqual(enriched["results"][0]["graph_artifacts"]["graph"]["status"], "available")
        self.assertEqual(digest(execution), execution_hash)
        save(self.root / "published.json", enriched)
        archived = load(self.root / "published.json")
        with patch("pipeline.graph_artifacts.attach_graph_artifacts", side_effect=AssertionError("Archive must not query local files")):
            roundtrip = enrich_graph_artifacts(archived)
            write_result_pages(roundtrip, self.output)
        self.assertEqual(roundtrip, archived)
        saved = load(self.output / "data/results" / (result_slug(self.record) + "-graph.json"))
        self.assertEqual(saved, enriched["results"][0]["graph_artifacts"])
        self.assertEqual(saved["graph"], artifact["graph"])
        self.assertEqual(saved["graph"]["self_loop_segment_ids"], ["a"])
        self.assertNotIn("AACCTTGG", str(saved))
        html = (self.output / result_href(self.record)).read_text()
        self.assertIn("2 GFA segments · 2 link records", html)
        self.assertIn("source value: Y", html)

    def test_mismatched_embedded_assembly_hash_hides_graph_and_circle_claims(self):
        _, artifact = self.make_sidecar()
        record = {**self.record, "assembly_sha256": "b" * 64, "graph_artifacts": artifact}
        result = graph_artifact(record)
        self.assertEqual(result["status"], "not_collected")
        self.assertIn("do not match", result["reason"])
        self.assertNotIn("assembly_info", result)

    def test_inert_graph_payload_escapes_script_terminators(self):
        self.record["graph_artifacts"] = {"status": "available", "graph": {"status": "available", "nodes": [{"id": "</script><script>alert(1)</script>", "length_bp": 4}], "edges": [], "paths": [], "source": {"filename": "synthetic.gfa", "role": "synthetic_fixture"}}}
        write_result_pages(self.document, self.output)
        html = (self.output / result_href(self.record)).read_text()
        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertIn("\\u003c/script\\u003e", html)
        saved = load(self.output / "data/results" / (result_slug(self.record) + "-graph.json"))
        self.assertEqual(saved["graph"]["nodes"][0]["id"], "</script><script>alert(1)</script>")

    def test_repeat_documents_keep_graph_metadata_in_both_execution_lists(self):
        _, artifact = self.make_sidecar()
        row = {**self.record, "run_id": "threads-1-repeat-1", "graph_artifacts": artifact}
        document = {**self.document, "results": [row], "determinism": {"executions": [copy.deepcopy(row)]}}
        enriched = enrich_graph_artifacts(document)
        self.assertEqual(enriched["results"], enriched["determinism"]["executions"])
        self.assertEqual(enriched["results"][0]["graph_artifacts"], artifact)
        write_result_pages(enriched, self.output)
        self.assertTrue((self.output / result_href(row)).exists())

    def test_rebuild_removes_stale_result_pages_and_downloads(self):
        write_result_pages(self.document, self.output)
        (self.output / "results/obsolete.html").write_text("stale")
        (self.output / "data/results/obsolete.json").write_text("{}")
        write_result_pages(self.document, self.output)
        self.assertFalse((self.output / "results/obsolete.html").exists())
        self.assertFalse((self.output / "data/results/obsolete.json").exists())

    def test_large_inventory_is_closed_so_graph_is_not_buried(self):
        _, artifact = self.make_sidecar()
        row = artifact["assembly_info"]["contigs"][0]
        artifact["assembly_info"]["contigs"] = [{**row, "id": f"contig_{i}"} for i in range(21)]
        html = contig_section(self.record, artifact)
        self.assertIn('<details><summary>Show all 21 reported contigs</summary>', html)
        self.assertNotIn('<details open', html)

    def test_unreadable_circle_report_keeps_source_and_reason_visible(self):
        artifact = {"assembly_info": {"status": "unsupported", "reason": "Missing header", "source": {"filename": "empty-summary.tsv", "file_sha256": "a" * 64, "role": "final"}}}
        html = contig_section(self.record, artifact)
        self.assertIn("empty-summary.tsv", html)
        self.assertIn("Missing header", html)
        self.assertIn("Circularity is <strong>unknown</strong>", html)


if __name__ == "__main__":
    unittest.main()
