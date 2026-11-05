"""Comparison artefacts preserve coordinate conventions and bind source bytes."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('compare_existing_outputs',ROOT/'scripts/compare_existing_outputs.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


class ExistingComparisonTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'.cache').mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=ROOT/'.cache')
        self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)

    def test_original_inclusive_endpoints_become_half_open_without_losing_strand(self):
        path=self.root/'coordinates.tsv'
        path.write_text('2\t11\t20\t11\t10\t10\t99.5\t100\t100\tref\tquery\n')
        rows=MODULE.parse_coords(path,[{'id':'ref','length':100}],[{'id':'query','length':100}])
        self.assertEqual(rows[0]['reference_interval'],[1,11])
        self.assertEqual(rows[0]['query_interval'],[10,20])
        self.assertEqual(rows[0]['strand'],'-')
        self.assertEqual(rows[0]['original_endpoints_1based_inclusive'],[2,11,20,11])
        self.assertEqual(rows[0]['identity_percent'],99.5)

    def test_mismatching_coordinate_identity_is_rejected(self):
        path=self.root/'coordinates.tsv';path.write_text('1\t10\t1\t10\t10\t10\t100\t100\t100\tother\tquery\n')
        with self.assertRaisesRegex(ValueError,'identifiers'):
            MODULE.parse_coords(path,[{'id':'ref','length':100}],[{'id':'query','length':100}])

    def test_inventory_omits_sequence_and_handles_empty_coordinates(self):
        path=self.root/'toy.fasta';path.write_text('>toy-reference\nACGTAC\nGT\n')
        records=MODULE.inventory(path)
        self.assertEqual(records,[{'id':'toy-reference','length':8}])
        self.assertNotIn('ACGT',json.dumps(records))
        coordinates=self.root/'empty.tsv';coordinates.write_text('')
        self.assertEqual(MODULE.parse_coords(coordinates,records,records),[])

    def test_source_metadata_mismatch_is_rejected_before_comparison(self):
        batch=self.root/'runs/toy';execution=batch/'results/toy/tool/execution.json'
        execution.parent.mkdir(parents=True)
        execution.write_text(json.dumps({'scenario_id':'toy','tool':'tool','status':'pass'}))
        inputs=batch/'cases/toy/input.json';inputs.parent.mkdir(parents=True)
        inputs.write_text(json.dumps({'status':'valid','case':{'id':'toy'}}))
        task={'batch':'toy','scenario_id':'toy','tool':'tool','execution_relative_path':'results/toy/tool/execution.json','execution_sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'Execution metadata'):
            MODULE.prepare_inputs(self.root,task)

    def test_paths_cannot_escape_the_batch(self):
        with self.assertRaisesRegex(ValueError,'escapes'):
            MODULE.inside(self.root,'../outside')
        with self.assertRaisesRegex(ValueError,'relative'):
            MODULE.inside(self.root,'/outside')
