#!/usr/bin/env python3
"""Read-only collection of bounded sequence-free metadata for selected executions.

No remote installation, assembly, alignment, tuning, jobs or publication.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAX_EXECUTION_BYTES = 256 * 1024
MAX_ASSEMBLY_BYTES = 256 * 1024 * 1024
MAX_SELECTIONS = 8
MAX_RESPONSE_BYTES = 72 * 1024 * 1024


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def inside(root, relative):
    value = Path(relative)
    if value.is_absolute():
        raise ValueError('Use paths relative to the selected batch')
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes the selected scope')
    return path


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Use a simple identifier, not a path')
    return value


def candidates(record):
    tool = record.get('tool')
    if tool in {'flye', 'flye-meta'}:
        paths = [('output/assembly_graph.gfa', 'gfa', 'final'),
                 ('output/assembly_info.txt', 'assembly_info', 'final')]
    elif tool == 'plassembler':
        argv = record.get('command') or []
        prefix = None
        if '--prefix' in argv and argv.index('--prefix') + 1 < len(argv):
            prefix = argv[argv.index('--prefix') + 1]
        else:
            prefix = next((value.split('=', 1)[1] for value in argv if value.startswith('--prefix=')), None)
        paths = []
        if prefix and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', prefix):
            paths += [('output/' + prefix + '_plasmids.gfa', 'gfa', 'final'),
                      ('output/' + prefix + '_summary.tsv', 'assembly_info', 'final')]
        paths += [('output/flye_output/assembly_graph.gfa', 'gfa', 'initial_flye'),
                 ('output/flye_output/assembly_info.txt', 'assembly_info', 'initial_flye'),
                 ('output/assembly_graph.gfa', 'gfa', 'initial_flye'),
                 ('output/assembly_info.txt', 'assembly_info', 'initial_flye'),
                 ('output/unicycler_output/assembly.gfa', 'gfa', 'unicycler_component')]
    elif tool == 'raven':
        paths = [('graph.gfa', 'gfa', 'final'), ('assembly_graph.gfa', 'gfa', 'final')]
    else:
        return []
    if record.get('status') in {'error', 'timeout'}:
        if tool in {'flye', 'flye-meta'}:
            paths += [('output/30-contigger/graph_final.gfa', 'gfa', 'partial_contigger'),
                      ('output/20-repeat/graph_before_rr.gfa', 'gfa', 'partial_repeat_graph')]
        elif tool == 'plassembler':
            paths += [('output/flye_output/30-contigger/graph_final.gfa', 'gfa', 'initial_flye'),
                      ('output/flye_output/20-repeat/graph_before_rr.gfa', 'gfa', 'initial_flye')]
    argv = record.get('command') or []
    for option in ('--graphical-fragment-assembly', '--unitig-graphical-fragment-assembly', '-F', '-U'):
        if option in argv and argv.index(option) + 1 < len(argv):
            paths.append((argv[argv.index(option) + 1], 'gfa', 'final'))
    return paths


def select_artifacts(directory, record):
    """Known filenames and explicitly recorded outputs only; never recurse."""
    observed, seen, selected, role = [], set(), {}, None
    available = []
    for relative, kind, candidate_role in candidates(record):
        path = Path(relative)
        path = path.resolve() if path.is_absolute() else (directory / path).resolve()
        if not path.is_relative_to(directory.resolve()):
            observed.append({'kind': kind, 'role': candidate_role, 'status': 'rejected_outside_execution'})
            continue
        if path in seen:
            continue
        seen.add(path)
        exists = path.is_file()
        empty_placeholder = (exists and candidate_role == 'final' and record.get('status') in {'error', 'timeout'}
                             and path.stat().st_size == 0)
        observed.append({'relative_path': str(path.relative_to(directory)), 'kind': kind, 'role': candidate_role,
                         'status': 'empty_placeholder' if empty_placeholder else 'available' if exists else 'missing'})
        if exists and not empty_placeholder:
            available.append((path, kind, candidate_role))
        if exists and not empty_placeholder and kind not in selected and (role is None or candidate_role == role):
            selected[kind] = path
            role = candidate_role
    if record.get('status') in {'error', 'timeout'} and available:
        # Prefer an actual retained graph over a claim-only later-stage file.
        # Claims are then selected only from that same component/stage.
        role = next((stage for path, kind, stage in available if kind == 'gfa'), available[0][2])
        selected = {}
        for path, kind, stage in available:
            if stage == role and kind not in selected:
                selected[kind] = path
    return selected, role or 'final', observed


def selected_execution(batch, relative):
    parts = Path(relative).parts
    if not (len(parts) == 4 or len(parts) == 6) or parts[0] != 'results' or parts[-1] != 'execution.json':
        raise ValueError('Select results/SCENARIO/TOOL/[repeats/RUN_ID/]execution.json')
    identifier(parts[1]); identifier(parts[2])
    if len(parts) == 6:
        if parts[3] != 'repeats':
            raise ValueError('Invalid repeat execution path')
        identifier(parts[4])
    return inside(batch, relative), parts


def unavailable(reason, execution_hash=None, assembly_hash=None):
    return {'schema_version': 1, 'status': 'missing', 'input_hashes': {'execution_sha256': execution_hash, 'assembly_sha256': assembly_hash},
            'graph': {'status': 'missing'}, 'assembly_info': {'status': 'missing'},
            'reason': reason, 'limitations': ['Metadata unavailable; no topology or sequence conclusion is implied.']}


def collect_execution(source_root, batch_id, relative):
    batch_id = identifier(batch_id)
    batch = (Path(source_root) / 'runs' / batch_id).resolve()
    execution, parts = selected_execution(batch, relative)
    if not execution.is_file():
        result = unavailable('Selected execution record is missing')
    elif execution.stat().st_size > MAX_EXECUTION_BYTES:
        result = unavailable('Execution metadata exceeds collection bound')
    else:
        execution_hash = sha256(execution)
        record = json.loads(execution.read_text())
        if record.get('scenario_id') != parts[1] or record.get('tool') != parts[2] or record.get('batch_id', batch_id) != batch_id:
            raise ValueError('Execution identity does not match the selected path/batch')
        if len(parts) == 6 and record.get('run_id') != parts[4]:
            raise ValueError('Repeat identity does not match selected execution')
        selected, role, observed = select_artifacts(execution.parent, record)
        if record.get('tool') not in {'flye', 'flye-meta', 'raven', 'plassembler'}:
            result = unavailable('Assembler graph layout is unsupported', execution_hash)
            result['status'] = 'unsupported'
        elif record.get('status') in {'error', 'timeout'}:
            from pipeline.graph_artifacts import build_graph_artifacts
            declared_role = role
            role = 'partial_output' if role == 'final' else role
            options = {'source_role': role, 'allow_failed': True}
            if record['tool'] == 'plassembler' and declared_role == 'final':
                options['assembly_info_kind'] = 'plassembler'
            result = build_graph_artifacts(execution, None, selected.get('gfa'), selected.get('assembly_info'), **options)
            if result.get('input_hashes', {}).get('execution_sha256') != execution_hash or result.get('input_hashes', {}).get('assembly_sha256') is not None:
                raise ValueError('Failed topology metadata did not preserve its execution-only binding')
        elif record.get('status') not in {'pass', 'fail'} or not record.get('assembly_file'):
            result = unavailable('No successfully recorded primary assembly to verify', execution_hash)
        else:
            assembly = inside(batch, record['assembly_file'])
            if not assembly.is_relative_to(execution.parent.resolve()):
                raise ValueError('Recorded assembly escapes selected execution directory')
            if not assembly.is_file():
                result = unavailable('Recorded assembly unavailable; primary hash cannot be verified', execution_hash)
            elif assembly.stat().st_size > MAX_ASSEMBLY_BYTES:
                result = unavailable('Recorded assembly exceeds bounded hash-verification size', execution_hash)
            elif sha256(assembly) != record.get('assembly_sha256'):
                result = unavailable('Recorded primary assembly hash differs from actual file', execution_hash)
                result['status'] = 'invalid'
            else:
                from pipeline.graph_artifacts import build_graph_artifacts
                options = {'source_role': role}
                if record['tool'] == 'plassembler' and role == 'final':
                    options['assembly_info_kind'] = 'plassembler'
                result = build_graph_artifacts(execution, assembly, selected.get('gfa'), selected.get('assembly_info'), **options)
                if result.get('input_hashes', {}).get('execution_sha256') != execution_hash or result.get('input_hashes', {}).get('assembly_sha256') != record.get('assembly_sha256'):
                    raise ValueError('Builder provenance differs from verified execution/assembly')
        result['collection'] = {'source_role': role, 'candidate_files': observed,
                                'recorded_primary_assembly_sha256': record.get('assembly_sha256'),
                                'assembly_hash_verified': bool(record.get('assembly_sha256')) and result.get('input_hashes', {}).get('assembly_sha256') == record.get('assembly_sha256'),
                                'checkpoint_policy': 'Opaque raven.cereal is not opened or exported.'}
    result['collection'] = {**result.get('collection', {}), 'batch_id': batch_id, 'execution_relative_path': str(Path(relative)),
                            'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                            'source_reads_modified': False, 'sequence_exported': False}
    return result


def collect_selected(source_root, batch_id, executions):
    if not executions or len(executions) > MAX_SELECTIONS or len(set(executions)) != len(executions):
        raise ValueError('Select one to eight unique explicit execution paths')
    output = []
    for relative in executions:
        try:
            artifact = collect_execution(source_root, batch_id, relative)
        except (ValueError, OSError, KeyError, TypeError) as error:
            artifact = unavailable('Collection validation or parser failed: ' + type(error).__name__)
            artifact['status'] = 'invalid'
            artifact['collection'] = {'batch_id': batch_id, 'execution_relative_path': str(relative), 'sequence_exported': False}
        if len(json.dumps(artifact).encode()) > 8 * 1024 * 1024:
            hashes = artifact.get('input_hashes', {})
            artifact = unavailable('Sequence-free sidecar exceeds eight-MiB bound', hashes.get('execution_sha256'), hashes.get('assembly_sha256'))
            artifact['status'] = 'unsupported'
        output.append({'execution_relative_path': relative, 'artifact': artifact})
    return {'schema_version': 1, 'batch_id': batch_id, 'executions': output}


REMOTE_BOOTSTRAP = '''import sys
sys.dont_write_bytecode=True
import json,types
from pathlib import Path
payload=json.load(sys.stdin)
root=Path(payload['source_root'])
package=types.ModuleType('pipeline'); package.__path__=[]
sys.modules['pipeline']=package
for name in ['common','graph_artifacts']:
 module=types.ModuleType('pipeline.'+name)
 module.__package__='pipeline'; module.__file__=str(root/'pipeline'/(name+'.py'))
 sys.modules[module.__name__]=module
 exec(compile(payload['modules'][name],module.__file__,'exec'),module.__dict__)
sys.argv=['collect_graph_artifacts.py']+payload['argv']
namespace={'__name__':'__main__','__file__':str(root/'scripts/collect_graph_artifacts.py')}
exec(compile(payload['collector'],namespace['__file__'],'exec'),namespace)
'''


def collect_remote(host, source_root, batch_id, executions, remote_python=None):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+', host) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(source_root)):
        raise ValueError('Use a simple SSH destination and absolute remote benchmark directory')
    identifier(batch_id)
    if not executions or len(executions) > MAX_SELECTIONS or len(set(executions)) != len(executions):
        raise ValueError('Select one to eight unique explicit execution paths')
    for relative in executions:
        selected_execution(Path(source_root) / 'runs' / batch_id, relative)
    interpreter = remote_python or str(Path(source_root) / '.pixi/envs/default/bin/python')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', interpreter):
        raise ValueError('Remote Python must be an absolute executable path')
    argv = ['--source-root', str(source_root), '--batch', batch_id, '--emit']
    for relative in executions:
        argv += ['--execution', relative]
    payload = {'source_root': str(source_root), 'argv': argv,
               'modules': {name: (ROOT / 'pipeline' / (name + '.py')).read_text() for name in ('common', 'graph_artifacts')},
               'collector': Path(__file__).read_text()}
    response = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', host,
                               shlex.join([interpreter, '-B', '-c', REMOTE_BOOTSTRAP])],
                              input=json.dumps(payload), text=True, capture_output=True, timeout=180)
    if response.returncode not in (0, 1) or not response.stdout.strip():
        raise RuntimeError('Read-only SSH helper failed; no source files changed and no interactive reauthentication requested')
    if len(response.stdout.encode()) > MAX_RESPONSE_BYTES:
        raise ValueError('Remote response exceeds bounded metadata size')
    document = json.loads(response.stdout)
    if document.get('batch_id') != batch_id or [row['execution_relative_path'] for row in document.get('executions', [])] != executions:
        raise ValueError('Remote response does not match explicit selection')
    return document


def write_sidecars(output_root, batch_id, document):
    import os
    import tempfile
    output_root = Path(output_root).resolve()
    if not output_root.is_relative_to(ROOT.resolve()):
        raise ValueError('Collected sidecars must stay inside assembly-benchmark')
    batch = inside(output_root, 'runs/' + identifier(batch_id))
    written = []
    for row in document['executions']:
        execution, unused = selected_execution(batch, row['execution_relative_path'])
        directory = execution.parent
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, prefix='.graph-artifacts-', suffix='.tmp', delete=False) as stream:
            json.dump(row['artifact'], stream, indent=2, sort_keys=True)
            stream.write('\n')
            temporary = stream.name
        destination = directory / 'graph_artifacts.json'
        os.replace(temporary, destination)
        written.append(str(destination.relative_to(output_root)))
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--execution', action='append', required=True, help='Explicit batch-relative execution.json path; max eight')
    parser.add_argument('--source-root', type=Path, default=ROOT, help='Existing local or remote benchmark root')
    parser.add_argument('--output-root', type=Path, default=ROOT, help='Local destination root inside assembly-benchmark')
    parser.add_argument('--ssh-host', help='Optional existing SSH route; BatchMode only')
    parser.add_argument('--remote-python', help='Existing remote Python3.10+; default Pixi default/bin/python')
    parser.add_argument('--emit', action='store_true', help='Return sequence-free JSON without writing sidecars')
    args = parser.parse_args(argv)
    identifier(args.batch)
    if not args.execution or len(args.execution) > MAX_SELECTIONS or len(set(args.execution)) != len(args.execution):
        raise ValueError('Select one to eight unique explicit execution paths')
    if args.ssh_host:
        document = collect_remote(args.ssh_host, args.source_root, args.batch, args.execution, args.remote_python)
    else:
        document = collect_selected(args.source_root, args.batch, args.execution)
    errors = any(row['artifact']['status'] in {'invalid', 'unsupported'} for row in document['executions'])
    if args.emit:
        print(json.dumps(document, sort_keys=True))
    else:
        from collections import Counter
        written = write_sidecars(args.output_root, args.batch, document)
        print(json.dumps({'batch_id': args.batch, 'written': written,
                          'status_counts': dict(Counter(row['artifact']['status'] for row in document['executions']))}, indent=2))
    return int(errors)


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
