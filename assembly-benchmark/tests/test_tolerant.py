"""Independent sequence fixtures for the separately versioned tolerant endpoint."""

import importlib.util
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import ROOT, reverse_complement, write_fasta
from pipeline.tolerant import evaluate_tolerant

HAS_EDLIB = importlib.util.find_spec('edlib') is not None


class TolerantTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.cache').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / '.cache')
        self.path = Path(self.temporary.name)
        rng = random.Random(4091)
        self.reference = ''.join(rng.choice('ACGT') for _ in range(1000))
        self.chromosome = ''.join(rng.choice('ACGT') for _ in range(12000))
        self.case = {'replicons': [
            {'refseq_accession': 'synthetic-chromosome', 'replicon_name': 'chromosome', 'molecule_type': 'chromosome', 'topology': 'circular', 'length_bp': 12000},
            {'refseq_accession': 'NC_017662.1', 'replicon_name': 'synthetic-pRK2-fixture', 'molecule_type': 'plasmid', 'topology': 'circular', 'length_bp': 1000}]}
        self.write_truth()

    def tearDown(self):
        self.temporary.cleanup()

    def write_truth(self):
        write_fasta(self.path / 'truth.fa', {'synthetic-chromosome': self.chromosome, 'NC_017662.1': self.reference})

    def evaluate(self, records, **kwargs):
        write_fasta(self.path / 'assembly.fa', records)
        return evaluate_tolerant(self.case, self.path / 'truth.fa', self.path / 'assembly.fa', **kwargs)

    def test_missing_dependency_is_unscored(self):
        with patch('pipeline.tolerant.importlib.import_module', side_effect=ImportError('not installed')):
            self.assertEqual(self.evaluate({'p': self.reference})['status'], 'unscored')

    def test_invalid_or_unbounded_policy_is_rejected(self):
        for policy in ({'minimum_alignment_identity': 0}, {'maximum_length_ratio': float('inf')}, {'maximum_reference_length': 1000000}, {'surprise': 1}):
            with self.assertRaises(ValueError):
                self.evaluate({'p': self.reference}, policy=policy)

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_rotation_reverse_complement_and_large_chromosome(self):
        rotated = self.reference[417:] + self.reference[:417]
        result = self.evaluate({'chromosome': self.chromosome, 'p': reverse_complement(rotated)})
        self.assertEqual(result['status'], 'pass', result)
        self.assertEqual(result['replicons'][0]['reference_coverage'], 1)
        self.assertEqual(result['replicons'][0]['alignment_identity'], 1)

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_small_indel_and_substitution_are_tolerated(self):
        for changed in (self.reference[:400] + self.reference[403:], self.reference[:400] + 'ACT' + self.reference[400:]):
            result = self.evaluate({'p': changed})
            self.assertEqual(result['status'], 'pass', result)
        changed = list(self.reference)
        for index in (150, 350, 750):
            changed[index] = 'A' if changed[index] != 'A' else 'C'
        self.assertEqual(self.evaluate({'p': ''.join(changed)})['status'], 'pass')

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_full_coverage_with_too_many_errors_fails(self):
        changed = list(self.reference)
        for index in range(50, 1000, 100):
            changed[index] = 'A' if changed[index] != 'A' else 'C'
        self.assertEqual(self.evaluate({'p': ''.join(changed)})['status'], 'fail')

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_fragments_do_not_combine_into_one_dedicated_molecule(self):
        self.assertEqual(self.evaluate({'a': self.reference[:600], 'b': self.reference[600:]})['status'], 'fail')
        self.assertEqual(self.evaluate({'a': self.reference[:985]})['status'], 'fail')

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_duplicate_and_near_complete_second_copy_fail(self):
        self.assertEqual(self.evaluate({'a': self.reference, 'b': reverse_complement(self.reference)})['status'], 'fail')
        result = self.evaluate({'a': self.reference, 'partial-copy': self.reference[:960]})
        self.assertEqual(result['status'], 'fail', result)

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_terminal_overlap_tandem_and_join_never_pass(self):
        for records in ({'p': self.reference + self.reference[:20]}, {'p': self.reference * 2},
                        {'p': self.reference + self.chromosome[:3000]},
                        {'p': self.reference, 'joined-copy': self.chromosome[:3000] + self.reference[277:] + self.reference[:277]}):
            self.assertIn(self.evaluate(records)['status'], {'fail', 'unscored'})

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_repetitive_or_shared_assignment_is_unscored(self):
        self.reference = 'ACGT' * 250
        self.write_truth()
        self.assertEqual(self.evaluate({'p': self.reference})['status'], 'unscored')

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_unsupported_topology_and_ambiguous_bases_are_unscored(self):
        self.case['replicons'][1]['topology'] = 'linear'
        self.assertEqual(self.evaluate({'p': self.reference})['status'], 'unscored')
        self.case['replicons'][1]['topology'] = 'circular'
        self.assertEqual(self.evaluate({'p': 'N' + self.reference[1:]})['status'], 'unscored')

    @unittest.skipUnless(HAS_EDLIB, 'Run in the pinned simulator environment with edlib')
    def test_one_contig_cannot_represent_two_indistinguishable_truth_plasmids(self):
        second = dict(self.case['replicons'][1], refseq_accession='NC_009653.1', replicon_name='synthetic-second-plasmid')
        self.case['replicons'].append(second)
        write_fasta(self.path / 'truth.fa', {'synthetic-chromosome': self.chromosome, 'NC_017662.1': self.reference, 'NC_009653.1': self.reference})
        self.assertEqual(self.evaluate({'one': self.reference})['status'], 'unscored')
