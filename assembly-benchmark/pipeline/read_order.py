"""S7: frozen FASTQ permutations and reference-independent output comparisons."""
import collections
import copy
import gzip
import hashlib
import os
import platform
import struct
import sys
from pathlib import Path
from .common import digest, fasta, fingerprint, load, save

VERSION = 'read-order-sha256-sort-v1'
COMPLETED = {'pass', 'fail'}
DNA = 'ACGTRYMKBDHVSWN'
COMPLEMENT = str.maketrans(DNA, 'TGCAYRKMVHDBSWN')


def records(path):
    """Read complete, unwrapped FASTQ records, preserving all four original lines."""
    with gzip.open(path, 'rb') as stream:
        while True:
            header = stream.readline()
            if not header:
                return
            sequence, plus, quality = [stream.readline() for _ in range(3)]
            if not header.startswith(b'@') or not plus.startswith(b'+') or not all(x.endswith(b'\n') for x in (header, sequence, plus, quality)):
                raise ValueError('Expected complete four-line FASTQ records')
            if not sequence.rstrip(b'\r\n') or len(sequence.rstrip(b'\r\n')) != len(quality.rstrip(b'\r\n')):
                raise ValueError('FASTQ sequence/quality lengths differ or are empty')
            yield header + sequence + plus + quality


def record_fingerprints(items):
    """Duplicates and qualities participate in both multiset and order fingerprints."""
    ordered, content, hashes = hashlib.sha256(), hashlib.sha256(), []
    total_bytes = 0
    for item in items:
        h = hashlib.sha256(item).digest()
        ordered.update(h)
        content.update(item)
        hashes.append(h)
        total_bytes += len(item)
    return {'record_count': len(hashes), 'record_multiset_sha256': hashlib.sha256(b''.join(sorted(hashes))).hexdigest(),
            'record_order_sha256': ordered.hexdigest(), 'uncompressed_sha256': content.hexdigest(),
            'uncompressed_bytes': total_bytes}


def permutation(count, seed):
    """Portable seeded permutation; independent of Python's random module version."""
    if type(seed) is not int or seed < 0:
        raise ValueError('Shuffle seed must be a nonnegative integer')
    prefix = (VERSION + ':' + str(seed) + ':').encode('ascii')
    return sorted(range(count), key=lambda i: (hashlib.sha256(prefix + struct.pack('>Q', i)).digest(), i))


def write_order(path, items, indices):
    with Path(path).open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as stream:
            for index in indices:
                stream.write(items[index])


def build_cases(source_case, config):
    result = []
    for order in config['read_order']['orders']:
        for repeat in range(1, config['read_order']['repeats_per_order'] + 1):
            case = copy.deepcopy(source_case)
            case.pop('fingerprint', None)
            case.update(id=f"s7-se11-{order['id']}-repeat-{repeat}", category='S7',
                        title=f"SE11 · {order['id']} · repeat {repeat}",
                        read_order={'order_id': order['id'], 'repeat': repeat})
            case['fingerprint'] = fingerprint(case)
            result.append(case)
    return result


