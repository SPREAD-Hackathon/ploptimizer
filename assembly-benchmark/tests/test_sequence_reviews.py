"""A checked observation cannot migrate to another assembly or execution."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline.common import ROOT,digest,save
from pipeline.reviews import attach_sequence_review


class SequenceReviewTests(unittest.TestCase):
    def test_only_matching_artefacts_receive_the_review_and_score_stays_failed(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as folder:
            root=Path(folder); batch=root/'runs/batch'; execution=batch/'execution.json'
            save(execution, {'original':'immutable'})
            record={'scenario_id':'case','tool':'raven','status':'fail','assembly_sha256':'assembly','truth_sha256':'truth','diagnostics':{'paf_sha256':'paf'}}
            hashes={'execution_sha256':digest(execution),'assembly_sha256':'assembly','truth_sha256':'truth','paf_sha256':'paf'}
            review={'status':'verified','strict_status':'fail','batch_id':'batch','scenario_id':'case','tool':'raven','hashes':hashes,'summary':'Checked observation'}
            with patch('pipeline.reviews.ROOT',root):
                for field in (None,*hashes):
                    changed=copy.deepcopy(review)
                    if field: changed['hashes'][field]='different'
                    save(root/'reviews/check.json',changed)
                    result=attach_sequence_review(copy.deepcopy(record),execution,batch)
                    self.assertEqual('sequence_review' in result,field is None)
                    self.assertEqual(result['status'],'fail')
                for key in ('batch_id','scenario_id','tool','strict_status'):
                    changed=copy.deepcopy(review);changed[key]='different'
                    save(root/'reviews/check.json',changed)
                    self.assertNotIn('sequence_review',attach_sequence_review(copy.deepcopy(record),execution,batch))
            self.assertEqual(digest(execution),hashes['execution_sha256'])


if __name__=='__main__':
    unittest.main()
