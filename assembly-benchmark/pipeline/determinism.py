"""Fixed-input repeat plans and conservative sequence-repeatability diagnostics."""

import collections
import hashlib

from .common import fasta, fingerprint, load, reverse_complement
from .scoring import equivalent


def repeat_settings(config):
    panel = config.get('determinism')
    if not panel:
        return None
    threads = panel.get('threads', [])
    repeats = panel.get('repeats')
    if not threads or any(type(value) is not int or value < 1 for value in threads) or len(set(threads)) != len(threads):
        raise ValueError('Determinism threads must be unique positive integers')
    if type(repeats) is not int or repeats < 2:
        raise ValueError('Determinism requires at least two identical-input executions')
    scenarios = panel.get('scenarios', [])
    if not scenarios or len(set(scenarios)) != len(scenarios):
        raise ValueError('Determinism requires unique scenario identifiers')
    return panel


def execution_id(threads, repeat):
    if type(threads) is not int or threads < 1 or type(repeat) is not int or repeat < 1:
        raise ValueError('Execution threads and repeat must be positive integers')
    return f'threads-{threads}-repeat-{repeat}'


def assembly_tasks(config, scenarios):
    panel = repeat_settings(config)
    if not panel:
        return [{'scenario': case['id'], 'tool': tool} for case in scenarios for tool in config['tools']]
    return [{'scenario': case['id'], 'tool': tool, 'threads': threads, 'repeat': repeat,
             'run_id': execution_id(threads, repeat)}
            for case in scenarios for tool in config['tools'] for threads in panel['threads']
            for repeat in range(1, panel['repeats'] + 1)]


def sequence_signature(case, truth_path, assembly_path):
    """Ignore names/order/strands; rotate only exact known circles.

    Non-exact/unclassified contigs retain their ends. This avoids treating every
    output as circular or hiding terminal-overlap/sequence errors. Signatures
    are anchored to the reference, and compared only within one scenario.
    """
    truth = fasta(truth_path)
    circles = [truth[r['refseq_accession']] for r in case['replicons'] if r['topology'] == 'circular']
    contigs = []
    for sequence in fasta(assembly_path).values():
        canonical = min(sequence, reverse_complement(sequence))
        policy = 'strand-only; ends retained'
        for reference in circles:
            if equivalent(reference, sequence, 'circular'):
                canonical = reference
                policy = 'exact circular truth; rotation and strand ignored'
                break
        contigs.append({'length_bp': len(sequence), 'sha256': hashlib.sha256(canonical.encode()).hexdigest(), 'normalisation': policy})
    contigs.sort(key=lambda item: (item['length_bp'], item['sha256'], item['normalisation']))
    return {'sha256': fingerprint(contigs), 'contigs': contigs,
            'policy': 'Ignore names, order and strands; rotation only for exact truth-matched circles. Duplicates retained. Not a topology assessment.'}


def biological_signature(evaluation):
    rows = [{'accession': row['accession'], 'status': row['status'],
             'exact_contig_count': len(row['exact_contigs']),
             'extra_full_copy_contig_count': len(row['extra_full_copy_contigs']),
             'topology_status': row['topology_status']} for row in evaluation['replicons']]
    return fingerprint({'status': evaluation['status'], 'replicons': sorted(rows, key=lambda row: row['accession']),
                        'contig_count': evaluation['contig_count']})


