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

    def test_primary_publication_updates_latest_and_deploys_only_dist(self):
        save(self.root / "config/vercel-project.json", {"projectId": "test-project", "orgId": "test-org"})
        with patch("pipeline.publication.ROOT", self.root), \
             patch("pipeline.publication.build", side_effect=self.render) as build, \
             patch("pipeline.publication.subprocess.run") as deploy:
            publish({}, self.batch, deploy=True)
        self.assertEqual(load(self.root / "published/latest.json"), self.document)
        self.assertEqual(load(self.root / "dist/.vercel/project.json"), {"projectId": "test-project", "orgId": "test-org"})
        build.assert_called_once_with({}, self.batch, output=self.root / "dist", include_history=True)
        argv = deploy.call_args.args[0]
        self.assertEqual(argv[argv.index("--cwd") + 1], str(self.root / "dist"))
        self.assertEqual(deploy.call_args.kwargs["cwd"], self.root)
        self.assertTrue(deploy.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
