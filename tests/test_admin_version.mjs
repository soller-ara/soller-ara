import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const html = await fs.readFile('admin/index.html', 'utf8');
const config = await fs.readFile('admin/config.js', 'utf8');
const initialVersion = html.match(/id="adminVersion"[^>]*>v([^<]+)</)[1];
const badge = {textContent: 'v' + initialVersion};
let onLoad;
const window = {addEventListener(event, callback) {
  assert.equal(event, 'DOMContentLoaded');
  onLoad = callback;
}};
const context = vm.createContext({window, document: {
  getElementById: id => id === 'adminVersion' ? badge : null,
  createElement: () => ({}),
  body: {appendChild() {}},
}});
vm.runInContext(config, context);
onLoad();
assert.equal(window.SOLLER_ARA_ADMIN_VERSION, initialVersion);
assert.equal(badge.textContent, 'v' + initialVersion,
  'Configuration must not overwrite the HTML badge with an older version');
for (const script of ['config.js', 'admin.js']) {
  const cacheVersion = html.match(new RegExp(`src="\\./${script.replace('.', '\\.')}\\?v=([^"]+)"`))[1];
  assert.ok(cacheVersion === initialVersion || cacheVersion.startsWith(initialVersion + '.'),
    `${script} must request the current administration version`);
}
console.log('PASS: administration keeps the same version before and after configuration loads, with current script cache keys.');
