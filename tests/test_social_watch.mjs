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
let failArchive=false;
const db={prepare:q=>new Stmt(q),async batch(ss){
  if(failArchive&&ss.some(s=>s.q.includes('INSERT INTO watch_posts')))throw Error('D1_ERROR: archive failed: SQLITE_ERROR; offline-only');
  sql.exec('BEGIN');try{const out=ss.map(s=>s.exec());sql.exec('COMMIT');return out;}catch(e){sql.exec('ROLLBACK');throw e;}}};
const workerSource=(await fs.readFile('worker/admin-worker.js','utf8')).replace('export default {','const worker = {');
const ui=await fs.readFile('admin/social-watch.js','utf8');
const now=Date.parse('2026-11-25T16:30:00Z');
class Clock extends Date{static now(){return now;}}
const calls=[],env={SOCIAL_WATCH_DB:db,SESSION_SECRET:'isolated-test-session',WATCH_META_READ_TOKEN:'offline-only',WATCH_INSTAGRAM_ID:'123'};
let reply;
const diagnosticLogs=[];
const context=vm.createContext({URL,URLSearchParams,Date:Clock,Intl,Request,Response,Headers,AbortSignal,TextEncoder,TextDecoder,crypto:webcrypto,btoa,atob,env,console:{...console,warn:value=>diagnosticLogs.push(String(value))},fetch:async(url,opts)=>{
  assert.equal(opts.method,'GET');assert.equal(opts.headers.Authorization,'Bearer offline-only');
  assert.equal(opts.redirect,'manual','Workers rejects redirect:error; credentials must never follow redirects');const u=new URL(url);
  assert.equal(u.host,'graph.facebook.com');assert.equal(u.searchParams.has('access_token'),false);calls.push(u);const body=reply(u);return body instanceof Response?body:new Response(JSON.stringify(body),{status:body.error?400:200});
}});
vm.runInContext(workerSource,context); vm.runInContext(ui,context);
const run=(expr)=>vm.runInContext(expr,context);
const token=await run('createSession(env.SESSION_SECRET)');
const path='https://worker.test/api/social-watch?from=2026-11-25&to=2026-11-25';
async function request(body,options={}){const req=new Request(options.url||path,{method:body?'POST':'GET',headers:options.noAuth?{}:{Authorization:'Bearer '+token},...(body?{body:JSON.stringify(body)}:{})});context.req=req;const response=await run('worker.fetch(req,env)');return [response.status,await response.json()];}
assert.equal((await request(undefined,{noAuth:true}))[0],401);
assert.deepEqual((await request())[1].posts,[]);
const api=run('globalThis.socialWatchTest'), plain=x=>JSON.parse(JSON.stringify(x));
assert.equal(api.previewUrl('https://www.instagram.com/reel/Example_27/?igsh=tracking','instagram'),
  'https://www.instagram.com/p/Example_27/embed/captioned/');
assert.equal(api.previewUrl('https://www.instagram.com/p/Example_28/','instagram'),
  'https://www.instagram.com/p/Example_28/embed/captioned/');
