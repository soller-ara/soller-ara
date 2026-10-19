import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = (await fs.readFile('worker/admin-worker.js', 'utf8')).replace('export default {', 'const worker = {');
const now = Date.parse('2026-10-19T12:00:00Z');
const old = '2026-10-19T09:00:00Z';
const completed = { id: 1, status: 'completed', created_at: old, run_started_at: old, conclusion: 'success' };

function scenario(options = {}) {
  let clock = now;
  class Clock extends Date { static now() { return clock; } }
  const calls = [], logs = [];
  const context = vm.createContext({ Date: Clock, URL, Request, Response, AbortSignal,
    console: { log: value => logs.push(value), error: value => logs.push(value) } });
  const env = { GITHUB_TOKEN: 'test-only-watchdog-token', ...options.env };
  context.env = env;
  context.fetch = async (url, init = {}) => {
    calls.push({ url, init });
    assert.ok(!url.includes(env.GITHUB_TOKEN));
    assert.ok(init.signal, 'watchdog requests must have a timeout');
    if (url.startsWith('https://raw.githubusercontent.com/')) {
      assert.equal(init.headers.Authorization, undefined);
      assert.ok(url.includes('/main/data/posts.json?'));
      return new Response(JSON.stringify({ sources_checked_at: old, fetched_at: new Date(now).toISOString(),
        ...options.data }), { status: options.dataStatus || 200 });
    }
    assert.ok(url.startsWith('https://api.github.com/repos/soller-ara/soller-ara/'));
    assert.equal(init.headers.Authorization, 'Bearer test-only-watchdog-token');
    if (init.method === 'POST') {
      assert.ok(url.endsWith('/actions/workflows/update-sources.yml/dispatches'));
      assert.deepEqual(JSON.parse(init.body), { ref: 'main', inputs: { watchdog: true } });
      return new Response(options.dispatchStatus ? 'Provider error' : null, { status: options.dispatchStatus || 204 });
    }
    assert.ok(url.endsWith('/runs?branch=main&per_page=100'));
    return new Response(JSON.stringify(options.badRuns || { workflow_runs: options.runs || [completed] }),
      { status: options.runsStatus || 200 });
  };
  vm.runInContext(source, context);
  return { calls, logs, context, env,
    tick: () => vm.runInContext('worker.scheduled({}, env)', context),
    advance: milliseconds => { clock += milliseconds; },
    posts: () => calls.filter(call => call.init.method === 'POST') };
}

for (const timestamp of ['2026-10-19T11:59:00Z', '2026-10-19T10:00:00Z', '2026-10-19T14:00:00+02:00']) {
  const test = scenario({ data: { sources_checked_at: timestamp } });
  assert.equal((await test.tick()).action, 'fresh');
  assert.equal(test.calls.length, 1);
}
for (const timestamp of [null, '', 'bad', '2026-10-19T12:06:00Z', '2026-10-19T08:00:00']) {
  const test = scenario({ data: { sources_checked_at: timestamp } });
  assert.equal((await test.tick()).action, 'invalid_timestamp');
  assert.equal(test.posts().length, 0);
}
for (const [env, action] of [[{ GITHUB_TOKEN: '' }, 'not_configured'], [{ COLLECTION_WATCHDOG_ENABLED: 'false' }, 'disabled']]) {
  const test = scenario({ env });
  assert.equal((await test.tick()).action, action);
  assert.equal(test.calls.length, 0);
}
for (const status of ['queued', 'in_progress', 'pending', 'requested', 'waiting']) {
  const test = scenario({ runs: [{ ...completed, status }] });
  assert.equal((await test.tick()).action, 'already_running');
  assert.equal(test.posts().length, 0);
}
for (const run of [
  { ...completed, conclusion: 'failure', created_at: '2026-10-19T11:30:00Z' },
  { ...completed, run_started_at: '2026-10-19T11:30:00Z' },
]) {
  const test = scenario({ runs: [run] });
  assert.equal((await test.tick()).action, 'recent_attempt');
  assert.equal(test.posts().length, 0);
}
{
  const test = scenario();
  assert.equal((await test.tick()).action, 'dispatched');
  assert.equal(test.posts().length, 1);
  assert.equal((await test.tick()).action, 'recent_attempt');
  test.advance(59 * 60 * 1000);
  assert.equal((await test.tick()).action, 'recent_attempt');
  assert.equal(test.posts().length, 1);
  assert.ok(!test.logs.join('').includes('test-only-watchdog-token'));
}
{
  const test = scenario();
  await Promise.all([test.tick(), test.tick(), test.tick()]);
  assert.equal(test.posts().length, 1, 'overlapping ticks on an instance share their work');
}
for (const options of [
  { dataStatus: 503 }, { runsStatus: 403 }, { badRuns: { workflow_runs: null } },
  { runs: [{ status: 'completed' }] },
  { runs: [{ ...completed, created_at: 'invalid' }] },
  { runs: [{ ...completed, run_started_at: '2026-10-19T12:10:00Z' }] },
]) {
  const test = scenario(options);
  await assert.rejects(test.tick(), /Collection watchdog failed/);
  assert.equal(test.posts().length, 0);
  assert.ok(!test.logs.join('').includes('test-only-watchdog-token'));
}
{
  const test = scenario({ dispatchStatus: 503 });
  await assert.rejects(test.tick(), /Collection watchdog failed/);
  assert.equal(test.posts().length, 1);
  assert.equal((await test.tick()).action, 'recent_attempt', 'uncertain POST is not repeated immediately');
  assert.equal(test.posts().length, 1);
}
const config = await fs.readFile('worker/wrangler.toml', 'utf8');
assert.ok(config.includes('crons = ["*/15 * * * *"]'));
console.log('PASS: watchdog freshness ignores manual timestamps, preserves the hourly workflow, skips active/recent runs, limits retries, merges concurrent ticks, validates provider responses and never contacts Meta.');
