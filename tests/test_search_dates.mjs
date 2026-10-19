import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('app.js', 'utf8');
const now = Date.parse('2026-10-19T09:00:00Z');
class Clock extends Date { static now() { return now; } }
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value:'', innerHTML:'', textContent:'', hidden:false, dataset:{}, listeners:{}, attributes:{},
    addEventListener(type, listener) { this.listeners[type] = listener; },
    setCustomValidity(message) { this.validationMessage = message; },
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelectorAll() { return []; },
    insertAdjacentHTML(position, markup) { assert.equal(position,'beforeend'); this.innerHTML += markup; },
  });
  return nodes.get(id);
}
const context = vm.createContext({Date:Clock, Intl, URL, console,
  localStorage:{getItem:()=>null}, window:{}, navigator:{},
  document:{documentElement:{}, getElementById:id=>id==='aemetWidget'?null:node(id),
    querySelectorAll:()=>[], querySelector:()=>null},
});
vm.runInContext(source.slice(0, source.lastIndexOf('sourceSelect.addEventListener')), context);
const run = code => vm.runInContext(code, context);
function load(items) {
  context.items = items;
  node('dateFromInput').value = node('dateUntilInput').value = '';
  run('posts=items;currentCategory="all";currentSource="all";currentSearch="";currentLanguage="ca";handleDateFilterChange()');
}
const ids = () => Array.from(run('filteredPosts().map(post=>post.id)'));
function dates(from='', until='') {
  node('dateFromInput').value = from;
  node('dateUntilInput').value = until;
  node('dateUntilInput').listeners.change();
}
const base = {source:'Font local', source_id:'local', source_type:'media', category:'news',
  summary:'Resum', url:'https://example.test/original', published_at:'2026-10-19T08:00:00Z'};

// Search is accent-insensitive in every searchable field and preserves the originals.
const words = [
  {...base,id:'title',title:'Festa de Sóller'},
  {...base,id:'summary',title:'Acte local',summary:'Música a Deià'},
  {...base,id:'source',title:'Acte municipal',source:'Associació Cultural'},
  {...base,id:'related',title:'Acte compartit',related_sources:[{source:'Club d’Atletisme',title:'Competició esportiva'}]},
  {...base,id:'decomposed',title:'Exposicio\u0301 a Fo\u0301rnalutx'},
  {...base,id:'missing'},
];
const originalWords = JSON.stringify(words);
load(words);
for (const [query, expected] of [['SOLLER',['title']],['sóller',['title']],['  musica   a  deia  ',['summary']],
  ['associacio',['source']],['competicio',['related']],['atletisme',['related']],['exposició',['decomposed']],['fornalutx',['decomposed']]]) {
  context.query = query;
  for (const language of ['ca','es','en']) {
    context.language = language;
    run('currentLanguage=language;currentSearch=query');
    assert.deepEqual(ids(), expected, `${language}: ${query}`);
  }
}
assert.equal(JSON.stringify(words), originalWords);

// Inclusive calendar-day bounds use Mallorca time, not UTC or retrieval time.
const edges = [
  {...base,id:'before',published_at:'2026-10-18T21:59:59.999Z'},
  {...base,id:'start',published_at:'2026-10-18T22:00:00Z'},
  {...base,id:'end',published_at:'2026-10-19T21:59:59.999Z'},
  {...base,id:'after',published_at:'2026-10-19T22:00:00Z'},
  {...base,id:'old',published_at:'2026-09-18T10:00:00+02:00',fetched_at:'2026-10-19T08:00:00Z'},
  {...base,id:'invalid',published_at:'invalid'},
  {...base,id:'undated',published_at:null},
];
load(edges);
assert.equal(ids().length,7,'no date filter must retain the existing inventory');
dates('2026-10-19','2026-10-19');assert.deepEqual(ids(),['start','end']);
dates('2026-10-19');assert.deepEqual(ids(),['start','end','after']);
dates('','2026-10-19');assert.deepEqual(ids(),['before','start','end','old']);
assert.ok(node('dateFilterSummary').textContent.includes('Fins a'));
dates('2026-10-20','2026-10-19');
assert.deepEqual(ids(),[]);
assert.equal(node('dateUntilInput').attributes['aria-invalid'],'true');
assert.equal(node('dateFilterError').hidden,false);
assert.ok(node('dateUntilInput').validationMessage.includes('posterior'));
run('currentLanguage="en";applyTranslations()');
assert.equal(node('dateFilterError').textContent,'The end date must be on or after the start date.');
node('clearDatesButton').listeners.click();
assert.equal(ids().length,7);assert.equal(node('dateFilterError').hidden,true);
assert.equal(node('dateUntilInput').validationMessage,'');
assert.equal(node('dateUntilInput').attributes['aria-invalid'],'false');
assert.equal(node('dateFromInput').value,'');assert.equal(node('dateUntilInput').value,'');
assert.equal(node('dateFilterSummary').textContent,'');assert.equal(node('clearDatesButton').disabled,true);