const fbPreview=new URL(api.previewUrl('https://www.facebook.com/story.php?id=12&story_fbid=34&access_token=discard','facebook'));
assert.equal(fbPreview.origin,'https://www.facebook.com');assert.equal(fbPreview.pathname,'/plugins/post.php');
assert.equal(fbPreview.searchParams.get('href'),'https://www.facebook.com/story.php?story_fbid=34&id=12');
assert.ok(!fbPreview.href.includes('discard'));
assert.equal(new URL(api.previewUrl('https://www.facebook.com/local/videos/123','facebook')).pathname,'/plugins/video.php');
for(const [url,network] of [
  ['javascript:alert(1)','instagram'],['http://www.instagram.com/p/ABC/','instagram'],
  ['https://www.instagram.com.evil.test/p/ABC/','instagram'],['https://www.instagram.com:444/p/ABC/','instagram'],
  ['https://person:secret@www.instagram.com/p/ABC/','instagram'],['https://www.instagram.com/ajuntament_de_soller/','instagram'],
  ['https://www.instagram.com/p/ABC/embed/','instagram'],['https://www.instagram.com/p/ABC/','facebook'],
  ['https://www.facebook.com/redirect?next=https://evil.test/','facebook'],['https://www.facebook.com/profile.php?id=12','facebook'],
  ['https://www.facebook.com/story.php?id=12','facebook'],['https://www.facebook.com/people/','facebook']
])assert.equal(api.previewUrl(url,network),'','Only verified post paths can open inside Administration');
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
  // Business Discovery returns cursors without paging.next; a final cursor may lead to an empty page.
  const n=++pages,media=n===1?{data:[post(1,'2026-11-24T23:30:00Z')],paging:{cursors:{after:'page_2'}}}
    :n===2?{data:[post(2,'2026-11-24T13:00:00Z')],paging:{cursors:{after:'page_3'}}}
    :n===3?{data:[post(1,'2026-11-24T23:30:00Z'),post(3,'2026-11-25T10:00:00Z','')],paging:{cursors:{after:'page_4'}}}
    :{data:[],paging:{cursors:{after:'page_4'}}};
  return {business_discovery:{username:'LOCAL_MUSEU',media}};};
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
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>({error:{code:110,error_subcode:2207013,message:'Never echo the secret offline-only'}});
assert.equal((await request({action:'check',id}))[1].state,'unavailable');
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>({error:{code:1,error_subcode:42,message:'Never echo the secret offline-only'}});
let failure=await request({action:'check',id});assert.equal(failure[0],503);
assert.equal(failure[1].diagnostic.stage,'meta');assert.equal(failure[1].diagnostic.meta_code,1);
assert.equal(failure[1].diagnostic.http_status,400);
assert.equal(failure[1].diagnostic.meta_subcode,42);assert.match(failure[1].error,/Meta/);
assert.ok(!JSON.stringify(failure[1]).includes('offline-only'));
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>new Response('',{status:302,headers:{Location:'https://other.invalid/never-follow?access_token=offline-only'}});
const callsBeforeRedirect=calls.length;failure=await request({action:'check',id});
assert.equal(failure[0],503);assert.equal(failure[1].diagnostic.reason,'redirect');
assert.equal(failure[1].diagnostic.http_status,302);assert.equal(calls.length,callsBeforeRedirect+1);
assert.ok(!JSON.stringify(failure[1]).includes('offline-only'));assert.ok(!JSON.stringify(failure[1]).includes('other.invalid'));
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>{const e=Error('Never echo offline-only');e.name='TimeoutError';throw e;};
failure=await request({action:'check',id});assert.equal(failure[0],503);
assert.equal(failure[1].diagnostic.stage,'meta');assert.equal(failure[1].diagnostic.reason,'timeout');
assert.ok(!JSON.stringify(failure[1]).includes('offline-only'));
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>{throw new TypeError('Invalid header value offline-only');};
failure=await request({action:'check',id});assert.equal(failure[0],503);
assert.equal(failure[1].diagnostic.reason,'request_headers');assert.match(failure[1].error,/token/);
assert.ok(!JSON.stringify(failure[1]).includes('offline-only'));
sql.prepare('UPDATE watch_accounts SET attempted=0,due=0').run();
reply=()=>({business_discovery:{username:'local_museu',media:{data:[post(4,'2026-11-25T11:00:00Z')]}}});
failArchive=true;failure=await request({action:'check',id});failArchive=false;
assert.equal(failure[0],503);assert.equal(failure[1].diagnostic.stage,'archive');
assert.equal(failure[1].diagnostic.db_code,'SQLITE_ERROR');assert.match(failure[1].error,/guardar/);
assert.ok(!JSON.stringify(failure[1]).includes('offline-only'));
data=(await request())[1];assert.equal(data.posts.length,2);assert.equal(data.accounts[0].status,'temporary');
assert.equal(sql.prepare('SELECT lease FROM watch_accounts WHERE id=?').get(id).lease,'');
assert.equal(diagnosticLogs.length,5);assert.ok(diagnosticLogs.every(line=>!line.includes('offline-only')));
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
const formElements=Object.assign([], {source_name:input(),original_url:input(),facebook:input('checkbox'),instagram:input('checkbox'),title:input(),category:input()});
formElements.push(...Object.values(formElements));let opened=0,reset=0;
const fixture={window:{confirm:()=>false},URL,socialLinkEditPostId:'',socialLinkSubmitButton:{disabled:false},socialLinkForm:{elements:formElements},
  resetSocialLinkEditMode(){reset++;for(const field of formElements){field.value=field.defaultValue;field.checked=field.defaultChecked;}},openModule(v){assert.equal(v,'social-links');opened++;},socialLinkMessage:{},socialLinkHeading:{textContent:'Enlace de una red social'},setMessage(){},
  fetch(){throw Error('handoff must not call any service');}};
vm.runInNewContext(bridge,fixture);const draft=fixture.window.SOLLER_ARA_WATCH_DRAFT,sourceUrl='https://www.instagram.com/p/P1/';
formElements.title.value='Borrador existente';assert.equal(draft('Museu',sourceUrl),false);assert.equal(reset,0);
fixture.window.confirm=()=>true;assert.equal(draft('Museu',sourceUrl),true);assert.equal(formElements.original_url.value,sourceUrl);
assert.equal(formElements.source_name.value,'Museu');assert.equal(formElements.instagram.checked,false);assert.equal(formElements.facebook.checked,false);assert.equal(opened,1);
fixture.socialLinkEditPostId='editing';assert.throws(()=>draft('Museu',sourceUrl));assert.equal(opened,1);
const manual=fixture.window.SOLLER_ARA_SOURCE_DRAFT;
assert.throws(()=>manual('Biblioteca','agenda'),'A manual source cannot replace an edit');
fixture.socialLinkEditPostId='';fixture.socialLinkSubmitButton.disabled=true;
assert.throws(()=>manual('Biblioteca','agenda'),'An ongoing submission cannot be replaced');
fixture.socialLinkSubmitButton.disabled=false;fixture.window.confirm=()=>false;
formElements.title.value='Borrador que conservar';const beforeManualReset=reset;
assert.equal(manual('Biblioteca','agenda'),false);assert.equal(reset,beforeManualReset);
assert.equal(formElements.title.value,'Borrador que conservar');assert.equal(formElements.original_url.value,sourceUrl);
fixture.window.confirm=()=>true;formElements.facebook.checked=formElements.instagram.checked=true;
assert.equal(manual('CEIP Es Fossaret · Sóller','news'),true);
assert.equal(formElements.original_url.value,'','A catalogue homepage is never passed off as the chosen publication');
assert.equal(formElements.source_name.value,'CEIP Es Fossaret · Sóller');assert.equal(formElements.category.value,'news');
assert.equal(formElements.facebook.checked,false);assert.equal(formElements.instagram.checked,false);
assert.equal(fixture.socialLinkHeading.textContent,'Enlace de una fuente');
console.log('PASS: private accounts, original dates, pagination/resume, deduplication, Meta restrictions, manual handoff boundary and isolated cron.');
