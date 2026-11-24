import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import vm from 'node:vm';

const guide = await fs.readFile('admin/editorial-guide.js', 'utf8');
const admin = await fs.readFile('admin/admin.js', 'utf8');
const defaults = {title:'',body:'',source_name:'',original_url:'',category:'politics',language:'ca',
  content_type:'social_link',image_url:'',image_authorized:false,show_in_now:true,instagram:false,facebook:false};
const nodes = new Map();
class Node {
  constructor(id='') {
    this.id=id;this.textContent='';this.children=[];this.listeners={};this.hidden=false;this.disabled=false;
    this.replacements=0;this.classList={toggle(){},add(){},remove(){}};
  }
  addEventListener(type, listener) { this.listeners[type]=listener; }
  replaceChildren(...children) { this.children=children;this.replacements++; }
  querySelector(selector) {
    const name=selector.match(/name="([^"]+)"/)?.[1];
    return name ? this.elements[name] : node(this.id+selector);
  }
  querySelectorAll() { return []; }
  get elements() {
    if (!this.fields) this.fields=Object.fromEntries(Object.entries(defaults).map(([key,value])=>[key,{
      value:typeof value==='string'?value:'',checked:value===true,required:false,maxLength:key==='title'?180:-1,
      disabled:false,addEventListener(){},
    }]));
    return this.fields;
  }
  reset() {
    this.listeners.reset?.(); // Browsers emit reset before restoring the field values.
    for(const [key,value] of Object.entries(defaults)) {
      this.elements[key].value=typeof value==='string'?value:'';
      this.elements[key].checked=value===true;
    }
  }
}
function node(id) { if(!nodes.has(id))nodes.set(id,new Node(id));return nodes.get(id); }
const form=node('socialLinkForm');
let confirmations=0,requests=0;
const window={SOLLER_ARA_ADMIN_API:'https://admin.test',scrollTo(){}};
const context=vm.createContext({window,URL,Intl,Date,Headers,console,queueMicrotask,
  document:{getElementById:node,querySelectorAll:()=>[],createElement:tag=>{assert.equal(tag,'li');return new Node();}},
  sessionStorage:{getItem:()=>'',setItem(){},removeItem(){}},
  FormData:class { constructor(form){this.form=form;} get(key){const field=this.form.elements[key];
    return typeof defaults[key]==='boolean' ? field.checked?'on':null : field.value;} },
  confirm:()=>{confirmations++;return false;},
  fetch:()=>{requests++;throw new Error('No real requests allowed');},
});
vm.runInContext(guide,context);
const snapshot=()=>JSON.stringify(form.elements);
const notes=()=>node('socialTextSuggestions').children.map(item=>item.textContent).join(' ');
const notify=()=>form.listeners.input();

assert.match(notes(),/pueden quedar vacíos/);
assert.equal(node('socialTitleCount').textContent,'Titular: 0/180 caracteres');
const before=snapshot();notify();assert.equal(snapshot(),before);
assert.equal(node('socialLinkSubmitButton').disabled,false);

form.elements.title.value='Acte';
form.elements.body.value='ACTE';
form.elements.original_url.value='https://example.test/post';
const authored=snapshot();notify();
assert.match(notes(),/qué ocurre y dónde/);assert.match(notes(),/complemente el titular/);
assert.match(notes(),/cuenta o entidad original/);
assert.equal(snapshot(),authored,'Advice must not rewrite text, requirements, destinations or Ara opt-out');
const stable=node('socialTextSuggestions').replacements;
form.elements.title.value='Actes';form.elements.body.value='ACTES';notify();
assert.equal(node('socialTextSuggestions').replacements,stable,'Unchanged advice must not be announced again on each keystroke');
assert.equal(node('socialTitleCount').textContent,'Titular: 5/180 caracteres');

form.elements.title.value='https://example.test/a';form.elements.body.value='https://example.test/b';notify();
assert.match(notes(),/dirección/);assert.match(notes(),/tus palabras/);
form.elements.title.value='<img src=x onerror=alert(1)>';form.elements.body.value='Text propi amb salts\nde línia';
const originalText=snapshot();notify();assert.equal(snapshot(),originalText);
assert.ok(node('socialTextSuggestions').children.every(item=>!item.textContent.includes('<img')));

