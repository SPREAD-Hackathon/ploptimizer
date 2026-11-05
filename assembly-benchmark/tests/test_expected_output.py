"""Reference schematics must preserve inventory and declared topology."""

import copy
import unittest

from pipeline.expected_output import expected_molecules, render_expected_output


class ExpectedOutputTests(unittest.TestCase):
    def setUp(self):
        self.case = {"replicons": [
            {"replicon_name": "chromosome", "molecule_type": "chromosome", "length_bp": 1000000, "topology": "circular", "refseq_accession": "synthetic-c"},
            {"replicon_name": "large fixture", "molecule_type": "plasmid", "length_bp": 100000, "topology": "circular", "refseq_accession": "synthetic-p1"},
            {"replicon_name": "small fixture", "molecule_type": "plasmid", "length_bp": 1000, "topology": "circular", "refseq_accession": "synthetic-p2"}]}

    def test_chromosome_and_two_plasmids_are_three_separate_reference_circles(self):
        before = copy.deepcopy(self.case)
        body = render_expected_output(self.case, {"tool": "flye"})
        self.assertEqual(body.count('<circle '), 3)
        self.assertIn('1 chromosome + 2 plasmids', body)
        self.assertIn('1,000,000 bp', body)
        self.assertIn('synthetic-p2', body)
        self.assertIn('not an observed assembly graph', body)
        self.assertEqual(self.case, before)

    def test_plassembler_final_target_excludes_chromosome(self):
        record = {"tool": "plassembler"}
        self.assertEqual(len(expected_molecules(self.case, record)), 2)
        body = render_expected_output(self.case, record)
        self.assertEqual(body.count('<circle '), 2)
        self.assertNotIn('synthetic-c', body)
        self.assertIn('2 plasmids', body)

    def test_chromosome_only_negative_control_does_not_expect_a_plasmid_circle(self):
        self.case["replicons"] = self.case["replicons"][:1]
        self.assertEqual(render_expected_output(self.case, {"tool": "flye"}).count('<circle '), 1)
        body = render_expected_output(self.case, {"tool": "plassembler"})
        self.assertNotIn('<circle ', body)
        self.assertIn('No plasmids expected', body)

    def test_linear_and_unknown_topology_never_become_circles(self):
        self.case["replicons"][0]["topology"] = "linear"
        self.case["replicons"][1].pop("topology")
        body = render_expected_output(self.case, {"tool": "raven"})
        self.assertEqual(body.count('<circle '), 1)
        self.assertEqual(body.count('<path '), 2)
        self.assertIn('stroke-dasharray=', body)

    def test_labels_are_escaped_and_missing_inventory_is_explicit(self):
        self.case["replicons"][0]["replicon_name"] = '<script>fixture</script>'
        self.assertNotIn('<script>', render_expected_output(self.case, {"tool": "flye"}))
        self.assertIn('No reference inventory recorded', render_expected_output({}, {"tool": "flye"}))


if __name__ == "__main__":
    unittest.main()
