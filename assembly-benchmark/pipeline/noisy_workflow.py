"""Freeze simulator assets and pair source fragments across error conditions."""
import argparse
import copy
import re
import shutil
from .common import ROOT, fingerprint, load, save, digest


def freeze(config, batch):
    from .noisy_reads import inspect_runtime
    runtimes = {profile['id']: inspect_runtime(profile) for profile in config['noisy_panel']['profiles'] if profile['id'] != 'matched-exact'}
    from .assessments import truth_controls
    truth_controls(config,batch)
    save(batch/'provenance/noisy-runtime.json', {'profiles':runtimes})
    return runtimes


def simulate_noise(case, sequences, batch, directory):
    from .reads import exact_reads
    clean = source_case(case)
    source = reuse_frozen_source(clean, batch, directory/'clean') if clean.get('frozen_source') else exact_reads(clean, sequences, directory/'clean')
    if source['status'] != 'valid':
        raise ValueError('Clean source fragments failed input admission')
    profile = copy.deepcopy(case['error_profile'])
    if profile['id'] == 'matched-exact':
        for filename in ('reads.fastq.gz','read_origins.tsv.gz','truth.fasta'):
            shutil.copy2(directory/'clean'/filename, directory/filename)
        result = {**source, 'case':case, 'model':'matched-error-v1', 'error_profile':profile,
                  'limitation':'Matched error-free geometry control. Q40 is a placeholder, not measured uncertainty.'}
    else:
        from .noisy_reads import transform_fragments
        runtime = load(batch/'provenance/noisy-runtime.json')['profiles'][profile['id']]
        profile['expected_runtime_sha256'] = runtime['sha256']
        result = transform_fragments(directory/'clean/reads.fastq.gz',directory/'clean/read_origins.tsv.gz',directory,profile,case)
        result.update(case=case, model='matched-error-v1', error_profile=case['error_profile'])
    result['source_fragments_sha256'] = source['reads_sha256']
    result['source_origins_sha256'] = source['origins_sha256']
    result['source_truth_sha256'] = source['truth_sha256']
    save(directory/'input.json', result)
    return result


def verified_frozen_source(clean, batch):
    """Verify a declared existing fragment set without generating any reads."""
    from .noisy_reads import GEOMETRY_FIELDS
    source = clean['frozen_source']
    for key in ('batch', 'scenario_id'):
        if not isinstance(source.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', source[key]):
            raise ValueError('Frozen source requires simple batch/scenario identifiers')
    runs = batch.parent.resolve()
    directory = (runs/source['batch']/'cases'/source['scenario_id']).resolve()
    if not directory.is_relative_to(runs) or source['batch'] == batch.name:
        raise ValueError('Frozen source must be an existing distinct batch under runs')
    manifest_path = directory/'input.json'
    if digest(manifest_path) != source.get('input_manifest_sha256'):
        raise ValueError('Frozen source manifest checksum changed')
    manifest = load(manifest_path)
    original = manifest.get('case', {})
    if manifest.get('status') != 'valid' or manifest.get('model') != 'exact-lognormal-v1':
        raise ValueError('Frozen source must be an admitted error-free fragment set')
    if original.get('id') != source['scenario_id'] or original.get('fingerprint') != fingerprint({k:v for k,v in original.items() if k != 'fingerprint'}):
        raise ValueError('Frozen source scenario identity/fingerprint changed')
    if original.get('replicons') != clean['replicons'] or any(original.get('simulation', {}).get(k) != clean['simulation'].get(k) for k in GEOMETRY_FIELDS + ['fastq_phred']):
        raise ValueError('Frozen source replicons or fragment geometry differ from the new case')
    for filename, key in [('reads.fastq.gz','reads_sha256'), ('truth.fasta','truth_sha256'), ('read_origins.tsv.gz','origins_sha256')]:
        expected = source.get(key)
        if not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected) or manifest.get(key) != expected or digest(directory/filename) != expected:
            raise ValueError('Frozen source file checksum changed: ' + filename)
    return directory, manifest


def reuse_frozen_source(clean, batch, directory):
    original, manifest = verified_frozen_source(clean, batch)
    directory = directory.resolve()
    if not directory.is_relative_to(batch.resolve()):
        raise ValueError('Reused fragments must remain inside the new batch')
    directory.mkdir(parents=True, exist_ok=True)
    files = {'reads.fastq.gz':'reads_sha256', 'truth.fasta':'truth_sha256', 'read_origins.tsv.gz':'origins_sha256', 'source-input.json':'input_manifest_sha256'}
    for filename, key in files.items():
        target = directory/filename
        if target.exists():
            if digest(target) != clean['frozen_source'][key]:
                raise ValueError('Existing reused fragment file differs: ' + filename)
        else:
            shutil.copy2(original/('input.json' if filename == 'source-input.json' else filename), target)
        if digest(target) != clean['frozen_source'][key]:
            raise ValueError('Copied frozen source checksum changed: ' + filename)
    result = {**manifest, 'case':copy.deepcopy(clean), 'reused_source':copy.deepcopy(clean['frozen_source'])}
    save(directory/'input.json', result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze'])
    parser.add_argument('--batch',required=True)
    args=parser.parse_args()
    from benchmark import batch_path
    batch=batch_path(args.batch)
    freeze(load(batch/'config.json'), batch)


def source_case(case):
    clean = copy.deepcopy(case)
    clean['simulation']['model'] = 'exact-lognormal-v1'
    clean.pop('error_profile', None)
    clean['id'] = case['source_case_id'] + '-fragments-seed-' + str(case['simulation']['seed'])
    clean['title'] = 'Frozen source fragments: ' + clean['id']
    clean['category'] = 'S1'
    clean['profile_id'] = 'matched-fragment-source-v1'
    clean['fingerprint'] = fingerprint({key:value for key,value in clean.items() if key != 'fingerprint'})
    return clean


if __name__=='__main__':
    main()
