import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';
const source=await fs.readFile('app.js','utf8');
const nodes=new Map();
function node(id) { if (!nodes.has(id)) nodes.set(id,{innerHTML:'',value:'',textContent:'',dataset:{},addEventListener(){},querySelectorAll(){return []}}); return nodes.get(id); }
function create(storage) {
 const context=vm.createContext({URL,Intl,Date,console,localStorage:storage,
  document:{getElementById:node,querySelectorAll(){return []},querySelector(){return null}},
  window:{},navigator:{}});
 vm.runInContext(source.slice(0,source.lastIndexOf('sourceSelect.addEventListener')),context);
 return context;
}
let c=create({getItem(){return 'invalid-language'}});
assert.equal(vm.runInContext('currentLanguage',c),'ca');
c=create({getItem(){throw new Error('Storage blocked')}});
assert.equal(vm.runInContext('currentLanguage',c),'ca');
c=create({getItem(){return 'es'}});
assert.equal(vm.runInContext('currentLanguage',c),'es');
const run=(code)=>vm.runInContext(code,c);
const now=Date.now();
c.post={id:'audit',source:'<script>bad</script>',category:'agenda',source_type:'own',
 published_at:new Date(now-3600000).toISOString(),show_in_now:false,title:'Title',summary:'Body',
 url:'javascript:alert(1)',original_url:'data:text/html,bad',related_sources:[{url:'javascript:alert(2)',source:'Related'}]};
assert.equal(run('isNowPost(post)'),false);
assert.equal(run('isFreshPost(post)'),true);
for (const [age,fresh,current] of [[-1,false,false],[23,true,true],[25,false,true],[167,false,true],[169,false,false]]) {
 c.post.published_at=new Date(now-age*3600000).toISOString();c.post.show_in_now=true;
 assert.equal(run('isFreshPost(post)'),fresh);
 assert.equal(run('isNowPost(post)'),current);
}
c.post.published_at='not-a-date';assert.equal(run('isFreshPost(post)'),false);assert.equal(run('isNowPost(post)'),false);
c.post.published_at=new Date(now).toISOString();c.post.show_in_now=false;
run('posts=[post];currentCategory="agenda";renderFeed()');
assert.ok(nodes.get('feed').innerHTML.includes('Title'));
assert.ok(!nodes.get('feed').innerHTML.includes('href="javascript:'));
assert.ok(!nodes.get('feed').innerHTML.includes('href="data:'));
assert.ok(nodes.get('feed').innerHTML.includes('&lt;script&gt;'));
run('currentCategory="now";renderFeed()');assert.ok(!nodes.get('feed').innerHTML.includes('Title'));
assert.equal(run('safeLinkUrl("https://example.test/a?q=1")'),'https://example.test/a?q=1');
assert.equal(run('safeLinkUrl("https://user:password@example.test/")'),'');
assert.equal(run('getEmbeddablePlatform("javascript://facebook.com/posts/1")'),'');
assert.equal(run('getEmbeddablePlatform("https://www.facebook.com/story.php?story_fbid=1&id=2")'),'facebook');
c.post.original_url='https://www.facebook.com/story.php?story_fbid=1&id=2';
assert.ok(run('renderManualOriginalEmbed(post)').includes('plugins/post.php'));
c.post.content_type='event_poster';c.post.media_url='https://example.test/poster.jpg';c.post.media_type='image';c.post.image_allowed=true;
assert.ok(run('renderAuthorizedPoster(post)').includes('poster.jpg'));
assert.equal(run('renderManualOriginalEmbed(post)'),'');
const auto=await fs.readFile('admin/social-auto-v1.js','utf8');
vm.runInContext('const esc = value => String(value ?? "").replaceAll("<", "&lt;");'+auto.slice(auto.indexOf('  function row('),auto.indexOf('  function currentRules(')),c);
c.config={enabled:true,platforms:{facebook:true,instagram:true},sources:{one:{facebook:true,instagram:true}}};
c.entries=[{mode:'automatic_collected',platform:'instagram',status:'success',recorded_at:new Date(now-10000).toISOString()}];
c.cooldowns={instagram_until:new Date(now+3600000).toISOString()};
assert.ok(run('platformRow(config,entries,"instagram",true,cooldowns)').includes('EN PAUSA · META'));
assert.ok(!run('platformRow(config,entries,"facebook",true,cooldowns)').includes('EN PAUSA · META'));
console.log('PASS: storage fallback, languages, Ara opt-out and date windows, safe links, source escaping, blank-title Facebook embed, authorized poster, Instagram cooldown display.');

const admin=await fs.readFile('admin/admin.js','utf8');
vm.runInContext(admin.slice(admin.indexOf('  async function readRepositoryState()'),admin.indexOf('  async function mergePublicState(')),c);
const paths=[];
c.window.SOLLER_ARA_READ_JSON=async(path)=>{paths.push(path);return {saved:path}};
const state=await run('readRepositoryState()');
assert.equal(state.posts.saved,'data/posts.json');
assert.deepEqual(paths.sort(),['data/moderation.json','data/posts.json']);
console.log('PASS: administration reads the saved repository state during deployment.');
