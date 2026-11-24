import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('app.js', 'utf8');
const nodes = new Map();
const guards = [];
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    innerHTML: '', value: '', textContent: '', dataset: {},
    addEventListener() {}, querySelectorAll() { return []; },
  });
  return nodes.get(id);
}
const feed = node('feed');
feed.contains = element => guards.some(guard => element === guard || element === guard.control);
feed.querySelectorAll = () => guards.filter(guard => guard.classList.contains('is-interactive'));
const context = vm.createContext({
  URL, Intl, Date, console,
  localStorage: { getItem() { return 'ca'; } },
  document: { getElementById: node, querySelectorAll() { return []; }, querySelector() { return null; } },
  window: {}, navigator: {},
});
vm.runInContext(source.slice(0, source.lastIndexOf('sourceSelect.addEventListener')), context);
const run = code => vm.runInContext(code, context);

function guard() {
  const classes = new Set();
  const frame = { src: 'https://publisher.test/article/embed/', loadCount: 1 };
  const item = {
    frame,
    classList: {
      contains: name => classes.has(name),
      toggle(name, enabled) { if (enabled) classes.add(name); else classes.delete(name); },
    },
  };
  item.control = {
    attrs: { 'aria-pressed': 'false' }, textContent: '',
    closest: () => item,
    setAttribute(name, value) { this.attrs[name] = value; },
  };
  item.querySelector = () => item.control;
  Object.defineProperty(item, 'innerHTML', { set() { throw new Error('An active iframe must not be rebuilt'); } });
  guards.push(item);
  return item;
}

const first = guard(), second = guard();
context.firstControl = first.control;
context.secondControl = second.control;
run('toggleEmbedInteraction(firstControl)');
assert.ok(first.classList.contains('is-interactive'));
assert.equal(first.control.attrs['aria-pressed'], 'true');
assert.equal(first.control.textContent, 'Continua desplaçant la pàgina');
run('toggleEmbedInteraction(secondControl)');
assert.ok(!first.classList.contains('is-interactive'));
assert.ok(second.classList.contains('is-interactive'));
assert.equal(first.control.attrs['aria-pressed'], 'false');
assert.equal(first.control.textContent, 'Interactua amb la publicació');
run('toggleEmbedInteraction(secondControl)');
assert.ok(!second.classList.contains('is-interactive'));
assert.equal(second.control.attrs['aria-pressed'], 'false');
for (const item of guards) {
  assert.equal(item.frame.src, 'https://publisher.test/article/embed/');
  assert.equal(item.frame.loadCount, 1);
}
context.foreignControl = { closest: () => ({ classList: { contains() { throw new Error('Foreign control'); } } }) };
run('toggleEmbedInteraction(foreignControl)');

const image = '<div class="social-embed social-embed-image"><img src="https://example.test/authorized.jpg"></div>';
context.image = image;
assert.equal(run('renderEmbedNavigation(image)'), image);
assert.equal(run('renderEmbedNavigation("")'), '');
context.frameMarkup = '<div class="social-embed"><iframe src="https://publisher.test/article/embed/"></iframe></div>';
assert.ok(run('renderEmbedNavigation(frameMarkup)').includes('aria-pressed="false"'));
assert.ok(run('renderEmbedNavigation(frameMarkup)').includes(context.frameMarkup));

for (const [language, label] of [
  ['ca', 'Interactua amb la publicació'],
  ['es', 'Interactuar con la publicación'],
  ['en', 'Interact with the post'],
]) {
  run(`currentLanguage=${JSON.stringify(language)}`);
  assert.ok(run('renderEmbedNavigation(frameMarkup)').includes(label));
}
run('currentLanguage="ca"');
const base = { id: 'post', title: 'Titular', source: 'Font local', category: 'news',
  published_at: new Date().toISOString(), source_type: 'social' };
for (const [platform, url, expected] of [
  ['facebook', 'https://www.facebook.com/test/posts/123', 'plugins/post.php'],
  ['instagram', 'https://www.instagram.com/p/ABC123/', 'instagram-media'],
  ['x', 'https://x.com/test/status/123', 'twitter-tweet'],
  ['youtube', 'https://www.youtube.com/watch?v=abcdefghijk', 'youtube-nocookie.com'],
  ['tiktok', 'https://www.tiktok.com/@test/video/12345', 'tiktok.com/player'],
  ['vimeo', 'https://vimeo.com/12345', 'player.vimeo.com'],
]) {
  context.post = { ...base, platform, url };
  const markup = run('renderPostCard(post)');
  assert.ok(markup.includes('data-embed-toggle'), platform);
  assert.ok(markup.includes(expected), platform);
}
context.post = { ...base, source_type: 'institution', url: 'https://publisher.test/article/',
  embed_type: 'official_oembed', embed_url: 'https://publisher.test/article/embed/' };
assert.ok(run('renderPostCard(post)').includes('data-embed-toggle'));
context.post = { ...base, source_type: 'own', url: 'https://example.test/own',
  media_type: 'image', media_url: 'https://example.test/authorized.jpg' };
assert.ok(!run('renderPostCard(post)').includes('data-embed-toggle'));
console.log('PASS: mobile embed opt-in, single active preview, return control, three languages, original iframe identity, SDK wrappers and unchanged native images.');
