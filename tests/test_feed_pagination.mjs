import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const source = await fs.readFile('app.js', 'utf8');
let focused, instagramCalls=0;
const xRoots=[];
class Node {
  constructor(id) { this.id=id;this._html='';this.children=[];this.value='all';this.dataset={};this.hidden=true;this.listeners={};this.writes=0;this.appends=0; }
  get innerHTML() { return this._html; }
  set innerHTML(value) { this.writes++;this._html=value;this.children=this.parse(value); }
  parse(value) { return [...value.matchAll(/<article\b([^>]*)>([\s\S]*?)<\/article>/g)].map(match=>{
    const node=new Node(match[1].match(/data-post-id="([^"]*)"/)?.[1]);node._html=match[0];return node;
  }); }
  insertAdjacentHTML(position,value) { assert.equal(position,'beforeend');this.appends++;this._html+=value;this.children.push(...this.parse(value)); }
  addEventListener(type,callback) { this.listeners[type]=callback; }
  querySelector(selector) {
    if (selector==='.instagram-media' && this._html.includes('instagram-media')) return {};
    if (selector==='[data-x-embed], .twitter-timeline' && this._html.includes('data-x-embed')) return {};
    return null;
  }
  querySelectorAll() { return []; }
  contains(node) { return this.children.includes(node.card); }
  focus(options) { focused=this;assert.equal(options.preventScroll,true); }
  scrollIntoView(options) { this.scrolled=options.block; }
}
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,new Node(id));return nodes.get(id);};
const feed=node('feed');
const document={hidden:false,documentElement:{lang:'ca'},
  getElementById:id=>id==='aemetWidget'?null:node(id),querySelectorAll:()=>[],
  querySelector:selector=>feed.children.map(child=>child.querySelector(selector)).find(Boolean)||null};
const shares=[];
const context=vm.createContext({Date,Intl,URL,console,document,localStorage:{getItem:()=>null},
  navigator:{share:async data=>shares.push(data)},window:{instgrm:{Embeds:{process:()=>instagramCalls++}},
    twttr:{widgets:{load:root=>xRoots.push(root||document)}}}});
vm.runInContext(source.slice(0,source.lastIndexOf('sourceSelect.addEventListener')),context);
const run=code=>vm.runInContext(code,context);
const now=Date.now();
const items=Array.from({length:53},(_,index)=>({id:'post-'+index,title:'Headline '+index,summary:index===52?'rare-query':'Body',
  source_id:index<21?'first':'second',source:index<21?'First source':'Second source',source_type:'media',
  category:index%2?'culture':'news',published_at:new Date(now-index*60000).toISOString(),url:'https://example.test/'+index}));
function load(records=items) {
  context.items=records;
  run('posts=items;currentCategory="all";currentSource="all";currentSearch="";currentLanguage="ca";renderFeed()');
}

load();
assert.equal(feed.children.length,20);
assert.equal(node('feedProgress').textContent,'Mostrant 20 de 53 publicacions');
assert.equal(node('loadMorePostsButton').hidden,false);
const first=feed.children.slice();const writes=feed.writes;
node('loadMorePostsButton').listeners.click();
assert.equal(feed.children.length,40);
assert.deepEqual(feed.children.slice(0,20),first,'existing DOM nodes must survive load more');
assert.equal(feed.writes,writes,'load more must append instead of rewriting innerHTML');
assert.equal(focused,feed.children[20]);assert.equal(focused.scrolled,'start');
assert.equal(node('feedProgress').textContent,'Mostrant 40 de 53 publicacions');
node('loadMorePostsButton').listeners.click();
assert.equal(feed.children.length,53);assert.equal(node('loadMorePostsButton').hidden,true);
assert.equal(new Set(feed.children.map(card=>card.id)).size,53);
run('renderFeed({append:true})');assert.equal(feed.children.length,53);
assert.deepEqual(feed.children.map(card=>card.id),items.map(item=>item.id));

