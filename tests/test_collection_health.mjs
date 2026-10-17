import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('admin/collection-health.js', 'utf8');
const now = Date.parse('2026-10-17T10:00:00Z');
class Clock extends Date { static now() { return now; } }
const notice = {textContent: '', dataset: {}};
const admin = {hidden: false};
let timer, onVisibility, reads = 0, payload, readError = false;
const document = {hidden: false, getElementById: id => id === 'adminView' ? admin : notice,
  addEventListener(type, fn) { assert.equal(type, 'visibilitychange'); onVisibility = fn; }};
const window = {SOLLER_ARA_READ_JSON: async path => {
  reads++;
  assert.equal(path, 'data/posts.json');
  if (readError) throw new Error('temporarily unavailable');
  return payload;
}};
vm.runInContext(source, vm.createContext({window, document, Date: Clock, Intl,
  setInterval(fn, ms) { assert.equal(ms, 60000); timer = fn; }}));
const render = window.SOLLER_ARA_RENDER_COLLECTION_HEALTH;
const recent = {sources_checked_at: '2026-10-17T09:45:00Z', source_status: []};
render(recent);
assert.equal(notice.dataset.state, 'recent');
assert.match(notice.textContent, /11:45/); // Mallorca, not the machine timezone.
render({sources_checked_at: '2026-10-17T07:59:59Z', fetched_at: '2026-10-17T10:00:00Z'});
assert.equal(notice.dataset.state, 'warning');
assert.match(notice.textContent, /más de 2 horas/);
render({sources_checked_at: '2026-10-17T08:00:00Z'});
assert.equal(notice.dataset.state, 'recent');
for (const value of [undefined, null, '', 'bad-date', '2026-10-17T10:06:00Z']) {
  render({sources_checked_at: value, fetched_at: '2026-10-17T10:00:00Z'});
  assert.equal(notice.dataset.state, 'warning');
  assert.match(notice.textContent, /fecha válida/);
}
render({...recent, source_status: [{ok: false}, {ok: true}]});
assert.equal(notice.dataset.state, 'warning');
assert.match(notice.textContent, /1 fuentes con incidencias/);
render({...recent, source_status: null});
assert.equal(notice.dataset.state, 'recent');
render({sources_checked_at: '2026-10-17T07:00:00Z'});
payload = recent;
await timer();
assert.equal(reads, 1);
assert.equal(notice.dataset.state, 'recent', 'Background refresh must clear an old delay once collection recovers');
readError = true;
await timer();
assert.equal(notice.dataset.state, 'warning');
assert.match(notice.textContent, /No se ha podido comprobar/);
assert.match(notice.textContent, /11:45/, 'A failed read must keep the last verified check time');
document.hidden = true;
const before = reads;
await timer();
assert.equal(reads, before);
document.hidden = false;
readError = false;
await onVisibility();
assert.equal(notice.dataset.state, 'recent');
admin.hidden = true;
await timer();
assert.equal(reads, before + 1, 'No repository polling while logged out');
const html = await fs.readFile('admin/index.html', 'utf8');
assert.ok(html.includes('id="collectionFreshness"'));
assert.ok(html.indexOf('./collection-health.js?') < html.indexOf('./admin.js?'));
console.log('PASS: collection timestamps, delay threshold, manual-post isolation, Madrid time, invalid/future dates, source failures, refresh recovery and failed/hidden-session reads.');