const beforeResetCount=node('socialTitleCount').textContent;
form.reset();assert.equal(node('socialTitleCount').textContent,beforeResetCount,'Reset notification runs before the browser clears fields');
await Promise.resolve();
assert.equal(node('socialTitleCount').textContent,'Titular: 0/180 caracteres');
assert.match(notes(),/pueden quedar vacíos/);

// Exercise the real administration handlers with the helper loaded, without a request or publication.
vm.runInContext(admin.replace(/\}\)\(\);\s*$/, `
  window.test={startSocialLinkEdit,setState(value){statusPayload=value;}};
})();`),context);
form.elements.original_url.value='https://example.test/post';
form.elements.show_in_now.checked=false;
await form.listeners.submit({preventDefault(){}});
assert.equal(confirmations,1,'Web-only publication must still accept empty title and summary');
assert.equal(requests,0);
form.elements.instagram.checked=true;form.listeners.change();
assert.match(notes(),/Instagram necesitas/);
assert.equal(form.elements.title.required,false);assert.equal(form.elements.body.required,false);
assert.equal(node('socialLinkSubmitButton').disabled,false);
await form.listeners.submit({preventDefault(){}});
assert.equal(confirmations,1,'Existing Instagram validation must still reject missing text');
assert.match(node('socialLinkMessage').textContent,/Instagram añade un titular y resumen/);
form.elements.title.value='Acte';form.elements.body.value='Acte';notify();
await form.listeners.submit({preventDefault(){}});
assert.equal(confirmations,2,'Advisory warnings must not block publication of valid input');
assert.equal(form.elements.show_in_now.checked,false);

const saved={id:'saved',source_type:'own',original_url:'https://example.test/saved',
  title:'Acte de barri a Sóller',summary:'Resum propi de la publicació original.',source:'Entitat local',
  category:'agenda',language:'ca',show_in_now:false,content_type:'social_link'};
window.test.setState({posts:{posts:[saved]}});
window.test.startSocialLinkEdit('saved');
assert.equal(node('socialTitleCount').textContent,`Titular: ${saved.title.length}/180 caracteres`);
assert.equal(node('socialBodyCount').textContent,`Resumen: ${saved.summary.length} caracteres`);
assert.equal(form.elements.instagram.checked,false);assert.equal(form.elements.instagram.disabled,true);
assert.equal(form.elements.show_in_now.checked,false);
node('cancelSocialLinkEditButton').listeners.click();await Promise.resolve();
assert.equal(node('socialTitleCount').textContent,'Titular: 0/180 caracteres');
assert.equal(node('socialBodyCount').textContent,'Resumen: 0 caracteres');
assert.equal(form.elements.instagram.disabled,false);
assert.equal(requests,0,'Typing, guidance, edits and reset must not call external services');
console.log('PASS: optional advice and counters preserve authored text, requirements, Ara and destinations; unchanged advice is quiet; real web/Instagram validation, edit loading and reset remain intact. No external requests.');

