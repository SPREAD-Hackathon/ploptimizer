"""Verify that public report files match the reviewed local static build."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import gzip
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def public_files(root):
    root = Path(root)
    return sorted(path for path in root.rglob("*") if path.is_file()
                  and not any(part.startswith(".") for part in path.relative_to(root).parts)
                  and path.name != "vercel.json" and path.suffix != ".map")


def verify(root, base_url, workers=6):
    """Check byte equality, so stale results and successful error pages fail QA."""
    root = Path(root)
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Supply an HTTP(S) report URL")
    files = public_files(root)
    results = root / "data/results.json"
    if not results.is_file():
        results = root / "data/results.json.gz"
    if not results.is_file():
        results = root / "site-manifest.json"
    if not files or not results.is_file():
        raise ValueError("The report build and results.json must exist")

    def check(path):
        route = path.relative_to(root).as_posix()
        url = base_url.rstrip("/") + "/" + quote(route, safe="/")
        try:
            request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "ploptimizer-publication-check/1"})
            with urlopen(request, timeout=30) as response:
                received = response.read()
            expected = path.read_bytes()
            if received != expected:
                return {"route": route, "error": "Published bytes differ from the local build",
                        "expected_sha256": hashlib.sha256(expected).hexdigest(),
                        "received_sha256": hashlib.sha256(received).hexdigest()}
        except Exception as error:
            if isinstance(error, HTTPError):
                error.close()
            return {"route": route, "error": f"{type(error).__name__}: {error}"}
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        failures = [failure for failure in pool.map(check, files) if failure]
    content = results.read_bytes()
    document = json.loads(gzip.decompress(content) if results.suffix == ".gz" else content)
    return {"status": "fail" if failures else "pass", "base_url": base_url,
            "batch": document.get("batch"), "generated_at": document.get("generated_at"),
            "checked_files": len(files), "failures": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify(args.root, args.base_url)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
    print(content, end="")
    return int(result["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
