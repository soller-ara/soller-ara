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
c.window.SOLLER_ARA_READ_JSON=async(path)=>{paths.push(path);return path==='data/posts.json' ? {posts:[],saved:path} : {hidden_post_ids:[],saved:path}};
const state=await run('readRepositoryState()');
assert.equal(state.posts.saved,'data/posts.json');
assert.deepEqual(paths.sort(),['data/moderation.json','data/posts.json']);
console.log('PASS: administration reads the saved repository state during deployment.');

c.post={id:'aemet',source:'AEMET',source_id:'aemet',source_type:'official',category:'alerts',
 title:'Aviso de lluvias',summary:'Horario original del aviso',published_at:new Date(now-3600000).toISOString(),
 url:'https://www.aemet.es/original',alert_status:'active',alert_valid_until:new Date(now-60000).toISOString()};
assert.equal(run('alertStatus(post)'),'expired');
assert.equal(run('isFreshPost(post)'),false);
assert.equal(run('isNowPost(post)'),true);
for (const [lang,label] of [['es','Aviso finalizado'],['ca','Avís finalitzat'],['en','Expired alert']]) {
 run(`currentLanguage="${lang}";posts=[post];currentCategory="now";renderFeed()`);
 assert.ok(nodes.get('feed').innerHTML.includes(label));
 assert.ok(nodes.get('feed').innerHTML.includes('Aviso de lluvias'));
 assert.ok(!nodes.get('feed').innerHTML.includes('class="new-badge"'));
}
console.log('PASS: expired AEMET alerts retain their original date and Ara visibility, show expiry in all languages and lose the New badge.');

vm.runInContext(admin.slice(admin.indexOf('  function manualInstagramStatus('),admin.indexOf('  function renderSocialLinkPosts(')),c);
run('statusPayload={socialLog:{entries:[{post_id:"manual",platform:"instagram",status:"deferred",retry_requested:true}]}}');
c.post={id:'manual'};
assert.ok(run('manualInstagramStatus(post)').includes('reintento automático'));
run('statusPayload.socialLog.entries.push({post_id:"manual",platform:"instagram",status:"publishing"})');
assert.ok(run('manualInstagramStatus(post)').includes('pendiente de confirmación'));
run('statusPayload.socialLog.entries.push({post_id:"manual",platform:"instagram",status:"error"})');
assert.ok(run('manualInstagramStatus(post)').includes('pendiente de confirmación'));
run('statusPayload.socialLog.entries.push({post_id:"manual",platform:"instagram",status:"verification_required"})');
assert.ok(run('manualInstagramStatus(post)').includes('evitar un envío duplicado'));
run('statusPayload.socialLog.entries.push({post_id:"manual",platform:"instagram",status:"success"})');
assert.equal(run('manualInstagramStatus(post)'),'Instagram: publicado');
run('statusPayload.socialLog.entries.push({post_id:"manual",platform:"instagram",status:"error"})');
assert.equal(run('manualInstagramStatus(post)'),'Instagram: publicado');
console.log('PASS: manual Instagram links distinguish pending verification, avoid offering blind retries and preserve confirmed success.');

vm.runInContext(auto.slice(auto.indexOf('  function isAlreadySent('),auto.indexOf('  function nextPreview(')),c);
c.state={posts:[{id:'new-title',source_id:'source',url:'https://example.test/same-article'}],
 entries:[{post_id:'old-title',source_id:'source',post_url:'https://example.test/same-article',platform:'facebook',status:'success'}]};
assert.equal(run('isAlreadySent("new-title","facebook")'),true);
assert.equal(run('isAlreadySent("new-title","instagram")'),false);
console.log('PASS: social preview does not propose resending a source URL after a headline edit.');

vm.runInContext(auto.slice(auto.indexOf('  function nextPreview('),auto.indexOf('  function safeSummary(')),c);
c.rules={source:{facebook:true,instagram:true}};
c.state={config:{enabled:true,platforms:{facebook:true,instagram:true},max_age_hours:6},
 sources:[{id:'source',enabled:true}], entries:[], cooldowns:{instagram_until:new Date(now+3600000).toISOString()},
 posts:[{id:'weather',source_id:'source',source_type:'official',published_at:new Date(now-60000).toISOString(),
   alert_status:'active',alert_valid_until:new Date(now+3600000).toISOString()}]};
