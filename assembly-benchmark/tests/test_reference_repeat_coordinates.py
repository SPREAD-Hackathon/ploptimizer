import unittest
from scripts.check_linear_reference_repeats import original_intervals


class ReferenceRepeatCoordinates(unittest.TestCase):
    def test_inverted_alignment_retains_original_end_offsets(self):
        row = {'reference_interval': [7, 87], 'query_interval': [10, 90],
               'strand': '-', 'identity_percent': 98.75, 'source_row': 4}
        result = original_intervals(row, 100, 201)
        self.assertEqual(result['left_interval'], [7, 87])
        self.assertEqual(result['right_interval'], [110, 190])
        self.assertEqual(result['orientation'], 'inverted')
        self.assertEqual(result['left_terminal_offset_bp'], 7)
        self.assertEqual(result['right_terminal_offset_bp'], 11)

    def test_direct_alignment_is_not_called_inverted(self):
        row = {'reference_interval': [0, 30], 'query_interval': [20, 50],
               'strand': '+', 'identity_percent': 100.0, 'source_row': 1}
        result = original_intervals(row, 50, 100)
        self.assertEqual(result['orientation'], 'direct')
        self.assertEqual(result['right_interval'], [70, 100])
        self.assertEqual(result['right_terminal_offset_bp'], 0)
