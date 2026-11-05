"""Publication isolation: companions never replace the primary static report."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.common import load, save
from pipeline.publication import publish


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = self.root / "runs/companion"
        self.batch.mkdir(parents=True)
        self.document = {"batch": "companion", "results": [{"status": "running"}]}

    def render(self, config, batch, *, output, include_history):
        save(output / "data/results.json", self.document)
        return output

    def test_companion_snapshot_preserves_latest_and_primary_site(self):
        previous = {"batch": "primary", "results": [{"status": "pass"}]}
        save(self.root / "published/latest.json", previous)
        marker = self.root / "dist/index.html"
        marker.parent.mkdir()
        marker.write_text("Primary site")
        with patch("pipeline.publication.ROOT", self.root), \
             patch("pipeline.publication.build", side_effect=self.render) as build, \
             patch("pipeline.publication.subprocess.run") as deploy:
            result = publish({}, self.batch, make_latest=False)
        self.assertEqual(result, self.document)
        self.assertEqual(load(self.root / "published/companion.json"), self.document)
        self.assertEqual(load(self.root / "published/latest.json"), previous)
        self.assertEqual(marker.read_text(), "Primary site")
        build.assert_called_once_with({}, self.batch, output=self.batch / "publication", include_history=False)
        deploy.assert_not_called()

    def test_companion_deployment_is_rejected_before_build_or_write(self):
        with patch("pipeline.publication.ROOT", self.root), \
             patch("pipeline.publication.build") as build, \
             patch("pipeline.publication.subprocess.run") as deploy:
            with self.assertRaisesRegex(ValueError, "Only the primary"):
                publish({}, self.batch, deploy=True, make_latest=False)
        build.assert_not_called()
        deploy.assert_not_called()
        self.assertFalse((self.root / "published").exists())

    def test_legacy_deployment_is_rejected_before_build_or_snapshot_mutation(self):
        with patch("pipeline.publication.build") as build, patch("pipeline.publication.subprocess.run") as deploy:
            with self.assertRaisesRegex(ValueError, "deploy-site"):
                publish({}, self.batch, deploy=True)
        build.assert_not_called()
        deploy.assert_not_called()
        self.assertFalse((self.root / 'published').exists())

    def test_reviewed_deployment_is_blocked_before_network_when_gate_fails(self):
        from pipeline.publication import deploy_site
        with patch("pipeline.publication.ROOT",self.root), patch("pipeline.site_gate.check_release",return_value={'status':'fail','errors':['stale evidence']}), patch("pipeline.publication.subprocess.run") as deploy:
            with self.assertRaisesRegex(ValueError,'stale evidence'):
                deploy_site(self.root/'bundle',self.root/'dist')
        deploy.assert_not_called()

    def test_reviewed_deployment_uses_scoped_project_and_one_archive(self):
        from pipeline.publication import deploy_site
        save(self.root/'config/vercel-project.json', {'projectId':'fixture','orgId':'fixture-team'})
        with patch("pipeline.publication.ROOT",self.root), patch("pipeline.site_gate.check_release",return_value={'status':'pass','errors':[]}), patch("pipeline.publication.subprocess.run") as deploy:
            deploy_site(self.root/'bundle',self.root/'dist')
        command=deploy.call_args.args[0]
        self.assertIn('--archive=tgz',command)
        self.assertEqual(command[-1],str((self.root/'dist').resolve()))
        self.assertEqual(load(self.root/'dist/.vercel/project.json')['projectId'],'fixture')


if __name__ == "__main__":
    unittest.main()