assert.equal(run('nextPreview(rules)?.id'),'weather');
assert.deepEqual(Array.from(run('previewPlatforms(state.posts[0],rules)')),['facebook']);
run('rules.source.facebook=false');
assert.equal(run('nextPreview(rules)'),null);
run('rules.source.facebook=true');
for(const status of ['unverified','archived','expired']) {
 c.state.posts[0].alert_status=status;
 assert.equal(run('nextPreview(rules)'),null);
}
c.state.posts[0].alert_status='active';c.state.posts[0].alert_valid_until=new Date(now-1000).toISOString();
assert.equal(run('nextPreview(rules)'),null);
console.log('PASS: automatic preview respects Instagram cooldowns while preserving Facebook and excludes expired, archived or unverified warnings.');

vm.runInContext(auto.slice(auto.indexOf('  function safeSummary('),auto.indexOf('  function sourceControls(')),c);
c.categoryNames={alerts:'Avisos'};
run('state.posts[0].alert_valid_until="";state.posts[0].url="javascript:alert(1)";state.posts[0].title="<img src=x>";currentRules=()=>rules;renderPreview()');
assert.ok(!nodes.get('socialPreview').innerHTML.includes('href="javascript:'));
assert.ok(nodes.get('socialPreview').innerHTML.includes('&lt;img'));
console.log('PASS: automatic previews escape headlines and never create executable links.');

// The corrected Facebook group permalink is recognized without altering the saved URL.
c.post={id:'beinetti',source_type:'own',original_url:'https://www.facebook.com/groups/2168168493412761/posts/4668467036716215/?hpir=1',title:'Personal per a tenda Beinetti'};
assert.equal(run('getEmbeddablePlatform(post.original_url)'),'facebook');
assert.ok(run('renderManualOriginalEmbed(post)').includes(encodeURIComponent(c.post.original_url)));

vm.runInContext(admin.slice(admin.indexOf('  function ownPostMatches('),admin.indexOf('  async function waitForOwnEdit(')),c);
c.expected={source_name:'Sóller, bolsa de trabajo',original_url:c.post.original_url,title:c.post.title,
 body:'Oferta de feina a Sóller.',category:'services',language:'ca',show_in_now:true,content_type:'social_link'};
const saved={...c.post,source:c.expected.source_name,summary:c.expected.body,category:'services',language:'ca',show_in_now:true,content_type:'social_link'};
c.previousIds=new Set(['already-saved']);c.message={};
let reads=0;let renders=0;
c.setTimeout=fn=>fn();
c.setMessage=(element,text)=>{element.textContent=text};
c.renderPosts=()=>{renders++};
const readSaved=async()=>{
 reads++;
 if (reads===2) throw new Error('Temporary read failure');
 const posts=[{...saved,id:'already-saved'}, {...saved,id:'foreign-source',source_type:'social'}];
 if(reads>=4) posts.push(saved);
 return {posts:{posts},moderation:{hidden_post_ids:[]}};
};
c.window.SOLLER_ARA_READ_JSON=async path=>{
 if(path==='data/posts.json') return (await readSaved()).posts;
 return {hidden_post_ids:[]};
};
assert.equal(await run('waitForOwnPublication(expected,previousIds,message)'),true);
assert.equal(reads,4);assert.equal(renders,1);
assert.ok(run('statusPayload.posts.posts.some(post=>post.id==="beinetti")'));

// A request accepted by the backend is not a confirmed save.
reads=0;renders=0;
c.window.SOLLER_ARA_READ_JSON=async path=>path==='data/posts.json'
 ? {posts:[{...saved,id:'already-saved'}]} : {hidden_post_ids:[]};
assert.equal(await run('waitForOwnPublication(expected,previousIds,message)'),false);
assert.equal(renders,0);
assert.ok(c.message.textContent.includes('No vuelvas a enviarla'));
assert.equal(run('ownPostMatches({...statusPayload.posts.posts.at(-1),original_url:"https://example.test/wrong"},expected)'),false);

vm.runInContext(admin.slice(admin.indexOf('  function renderSocialLinkPosts('),admin.indexOf('  function renderHidden(')),c);
c.socialLinkList=node('socialLinkList');
run('statusPayload={posts:{posts:[statusPayload.posts.posts.at(-1)]},socialLog:{entries:[]}};renderSocialLinkPosts()');
assert.ok(c.socialLinkList.innerHTML.includes('Personal per a tenda Beinetti'));
assert.ok(c.socialLinkList.innerHTML.includes('data-social-link-edit-id="beinetti"'));
console.log('PASS: corrected Facebook permalink, delayed save confirmation, transient read failure, existing-post exclusion, timeout without false success and editable social-link gallery.');
