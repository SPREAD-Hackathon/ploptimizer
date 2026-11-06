import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import digest
from pipeline.stage_notes import attach_stage_facts


class StageNoteTests(unittest.TestCase):
    def test_only_matching_saved_execution_and_log_receive_reviewed_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / 'reviews/stages'
            notes.mkdir(parents=True)
            directory = root / 'artifacts/b/results/example/tool'
            directory.mkdir(parents=True)
            (directory / 'execution.json').write_text('{}')
            log = directory / 'stderr.log'
            log.write_text('Saved process history')
            record = {'scenario_id':'example', 'tool':'tool', 'assembly_sha256':'a', 'truth_sha256':'t'}
            fact = {'label':'Process', 'value':'Reconstructed output', 'kind':'text', 'source':'saved log'}
            note = {'batch_id':'b', 'scenario_id':'example', 'tool':'tool',
                    'hashes':{'assembly_sha256':'a', 'truth_sha256':'t'},
                    'execution_sha256':digest(directory / 'execution.json'),
                    'log_sha256':digest(log), 'facts':[fact]}
            (notes / 'review.json').write_text(json.dumps(note))
            with patch('pipeline.stage_notes.ROOT', root):
                summary = {'facts':[]}
                attach_stage_facts(summary, record, 'b', root / 'artifacts')
                self.assertEqual(summary['facts'][0]['value'], fact['value'])
                log.write_text('Different process history')
                summary = {'facts':[]}
                attach_stage_facts(summary, record, 'b', root / 'artifacts')
                self.assertEqual(summary['facts'], [])
