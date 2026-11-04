"""Adapter contracts without requiring local Badread or downloading model assets."""

import copy
import csv
import gzip
import hashlib
import importlib.util
import io
from pathlib import Path
import random
import re
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from pipeline import noisy_reads as noisy
from pipeline.common import digest, fingerprint, load, save, write_fasta


class FakeBackend:
    mode = "substitution"
    calls = []

    def __init__(self, profile):
        self.mode = type(self).mode

    def generate(self, fragment, target, seed):
        type(self).calls.append((fragment, target, seed))
        if self.mode == "bad_quality":
            return fragment, "I", 0.25, 0.5
        if self.mode == "insertion":
            result = "C" + fragment
        elif self.mode == "deletion":
            result = fragment[1:]
        elif self.mode == "unchanged":
            result = fragment
        else:
            position = int(seed, 16) % len(fragment)
            result = fragment[:position] + ("C" if fragment[position] != "C" else "A") + fragment[position + 1:]
        # Deliberately wrong upstream identities prove the adapter recomputes truth.
        return result, "I" * len(result), 0.25, 0.5

    def align(self, emitted, fragment):
        if self.mode == "insertion":
            return {"cigar": "1I" + str(len(fragment)) + "=", "editDistance": 1}
        if self.mode == "deletion":
            return {"cigar": "1D" + str(len(emitted)) + "=", "editDistance": 1}
        operations = ["=" if a == b else "X" for a, b in zip(emitted, fragment)]
        groups = [(len(match.group()), match.group()[0]) for match in re.finditer(r"=+|X+", "".join(operations))]
        return {"cigar": "".join(str(size) + operation for size, operation in groups), "editDistance": operations.count("X")}


class NoisyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.clean = self.root / "clean"
        self.clean.mkdir()
        self.output = self.root / "output"
        self.profile = {"id": "generic-stress", "error_model": "random", "qscore_model": "ideal",
                        "identity_beta_percent": {"mean": 99, "maximum": 99, "sd": 0}, "expected_runtime_sha256": "a" * 64}
        self.runtime = {"runtime": {"badread_version": "0.4.2", "test_backend": True}, "sha256": "a" * 64}
        self.root_patch = patch.object(noisy, "ROOT", self.root)
        self.runtime_patch = patch.object(noisy, "inspect_runtime", return_value=self.runtime)
        self.backend_patch = patch.object(noisy, "BadreadBackend", FakeBackend)
        for item in (self.root_patch, self.runtime_patch, self.backend_patch):
            item.start()
            self.addCleanup(item.stop)
        FakeBackend.calls, FakeBackend.mode = [], "substitution"
        self.prepare()

    def prepare(self, count=30, read_length=100, minimum_breadth=0.99):
        replicon = {"refseq_accession": "p", "replicon_name": "p", "length_bp": 100,
                    "molecule_type": "plasmid", "topology": "circular"}
        self.case = {"id": "s1-test", "replicons": [replicon], "simulation": {
            "model": "exact-lognormal-v1", "seed": 123, "chromosome_depth": 30,
            "plasmid_relative_depth": 1, "length_mean": read_length, "length_sd": 0,
            "length_min": read_length, "length_max": read_length, "circular_read_limit": "one_circumference", "minimum_breadth": minimum_breadth}}
        self.case["fingerprint"] = fingerprint(self.case)
        write_fasta(self.clean / "truth.fasta", {"p": "A" * 100})
        with gzip.open(self.clean / "reads.fastq.gz", "wt") as reads, gzip.open(self.clean / "read_origins.tsv.gz", "wt") as origins:
            origins.write("\t".join(noisy.ORIGIN_FIELDS) + "\n")
            for number in range(count):
                name = "p_" + str(number)
                reads.write(f"@{name}\n{'A' * read_length}\n+\n{'I' * read_length}\n")
                origins.write(f"{name}\tp\t0\t{read_length}\t+\n")
        self.refresh_manifest()

    def refresh_manifest(self, origins=None):
        origins = origins or self.clean / "read_origins.tsv.gz"
        save(self.clean / "input.json", {"case": self.case, "model": "exact-lognormal-v1", "status": "valid",
             "reads_sha256": digest(self.clean / "reads.fastq.gz"), "origins_sha256": digest(origins), "truth_sha256": digest(self.clean / "truth.fasta")})

    def transform(self, output=None, origins=None, profile=None, case=None):
        return noisy.transform_fragments(self.clean / "reads.fastq.gz", origins or self.clean / "read_origins.tsv.gz",
                                        output or self.output, profile or self.profile, case or self.case)

    def test_preserves_origins_and_independently_measures_final_read(self):
        before = digest(self.clean / "reads.fastq.gz")
        result = self.transform()
        self.assertEqual(result["status"], "valid")
        row = result["replicons"][0]
        self.assertEqual(row["identity_stats"]["source_base_weighted_mean"], 0.99)
        self.assertEqual(row["error_counts"]["substitutions"], 30)
        self.assertEqual(row["breadth"], 1)
        self.assertEqual(row["source_depth"], 30)
        self.assertEqual(row["achieved_depth"], 30)
        self.assertEqual(digest(self.clean / "reads.fastq.gz"), before)
        with gzip.open(self.output / "read_audit.tsv.gz", "rt") as stream:
            audit = list(csv.DictReader(stream, delimiter="\t"))
        self.assertEqual(audit[0]["upstream_padded_identity"], "0.25")
        self.assertEqual(audit[0]["actual_identity"], "0.99")
        self.assertEqual(audit[0]["read_id"], "p_0")
        self.assertEqual(load(self.output / "noisy-input.json")["status"], "valid")

    def test_gzip_and_streams_reproduce_and_do_not_use_process_global_randomness(self):
        first = self.transform()
        random.seed(9981)
        second = self.transform(self.root / "second")
        for key in ("reads_sha256", "origins_sha256", "read_audit_sha256", "truth_sha256"):
            self.assertEqual(first[key], second[key])
        raw = (self.output / "reads.fastq.gz").read_bytes()
        self.assertEqual(raw[4:8], b"\0\0\0\0")

    def test_identity_targets_pair_between_profiles_but_error_streams_differ(self):
        self.profile["identity_beta_percent"] = {"mean": 98, "maximum": 99.5, "sd": 1}
        self.transform()
        first = list(FakeBackend.calls)
        FakeBackend.calls = []
        other = {**self.profile, "id": "ont2023-shaped", "error_model": "nanopore2023", "qscore_model": "nanopore2023"}
        self.transform(self.root / "other", profile=other)
        self.assertEqual([call[1] for call in first], [call[1] for call in FakeBackend.calls])
        self.assertNotEqual([call[2] for call in first], [call[2] for call in FakeBackend.calls])

    def test_final_insertions_are_retained_without_clipping_to_source_circle(self):
        FakeBackend.mode = "insertion"
        result = self.transform()
        row = result["replicons"][0]
        self.assertEqual(result["status"], "valid")
        self.assertEqual(row["maximum_read_length"], 101)
        self.assertEqual(row["source_length_stats"]["maximum"], 100)
        self.assertEqual(row["error_counts"]["insertions"], 30)
        self.assertEqual(row["quality_stats"]["calibration"][0]["substitutions_or_insertions"], 30)

    def test_deletions_have_no_emitted_quality_assignment(self):
        FakeBackend.mode = "deletion"
        row = self.transform()["replicons"][0]
        self.assertEqual(row["error_counts"]["deletions"], 30)
        self.assertEqual(row["source_breadth"], 1)
        self.assertEqual(row["emitted_breadth"], 0.99)
        self.assertEqual(row["quality_stats"]["calibration"][0]["substitutions_or_insertions"], 0)
        self.assertEqual(row["minimum_read_length"], 99)

    def test_identity_validation_hold_is_invalid_input_not_assembler_failure(self):
        self.profile["identity_beta_percent"] = {"mean": 95, "maximum": 95, "sd": 0}
        result = self.transform()
        self.assertEqual(result["status"], "invalid_input")
        self.assertTrue(any("identity" in message for message in result["replicons"][0]["validation_holds"]))
        self.assertNotIn("evaluation", result)

    def test_breadth_and_source_stopping_checks_are_recomputed(self):
        self.prepare(count=60, read_length=50)
        self.profile["identity_beta_percent"] = {"mean": 98, "maximum": 98, "sd": 0}
        result = self.transform()
        self.assertEqual(result["status"], "invalid_input")
        self.assertEqual(result["replicons"][0]["breadth"], 0.5)
        self.assertTrue(any("breadth" in message for message in result["replicons"][0]["validation_holds"]))

    def test_wrong_source_depth_invalidates_even_with_full_breadth(self):
        self.prepare(count=29)
        result = self.transform()
        self.assertEqual(result["status"], "invalid_input")
        self.assertTrue(any("depth" in message for message in result["replicons"][0]["validation_holds"]))

    def test_unfrozen_or_changed_runtime_fails_closed(self):
        for value in (None, "b" * 64):
            profile = dict(self.profile)
            if value is None:
                del profile["expected_runtime_sha256"]
            else:
                profile["expected_runtime_sha256"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.transform(profile=profile)
        self.assertFalse(self.output.exists())

    def test_corrupt_source_hash_or_origin_rejected(self):
        with gzip.open(self.clean / "reads.fastq.gz", "at") as stream:
            stream.write("extra")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.transform()
        self.prepare()
        with gzip.open(self.clean / "read_origins.tsv.gz", "wt") as stream:
            stream.write("\t".join(noisy.ORIGIN_FIELDS) + "\np_0\tunknown\t0\t100\t+\n")
        self.refresh_manifest()
        with self.assertRaisesRegex(ValueError, "origin"):
            self.transform()
        self.assertFalse((self.output / "noisy-input.json").exists())

    def test_failed_generation_cleans_partial_files(self):
        FakeBackend.mode = "bad_quality"
        with self.assertRaisesRegex(ValueError, "quality"):
            self.transform()
        self.assertFalse(list(self.output.glob("*.partial")))
        self.assertFalse((self.output / "reads.fastq.gz").exists())
        self.assertFalse((self.output / "noisy-input.json").exists())

    def test_existing_output_and_paths_outside_work_area_rejected(self):
        self.transform()
        with self.assertRaisesRegex(ValueError, "already exist"):
            self.transform()
        with self.assertRaisesRegex(ValueError, "work area"):
            self.transform(output=self.root.parent / "outside-output")

    def test_plain_origin_table_supported_when_frozen_hash_matches(self):
        path = self.clean / "origins.tsv"
        with gzip.open(self.clean / "read_origins.tsv.gz", "rt") as stream:
            path.write_text(stream.read())
        self.refresh_manifest(path)
        self.assertEqual(self.transform(origins=path)["status"], "valid")

    def test_changed_geometry_and_unknown_problem_profile_are_rejected(self):
        other = copy.deepcopy(self.case)
        other["simulation"]["seed"] += 1
        other["fingerprint"] = fingerprint({key: value for key, value in other.items() if key != "fingerprint"})
        with self.assertRaisesRegex(ValueError, "geometry"):
            self.transform(case=other)
        with self.assertRaisesRegex(ValueError, "chimeras"):
            self.transform(profile={**self.profile, "additional_problems": {"chimeras": True}})


class AlignmentContractTests(unittest.TestCase):
    def test_indel_cigar_and_quality_calibration_are_emitted_base_oriented(self):
        result = noisy.alignment_evidence("TACG", "ACGT", "I!II", {"cigar": "1I3=1D", "editDistance": 2})
        self.assertEqual(result["identity"], 3 / 5)
        self.assertEqual(result["insertions"], 1)
        self.assertEqual(result["deletions"], 1)
        self.assertEqual(result["quality_errors"], {40: 1})

    def test_inconsistent_cigar_is_rejected(self):
        for alignment in ({"cigar": "4=", "editDistance": 0}, {"cigar": "3M", "editDistance": 0}, {"cigar": "1I3=1D", "editDistance": 1}):
            with self.subTest(alignment=alignment), self.assertRaises(ValueError):
                noisy.alignment_evidence("TACG", "ACGT", "IIII", alignment)

    def test_profile_beta_parameters_and_unsupported_models(self):
        profile = {"id": "generic", "error_model": "random", "qscore_model": "ideal", "expected_runtime_sha256": "a" * 64,
                   "identity_beta_percent": {"mean": 98, "maximum": 99.5, "sd": 1}}
        maximum, alpha, beta = noisy._profile(profile)
        self.assertAlmostEqual(maximum * alpha / (alpha + beta), 0.98)
        for params in ({"mean": 98, "maximum": 97, "sd": 1}, {"mean": 98, "maximum": 98, "sd": 1}, {"mean": float("nan"), "maximum": 99, "sd": 1}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                noisy._profile({**profile, "identity_beta_percent": params})
        with self.assertRaises(ValueError):
            noisy._profile({**profile, "error_model": "unrecorded-custom-file"})


@unittest.skipUnless(importlib.util.find_spec("badread") and importlib.util.find_spec("edlib"), "Optional installed Badread/Edlib smoke test; dependencies are provided by Linux Pixi")
class InstalledBadreadTests(unittest.TestCase):
    def test_pinned_runtime_and_model_generation(self):
        for profile in ({"error_model": "random", "qscore_model": "ideal"}, {"error_model": "nanopore2023", "qscore_model": "nanopore2023"}):
            with self.subTest(profile=profile):
                runtime = noisy.inspect_runtime(profile)
                self.assertEqual(runtime["runtime"]["badread_version"], "0.4.2")
                backend = noisy.BadreadBackend(profile)
                fragment = "ACGT" * 250
                emitted, quality, _, _ = backend.generate(fragment, 0.98, "d" * 64)
                self.assertEqual(len(emitted), len(quality))
                result = noisy.alignment_evidence(emitted, fragment, quality, backend.align(emitted, fragment))
                self.assertGreater(result["identity"], 0.9)
                self.assertEqual(backend.generate(fragment, 0.98, "d" * 64)[:2], (emitted, quality))



class RuntimeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("simulate.py", "error_model.py", "qscore_model.py", "misc.py", "settings.py", "version.py"):
            (self.root / name).write_text("# pinned test source\n")
        for folder in ("error_models", "qscore_models"):
            (self.root / folder).mkdir()
            (self.root / folder / "nanopore2023.gz").write_bytes(b"pinned model")
        (self.root / "edlib.so").write_bytes(b"edlib binary")
        (self.root / "mtrand.so").write_bytes(b"numpy RNG binary")
        self.version = SimpleNamespace(__version__="0.4.2")
        self.modules = {"badread.simulate": SimpleNamespace(__file__=str(self.root / "simulate.py")),
                        "badread.version": self.version, "numpy": SimpleNamespace(__version__="2.2.0"),
                        "edlib": SimpleNamespace(__file__=str(self.root / "edlib.so")),
                        "numpy.random.mtrand": SimpleNamespace(__file__=str(self.root / "mtrand.so"))}
        self.import_patch = patch.object(noisy.importlib, "import_module", side_effect=lambda name: self.modules[name])
        self.metadata_patch = patch.object(noisy.importlib.metadata, "version", return_value="1.3.9")
        self.import_patch.start()
        self.metadata_patch.start()
        self.addCleanup(self.import_patch.stop)
        self.addCleanup(self.metadata_patch.stop)
        self.profile = {"error_model": "nanopore2023", "qscore_model": "nanopore2023"}

    def test_sources_models_and_rng_binary_are_fingerprinted(self):
        first = noisy.inspect_runtime(self.profile)
        self.assertEqual(len(first["runtime"]["model_assets_sha256"]), 2)
        (self.root / "error_models/nanopore2023.gz").write_bytes(b"changed model")
        second = noisy.inspect_runtime(self.profile)
        self.assertNotEqual(first["sha256"], second["sha256"])
        (self.root / "simulate.py").write_text("# changed source\n")
        self.assertNotEqual(second["sha256"], noisy.inspect_runtime(self.profile)["sha256"])

    def test_missing_assets_and_unpinned_version_fail_closed(self):
        (self.root / "qscore_models/nanopore2023.gz").unlink()
        with self.assertRaisesRegex(ValueError, "asset is missing"):
            noisy.inspect_runtime(self.profile)
        self.version.__version__ = "0.4.3"
        with self.assertRaisesRegex(ValueError, "requires Badread 0.4.2"):
            noisy.inspect_runtime(self.profile)


class GlobalRngIsolationTests(unittest.TestCase):
    def test_seed_context_restores_python_and_numpy_even_after_exception(self):
        class NumpyRng:
            state = [4, 5, 6]
            def get_state(self):
                return list(self.state)
            def set_state(self, state):
                self.state = list(state)
            def seed(self, seed):
                self.state = list(seed)
        numpy_rng = NumpyRng()
        backend = noisy.BadreadBackend.__new__(noisy.BadreadBackend)
        backend.numpy = SimpleNamespace(random=numpy_rng)
        original = random.getstate()
        with self.assertRaisesRegex(RuntimeError, "test failure"):
            with backend.seeded("d" * 64):
                self.assertEqual(numpy_rng.state, [int("dddddddd", 16)] * 8)
                self.assertNotEqual(random.getstate(), original)
                raise RuntimeError("test failure")
        self.assertEqual(random.getstate(), original)
        self.assertEqual(numpy_rng.state, [4, 5, 6])


class OriginProjectionTests(unittest.TestCase):
    def test_circular_forward_and_reverse_projection(self):
        self.assertEqual(noisy.project_fragment_intervals([(0, 15)], 90, 20, "+", 100), [(90, 100), (0, 5)])
        self.assertEqual(noisy.project_fragment_intervals([(0, 5)], 90, 20, "-", 100), [(5, 10)])


@unittest.skipUnless(importlib.util.find_spec("badread") and importlib.util.find_spec("edlib"), "Optional installed Badread writer smoke test; run under Linux Pixi simulator environment")
class InstalledBadreadWriterTests(unittest.TestCase):
    def test_both_pinned_models_transform_tiny_30x_set(self):
        from pipeline.reads import exact_reads
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            rng = random.Random(731)
            reference = "".join(rng.choice("ACGT") for _ in range(1000))
            case = {"id": "tiny-source", "replicons": [{"refseq_accession": "fixture", "replicon_name": "fixture",
                    "length_bp": 1000, "molecule_type": "plasmid", "topology": "circular"}],
                    "simulation": {"model": "exact-lognormal-v1", "seed": 20261105, "chromosome_depth": 30,
                    "plasmid_relative_depth": 1, "length_mean": 1000, "length_sd": 0, "length_min": 500,
                    "length_max": 50000, "circular_read_limit": "one_circumference", "minimum_breadth": 0.99, "fastq_phred": 40}}
            case["fingerprint"] = fingerprint(case)
            source = root / "clean"
            exact_reads(case, {"fixture": reference}, source)
            for profile in ({"id": "generic-stress", "error_model": "random", "qscore_model": "ideal"},
                            {"id": "ont2023-shaped", "error_model": "nanopore2023", "qscore_model": "nanopore2023"}):
                with self.subTest(profile=profile["id"]), patch.object(noisy, "ROOT", root):
                    profile = {**profile, "identity_beta_percent": {"mean": 98, "maximum": 98, "sd": 0}}
                    profile["expected_runtime_sha256"] = noisy.inspect_runtime(profile)["sha256"]
                    target_case = copy.deepcopy(case)
                    target_case["id"] = "tiny-" + profile["id"]
                    target_case["simulation"]["model"] = noisy.ADAPTER_VERSION
                    target_case["fingerprint"] = fingerprint({key: value for key, value in target_case.items() if key != "fingerprint"})
                    output = root / profile["id"]
                    result = noisy.transform_fragments(source / "reads.fastq.gz", source / "read_origins.tsv.gz", output, profile, target_case)
                    self.assertEqual(result["status"], "valid", result["replicons"][0]["validation_holds"])
                    row = result["replicons"][0]
                    self.assertEqual(row["read_count"], 30)
                    self.assertEqual(row["source_depth"], 30)
                    self.assertEqual(row["source_breadth"], 1)
                    self.assertGreater(row["emitted_breadth"], 0.99)
                    self.assertAlmostEqual(row["identity_stats"]["source_base_weighted_mean"], 0.98, delta=0.005)
                    self.assertTrue((output / "noisy-input.json").exists())
                    with gzip.open(output / "reads.fastq.gz", "rt") as stream:
                        lines = stream.read().splitlines()
                    self.assertEqual(len(lines), 120)
                    self.assertTrue(all(len(lines[index + 1]) == len(lines[index + 3]) for index in range(0, 120, 4)))
                    repeat = noisy.transform_fragments(source / "reads.fastq.gz", source / "read_origins.tsv.gz", root / (profile["id"] + "-repeat"), profile, target_case)
                    self.assertEqual(result["reads_sha256"], repeat["reads_sha256"])
                    self.assertEqual(result["read_audit_sha256"], repeat["read_audit_sha256"])


if __name__ == "__main__":
    unittest.main()
