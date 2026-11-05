import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat, readdir } from 'node:fs/promises';
import { dirname, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../dist');
const cohortConfig = JSON.parse(await readFile(resolve(root, '../config/overview.json'), 'utf8'));
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
const statusCache = new Map();
const checkedPages = new Set();
const compact = value => value.replace(/\s+/g, ' ').trim();
const escaped = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#x27;');
const slug = row => [row.scenario_id, row.tool, row.run_id].filter(Boolean).join('--');
const titleCase = value => value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase());

async function httpStatus(url) {
  if (!statusCache.has(url)) statusCache.set(url, (async () => {
    const response = await fetch(url);
    await response.body?.cancel();
    return response.status;
  })());
  return statusCache.get(url);
}

async function textAt(route) {
  const response = await fetch(base + route);
  assert.equal(response.status, 200, route);
  statusCache.set(base + route, Promise.resolve(response.status));
  return response.text();
}

async function jsonAt(route) { return JSON.parse(await textAt(route)); }

async function checkPage(route) {
  const html = await textAt(route);
  if (!checkedPages.has(route)) {
    checkedPages.add(route);
    assert.ok(html.includes('genomicx-nav'), route);
    assert.ok(html.includes('assets/genomicx.js'), route);
    for (const match of html.matchAll(/(?:href|src)="([^"]+)"/g)) {
      const url = new URL(match[1], base + route);
      if (url.origin === base) {
        assert.ok(!/\.(?:gfa|fasta|fastq|cereal)(?:\.gz)?$/i.test(url.pathname), `${route}: raw sequence artefact must not be published`);
        assert.equal(await httpStatus(url.href), 200, `${route}: ${url.pathname}`);
      }
    }
  }
  return html;
}

function noSequenceFields(value) {
  if (Array.isArray(value)) value.forEach(noSequenceFields);
  else if (value && typeof value === 'object') for (const [key, item] of Object.entries(value)) {
    assert.ok(!['sequence', 'sequences', 'segment_sequence', 'raw_sequence'].includes(key), `Unexpected sequence payload: ${key}`);
    noSequenceFields(item);
  }
}

async function checkOverview(prefix) {
  const overview = await jsonAt(prefix + '/data/overview.json');
  const home = await checkPage(prefix + '/');
  assert.equal(overview.endpoint, 'recorded_exact_status');
  assert.ok(home.includes('overview-heatmap'));
  assert.ok(!home.includes('data-assembly-graph'), 'Graphs belong on individual result pages');
  assert.ok(!home.includes('assembler-result'), 'Per-run diagnoses must stay off the headline');
  assert.ok(!home.includes('class="matrix"'), 'The headline must aggregate families, not individual cases');
  assert.ok(![...home.matchAll(/href="([^"]+)"/g)].some(match => /(?:^|\/)results\//.test(match[1])), 'Headline links should open a family');
  const cells = [...home.matchAll(/<td\b[^>]*class="([^"]*\boverview-cell\b[^"]*)"[^>]*>[\s\S]*?<\/td>/g)];
  const displayedFamilies = overview.scope === 'archived_batch' ? overview.families.filter(family => family.counts.total > 0) : overview.families;
  assert.equal(cells.length, displayedFamilies.length * overview.tools.length);
  let index = 0;
  const identities = new Set();
  for (const family of overview.families) {
    for (const tool of (displayedFamilies.includes(family) ? family.tools : [])) {
      const cell = cells[index++];
      const repeat = tool.repeatability;
      const numerator = repeat ? repeat.identical : tool.pass;
      const denominator = repeat ? repeat.identical + repeat.different : tool.denominator;
      const fields = repeat ? {identical: repeat.identical, different: repeat.different, denominator} : {pass: tool.pass, fail: tool.fail, denominator};
      for (const [key, value] of Object.entries(fields)) assert.ok(cell[0].includes(`data-${key}="${value}"`), `${prefix}/${family.id}/${tool.id}: ${key}`);
      if (repeat) {
        assert.ok(cell[0].includes(`${repeat.identical} identical · ${repeat.different} different`));
        if (repeat.not_assessed) assert.ok(compact(cell[0]).includes(`${repeat.not_assessed} not assessed`));
      } else {
        if (tool.errors) assert.ok(compact(cell[0]).includes(`${tool.errors} errors`));
        if (tool.unscored) assert.ok(compact(cell[0]).includes(`${tool.unscored} unscored`));
      }
      assert.equal(cell[1].split(/\s+/).includes('neutral'), denominator === 0, 'Unassessed cells must be neutral');
      if (denominator > 0) {
        const heat = Math.min(4, Math.floor(numerator / denominator * 5));
        assert.ok(cell[1].split(/\s+/).includes(`heat-${heat}`), 'Heat bin must use its assessed endpoint');
      }
    }
    const route = prefix + '/' + family.href;
    const html = await checkPage(route);
    assert.ok(html.includes('Assembler / version'), route);
    assert.ok(html.includes('Exact status'), route);
    assert.ok(!html.includes('data-assembly-graph'), 'Family page lists runs; graphs are third level');
    const tableRows = [...html.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/g)].map(match => match[0]);
    for (const record of family.records) {
      const expected = (overview.scope === 'primary_cohort' && record.batch !== cohortConfig.root_batch ? `batches/${record.batch}/` : '') + `results/${slug(record)}.html`;
      assert.equal(record.href, expected, 'Result link must retain its batch and repeat identity');
      const identity = JSON.stringify([record.batch, record.scenario_id, record.tool, record.run_id]);
      assert.ok(!identities.has(identity), `Duplicate family record: ${identity}`);
      identities.add(identity);
      const matches = tableRows.filter(row => row.includes(`href="../${escaped(record.href)}"`));
      assert.equal(matches.length, 1, `${route}: missing or duplicated run link ${record.href}`);
      assert.ok(compact(matches[0]).includes(compact(escaped(record.version))), `${route}: version absent from its run row`);
      assert.ok(matches[0].includes(titleCase(record.status)), `${route}: status absent from its run row`);
      assert.ok(matches[0].includes(escaped(record.run_id ?? 'Single run')), `${route}: repeat identity missing`);
      if (overview.scope === 'primary_cohort') assert.ok(record.version && record.version !== 'Version not recorded', 'Completed cohort rows require recorded software versions');
      if (family.id === 'S3') {
        assert.match(record.run_id, /^threads-(1|4)-repeat-[1-5]$/);
        assert.equal(record.threads, Number(record.run_id.match(/^threads-(\d+)/)[1]));
      }
      const result = new URL('../' + record.href, base + route);
      assert.equal(await httpStatus(result.href), 200, `${route}: ${result.pathname}`);
    }
    assert.equal(family.records.length, family.counts.total);
  }
  assert.equal(identities.size, overview.counts.total);
  return overview;
}

