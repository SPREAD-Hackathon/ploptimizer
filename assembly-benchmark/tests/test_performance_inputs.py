"""Frozen published bytes are checked without simulating reads."""
import gzip
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pipeline.common import load
from pipeline.execution import command
from pipeline.performance.inputs import cases, fastq_statistics
from pipeline.performance.archive import ranged_response

class PerformanceInputTests(unittest.TestCase):
    def test_original_balance_is_frozen(self):
        root=Path(__file__).resolve().parents[1]
        planned=cases(load(root/'references/performance-wick/selection-50.json'))
        self.assertEqual(len(planned),50)
        self.assertEqual(sum(bool(c['plasmid_count']) for c in planned),25)
        self.assertEqual(sum(c['plasmid_count'] for c in planned),50)
        self.assertEqual(len({c['fingerprint'] for c in planned}),50)

    def test_fastq_crc_counts_and_n50(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'reads.gz'
            with gzip.open(path,'wb') as stream:stream.write(b'@a\nACG\n+\nIII\n@b\nACGTA\n+\nIIIII\n')
            stats=fastq_statistics(path)
            self.assertEqual((stats['read_count'],stats['total_read_bases'],stats['read_n50_bp']),(2,8,5))
            data=bytearray(path.read_bytes());data[-8]^=1;path.write_bytes(data)
            with self.assertRaises((gzip.BadGzipFile,EOFError)):fastq_statistics(path)

    def test_sequence_quality_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'reads.gz'
            with gzip.open(path,'wb') as stream:stream.write(b'@a\nACGT\n+\nIII\n')
            with self.assertRaisesRegex(ValueError,'length mismatch'):fastq_statistics(path)

    def test_range_cannot_fall_back_to_full_archive(self):
        response=io.BytesIO(b'wrong');response.status=200;response.headers={}
        with patch('urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(ValueError,'refusing a whole-archive'):
                ranged_response({'size':100,'download_url':'https://example.invalid/archive'},0,5)

    def test_raw_flags_are_explicit(self):
        config={'threads':4,'plassembler_chromosome_threshold':400000}
        self.assertIn('--nano-hq',command('flye','reads',Path('/out'),config))
        self.assertNotIn('--raw_flag',command('plassembler','reads',Path('/out'),config))
        raw=dict(config,flye_input_mode='nano-raw',plassembler_raw_flag=True)
        self.assertIn('--nano-raw',command('flye','reads',Path('/out'),raw))
        self.assertIn('--raw_flag',command('plassembler','reads',Path('/out'),raw))

    def test_reference_md5_and_ids_are_checked(self):
        import hashlib,tarfile
        from pipeline.performance.inputs import download_references
        datasets=[{'id':f'{n:03d}_GCF_000000001.1','replicons':[{'refseq_accession':f'ref{n}','length_bp':4}]} for n in range(50)]
        payload=io.BytesIO()
        with tarfile.open(fileobj=payload,mode='w:gz') as archive:
            for n,case in enumerate(datasets):
                data=f'>ref{n}\nACGT\n'.encode();member=tarfile.TarInfo('reference_genomes/'+case['id']+'.fasta');member.size=len(data);archive.addfile(member,io.BytesIO(data))
        data=payload.getvalue();source={'name':'references.tar.gz','size':len(data),'computed_md5':hashlib.md5(data).hexdigest()}
        selection={'datasets':datasets,'archives':{'references':source}}
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);(directory/source['name']).write_bytes(data)
            self.assertEqual(len(download_references(selection,directory)['selected']),50)
            bad=dict(selection,archives={'references':dict(source,computed_md5='0'*32)})
            with self.assertRaisesRegex(ValueError,'published bytes'):download_references(bad,directory)
