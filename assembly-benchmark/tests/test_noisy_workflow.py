"""S6 orchestration integration without local Badread, NumPy or model assets."""

import copy
import gzip
import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.assessments import attach_assessment
from pipeline.cases import plan
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.noisy_workflow import simulate_noise
from pipeline.reads import simulate


class MockBadreadBackend:
    calls = []

    def __init__(self, profile):
        self.profile = profile["id"]

    def generate(self, fragment, target, seed):
        type(self).calls.append((self.profile, target, seed))
        emitted = list(fragment)
        for index in (0, 50):
            emitted[index] = "A" if emitted[index] != "A" else "C"
        emitted = ''.join(emitted)
        return emitted, "I" * len(emitted), .98, .98

    def align(self, emitted, fragment):
        operations = ''.join("=" if left == right else "X" for left, right in zip(emitted, fragment))
        cigar = ''.join(str(len(match.group())) + match.group()[0] for match in re.finditer(r"=+|X+", operations))
        return {"cigar": cigar, "editDistance": operations.count("X")}


class NoisyWorkflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root / "runs/noisy-fixture"
        self.config = load(ROOT / "config/noisy-smoke.json")
        self.config["simulation"].update(length_mean=100, length_sd=0, length_min=100, length_max=100)
        self.cases = plan(self.config)
        rng = random.Random(97)
        self.sequences = {}
        for case in self.cases:
            for replicon in case["replicons"]:
                replicon["length_bp"] = 401 if replicon["molecule_type"] == "chromosome" else 100
                self.sequences.setdefault(replicon["refseq_accession"], ''.join(rng.choice("ACGT") for _ in range(replicon["length_bp"])))
            case["fingerprint"] = fingerprint({key: value for key, value in case.items() if key != "fingerprint"})
        self.runtime = {"sha256": "a" * 64, "runtime": {"fixture_backend": True}}
        save(self.batch / "provenance/noisy-runtime.json", {"profiles": {
            profile["id"]: self.runtime for profile in self.config["noisy_panel"]["profiles"] if profile["id"] != "matched-exact"}})
        for item in (patch("pipeline.noisy_reads.ROOT", self.root),
                     patch("pipeline.noisy_reads.inspect_runtime", return_value=self.runtime),
                     patch("pipeline.noisy_reads.BadreadBackend", MockBadreadBackend)):
            item.start()
            self.addCleanup(item.stop)
        MockBadreadBackend.calls = []

    def run_case(self, case, suffix=""):
        directory = self.batch / "cases" / (case["id"] + suffix)
        return simulate_noise(case, self.sequences, self.batch, directory), directory

    def test_smoke_plan_is_three_cases_twelve_comparisons_and_preserves_config(self):
        config = load(ROOT / "config/noisy-smoke.json")
        before = copy.deepcopy(config)
        cases = plan(config)
        self.assertEqual(config, before)
        self.assertEqual(len(cases), 3)
        self.assertEqual(len(cases) * len(config["tools"]), 12)
        self.assertEqual({case["category"] for case in cases}, {"S6"})
        self.assertEqual({case["error_profile"]["id"] for case in cases}, {"matched-exact", "generic-stress", "ont2023-shaped"})
        self.assertEqual(len({case["fingerprint"] for case in cases}), 3)
        baseline = load(ROOT / "config/next-stages.json")
        expected = plan(baseline)
        baseline["noisy_panel"] = config["noisy_panel"]
        expanded = plan(baseline)
        self.assertEqual([case for case in expanded if case["category"] in ("S1", "S2")], expected)
        self.assertEqual(len(expected), 32)

    def test_profiles_share_canonical_clean_fingerprints_and_source_hashes(self):
        original_cases = copy.deepcopy(self.cases)
        original_config = copy.deepcopy(self.config)
        manifests, directories = zip(*(self.run_case(case) for case in self.cases))
        self.assertEqual(self.cases, original_cases)
        self.assertEqual(self.config, original_config)
        for manifest in manifests:
            self.assertEqual(manifest["status"], "valid")
        for field in ("source_fragments_sha256", "source_origins_sha256", "source_truth_sha256"):
            self.assertEqual(len({manifest[field] for manifest in manifests}), 1, field)
        clean = [load(directory / "clean/input.json") for directory in directories]
        self.assertEqual(len({manifest["case"]["fingerprint"] for manifest in clean}), 1)
        for manifest in clean:
            case = manifest["case"]
            self.assertNotIn("error_profile", case)
            self.assertEqual(case["fingerprint"], fingerprint({key: value for key, value in case.items() if key != "fingerprint"}))
        for filename in ("reads.fastq.gz", "read_origins.tsv.gz", "truth.fasta"):
            self.assertEqual(len({digest(directory / "clean" / filename) for directory in directories}), 1, filename)
        self.assertEqual(manifests[0]["reads_sha256"], manifests[0]["source_fragments_sha256"])
        self.assertNotEqual(manifests[1]["reads_sha256"], manifests[1]["source_fragments_sha256"])
        with gzip.open(directories[1] / "read_origins.tsv.gz", "rt") as emitted, gzip.open(directories[1] / "clean/read_origins.tsv.gz", "rt") as source:
            self.assertEqual(emitted.read(), source.read())
        self.assertEqual(manifests[1]["truth_sha256"], manifests[1]["source_truth_sha256"])
        calls = {profile: [(target, seed) for name, target, seed in MockBadreadBackend.calls if name == profile] for profile in ("generic-stress", "ont2023-shaped")}
        self.assertEqual([target for target, _ in calls["generic-stress"]], [target for target, _ in calls["ont2023-shaped"]])
        self.assertNotEqual([seed for _, seed in calls["generic-stress"]], [seed for _, seed in calls["ont2023-shaped"]])

    def test_cached_inputs_validate_each_clean_artifact_before_reuse(self):
        case = self.cases[0]
        _, directory = self.run_case(case)
        for filename in ("reads.fastq.gz", "read_origins.tsv.gz", "truth.fasta"):
            path = directory / "clean" / filename
            original = path.read_bytes()
            path.write_bytes(original + b"tamper")
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "Cached clean source fragments changed"):
                simulate(case, self.batch)
            path.write_bytes(original)
        with patch("pipeline.noisy_workflow.simulate_noise", side_effect=AssertionError("Cache must not resimulate")):
            cached = simulate(case, self.batch)
        self.assertEqual(cached["case"]["fingerprint"], case["fingerprint"])

    def test_cached_clean_manifest_provenance_tamper_is_rejected(self):
        case = self.cases[0]
        _, directory = self.run_case(case)
        path = directory / "clean/input.json"
        manifest = load(path)
        manifest["case"]["profile_id"] = "tampered-source-profile"
        save(path, manifest)
        with self.assertRaises(ValueError):
            simulate(case, self.batch)

    def test_tolerant_attachment_requires_both_hashes_and_preserves_strict_status(self):
        path = self.batch / "results/fixture/flye/execution.json"
        record = {"status": "fail", "assembly_sha256": "assembly-hash", "evaluation": {"status": "fail"}}
        save(path, record)
        strict_bytes = path.read_bytes()
        assessment = {"status": "pass", "input_hashes": {"execution_sha256": digest(path), "assembly_sha256": "assembly-hash"}}
        save(path.parent / "tolerant.json", assessment)
        result = attach_assessment(copy.deepcopy(record), path)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["evaluation"]["status"], "fail")
        self.assertEqual(result["tolerant_assessment"]["status"], "pass")
        self.assertEqual(path.read_bytes(), strict_bytes)
        for field in ("execution_sha256", "assembly_sha256"):
            stale = copy.deepcopy(assessment)
            stale["input_hashes"][field] = "stale-hash"
            save(path.parent / "tolerant.json", stale)
            self.assertNotIn("tolerant_assessment", attach_assessment(copy.deepcopy(record), path))

    def test_assessment_with_missing_assembly_provenance_is_not_attached(self):
        path = self.batch / "results/fixture/flye/execution.json"
        record = {"status": "fail"}
        save(path, record)
        save(path.parent / "tolerant.json", {"status": "pass", "input_hashes": {"execution_sha256": digest(path)}})
        self.assertNotIn("tolerant_assessment", attach_assessment(record, path))


if __name__ == "__main__":
    unittest.main()
