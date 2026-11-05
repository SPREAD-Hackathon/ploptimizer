import copy
import gzip
import random
import tempfile
import unittest
from pathlib import Path
from pipeline.common import ROOT, load, reverse_complement, write_fasta
from pipeline.cases import plan
from pipeline.determinism import assembly_tasks
from pipeline.reads import exact_reads
from pipeline.scoring import equivalent
from pipeline.execution import command


class LinearPanelTests(unittest.TestCase):
    def config(self):return load(ROOT/'config/linear-plasmids.json')

    def test_four_isolated_cases_sixteen_assemblies_and_no_native_mix(self):
        config=self.config();cases=plan(config)
        self.assertEqual(len(cases),4)
        self.assertEqual(len(assembly_tasks(config,cases)),16)
        self.assertTrue(all(c['category']=='S5' and len(c['replicons'])==1 and c['replicons'][0]['topology']=='linear' for c in cases))
        self.assertTrue(all(c['assembly_accession'] is None and c['truth_type']=='isolated_linear_reference_record' for c in cases))
        config['references']=['not-admitted']
        with self.assertRaises(ValueError):plan(config)

    def test_linear_end_reads_are_exact_end_complete_and_never_wrap(self):
        case=copy.deepcopy(plan(self.config())[0]);case['simulation'].update(chromosome_depth=20,length_mean=120,length_sd=30,length_min=50,length_max=200,linear_terminal_read_length=200)
        rng=random.Random(42);sequence=''.join(rng.choice('ACGT') for _ in range(1000));acc=case['replicons'][0]['refseq_accession'];case['replicons'][0]['length_bp']=1000
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=exact_reads(case,{acc:sequence},root)
            self.assertEqual(manifest['status'],'valid');row=manifest['replicons'][0]
            self.assertEqual(row['breadth'],1)
            self.assertGreaterEqual(row['left_terminal_read_count'],2);self.assertGreaterEqual(row['right_terminal_read_count'],2)
            with gzip.open(root/'read_origins.tsv.gz','rt') as stream:origins=[line.strip().split('\t') for line in stream][1:]
            with gzip.open(root/'reads.fastq.gz','rt') as stream:reads=stream.read().splitlines()
            for index,origin in enumerate(origins):
                _,_,start,length,strand=origin;start=int(start);length=int(length)
                self.assertLessEqual(start+length,len(sequence))
                expected=sequence[start:start+length]
                self.assertEqual(reads[4*index+1],reverse_complement(expected) if strand=='-' else expected)

    def test_linear_equivalence_preserves_ends(self):
        seq='AACCGGTA'
        self.assertTrue(equivalent(seq,reverse_complement(seq),'linear'))
        self.assertFalse(equivalent(seq,seq[2:]+seq[:2],'linear'))

    def test_plassembler_only_mode_is_explicit_and_does_not_keep_placeholder(self):
        config=self.config();argv=command('plassembler',Path('reads.fq'),Path('out'),config)
        self.assertIn('--no_chromosome',argv);self.assertNotIn('--keep_chromosome',argv)
        old=load(ROOT/'config/pilot.json');argv=command('plassembler',Path('reads.fq'),Path('out'),old)
        self.assertIn('--keep_chromosome',argv);self.assertNotIn('--no_chromosome',argv)

    def test_preparation_rechecks_literal_terminal_curation(self):
        from pipeline.linear_cases import validate_terminal_reference
        reference={'topology':'linear','terminal_repeat_evidence':{'literature_length_bp_approx':4,'exact_terminal_prefix_match_bp':4,'literature_window_mismatched_positions':0,'left_window_0based_half_open':[0,4],'right_window_0based_half_open':[6,10]}}
        validate_terminal_reference(reference,'ACGTTTACGT')
        with self.assertRaisesRegex(ValueError,'differs'):
            validate_terminal_reference(reference,'TCGTTTACGT')
