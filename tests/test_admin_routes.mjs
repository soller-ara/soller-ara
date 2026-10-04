import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
const source=(await fs.readFile('worker/admin-worker.js','utf8')).replace('export default {','const worker = {');
const c=vm.createContext({crypto:webcrypto,TextEncoder,TextDecoder,Request,Response,URL,AbortSignal,btoa,atob,console});
vm.runInContext(source,c);
c.env={SESSION_SECRET:'test-only-session-secret',ADMIN_PASSWORD:'test-only-password',GITHUB_TOKEN:'test-only-token'};
let calls=[];
c.fetch=async(url,opts)=>{calls.push({url,opts});return new Response(null,{status:204})};
async function request(path,body,token='',ip='test-client') {
 c.req=new Request('https://test.invalid'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','CF-Connecting-IP':ip,...(token?{Authorization:'Bearer '+token}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const response=await vm.runInContext('worker.fetch(req,env)',c);
 return {status:response.status,body:await response.json(),headers:response.headers};
}
for (const path of ['/api/status','/api/check','/api/publish','/api/edit','/api/moderate','/api/source','/api/social-settings']) {
 assert.equal((await request(path,path.endsWith('status')||path.endsWith('check')?undefined:{})).status,401);
}
assert.equal(calls.length,0);
assert.equal((await request('/api/login',{password:'wrong'})).status,401);
let login=await request('/api/login',{password:'test-only-password'},'','successful-client');
assert.equal(login.status,200);
const token=login.body.token;assert.ok(token);
assert.equal((await request('/api/publish',{},token+'bad')).status,401);
assert.equal((await request('/api/publish',{},token)).status,400);
assert.equal((await request('/api/publish',{title:'A',body:'B',original_url:'javascript:alert(1)'},token)).status,400);
assert.equal((await request('/api/publish',{title:'A',body:'B',content_type:'event_poster',image_url:'https://example.test/poster.jpg',image_authorized:false},token)).status,400);
assert.equal((await request('/api/publish',{original_url:'https://www.facebook.com/story.php?story_fbid=1&id=2',instagram:true},token)).status,400);
assert.equal(calls.length,0);
assert.equal((await request('/api/publish',{title:'',body:'',original_url:'https://www.facebook.com/story.php?story_fbid=1&id=2',source_name:'Ajuntament de Deià',category:'agenda',show_in_now:false},token)).status,202);
let dispatch=JSON.parse(calls.at(-1).opts.body);
assert.equal(dispatch.inputs.show_in_now,false);assert.equal(dispatch.inputs.content_type,'social_link');assert.equal(dispatch.inputs.title,'');
assert.ok(calls.at(-1).url.endsWith('/actions/workflows/publish-own-content.yml/dispatches'));
assert.equal((await request('/api/edit',{post_id:'test',title:'Title',body:'Body',content_type:'event_poster',image_url:'https://example.test/poster.jpg',image_authorized:true,category:'social',show_in_now:false},token)).status,202);
dispatch=JSON.parse(calls.at(-1).opts.body);assert.equal(dispatch.inputs.content_type,'event_poster');assert.equal(dispatch.inputs.category,'social');assert.equal(dispatch.inputs.show_in_now,false);
assert.equal(login.headers.get('Cache-Control'),'no-store');
for(let i=0;i<5;i++)assert.equal((await request('/api/login',{password:'wrong'},'','blocked-client')).status,401);
assert.equal((await request('/api/login',{password:'test-only-password'},'','blocked-client')).status,429);
assert.ok(!JSON.stringify(login.body).includes('test-only-password'));
console.log('PASS: private routes require signed sessions; login and rate limit; URL and poster validation; blank references; Ara and content type reach workflows. No external requests.');
