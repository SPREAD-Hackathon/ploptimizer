"""S4 checks: bounded inputs, stable baseline plans and per-molecule evidence."""

import copy
import gzip
import random
import tempfile
import unittest
from pathlib import Path

from pipeline.cases import plan
from pipeline.common import ROOT, load
from pipeline.reads import exact_reads


class SmallPlasmidTests(unittest.TestCase):
    def setUp(self):
        self.config = load(ROOT / "config/small-plasmids.json")

    def test_two_species_two_contexts_three_length_profiles(self):
        cases = plan(self.config)
        self.assertEqual(len(cases), 12)
        self.assertEqual({case["category"] for case in cases}, {"S4"})
        self.assertEqual({case["read_length_profile"] for case in cases}, {"short", "baseline", "long"})
        self.assertEqual(sum(case["truth_type"] == "native_complement" for case in cases), 6)
        self.assertEqual({case["small_plasmid_accession"] for case in cases}, {"NC_017662.1", "NC_009653.1"})
        self.assertEqual(len({case["fingerprint"] for case in cases}), 12)
        self.assertEqual(len(cases) * len(self.config["tools"]), 48)
        self.assertTrue(all(case["simulation"]["chromosome_depth"] == 30 for case in cases))

    def test_short_profile_is_below_both_small_plasmid_lengths(self):
        for case in plan(self.config):
            if case["read_length_profile"] == "short":
                target = next(r for r in case["replicons"] if r["refseq_accession"] == case["small_plasmid_accession"])
                self.assertLess(case["simulation"]["length_max"], target["length_bp"])
        self.assertEqual(self.config["simulation"]["length_mean"], 10000)

    def test_s4_expansion_preserves_baseline_case_fingerprints(self):
        config = load(ROOT / "config/next-stages.json")
        before = plan(config)
        config["read_length_panel"] = self.config["read_length_panel"]
        after = plan(config)
        self.assertEqual(before, [case for case in after if case["category"] in {"S1", "S2"}])
        changed = next(case for case in after if case["category"] == "S4")
        changed["simulation"]["length_mean"] = 1
        self.assertEqual(before, [case for case in after if case["category"] in {"S1", "S2"}])

    def test_invalid_target_profile_and_duplicate_context_are_rejected(self):
        for mutate in (
            lambda c: c["read_length_panel"]["targets"][0].update(plasmid="NC_017660.1"),
            lambda c: c["read_length_panel"]["profiles"][0].update(length_mean=float("nan")),
            lambda c: c["read_length_panel"]["profiles"][0].update(length_min=3000),
            lambda c: c["read_length_panel"].update(contexts=["native", "native"]),
            lambda c: c["read_length_panel"]["profiles"][0].update(length_max=2500.5),
        ):
            config = copy.deepcopy(self.config)
            mutate(config)
            with self.assertRaises(ValueError):
                plan(config)

    def test_actual_read_lengths_and_clipping_are_in_input_evidence(self):
        # Use only the genuine small plasmid sequence length; a small independent
        # fixture chromosome avoids making the test generate whole-genome reads.
        cases = [c for c in plan(self.config) if c["id"].startswith("s4-mgh78578-pkpn7-")]
        rng = random.Random(482)
        observed = {}
        with tempfile.TemporaryDirectory() as directory:
            for case in cases:
                case = copy.deepcopy(case)
                for replicon in case["replicons"]:
                    if replicon["molecule_type"] == "chromosome":
                        replicon["length_bp"] = 20011
                sequences = {r["refseq_accession"]: "".join(rng.choice("ACGT") for _ in range(r["length_bp"])) for r in case["replicons"]}
                output = Path(directory) / case["read_length_profile"]
                manifest = exact_reads(case, sequences, output)
                self.assertEqual(manifest["status"], "valid")
                stats = next(r for r in manifest["replicons"] if r["accession"] == case["small_plasmid_accession"])
                self.assertGreaterEqual(stats["breadth"], .99)
                self.assertGreater(stats["read_count"], 0)
                self.assertLessEqual(stats["maximum_read_length"], 3478)
                self.assertGreaterEqual(stats["achieved_depth"], 30)
                observed[case["read_length_profile"]] = stats
                with gzip.open(output / "read_origins.tsv.gz", "rt") as origins:
                    for line in list(origins)[1:]:
                        _, accession, _, length, _ = line.strip().split("\t")
                        self.assertLessEqual(int(length), len(sequences[accession]))
        self.assertLessEqual(observed["short"]["maximum_read_length"], 2500)
        self.assertLess(observed["short"]["mean_read_length"], observed["baseline"]["mean_read_length"])
        self.assertLess(observed["long"]["mean_read_length"], 25000)


if __name__ == "__main__":
    unittest.main()
