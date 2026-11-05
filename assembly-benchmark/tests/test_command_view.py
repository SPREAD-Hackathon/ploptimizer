import copy
import html
import shlex
import unittest

from pipeline.command_view import render_command


class CommandViewTests(unittest.TestCase):
    def test_recorded_arguments_and_thread_values_are_preserved(self):
        row = {"status": "pass", "tool": "flye-meta", "version": "2.9.6-b1802", "command": ["flye", "--nano-hq", "<workdir>/reads with spaces.fastq.gz", "--threads", "1", "--meta"]}
        original = copy.deepcopy(row)
        body = render_command(row)
        self.assertIn(html.escape(shlex.join(row["command"]), quote=True), body)
        self.assertIn('uneven-coverage mode', body)
        self.assertEqual(row, original)

    def test_mode_name_does_not_invent_a_flag(self):
        body = render_command({"tool": "flye-meta", "status": "pass", "command": ["flye", "--threads", "4"]})
        self.assertNotIn('<code>--meta</code>', body)

    def test_missing_command_and_unknown_flags_are_explicit(self):
        self.assertIn('No command was recorded', render_command({"command": None}))
        body = render_command({"tool": "flye", "status": "pass", "command": ["flye", "--unknown=<script>"]})
        self.assertNotIn('<script>', body)
        self.assertIn('No description is included', body)

    def test_workflow_options_keep_their_specific_meanings(self):
        body = render_command({"tool": "plassembler", "status": "pass", "command": ["plassembler", "long", "--skip_mash", "--keep_chromosome", "--chromosome", "1000000"]})
        self.assertIn('Long-read-only workflow', body)
        self.assertIn('Mash comparison', body)
        self.assertIn('during cleanup', body)
        self.assertIn('base pairs', body)


if __name__ == '__main__':
    unittest.main()
