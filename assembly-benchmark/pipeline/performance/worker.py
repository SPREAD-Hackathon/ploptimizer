"""Compute-node workers for frozen broad-performance inputs and workflows."""
import datetime
import os
import shutil
from pathlib import Path
from ..common import ROOT, digest, fingerprint, load, save
from ..execution import run
from .inputs import cases, download_references, prepare_input


def configuration(batch):
    config = load(batch / 'config.json')
    selection = load(batch / 'selection.json')
    return config, selection, cases(selection)


def prepare(batch):
    _, selection, _ = configuration(batch)
    result = download_references(selection, batch / 'reference-cache')
    save(batch / 'preparation.json', {'status': 'complete', 'reference_archive_sha256': result['archive_sha256'], 'selected_reference_count': len(result['selected'])})
    return result


def fetch(batch, index):
    _, selection, planned = configuration(batch)
    case = planned[index]
    try:
        return prepare_input(case, batch, selection, load(batch / 'reads-index.json'))
    except Exception as error:
        save(batch / 'cases' / case['id'] / 'input_error.json',
             {'status': 'error', 'dataset_id': case['id'], 'case_fingerprint': case['fingerprint'],
              'error': f'{type(error).__name__}: {error}',
              'slurm_job_id': os.environ.get('SLURM_JOB_ID'),
              'slurm_array_task_id': os.environ.get('SLURM_ARRAY_TASK_ID')})
        raise


def stage_raw(batch, case):
    source = batch / 'results' / case['id'] / 'miniasm'
    execution = source / 'execution.json'
    record = load(execution)
    graph = source / 'output/assembly.raw.gfa'
    if (record.get('tool') != 'miniasm' or record.get('status') not in ('pass', 'fail') or record.get('scenario_fingerprint') != case['fingerprint'] or record.get('assembly_workflow', {}).get('conversion', {}).get('raw_gfa_sha256') != digest(graph)):
        raise ValueError('Raw Miniasm prerequisite is incomplete or differs from frozen provenance')
    target = batch / 'raw_assemblies' / case['id']
    target.mkdir(parents=True, exist_ok=False)
    shutil.copy2(execution, target / 'execution.json')
    os.link(graph, target / 'assembly.raw.gfa')
    save(target / 'reuse.json', {'status': 'complete', 'source_execution_sha256': digest(execution), 'raw_gfa_sha256': digest(graph), 'reads_sha256': record['reads_sha256'], 'method': 'Metadata copied; original annotated raw GFA hard-linked; no overlaps recomputed.'})


def assemble(batch, index, tool):
    config, _, planned = configuration(batch)
    case = planned[index]
    if tool == 'miniasm-plus':
        try:
            stage_raw(batch, case)
        except Exception as error:
            path = batch / 'results' / case['id'] / tool / 'execution.json'
            if path.exists():
                raise ValueError('Execution already recorded; do not overwrite')
            result = {'status': 'error', 'error': 'Raw Miniasm prerequisite: ' + str(error), 'tool': tool, 'batch_id': batch.name, 'scenario_id': case['id'], 'scenario_fingerprint': case['fingerprint'], 'config_fingerprint': fingerprint(config), 'threads': config['threads'], 'slurm_job_id': os.environ.get('SLURM_JOB_ID'), 'slurm_array_task_id': os.environ.get('SLURM_ARRAY_TASK_ID'), 'finished_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            save(path, result)
            return result
    return run(case, tool, batch, config)


def assess_result(batch, index, tool):
    from .assessment import assess
    _, _, planned = configuration(batch)
    case = planned[index]
    execution = batch / 'results' / case['id'] / tool / 'execution.json'
    if not execution.exists():
        raise ValueError('No execution record exists; verify scheduler state before recording an outcome')
    record = load(execution)
    if record.get('status') == 'running':
        backup = execution.with_name('execution.before-scheduler-finalisation.json')
        if not backup.exists():
            shutil.copy2(execution, backup)
        import subprocess
        job = record.get('slurm_job_id', '')
        # SLURM_JOB_ID is the element's own ID, not the array master.
        # JobIDRaw resolves it without constructing a nonexistent master_task ID.
        state = subprocess.check_output(['sacct', '-j', job, '--parsable2', '--noheader', '--format=JobIDRaw,State,Elapsed,ExitCode'], text=True)
        own = next((line.split('|') for line in state.splitlines() if line.split('|')[0] == job), None)
        if own is None or own[1].startswith(('RUNNING', 'PENDING', 'COMPLETING')):
            raise ValueError('Assembly has no verified terminal scheduler state')
        record.update(status='timeout' if own[1].startswith('TIMEOUT') else 'error', scheduler_state=own[1], error='Worker ended without persisting a terminal result: ' + own[1], original_running_record_sha256=digest(backup))
        if record['status'] == 'timeout':
            record['execution_outcome'] = 'did_not_complete'
        save(execution, record)
    return assess(case, execution, batch, threads=1)