// Search and source filters inspect the full inventory, including the last page.
run('currentSearch="rare-query";renderFeed()');
assert.equal(feed.children.length,1);assert.equal(feed.children[0].id,'post-52');
run('currentSearch="";currentSource="name:second source";renderFeed()');
assert.equal(feed.children.length,20);assert.equal(node('feedProgress').textContent,'Mostrant 20 de 32 publicacions');
assert.ok(feed.children.every(card=>Number(card.id.split('-')[1])>=21));
run('renderFeed({append:true})');assert.equal(feed.children.length,32);
run('currentCategory="culture";renderFeed()');assert.equal(feed.children.length,16);
run('currentSearch="no matches";renderFeed()');
assert.equal(feed.children.length,0);assert.equal(node('feedPagination').hidden,true);
assert.ok(feed.innerHTML.includes('No hi ha publicacions'));

for (const length of [0,1,19,20,21,40]) {
  load(items.slice(0,length));
  assert.equal(feed.children.length,Math.min(20,length));
  assert.equal(node('loadMorePostsButton').hidden,length<=20);
}
load();run('renderFeed({append:true});currentLanguage="en";applyTranslations()');
assert.equal(feed.children.length,40);
assert.equal(node('feedProgress').textContent,'Showing 40 of 53 posts');
assert.equal(node('loadMorePostsButton').textContent,'Show more');
run('currentLanguage="es";applyTranslations()');
assert.equal(feed.children.length,40);assert.equal(node('loadMorePostsButton').textContent,'Ver más');

// Ara remains in descending original publication order across every block.
load([...items].reverse());run('currentCategory="now";renderFeed();renderFeed({append:true});renderFeed({append:true})');
assert.deepEqual(feed.children.map(card=>card.id),items.map(item=>item.id));

// Sharing is delegated once to the feed and works for appended cards.
const button={dataset:{shareId:'post-40'},card:feed.children[40]};
feed.listeners.click({target:{closest:()=>button}});
assert.equal(shares.length,1);assert.equal(shares[0].url,'https://example.test/40');

// SDK processing must not revisit existing embeds for a plain appended batch.
const embedded=items.map(item=>({...item}));
embedded[0]={...embedded[0],source_type:'social',platform:'Instagram',url:'https://www.instagram.com/p/example/'};
embedded[1]={...embedded[1],source_type:'social',platform:'YouTube',url:'https://www.youtube.com/watch?v=abcdefghijk'};
embedded[21]={...embedded[21],source_type:'social',platform:'X',url:'https://x.com/example/status/123'};
embedded[41]={...embedded[41],source_type:'social',platform:'Instagram',url:'https://www.instagram.com/p/later/'};
load(embedded);
const instagram=feed.children[0],youtube=feed.children[1],igBefore=instagramCalls;
const xBefore=xRoots.length;
run('renderFeed({append:true})');
assert.equal(feed.children[0],instagram);assert.equal(feed.children[1],youtube);
assert.equal(instagramCalls,igBefore);
assert.equal(xRoots.length,xBefore+1);assert.equal(xRoots.at(-1),feed.children[21]);
run('renderFeed({append:true})');
assert.equal(instagramCalls,igBefore+1);assert.equal(feed.children[0],instagram);

// Active warnings use all filtered posts, even when their card is on a later page.
const warnings=items.map(item=>({...item}));
warnings[45]={...warnings[45],source_type:'official',category:'alerts',title:'Avís vigent més antic',
  alert_status:'active',alert_in_feed:true,alert_valid_from:new Date(now-3600000).toISOString(),
  alert_valid_until:new Date(now+3600000).toISOString()};
load(warnings);context.checked=new Date(now).toISOString();
run('sourcesCheckedAt=checked;sourceStatus=[{source_id:"second",ok:true}];currentCategory="now";renderFeed()');
assert.equal(feed.children.length,20);
assert.ok(!feed.children.some(card=>card.id==='post-45'));
assert.ok(node('currentAlerts').innerHTML.includes('Avís vigent més antic'));

// Changed data cannot accidentally append a stale or duplicate prefix.
const updated=[{...items[0],id:'new-headline'},...items];context.items=updated;
run('posts=items;renderFeed({append:true})');
assert.equal(feed.children.length,20);assert.equal(feed.children[0].id,'new-headline');
console.log('PASS: 20-post batches preserve nodes and order, search all posts, reset filters, retain language page size, share appended cards and scope embed processing to new content.');
