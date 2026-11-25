import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import { DatabaseSync } from 'node:sqlite';
import { webcrypto } from 'node:crypto';

// SQLite exercises the same transactions, cursor queries and uniqueness as the private D1 archive.
const sql = new DatabaseSync(':memory:'); sql.exec('PRAGMA foreign_keys=ON');
class Stmt {
  constructor(q,b=[]){this.q=q;this.b=b;}
  bind(...b){return new Stmt(this.q,b);}
  exec(){const st=sql.prepare(this.q);if(st.columns().length)return {results:st.all(...this.b)};return {meta:{changes:Number(st.run(...this.b).changes)}};}
  async run(){return this.exec();} async all(){return this.exec();} async first(){return sql.prepare(this.q).get(...this.b);}
}
const db={prepare:q=>new Stmt(q),async batch(ss){sql.exec('BEGIN');try{const out=ss.map(s=>s.exec());sql.exec('COMMIT');return out;}catch(e){sql.exec('ROLLBACK');throw e;}}};
const workerSource=(await fs.readFile('worker/admin-worker.js','utf8')).replace('export default {','const worker = {');
const ui=await fs.readFile('admin/social-watch.js','utf8');
const now=Date.parse('2026-11-25T16:30:00Z');
class Clock extends Date{static now(){return now;}}
const calls=[],env={SOCIAL_WATCH_DB:db,SESSION_SECRET:'isolated-test-session',WATCH_META_READ_TOKEN:'offline-only',WATCH_INSTAGRAM_ID:'123'};
let reply;
const context=vm.createContext({URL,URLSearchParams,Date:Clock,Intl,Request,Response,Headers,AbortSignal,TextEncoder,TextDecoder,crypto:webcrypto,btoa,atob,env,console,fetch:async(url,opts)=>{
  assert.equal(opts.method,'GET');assert.equal(opts.headers.Authorization,'Bearer offline-only');const u=new URL(url);
  assert.equal(u.host,'graph.facebook.com');assert.equal(u.searchParams.has('access_token'),false);calls.push(u);return new Response(JSON.stringify(reply(u)),{status:200});
}});
vm.runInContext(workerSource,context); vm.runInContext(ui,context);
const run=(expr)=>vm.runInContext(expr,context);
const token=await run('createSession(env.SESSION_SECRET)');
const path='https://worker.test/api/social-watch?from=2026-11-25&to=2026-11-25';
async function request(body,options={}){const req=new Request(options.url||path,{method:body?'POST':'GET',headers:options.noAuth?{}:{Authorization:'Bearer '+token},...(body?{body:JSON.stringify(body)}:{})});context.req=req;const response=await run('worker.fetch(req,env)');return [response.status,await response.json()];}
assert.equal((await request(undefined,{noAuth:true}))[0],401);
assert.deepEqual((await request())[1].posts,[]);
const api=run('globalThis.socialWatchTest'), plain=x=>JSON.parse(JSON.stringify(x));
assert.deepEqual(plain(api.period('today','',Date.parse('2026-11-24T23:30:00Z'))),{from:'2026-11-25',to:'2026-11-25'});
assert.deepEqual(plain(api.period('week','2026-03-29')),{from:'2026-03-23',to:'2026-03-29'});
assert.deepEqual(plain(api.period('week','2026-01-01')),{from:'2025-12-29',to:'2026-01-04'});
for(const bad of ['https://www.instagram.com/p/asd/','https://www.facebook.com/groups/12','http://instagram.com/abc','https://instagram.com.example.test/local','https://www.facebook.com/profile.php?id=abc']){
  assert.throws(()=>api.profile({profile:bad}));assert.equal((await request({action:'add',profile:bad}))[0],400);
}
const add={action:'add',profile:'https://www.instagram.com/Local_Museu/?igsh=xxx',name:'Museu'};
assert.equal((await request(add))[0],201);assert.equal((await request(add))[1].existing,true);
const id=(await request())[1].accounts[0].id;
let pages=0;
const post=(id,stamp,caption='Taller infantil: ceràmica i fang')=>({id:String(id),timestamp:stamp,caption,permalink:'https://www.instagram.com/p/P'+id+'/?igsh=tracking'});
reply=u=>{assert.match(u.searchParams.get('fields'),/business_discovery.username\(local_museu\)/);
  const n=++pages;return {business_discovery:{username:'LOCAL_MUSEU',media:n===1?{data:[post(1,'2026-11-24T23:30:00Z')],paging:{next:'opaque',cursors:{after:'page_2'}}}:n===2?{data:[post(2,'2026-11-24T13:00:00Z')],paging:{next:'opaque',cursors:{after:'page_3'}}}:{data:[post(1,'2026-11-24T23:30:00Z'),post(3,'2026-11-25T10:00:00Z','')]}}};};