try {
  const primary = await checkOverview('');
  assert.equal(primary.scope, 'primary_cohort');
  assert.deepEqual(Object.fromEntries(['total', 'pass', 'fail', 'errors', 'unscored', 'denominator'].map(key => [key, primary.counts[key]])),
    {total: 268, pass: 84, fail: 180, errors: 4, unscored: 0, denominator: 264});
  assert.ok(primary.excluded_batches.includes('20261104T183058'));
  assert.ok(!primary.included_batches.includes('20261104T183058'));
  const prefixes = ['', ...(await readdir(resolve(root, 'batches')).catch(() => [])).map(id => `/batches/${id}`)];
  assert.ok(!prefixes.includes('/batches/' + cohortConfig.root_batch), 'The primary report must not be duplicated in its own archive');
  let batchViews = 0;
  let resultViews = 0;
  for (const prefix of prefixes) {
    if (await httpStatus(base + prefix + '/data/results.json') !== 200) continue;
    const data = await jsonAt(prefix + '/data/results.json');
    const repeats = data.config.determinism;
    const factor = repeats ? repeats.repeats * repeats.threads.length : 1;
    assert.equal(data.results.length, data.scenarios.length * data.config.tools.length * factor);
    const frozen = JSON.parse(await readFile(resolve(root, '../published', data.batch + '.json'), 'utf8'));
    assert.deepEqual(data.config, frozen.config, 'Presentation must preserve the frozen configuration');
    const sourceRows = new Map(frozen.results.map(row => [JSON.stringify([row.scenario_id, row.tool, row.run_id]), row]));
    for (const row of data.results) {
      const original = sourceRows.get(JSON.stringify([row.scenario_id, row.tool, row.run_id]));
      assert.ok(original, 'The hierarchy cannot invent scientific executions');
      for (const field of ['status', 'evaluation', 'version', 'threads', 'repeat', 'elapsed_seconds', 'peak_memory_kb', 'assembly_sha256', 'reads_sha256', 'truth_sha256']) {
        assert.deepEqual(row[field], original[field], `${prefix}/${slug(row)}: changed scientific field ${field}`);
      }
    }
    if (prefix) {
      const archived = await checkOverview(prefix);
      assert.equal(archived.scope, 'archived_batch');
      assert.deepEqual(archived.included_batches, [data.batch], 'Archived views cannot pool the primary cohort');
      assert.equal(archived.counts.total, data.results.length);
    }
    for (const route of ['/methods.html', '/about.html', '/history.html', '/scenarios/index.html', '/batch-details.html', ...data.scenarios.map(scenario => `/scenarios/${scenario.id}.html`)]) {
      await checkPage(prefix + route);
    }
    for (const record of data.results) {
      const route = prefix + `/results/${slug(record)}.html`;
      const html = await checkPage(route);
      assert.ok(html.includes('Tool version'), `${route}: tool version fact missing`);
      assert.ok(html.includes('id="assembly-graph"'), `${route}: graph section missing`);
      assert.ok(html.includes('id="assembly-graph-data"'), `${route}: graph data missing`);
      if (record.assembly_sha256) assert.ok(html.includes(record.assembly_sha256), `${route}: assembly provenance missing`);
      const execution = await jsonAt(prefix + `/data/results/${slug(record)}.json`);
      assert.equal(execution.status, record.status, `${route}: download changed status`);
      assert.equal(execution.assembly_sha256, record.assembly_sha256, `${route}: download changed assembly provenance`);
      const artifact = await jsonAt(prefix + `/data/results/${slug(record)}-graph.json`);
      noSequenceFields(artifact);
      if (artifact.input_hashes?.assembly_sha256 && record.assembly_sha256) assert.equal(artifact.input_hashes.assembly_sha256, record.assembly_sha256, `${route}: graph belongs to another assembly`);
      if (artifact.graph?.status === 'available') assert.match(artifact.graph.source.file_sha256, /^[0-9a-f]{64}$/);
      resultViews++;
    }
    batchViews++;
  }
  const assetInfo = await jsonAt('/assets/build.json');
  assert.equal(assetInfo.packages['@genomicx/ui'], '0.10.1');
  const bundle = await textAt('/assets/genomicx.js');
  for (const marker of ['gx-theme-toggle', 'gx-nav-logo', 'gx-badge']) assert.ok(bundle.includes(marker));
  console.log(`HTTP end-to-end checks passed: ${checkedPages.size} routes, ${resultViews} result views across ${batchViews} batch views; primary cohort 268 executions; family/run/graph hierarchy and scientific metrics preserved.`);
} finally { await new Promise(resolve => server.close(resolve)); }
