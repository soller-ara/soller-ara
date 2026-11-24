import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('admin/admin.js', 'utf8');
function scenario({healthDelay = false, healthError = false, readFails = false, invalidRead = false, storedPost = null, approve = true} = {}) {
  const nodes = new Map();
  const defaults = {category: 'agenda', language: 'ca', content_type: 'social_link',
    title: 'Título', body: 'Resumen', source_name: 'Fuente', original_url: 'https://example.test/post',
    image_url: '', instagram: false, facebook: false, image_authorized: false, show_in_now: true};
  const getNode = id => {
    if (!nodes.has(id)) {
      const fields = new Map();
      const item = {id, value: '', textContent: '', innerHTML: '', dataset: {}, disabled: false,
        listeners: {}, hidden: false, classList: {toggle() {}, add() {}, remove() {}},
        addEventListener(type, callback) {this.listeners[type] = callback;},
        querySelector(selector) {const name = selector.match(/name="([^"]+)"/)?.[1]; return name ? this.elements[name] : getNode(id + selector);},
        querySelectorAll() {return [];}, reset() {},
        elements: new Proxy({}, {get(_, key) {
          if (!fields.has(key)) fields.set(key, {value: typeof defaults[key] === 'string' ? defaults[key] : '',
            checked: defaults[key] === true, disabled: false, addEventListener() {}});
          return fields.get(key);
        }}),
      };
      nodes.set(id, item);
    }
    return nodes.get(id);
  };
  let healthCalls = 0, dispatches = 0, releaseHealth;
  const submitted = [], prompts = [];
  const healthReady = new Promise(resolve => {releaseHealth = resolve;});
  const state = {posts: {posts: storedPost ? [storedPost] : []}, moderation: {hidden_post_ids: []}};
  const context = vm.createContext({console, URL, Headers, Date, Intl,
    sessionStorage: {getItem: () => '', setItem() {}, removeItem() {}},
    document: {getElementById: getNode, querySelectorAll: () => []},
    window: {SOLLER_ARA_ADMIN_API: 'https://admin.test', scrollTo() {},
      SOLLER_ARA_READ_JSON: async path => {
        if (readFails) throw new Error('Lectura temporalmente no disponible');
        if (invalidRead) return invalidRead === true ? {} : structuredClone(path === 'data/posts.json' ? invalidRead.posts : invalidRead.moderation);
        return structuredClone(path === 'data/posts.json' ? state.posts : state.moderation);
      }},
    FormData: class {
      constructor(form) {this.form = form;}
      get(name) {const field = this.form.elements[name]; return name in defaults && typeof defaults[name] === 'boolean' ? (field.checked ? 'on' : null) : field.value;}
    },
    confirm: message => {prompts.push(message);return approve;}, setTimeout: callback => callback(),
    fetch: async (url, options = {}) => {
      if (url.endsWith('/health')) {
        healthCalls++;
        if (healthDelay) await healthReady;
        if (healthError) return {ok: false, status: 503};
        return {ok: true, status: 200, json: async () => ({capabilities: ['manual_social_links']})};
      }
      if (options.method === 'POST') {
        dispatches++;
        const payload = JSON.parse(options.body);
        submitted.push({url, payload});
        state.posts.posts = [{...payload, id: payload.post_id || 'saved', source_type: 'own',
          summary: payload.body, source: payload.original_url ? payload.source_name || 'Publicació de xarxa' : 'Sóller Ara'}];
      }
      return {ok: true, status: 200, json: async () => structuredClone(state)};
    },
  });
  vm.runInContext(source.replace(/\}\)\(\);\s*$/, `
    window.test = {startEdit, startSocialLinkEdit, waitForModeration, loadStatus, renderPosts, ownPostMatches,
      getState() {return statusPayload;}, setState(value) {statusPayload = value;}};
  })();`), context);
  context.window.test.setState(structuredClone(state));
  return {nodes, getNode, context, releaseHealth, submitted, prompts, counts: () => ({healthCalls, dispatches}),
    submit: id => getNode(id).listeners.submit({preventDefault() {}})};
}

