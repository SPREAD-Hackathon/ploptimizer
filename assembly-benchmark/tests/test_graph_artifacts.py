"""Synthetic format fixtures only: no reference or assembler analyses."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from pipeline.common import digest, save
from pipeline.graph_artifacts import attach_graph_artifacts, build_graph_artifacts, parse_gfa, parse_flye_assembly_info, parse_plassembler_summary


class GraphMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "graph.gfa"

    def gfa(self, text, **kwargs):
        self.path.write_text(text)
        return parse_gfa(self.path, **kwargs)

    def test_segments_links_paths_orientations_and_self_links_without_sequences(self):
        text = "H\tVN:Z:1.0\nS\ta\tAACCGG\tLN:i:6\tdp:f:12.5\tRC:i:9\tKC:i:30\tZZ:Z:SECRETSEQUENCE\nS\tb\t*\tLN:i:8\nL\ta\t+\tb\t-\t2M\nL\tb\t-\tb\t+\t0M\nP\tpath1\ta+,b-\t2M\n"
        result = self.gfa(text)
        self.assertEqual(result["status"], "available")
        self.assertTrue(result["complete"])
        self.assertEqual(result["nodes"][0]["length_bp"], 6)
        self.assertEqual(result["nodes"][1]["length_bp"], 8)
        self.assertEqual(result["edges"][0]["target_orientation"], "-")
        self.assertEqual(result["self_loop_segment_ids"], ["b"])
        self.assertEqual(result["paths"][0]["steps"][1], {"segment": "b", "orientation": "-"})
        self.assertEqual(result["source"]["file_sha256"], digest(self.path))
        tags = {row["tag"]: row for row in result["nodes"][0]["reported_coverage_tags"]}
        self.assertEqual(tags["dp"]["value"], 12.5)
        self.assertEqual(tags["RC"]["meaning"], "read_count")
        self.assertEqual(tags["KC"]["meaning"], "kmer_count")
        self.assertNotIn("AACCGG", json.dumps(result))
        self.assertNotIn("SECRETSEQUENCE", json.dumps(result))
        self.assertEqual(self.path.read_text(), text)

    def test_thousands_of_segment_paths_are_supported_but_still_bounded(self):
        text = "".join(f"S\tn{i}\t*\tLN:i:10\n" for i in range(2102))
        text += "".join(f"P\tp{i}\tn{i}+\t*\n" for i in range(2102))
        result = self.gfa(text)
        self.assertEqual(result["status"], "available")
        self.assertEqual(len(result["paths"]), 2102)
        self.assertEqual(result["edges"], [])
        self.assertEqual(self.gfa(text, limits={"max_paths": 1000})["status"], "unsupported")

    def test_unspecified_lengths_overlaps_and_forward_references_are_preserved(self):
        result = self.gfa("L\ta\t-\tb\t+\t*\nP\tp\ta-,b+\t*\nS\ta\t*\nS\tb\t*\tLN:i:10\n")
        self.assertEqual(result["status"], "available")
        self.assertIsNone(result["nodes"][0]["length_bp"])
        self.assertIsNone(result["paths"][0]["overlaps"])
        self.assertEqual(result["edges"][0]["overlap"], "*")

    def test_missing_invalid_and_unsupported_are_distinct(self):
        self.assertEqual(parse_gfa(None)["status"], "missing")
        self.assertEqual(self.gfa("S\ta\tAAAA\tLN:i:5\n")["status"], "invalid")
        self.assertEqual(self.gfa("H\tVN:Z:2.0\nS\ta\t4\tAAAA\n")["status"], "unsupported")
        self.assertEqual(self.gfa("S\ta\tAAAA\nW\ts\t0\tx\t0\t4\t>a\n")["status"], "unsupported")
        result = self.gfa("S\ta\tAAAA\nC\ta\t+\ta\t+\t0\t4M\n")
        self.assertFalse(result["complete"])
        self.assertEqual(result["unsupported_record_counts"], {"C": 1})

    def test_bad_references_duplicate_names_and_orientations_are_invalid(self):
        fixtures = ["S\ta\tAAAA\nS\ta\tCCCC\n", "S\ta\tAAAA\nL\ta\t?\ta\t+\t0M\n",
                    "S\ta\tAAAA\nL\ta\t+\tmissing\t+\t0M\n", "S\ta\tAAAA\nP\tp\ta+,a+\t1M,1M\n",
                    "S\ta\tAAAA\nP\ta\ta+\t*\n", "S\ta\tAAAA\tdp:f:nan\n"]
        for text in fixtures:
            with self.subTest(text=text):
                result = self.gfa(text)
                self.assertEqual(result["status"], "invalid")
                self.assertEqual(result["nodes"], [])

    def test_limits_fail_explicitly_without_exporting_partial_sequence_payloads(self):
        result = self.gfa("S\ta\tAAAA\nS\tb\tCCCC\n", limits={"max_nodes": 1})
        self.assertEqual(result["status"], "unsupported")
        self.assertFalse(result["complete"])
        self.assertEqual(result["nodes"], [])
        self.assertEqual(self.gfa("S\ta\tAAAA\n", limits={"max_source_bytes": 2})["status"], "unsupported")
        self.assertEqual(self.gfa("S\ta\tAAAA\n", limits={"max_line_bytes": 4})["status"], "unsupported")

    def test_non_numeric_tag_error_does_not_echo_sequence_like_payload(self):
        result = self.gfa("S\ta\tAAAA\tdp:f:ACGTACGTSECRET\n")
        self.assertEqual(result["status"], "invalid")
        self.assertNotIn("ACGTACGTSECRET", json.dumps(result))

    def test_flye_claims_do_not_turn_n_into_verified_linear_topology(self):
        path = self.root / "assembly_info.txt"
        text = "#seq_name\tlength\tcov.\tcirc.\trepeat\tmult.\talt_group\tgraph_path\ncontig_1\t10\t20\tY\tN\t1\t*\t1\ncontig_2\t8\t15\tN\tN\t1\t*\t2\n"
        path.write_text(text)
        result = parse_flye_assembly_info(path)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["contigs"][0]["reported_circularity"], "circular")
        self.assertEqual(result["contigs"][1]["reported_circularity"], "not_circular")
        self.assertIn("not proven linear", result["contigs"][1]["claim_scope"])
        self.assertEqual(path.read_text(), text)
        self.assertEqual(parse_flye_assembly_info(None)["status"], "missing")

    def test_invalid_flye_rows_and_unknown_formats_stay_unavailable(self):
        path = self.root / "info.txt"
        path.write_text("some other file\n")
        self.assertEqual(parse_flye_assembly_info(path)["status"], "unsupported")
        path.write_text("#seq_name\tlength\tcov.\tcirc.\na\t-1\t20\tY\n")
        self.assertEqual(parse_flye_assembly_info(path)["status"], "invalid")

    def test_plassembler_final_claims_are_whitelisted_and_source_labelled(self):
        path = self.root / "benchmark_summary.tsv"
        path.write_text("contig\tlength\tmean_depth_long\tsequence\tcircularity\na\t12\t20.0\tSECRETBASES\tcircular\nb\t10\t15\tAAAACCCC\tlinear\n")
        result = parse_plassembler_summary(path)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["source"]["kind"], "plassembler_summary")
        self.assertEqual(result["contigs"][0]["reported_circularity"], "circular")
        self.assertEqual(result["contigs"][1]["reported_circularity"], "not_circular")
        self.assertNotIn("mean_depth_long", json.dumps(result))
        self.assertNotIn("SECRETBASES", json.dumps(result))
        self.assertNotIn("AAAACCCC", json.dumps(result))


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.assembly = self.root / "assembly.fasta"
        self.assembly.write_bytes(b"generic placeholder assembly bytes\n")
        self.record = {"status": "fail", "tool": "flye", "assembly_file": "assembly.fasta", "assembly_sha256": digest(self.assembly)}
        self.execution = self.root / "execution.json"
        save(self.execution, self.record)
        self.gfa = self.root / "assembly_graph.gfa"
        self.gfa.write_text("S\t1\tACGT\nL\t1\t+\t1\t+\t0M\n")
        self.sidecar = self.root / "graph_artifacts.json"

    def collect(self, **kwargs):
        result = build_graph_artifacts(self.execution, self.assembly, self.gfa, **kwargs)
        save(self.sidecar, result)
        return result

    def test_checked_sidecar_attachment_is_hash_bound_and_read_only(self):
        self.collect()
        original = copy.deepcopy(self.record)
        source_bytes = self.execution.read_bytes()
        result = attach_graph_artifacts(self.record, self.execution)
        self.assertEqual(result["graph_artifacts"]["status"], "available")
        self.assertTrue(result["graph_artifacts"]["attachment"]["execution_hash_verified"])
        self.assertEqual(self.record, original)
        self.assertEqual(self.execution.read_bytes(), source_bytes)
        self.assertNotIn("ACGT", json.dumps(result))

    def test_stale_execution_and_assembly_hashes_are_not_attached(self):
        self.collect()
        self.execution.write_text(self.execution.read_text() + "\n")
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")
        self.collect()
        changed = {**self.record, "assembly_sha256": "0" * 64}
        self.assertEqual(attach_graph_artifacts(changed, self.execution)["graph_artifacts"]["status"], "not_collected")

    def test_missing_sidecar_or_execution_context_does_not_trigger_raw_parsing(self):
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")
        self.collect()
        self.assertEqual(attach_graph_artifacts(self.record)["graph_artifacts"]["status"], "not_collected")
        self.gfa.unlink()
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "available")

    def test_sequence_field_injection_is_rejected_instead_of_published(self):
        result = self.collect()
        result["graph"]["nodes"][0]["sequence"] = "DONOTEXPORT"
        save(self.sidecar, result)
        attached = attach_graph_artifacts(self.record, self.execution)
        self.assertEqual(attached["graph_artifacts"]["status"], "not_collected")
        self.assertNotIn("DONOTEXPORT", json.dumps(attached))

    def test_explicit_collected_missing_state_survives_for_failed_execution(self):
        failed = {"status": "error", "tool": "flye"}
        save(self.execution, failed)
        save(self.sidecar, build_graph_artifacts(self.execution, None, source_role="partial_output", allow_failed=True))
        self.assertEqual(attach_graph_artifacts(failed, self.execution)["graph_artifacts"]["status"], "missing")

    def test_builder_rejects_wrong_assembly_and_preserves_source_roles(self):
        self.collect(source_role="initial_flye")
        result = json.loads(self.sidecar.read_text())
        self.assertEqual(result["graph"]["source"]["role"], "initial_flye")
        self.assembly.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.collect()

    def test_miniasm_unitig_metadata_is_attachable_with_verified_sources(self):
        self.gfa.write_text("S\tutg000001c\tACGT\nL\tutg000001c\t+\tutg000001c\t+\t0M\n")
        result = self.collect(assembly_info_path=self.gfa, assembly_info_kind="miniasm")
        self.assertEqual(result["assembly_info"]["format"], "Miniasm unitig identifiers in GFA")
        attached = attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]
        self.assertEqual(attached["status"], "available")
        self.assertEqual(attached["assembly_info"]["contigs"][0]["reported_circularity"], "circular")

    def test_plassembler_builder_uses_final_summary_parser(self):
        info = self.root / "benchmark_summary.tsv"
        info.write_text("contig\tlength\tcircularity\na\t4\tcircular\n")
        result = self.collect(assembly_info_path=info, assembly_info_kind="plassembler")
        self.assertEqual(result["assembly_info"]["source"]["kind"], "plassembler_summary")
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "available")

    def test_plassembler_not_circular_token_is_preserved_and_attachable(self):
        info = self.root / "summary.tsv"
        info.write_text("contig\tlength\tcircularity\na\t4\tnot_circular\n")
        result = self.collect(assembly_info_path=info, assembly_info_kind="plassembler")
        claim = result["assembly_info"]["contigs"][0]
        self.assertEqual(claim["reported_circularity"], "not_circular")
        self.assertEqual(claim["reported_circularity_raw"], "not_circular")
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "available")

    def test_failed_graph_is_execution_bound_without_primary_verification(self):
        for state in ("error", "timeout"):
            with self.subTest(state=state):
                failed = {"status": state, "tool": "flye", "assembly_sha256": self.record["assembly_sha256"]}
                save(self.execution, failed)
                before = self.execution.read_bytes(), self.gfa.read_bytes()
                document = build_graph_artifacts(self.execution, None, self.gfa, source_role="initial_flye", allow_failed=True)
                save(self.sidecar, document)
                attached = attach_graph_artifacts(failed, self.execution)
                meta = attached["graph_artifacts"]
                self.assertEqual(attached["status"], state)
                self.assertEqual(meta["status"], "available")
                self.assertIsNone(meta["input_hashes"]["assembly_sha256"])
                self.assertFalse(meta["validation"]["assembly_bytes_verified"])
                self.assertFalse(meta["attachment"]["assembly_record_hash_verified"])
                self.assertTrue(meta["attachment"]["failed_execution_state_verified"])
                self.assertEqual(meta["graph"]["source"]["file_sha256"], digest(self.gfa))
                self.assertEqual(meta["failed_execution_provenance"]["recorded_primary_assembly_sha256"], self.record["assembly_sha256"])
                self.assertEqual(before, (self.execution.read_bytes(), self.gfa.read_bytes()))
                self.assertEqual(attach_graph_artifacts(dict(failed, status="pass"), self.execution)["graph_artifacts"]["status"], "not_collected")
                document["failed_execution_provenance"]["execution_status"] = "timeout" if state == "error" else "error"
                save(self.sidecar, document)
                self.assertEqual(attach_graph_artifacts(failed, self.execution)["graph_artifacts"]["status"], "not_collected")

    def test_failed_metadata_admission_cannot_bypass_successful_assembly_checks(self):
        with self.assertRaises(ValueError):
            build_graph_artifacts(self.execution, None, self.gfa, source_role="partial_output", allow_failed=True)
        failed = {"status": "error", "tool": "flye"}
        save(self.execution, failed)
        for options in ({"source_role": "initial_flye"}, {"source_role": "final", "allow_failed": True}):
            with self.assertRaises(ValueError):
                build_graph_artifacts(self.execution, None, self.gfa, **options)
        document = build_graph_artifacts(self.execution, None, self.gfa, source_role="partial_output", allow_failed=True)
        document["validation"]["assembly_bytes_verified"] = True
        save(self.sidecar, document)
        self.assertEqual(attach_graph_artifacts(failed, self.execution)["graph_artifacts"]["status"], "not_collected")
        save(self.execution, {"status": "running", "tool": "flye"})
        with self.assertRaises(ValueError):
            build_graph_artifacts(self.execution, None, self.gfa, source_role="partial_output", allow_failed=True)

    def test_forged_failed_provenance_cannot_attach_to_scored_execution(self):
        failed = {"status": "error", "tool": "flye", "assembly_sha256": self.record["assembly_sha256"]}
        save(self.execution, failed)
        document = build_graph_artifacts(self.execution, None, self.gfa, source_role="partial_output", allow_failed=True)
        save(self.execution, self.record)
        document["input_hashes"]["execution_sha256"] = digest(self.execution)
        document["failed_execution_provenance"]["execution_sha256"] = digest(self.execution)
        save(self.sidecar, document)
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")
        document.pop("failed_execution_provenance")
        save(self.sidecar, document)
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")

    def test_collection_provenance_can_be_retained_without_raw_source_contents(self):
        result = self.collect()
        result["collection"] = {"source_role": "final", "candidate_files": [{"relative_path": "output/assembly_graph.gfa", "kind": "gfa", "role": "final", "status": "available"}],
                                "batch_id": "fixture", "execution_relative_path": "results/example/execution.json", "collected_at": "2026-11-05T00:00:00Z", "source_reads_modified": False, "sequence_exported": False, "checkpoint_policy": "Opaque checkpoints are not opened."}
        save(self.sidecar, result)
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "available")


    def test_collection_payload_is_typed_and_cannot_hide_sequences(self):
        for collection in ({"batch_id": {"payload": "SECRETBASES"}}, {"sequence": "SECRETBASES"},
                           {"candidate_files": [{"kind": "gfa", "role": "final", "status": "available", "sequence": "SECRETBASES"}]}):
            with self.subTest(collection=collection):
                document = self.collect()
                document["collection"] = collection
                save(self.sidecar, document)
                result = attach_graph_artifacts(self.record, self.execution)
                self.assertEqual(result["graph_artifacts"]["status"], "not_collected")
                self.assertNotIn("SECRETBASES", json.dumps(result))

    def test_graph_self_link_and_non_circular_tool_claim_remain_separate(self):
        info = self.root / "assembly_info.txt"
        info.write_text("#seq_name\tlength\tcov.\tcirc.\n1\t4\t10\tN\n")
        document = self.collect(assembly_info_path=info)
        self.assertEqual(document["graph"]["self_loop_segment_ids"], ["1"])
        self.assertEqual(document["assembly_info"]["contigs"][0]["reported_circularity"], "not_circular")
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "available")

    def test_mixed_stages_and_fabricated_self_link_labels_are_rejected(self):
        document = self.collect()
        document["graph"]["self_loop_segment_ids"] = ["not-an-observed-node"]
        save(self.sidecar, document)
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")
        document = self.collect()
        document["assembly_info"]["source"]["role"] = "initial_flye"
        save(self.sidecar, document)
        self.assertEqual(attach_graph_artifacts(self.record, self.execution)["graph_artifacts"]["status"], "not_collected")

    def test_serialized_sidecar_limit_preserves_explicit_unsupported_state(self):
        self.gfa.write_text("".join("S\t" + str(i) + "\tACGT\n" for i in range(100)))
        document = self.collect(limits={"max_sidecar_bytes": 4096})
        self.assertEqual(document["status"], "unsupported")
        self.assertEqual(document["graph"]["nodes"], [])
        self.assertLessEqual(len(json.dumps(document, sort_keys=True).encode()), 4096)


if __name__ == "__main__":
    unittest.main()
