import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
const source=await fs.readFile('admin/sources-v2.js','utf8');
const collect=source.slice(source.indexOf('  async function collect()'),source.indexOf('  async function waitFor('));
async function scenario(result,states) {
 const button={disabled:false,textContent:'Buscar y publicar ahora'};
 const notice={textContent:''};
 const calls=[];
 let loads=0;
 const c=vm.createContext({document:{getElementById:id=>id==='collectSourcesButton'?button:notice},
  setTimeout:callback=>callback(),api:async(path,options)=>{
   calls.push({path,options});
   if(options?.method==='POST')return result;
   const state=states.shift();if(state instanceof Error)throw state;
   return state||{run:null};
  },load:async()=>{loads++}});
 vm.runInContext('let collectionRunning=false;'+collect,c);
 await vm.runInContext('collect()',c);
 assert.equal(button.disabled,false);assert.equal(button.textContent,'Buscar y publicar ahora');
 return {button,notice,calls,loads};
}
let r=await scenario({already_running:false,previous_run_id:1},[
 {run:{id:1,status:'completed',conclusion:'success'}},
 {run:{id:2,status:'queued'}},
 {run:{id:2,status:'completed',conclusion:'success'}}]);
assert.equal(r.loads,1);assert.ok(r.notice.textContent.includes('Revisión terminada'));
assert.equal(r.calls.filter(c=>c.options?.method==='POST').length,1);
assert.equal(r.calls.at(-1).path,'/api/collect?run_id=2');
r=await scenario({already_running:true,run:{id:3,status:'in_progress'}},[
 {run:{id:3,status:'completed',conclusion:'failure'}}]);
assert.ok(r.notice.textContent.includes('incidencia'));assert.equal(r.calls.at(-1).path,'/api/collect?run_id=3');
r=await scenario({already_running:false,previous_run_id:1},[new Error('Provider unavailable')]);
assert.equal(r.notice.textContent,'Provider unavailable');assert.equal(r.loads,0);
console.log('PASS: manual source button waits for its actual run, tracks queued and active runs, reports failures and restores controls.');