let s = scenario({healthDelay: true});
s.getNode('socialLinkForm').elements.facebook.checked = true;
const first = s.submit('socialLinkForm');
const second = s.submit('socialLinkForm');
assert.equal(s.counts().healthCalls, 1, 'Second click must not start another health check or dispatch');
assert.equal(s.getNode('socialLinkSubmitButton').disabled, true);
assert.equal(s.getNode('cancelSocialLinkEditButton').disabled, true);
s.context.window.test.startSocialLinkEdit('another');
s.getNode('cancelSocialLinkEditButton').listeners.click();
assert.equal(s.getNode('socialLinkSubmitButton').disabled, true);
s.releaseHealth(); await Promise.all([first, second]);
assert.equal(s.counts().dispatches, 1);
assert.equal(s.submitted[0].payload.facebook, true);
assert.equal(s.submitted[0].payload.instagram, false);
assert.equal(s.getNode('socialLinkSubmitButton').disabled, false);
assert.equal(s.getNode('cancelSocialLinkEditButton').disabled, false);

s = scenario({healthError: true});
await s.submit('socialLinkForm');
assert.equal(s.counts().dispatches, 0);
assert.match(s.getNode('socialLinkMessage').textContent, /comprobar el servidor/);
assert.ok(!s.getNode('socialLinkMessage').textContent.includes('desplegar'));
assert.equal(s.getNode('socialLinkSubmitButton').disabled, false);

const saved = {id: 'saved', source_type: 'own', title: 'Título', summary: 'Resumen',
  category: 'agenda', language: 'ca', source: 'Fuente', show_in_now: true,
  content_type: 'social_link', original_url: 'https://example.test/post'};
s = scenario({storedPost: saved});
s.context.window.test.startSocialLinkEdit('saved');
assert.equal(s.getNode('socialLinkForm').elements.facebook.checked, false);
assert.equal(s.getNode('socialLinkForm').elements.facebook.disabled, true);
// Even a stale or programmatically checked destination must not resend an edit.
s.getNode('socialLinkForm').elements.facebook.checked = true;
s.getNode('socialLinkForm').elements.instagram.checked = true;
await s.submit('socialLinkForm');
assert.match(s.getNode('socialLinkMessage').textContent, /actualizado correctamente/);
assert.equal(s.submitted[0].payload.facebook, false);
assert.equal(s.submitted[0].payload.instagram, false);
assert.ok(s.submitted[0].url.endsWith('/api/edit'));
s.getNode('cancelSocialLinkEditButton').listeners.click();
assert.equal(s.getNode('socialLinkForm').elements.facebook.disabled, false);

// Sharing a bare Instagram reference on Facebook does not require a fabricated summary.
s = scenario();
let fields = s.getNode('socialLinkForm').elements;
fields.original_url.value = 'https://www.instagram.com/p/Reference123/';
fields.title.value = '';fields.body.value = '';fields.facebook.checked = true;
await s.submit('socialLinkForm');
assert.equal(s.submitted.length, 1);
assert.equal(s.submitted[0].payload.facebook, true);
assert.equal(s.submitted[0].payload.instagram, false);
assert.equal(s.submitted[0].payload.original_url, fields.original_url.value);
assert.match(s.prompts[0], /Facebook/);

s = scenario();await s.submit('socialLinkForm');
assert.equal(s.submitted[0].payload.facebook, false, 'Facebook remains an explicit choice');
assert.ok(!s.prompts[0].includes('Facebook'));
s = scenario({approve:false});s.getNode('socialLinkForm').elements.facebook.checked = true;
await s.submit('socialLinkForm');assert.equal(s.counts().dispatches,0);
assert.equal(s.counts().healthCalls,0,'Cancelling confirmation never starts the send');

