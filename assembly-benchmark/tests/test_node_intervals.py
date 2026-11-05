"""Synthetic metadata-only interval cases; no sequences or alignment software."""
import copy
import unittest
from pipeline.node_intervals import build_node_intervals
from pipeline.reference_origins import build_reference_origins


def fixture():
    hashes = dict(assembly_sha256='a'*64, truth_sha256='b'*64, gfa_sha256='c'*64)
    nodes = [{'id': name, 'length_bp': 1000} for name in ('single', 'mixed', 'shared', 'unknown')]
    refs = [{'id': 'fixture-A', 'name': 'Reference A', 'length_bp': 10000, 'colour': '#72a9e8', 'light_colour': '#326eae'},
            {'id': 'fixture-B', 'name': 'Reference B', 'length_bp': 5000, 'colour': '#d8974e', 'light_colour': '#9c5a15'}]
    def row(name, node, start, end, ref, status='supported'):
        return {'id':name, 'node_id':node, 'node_interval':[start,end], 'reference_id':ref,
                'reference_interval':[100+start,100+end], 'strand':'+', 'assignment_status':status,
                'match_quality':{'identity_fraction':1.0, 'mapping_quality':60}}
    evidence = {'schema_version':1, 'evidence_type':'graph_node_to_reference', 'coordinate_system':'0-based half-open',
                'input_hashes':dict(hashes), 'source':{'name':'Synthetic fixture; not a benchmark execution', 'sha256':'d'*64},
                'alignments':[row('single-a','single',0,1000,'fixture-A'), row('mixed-a','mixed',0,400,'fixture-A'),
                              row('mixed-b','mixed',400,750,'fixture-B'), row('shared-a','mixed',750,900,'fixture-A'),
                              row('shared-b','mixed',750,900,'fixture-B'), row('ambiguous-a','shared',0,1000,'fixture-A','ambiguous')]}
    return evidence,nodes,refs,hashes


class NodeIntervalTests(unittest.TestCase):
    def test_mixed_shared_and_missing_spans_preserve_records(self):
        args=fixture();before=copy.deepcopy(args);out=build_node_intervals(*args)
        self.assertEqual(out['single']['intervals'][0]['reference_id'],'fixture-A')
        self.assertEqual([r['status'] for r in out['mixed']['intervals']],['supported','supported','ambiguous','unresolved'])
        self.assertEqual([r['node_interval'] for r in out['mixed']['intervals']],[[0,400],[400,750],[750,900],[900,1000]])
        self.assertEqual(out['mixed']['intervals'][2]['candidate_reference_ids'],['fixture-A','fixture-B'])
        self.assertEqual(out['shared']['intervals'][0]['status'],'ambiguous')
        self.assertNotIn('unknown',out)
        self.assertEqual(args,before)
        self.assertEqual(out['mixed']['alignments'][0]['reference_interval'],[100,500])

    def test_overlapping_rows_retain_original_spans_instead_of_projecting(self):
        evidence,nodes,refs,hashes=fixture();evidence['alignments']=evidence['alignments'][1:3]
        evidence['alignments'][0]['node_interval']=[0,600]
        out=build_node_intervals(evidence,nodes,refs,hashes)['mixed']
        self.assertEqual([r['node_interval'] for r in out['intervals']],[[0,400],[400,600],[600,750],[750,1000]])
        self.assertEqual(out['intervals'][1]['status'],'ambiguous')
        self.assertEqual(out['alignments'][0]['node_interval'],[0,600])

    def test_invalid_or_stale_evidence_is_rejected(self):
        for mutate in [lambda e:e['input_hashes'].update(truth_sha256='e'*64),
                       lambda e:e.update(coordinate_system='1-based'),
                       lambda e:e['alignments'][0].update(node_interval=[-1,100]),
                       lambda e:e['alignments'][0].update(reference_interval=[0,20000]),
                       lambda e:e['alignments'][0].update(strand='?'),
                       lambda e:e['alignments'][0].update(node_id='missing'),
                       lambda e:e['alignments'][0].update(match_quality={}),
                       lambda e:e['alignments'][0].update(match_quality={'identity_fraction':1.5}),
                       lambda e:e['alignments'][0].update(match_quality={'score':float('nan')}),
                       lambda e:e['alignments'][0].pop('assignment_status'),
                       lambda e:e['alignments'].append(copy.deepcopy(e['alignments'][0]))]:
            evidence,nodes,refs,hashes=fixture();mutate(evidence)
            with self.assertRaises(ValueError):build_node_intervals(evidence,nodes,refs,hashes)

    def test_backend_origin_integration_does_not_require_whole_node_identity(self):
        evidence,nodes,refs,hashes=fixture()
        case={'replicons':[{'refseq_accession':r['id'],'replicon_name':r['name'],'length_bp':r['length_bp'],'molecule_type':'plasmid'} for r in refs]}
        record={'tool':'flye',**hashes}
        artifact={'input_hashes':{'assembly_sha256':hashes['assembly_sha256']},'graph':{'status':'available','complete':True,'nodes':nodes,'source':{'role':'final','file_sha256':hashes['gfa_sha256']}},'reference_interval_evidence':evidence}
        out=build_reference_origins(case,record,artifact)
        self.assertFalse(out['nodes'])
        self.assertEqual(out['internal_boundaries_status'],'recorded_alignment_spans')
        self.assertIn('mixed',out['node_intervals'])
        artifact.pop('reference_interval_evidence')
        self.assertEqual(build_reference_origins(case,record,artifact)['node_intervals'],{})
