import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from pipeline.common import ROOT

spec=importlib.util.spec_from_file_location('integrity_audit',ROOT/'scripts/audit_saved_artifacts.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class IntegrityAuditTests(unittest.TestCase):
    def test_detects_changed_input_bytes_without_confusing_missing_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);batch=root/'runs/batch';d=batch/'results/case/raven';inputs=batch/'cases/case';d.mkdir(parents=True);inputs.mkdir(parents=True)
            files={'reads.fastq.gz':b'input fixture bytes','truth.fasta':b'>fixture\nACGT\n'}
            for name,value in files.items():(inputs/name).write_bytes(value)
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            manifest={'status':'valid','reads_sha256':sha(inputs/'reads.fastq.gz'),'truth_sha256':sha(inputs/'truth.fasta')}
            (inputs/'input.json').write_text(json.dumps(manifest));(d/'assembly.fa').write_bytes(b'>output\nACGT\n')
            record={**manifest,'assembly_file':'results/case/raven/assembly.fa','assembly_sha256':sha(d/'assembly.fa')}
            (d/'execution.json').write_text(json.dumps(record));(d/'raven.cereal').write_bytes(b'opaque checkpoint: never parse')
            task={'batch':'batch','scenario_id':'case','tool':'raven','run_id':None,'status':'pass','assembly_sha256':record['assembly_sha256'],'execution_sha256':sha(d/'execution.json'),'input_manifest_sha256':sha(inputs/'input.json')}
            good=module.audit(root,{'executions':[task]})
            self.assertEqual(good['records_with_issues'],0)
            self.assertEqual(good['executions'][0]['raven_gfa_files'],[])
            (inputs/'reads.fastq.gz').write_bytes(b'changed input fixture')
            bad=module.audit(root,{'executions':[task]})
            self.assertEqual(bad['records_with_issues'],1)
            self.assertIn('reads_sha256',bad['executions'][0]['issues'])
