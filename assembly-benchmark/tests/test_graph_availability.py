import unittest
from pathlib import Path
from pipeline.graph_availability import graph_availability, graph_requested
from pipeline.execution import command


class GraphAvailabilityTests(unittest.TestCase):
    def test_missing_raven_graph_without_request_is_not_a_validation_failure(self):
        row={'tool':'raven','status':'fail','command':['raven','-t','4','reads.fastq.gz']}
        self.assertEqual(graph_availability(row,{'graph':{'status':'missing'}})['status'],'not_requested')
        self.assertEqual(graph_availability(row,{'graph':{'status':'available'}})['status'],'available')
        self.assertEqual(graph_availability(row,{'graph':{'status':'invalid'}})['status'],'invalid')

    def test_requested_graph_that_is_missing_stays_a_collection_gap(self):
        for flags in (['-F','graph.gfa'],['--graphical-fragment-assembly=graph.gfa'],['-Ugraph.gfa']):
            argv=['raven',*flags,'reads.fastq.gz'];self.assertTrue(graph_requested(argv))
            self.assertEqual(graph_availability({'tool':'raven','command':argv},{'graph':{'status':'missing'}})['status'],'not_collected')
        self.assertEqual(graph_availability({'status':'not_run'},{})['status'],'not_run')

    def test_future_raven_commands_request_graph_in_isolated_execution_directory(self):
        argv=command('raven',Path('/fixture/reads.fastq.gz'),Path('/fixture/run/output'),{'threads':4})
        self.assertEqual(argv[:3],['raven','-t','4'])
        self.assertEqual(argv[argv.index('-F')+1],'/fixture/run/assembly_graph.gfa')
        self.assertEqual(argv[-1],'/fixture/reads.fastq.gz')
