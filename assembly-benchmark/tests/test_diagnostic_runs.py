"""Verify retrospective provenance and supplementary mapper isolation."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pipeline import diagnostic_runs as runner
from pipeline.common import digest, fingerprint, load, save


class DiagnosticRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pipeline").mkdir()
        shutil.copy2(Path(runner.__file__).with_name("diagnostics.py"), self.root / "pipeline/diagnostics.py")
        self.patch_root = patch.object(runner, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        self.batch = self.root / "runs/example"
        self.input = self.batch / "cases/s1-example"
        self.input.mkdir(parents=True)
        self.directory = self.batch / "results/s1-example/flye/repeats/t1-r1"
        self.directory.mkdir(parents=True)
        self.assembly = self.directory / "assembly.fasta"
        self.assembly.write_text(">contig\n" + "A" * 600 + "\n")
        (self.input / "truth.fasta").write_text(">p\n" + "A" * 600 + "\n")
        (self.input / "reads.fastq.gz").write_bytes(b"frozen-reads")
        config = {"profile_id": "test", "threads": 1}
        save(self.batch / "config.json", config)
        case = {"id": "s1-example", "replicons": [{"refseq_accession": "p", "replicon_name": "p",
                "length_bp": 600, "molecule_type": "plasmid", "topology": "circular"}]}
        case["fingerprint"] = fingerprint(case)
        hashes = {"reads_sha256": digest(self.input / "reads.fastq.gz"), "truth_sha256": digest(self.input / "truth.fasta")}
        save(self.input / "input.json", {"case": case, "status": "valid", **hashes})
        self.execution = self.directory / "execution.json"
        save(self.execution, {"batch_id": "example", "scenario_id": "s1-example", "scenario_fingerprint": case["fingerprint"],
                              "tool": "flye", "status": "fail", "config_fingerprint": fingerprint(config),
                              "assembly_file": str(self.assembly.relative_to(self.batch)), "assembly_sha256": digest(self.assembly), **hashes})
        self.version = patch.object(runner.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="2.28-r1209\n", stderr=""))
        self.version_mock = self.version.start()
        self.addCleanup(self.version.stop)
        self.mapper = patch.object(runner, "run_mapper", side_effect=self.write_paf)
        self.mapper_mock = self.mapper.start()
        self.addCleanup(self.mapper.stop)

    def write_paf(self, command, stdout, stderr, timeout):
        stdout.write("contig\t600\t0\t600\t+\tp\t600\t0\t600\t600\t600\t60\ttp:A:P\tcg:Z:600M\n")
        stderr.write("mapper log\n")
        return 0

    def update_record(self, **values):
        record = load(self.execution)
        record.update(values)
        save(self.execution, record)

    def test_success_records_evidence_without_mutating_execution(self):
        original = self.execution.read_bytes()
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["evidence"]["replicons"][0]["recovered_fraction"], 1)
        self.assertEqual(result["strict_status"], "fail")
        self.assertTrue(result["input_hashes"]["reads_sha256_execution_hash_available"])
        self.assertEqual(self.execution.read_bytes(), original)
        self.assertEqual(result["command"][:5], ["pixi", "run", "--locked", "-e", "plassembler"])

    def test_recursive_batch_and_cache_reuse(self):
        self.assertEqual(runner.run_batch(self.batch), {"complete": 1})
        original = (self.directory / "diagnostics.json").read_bytes()
        self.assertEqual(runner.run_batch(self.batch), {"complete": 1})
        self.assertEqual(self.mapper_mock.call_count, 1)
        self.assertEqual((self.directory / "diagnostics.json").read_bytes(), original)
        (self.directory / "alignment.paf").write_text("tampered")
        self.assertEqual(runner.run_batch(self.batch), {"complete": 1})
        self.assertEqual(self.mapper_mock.call_count, 2)

    def test_old_execution_hash_absence_is_explicit_and_manifest_still_checked(self):
        record = load(self.execution)
        for key in ("reads_sha256", "truth_sha256"):
            del record[key]
        save(self.execution, record)
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["input_hashes"]["reads_sha256_execution_hash_available"])
        self.assertFalse(result["input_hashes"]["truth_sha256_execution_hash_available"])
        (self.input / "reads.fastq.gz").write_bytes(b"changed")
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertIn("checksum mismatch", result["error"])

    def test_old_execution_missing_batch_id_is_explicit_but_wrong_id_fails(self):
        record = load(self.execution)
        del record["batch_id"]
        save(self.execution, record)
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["input_hashes"]["batch_id_execution_available"])
        self.update_record(batch_id="another-batch")
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertIn("different batch", result["error"])
        self.assertEqual(self.mapper_mock.call_count, 1)

    def test_present_but_wrong_execution_input_hash_must_fail(self):
        self.update_record(truth_sha256="incorrect")
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.mapper_mock.assert_not_called()

    def test_missing_or_changed_assembly_is_independent_error(self):
        self.assembly.unlink()
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertEqual(load(self.execution)["status"], "fail")
        self.mapper_mock.assert_not_called()

    def test_mapper_failure_is_not_zero_recovery(self):
        self.mapper_mock.return_value = 3
        self.mapper_mock.side_effect = None
        with patch.object(runner, "summarise_paf") as parser:
            result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_code"], 3)
        self.assertNotIn("evidence", result)
        parser.assert_not_called()

    def test_empty_assembly_is_valid_no_supported_alignment(self):
        self.assembly.write_text("")
        self.update_record(assembly_sha256=digest(self.assembly))
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["mapper_invoked"])
        self.assertEqual(result["evidence"]["replicons"][0]["recovered_fraction"], 0)
        self.mapper_mock.assert_not_called()

    def test_nonterminal_execution_is_skipped_and_malformed_record_is_error(self):
        self.update_record(status="running")
        self.assertEqual(runner.diagnose_execution(self.batch, self.execution)["status"], "skipped")
        self.execution.write_text("not JSON")
        self.assertEqual(runner.diagnose_execution(self.batch, self.execution)["status"], "error")
        self.mapper_mock.assert_not_called()

    def test_path_traversal_and_symlink_escape_are_rejected(self):
        with self.assertRaises(ValueError):
            runner.batch_directory("../../example")
        self.update_record(assembly_file="../outside.fa")
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertIn("escapes", result["error"])
        self.mapper_mock.assert_not_called()

    def test_timeout_is_recorded_independently(self):
        self.mapper_mock.side_effect = subprocess.TimeoutExpired("minimap2", 1)
        result = runner.diagnose_execution(self.batch, self.execution)
        self.assertEqual(result["status"], "error")
        self.assertIn("TimeoutExpired", result["error"])
        self.assertNotIn("evidence", result)


if __name__ == "__main__":
    unittest.main()
