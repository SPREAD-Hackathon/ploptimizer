import importlib.util
import tempfile
import unittest
from pathlib import Path

from pipeline.common import ROOT

spec = importlib.util.spec_from_file_location('length_inventory', ROOT/'scripts/collect_length_inventories.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class LengthInventoryTests(unittest.TestCase):
    def test_multiline_lengths_identifiers_and_empty_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'assembly.fa'
            path.write_bytes(b'>one description\nACGT\nAC\n>two\nTTT\n')
            self.assertEqual(collector.inventory(path), [{'id':'one','length_bp':6},{'id':'two','length_bp':3}])
            path.write_bytes(b'')
            self.assertEqual(collector.inventory(path),[])

    def test_duplicate_names_and_invalid_order_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'assembly.fa'
            for content in (b'ACGT\n',b'>x\nAC\n>x\nGT\n',b'>x\n'):
                path.write_bytes(content)
                with self.assertRaises(ValueError): collector.inventory(path)


class LengthMetricsTests(unittest.TestCase):
    def test_nx_weighted_by_bases_not_record_count(self):
        from pipeline.length_metrics import distribution
        result=distribution([{'id':str(i),'length_bp':v} for i,v in enumerate([60,25,15])])
        self.assertEqual((result['total_bp'],result['n50_bp'],result['n90_bp'],result['median_bp']),(100,60,15,25))

    def test_unknown_or_incomplete_inventory_never_pretends_total_or_n50(self):
        from pipeline.length_metrics import distribution
        for rows,complete in [([{'id':'x','length_bp':50},{'id':'y','length_bp':None}],True),([{'id':'x','length_bp':50}],False)]:
            result=distribution(rows,complete)
            self.assertEqual(result['status'],'partial')
            self.assertIsNone(result['total_bp'])
            self.assertIsNone(result['n50_bp'])
        self.assertEqual(distribution([])['total_bp'],0)
        self.assertIsNone(distribution([])['n50_bp'])

    def test_lengths_are_not_double_counted_from_paths_or_orientations(self):
        from pipeline.length_metrics import build_length_metrics
        artifact={'graph':{'status':'available','complete':True,'nodes':[{'id':'s','length_bp':40}], 'paths':[{'steps':['s+','s-']}], 'source':{'role':'intermediate'}},'assembly_info':{}}
        result=build_length_metrics({'scenario_id':'case','tool':'flye'},artifact,'batch')
        self.assertEqual(result['graph_segments']['total_bp'],40)
        self.assertIsNone(result['scored_contigs']['total_bp'])
        self.assertEqual(result['graph_segments']['source']['role'],'intermediate')

    def test_final_inventory_is_hash_bound_and_empty_is_distinct_from_missing(self):
        import json
        from pipeline.length_metrics import saved_inventory
        from pipeline.common import digest
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'batch/results/case/flye';folder.mkdir(parents=True)
            record={'scenario_id':'case','tool':'flye','status':'pass','assembly_sha256':'a'*64,'evaluation':{'contig_count':0}}
            execution=folder/'execution.json';execution.write_text(json.dumps(record))
            source={'schema_version':1,'kind':'scored_fasta_lengths','status':'complete','assembly_sha256':'a'*64,'execution_sha256':digest(execution),'producer_sha256':'b'*64,'contigs':[]}
            path=folder/'length_inventory.json';path.write_text(json.dumps(source))
            self.assertEqual(saved_inventory(record,'batch',root)['total_bp'],0)
            source['assembly_sha256']='c'*64;path.write_text(json.dumps(source))
            with self.assertRaisesRegex(ValueError,'provenance'):saved_inventory(record,'batch',root)
