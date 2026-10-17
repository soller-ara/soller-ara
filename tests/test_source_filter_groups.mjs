import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('app.js', 'utf8');
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',value:'',textContent:'',dataset:{},
    addEventListener(){},querySelectorAll(){return []}});
  return nodes.get(id);
};
const context = vm.createContext({URL,Intl,Date,console,localStorage:{getItem:()=>null},
  document:{getElementById:node,querySelectorAll:()=>[],querySelector:()=>null}, window:{},navigator:{}});
vm.runInContext(source.slice(0,source.lastIndexOf('sourceSelect.addEventListener')),context);
const run = code => vm.runInContext(code,context);
const config = [
  {id:'town',name:'Ajuntament de Sóller'}, {id:'mes',name:'MÉS per Sóller'},
  {id:'school',name:'IES Guillem Colom Casasnoves'}, {id:'paper',name:'Setmanari Sóller'},
  {id:'sa-veu',name:'Sa Veu de Sóller'}, {id:'youtube',name:'Ajuntament de Sóller · YouTube'},
];
const post = (id,source_id,source,source_type='own') => ({id,source_id,source,source_type,
  title:id,category:'news',language:'ca',summary:'',published_at:new Date().toISOString(),
  url:'https://example.test/'+id});
const items = [
  post('automatic','town','Ajuntament de Sóller','official'),
  post('manual','manual-town','Ajuntament de Soller'),
  post('party-auto','mes','MÉS per Sóller','political_party'),
  post('party-manual','manual-mes','Mes per Sóller'),
  post('school-manual','manual-school','IES Guillem Colom Casasnovas'),
  post('paper-manual','manual-paper','Setmanari Sóller'),
  post('sa-veu-manual','manual-sa-veu','Setmanari Veu de Sóller'),
  post('youtube-post','youtube','Ajuntament de Sóller · YouTube','social'),
  post('reference','soller-ara','Publicació de xarxa'),
  post('own','soller-ara','Sóller Ara'),
  post('unsafe','manual-unsafe','<img src=x onerror=alert(1)>'),
  post('missing','manual-missing',''),
];
context.config = config; context.items = items;
run('configuredSources=config;posts=items;currentCategory="all";populateSourceSelect()');
const html = node('sourceSelect').innerHTML;
assert.equal((html.match(/>Ajuntament de Sóller<\/option>/g)||[]).length,1);
assert.ok(html.includes('>Ajuntament de Sóller · YouTube</option>'));
assert.equal((html.match(/>MÉS per Sóller<\/option>/g)||[]).length,1);
assert.ok(!html.includes('>Mes per Sóller</option>'));
assert.ok(!html.includes('>IES Guillem Colom Casasnovas</option>'));
assert.ok(!html.includes('>Setmanari Veu de Sóller</option>'));
assert.ok(html.includes('>Setmanari Sóller</option>'));
assert.ok(html.includes('>Sa Veu de Sóller</option>'));
assert.ok(html.includes('>Publicació de xarxa</option>') && html.includes('>Sóller Ara</option>'));
assert.ok(html.includes('&lt;img') && !html.includes('<img'));
assert.notEqual(run('sourceFilterKey("A+B")'),run('sourceFilterKey("A B")'));
assert.notEqual(run('sourceFilterKey("Setmanari Sóller")'),run('sourceFilterKey("Sa Veu de Sóller")'));
const original = JSON.stringify(items);
run('currentSource=sourceFilterKey("Ajuntament de Sóller");renderFeed()');
assert.ok(node('feed').innerHTML.includes('<h3>automatic</h3>'));
assert.ok(node('feed').innerHTML.includes('<h3>manual</h3>'));
assert.ok(!node('feed').innerHTML.includes('<h3>youtube-post</h3>'));
assert.ok(node('feed').innerHTML.includes('Ajuntament de Soller'), 'Original card attribution must remain unchanged');
run('currentSource=sourceFilterKey("Més per Sóller");renderFeed()');
assert.ok(node('feed').innerHTML.includes('party-auto') && node('feed').innerHTML.includes('party-manual'));
run('currentLanguage="en";populateSourceSelect()');
assert.equal(run('currentSource'),run('sourceFilterKey("MÉS per Sóller")'));
run('currentSearch="does-not-match-anything";renderFeed()');
assert.ok(node('feed').innerHTML.includes('No posts match'));
run('currentSearch="";currentSource=sourceFilterKey("Publicació de xarxa");renderFeed()');
assert.ok(node('feed').innerHTML.includes('<h3>reference</h3>'));
assert.ok(!node('feed').innerHTML.includes('<h3>own</h3>'));
assert.equal(JSON.stringify(items),original,'Grouping cannot modify publications or IDs');
run('configuredSources=[];populateSourceSelect()');
assert.equal(run('currentSource'),run('sourceFilterKey("Publicació de xarxa")'));
run('posts=[];populateSourceSelect()');
assert.equal(run('currentSource'),'all');
console.log('PASS: source grouping joins automatic/manual posts, preserves attributions and selection, separates publications sharing an ID and YouTube channels, handles aliases, missing names and escaping.');
