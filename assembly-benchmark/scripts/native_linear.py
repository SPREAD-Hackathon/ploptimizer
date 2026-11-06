"""Submit/collect the authorised six-input, 24-execution native S5 panel."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.cases import plan
from pipeline.cluster import collect, ssh, submit
from pipeline.common import ROOT, digest, fingerprint, load, save
from pipeline.determinism import assembly_tasks
from scripts.large_baseline import queue_evidence

STATUS = ROOT / 'evidence/s5-native-v2/status.json'
CONFIG = ROOT / 'config/linear-plasmids.json'


def panel_plan():
    config = load(CONFIG)
    cases = plan(config)
    if (len(cases) != 6 or len(assembly_tasks(config, cases)) != 24
            or config['linear_panel']['scope'] != 'native_genome'):
        raise ValueError('Expected the authorised native-genome S5 panel')
    repeats = load(ROOT / 'evidence/s5-native-v2/reference-repeat-alignments.json')
    admitted = {r['accession']: r['sequence_sha256'] for r in repeats['references']}
    for case in cases:
        for reference in case['replicons']:
            if admitted.get(reference['refseq_accession']) != reference['sequence_sha256']:
                raise ValueError('Missing hash-bound inter-arm repeat assessment')
    return {'schema_version': 1, 'status': 'ready_not_submitted',
            'config': str(CONFIG.relative_to(ROOT)), 'config_fingerprint': fingerprint(config),
            'reference_panel_sha256': digest(ROOT / 'references/streptomyces-linear-panel.json'),
            'input_count': 6, 'assembly_count': 24,
            'scenario_ids': [case['id'] for case in cases]}


def submit_panel():
    planned = panel_plan()
    state = load(STATUS) if STATUS.exists() else planned
    for key in ('config_fingerprint', 'reference_panel_sha256'):
        if state[key] != planned[key]:
            raise ValueError('Panel changed since checkpoint; inspect before submission')
    cluster = load(ROOT / 'config/cluster.local.json')
    if cluster['array_concurrency'] != 1000:
        raise ValueError('Keep the authorised scheduler cap of 1000')
    ssh(cluster['host'], ['true'])
    if not state.get('batch_id'):
        before = set((ROOT / 'runs').iterdir())
        try:
            record = submit(load(CONFIG), cluster)
        except Exception:
            created = set((ROOT / 'runs').iterdir()) - before
            if len(created) == 1:
                state.update(batch_id=created.pop().name, status='submission_needs_review')
                save(STATUS, state)
            raise
        state.update(batch_id=record['batch_id'], status='submitted')
        save(STATUS, state)
    batch = ROOT / 'runs' / state['batch_id']
    record = load(batch / 'submission.json')
    if record['status'] != 'submitted':
        raise ValueError('Partial submission: inspect recorded jobs; do not duplicate')
    if not record['jobs'].get('evidence'):
        queue_evidence(batch, cluster, comparison_label='s5-native-v2')
        record = load(batch / 'submission.json')
    state.update(jobs=record['jobs'])
    save(STATUS, state)
    return state


def collect_panel():
    state = load(STATUS)
    batch = ROOT / 'runs' / state['batch_id']
    collect(batch, include_site=False)
    record = load(batch / 'submission.json')
    cluster = record['cluster']
    remote = Path(cluster['remote_root'])
    status_path = remote / 'runs' / batch.name / 'evidence_status.json'
    try:
        ssh(cluster['host'], ['test', '-f', str(status_path)])
    except subprocess.CalledProcessError as error:
        if error.returncode != 1:
            raise
        return state
    subprocess.run(['rsync', '-az', cluster['host'] + ':' + str(status_path), str(batch) + '/'], check=True)
    state['evidence'] = load(batch / 'evidence_status.json')
    if state['evidence']['status'] == 'complete':
        subprocess.run(['rsync', '-az', '--exclude=*.delta', cluster['host'] + ':' + str(remote / 'runs' / batch.name / 'comparisons') + '/', str(batch / 'comparisons') + '/'], check=True)
        subprocess.run(['rsync', '-az', cluster['host'] + ':' + str(remote / 'published' / (batch.name + '.json')), str(ROOT / 'published') + '/'], check=True)
        manifests = [load(batch / 'cases' / case / 'input.json') for case in state['scenario_ids']]
        state['inputs_admitted'] = sum(item['status'] == 'valid' for item in manifests)
        state['status'] = 'evidence_complete' if state['inputs_admitted'] == 6 else 'needs_review'
    else:
        state['status'] = 'needs_review'
    save(STATUS, state)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'submit', 'collect'])
    action = parser.parse_args().action
    print(json.dumps({'plan': panel_plan, 'submit': submit_panel, 'collect': collect_panel}[action](), indent=2))
