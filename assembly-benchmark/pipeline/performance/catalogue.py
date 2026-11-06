"""Select a frozen balanced subset of Wick/Holt's published simulated datasets."""
import hashlib
import json
from pathlib import Path
import random
import re
import zipfile
import xml.etree.ElementTree as ET

from ..common import digest

SOURCE_REVISION = '4bc676c4a5b01602abf1143bfefcaab4cc0dde97'
DATASET_ID = re.compile(r'^\d{3}_GCF_\d{9}\.\d+$')


def original_catalogue(workbook):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(workbook) as archive:
        strings = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        def rows(name):
            result = []
            for row in ET.fromstring(archive.read(name)).findall('.//s:sheetData/s:row', ns):
                values = {}
                for cell in row:
                    value = cell.find('s:v', ns)
                    value = value.text if value is not None else ''
                    values[re.sub(r'\d', '', cell.get('r'))] = strings[int(value)] if cell.get('t') == 's' and value else value
                result.append(values)
            return result
        genomes = rows('xl/worksheets/sheet1.xml')[1:]
        molecules = rows('xl/worksheets/sheet2.xml')[1:]
    result = {}
    columns = {'I': 'depth', 'K': 'length_mean', 'L': 'length_sd', 'N': 'identity_mean',
               'O': 'identity_max', 'P': 'identity_sd', 'Q': 'junk_percent', 'R': 'random_percent',
               'S': 'chimera_percent', 'T': 'glitch_rate', 'U': 'glitch_size_skip', 'V': 'adapter_length'}
    for row in genomes:
        identifier = Path(row.get('A', '')).stem
        if not DATASET_ID.fullmatch(identifier):
            continue
        if identifier in result:
            raise ValueError('Duplicated published dataset ID')
        result[identifier] = {'id': identifier, 'assembly_accession': identifier[4:],
            'organism': row['F'] if row['F'] not in ('none', '') else row['G'],
            'ncbi_taxonomy_as_published': row['F'], 'gtdb_taxonomy_as_published': row['G'],
            'plasmid_count': int(float(row['B'])), 'total_size_bp': int(float(row['C'])),
            'badread_command_as_published': row['H'],
            'badread_parameters': {key: float(row[column]) for column, key in columns.items()},
            'published_read_statistics': {'read_count': int(float(row['W'])),
                 'total_read_bases': int(float(row['X'])), 'read_n50_bp': int(float(row['Y'])),
                 'mean_depth': float(row['Z'])}, 'replicons': []}
    for row in molecules:
        if row.get('A') not in result:
            continue
        result[row['A']]['replicons'].append({'refseq_accession': row['B'], 'replicon_name': row['B'],
            'molecule_type': row['C'], 'length_bp': int(float(row['D'])),
            'topology': 'circular', 'topology_scope': 'Original study simulation assumption; not a native-topology claim.',
            'source_relative_depth': float(row['F']), 'published_achieved_depth': float(row['G'])})
    if len(result) != 500:
        raise ValueError('Expected the original 500 simulated datasets')
    for item in result.values():
        if (sum(r['molecule_type'] == 'plasmid' for r in item['replicons']) != item['plasmid_count']
                or sum(r['length_bp'] for r in item['replicons']) != item['total_size_bp']):
            raise ValueError('Published input metadata disagree')
    return sorted(result.values(), key=lambda item: item['id'])


def select(catalogue, seed=20261106):
    """Mirror the original balance and total plasmid count, at one-tenth scale."""
    rng = random.Random(seed)
    with_plasmids = [d for d in catalogue if d['plasmid_count']]
    without = [d for d in catalogue if not d['plasmid_count']]
    if len(catalogue) != 500 or min(len(with_plasmids), len(without)) < 25:
        raise ValueError('The published sampling frame is insufficient')
    for attempt in range(100000):
        chosen = rng.sample(with_plasmids, 25)
        if sum(d['plasmid_count'] for d in chosen) == 50:
            break
    else:
        raise ValueError('Could not draw the declared plasmid-count balance')
    chosen += rng.sample(without, 25)
    rng.shuffle(chosen)
    return {'schema_version': 1, 'track': 'broad-performance', 'panel_id': 'wick-subset-50-v1',
            'seed': seed, 'dataset_count': 50, 'with_plasmids': 25, 'without_plasmids': 25,
            'plasmid_count': 50, 'sampling_attempts': attempt + 1,
            'source_pool_with_plasmids': len(with_plasmids), 'source_pool_without_plasmids': len(without),
            'source_pool_note': 'Paper describes 250/250; the frozen workbook labels 254/246. Selection uses the workbook classifications and records this difference.',
            'sampling_method': 'Seeded sample of 25 plasmid-containing genomes, conditioned on 50 plasmids, and 25 without plasmids from the original 500 published simulated inputs.',
            'source_revision': SOURCE_REVISION, 'datasets': chosen}


def freeze(workbook, read_metadata, reference_metadata):
    result = select(original_catalogue(workbook))
    reads = next(f for f in read_metadata['files'] if f['name'] == 'simulated_read_sets.tar')
    references = next(f for f in reference_metadata['files'] if f['name'] == 'reference_genomes.tar.gz')
    result['archives'] = {name: {k: item[k] for k in ('id', 'name', 'size', 'download_url', 'computed_md5')}
                          for name, item in [('reads', reads), ('references', references)]}
    result['sources'] = {'workbook_sha256': digest(workbook), 'read_article_id': read_metadata['id'],
                         'reference_article_id': reference_metadata['id'], 'licence': 'CC BY 4.0',
                         'attribution': 'Ryan R. Wick and Kathryn E. Holt, Long-read-assembler-comparison.'}
    return result