// Mallorca's daylight-saving change must not shift either boundary or lose the repeated hour.
load([
  {...base,id:'dst-before',published_at:'2026-10-24T21:59:59Z'},
  {...base,id:'dst-start',published_at:'2026-10-24T22:00:00Z'},
  {...base,id:'first-02h',published_at:'2026-10-25T00:30:00Z'},
  {...base,id:'second-02h',published_at:'2026-10-25T01:30:00Z'},
  {...base,id:'dst-end',published_at:'2026-10-25T22:59:59.999Z'},
  {...base,id:'dst-after',published_at:'2026-10-25T23:00:00Z'},
]);
dates('2026-10-25','2026-10-25');
assert.deepEqual(ids(),['dst-start','first-02h','second-02h','dst-end']);

// Dates intersect the complete inventory, category/source/search filters and Ara's opt-out.
const inventory = Array.from({length:53},(_,index)=>({...base,id:'post-'+index,title:'Notícia '+index,
  source:index<45?'Primera font':'Segona font',category:index%2?'culture':'news',
  published_at:index<45?'2026-10-19T08:00:00Z':'2026-10-18T08:00:00Z'}));
load(inventory);run('renderFeed({append:true})');
assert.equal(run('renderedFeedPosts.length'),40);
dates('2026-10-19','2026-10-19');assert.equal(run('renderedFeedPosts.length'),20);
assert.equal(ids().length,45);run('renderFeed({append:true})');
assert.equal(run('renderedFeedPosts.length'),40);
run('currentLanguage="es";applyTranslations()');
assert.equal(run('renderedFeedPosts.length'),40);
assert.equal(node('feedProgress').textContent,'Mostrando 40 de 45 publicaciones');
assert.ok(node('dateFilterSummary').textContent.includes('19/10/2026'));
dates('2026-10-18','2026-10-18');assert.equal(run('renderedFeedPosts.length'),8);
run('currentCategory="culture";currentSource="name:segona font";currentSearch="noticia 51";renderFeed()');
assert.deepEqual(ids(),['post-51']);assert.ok(node('feed').innerHTML.includes('Notícia 51'));
run('currentSearch="";currentCategory="now";currentSource="all"');
inventory[51].show_in_now=false;
assert.ok(!ids().includes('post-51'));
dates('2026-09-01','2026-09-30');assert.deepEqual(ids(),[]);
assert.equal(node('feedPagination').hidden,true);
assert.deepEqual(inventory.map(post=>post.id),Array.from({length:53},(_,index)=>'post-'+index));

// An active alert follows its original publication date, not its validity window.
load([{...base,id:'warning',title:'Avís oficial vigent',source_type:'official',category:'alerts',
  published_at:'2026-10-18T10:00:00+02:00',alert_in_feed:true,alert_status:'active',
  alert_valid_from:'2026-10-19T08:00:00Z',alert_valid_until:'2026-10-19T12:00:00Z'}]);
run('sourcesCheckedAt="2026-10-19T09:00:00Z";sourceStatus=[{source_id:"local",ok:true}];currentCategory="alerts";renderFeed()');
assert.equal(node('currentAlerts').hidden,false);
dates('2026-10-19','2026-10-19');assert.equal(node('currentAlerts').hidden,true);
dates('2026-10-18','2026-10-18');assert.equal(node('currentAlerts').hidden,false);
console.log('PASS: accent-insensitive global search, inclusive Mallorca dates and DST, validation/clear handlers, translations, combined filters and pagination resets.');
