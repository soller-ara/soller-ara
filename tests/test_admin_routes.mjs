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
for (const path of ['/api/status','/api/check','/api/publish','/api/edit','/api/moderate','/api/source','/api/social-settings','/api/collect']) {
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

const health=await request('/health');
assert.ok(health.body.capabilities.includes('manual_collection'));
let workflowRuns=[{id:1,status:'completed',conclusion:'success',html_url:'https://github.com/soller-ara/soller-ara/actions/runs/1'}];
calls=[];
c.fetch=async(url,opts)=>{
 calls.push({url,opts});
 if(url.includes('/runs?'))return new Response(JSON.stringify({workflow_runs:workflowRuns}),{status:200});
 return new Response(null,{status:204});
};
let collection=await request('/api/collect',{},token);
assert.equal(collection.status,202);assert.equal(collection.body.already_running,false);
assert.equal(collection.body.previous_run_id,1);
assert.ok(calls.at(-1).url.endsWith('/actions/workflows/update-sources.yml/dispatches'));
dispatch=JSON.parse(calls.at(-1).opts.body);
assert.equal(dispatch.ref,'main');assert.deepEqual(dispatch.inputs,{});
workflowRuns=[{id:2,status:'in_progress',conclusion:null},...workflowRuns];
calls=[];collection=await request('/api/collect',{},token);
assert.equal(collection.status,202);assert.equal(collection.body.already_running,true);
assert.equal(collection.body.run.id,2);assert.equal(calls.length,1);
assert.equal((await request('/api/collect',undefined,token)).body.run.status,'in_progress');
workflowRuns[0].status='completed';workflowRuns[0].conclusion='success';
assert.equal((await request('/api/collect',undefined,token)).body.run.conclusion,'success');
c.fetch=async(url,opts)=>{
 calls.push({url,opts});
 return new Response(JSON.stringify(workflowRuns[0]),{status:200});
};
assert.equal((await request('/api/collect?run_id=2',undefined,token)).body.run.id,2);
assert.ok(calls.at(-1).url.endsWith('/actions/runs/2'));
assert.equal((await request('/api/collect?run_id=invalid',undefined,token)).status,400);
c.fetch=async()=>new Response('Provider failure',{status:503});
assert.equal((await request('/api/collect',{},token)).status,503);
console.log('PASS: authenticated manual source refresh dispatches the existing workflow, reuses active runs, reports completion and stops on provider failures.');