// A confirmed Facebook receipt wins over a later error; no receipt is not a failure.
s = scenario({storedPost:saved});
s.context.window.test.setState({posts:{posts:[saved]},socialLog:{entries:[]}});
s.context.window.test.renderPosts();
assert.ok(!s.getNode('socialLinkList').innerHTML.includes('Facebook:'));
s.context.window.test.setState({posts:{posts:[saved]},socialLog:{entries:[
  {post_id:saved.id,platform:'facebook',status:'error',error:'Do not render raw errors <script>'},
]}});s.context.window.test.renderPosts();
assert.match(s.getNode('socialLinkList').innerHTML,/Facebook: error de envío/);
assert.ok(!s.getNode('socialLinkList').innerHTML.includes('Do not render raw errors'));
s.context.window.test.setState({posts:{posts:[saved]},socialLog:{entries:[
  {post_id:saved.id,platform:'facebook',status:'success',remote_id:'confirmed'},
  {post_id:saved.id,platform:'facebook',status:'error'},
]}});s.context.window.test.renderPosts();
assert.match(s.getNode('socialLinkList').innerHTML,/Facebook: publicado/);
assert.ok(!s.getNode('socialLinkList').innerHTML.includes('Facebook: error'));

const html = await fs.readFile('admin/index.html','utf8');
const socialForm = html.match(/<form id="socialLinkForm"[^>]*>([\s\S]*?)<\/form>/)?.[1];
const facebookField = socialForm?.match(/<input\b[^>]*name="facebook"[^>]*>/)?.[0];
assert.ok(facebookField,'The real social-link form offers Facebook');
assert.ok(!/\b(?:checked|disabled)\b/.test(facebookField),'New Facebook destinations start unchecked and enabled');

// Clearing a source label must not match its old value before the backend has saved it.
const expected = {...saved, title:saved.title, body:saved.summary, source_name:'', show_in_now:true};
assert.equal(s.context.window.test.ownPostMatches(saved, expected), false);
assert.equal(s.context.window.test.ownPostMatches({...saved,source:'Publicació de xarxa'}, expected), true);

s = scenario({storedPost: {...saved, original_url: '', content_type: 'own'}});
s.context.window.test.startEdit('saved');
await s.submit('publishForm');
assert.match(s.getNode('moderationMessage').textContent, /Cambios guardados/);

s = scenario({readFails: true});
assert.equal(await s.context.window.test.waitForModeration('delete-own', 'target'), false,
  'A failed repository read must not confirm deletion from an empty backend fallback');
assert.ok(!s.getNode('moderationMessage').textContent.includes('correctamente'));

s = scenario({invalidRead: true});
assert.equal(await s.context.window.test.waitForModeration('delete-own', 'target'), false);
for(const posts of [{posts:[{}]}, {posts:[{id:'same'},{id:'same'}]}, {posts:[],post_count:1}]) {
 s = scenario({invalidRead:{posts,moderation:{hidden_post_ids:[]}}});
 assert.equal(await s.context.window.test.waitForModeration('delete-own', 'target'), false);
}
s = scenario({invalidRead:{posts:{posts:[]},moderation:{hidden_post_ids:[{}]}}});
assert.equal(await s.context.window.test.waitForModeration('delete-own', 'target'), false);

// A failed refresh retains the last verified state and shows the failure in the current module.
s = scenario({readFails: true});
const verified = {posts: {posts: [saved]}, moderation: {hidden_post_ids: []}};
s.context.window.test.setState(verified);
assert.equal(await s.context.window.test.loadStatus(s.getNode('socialLinkActionMessage')), false);
assert.equal(s.context.window.test.getState(), verified);
assert.match(s.getNode('socialLinkActionMessage').textContent, /Lectura temporalmente/);
assert.equal(s.getNode('refreshButton').disabled, false);

s = scenario({storedPost: {...saved, title:'<img src=x onerror=alert(1)>',
  url:'javascript:alert(1)', original_url:'data:text/html,unsafe'}});
s.context.window.test.renderPosts();
for(const id of ['postList','socialLinkList']) {
 assert.ok(s.getNode(id).innerHTML.includes('&lt;img'));
 assert.ok(!s.getNode(id).innerHTML.includes('href="javascript:'));
 assert.ok(!s.getNode(id).innerHTML.includes('href="data:'));
}

console.log('PASS: exclusive submissions and edit controls, visible edit confirmation, transient health errors, invalid/read failure rejection, verified state preservation, escaped titles and safe administration links. No external requests.');
