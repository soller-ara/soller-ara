import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('admin/admin.js', 'utf8');
const prefix = source.slice(0, source.indexOf('  loginForm.addEventListener'));
const html = await fs.readFile('admin/index.html', 'utf8');
const linksSection = html.slice(html.indexOf('<section id="social-links"'), html.indexOf('<section id="moderation"'));
assert.match(linksSection, /id="socialLinkActionMessage"[^>]*aria-live="polite"/);

function node(id = '', dataset = {}, textContent = '') {
  return {
    id, dataset, textContent, disabled: false, listeners: {}, buttons: [],
    addEventListener(type, callback) { this.listeners[type] = callback; },
    querySelector() { return node(); },
    querySelectorAll(selector) {
      const key = selector.slice(6, -1).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      return this.buttons.filter(button => key in button.dataset);
    },
    set innerHTML(value) {
      this.buttons = [...value.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)].map(([, attributes, label]) => {
        const data = Object.fromEntries([...attributes.matchAll(/data-([a-z-]+)="([^"]*)"/g)]
          .map(([, key, value]) => [key.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()), value]));
        return node('', data, label);
      });
    },
  };
}

function scenario({states = [], dispatchError = '', pollError = '', confirm = true} = {}) {
  const nodes = new Map();
  const getNode = id => {
    if (!nodes.has(id)) nodes.set(id, node(id));
    return nodes.get(id);
  };
  let state = {posts: {posts: [{id: 'target', source_type: 'own', original_url: 'https://example.test/post', category: 'agenda'}]}, moderation: {hidden_post_ids: []}};
  let release;
  let postCalls = 0;
  let confirmations = 0;
  let repositoryReads = 0;
  const acknowledgement = new Promise(resolve => { release = resolve; });
  const window = {
    SOLLER_ARA_ADMIN_API: 'https://admin.test',
    SOLLER_ARA_READ_JSON: async path => {
      if (path === 'data/posts.json') {
        repositoryReads++;
        if (pollError) throw new Error(pollError);
        state = states.shift() || state;
      }
      return path === 'data/posts.json' ? state.posts : state.moderation;
    },
  };
  const context = vm.createContext({window, Headers, URL, Intl, Date, console,
    sessionStorage: {getItem: () => 'test-only-token'},
    document: {getElementById: getNode, querySelectorAll: () => [...nodes.values()].flatMap(item => item.buttons)},
    confirm: () => { confirmations++; return confirm; },
    setTimeout: callback => callback(),
    fetch: async (url, options) => {
      if (options.method === 'POST') {
        postCalls++;
        if (dispatchError) throw new Error(dispatchError);
        await acknowledgement;
        return {ok: true, status: 202, json: async () => ({ok: true})};
      }
      throw new Error('Moderation must confirm saved public data, not an API fallback');
    },
  });
  vm.runInContext(prefix + `
    window.test = {moderate, renderPosts, pendingModerations,
      setState(data) {statusPayload = data; renderPosts();}};
  })();`, context);
  window.test.setState(state);
  return {nodes, window, release, counts: () => ({postCalls, confirmations, repositoryReads}),
    click: () => getNode('socialLinkList').buttons.find(button => button.dataset.action === 'delete-own').listeners.click()};
}

const removed = {posts: {posts: []}, moderation: {hidden_post_ids: []}};
let s = scenario({states: [undefined, removed]});
const pending = s.click();
assert.equal(s.nodes.get('socialLinkActionMessage').textContent, 'Enviando solicitud…');
assert.equal(s.nodes.get('moderationMessage').textContent, '');
for (const id of ['socialLinkList', 'postList']) {
  const button = s.nodes.get(id).buttons.find(button => button.dataset.action === 'delete-own');
  assert.equal(button.disabled, true);
  assert.equal(button.textContent, 'Eliminando…');
}
// A refresh creates new DOM buttons; the pending state must survive it.
s.window.test.renderPosts();
assert.ok(s.nodes.get('socialLinkList').buttons.every(button => button.disabled));
await s.window.test.moderate('delete-own', 'target');
assert.equal(s.counts().postCalls, 1);
assert.equal(s.counts().confirmations, 1);
s.release();
await pending;
assert.equal(s.counts().repositoryReads, 2);
assert.equal(s.nodes.get('socialLinkActionMessage').textContent, 'Publicación eliminada correctamente.');
assert.equal(s.nodes.get('socialLinkActionMessage').className, 'message success');
assert.equal(s.nodes.get('moderationMessage').textContent, '');
assert.equal(s.nodes.get('socialLinkList').buttons.length, 0);
assert.equal(s.window.test.pendingModerations.size, 0);

for (const options of [{dispatchError: 'No se pudo enviar'}]) {
  s = scenario(options);
  const result = s.click(); s.release(); await result;
  assert.equal(s.nodes.get('socialLinkActionMessage').textContent, options.dispatchError || options.pollError);
  assert.equal(s.nodes.get('socialLinkActionMessage').className, 'message error');
  const button = s.nodes.get('socialLinkList').buttons.find(button => button.dataset.action === 'delete-own');
  assert.equal(button.disabled, false); assert.equal(button.textContent, 'Eliminar');
}
s = scenario();
let result = s.click(); s.release(); await result;
assert.equal(s.counts().repositoryReads, 120);
assert.match(s.nodes.get('socialLinkActionMessage').textContent, /todavía no se ha confirmado/);
assert.equal(s.nodes.get('socialLinkActionMessage').className, 'message');
assert.notEqual(s.nodes.get('socialLinkActionMessage').textContent, 'Publicación eliminada correctamente.');
s = scenario({pollError: 'No se pudo confirmar'});
result = s.click(); s.release(); await result;
assert.equal(s.counts().repositoryReads, 120);
assert.match(s.nodes.get('socialLinkActionMessage').textContent, /todavía no se ha confirmado/);
assert.equal(s.nodes.get('socialLinkActionMessage').className, 'message');
s = scenario({confirm: false});
await s.click();
assert.equal(s.counts().postCalls, 0);
assert.equal(s.nodes.get('socialLinkActionMessage').textContent, '');
s = scenario({states: [removed]});
result = s.window.test.moderate('delete-own', 'target'); s.release(); await result;
assert.equal(s.nodes.get('moderationMessage').textContent, 'Publicación eliminada correctamente.');
assert.equal(s.nodes.get('socialLinkActionMessage').textContent, '');

console.log('PASS: social-link deletion shows progress and results in its own module, prevents duplicate requests, survives rerenders and reports errors or unconfirmed requests. No external requests.');
