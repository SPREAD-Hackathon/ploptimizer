import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { dirname, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../dist');
const types = {'.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json'};
const server = createServer(async (request, response) => {
  try {
    const path = resolve(root, '.' + new URL(request.url, 'http://localhost').pathname);
    if (!path.startsWith(root + '/') && path !== root) throw Error('Invalid path');
    const file = (await stat(path)).isDirectory() ? resolve(path, 'index.html') : path;
    response.setHeader('content-type', types[extname(file)] ?? 'application/octet-stream');
    response.end(await readFile(file));
  } catch { response.writeHead(404); response.end('Not found'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
try {
  const data = await (await fetch(base + '/data/results.json')).json();
  assert.equal(data.results.length, data.scenarios.length * data.config.tools.length);
  const routes = ['/', '/methods.html', '/about.html', '/history.html', '/scenarios/index.html', ...data.scenarios.map(s => `/scenarios/${s.id}.html`)];
  for (const route of routes) {
    const response = await fetch(base + route);
    assert.equal(response.status, 200, route);
    const text = await response.text();
    assert.ok(text.includes('genomicx-nav'), route);
    assert.ok(text.includes('assets/genomicx.js'), route);
    for (const match of text.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const url = new URL(match[1], base + route);
      if (url.origin === base) assert.equal((await fetch(url)).status, 200, `${route}: ${url.pathname}`);
    }
  }
  const assetInfo = await (await fetch(base + '/assets/build.json')).json();
  assert.equal(assetInfo.packages['@genomicx/ui'], '0.10.1');
  const bundle = await (await fetch(base + '/assets/genomicx.js')).text();
  assert.ok(bundle.includes('gx-theme-toggle'));
  assert.ok(bundle.includes('gx-nav-logo'));
  assert.ok(bundle.includes('gx-badge'));
  console.log(`HTTP end-to-end checks passed: ${routes.length} routes, ${data.results.length} comparisons, native GenomicX assets.`);
} finally { await new Promise(resolve => server.close(resolve)); }
