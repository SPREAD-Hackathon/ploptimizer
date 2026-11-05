"""Evidence-first views of saved assessments; no sequence analysis or rescoring."""

import html
import math


def e(value):
    return html.escape(str(value), quote=True)


def assessed_molecules(record):
    """Select the molecules relevant to the recorded endpoint, not a new policy."""
    molecules = (record.get("evaluation") or {}).get("replicons", [])
    plasmids = [m for m in molecules if m.get("molecule_type") == "plasmid"]
    if plasmids or record.get("tool") == "plassembler":
        return plasmids
    return molecules


def verdict(record):
    status = record["status"]
    if status not in {"pass", "fail"}:
        return "No completed exact assessment", record.get("error") or "This run has no completed sequence verdict."
    if not record.get("evaluation"):
        return f'{status.title()} — recorded exact endpoint', "Per-molecule assessment details are not recorded for this run."
    molecules = assessed_molecules(record)
    failed = [m for m in molecules if m.get("status") != "pass"]
    if status == "pass":
        if not molecules and record.get("tool") == "plassembler":
            return "Pass — chromosome-only negative control", "The saved output meets the no-plasmid endpoint."
        return "Pass — exact recovery", "Every molecule required by this endpoint has a complete, separate exact match."
    names = ", ".join(m.get("name", m.get("accession", "Expected molecule")) for m in failed)
    heading = f"Fail — {names} not recovered exactly" if names else "Fail — the exact endpoint was not met"
    review = record.get("sequence_review") or {}
    if review.get("status") == "verified" and review.get("summary"):
        return heading, review["summary"]
    if failed:
        if all(not m.get("exact_contigs") for m in failed):
            return heading, "No complete, separate copy matches the reference sequence."
        return heading, "Exact matches were recorded, but their copy count or assignment does not meet the saved criterion."
    return heading, "Inspect the saved exact criterion and assessment below for the recorded reason."


def outcome_section(record):
    heading, explanation = verdict(record)
    body = f'<section class="result-outcome" aria-labelledby="outcome-title"><h2 id="outcome-title">{e(heading)}</h2><p>{e(explanation)}</p>'
    if record["status"] not in {"pass", "fail"}:
        return body + '</section>'
    evaluation = record.get("evaluation") or {}
    molecules = evaluation.get("replicons", [])
    relevant = {m.get("accession") for m in assessed_molecules(record)}
    evidence = (record.get("diagnostics") or {}).get("evidence") or {}
    mapped = {m.get("accession"): m for m in evidence.get("replicons", [])}
    displayed = [m for m in molecules if record.get("tool") != "plassembler" or m.get("molecule_type") == "plasmid"]
    for molecule in sorted(displayed, key=lambda m: m.get("accession") not in relevant):
        accession = molecule.get("accession")
        row = mapped.get(accession, {})
        length = molecule.get("length_bp")
        size = f'{length:,} bp' if isinstance(length, int) else 'Length not recorded'
        context = ' · supporting context' if accession not in relevant else ''
        fraction = row.get("recovered_fraction")
        if context:
            label = f'{molecule.get("name", "Molecule")} · supporting context'
            if isinstance(fraction, (float, int)) and math.isfinite(fraction) and 0 <= fraction <= 1:
                label += f' · {100 * fraction:.2f}% aligned'
                if row.get("contig_count") is not None:
                    label += f' across {row["contig_count"]} contig(s)'
            body += f'<details class="molecule-context"><summary>{e(label)}</summary>'
        body += f'<section class="molecule-outcome"><h3>{e(molecule.get("name", accession or "Reference molecule"))}<small>{e(size + context)}</small></h3>'
        exact = molecule.get("exact_contigs", [])
        exact_text = " · ".join(exact) if exact else "No exact copy recorded"
        # Keep a failed duplication/assignment outcome distinct from zero exact copies.
        if exact and molecule.get("status") == "fail":
            exact_text += ". " + molecule.get("reason", "The exact-copy count or assignment fails the saved criterion.")
        exact_label = "Pass" if molecule.get("status") == "pass" else "Fail" if molecule.get("status") == "fail" else "Unscored"
        body += f'<div class="molecule-evidence"><div><span class="evidence-label">Exact molecule</span><strong>{e(exact_label)}</strong><p>{e(exact_text)}</p></div><div><span class="evidence-label">Aligned reference sequence</span>'
        if isinstance(fraction, (float, int)) and math.isfinite(fraction) and 0 <= fraction <= 1:
            percentage = 100 * fraction
            body += f'<strong>{percentage:.2f}%</strong><div class="coverage-track" role="img" aria-label="{percentage:.2f}% retained reference coverage"><span style="width:{percentage:.6f}%"></span></div>'
            count = row.get("contig_count")
            text = "No alignment retained by the saved filters." if fraction == 0 else f'Across {count} contig(s).' if count is not None else 'Retained alignment coverage.'
            body += f'<p>{e(text)}</p>'
        else:
            body += '<strong>Not measured</strong><p>No completed mapping measurement is recorded.</p>'
        body += '</div></div></section>'
        if context:
            body += '</details>'
    if mapped:
        body += '<p class="evidence-note">Bars show total aligned coverage, not genomic positions. An alignment is not an exact-copy test.</p>'
    if record["status"] == "fail":
        review = record.get("sequence_review") or {}
        if review.get("status") != "verified":
            has_zero = any(mapped.get(m.get("accession"), {}).get("recovered_fraction") == 0 for m in assessed_molecules(record) if m.get("status") == "fail")
            body += '<p class="cause-status"><strong>Why did the assembler do this?</strong> Not established by the saved evidence.'
            if has_zero:
                body += ' Zero retained alignment does not establish that the sequence is absent; its location or loss remains unresolved.'
            body += '</p>'
        else:
            body += '<p class="cause-status">The checked mismatch is described above. The assembler’s internal cause remains unresolved.</p>'
    return body + '</section>'
