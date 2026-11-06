"""Attach human-reviewed process history to matching saved logs, without sequence analysis."""
from pathlib import Path

from .common import ROOT, digest, load
from .recorded_coordinates import _safe_path


def attach_stage_facts(summary, record, batch, artifact_root):
    if not summary or artifact_root is None:
        return
    for path in sorted((ROOT / 'reviews' / 'stages').glob('*.json')):
        note = load(path)
        if (note['batch_id'], note['scenario_id'], note['tool']) != (batch, record['scenario_id'], record['tool']):
            continue
        if any(note['hashes'].get(k) != record.get(k) for k in ('assembly_sha256', 'truth_sha256')):
            continue
        directory = Path('results') / record['scenario_id'] / record['tool']
        root = Path(artifact_root) / batch
        try:
            if any(digest(_safe_path(root, directory / filename)) != note[key]
                   for filename, key in [('execution.json', 'execution_sha256'), ('stderr.log', 'log_sha256')]):
                continue
        except (OSError, ValueError):
            continue
        for fact in note['facts']:
            summary['facts'].append({**fact, 'source': f'{path.relative_to(ROOT)} · {fact["source"]} · log SHA-256 {note["log_sha256"]}'})
        return
