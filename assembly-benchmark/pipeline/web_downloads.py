"""Publish presentation assets only; backend evidence stays in its source bundle."""
import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit


def package_downloads(output):
    """Remove bulk evidence copies and their links from the generated website.

    Scores, visible tables, plots and inline graph models are untouched. The
    complete validated backend bundle and its separate ZIP remain outside output.
    """
    root = Path(output).resolve()
    audit_path = root / 'site-manifest.json'
    (root / 'download-sizes.json').unlink(missing_ok=True)
    before = sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and p != audit_path)
    removed = set()
    removed_bytes = 0
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        in_data = parts[0] == 'data' or (len(parts) >= 4 and parts[0] == 'batches' and parts[2] == 'data')
        if not in_data or (path.name == 'overview.json'):
            continue
        if path.suffix not in {'.json', '.gz', '.zip', '.md'}:
            continue
        removed.add('/' + path.relative_to(root).as_posix())
        removed_bytes += path.stat().st_size
        path.unlink()

    for path in sorted(root.rglob('*.html')):
        content = path.read_text()
        base = 'https://bundle.invalid/' + path.relative_to(root).as_posix()
        base_tag = re.search(r'<base\b[^>]*\bhref=["\']([^"\']+)["\']', content)
        if base_tag:
            base = urljoin(base, html.unescape(base_tag[1]))

        def anchor(match):
            resolved = urlsplit(urljoin(base, html.unescape(match[2])))
            if resolved.netloc == 'bundle.invalid' and unquote(resolved.path) in removed:
                return ''
            return match[0]

        # Do not edit inert JSON: it is the graph's runtime model.
        segments = re.split(r'(<script\b[^>]*>.*?</script>)', content, flags=re.DOTALL | re.IGNORECASE)
        for index in range(0, len(segments), 2):
            value = re.sub(r'<a\b[^>]*\bhref=(["\'])([^"\']+)\1[^>]*>.*?</a>', anchor, segments[index], flags=re.DOTALL)
            value = re.sub(r'<p>\s*(?:[·|]\s*)*</p>', '', value)
            value = re.sub(r'(<p>)\s*[·|]\s*', r'\1', value)
            value = re.sub(r'\s*[·|]\s*(</p>)', r'\1', value)
            segments[index] = value
        path.write_text(''.join(segments))

    # Runtime assets are identical across batch reports. Serve a single copy.
    for folder in sorted((root / 'batches').glob('*/assets')):
        for path in folder.rglob('*'):
            if path.is_file():
                shared = root / 'assets' / path.relative_to(folder)
                if not shared.is_file() or path.read_bytes() != shared.read_bytes():
                    raise ValueError(f'Batch asset differs from root asset: {path}')
        batch = folder.parent.name
        for page in folder.parent.rglob('*.html'):
            value = page.read_text()
            value = re.sub(r'((?:href|src)=")(?:(?:\.\./)*|/batches/' + re.escape(batch) + r'/)assets/', r'\1/assets/', value)
            page.write_text(value)
        import shutil
        shutil.rmtree(folder)

    # Full backend JSON is deliberately unavailable on the presentation host.
    # Do not leave compression redirects targeting files excluded above.
    config_path = root / 'vercel.json'
    config = json.loads(config_path.read_text())
    for key in ('redirects', 'headers'):
        if key in config:
            config[key] = [rule for rule in config[key] if ':scope(' not in rule.get('source', '')]
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    overview = json.loads((root / 'data/overview.json').read_text()) if (root / 'data/overview.json').is_file() else {}
    after = sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and p != audit_path)
    manifest = {'schema_version': 2, 'policy': 'presentation-only',
                'batch': overview.get('included_batches', [None])[0],
                'website_bytes_before': before, 'website_bytes_after': after,
                'removed_download_count': len(removed), 'removed_download_bytes': removed_bytes,
                'backend_evidence': 'Retained in the separate validated backend bundle; not deployed to Vercel.'}
    audit_path.write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
