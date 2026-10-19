import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('app.js', 'utf8');
const initial = Date.parse('2026-10-19T12:00:00Z');
let clock = initial;
class Clock extends Date { static now() { return clock; } }
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, {innerHTML:'',value:'',textContent:'',dataset:{},hidden:true,
    querySelector:()=>null,addEventListener(){},querySelectorAll:()=>[]});
  return nodes.get(id);
};
const document = {hidden:false,getElementById:node,querySelectorAll:()=>[],querySelector:()=>null};
const context = vm.createContext({URL,Intl,Date:Clock,console,document,window:{},navigator:{},localStorage:{getItem:()=>null}});
vm.runInContext(source.slice(0,source.lastIndexOf('sourceSelect.addEventListener')),context);
const run = code => vm.runInContext(code,context);
const official = overrides => ({id:'one',source_id:'aemet',source:'AEMET · Serra de Tramuntana',source_type:'official',
  category:'alerts',title:'Avís de pluja',summary:'Horari original',url:'https://www.aemet.es/aviso',
  published_at:'2026-10-19T10:00:00Z',alert_status:'active',alert_in_feed:true,
  alert_valid_from:'2026-10-19T11:00:00Z',alert_valid_until:'2026-10-19T13:00:00Z',...overrides});
const notice = node('currentAlerts');
function load(items, payload={}) {
  clock = initial;
  context.payload = {posts:items,sources_checked_at:'2026-10-19T11:45:00Z',
    source_status:[{source_id:'aemet',ok:true}],...payload};
  run('applyPostsPayload(payload);currentCategory="now";currentSource="all";currentSearch="";currentLanguage="ca";renderFeed()');
}
load([official()]);
assert.equal(notice.hidden,false);
assert.ok(notice.innerHTML.includes('Avisos oficials vigents'));
assert.ok(notice.innerHTML.includes('13:00')); // 11:00 UTC -> Mallorca 13:00
assert.ok(notice.innerHTML.includes('15:00')); // end, not machine timezone
assert.ok(notice.innerHTML.includes('AEMET · Serra de Tramuntana'));
const original = official();
const excluded = [
  {source_type:'media'}, {source_type:'own'}, {category:'news'}, {alert_in_feed:false},
  {alert_status:'unverified'}, {alert_status:'archived'}, {alert_status:'expired'},
  {alert_valid_from:'2026-10-19T12:01:00Z',alert_status:'scheduled'},
  {alert_valid_until:'2026-10-19T12:00:00Z'}, {alert_valid_until:''},
  {alert_valid_from:''}, {alert_valid_from:'bad'}, {published_at:'bad'},
  {published_at:'2026-10-19T12:01:00Z'}, {title:''}, {url:'javascript:alert(1)'},
];
for (const override of excluded) {
  load([official(override)]);
  assert.equal(notice.hidden,true,JSON.stringify(override));
  assert.equal(notice.innerHTML,'');
}
for (const payload of [
  {sources_checked_at:null}, {sources_checked_at:'bad'},
  {sources_checked_at:'2026-10-19T12:06:00Z'},
  {sources_checked_at:'2026-10-19T09:59:59Z',fetched_at:'2026-10-19T12:00:00Z'},
  {source_status:[{source_id:'aemet',ok:false}]}, {source_status:[]},
]) {
  load([original],payload);
  assert.equal(notice.hidden,true);
}
load([original],{sources_checked_at:'2026-10-19T10:00:00Z'});
assert.equal(notice.hidden,false); // exact two-hour boundary
load([official({alert_status:'scheduled'})]);
context.item=official({alert_status:'scheduled'});
assert.equal(run('alertStatus(item)'),'active');
assert.equal(notice.hidden,false);
context.item=official({alert_valid_from:'2026-10-19T12:05:00Z'});
assert.equal(run('alertStatus(item)'),'scheduled');

load([official({show_in_now:false})]);
assert.equal(notice.hidden,true);
run('currentCategory="alerts";renderFeed()');
assert.equal(notice.hidden,false);
for (const category of ['all','news','politics','social']) {
  context.category=category;
  run('currentCategory=category;renderFeed()');
  assert.equal(notice.hidden,true,category);
}
load([official()]);
run('currentSource="name:other";renderFeed()');assert.equal(notice.hidden,true);
run('currentSource="all";currentSearch="does not match";renderFeed()');assert.equal(notice.hidden,true);
run('currentSearch="pluja";renderFeed()');assert.equal(notice.hidden,false);

// Same source, event and period appear once, keeping the latest bulletin.
load([official({id:'old'}), official({id:'new',published_at:'2026-10-19T11:55:00Z',url:'https://www.aemet.es/new'})]);
assert.equal((notice.innerHTML.match(/class="current-alert-item"/g)||[]).length,1);
assert.ok(notice.innerHTML.includes('https://www.aemet.es/new'));
load([official(), official({id:'two',title:'Avís de vent'}), official({id:'three',title:'Avís de costa'})]);
assert.ok(notice.innerHTML.includes('Altres avisos vigents (1)'));
assert.equal((notice.innerHTML.match(/class="current-alert-item"/g)||[]).length,3);
for (const [lang,label] of [['es','Avisos oficiales vigentes'],['en','Current official alerts'],['ca','Avisos oficials vigents']]) {
  context.language=lang;
  run('currentLanguage=language;renderFeed()');
  assert.ok(notice.innerHTML.includes(label));
}
load([official({title:'<img src=x> Pluja',source:'<script>bad</script>'})]);
assert.ok(notice.innerHTML.includes('&lt;img'));
assert.ok(notice.innerHTML.includes('&lt;script&gt;'));
assert.ok(!notice.innerHTML.includes('<img'));

// Expiry is clock-driven, without reloading embeds, moving or rewriting the feed.
load([original]);
const before = node('feed').innerHTML;
const saved = JSON.stringify(context.payload);
clock = Date.parse('2026-10-19T13:00:00Z');
document.hidden=true;
run('refreshCurrentAlerts()');assert.equal(notice.hidden,false);
document.hidden=false;
run('refreshCurrentAlerts()');assert.equal(notice.hidden,true);
assert.equal(node('feed').innerHTML,before);
assert.equal(JSON.stringify(context.payload),saved);
assert.ok(source.includes('window.setInterval(refreshCurrentAlerts, 60000)'));
assert.ok(source.includes('document.addEventListener("visibilitychange", refreshCurrentAlerts)'));
console.log('PASS: current official alerts require verified intervals and recent successful source review, respect Ara/source/search filters, deduplicate bulletins, translate, escape HTML and expire without rewriting the feed.');
