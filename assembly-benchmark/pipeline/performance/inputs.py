"""Verify and cache selected published inputs; no read simulation or changes."""
import gzip
import hashlib
import os
import shutil
import tarfile
import urllib.request
from collections import Counter
from pathlib import Path

from ..common import digest, fasta, fingerprint, load, save
from .archive import fetch_member


def cases(selection):
    result = []
    for dataset in selection['datasets']:
        case = dict(dataset, category='P1', title=dataset['id'], track='broad-performance')
        case['fingerprint'] = fingerprint(case)
        result.append(case)
    if len(result) != 50 or len({case['id'] for case in result}) != 50:
        raise ValueError('Expected exactly fifty distinct frozen datasets')
    return result


def download_references(selection, directory):
    """Download the original compact reference archive, checking its published MD5."""
    directory.mkdir(parents=True, exist_ok=True)
    source = selection['archives']['references']
    archive = directory / source['name']
    receipt = directory / 'reference-archive.json'
    if archive.exists():
        checksum = hashlib.md5()
        with archive.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(block)
        if archive.stat().st_size != source['size'] or checksum.hexdigest() != source['computed_md5']:
            raise ValueError('Cached reference archive differs from the published bytes')
    else:
        temporary = archive.with_suffix(archive.suffix + '.download')
        checksum = hashlib.md5()
        try:
            with urllib.request.urlopen(source['download_url'], timeout=120) as response, temporary.open('wb') as output:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    checksum.update(block)
                    output.write(block)
            if temporary.stat().st_size != source['size'] or checksum.hexdigest() != source['computed_md5']:
                raise ValueError('Downloaded reference archive failed published size/MD5 verification')
            temporary.replace(archive)
        finally:
            if temporary.exists():
                temporary.unlink()
    selected = {case['id']: case for case in cases(selection)}
    extracted = {}
    with tarfile.open(archive, 'r:gz') as stream:
        for member in stream:
            name = Path(member.name)
            if not member.isfile() or name.name not in {identifier + '.fasta' for identifier in selected}:
                continue
            identifier = name.stem
            if identifier in extracted:
                raise ValueError('Duplicate selected reference member')
            destination = directory / name.name
            with stream.extractfile(member) as source_file, destination.with_suffix('.fasta.tmp').open('wb') as output:
                shutil.copyfileobj(source_file, output)
            destination.with_suffix('.fasta.tmp').replace(destination)
            records = fasta(destination)
            expected = {r['refseq_accession']: r['length_bp'] for r in selected[identifier]['replicons']}
            if {name: len(sequence) for name, sequence in records.items()} != expected:
                raise ValueError('Published reference IDs/lengths differ from selected workbook metadata: ' + identifier)
            extracted[identifier] = {'file': destination.name, 'sha256': digest(destination), 'bytes': destination.stat().st_size}
    if set(extracted) != set(selected):
        raise ValueError('Reference archive does not contain every selected dataset')
    result = {'status': 'complete', 'archive': source, 'archive_sha256': digest(archive), 'selected': extracted}
    save(receipt, result)
    return result


def fastq_statistics(path):
    """Check every FASTQ record and gzip CRC, retaining only bounded statistics."""
    count = total = 0
    lengths = Counter()
    content_hash = hashlib.sha256()
    with gzip.open(path, 'rb') as stream:
        while True:
            header = stream.readline()
            if not header:
                break
            sequence, plus, quality = stream.readline(), stream.readline(), stream.readline()
            if not (header.startswith(b'@') and plus.startswith(b'+') and sequence and quality):
                raise ValueError('Invalid or truncated FASTQ record')
            sequence_length = len(sequence.rstrip(b'\r\n'))
            if sequence_length != len(quality.rstrip(b'\r\n')) or sequence_length == 0:
                raise ValueError('FASTQ sequence/quality length mismatch')
            for line in (header, sequence, plus, quality):
                content_hash.update(line)
            count += 1
            total += sequence_length
            lengths[sequence_length] += 1
    if not count:
        raise ValueError('Published FASTQ is empty')
    cumulative = 0
    for length, frequency in sorted(lengths.items(), reverse=True):
        cumulative += length * frequency
        if cumulative * 2 >= total:
            n50 = length
            break
    return {'read_count': count, 'total_read_bases': total, 'read_n50_bp': n50,
            'uncompressed_fastq_sha256': content_hash.hexdigest()}


def prepare_input(case, batch, selection, archive_index):
    directory = batch / 'cases' / case['id']
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'input.json'
    reads = directory / 'reads.fastq.gz'
    truth = directory / 'truth.fasta'
    if manifest_path.exists():
        previous = load(manifest_path)
        if previous.get('case') != case or previous.get('status') != 'valid':
            raise ValueError('Existing input is not the matching admitted frozen dataset')
        if digest(reads) != previous['reads_sha256'] or digest(truth) != previous['truth_sha256']:
            raise ValueError('Existing input bytes changed')
        return previous
    receipt = load(batch / 'reference-cache/reference-archive.json')
    reference = batch / 'reference-cache' / (case['id'] + '.fasta')
    if receipt['selected'][case['id']]['sha256'] != digest(reference):
        raise ValueError('Cached reference differs from its admission receipt')
    if truth.exists():
        if digest(truth) != digest(reference):
            raise ValueError('A different truth file already exists')
    else:
        os.link(reference, truth)
    members = [m for m in archive_index['members'] if m['name'] == case['id'] + '.fastq.gz']
    if len(members) != 1 or archive_index['archive'] != selection['archives']['reads']:
        raise ValueError('Read range does not identify the frozen archive member')
    if reads.exists():
        read_receipt = load(directory / 'read-download.json')
        if read_receipt['sha256'] != digest(reads) or read_receipt['archive_member'] != members[0]:
            raise ValueError('Existing read download has no matching checksum receipt')
    else:
        read_receipt = fetch_member(selection['archives']['reads'], members[0], reads)
        save(directory / 'read-download.json', read_receipt)
    statistics = fastq_statistics(reads)
    expected = case['published_read_statistics']
    for key in ('read_count', 'total_read_bases', 'read_n50_bp'):
        if statistics[key] != expected[key]:
            raise ValueError('Published FASTQ statistics differ from the workbook: ' + key)
    result = {'schema_version': 1, 'status': 'valid', 'case': case,
              'model': 'published-Badread-v0.1.5-frozen-bytes',
              'reads_sha256': read_receipt['sha256'], 'truth_sha256': digest(truth),
              'source_read_archive': selection['archives']['reads'], 'source_reference_archive': selection['archives']['references'],
              'read_archive_member': members[0], 'statistics': statistics,
              'validation_summary': 'Published bytes downloaded without simulation or reordering; gzip CRC, FASTQ structure and published count/bases/N50 verified.'}
    save(manifest_path, result)
    return result