const available = [
  {id:'permitted',url:'https://example.test/allowed/?keep=one',source:'Entitat local',source_type:'official',
    title:'Una actuació de servei a Sóller',summary:'El servei obre a les 14.30 h. Es manté fins al 27/11. Una tercera frase.',
    content_policy:'short_factual_excerpt',language:'ca',published_at:new Date(Date.now()-3600000).toISOString()},
  {id:'restricted',url:'https://example.test/restricted',source:'Mitjà local',source_type:'media',
    title:'Un titular local contrastat',summary:'Text no autoritzat 8822.',content_policy:'headline_date_link_only',
    language:'ca',published_at:new Date(Date.now()-3600000).toISOString()},
  {id:'duplicate',url:'https://soller-ara.github.io/soller-ara/noticies/existing.html',
    original_url:'https://www.facebook.com/story.php?story_fbid=1&id=2',source:'Font',source_type:'own',
    title:'Publicació existent',summary:'Resum existent',published_at:new Date().toISOString()},
];
window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts(available);
const prepare=()=>node('socialPrepareTextButton').listeners.click();
const message=()=>node('socialPrepareTextMessage').textContent;
form.reset();await Promise.resolve();
form.elements.original_url.value='https://www.example.test/allowed/?utm_source=instagram&keep=one#details';
form.elements.instagram.checked=true;form.elements.show_in_now.checked=false;
form.elements.category.value='politics';form.elements.language.value='ca';
prepare();
assert.equal(form.elements.title.value,available[0].title);
assert.equal(form.elements.body.value,'El servei obre a les 14.30 h. Es manté fins al 27/11.');
assert.equal(form.elements.source_name.value,'Entitat local');
assert.equal(form.elements.instagram.checked,true);assert.equal(form.elements.show_in_now.checked,false);
assert.equal(form.elements.category.value,'politics');assert.equal(form.elements.language.value,'ca');
assert.match(message(),/Publicación original del/);assert.match(message(),/antes de publicar/);
const prepared=snapshot();prepare();assert.equal(snapshot(),prepared,'Prepared or authored fields cannot be overwritten');

form.reset();await Promise.resolve();form.elements.original_url.value=available[1].url;prepare();
assert.equal(form.elements.title.value,available[1].title);
assert.match(form.elements.body.value,/Consulta la publicació original/);
assert.ok(!form.elements.body.value.includes('8822'));
assert.match(message(),/no ofrece un resumen reutilizable/);

form.reset();await Promise.resolve();form.elements.original_url.value='https://example.test/allowed/extra?keep=one';
let untouched=snapshot();prepare();assert.equal(snapshot(),untouched);assert.match(message(),/No hay información verificable/);
form.elements.original_url.value='https://user:password@example.test/allowed?keep=one';
untouched=snapshot();prepare();assert.equal(snapshot(),untouched);assert.match(message(),/enlace HTTPS/);

form.reset();await Promise.resolve();form.elements.original_url.value='https://www.facebook.com/story.php?id=2&story_fbid=1&hpir=1';
untouched=snapshot();prepare();assert.equal(snapshot(),untouched);assert.match(message(),/evitar duplicarlo/);
form.reset();await Promise.resolve();form.elements.original_url.value=available[0].url;
form.elements.source_name.value='Una cuenta distinta';untouched=snapshot();prepare();
assert.equal(snapshot(),untouched);assert.match(message(),/no coincide/);

for(const badDate of ['invalid',new Date(Date.now()+86400000).toISOString(),new Date(Date.now()-61*86400000).toISOString()]) {
  form.reset();await Promise.resolve();form.elements.original_url.value=available[0].url;
  window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts([{...available[0],published_at:badDate}]);
  untouched=snapshot();prepare();assert.equal(snapshot(),untouched);assert.match(message(),/No hay información verificable/);
}
form.reset();await Promise.resolve();form.elements.original_url.value=available[0].url;
window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts([{...available[0],alert_status:'expired'}]);
untouched=snapshot();prepare();assert.equal(snapshot(),untouched);
window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts([{...available[0],language:'invalid_invalid_locale'}]);
untouched=snapshot();prepare();assert.equal(snapshot(),untouched);assert.match(message(),/No se ha podido preparar/);
window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts([{...available[0],title:'😀'.repeat(200)}]);prepare();
assert.ok(form.elements.title.value.length<=180);assert.ok(form.elements.title.value.isWellFormed());
form.reset();await Promise.resolve();form.elements.original_url.value=available[0].url;
window.SOLLER_ARA_EDITORIAL_GUIDE.setPosts([{...available[0],summary:"sarrom dv., 20/11/2026 - 10:46 20-Novembre-2026 L'Ajuntament atendrà el 24/11 a les 14.30 h."}]);prepare();
assert.equal(form.elements.body.value,"L'Ajuntament atendrà el 24/11 a les 14.30 h.");
assert.equal(requests,0);assert.equal(confirmations,2,'Preparation never submits, confirms or publishes');
console.log('PASS: permitted text preparation, explicit reference-only fallback, immutable authored fields and destinations, exact URL matching, original date, expired alerts, duplicate prevention and safe failures. No network or publication.');
