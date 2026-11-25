// Administrative, read-only editorial inbox. Posts never leave here unless a person opens a draft.
(() => {
  "use strict";
  const zone="Europe/Madrid", dayFmt=new Intl.DateTimeFormat("sv-SE",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"});
  const dayKey=(clock=Date.now())=>dayFmt.format(new Date(clock));
  const valid=s=>typeof s==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(s)&&Number.isFinite(Date.parse(s+"T12:00Z"))&&new Date(s+"T12:00Z").toISOString().slice(0,10)===s;
  function period(mode,selected,now=Date.now()){
    const today=dayKey(now),day=mode==="today"||!valid(selected)?today:selected;
    if(mode!=="week")return {from:day,to:day};
    const d=new Date(day+"T12:00Z"),i=(d.getUTCDay()+6)%7;
    const offset=n=>new Date(d.valueOf()+(n-i)*86400000).toISOString().slice(0,10);
    return {from:offset(0),to:offset(6)};
  }
  function profile(input){
    let u;try{u=new URL(input.profile);}catch{}
    const bad=()=>{throw Error("Pega el enlace al perfil o a la página, no al grupo ni a una publicación.");};
    if(!u||u.protocol!=="https:"||u.port||u.username||u.password||u.href.length>350)bad();
    const host=u.hostname.replace(/^(www\.|m\.)/,""),p=u.pathname.replace(/^\/|\/$/g,"");
    let network,handle,link,pageId="";
    if(host==="instagram.com"&&/^[\w.]{1,30}$/.test(p)&&!/^(?:p|reels?|stories|explore|direct|accounts|share|tv|about|developer|legal|directory|web)$/i.test(p)){
      network="instagram";handle=p.toLowerCase();link="https://www.instagram.com/"+handle+"/";
    }else if(host==="facebook.com"){
      network="facebook";if(p==="profile.php"&&!/^\d{1,22}$/.test(u.searchParams.get("id")||""))bad();handle=p==="profile.php"?u.searchParams.get("id")||"":/^(?:pages|people)\/[^/]+\/\d{1,22}$/.test(p)?p.split("/").at(-1):p;
      if(!/^[a-zA-Z0-9.\-]{1,90}$/.test(handle)||/(?:\.php$|^(?:groups|group|share|posts|watch|reels?|events|stories|marketplace|gaming|pages|people|login|media|photo|videos|plugins|help))$/i.test(handle))bad();
      handle=handle.toLowerCase();const numeric=/^\d{1,22}$/.test(handle);pageId=String(input.page_id||"").trim();
      if(pageId&&(!/^\d{1,22}$/.test(pageId)||(numeric&&pageId!==handle)))throw Error("Comprueba el ID numérico de la página.");
      pageId=numeric?handle:pageId;link=numeric?"https://www.facebook.com/profile.php?id="+handle:"https://www.facebook.com/"+handle+"/";
    }else bad();
    return {id:network+":"+handle,network,handle,profile:link,page_id:pageId,label:String(input.name||"").trim().slice(0,90)||(network==="instagram"?"@":"")+handle,status:"device"};
  }
  const stateText={device:"Solo consulta manual en este dispositivo.",pending:"Pendiente de primera lectura.",ready:"Lectura automática.",
    credentials:"Solo consulta manual: falta configurar o renovar el acceso de lectura de Meta.",permission:"Solo consulta manual: Meta no ha concedido permiso.",
    unavailable:"Solo consulta manual: Meta no permite identificar o consultar esta cuenta.",limited:"Meta ha limitado las consultas. Se volverá a intentar.",
    temporary:"Lectura interrumpida. El archivo anterior se conserva.",cursor:"Paginación interrumpida. Se volverá a consultar.",
    catching_up:"Leyendo más publicaciones: cobertura parcial.",partial_rows:"Lectura parcial: hay entradas sin enlace o fecha verificables.",incomplete:"Lectura parcial: faltan enlaces o fechas verificables.",busy:"Hay una revisión en curso."};
  if(typeof document==="undefined"){globalThis.socialWatchTest={period,dayKey,profile,stateText};return;}
  const el=id=>document.getElementById(id), panel=el("social-watch");if(!panel)return;
  const form=el("watchAddForm"),list=el("watchPosts"),accounts=el("watchAccounts"),date=el("watchDate"),feedback=el("watchFeedback");
  const localKey="sollerAraWatchProfiles.v1",token=()=>sessionStorage.getItem("sollerAraAdminSession")||"";
  const months=new Intl.DateTimeFormat("es-ES",{timeZone:zone,dateStyle:"long"}), time=new Intl.DateTimeFormat("es-ES",{timeZone:zone,dateStyle:"short",timeStyle:"short"});
  const dateLabel=d=>months.format(new Date(d+"T12:00Z"));
  let mode="today",storeMode="loading",entries=[],items=[],next="",generation=0,busy=false,localReadable=true;
  function readLocal(){try{const raw=JSON.parse(localStorage.getItem(localKey)||"[]");if(!Array.isArray(raw))throw Error();const result=raw.map(a=>profile({profile:a.profile,name:a.label,page_id:a.page_id}));localReadable=true;return result;}catch{localReadable=false;return [];}}
  function saveLocal(rows){if(!localReadable)throw Error("No se puede leer la lista de este navegador. No se han escrito cambios.");try{localStorage.setItem(localKey,JSON.stringify(rows));}catch{throw Error("El navegador no ha permitido guardar la cuenta.");}}
  const msg=(s,err=false)=>{feedback.textContent=s;feedback.className=err?"message error":"message";};
  const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  function button(text,fn){const b=node("button",text,"button-secondary");b.type="button";b.addEventListener("click",fn);return b;}
  function anchor(label,raw,network){const a=node("a",label,"button-link");let u;try{u=new URL(raw);}catch{return null;}
    if(u.protocol!=="https:"||u.hostname!==(network==="instagram"?"www.instagram.com":"www.facebook.com")||u.username||u.password||u.port)return null;
    a.href=u.href;a.target="_blank";a.rel="noopener noreferrer";return a;}
  function current(){return !el("adminView").hidden&&panel.classList.contains("active")&&Boolean(token());}
  function filters(){const p=period(mode,date.value);date.hidden=false;el("watchDateBox").hidden=mode==="today";
    panel.querySelectorAll("[data-watch-period]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.watchPeriod===mode)));
    el("watchPeriodLabel").textContent=(p.from===p.to?dateLabel(p.from):dateLabel(p.from)+" — "+dateLabel(p.to))+" · Fecha original, hora de Mallorca";return p;}
  async function request(params,body){
    const access=token();if(!access)throw Error("La sesión ha caducado.");
    const target=String(window.SOLLER_ARA_ADMIN_API||"").replace(/\/$/,"")+"/api/social-watch"+(params?"?"+new URLSearchParams(params):"");
    const rsp=await fetch(target,{method:body?"POST":"GET",mode:"cors",cache:"no-store",signal:AbortSignal.timeout(20000),headers:{Authorization:"Bearer "+access,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});
    let data;try{data=await rsp.json();}catch{throw Error("Respuesta no válida de Administración.");}
    if(!rsp.ok){const e=Error(data.error||"Error al consultar las cuentas.");e.device=!body&&(rsp.status===404||(rsp.status===503&&data.code==="watch_storage_setup"));throw e;}return data;
  }
  function render(){
    const p=filters(),local=readLocal();
    form.querySelector('[type="submit"]').disabled=busy||!["server","device"].includes(storeMode)||(storeMode==="device"&&!localReadable);
    el("watchMode").textContent=storeMode==="device"?"Lista provisional de este dispositivo. Puedes guardar cuentas y abrir sus perfiles; la lectura automática y la sincronización requieren conectar el archivo privado en Cloudflare.":storeMode==="server"?"Lista privada de Administración, disponible desde tus dispositivos.":storeMode==="error"?"No se ha podido actualizar la lista. No se han cambiado tus cuentas.":"Consultando las cuentas…";
    el("watchImport").hidden=storeMode!=="server"||!local.length;el("watchImport").disabled=busy;
    el("watchCount").textContent="("+entries.length+")";el("watchMore").hidden=!next;el("watchMore").disabled=busy;
    const outside=entries.filter(a=>a.status!=="ready"||!a.earliest||dayKey(a.earliest)>=p.from||!a.completed||dayKey(a.completed)<p.to);
    el("watchCoverage").textContent=storeMode==="loading"?"":storeMode==="error"?"Los datos que ya estaban en pantalla pueden estar desactualizados.":!entries.length?"Añade tu primera cuenta en «Mis cuentas».":storeMode==="device"?"Las cuentas de este dispositivo no se han consultado automáticamente.":(items.length?"Publicaciones encontradas. ":"No se han encontrado publicaciones para este periodo. ")+(outside.length?"Hay cuentas pendientes, sin acceso o sin cobertura completa de estas fechas.":"Consulta realizada hasta la última lectura de cada cuenta.");
    list.replaceChildren();for(const p of items){const a=anchor("Abrir publicación original",p.url,p.network);if(!a)continue;
      const card=node("article",undefined,"watch-card"),controls=node("div",undefined,"watch-controls");
      controls.append(a,button("Preparar en Enlaces de redes",()=>{try{window.SOLLER_ARA_WATCH_DRAFT(p.label,p.url);}catch(e){msg(e.message,true);}}));
      card.append(node("small",time.format(new Date(p.stamp))+" · "+(p.network==="instagram"?"Instagram":"Facebook")),node("h3",p.label),node("p",p.brief),controls);list.append(card);}
    accounts.replaceChildren();for(const a of entries){const card=node("article",undefined,"watch-card"),controls=node("div",undefined,"watch-controls"),link=anchor("Abrir perfil",a.profile,a.network);
      if(link)controls.append(link);
      if(storeMode==="server"){const check=button("Comprobar lectura",()=>act(async()=>{const result=await request(null,{action:"check",id:a.id});return stateText[result.state]||"Revisión solicitada.";}));check.disabled=busy;controls.append(check);}
      const remove=button("Quitar",()=>{if(!window.confirm("¿Quitar "+a.label+" de esta lista y de su archivo de seguimiento? Las publicaciones de Sóller Ara no cambian."))return;
        act(async()=>{if(storeMode==="server")await request(null,{action:"remove",id:a.id});else saveLocal(readLocal().filter(x=>x.id!==a.id));return "Cuenta retirada de esta lista.";});});remove.disabled=busy||!["server","device"].includes(storeMode);controls.append(remove);
      card.append(node("h3",a.label),node("small",a.network==="instagram"?"Instagram":"Facebook"),node("p",stateText[a.status]||"Pendiente de comprobación."),controls);
      if(a.attempted)card.append(node("small","Último intento: "+time.format(new Date(a.attempted))+(a.completed?" · Última lectura: "+time.format(new Date(a.completed)):"")));accounts.append(card);}
  }
  async function load(more=false){
    if(!current())return;const version=++generation,p=filters(),cursor=next;
    if(!more){list.replaceChildren();items=[];next="";el("watchMore").hidden=true;}
    try{const data=await request({...p,...(more&&cursor?{before:cursor}:{})});if(version!==generation||!current())return;
      if(!Array.isArray(data.accounts)||!Array.isArray(data.posts))throw Error("Respuesta de seguimiento no válida.");
      storeMode="server";entries=data.accounts;items=more?[...new Map([...items,...data.posts].map(v=>[v.k,v])).values()]:data.posts;next=data.next||"";
    }catch(e){if(version!==generation||!current())return;if(e.device){storeMode="device";entries=readLocal();items=[];next="";if(!localReadable)msg("No se ha podido leer la lista local.",true);}
      else{storeMode="error";msg(e.message,true);}}
    render();if(!entries.length)el("watchAccountsBox").open=true;
  }
  async function act(fn){if(busy||!current())return;busy=true;render();msg("Un momento…");try{const message=await fn();await load();if(current())msg(message);}catch(e){if(current())msg(e.message,true);}finally{busy=false;if(current())render();}}
  form.addEventListener("submit",e=>{e.preventDefault();act(async()=>{const data={profile:form.elements.profile.value,name:form.elements.name.value,page_id:form.elements.page_id.value},a=profile(data);let existing=false;
    if(storeMode==="server"){existing=(await request(null,{action:"add",...data})).existing;}
    else if(storeMode==="device"){const rows=readLocal();existing=rows.some(x=>x.id===a.id);if(!existing){if(rows.length>=100)throw Error("La lista admite hasta 100 cuentas.");saveLocal([...rows,a]);}}
    else throw Error("Actualiza la lista antes de añadir cuentas.");
    form.reset();el("watchPageIdBox").hidden=true;return existing?"Esa cuenta ya figuraba en la lista.":"Cuenta añadida.";});});
  form.elements.profile.addEventListener("input",()=>{let fb=false;try{fb=/^(?:www\.|m\.)?facebook\.com$/.test(new URL(form.elements.profile.value).hostname);}catch{}el("watchPageIdBox").hidden=!fb;if(!fb)form.elements.page_id.value="";});
  el("watchImport").addEventListener("click",()=>act(async()=>{for(const p of readLocal()){
    await request(null,{action:"add",profile:p.profile,name:p.label,page_id:p.page_id});saveLocal(readLocal().filter(x=>x.id!==p.id));}
    return "Cuentas guardadas en Administración."; }));
  panel.querySelectorAll("[data-watch-period]").forEach(b=>b.addEventListener("click",()=>{if(mode==="today"||b.dataset.watchPeriod==="today")date.value=dayKey();mode=b.dataset.watchPeriod;load();}));
  date.value=dayKey();date.addEventListener("change",()=>{if(valid(date.value)){load();}else msg("Selecciona una fecha válida.",true);});
  el("watchReload").addEventListener("click",()=>{msg("");load();});el("watchMore").addEventListener("click",()=>{if(next)load(true);});
  const visible=()=>{if(current())load();else{generation++;if(el("adminView").hidden){entries=[];items=[];next="";storeMode="loading";accounts.replaceChildren();list.replaceChildren();msg("");form.reset();}}};
  new MutationObserver(visible).observe(panel,{attributes:true,attributeFilter:["class"]});
  new MutationObserver(visible).observe(el("adminView"),{attributes:true,attributeFilter:["hidden"]});
  const openBookmark=()=>{if(window.location.hash==="#cuentas-que-sigo")document.querySelector('.nav-button[data-view="social-watch"]')?.click();};
  window.addEventListener("hashchange",openBookmark);openBookmark();
  document.addEventListener("visibilitychange",()=>{if(!document.hidden&&current())load();});
  window.setInterval(()=>{if(!document.hidden&&!busy&&current())load();},300000);
})();
