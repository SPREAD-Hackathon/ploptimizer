"""Save a small reproducible result snapshot and optionally deploy its static site."""

import os
import subprocess

from .common import ROOT, load, save
from .report import build


def publish(config, batch, deploy=False):
    build(config, batch)
    document = load(ROOT / "dist/data/results.json")
    save(ROOT / "published" / (batch.name + ".json"), document)
    save(ROOT / "published/latest.json", document)
    if deploy:
        project = load(ROOT / "config/vercel-project.json")
        save(ROOT / "dist/.vercel/project.json", project)
        env = dict(os.environ, npm_config_cache=str(ROOT / ".cache/npm"))
        subprocess.run(["npx", "--yes", "vercel@65.11.0", "deploy", "--prod", "--yes", "--cwd", str(ROOT / "dist")], cwd=ROOT, env=env, check=True)
    return document
