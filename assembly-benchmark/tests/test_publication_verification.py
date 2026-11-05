"""A successful HTTP response must not hide stale or incorrect report content."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import tempfile
import threading
import unittest


spec = importlib.util.spec_from_file_location("verify_publication", Path(__file__).resolve().parents[1] / "scripts/verify_publication.py")
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class PublicationVerificationTests(unittest.TestCase):
    def test_reports_stale_content_and_missing_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected, served = root / "build", root / "served"
            for folder in (expected, served):
                (folder / "data").mkdir(parents=True)
                (folder / "index.html").write_text("Reviewed report")
                (folder / "data/results.json").write_text('{"batch":"fixture"}')
            (expected / ".vercel").mkdir()
            (expected / ".vercel/project.json").write_text("private deployment metadata")
            server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(served)))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                result = publication.verify(expected, url)
                self.assertEqual(result["status"], "pass")
                self.assertEqual(result["checked_files"], 2)
                (served / "index.html").write_text("Old report")
                (expected / "data/results.tsv").write_text("missing download")
                result = publication.verify(expected, url)
                self.assertEqual(result["status"], "fail")
                self.assertEqual({item["route"] for item in result["failures"]}, {"index.html", "data/results.tsv"})
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_empty_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "must exist"):
                publication.verify(Path(directory), "https://example.com")
