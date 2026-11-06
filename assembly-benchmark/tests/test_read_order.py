"""S7 validates permutation integrity and truth-independent sequence comparisons."""
import gzip
import itertools
import random
import tempfile
import unittest
from pathlib import Path
from pipeline.read_order import (records, record_fingerprints, permutation, write_order,
                                 least_rotation, sequence_fingerprint, assess_tool, stage_inputs, summarise, inherited_chromosome_topology)
from pipeline.common import digest, save, load, fingerprint


class ReadOrderTests(unittest.TestCase):
    def test_shuffle_preserves_duplicate_complete_records_and_quality(self):
        items = [b'@same\nACGT\n+\nIIII\n', b'@same\nACGT\n+\n!!!!\n', b'@same\nACGT\n+\nIIII\n', b'@other\nTGCA\n+\n####\n']
        original = record_fingerprints(items)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'reads.fastq.gz'
            indices = permutation(len(items), 1)
            self.assertEqual(sorted(indices), list(range(len(items))))
            write_order(path, items, indices)
            frozen = path.read_bytes()
            actual = record_fingerprints(records(path))
            self.assertEqual(actual['record_multiset_sha256'], original['record_multiset_sha256'])
            self.assertEqual(actual['record_count'], 4)
            write_order(path, items, indices)
            self.assertEqual(path.read_bytes(), frozen)
        self.assertNotEqual(record_fingerprints(items[:-1])['record_multiset_sha256'], original['record_multiset_sha256'])
        self.assertNotEqual(record_fingerprints(items[::-1])['record_order_sha256'], original['record_order_sha256'])
        changed = items.copy(); changed[1] = changed[0]
        self.assertNotEqual(record_fingerprints(changed)['record_multiset_sha256'], original['record_multiset_sha256'])

    def test_invalid_fastq_fails_admission(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'bad.fastq.gz'
            with gzip.open(path, 'wb') as stream:
                stream.write(b'@x\nACGT\n+\nII\n')
            with self.assertRaises(ValueError): list(records(path))

    def test_seeded_orders_are_distinct_and_reproducible(self):
        values = [permutation(100, seed) for seed in (1, 2, 3)]
        self.assertEqual(values[0], permutation(100, 1))
        self.assertEqual(len({tuple(v) for v in values}), 3)
        self.assertTrue(all(sorted(v) == list(range(100)) for v in values))

    def test_booth_matches_exhaustive_rotations(self):
        for size in range(1, 7):
            for bases in itertools.product('AC', repeat=size):
                sequence = ''.join(bases)
                self.assertEqual(least_rotation(sequence), min(sequence[i:] + sequence[:i] for i in range(size)))

    def test_normalisation_ignores_names_order_strand_but_retains_copies_and_changes(self):
        a = sequence_fingerprint([('a', 'ACGTT'), ('b', 'GGA')])
        b = sequence_fingerprint([('renamed', 'TCC'), ('other', 'AACGT')])
        self.assertEqual(a['end_sensitive_sha256'], b['end_sensitive_sha256'])
        c = sequence_fingerprint([('a', 'ACGTT'), ('b', 'GGA'), ('copy', 'GGA')])
        self.assertNotEqual(a['end_sensitive_sha256'], c['end_sensitive_sha256'])
        d = sequence_fingerprint([('a', 'ACGTA'), ('b', 'GGA')])
        self.assertNotEqual(a['end_sensitive_sha256'], d['end_sensitive_sha256'])

    def test_circular_equivalence_never_uses_a_reference(self):
        a = sequence_fingerprint([('a', 'AACGTTT')], {'a': True})
        b = sequence_fingerprint([('b', 'GTTTAAC')], {'b': True})
        self.assertNotEqual(a['end_sensitive_sha256'], b['end_sensitive_sha256'])
        self.assertEqual(a['circular_representation_sha256'], b['circular_representation_sha256'])
        self.assertIsNone(sequence_fingerprint([('a', 'AACGTTT')])['circular_representation_sha256'])

    def test_within_order_variability_is_not_called_an_order_effect(self):
        rows = [{'order_id': order, 'repeat': repeat, 'version': 'fixed', 'status': 'fail', 'signature': {'hash': h}}
                for order, hashes in [('original', ['a', 'a', 'a']), ('shuffle', ['b', 'b', 'b'])]
                for repeat, h in enumerate(hashes, 1)]
        result = assess_tool(rows, ['original', 'shuffle'], 3, 'hash')
        self.assertEqual(result['verdict'], 'Order-associated output difference')
        rows[-1]['signature']['hash'] = 'a'
        self.assertIn('Within-order variability', assess_tool(rows, ['original', 'shuffle'], 3, 'hash')['verdict'])
        rows[-1]['status'] = 'timeout'
        self.assertFalse(assess_tool(rows, ['original', 'shuffle'], 3, 'hash')['complete'])
        self.assertIn('Not assessed', assess_tool(rows[:-1], ['original', 'shuffle'], 3, 'hash')['verdict'])

    def test_different_tool_versions_are_not_pooled(self):
        rows = [{'order_id': 'one', 'repeat': i, 'version': str(i), 'status': 'pass', 'signature': {'hash': 'same'}} for i in (1, 2)]
        self.assertFalse(assess_tool(rows, ['one'], 2, 'hash')['complete'])

    def test_stage_freezes_four_orders_and_shares_bytes_across_repeats(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir(); batch = root / 'batch'; batch.mkdir()
            items = [f'@r{i}\nACGT\n+\nIIII\n'.encode() for i in range(100)]
            write_order(source / 'reads.fastq.gz', items, list(range(100)))
            (source / 'truth.fasta').write_text('>fixture\nACGT\n')
            with gzip.open(source / 'read_origins.tsv.gz', 'wt') as stream: stream.write('fixture origins\n')
            case = {'id':'frozen-case','category':'S1','replicons':[]};case['fingerprint']=fingerprint(case)
            manifest = {'status':'valid','case':case,'reads_sha256':digest(source/'reads.fastq.gz'),
                        'truth_sha256':digest(source/'truth.fasta'),'origins_sha256':digest(source/'read_origins.tsv.gz')}
            save(source/'input.json',manifest)
            config = {'read_order':{'source':{'case_id':'frozen-case','input_manifest_sha256':digest(source/'input.json'),
                        'reads_sha256':manifest['reads_sha256'],'truth_sha256_for_provenance_only':manifest['truth_sha256']},
                        'orders':[{'id':'original','shuffle_seed':None}]+[{'id':f'shuffle-{i}','shuffle_seed':i} for i in (1,2,3)],'repeats_per_order':3}}
            save(batch/'config.json',config)
            admitted=stage_inputs(batch,source)
            self.assertEqual(len(admitted['orders']),4)
            self.assertEqual(len({o['record_multiset_sha256'] for o in admitted['orders']}),1)
            self.assertEqual(len({o['record_order_sha256'] for o in admitted['orders']}),4)
            cases=load(batch/'cases.json');self.assertEqual(len(cases),12)
            for order in ('original','shuffle-1','shuffle-2','shuffle-3'):
                paths=[batch/'cases'/c['id']/'reads.fastq.gz' for c in cases if c['read_order']['order_id']==order]
                self.assertEqual(len({p.stat().st_ino for p in paths}),1)
                self.assertEqual(len({digest(p) for p in paths}),1)
            with self.assertRaises(ValueError): stage_inputs(batch,source)

    def test_summary_uses_output_agreement_even_when_every_reference_score_fails(self):
        from pipeline.read_order_report import render
        with tempfile.TemporaryDirectory() as temporary:
            batch=Path(temporary)/'batch';batch.mkdir()
            config={'tools':['flye'],'threads':4,'read_order':{'orders':[{'id':'original'},{'id':'shuffle'}],'repeats_per_order':2}}
            save(batch/'config.json',config)
            admitted={'status':'valid','config_sha256':digest(batch/'config.json'), 'orders':[{'id':o,'reads_sha256':str(i)*64,'shuffle_seed':i,'record_count':10,'record_multiset_sha256':'m'*64,'record_order_sha256':str(i)*64,'permutation_sha256':'p'*64} for i,o in enumerate(('original','shuffle'),1)]}
            save(batch/'input_orders.json',admitted);save(batch/'submission.json',{'jobs':{}})
            tasks=[]
            for index,(order,repeat) in enumerate((o,r) for o in ('original','shuffle') for r in (1,2)):
                case=f'{order}-{repeat}'
                task={'scenario':case,'tool':'flye','order_id':order,'repeat':repeat,'tool_index':index};tasks.append(task)
                directory=batch/'results'/case/'flye'
                record={'status':'fail','tool':'flye','scenario_fingerprint':case,'config_fingerprint':fingerprint(config),'threads':4,'version':'fixed','reads_sha256':next(o['reads_sha256'] for o in admitted['orders'] if o['id']==order),'evaluation':{'status':'fail'},'command':['flye','--example']}
                save(directory/'execution.json',record)
                save(batch/'cases'/case/'input.json',{'case':{'fingerprint':case}})
                signature={'end_sensitive_sha256':'same','circular_representation_sha256':None,'contig_count':1,'total_length_bp':4,'scope':'Final assembly contigs'}
                save(directory/'read_order_signature.json',{'status':'complete','execution_sha256':digest(directory/'execution.json'),'signature':signature})
            save(batch/'tasks.json',{'assemble':tasks})
            result=summarise(batch)
            self.assertTrue(result['complete'])
            self.assertEqual(result['status_counts'],{'fail':4})
            self.assertEqual(result['tools'][0]['end_sensitive']['verdict'],'No order effect observed')
            render(result,batch/'report')
            self.assertIn('No order effect observed',(batch/'report/index.html').read_text())
            self.assertIn('Completed',(batch/'report/index.html').read_text())
            self.assertIn('completed',(batch/'report/runs.tsv').read_text())
            self.assertTrue((batch/'report/runs.tsv').is_file())
            render(result,batch/'public-report',public=True)
            self.assertFalse((batch/'public-report/summary.json').exists())
            self.assertNotIn('href="summary.json"',(batch/'public-report/index.html').read_text())
            render(result,batch/'report',public=True)
            self.assertFalse((batch/'report/summary.json').exists())

    def test_retained_chromosome_label_requires_exact_initial_sequence_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);initial=directory/'output/flye_output';initial.mkdir(parents=True)
            (initial/'assembly.fasta').write_text('>contig_1\nACGTTT\n')
            (initial/'assembly_info.txt').write_text('#seq_name\tlength\tcov.\tcirc.\trepeat\tmult.\talt_group\tgraph_path\ncontig_1\t6\t30\tY\tN\t1\t*\t1\n')
            claims,evidence=inherited_chromosome_topology(directory,{'renamed':'AAACGT'})
            self.assertEqual(claims,{'retained_chromosome:renamed':True})
            self.assertEqual(evidence[0]['initial_contigs'],['contig_1'])
            self.assertEqual(inherited_chromosome_topology(directory,{'renamed':'ACGTTA'}),({},[]))

    def test_submit_returns_completed_checkpoint_without_external_actions(self):
        from unittest.mock import patch
        from scripts import read_order as controller
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'status.json'
            state={**controller.plan(),'status':'results_complete','batch_id':'fixture','jobs':{'report':'123'}}
            save(path,state)
            with patch.object(controller,'STATE',path), patch.object(controller,'ssh',side_effect=AssertionError('Duplicate external submission')), patch.object(controller.subprocess,'run',side_effect=AssertionError('Unexpected transfer')):
                self.assertEqual(controller.submit(),state)
