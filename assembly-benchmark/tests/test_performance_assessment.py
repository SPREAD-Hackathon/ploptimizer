"""Synthetic cases for Wick completion and source-bound mapping evidence."""
import tempfile
import unittest
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from pipeline.common import digest, fasta, load, save, write_fasta
from pipeline.performance.assessment import (assess, classify, mapping_command,
    parse_alignments, summarise_alignments, _assembly_input)
from pipeline.performance.vendor.wick_assess_assembly import Alignment


def alignment(name, span, start=0, matches=None, cigar=None, length=1000, query='contig'):
    return Alignment('\t'.join(map(str, [query, span, 0, span, '+', name, length*3,
        start, start+span, span if matches is None else matches, span, 60,
        'cg:Z:'+(cigar or f'{span}M')])))


class PerformanceMetricTests(unittest.TestCase):
    def setUp(self):
        self.case={'id':'fixture','replicons':[
            {'refseq_accession':'chr','molecule_type':'chromosome','length_bp':1000},
            {'refseq_accession':'plasmid','molecule_type':'plasmid','length_bp':100}]}

    def test_completion_is_longest_span_not_union_and_can_exceed_one(self):
        records=summarise_alignments(self.case,[alignment('chr',600),
            alignment('chr',600,start=600),alignment('plasmid',110,length=100)])
        self.assertEqual(records[0]['contiguity'],.6)
        self.assertFalse(records[0]['complete'])
        self.assertEqual(records[1]['contiguity'],1.1)
        self.assertTrue(records[1]['complete'])
        self.assertEqual(classify(records,2),'incomplete')

    def test_tie_uses_earliest_reference_start_like_upstream(self):
        records=summarise_alignments(self.case,[alignment('chr',990,100,query='later'),
            alignment('chr',990,0,query='earlier'),alignment('plasmid',99,length=100)])
        self.assertEqual(records[0]['contig_id'],'earlier')
        self.assertEqual(classify(records,3),'fully_complete')

    def test_unmeasured_identity_is_null_and_indels_follow_cigar(self):
        records=summarise_alignments(self.case,[alignment('chr',250),
            alignment('plasmid',99,matches=97,cigar='50M2D47M',length=100)])
        self.assertFalse(records[0]['identity_measured'])
        self.assertIsNone(records[0]['identity'])
        self.assertIsNone(records[0]['max_indel_bp'])
        self.assertEqual(records[1]['identity'],97/99)
        self.assertEqual(records[1]['max_indel_bp'],2)

    def test_absent_plasmid_preserves_chromosome_complete_outcome(self):
        records=summarise_alignments(self.case,[alignment('chr',990)])
        self.assertEqual(classify(records,1),'chromosome_complete')
        self.assertEqual(classify(records,0),'empty')
        self.assertEqual(records[1]['contiguity'],0)
        self.assertIsNone(records[1]['identity'])

    def test_mapper_flags_and_tripled_inventory(self):
        self.assertEqual(mapping_command('tripled.fasta','assembly.fasta',4),
            ['minimap2','-c','-t','4','-x','asm20','-r','10000','-g','10000',
             '-z','1000,500','tripled.fasta','assembly.fasta'])
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'alignment.paf'
            path.write_text('q\t100\t0\t100\t+\tchr\t300\t0\t100\t100\t100\t60\tcg:Z:100M\n')
            self.assertEqual(len(parse_alignments(path,{'chr':100},{'q':100})),1)
            with self.assertRaisesRegex(ValueError,'inventories'):
                parse_alignments(path,{'chr':101},{'q':100})


class PerformanceSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.batch=Path(self.temporary.name)/'batch'
        self.directory=self.batch/'results/fixture/plassembler'
        (self.directory/'output').mkdir(parents=True)
        self.execution=self.directory/'execution.json'
        self.input=self.batch/'cases/fixture';self.input.mkdir(parents=True)
        write_fasta(self.input/'truth.fasta',{'chr':'ACGT','plasmid':'TT'})
        self.case={'id':'fixture','replicons':[
            {'refseq_accession':'chr','molecule_type':'chromosome','length_bp':4},
            {'refseq_accession':'plasmid','molecule_type':'plasmid','length_bp':2}]}
        self.assembly=self.directory/'output/benchmark_plasmids.fasta'
        write_fasta(self.assembly,{'contig':'TT'})
        self.chromosome=self.directory/'output/chromosome.fasta'
        write_fasta(self.chromosome,{'contig':'ACGT'})
        self.record={'scenario_id':'fixture','tool':'plassembler','status':'fail',
            'assembly_file':str(self.assembly.relative_to(self.batch)),
            'assembly_sha256':digest(self.assembly),'retained_chromosome_sha256':digest(self.chromosome),
            'truth_sha256':digest(self.input/'truth.fasta'),'reads_sha256':'a'*64}
        save(self.execution,self.record)
        save(self.input/'input.json',{'truth_sha256':self.record['truth_sha256'],
            'reads_sha256':self.record['reads_sha256']})

    def test_plassembler_joins_actual_final_sources_not_initial_flye(self):
        initial=self.directory/'output/flye_output';initial.mkdir()
        write_fasta(initial/'assembly.fasta',{'wrong':'AAAA'})
        output=self.directory/'performance';output.mkdir()
        combined,sources,origins=_assembly_input(self.record,self.directory,self.batch,output)
        self.assertEqual(fasta(combined),{'final_plasmids:contig':'TT','retained_chromosome:contig':'ACGT'})
        self.assertEqual(len(origins),2)
        self.assertFalse(any('flye_output' in row['file'] for row in sources))

    def test_mapper_failure_is_error_not_a_missing_molecule(self):
        def run(command,**kwargs):
            if '--version' in command:return SimpleNamespace(stdout='2.31-r1302',stderr='')
            raise subprocess.CalledProcessError(1,command)
        with patch('pipeline.performance.assessment.subprocess.run',side_effect=run):
            result=assess(self.case,self.execution,self.batch)
        self.assertEqual(result['status'],'error')
        self.assertEqual(result['genome_outcome'],'execution_error')
        self.assertEqual(result['failure_scope'],'assessment')
        self.assertEqual(result['replicons'],[])
        self.assertEqual(load(self.execution),self.record)

    def test_diagnostic_exact_failure_can_be_broad_completion(self):
        def run(command,**kwargs):
            if '--version' in command:return SimpleNamespace(stdout='2.31-r1302',stderr='')
            kwargs['stdout'].write('final_plasmids:contig\t2\t0\t2\t+\tplasmid\t6\t0\t2\t2\t2\t60\tcg:Z:2M\n')
            kwargs['stdout'].write('retained_chromosome:contig\t4\t0\t4\t+\tchr\t12\t0\t4\t4\t4\t60\tcg:Z:4M\n')
            return SimpleNamespace(returncode=0)
        with patch('pipeline.performance.assessment.subprocess.run',side_effect=run):
            result=assess(self.case,self.execution,self.batch)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['execution_status'],'fail')
        self.assertEqual(result['genome_outcome'],'fully_complete')
        self.assertTrue(result['complete_all'])

    def test_timeout_has_no_invented_sequence_assessment(self):
        self.record.update(status='timeout',error='Two-hour time limit');save(self.execution,self.record)
        with patch('pipeline.performance.assessment.subprocess.run') as process:
            result=assess(self.case,self.execution,self.batch)
        process.assert_not_called()
        self.assertEqual(result['genome_outcome'],'did_not_complete')
        self.assertIsNone(result['complete_all'])
        self.assertEqual(result['replicons'],[])

    def test_resource_labels_separate_worker_wall_and_process_memory(self):
        self.record.update(status='timeout', elapsed_seconds=123, peak_memory_kb=456)
        save(self.execution,self.record)
        result=assess(self.case,self.execution,self.batch)
        self.assertEqual(result['elapsed_seconds'],123)
        self.assertEqual(result['peak_memory_kb'],456)
        self.assertIn('input verification and exact assessment',result['elapsed_scope'])
        self.assertIn('excludes downloads and scheduler wait',result['elapsed_scope'])
        self.assertIn('assembler process tree',result['memory_scope'])
        self.assertEqual(load(self.execution),self.record)
