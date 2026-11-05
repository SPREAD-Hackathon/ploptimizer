"""Display saved invocations and describe only arguments actually recorded."""

import html
import shlex

SOURCES = {
    "flye": ("Flye 2.9.6 manual", "https://github.com/mikolmogorov/Flye/blob/2.9.6/docs/USAGE.md"),
    "flye-meta": ("Flye 2.9.6 manual", "https://github.com/mikolmogorov/Flye/blob/2.9.6/docs/USAGE.md"),
    "raven": ("Raven command-line documentation", "https://github.com/lbcb-sci/raven#usage"),
    "plassembler": ("Plassembler 1.9.0 command definitions", "https://github.com/gbouras13/plassembler/blob/v1.9.0/src/plassembler/__init__.py"),
}
FLAGS = {
    "flye": {
        "--nano-hq": "Supply reads using Flye’s high-quality Nanopore input mode.",
        "--out-dir": "Directory for assembly output.",
        "--threads": "Number of parallel threads requested.",
        "--meta": "Enable the metagenome / uneven-coverage mode.",
    },
    "raven": {"-t": "Number of threads requested."},
    "plassembler": {
        "--longreads": "Input long-read FASTQ file.",
        "--outdir": "Directory for output files.",
        "--threads": "Number of threads requested.",
        "--skip_qc": "Skip the workflow’s read-QC filtering step.",
        "--skip_mash": "Skip the Mash comparison against PLSDB.",
        "--keep_chromosome": "Retain the chromosome assembly file during cleanup.",
        "--prefix": "Prefix for output filenames.",
        "--chromosome": "Lower-bound chromosome-length threshold, in base pairs.",
    },
}


def render_command(record, case=None):
    from .report import execution_evidence
    e = lambda value: html.escape(str(value), quote=True)
    command = record.get("command", [])
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
        return '<details class="command-used"><summary>Command used and flags</summary><p id="command-used">No command was recorded for this execution.</p></details>'
    command = execution_evidence(record, case)["command"]
    tool = record.get("tool")
    definitions = FLAGS.get("flye" if tool == "flye-meta" else tool, {})
    body = '<details class="command-used"><summary>Command used and flags</summary><div id="command-used">'
    body += f'<p class="muted">Recorded tool version: {e(record.get("version") or "not recorded")}</p><pre class="recorded-command"><code>{e(shlex.join(command))}</code></pre>'
    if any("<workdir>" in arg for arg in command):
        body += '<p class="muted"><code>&lt;workdir&gt;</code> marks the benchmark work directory.</p>'
    body += '<dl class="command-options">'
    if tool == "plassembler" and len(command) > 1 and command[1] == "long":
        body += '<dt><code>long</code></dt><dd>Long-read-only workflow.</dd>'
    for flag in dict.fromkeys(arg.split("=", 1)[0] for arg in command[1:] if arg.startswith("-")):
        body += f'<dt><code>{e(flag)}</code></dt><dd>{e(definitions.get(flag, "No description is included here; consult the tool documentation."))}</dd>'
    if tool == "raven":
        body += '<dt>Input file</dt><dd>The positional argument supplies the read file.</dd>'
    body += '</dl>'
    if tool in SOURCES:
        title, url = SOURCES[tool]
        body += f'<p class="muted">Flag descriptions: <a href="{e(url)}">{e(title)}</a>.</p>'
    return body + '</div></details>'