assert.equal((await request({action:'check',id}))[1].state,'catching_up');
assert.equal((await request({action:'check',id}))[0],429);
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();await run('worker.scheduled({cron: WATCH_CRON},env)');
let data=(await request())[1];assert.equal(data.posts.length,2);assert.equal(data.accounts[0].status,'ready');
assert.equal(data.posts[1].url,'https://www.instagram.com/p/P1/');assert.match(data.posts[0].brief,/sin descripción/);
assert.ok(!data.posts[1].brief.includes('Taller infantil: ceràmica i fang'));
assert.equal((await request(undefined,{url:path.replaceAll('11-25','11-24')}))[1].posts.length,1);
assert.equal((await request(undefined,{url:path.replace('from=2026-11-25','from=2026-09-01')}))[0],400);
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();reply=()=>({error:{code:10}});
assert.equal((await request({action:'check',id}))[1].state,'permission');
data=(await request())[1];assert.equal(data.posts.length,2);assert.equal(data.accounts[0].status,'permission');
const fb={action:'add',profile:'https://www.facebook.com/profile.php?id=456',name:'Pàgina'};
assert.equal((await request(fb))[0],201);const fid=(await request())[1].accounts.find(x=>x.network==='facebook').id;
reply=u=>{assert.match(u.pathname,/\/456\/posts$/);return {data:[{id:'456_7',created_time:'2026-11-25T11:00:00+0000',permalink_url:'https://www.facebook.com/permalink.php?story_fbid=7&id=456&utm_source=other',message:'Avís canvi del calendari'}]};};
assert.equal((await request({action:'check',id:fid}))[1].state,'ready');
data=(await request())[1];assert.ok(data.posts.find(x=>x.url==='https://www.facebook.com/permalink.php?story_fbid=7&id=456'));
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();delete env.WATCH_META_READ_TOKEN;
const count=calls.length;assert.equal((await request({action:'check',id:fid}))[1].state,'credentials');assert.equal(calls.length,count);
await request({action:'remove',id});data=(await request())[1];assert.equal(data.accounts.length,1);assert.equal(data.posts.length,1);
delete env.SOCIAL_WATCH_DB;assert.equal((await request())[1].code,'watch_storage_setup');
assert.equal((await run('worker.scheduled({cron: WATCH_CRON},env)')).action,'watch_not_configured');
// Exercise the real handoff with no network, even if a prior draft contains unsaved text.
const admin=await fs.readFile('admin/admin.js','utf8');
const bridge=admin.slice(admin.indexOf('  window.SOLLER_ARA_WATCH_DRAFT ='),admin.indexOf('  function updateSocialPosterFields()'));
const input=(type='text')=>({type,tagName:'INPUT',value:'',defaultValue:'',checked:false,defaultChecked:false,focus(){}});
const formElements=Object.assign([], {source_name:input(),original_url:input(),facebook:input('checkbox'),instagram:input('checkbox'),title:input()});
formElements.push(...Object.values(formElements));let opened=0,reset=0;
const fixture={window:{confirm:()=>false},URL,socialLinkEditPostId:'',socialLinkSubmitButton:{disabled:false},socialLinkForm:{elements:formElements},
  resetSocialLinkEditMode(){reset++;},openModule(v){assert.equal(v,'social-links');opened++;},socialLinkMessage:{},setMessage(){},
  fetch(){throw Error('handoff must not call any service');}};
vm.runInNewContext(bridge,fixture);const draft=fixture.window.SOLLER_ARA_WATCH_DRAFT,sourceUrl='https://www.instagram.com/p/P1/';
formElements.title.value='Borrador existente';assert.equal(draft('Museu',sourceUrl),false);assert.equal(reset,0);
fixture.window.confirm=()=>true;assert.equal(draft('Museu',sourceUrl),true);assert.equal(formElements.original_url.value,sourceUrl);
assert.equal(formElements.source_name.value,'Museu');assert.equal(formElements.instagram.checked,false);assert.equal(formElements.facebook.checked,false);assert.equal(opened,1);
fixture.socialLinkEditPostId='editing';assert.throws(()=>draft('Museu',sourceUrl));assert.equal(opened,1);
console.log('PASS: private accounts, original dates, pagination/resume, deduplication, Meta restrictions, manual handoff boundary and isolated cron.');