def collect_records(config, batch):
    """Flatten all expected repeats, including scheduler failures and pending tasks."""
    from .cases import plan
    from .report import attach_diagnostics, result_status
    cases = {case['id']: case for case in plan(config)}
    tasks = load(batch / 'tasks.json')['assemble']
    submission_path = batch / 'submission.json'
    submission = load(submission_path) if submission_path.exists() else {}
    job = submission.get('jobs', {}).get('assemble', '')
    accounting = {}
    accounting_path = batch / 'accounting.tsv'
    if accounting_path.exists():
        for line in accounting_path.read_text().splitlines():
            fields = line.split('|')
            if len(fields) >= 2:
                accounting[fields[0]] = fields[1]
    records = []
    for index, task in enumerate(tasks):
        path = batch / 'results' / task['scenario'] / task['tool'] / 'repeats' / task['run_id'] / 'execution.json'
        record = load(path) if path.exists() else {}
        if record and (record.get('config_fingerprint') != fingerprint(config)
                       or record.get('scenario_fingerprint') != cases[task['scenario']]['fingerprint']
                       or record.get('threads') != task['threads'] or record.get('repeat') != task['repeat']):
            record = {'status': 'error', 'error': 'Result provenance does not match this repeat task'}
        record = attach_diagnostics(record, path)
        state = accounting.get(f'{job}_{index}', accounting.get(job, ''))
        if not state and not record:
            state = 'PENDING' if submission else ''
        records.append({**record, **task, 'scenario_id': task['scenario'],
                        'status': result_status(record, state), 'scheduler_state': state or None})
    return records


METRICS = (('byte', 'assembly_sha256'), ('normalised_sequence', 'normalised_assembly_sha256'), ('biological', 'biological_sha256'))


def collect_summary(config, batch):
    """Keep missing/failed repeats in denominators; never call incomplete groups identical."""
    panel = repeat_settings(config)
    if not panel:
        raise ValueError('This configuration has no determinism panel')
    records = collect_records(config, batch)
    groups = collections.defaultdict(list)
    for row in records:
        groups[(row['scenario_id'], row['tool'], row['threads'])].append(row)
    within = []
    for (scenario, tool, threads), rows in groups.items():
        valid = [row for row in rows if row['status'] in ('pass', 'fail')]
        complete = len(valid) == panel['repeats']
        inputs_identical = complete and all(row.get('reads_sha256') and row.get('truth_sha256') for row in valid) and len({(row['reads_sha256'], row['truth_sha256']) for row in valid}) == 1
        metrics = {}
        for label, field in METRICS:
            hashes = [row.get(field) for row in valid]
            observed = set(value for value in hashes if value)
            metrics[label + '_variants'] = len(observed)
            metrics[label + '_identical'] = len(observed) == 1 if inputs_identical and all(hashes) else None
        within.append({'scenario_id': scenario, 'tool': tool, 'threads': threads, 'expected_runs': panel['repeats'],
                       'scored_runs': len(valid), 'complete': complete, 'inputs_identical': inputs_identical if complete else None, 'status_counts': dict(collections.Counter(row['status'] for row in rows)), **metrics})
    between = []
    for scenario, tool in sorted({(row['scenario_id'], row['tool']) for row in within}):
        selected = [row for row in records if row['scenario_id'] == scenario and row['tool'] == tool]
        valid = [row for row in selected if row['status'] in ('pass', 'fail')]
        complete = len(valid) == panel['repeats'] * len(panel['threads'])
        inputs_identical = complete and all(row.get('reads_sha256') and row.get('truth_sha256') for row in valid) and len({(row['reads_sha256'], row['truth_sha256']) for row in valid}) == 1
        between.append({'scenario_id': scenario, 'tool': tool, 'threads': panel['threads'], 'complete': complete, 'inputs_identical': inputs_identical if complete else None,
                        **{label + '_identical': len({row[field] for row in valid}) == 1
                           if inputs_identical and all(row.get(field) for row in valid) else None for label, field in METRICS}})
    return {'schema_version': 1, 'batch_id': batch.name, 'category': 'S3', 'expected_runs': len(records),
            'status_counts': dict(collections.Counter(row['status'] for row in records)),
            'within_thread': within, 'across_threads': between, 'executions': records,
            'limitations': 'Repeats on one frozen simulated read set assess observed repeatability, not a guarantee of determinism. Non-exact contigs retain their ends during normalisation. Biological signatures describe the strict endpoint, not all assembly errors.'}
