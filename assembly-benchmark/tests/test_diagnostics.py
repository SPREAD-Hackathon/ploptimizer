"""Synthetic alignment fixtures exercise evidence, not assembler-specific output."""

import tempfile
import unittest
from pathlib import Path

from pipeline.diagnostics import minimap2_command, read_paf, summarise_paf


def replicon(accession, length=1000):
    return {"refseq_accession": accession, "length_bp": length, "replicon_name": accession,
            "molecule_type": "plasmid", "topology": "circular"}


def paf(query="a", qlen=1000, qs=0, qe=1000, target="p", tlen=1000, ts=0, te=1000,
        matches=None, block=None, mapq=60, strand="+", kind="P", cigar=None):
    block = block if block is not None else qe - qs
    matches = matches if matches is not None else block
    fields = [query, qlen, qs, qe, strand, target, tlen, ts, te, matches, block, mapq]
    tags = [f"tp:A:{kind}"]
    if cigar is not False:
        tags.append(f"cg:Z:{cigar or str(qe - qs) + 'M'}")
    return "\t".join(map(str, fields + tags))


class RecoveryDiagnosticsTests(unittest.TestCase):
    def summary(self, rows, refs=None, lengths=None, policy=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mapping.paf"
            path.write_text("\n".join(rows) + ("\n" if rows else ""))
            return summarise_paf({"replicons": refs or [replicon("p")]}, path, lengths, policy)

    def test_missing_preserves_zero_coverage_and_unknown_identity(self):
        result = self.summary([], lengths={"unmapped": 1500})
        row = result["replicons"][0]
        self.assertEqual(row["recovered_fraction"], 0)
        self.assertIsNone(row["alignment_identity"])
        self.assertTrue(row["candidate_flags"]["no_supported_alignment"])
        self.assertEqual(result["contigs_without_supported_alignment"], ["unmapped"])

    def test_fragmentation_unions_contigs_without_inflating_coverage(self):
        rows = [paf("a", qlen=600, qe=600, te=600),
                paf("b", qlen=600, qe=600, ts=400, te=1000)]
        row = self.summary(rows)["replicons"][0]
        self.assertEqual(row["recovered_fraction"], 1)
        self.assertEqual(row["best_contig_recovered_fraction"], 0.6)
        self.assertTrue(row["candidate_flags"]["fragmented"])
        self.assertTrue(row["candidate_flags"]["duplicated"])
        self.assertEqual(row["duplicated_reference_fraction"], 0.2)

    def test_duplicate_full_molecules_are_evidence_not_strict_pass(self):
        row = self.summary([paf("a"), paf("b")])["replicons"][0]
        self.assertEqual(row["contig_count"], 2)
        self.assertTrue(row["candidate_flags"]["duplicated"])
        self.assertFalse(row["candidate_flags"]["fragmented"])
        self.assertNotIn("status", row)

    def test_tandem_copy_on_one_contig_uses_disjoint_query_intervals(self):
        row = self.summary([paf(qlen=2000), paf(qlen=2000, qs=1000, qe=2000)])["replicons"][0]
        self.assertTrue(row["candidate_flags"]["duplicated"])
        self.assertEqual(row["contig_count"], 1)

    def test_join_is_supported_by_distinct_query_segments(self):
        rows = [paf(qlen=2000), paf(qlen=2000, qs=1000, qe=2000, target="q")]
        result = self.summary(rows, refs=[replicon("p"), replicon("q")])
        self.assertEqual(result["candidate_joins"], [{"contig": "a", "replicon_pairs": [["p", "q"]]}])
        self.assertTrue(all(row["candidate_flags"]["joined"] for row in result["replicons"]))

    def test_shared_query_region_is_not_called_a_join(self):
        result = self.summary([paf(), paf(target="q")], refs=[replicon("p"), replicon("q")])
        self.assertEqual(result["candidate_joins"], [])

    def test_reverse_strand_and_circular_origin_split_remain_full_coverage(self):
        rows = [paf(qlen=1000, qe=400, ts=600, te=1000, strand="-"),
                paf(qlen=1000, qs=400, qe=1000, ts=0, te=600, strand="-")]
        row = self.summary(rows)["replicons"][0]
        self.assertEqual(row["recovered_fraction"], 1)
        self.assertFalse(any(row["candidate_flags"].values()))
        self.assertEqual(row["topology_status"], "not_assessed")

    def test_overlapping_records_on_same_query_do_not_imply_duplicate(self):
        rows = [paf(qlen=1000, qe=700, te=700), paf(qlen=1000, qs=300, qe=1000, ts=300)]
        row = self.summary(rows)["replicons"][0]
        self.assertEqual(row["recovered_fraction"], 1)
        self.assertFalse(row["candidate_flags"]["duplicated"])

    def test_deleted_reference_bases_are_not_recovered(self):
        row = self.summary([paf(qlen=900, qe=900, block=1000, matches=900, cigar="450M100D450M")])["replicons"][0]
        self.assertEqual(row["recovered_fraction"], 0.9)
        self.assertEqual(row["alignment_identity"], 0.9)

    def test_identity_is_alignment_weighted_and_missing_cigar_excluded(self):
        rows = [paf("a", qlen=400, qe=400, te=400, matches=360),
                paf("b", qlen=600, qe=600, ts=400, te=1000, matches=600), paf("c", cigar=False)]
        result = self.summary(rows)
        self.assertEqual(result["replicons"][0]["alignment_identity"], 0.96)
        self.assertEqual(result["excluded_alignment_counts"], {"missing_base_alignment": 1})

    def test_ambiguity_filters_are_explicit_and_deduplicate_identical_lines(self):
        rows = [paf(), paf(), paf("b", mapq=0), paf("c", mapq=255), paf("d", kind="S"),
                paf("e", matches=800), paf("f", qlen=100, qe=100, te=100), paf("g", kind="i")]
        result = self.summary(rows)
        self.assertEqual(result["accepted_alignment_count"], 1)
        self.assertEqual(result["excluded_alignment_counts"], {"duplicate_paf_record": 1,
                         "low_mapq": 1, "missing_mapq": 1, "secondary_or_unclassified": 2,
                         "low_identity": 1, "short_alignment": 1})
        self.assertFalse(result["replicons"][0]["candidate_flags"]["duplicated"])

    def test_mismatched_inventories_and_malformed_cigar_raise(self):
        for rows, lengths in (([paf(target="other")], None), ([paf()], {"a": 999}),
                              ([paf(cigar="999M")], None), ([paf(te=999)], None)):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.summary(rows, lengths=lengths)

    def test_ambiguous_base_alignment_is_valid_paf_but_excluded(self):
        row = paf(matches=990, block=990) + "\tnn:i:10"
        result = self.summary([row])
        self.assertEqual(result["excluded_alignment_counts"], {"ambiguous_bases": 1})
        self.assertIsNone(result["replicons"][0]["alignment_identity"])

    def test_bad_coordinates_raise(self):
        with self.assertRaises(ValueError):
            self.summary([paf(qs=-1)])

    def test_command_order_and_policy_validation(self):
        command = minimap2_command("truth.fa", "assembly.fa", 2)
        self.assertEqual(command[:4], ["minimap2", "-x", "asm5", "-c"])
        self.assertEqual(command[-2:], ["truth.fa", "assembly.fa"])
        for value in (0, True, 1.5):
            with self.assertRaises(ValueError):
                minimap2_command("t", "a", value)
        with self.assertRaises(ValueError):
            self.summary([], policy={"minimum_identity": 1.1})


if __name__ == "__main__":
    unittest.main()
