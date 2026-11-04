"""Freeze simulator assets and pair source fragments across error conditions."""
import argparse
import copy
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
    source = exact_reads(clean, sequences, directory/'clean')
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
