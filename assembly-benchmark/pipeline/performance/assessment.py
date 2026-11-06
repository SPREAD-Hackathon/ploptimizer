"""Wick/Holt longest-alignment assessment of frozen broad-benchmark outputs."""
import datetime
import subprocess
from pathlib import Path
from ..common import digest, fasta, load, save, write_fasta
from .vendor import wick_assess_assembly as wick

METHOD = 'wick-longest-alignment-v1'
COMPLETENESS_THRESHOLD = 0.99
ELAPSED_SCOPE = 'Workflow wall time including input verification and exact assessment; excludes downloads and scheduler wait.'
MEMORY_SCOPE = 'GNU time peak resident memory of the assembler process tree.'
OUTCOMES = ('fully_complete', 'chromosome_complete', 'incomplete', 'empty',
            'did_not_complete', 'execution_error')


def _inside(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if root not in path.parents:
        raise ValueError('Assessment source must stay within its batch')
    return path


def _relative(root, path):
    return str(Path(path).resolve().relative_to(Path(root).resolve()))


def mapping_command(tripled_reference, assembly, threads=1, mapper='minimap2'):
    if isinstance(threads, bool) or not isinstance(threads, int) or threads < 1:
        raise ValueError('Positive mapper thread count required')
    return [mapper, '-c', '-t', str(threads), '-x', 'asm20', '-r', '10000',
            '-g', '10000', '-z', '1000,500', str(tripled_reference), str(assembly)]


def parse_alignments(path, references, queries):
    """Validate inventories before using the pinned upstream PAF parser."""
    alignments = []
    with Path(path).open() as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            fields = line.rstrip('\n').split('\t')
            if len(fields) < 12:
                raise ValueError(f'Invalid PAF row {number}')
            query, qlength, qstart, qend, strand, reference, rlength, rstart, rend, matches, block = fields[:11]
            qlength, qstart, qend, rlength, rstart, rend, matches, block = map(
                int, (qlength, qstart, qend, rlength, rstart, rend, matches, block))
            if (query not in queries or reference not in references
                    or queries[query] != qlength or references[reference] * 3 != rlength
                    or not 0 <= qstart < qend <= qlength or not 0 <= rstart < rend <= rlength
                    or strand not in ('+', '-') or not 0 <= matches <= block or block <= 0
                    or not any(field.startswith('cg:Z:') for field in fields[12:])):
                raise ValueError(f'PAF row {number} disagrees with frozen source inventories')
            try:
                alignment = wick.Alignment(line)
            except SystemExit as error:
                raise ValueError(f'Invalid upstream alignment row {number}: {error}') from error
            alignments.append(alignment)
    return alignments


def summarise_alignments(case, alignments):
    """Preserve upstream span selection and strict identity-measurement threshold."""
    molecules = []
    for replicon in case['replicons']:
        accession, length = replicon['refseq_accession'], replicon['length_bp']
        if not isinstance(length, int) or isinstance(length, bool) or length <= 0:
            raise ValueError('Positive reference length required')
        matches = [a for a in alignments if a.ref_name == accession]
        best = sorted(matches, key=lambda a: (a.ref_align_length, 1.0 / (a.ref_start + 1)))[-1] if matches else None
        measured = best is not None and (best.ref_align_length > 100000 or best.ref_align_length > length / 4)
        contig, contiguity, original_identity, original_indel = wick.get_contiguity(
            accession, length, alignments, [], [], 'replicon')
        molecules.append({'accession': accession, 'name': replicon.get('replicon_name', accession),
            'molecule_type': replicon['molecule_type'], 'length_bp': length,
            'contiguity': contiguity, 'complete': contiguity >= COMPLETENESS_THRESHOLD,
            'contig_id': contig or None, 'identity_measured': measured,
            'identity': original_identity if measured else None,
            'max_indel_bp': original_indel if measured else None,
            'longest_alignment_span_bp': best.ref_align_length if best is not None else 0,
            'alignment_count': len(matches),
            'reference_interval_tripled_0based_half_open': [best.ref_start, best.ref_end] if best else None,
            'query_interval_0based_half_open': [best.query_start, best.query_end] if best else None,
            'strand': best.strand if best else None,
            'source_relative_depth': replicon.get('source_relative_depth'),
            'published_achieved_depth': replicon.get('published_achieved_depth'),
            'identity_measurement_rule': 'Longest alignment span >100,000 bp or >one quarter of the reference length.'})
    return molecules


def classify(molecules, query_count):
    if query_count == 0:
        return 'empty'
    if all(m['complete'] for m in molecules):
        return 'fully_complete'
    chromosomes = [m for m in molecules if m['molecule_type'] == 'chromosome']
    return 'chromosome_complete' if chromosomes and all(m['complete'] for m in chromosomes) else 'incomplete'


def _assembly_input(record, directory, batch, output):
    """Join final Plassembler plasmids and the actual retained chromosome only."""
    assembly = _inside(batch, batch / record['assembly_file'])
    if not assembly.is_file() or digest(assembly) != record.get('assembly_sha256'):
        raise ValueError('Final assembly differs from the frozen execution record')
    sources = [{'role': 'final_assembly', 'file': _relative(batch, assembly),
                'sha256': digest(assembly), 'bytes': assembly.stat().st_size}]
    if record['tool'] != 'plassembler':
        return assembly, sources, [{'contig_id': name, 'source_role': 'final_assembly', 'source_contig_id': name}
                                   for name in fasta(assembly)]
    chromosome = _inside(batch, batch / record['retained_chromosome_file']) if record.get('retained_chromosome_file') else directory / 'output/chromosome.fasta'
    chromosome = _inside(batch, chromosome)
    expected = record.get('retained_chromosome_sha256')
    if expected and (not chromosome.is_file() or digest(chromosome) != expected):
        raise ValueError('Retained chromosome differs from the frozen execution record')
    combined, origin = {}, []
    for role, path in [('final_plasmids', assembly), ('retained_chromosome', chromosome)]:
        if not path.is_file():
            sources.append({'role': role, 'file': _relative(batch, path), 'status': 'not_produced'})
            continue
        if role == 'retained_chromosome':
            sources.append({'role': role, 'file': _relative(batch, path), 'sha256': digest(path),
                            'bytes': path.stat().st_size, 'execution_hash_recorded': bool(expected)})
        for name, sequence in fasta(path).items():
            identifier = role + ':' + name
            combined[identifier] = sequence
            origin.append({'contig_id': identifier, 'source_role': role, 'source_contig_id': name})
    joined = output / 'final-plasmids-and-retained-chromosome.fasta'
    write_fasta(joined, combined)
    return joined, sources, origin


def assess(case, execution_path, batch, threads=1, mapper='minimap2', timeout=1800):
    """Assess one frozen execution and persist a small, source-bound record."""
    batch = Path(batch).resolve()
    execution_path = _inside(batch, execution_path)
    if (batch / 'results').resolve() not in execution_path.parents or execution_path.name != 'execution.json':
        raise ValueError('Expected this batch execution record')
    directory = execution_path.parent
    target = directory / 'performance.json'
    record = load(execution_path)
    result = {'schema_version': 1, 'track': 'broad-performance', 'assessment': METHOD,
              'dataset_id': case['id'], 'tool': record.get('tool'), 'status': 'running',
              'execution_status': record.get('status'), 'batch_id': batch.name,
              'completion_threshold': COMPLETENESS_THRESHOLD,
              'elapsed_seconds': record.get('elapsed_seconds'), 'peak_memory_kb': record.get('peak_memory_kb'),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'replicons': [], 'commands': {'assembly': record.get('command', [])},
              'version': record.get('version'), 'threads': record.get('threads'),
              'resource_scope': ELAPSED_SCOPE + (' Miniasm + Minipolish sums the recorded raw and polishing worker times.' if record.get('tool') == 'miniasm-plus' else ''),
              'elapsed_scope': ELAPSED_SCOPE + (' Sum of raw assembly and polishing worker times.' if record.get('tool') == 'miniasm-plus' else ''),
              'memory_scope': MEMORY_SCOPE + (' Larger peak from the two sequential phases.' if record.get('tool') == 'miniasm-plus' else ''),
              'execution_resource_scope': record.get('resource_scope'),
              'provenance': {'execution_file': _relative(batch, execution_path), 'execution_sha256': digest(execution_path),
                             'assessment_source_sha256': digest(Path(__file__)),
                             'upstream_source_sha256': digest(Path(wick.__file__)),
                             'upstream_revision': '4bc676c4a5b01602abf1143bfefcaab4cc0dde97'}}
    workflow = record.get('assembly_workflow') or {}
    result['versions'] = dict(workflow.get('versions') or {})
    result['versions'].setdefault(record.get('tool', 'assembler'), record.get('version'))
    result['workflow_steps'] = []
    for number, step in enumerate(workflow.get('steps', []), 1):
        label = ('reused_source_' if step.get('reused_source_stage') else 'workflow_') + str(number)
        if step.get('command'):
            result['commands'][label] = step['command']
        result['workflow_steps'].append({key: step[key] for key in
            ('name','command','reused_source_stage','status','exit_code') if key in step})
    result['phase_resources'] = {key: value for key, value in {
        'source_elapsed_seconds': workflow.get('source_elapsed_seconds'),
        'source_peak_memory_kb': workflow.get('source_peak_memory_kb'),
        'polishing_elapsed_seconds': record.get('polishing_elapsed_seconds')}.items() if value is not None}
    try:
        _assess_saved(case, record, batch, directory, result, threads, mapper, timeout)
    except Exception as error:
        result.update(status='error', genome_outcome='execution_error', failure_scope='assessment',
                      complete_chromosome=None, complete_all=None, replicons=[],
                      error=f'{type(error).__name__}: {error}')
    finally:
        result['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save(target, result)
    return result


def _assess_saved(case, record, batch, directory, result, threads, mapper, timeout):
    if record.get('scenario_id') != case['id']:
        raise ValueError('Execution does not identify this frozen dataset')
    if record.get('status') not in ('pass', 'fail'):
        if record.get('status') in ('timeout', 'error', 'invalid_input'):
            outcome = 'did_not_complete' if record.get('status') == 'timeout' or record.get('execution_outcome') == 'did_not_complete' else 'execution_error'
            result.update(status='complete', genome_outcome=outcome, reason=record.get('error'),
                          complete_chromosome=None, complete_all=None)
            return
        raise ValueError('Assembler execution is not terminal')
    input_dir = batch / 'cases' / case['id']
    truth = _inside(batch, input_dir / 'truth.fasta')
    manifest = load(input_dir / 'input.json')
    if digest(truth) != manifest.get('truth_sha256') or digest(truth) != record.get('truth_sha256'):
        raise ValueError('Frozen reference hashes disagree')
    if record.get('reads_sha256') != manifest.get('reads_sha256'):
        raise ValueError('Execution does not identify the frozen reads')
    references = fasta(truth)
    lengths = {m['refseq_accession']: m['length_bp'] for m in case['replicons']}
    if {name: len(seq) for name, seq in references.items()} != lengths:
        raise ValueError('Frozen reference inventory differs from the case definition')
    output = directory / 'performance'; output.mkdir(exist_ok=True)
    assembly, sources, origins = _assembly_input(record, directory, batch, output)
    queries = {name: len(sequence) for name, sequence in fasta(assembly).items()}
    result['provenance'].update(input_manifest_sha256=digest(input_dir / 'input.json'),
                                truth_sha256=digest(truth), reads_sha256=record['reads_sha256'],
                                assessed_assembly_sha256=digest(assembly), assembly_sources=sources)
    result['query_count'] = len(queries)
    result['contig_sources'] = origins
    result['assessed_output_scope'] = 'Final plasmids plus actual retained chromosome' if record['tool'] == 'plassembler' else 'Final assembler FASTA'
    alignments = _map_saved(references, lengths, queries, assembly, output, batch, result, threads, mapper, timeout)
    molecules = summarise_alignments(case, alignments)
    chromosomes = [m for m in molecules if m['molecule_type'] == 'chromosome']
    result.update(status='complete', genome_outcome=classify(molecules, len(queries)),
                  replicons=molecules, complete_chromosome=all(m['complete'] for m in chromosomes),
                  complete_all=all(m['complete'] for m in molecules), alignment_count=len(alignments))
    execution_path = directory / 'execution.json'
    if digest(execution_path) != result['provenance']['execution_sha256'] or digest(truth) != result['provenance']['truth_sha256']:
        raise ValueError('Frozen execution/reference changed during assessment')
    for source in sources:
        if source.get('sha256') and digest(batch / source['file']) != source['sha256']:
            raise ValueError('Frozen final output changed during assessment')


def _map_saved(references, lengths, queries, assembly, output, batch, result, threads, mapper, timeout):
    if not queries:
        result.update(mapper_invoked=False, mapping_reason='Final assessed output is empty; mapper was not invoked.')
        return []
    tripled = output / 'tripled-reference.fasta'
    write_fasta(tripled, {name: seq * 3 for name, seq in references.items()})
    command = mapping_command(tripled, assembly, threads, mapper)
    version_command = [mapper, '--version']
    version = subprocess.run(version_command, check=True, capture_output=True, text=True, timeout=30)
    result['mapper_version'] = (version.stdout + version.stderr).strip()
    result['versions']['assessment_minimap2'] = result['mapper_version']
    result['commands'].update(mapping=command, mapper_version=version_command)
    paf, stderr = output / 'alignment.paf', output / 'alignment.stderr.log'
    with paf.open('w') as stdout, stderr.open('w') as log:
        subprocess.run(command, stdout=stdout, stderr=log, check=True, timeout=timeout)
    alignments = parse_alignments(paf, lengths, queries)
    result['provenance'].update(paf_file=_relative(batch, paf), paf_sha256=digest(paf),
                                mapper_stderr_file=_relative(batch, stderr), mapper_stderr_sha256=digest(stderr),
                                tripled_reference_sha256=digest(tripled))
    result['mapper_invoked'] = True
    return alignments
