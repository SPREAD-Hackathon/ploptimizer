"""Bounded range access to published TAR members; never fetch the whole read archive."""
import hashlib
import http.client
import re
import tarfile
import time
import urllib.request

from ..common import load, save


def ranged_response(source, start, length):
    if start < 0 or length < 1 or start + length > source['size']:
        raise ValueError('Range outside the pinned archive')
    request = urllib.request.Request(source['download_url'], headers={'Range': f'bytes={start}-{start + length - 1}'})
    for attempt in range(4):
        try:
            response = urllib.request.urlopen(request, timeout=120)
            expected = f'bytes {start}-{start + length - 1}/{source["size"]}'
            if response.status != 206 or response.headers.get('Content-Range') != expected:
                response.close()
                raise ValueError('Server did not honour the exact bounded range; refusing a whole-archive download')
            return response
        except (OSError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(min(2 ** attempt, 8))


def index_reads(source, output):
    """Inspect 512-byte TAR headers, seeking over compressed read payloads."""
    state = load(output) if output.exists() else {'schema_version': 1, 'status': 'indexing',
             'archive': source, 'next_offset': 0, 'members': [], 'header_bytes_fetched': 0}
    if state['archive'] != source:
        raise ValueError('Pinned read archive changed')
    if state['status'] == 'complete':
        return state
    offset = state['next_offset']
    while offset + 512 <= source['size']:
        with ranged_response(source, offset, 512) as response:
            header = response.read(513)
        if len(header) != 512:
            raise ValueError('Truncated TAR header')
        state['header_bytes_fetched'] += 512
        if header == b'\0' * 512:
            state['status'] = 'complete'
            break
        member = tarfile.TarInfo.frombuf(header, 'utf-8', 'strict')
        if member.isfile():
            if not re.fullmatch(r'\d{3}_GCF_\d{9}\.\d+\.fastq\.gz', member.name):
                raise ValueError('Unexpected simulated read archive member: ' + member.name)
            state['members'].append({'name': member.name, 'offset': offset + 512,
                                    'size': member.size, 'header_sha256': hashlib.sha256(header).hexdigest()})
        elif not member.isdir():
            raise ValueError('Unsupported TAR record; no payload downloaded')
        offset += 512 + ((member.size + 511) // 512) * 512
        state['next_offset'] = offset
        save(output, state)
    if state['status'] != 'complete' or len(state['members']) != 500 or len({m['name'] for m in state['members']}) != 500:
        raise ValueError('Read archive index does not contain the expected unique 500 datasets')
    save(output, state)
    return state


def fetch_member(source, member, destination):
    if destination.exists():
        raise ValueError('Do not overwrite a retained read set')
    temporary = destination.with_suffix(destination.suffix + '.download')
    for attempt in range(4):
        checksum = hashlib.sha256()
        count = 0
        try:
            with ranged_response(source, member['offset'], member['size']) as response, temporary.open('wb') as output:
                while count < member['size']:
                    block = response.read(min(1024 * 1024, member['size'] - count))
                    if not block:
                        raise EOFError('Truncated TAR member')
                    output.write(block)
                    checksum.update(block)
                    count += len(block)
            temporary.replace(destination)
            return {'sha256': checksum.hexdigest(), 'bytes': count,
                    'archive_member': member, 'download_attempts': attempt + 1}
        except (OSError, EOFError, http.client.IncompleteRead):
            if attempt == 3:
                raise
            time.sleep(min(2 ** attempt, 8))
        finally:
            if temporary.exists():
                temporary.unlink()
