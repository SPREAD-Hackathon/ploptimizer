import importlib.util
import tempfile
import unittest
from pathlib import Path
from pipeline.common import ROOT

spec=importlib.util.spec_from_file_location('identity_collector',ROOT/'scripts/collect_graph_contig_identities.py')
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


class IdentityCollectorTests(unittest.TestCase):
    def test_identity_uses_content_not_equal_names_or_lengths(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'a.fa';g=Path(folder)/'g.gfa'
            a.write_text('>plasmid\nAAC\nCGG\n>same-name\nTTTTTT\n')
            g.write_text('S\tdifferent-name\taaccgg\nS\tplasmid\tAAACGG\nS\tsame-name\tAAAAAA\n')
            rows=collector.identities(a,g)
            self.assertEqual([(r['segment_id'],r['contig_id']) for r in rows],[('different-name','plasmid')])

    def test_missing_segment_sequence_does_not_imply_a_match(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'a.fa';g=Path(folder)/'g.gfa'
            a.write_text('>x\nAACCGG\n');g.write_text('S\tx\t*\tLN:i:6\n')
            self.assertEqual(collector.identities(a,g),[])


class IdentityMetadataTests(unittest.TestCase):
    def test_provenance_and_inventory_lengths_are_required(self):
        import json
        from pipeline.graph_contig_identity import load_graph_contig_identity
        from pipeline.common import digest
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);d=root/'batch/results/case/plassembler';d.mkdir(parents=True)
            record={'scenario_id':'case','tool':'plassembler','status':'pass','assembly_sha256':'a'*64}
            execution=d/'execution.json';execution.write_text(json.dumps(record))
            artifact={'graph':{'source':{'file_sha256':'b'*64},'nodes':[{'id':'segment','length_bp':6}]}}
            lengths={'scored_contigs':{'items':[{'id':'contig','length_bp':6}]}}
            value={'schema_version':1,'method':'whole_segment_contig_sha256_v1','assembly_sha256':'a'*64,'gfa_sha256':'b'*64,'execution_sha256':digest(execution),'producer_sha256':'c'*64,'associations':[{'segment_id':'segment','contig_id':'contig','length_bp':6,'sequence_sha256':'d'*64,'orientation':'+'}]}
            path=d/'graph_contig_identity.json';path.write_text(json.dumps(value))
            self.assertEqual(load_graph_contig_identity(record,artifact,'batch',root,lengths)['associations'],value['associations'])
            value['associations'][0]['length_bp']=7;path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'inventories'):load_graph_contig_identity(record,artifact,'batch',root,lengths)
            value['gfa_sha256']='e'*64;path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'hash'):load_graph_contig_identity(record,artifact,'batch',root,lengths)
