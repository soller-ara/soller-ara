import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const script = await fs.readFile('admin/web-discovery.js', 'utf8');
const html = await fs.readFile('admin/index.html', 'utf8');
const fields = {
  webDiscoveryTopic: { value: '' },
  webDiscoveryArea: { value: 'all' },
  webDiscoveryDays: { value: '30' },
  webDiscoveryEngine: { value: 'brave' },
  webDiscoveryQuery: { value: '' },
  webDiscoveryTimeFilter: { value: '', disabled: true },
  webDiscoverySubmit: { disabled: true },
};
let handleSubmit;
const form = { addEventListener(name, callback) {
  assert.equal(name, 'submit');
  handleSubmit = callback;
}};
fields.webDiscoveryForm = form;

let now = '2026-11-14T23:15:00Z'; // Ya es día 15 en Mallorca.
class TestDate extends Date {
  constructor(...args) { super(...(args.length ? args : [now])); }
}

vm.runInNewContext(script, { document: { getElementById: id => fields[id] }, Date: TestDate, Intl });
assert.equal(fields.webDiscoverySubmit.disabled, false);

function query({ topic = '', area = 'all', days = '30', engine = 'brave' } = {}) {
  fields.webDiscoveryTopic.value = topic;
  fields.webDiscoveryArea.value = area;
  fields.webDiscoveryDays.value = days;
  fields.webDiscoveryEngine.value = engine;
  let stopped = false;
  handleSubmit({ preventDefault() { stopped = true; } });
  if (stopped) return null;
  const url = new URL(form.action);
  url.searchParams.set('q', fields.webDiscoveryQuery.value);
  if (!fields.webDiscoveryTimeFilter.disabled) url.searchParams.set('tf', fields.webDiscoveryTimeFilter.value);
  return url;
}

const local = query();
assert.equal(local.origin, 'https://search.brave.com');
assert.equal(local.pathname, '/search');
assert.equal(local.searchParams.get('tf'), '2026-10-16to2026-11-15');
assert.match(local.searchParams.get('q'), /"Sóller".*"sollerics".*"Fornalutx".*"Biniaraix".*"Deià"/);
assert.doesNotMatch(local.searchParams.get('q'), /Esporles|Bunyola|Casal Solleric|"solleric"/i);

const port = query({ area: 'port', topic: 'horaris tren', days: '7' });
assert.match(port.searchParams.get('q'), /^horaris tren AND .*"Port de Sóller".*"Puerto de Sóller"/);
assert.equal(port.searchParams.get('tf'), '2026-11-08to2026-11-15');

const deia = query({ area: 'deia', topic: 'festes d’estiu', days: '60', engine: 'google' });
assert.equal(deia.origin, 'https://www.google.com');
assert.equal(deia.searchParams.has('tf'), false, 'Switching engines must not pass a stale Brave filter');
assert.equal(deia.searchParams.get('q'), 'festes d’estiu ("Deià" OR "Deia") after:2026-09-16 before:2026-11-16');

const serra = query({ area: 'serra', topic: 'obres', days: '7' }).searchParams.get('q');
assert.match(serra, /"Serra de Tramuntana".* AND .*"Sóller".*"Fornalutx"/);
assert.equal(query({ days: '61' }), null);
assert.equal(query({ area: 'bunyola' }), null);
assert.equal(query({ engine: 'https://unrelated.test' }), null);

now = '2026-03-29T22:20:00Z'; // Ya es día 30 tras el cambio de hora.
assert.equal(query({ area: 'fornalutx', days: '7' }).searchParams.get('tf'), '2026-03-23to2026-03-30');

const formTag = html.match(/<form id="webDiscoveryForm"[^>]*>/s)?.[0];
assert.match(formTag, /method="get"/);
assert.match(formTag, /target="_blank"/);
assert.match(formTag, /rel="noopener noreferrer"/);
assert.match(html, /<button[^>]*data-view="web-search"/);
assert.match(html, /<section id="web-search"/);
console.log('PASS: searches keep verified locality terms, Madrid dates, both engine URLs and native new-tab submission.');

