"""Save snapshots; deploy reviewed static bundles through an offline release gate."""

import os
import subprocess
from pathlib import Path

from .common import ROOT, load, save
from .report import build


def publish(config, batch, deploy=False, make_latest=True):
    if deploy and not make_latest:
        raise ValueError("Only the primary report can deploy the site")
    if deploy:
        raise ValueError("Direct legacy deployment is disabled. Export/render and use deploy-site with its validated bundle.")
    output = ROOT / "dist" if make_latest else batch / "publication"
    build(config, batch, output=output, include_history=make_latest)
    document = load(output / "data/results.json")
    save(ROOT / "published" / (batch.name + ".json"), document)
    if make_latest:
        save(ROOT / "published/latest.json", document)
    return document


def deploy_site(bundle, output):
    """Deploy only a source-bound reviewed lean build; never rebuild or collect."""
    from .site_gate import check_release
    output = Path(output).resolve()
    if output != (ROOT / 'dist').resolve():
        raise ValueError('Production deployment requires assembly-benchmark/dist')
    report = check_release(bundle, output)
    if report['status'] != 'pass':
        raise ValueError('Release gate blocked deployment: ' + '; '.join(report['errors'][:5]))
    save(output / '.vercel/project.json', load(ROOT / 'config/vercel-project.json'))
    env = dict(os.environ, npm_config_cache=str(ROOT / '.cache/npm'))
    subprocess.run(['npx', '--yes', 'vercel@65.11.0', 'deploy', '--prod', '--yes', '--archive=tgz', '--cwd', str(output)], cwd=ROOT, env=env, check=True)
    return report
