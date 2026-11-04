"""Scientific and orchestration checks; no real assembler results are simulated."""

import copy
import gzip
import random
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from pipeline.cases import plan
from pipeline.common import ROOT, digest, fasta, fingerprint, load, reverse_complement, write_fasta
from pipeline.execution import command
from pipeline.reads import covered_bases, exact_reads
from pipeline.report import collect_records, result_status
from pipeline.scoring import equivalent, evaluate


def fixture_case():
    config = copy.deepcopy(load(ROOT / "config/pilot.json"))
    simulation = config["simulation"]
    simulation.update(chromosome_depth=25, length_mean=50, length_sd=20, length_min=10, length_max=100)
    replicons = [{"refseq_accession": "chrom", "replicon_name": "chromosome", "molecule_type": "chromosome", "topology": "circular", "length_bp": 401},
                 {"refseq_accession": "plasmid", "replicon_name": "small", "molecule_type": "plasmid", "topology": "circular", "length_bp": 73}]
    rng = random.Random(12)
    sequences = {r["refseq_accession"]: "".join(rng.choice("ACGT") for _ in range(r["length_bp"])) for r in replicons}
    case = {"id": "test", "replicons": replicons, "simulation": simulation}
    case["fingerprint"] = fingerprint(case)
    return case, sequences


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".cache").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".cache")
        self.path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def score(self, contigs, case=None):
        default, sequences = fixture_case()
        case = case or default
        write_fasta(self.path / "truth.fa", sequences)
        write_fasta(self.path / "assembly.fa", contigs)
        return evaluate(case, self.path / "truth.fa", self.path / "assembly.fa")

    def test_circle_rotation_and_reverse_complement(self):
        sequence = "AAACCGT"
        self.assertTrue(equivalent(sequence, sequence[3:] + sequence[:3], "circular"))
        self.assertTrue(equivalent(sequence, reverse_complement(sequence[3:] + sequence[:3]), "circular"))

    def test_linear_ends_are_not_rotatable(self):
        self.assertFalse(equivalent("AAACCGT", "CCGTAAA", "linear"))
        self.assertTrue(equivalent("AAACCGT", reverse_complement("AAACCGT"), "linear"))

    def test_exact_plasmid_passes_despite_fragmented_chromosome(self):
        case, seq = fixture_case()
        self.assertEqual(self.score({"p": seq["plasmid"], "c1": seq["chrom"][:200], "c2": seq["chrom"][200:]})["status"], "pass")

    def test_missing_and_partial_plasmid_fail_without_claiming_zero_recovery(self):
        case, seq = fixture_case()
        score = self.score({"c": seq["chrom"], "part": seq["plasmid"][:50]})
        self.assertEqual(score["status"], "fail")
        self.assertIsNone(score["replicons"][1]["recovered_fraction"])

    def test_duplicate_exact_molecules_fail(self):
        _, seq = fixture_case()
        self.assertEqual(self.score({"p1": seq["plasmid"], "p2": reverse_complement(seq["plasmid"])})["status"], "fail")

    def test_tandem_copy_and_chromosome_merge_fail(self):
        _, seq = fixture_case()
        for output in [seq["plasmid"] * 2, seq["chrom"] + seq["plasmid"]]:
            self.assertEqual(self.score({"wrong": output})["status"], "fail")

    def test_extra_full_copy_invalidates_exact_molecule(self):
        _, seq = fixture_case()
        self.assertEqual(self.score({"p": seq["plasmid"], "merge": seq["chrom"] + seq["plasmid"]})["status"], "fail")

    def test_mismatch_and_terminal_overlap_fail(self):
        _, seq = fixture_case()
        changed = ("A" if seq["plasmid"][0] != "A" else "C") + seq["plasmid"][1:]
        for output in [changed, seq["plasmid"] + seq["plasmid"][:5]]:
            self.assertEqual(self.score({"p": output})["status"], "fail")

    def test_empty_plasmid_output_passes_only_negative_control(self):
        case, seq = fixture_case()
        write_fasta(self.path / "truth.fa", seq)
        (self.path / "empty.fa").write_text("")
        self.assertEqual(evaluate(case, self.path / "truth.fa", self.path / "empty.fa", True)["status"], "fail")
        case["replicons"] = case["replicons"][:1]
        self.assertEqual(evaluate(case, self.path / "truth.fa", self.path / "empty.fa", True)["status"], "pass")

    def test_duplicate_headers_are_rejected(self):
        path = self.path / "duplicate.fa"
        path.write_text(">same\nACGT\n>same\nACGT\n")
        with self.assertRaises(ValueError):
            fasta(path)

    def test_exact_read_origins_and_quality_lengths(self):
        case, seq = fixture_case()
        manifest = exact_reads(case, seq, self.path / "first")
        self.assertEqual(manifest["status"], "valid")
        with gzip.open(self.path / "first/read_origins.tsv.gz", "rt") as f:
            origins = [line.strip().split("\t") for line in f][1:]
        with gzip.open(self.path / "first/reads.fastq.gz", "rt") as f:
            fastq = f.read().splitlines()
        strands = set()
        for i, (name, accession, start, length, strand) in enumerate(origins):
            read = fastq[i * 4 + 1]
            expected = (seq[accession] * 2)[int(start):int(start) + int(length)]
            self.assertEqual(read, reverse_complement(expected) if strand == "-" else expected)
            self.assertEqual(len(read), len(fastq[i * 4 + 3]))
            self.assertLessEqual(len(read), len(seq[accession]))
            strands.add(strand)
        self.assertEqual(strands, {"+", "-"})

    def test_reproducible_gzip_and_independent_seed(self):
        case, seq = fixture_case()
        exact_reads(case, seq, self.path / "a")
        exact_reads(case, seq, self.path / "b")
        self.assertEqual(digest(self.path / "a/reads.fastq.gz"), digest(self.path / "b/reads.fastq.gz"))
        case["simulation"]["seed"] += 1
        exact_reads(case, seq, self.path / "c")
        self.assertNotEqual(digest(self.path / "a/reads.fastq.gz"), digest(self.path / "c/reads.fastq.gz"))

    def test_chromosome_reads_are_preserved_across_subsets(self):
        case, seq = fixture_case()
        exact_reads(case, seq, self.path / "with-plasmid")
        case["replicons"] = case["replicons"][:1]
        exact_reads(case, {"chrom": seq["chrom"]}, self.path / "chrom-only")
        def chromosome_reads(path):
            with gzip.open(path, "rt") as f:
                lines = f.read().splitlines()
            return [lines[i:i + 4] for i in range(0, len(lines), 4) if lines[i].startswith("@chrom_")]
        self.assertEqual(chromosome_reads(self.path / "with-plasmid/reads.fastq.gz"), chromosome_reads(self.path / "chrom-only/reads.fastq.gz"))

    def test_coverage_union_does_not_double_count(self):
        self.assertEqual(covered_bases([(0, 20), (10, 40), (50, 60)]), 50)

    def test_finite_scenario_plan(self):
        cases = plan(load(ROOT / "config/pilot.json"))
        self.assertEqual(len(cases), 4)
        self.assertIn("s1-w-prk2", [case["id"] for case in cases])
        self.assertEqual(len({case["id"] for case in cases}), 4)

    def test_held_reference_is_not_silently_admitted(self):
        config = load(ROOT / "config/pilot.json")
        config["references"] = ["GCF_000220485.1"]
        with self.assertRaises(ValueError):
            plan(config)

    def test_next_stages_cover_both_species_and_declared_ratios(self):
        config = load(ROOT / "config/next-stages.json")
        cases = plan(config)
        self.assertEqual(sum(c["category"] == "S1" for c in cases), 22)
        coverage = [c for c in cases if c["category"] == "S2"]
        self.assertEqual(len(coverage), 10)
        self.assertEqual({c["simulation"]["plasmid_relative_depth"] for c in coverage}, {0.8, 1, 1.2, 3, 5})
        self.assertTrue(any(c["organism"].startswith("Klebsiella") for c in coverage))
        self.assertTrue(any(c["organism"].startswith("Escherichia") for c in coverage))
        self.assertEqual(config["simulation"]["plasmid_relative_depth"], 1)
        self.assertEqual(len({c["fingerprint"] for c in cases}), 32)

    def test_coverage_case_does_not_change_baseline_settings(self):
        cases = plan(load(ROOT / "config/next-stages.json"))
        self.assertTrue(all(c["simulation"]["plasmid_relative_depth"] == 1 for c in cases if c["category"] == "S1"))

    def test_coverage_target_must_be_a_native_plasmid(self):
        config = load(ROOT / "config/next-stages.json")
        config["coverage_panel"]["targets"][0]["plasmid"] = "NC_000913.3"
        with self.assertRaises(ValueError):
            plan(config)

    def test_commands_do_not_receive_truth(self):
        config = load(ROOT / "config/pilot.json")
        for tool in config["tools"]:
            argv = command(tool, Path("reads.fq.gz"), Path("output"), config)
            self.assertFalse(any("truth" in arg or "reference" in arg for arg in argv))

    def test_scheduler_failure_does_not_remain_running(self):
        self.assertEqual(result_status({"status": "running"}, "OUT_OF_MEMORY"), "error")
        self.assertEqual(result_status({}, "TIMEOUT"), "timeout")
        self.assertEqual(result_status({}, "RUNNING"), "running")
        self.assertEqual(result_status({}, "PENDING"), "pending")
        self.assertEqual(result_status({"status": "fail"}, "COMPLETED"), "fail")

    def test_unrun_report_never_invents_pass_or_fail(self):
        rows = collect_records(load(ROOT / "config/pilot.json"), None)
        self.assertEqual(len(rows), 16)
        self.assertEqual({row["status"] for row in rows}, {"not_run"})

    def test_report_rebuild_removes_stale_evidence(self):
        import shutil
        from pipeline.report import build
        shutil.copytree(ROOT / "website", self.path / "website", ignore=shutil.ignore_patterns("node_modules"))
        stale = self.path / "dist/data/old-run.json"
        stale.parent.mkdir(parents=True)
        stale.write_text('{"status":"pass"}')
        old_batch = self.path / "dist/batches/stale/data/results.json"
        old_batch.parent.mkdir(parents=True)
        old_batch.write_text('{"status":"pass"}')
        with patch("pipeline.report.ROOT", self.path):
            build(load(ROOT / "config/pilot.json"))
        self.assertFalse(stale.exists())
        self.assertFalse(old_batch.exists())
        data = load(self.path / "dist/data/results.json")
        self.assertEqual({r["status"] for r in data["results"]}, {"not_run"})

    def test_follow_tracks_only_the_submitted_comparisons(self):
        from pipeline.follow import selected_rows
        document = {"results": [{"scenario_id": "submitted", "tool": "flye", "status": "pass"},
                                {"scenario_id": "later", "tool": "flye", "status": "not_run"}]}
        rows = selected_rows(document, [{"scenario": "submitted", "tool": "flye"}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "pass")

    def test_publication_does_not_repeat_for_snapshot_time_only(self):
        from pipeline.follow import progress_fingerprint
        first = {"generated_at": "earlier", "results": [{"status": "running"}], "inputs": {}}
        second = {**first, "generated_at": "later"}
        self.assertEqual(progress_fingerprint(first), progress_fingerprint(second))
        second["results"] = [{"status": "pass"}]
        self.assertNotEqual(progress_fingerprint(first), progress_fingerprint(second))


if __name__ == "__main__":
    unittest.main()