def stage_inputs(batch, source):
    """One frozen file per order; repeats hard-link it. Never simulate new reads."""
    config = load(batch / 'config.json')
    declared = config['read_order']['source']
    manifest = load(source / 'input.json')
    if manifest.get('status') != 'valid' or manifest['case']['id'] != declared['case_id'] or digest(source / 'input.json') != declared['input_manifest_sha256']:
        raise ValueError('Source input manifest differs from the admitted frozen input')
    for name, key in [('reads.fastq.gz', 'reads_sha256'), ('truth.fasta', 'truth_sha256'), ('read_origins.tsv.gz', 'origins_sha256')]:
        if digest(source / name) != manifest[key]:
            raise ValueError('Source input checksum mismatch: ' + name)
    if manifest['reads_sha256'] != declared['reads_sha256'] or manifest['truth_sha256'] != declared['truth_sha256_for_provenance_only']:
        raise ValueError('Source reads/reference differ from the frozen S7 design')
    if (batch / 'input_orders.json').exists() or (batch / 'orders').exists():
        raise ValueError('Inputs already staged or partially staged; inspect before retrying')
    items = list(records(source / 'reads.fastq.gz'))
    original = record_fingerprints(items)
    if not items:
        raise ValueError('Cannot shuffle an empty input')
    cases = build_cases(manifest['case'], config)
    save(batch / 'cases.json', cases)
    orders, seen = [], set()
    for order in config['read_order']['orders']:
        directory = batch / 'orders' / order['id']
        directory.mkdir(parents=True)
        path = directory / 'reads.fastq.gz'
        indices = list(range(len(items))) if order['shuffle_seed'] is None else permutation(len(items), order['shuffle_seed'])
        if order['shuffle_seed'] is None:
            os.link(source / 'reads.fastq.gz', path)
        else:
            write_order(path, items, indices)
        metrics = record_fingerprints(records(path))
        if metrics['record_multiset_sha256'] != original['record_multiset_sha256'] or metrics['record_count'] != original['record_count']:
            raise ValueError('Shuffling changed the FASTQ record multiset')
        if metrics['record_order_sha256'] in seen:
            raise ValueError('Two input orders are identical; no distinct permutation was established')
        seen.add(metrics['record_order_sha256'])
        permutation_path = directory / 'permutation.u64be.gz'
        with permutation_path.open('wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as stream:
                for index in indices:
                    stream.write(struct.pack('>Q', index))
        row = {**order, **metrics, 'reads_sha256': digest(path), 'permutation_sha256': digest(permutation_path),
               'algorithm': VERSION, 'permutation_encoding': 'gzip of zero-based unsigned 64-bit big-endian source record indices'}
        orders.append(row)
        for case in (c for c in cases if c['read_order']['order_id'] == order['id']):
            target = batch / 'cases' / case['id']
            target.mkdir(parents=True)
            os.link(path, target / 'reads.fastq.gz')
            for filename in ('truth.fasta', 'read_origins.tsv.gz'):
                os.link(source / filename, target / filename)
            copied = {**copy.deepcopy(manifest), 'case': case, 'reads_sha256': row['reads_sha256'],
                      'read_order': row, 'source_input_manifest_sha256': digest(source / 'input.json'),
                      'origins_order': 'Unchanged original table; associate origins by read identifier, not row position.'}
            save(target / 'input.json', copied)
    result = {'schema_version': 1, 'status': 'valid', 'source': declared, 'orders': orders,
              'algorithm': VERSION, 'generator_source_sha256': digest(Path(__file__)),
              'python': sys.version, 'platform': platform.platform(), 'config_sha256': digest(batch / 'config.json')}
    save(batch / 'input_orders.json', result)
    return result


def least_rotation(sequence):
    """Booth's linear-time algorithm; no reference or read input is consulted."""
    size = len(sequence)
    if not size:
        return sequence
    doubled = sequence + sequence
    left, right, offset = 0, 1, 0
    while left < size and right < size and offset < size:
        a, b = doubled[left + offset], doubled[right + offset]
        if a == b:
            offset += 1
            continue
        if a > b:
            left += offset + 1
            if left <= right:
                left = right + 1
        else:
            right += offset + 1
            if right <= left:
                right = left + 1
        offset = 0
    begin = min(left, right)
    return doubled[begin:begin + size]


def sequence_fingerprint(parts, circularity=None):
    """Preserve sequence/copy differences; ignore names, strand and output order."""
    circularity = circularity or {}
    end_sensitive, circular = [], []
    unknown = []
    for identifier, sequence in parts:
        if not sequence or set(sequence) - set(DNA):
            raise ValueError('Assembly contains empty or unsupported DNA records')
        reverse = sequence.translate(COMPLEMENT)[::-1]
        end = min(sequence, reverse)
        row = {'length_bp': len(sequence), 'sha256': hashlib.sha256(end.encode()).hexdigest()}
        end_sensitive.append(row)
        topology = circularity.get(identifier)
        if topology is None:
            unknown.append(identifier)
        normal = min(least_rotation(sequence), least_rotation(reverse)) if topology is True else end
        circular.append({'length_bp': len(sequence), 'sha256': hashlib.sha256(normal.encode()).hexdigest(),
                         'reported_topology': 'circular' if topology is True else 'linear' if topology is False else 'unknown'})
    end_sensitive.sort(key=lambda r: (r['length_bp'], r['sha256']))
    circular.sort(key=lambda r: (r['length_bp'], r['sha256'], r['reported_topology']))
    return {'schema_version': 1, 'method': 'reference-independent-contig-multiset-v1',
            'end_sensitive_sha256': fingerprint(end_sensitive), 'contigs': end_sensitive,
            'circular_representation_sha256': fingerprint(circular) if not unknown else None,
            'circularity_unknown_contigs': unknown, 'contig_count': len(end_sensitive),
            'total_length_bp': sum(r['length_bp'] for r in end_sensitive),
            'end_sensitive_policy': 'Names/order/strand ignored; ends, sequence and duplicate copies retained.',
            'circular_policy': 'Rotations ignored only for tool-reported circular contigs; unavailable when any contig topology is unknown.'}



def inherited_chromosome_topology(directory, chromosomes):
    """Carry a saved Flye label only across exact whole-contig sequence identity."""
    from .graph_artifacts import parse_flye_assembly_info
    initial = directory / 'output/flye_output/assembly.fasta'
    information = directory / 'output/flye_output/assembly_info.txt'
    if not initial.is_file() or not information.is_file():
        return {}, []
    initial_hash, information_hash = digest(initial), digest(information)
    metadata = parse_flye_assembly_info(information)
    if metadata['status'] != 'available':
        return {}, []
    claims = {r['id']:r['reported_circularity'] for r in metadata['contigs']}
    candidates = collections.defaultdict(list)
    for name, sequence in fasta(initial).items():
        reverse = sequence.translate(COMPLEMENT)[::-1]
        key = (len(sequence), hashlib.sha256(min(sequence, reverse).encode()).hexdigest())
        candidates[key].append((name, claims.get(name)))
    matched, evidence = {}, []
    for name, sequence in chromosomes.items():
        reverse = sequence.translate(COMPLEMENT)[::-1]
        key = (len(sequence), hashlib.sha256(min(sequence, reverse).encode()).hexdigest())
        rows = candidates.get(key, [])
        labels = {r[1] for r in rows}
        if len(labels) == 1 and labels <= {'circular', 'not_circular'}:
            claim = next(iter(labels))
            matched['retained_chromosome:' + name] = claim == 'circular'
            evidence.append({'retained_contig':name,'initial_contigs':[r[0] for r in rows],
                             'sequence_identity':'Exact complete sequence, allowing reverse complement only',
                             'reported_circularity':claim,'initial_assembly_sha256':initial_hash,
                             'initial_info_sha256':information_hash,'retained_sequence_sha256':key[1],
                             'source':'Initial Flye assembly_info.txt, associated by verified sequence identity; no reference used.'})
    if digest(initial) != initial_hash or digest(information) != information_hash:
        raise ValueError('Initial chromosome metadata changed during verification')
    return matched, evidence


def output_signature(directory, record):
    """Final outputs only; Plassembler includes its separately retained chromosome."""
    from .graph_artifacts import parse_flye_assembly_info, parse_plassembler_summary
    batch = directory.parents[2]
    assembly = batch / record['assembly_file']
    if digest(assembly) != record['assembly_sha256']:
        raise ValueError('Final assembly checksum differs from its execution record')
    parts = [('final:' + name, sequence) for name, sequence in fasta(assembly).items()]
    circularity = {}
    tool = record['tool']
    info = None
    if tool in ('flye', 'flye-meta'):
        info = parse_flye_assembly_info(directory / 'output/assembly_info.txt')
    elif tool == 'plassembler':
        info = parse_plassembler_summary(directory / 'output/benchmark_summary.tsv')
    if info and info['status'] == 'available':
        for row in info['contigs']:
            if row['reported_circularity'] in ('circular', 'not_circular'):
                circularity['final:' + row['id']] = row['reported_circularity'] == 'circular'
    sources = [{'role': 'final', 'sha256': record['assembly_sha256']}]
    topology_evidence = []
    if tool == 'plassembler':
        chromosome = directory / 'output/chromosome.fasta'
        if not chromosome.exists() or digest(chromosome) != record.get('retained_chromosome_sha256'):
            raise ValueError('Retained chromosome missing or unverified; whole-workflow comparison unavailable')
        chromosomes = fasta(chromosome)
        parts += [('retained_chromosome:' + name, sequence) for name, sequence in chromosomes.items()]
        inherited, topology_evidence = inherited_chromosome_topology(directory, chromosomes)
        circularity.update(inherited)
        sources.append({'role': 'retained_chromosome', 'sha256': digest(chromosome)})
    return {**sequence_fingerprint(parts, circularity), 'source_files': sources,
            'circularity_source_evidence': topology_evidence,
            'scope': 'Final plasmids plus retained chromosome' if tool == 'plassembler' else 'Final assembly contigs'}


def assess_tool(rows, orders, repeats, field):
    by_order = {}
    expected = len(orders) * repeats
    for order in orders:
        selected = [r for r in rows if r['order_id'] == order]
        hashes = [r.get('signature', {}).get(field) for r in selected]
        complete = (len(selected) == repeats and len({r['repeat'] for r in selected}) == repeats
                    and all(r['status'] in COMPLETED for r in selected) and all(hashes))
        by_order[order] = {'complete': bool(complete), 'variants': len(set(h for h in hashes if h)),
                           'identical': len(set(hashes)) == 1 if complete else None}
    versions = {r.get('version') for r in rows}
    complete = len(rows) == expected and all(r['complete'] for r in by_order.values()) and len(versions) == 1 and None not in versions
    if not complete:
        verdict = 'Not assessed — incomplete executions or comparison evidence'
    elif any(not r['identical'] for r in by_order.values()):
        verdict = 'Within-order variability — order-specific effect not established'
    elif len({r['signature'][field] for r in rows}) > 1:
        verdict = 'Order-associated output difference'
    else:
        verdict = 'No order effect observed'
    return {'verdict': verdict, 'complete': complete, 'expected_runs': expected, 'observed_runs': sum(r['status'] in COMPLETED and bool(r.get('signature', {}).get(field)) for r in rows),
            'within_order': by_order, 'variants': len({r['signature'][field] for r in rows if r.get('signature', {}).get(field)})}


def summarise(batch):
    config = load(batch / 'config.json')
    admitted = load(batch / 'input_orders.json')
    if admitted.get('status') != 'valid' or admitted['config_sha256'] != digest(batch / 'config.json'):
        raise ValueError('No valid frozen input-order admission')
    expected_orders = [o['id'] for o in config['read_order']['orders']]
    rows = []
    accounting = {}
    if (batch / 'accounting.tsv').exists():
        for line in (batch / 'accounting.tsv').read_text().splitlines():
            fields = line.split('|')
            if len(fields) >= 2:
                accounting[fields[0]] = fields[1]
    submission = load(batch / 'submission.json')
    from .report import result_status
    for task in load(batch / 'tasks.json')['assemble']:
        directory = batch / 'results' / task['scenario'] / task['tool']
        path = directory / 'execution.json'
        record = load(path) if path.exists() else {'status': 'not_run'}
        signature_path = directory / 'read_order_signature.json'
        signature = load(signature_path) if signature_path.exists() else None
        job = submission.get('jobs', {}).get('assemble-' + task['tool'], '')
        scheduler = accounting.get(f"{job}_{task['tool_index']}", '')
        status = result_status(record, scheduler)
        input_manifest = load(batch / 'cases' / task['scenario'] / 'input.json')
        frozen = next(o for o in admitted['orders'] if o['id'] == task['order_id'])
        valid = (record.get('status') in COMPLETED and record.get('reads_sha256') == frozen['reads_sha256']
                 and record.get('config_fingerprint') == fingerprint(config) and record.get('threads') == config['threads']
                 and record.get('scenario_fingerprint') == input_manifest['case']['fingerprint']
                 and signature
                 and signature.get('execution_sha256') == digest(path) and signature.get('status') == 'complete')
        rows.append({**task, 'status': status, 'scheduler_state': scheduler, 'signature': signature['signature'] if valid else {},
                     'comparison_error': signature.get('error') if signature else 'Signature not yet recorded',
                     'secondary_reference_status': record.get('evaluation', {}).get('status'),
                     'version': record.get('version'), 'command': record.get('command'),
                     'execution_sha256': digest(path) if path.exists() else None,
                     'reads_sha256': record.get('reads_sha256'), 'error': record.get('error')})
    tools = []
    for tool in config['tools']:
        selected = [r for r in rows if r['tool'] == tool]
        tools.append({'tool': tool, 'threads': config['threads'], 'mode': 'default',
                      'end_sensitive': assess_tool(selected, expected_orders, config['read_order']['repeats_per_order'], 'end_sensitive_sha256'),
                      'circular_representation': assess_tool(selected, expected_orders, config['read_order']['repeats_per_order'], 'circular_representation_sha256'),
                      'runs': selected})
    return {'schema_version': 1, 'category': 'S7', 'batch_id': batch.name, 'input_admission': admitted,
            'report_producer_sha256': digest(Path(__file__)),
            'expected_executions': len(rows), 'status_counts': dict(collections.Counter(r['status'] for r in rows)),
            'tools': tools, 'complete': all(t['end_sensitive']['complete'] for t in tools),
            'endpoint': 'Output agreement across orders and repeats; reference-independent.',
            'reference_recovery': 'Secondary only; never used to decide S7 agreement.'}
