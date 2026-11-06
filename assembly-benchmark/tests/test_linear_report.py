import unittest
from pipeline.linear_report import reference_repeat_table


class LinearReferenceReport(unittest.TestCase):
    def test_offset_is_visible_and_coordinates_are_one_based(self):
        case = {'replicons': [{'refseq_accession': 'NZ_TEST.1', 'molecule_type': 'chromosome',
                'terminal_repeat_evidence': {'inter_arm_alignment': {
                    'selected_left_terminal_inverted_alignment': {
                        'left_interval': [0, 25460], 'right_interval': [7109023, 7134484],
                        'identity_percent': 99.99, 'right_terminal_offset_bp': 1290}}}}]}
        html = reference_repeat_table(case)
        self.assertIn('1–25,460', html)
        self.assertIn('7,109,024–7,134,484', html)
        self.assertIn('1,290 bp', html)
        self.assertIn('Inverted', html)

    def test_historical_results_do_not_gain_unmeasured_repeat_intervals(self):
        self.assertEqual(reference_repeat_table({'replicons': []}), '')
