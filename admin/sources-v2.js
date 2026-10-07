(() => {
  const API = String(window.SOLLER_ARA_ADMIN_API || "").replace(/\/$/, "");
  const TOKEN_KEY = "sollerAraAdminSession";
  const repoJson = window.SOLLER_ARA_READ_JSON;
  let collectionRunning = false;

  const esc = (v) => String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");
    const token = sessionStorage.getItem(TOKEN_KEY) || "";
    if (token) headers.set("Authorization", "Bearer " + token);
    const response = await fetch(API + path, { ...options, headers, cache: "no-store", mode: "cors" });
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload.error || "Error de Administración.");
    return payload;
  }



  function message(text, kind = "") {
    const el = document.getElementById("sourcesMessage");
    if (!el) return;
    el.textContent = text || "";
    el.className = "message" + (kind ? " " + kind : "");
  }

  function inject() {
    const nav = document.querySelector(".admin-nav");
    const app = document.getElementById("adminView");
    if (!nav || !app || document.getElementById("sources")) return;

    const tab = document.createElement("button");
    tab.className = "nav-button";
    tab.type = "button";
    tab.dataset.view = "sources";
    tab.textContent = "Fuentes";
    nav.appendChild(tab);

    const section = document.createElement("section");
    section.id = "sources";
    section.className = "module";
    section.innerHTML = `
      <div class="module-heading">
        <div><p class="eyebrow">Recopilación</p><h2>Fuentes de Sóller Ara</h2>
        <p class="hint">Activa o desactiva las fuentes que alimentan automáticamente la web. Desactivar una fuente detiene nuevas recopilaciones; las publicaciones anteriores se conservan dentro del límite de antigüedad y pueden ocultarse desde Moderación.</p></div>
        <div class="post-actions"><button id="collectSourcesButton" type="button" disabled>Buscar y publicar ahora</button>
        <button id="refreshSourcesButton" class="button-secondary" type="button">Actualizar estado</button></div>
      </div>
      <p class="hint">Buscar y publicar ahora revisa las fuentes y realiza los envíos permitidos por la configuración actual. La revisión automática de cada hora continúa igual. Los envíos manuales de Instagram pendientes por una pausa de Meta se reintentan en estas revisiones.</p>
      <p id="collectionMessage" class="message" aria-live="polite"></p>
      <div id="sourcesSummary" class="metrics"></div>
      <article class="panel-card"><h3>Fuentes de información</h3><div id="sourcesList" class="post-list"><p class="empty">Cargando fuentes…</p></div></article>
      <article class="panel-card" style="margin-top:18px"><h3>Fuentes sociales externas</h3><p class="hint">Su estado se muestra aquí. La activación depende de las APIs de cada plataforma.</p><div id="socialSourcesList" class="post-list"><p class="empty">Cargando…</p></div></article>
      <article class="panel-card" style="margin-top:18px"><h3>Distribución automática a redes</h3><p class="hint">Estado de los envíos automáticos a Facebook e Instagram según las fuentes y los límites configurados.</p></article>
      <p id="sourcesMessage" class="message" aria-live="polite"></p>`;
    app.appendChild(section);

    tab.addEventListener("click", () => {
      document.querySelectorAll(".nav-button").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".module").forEach((x) => x.classList.remove("active"));
      tab.classList.add("active");
      section.classList.add("active");
      load();
    });
    document.getElementById("refreshSourcesButton").addEventListener("click", load);
    document.getElementById("collectSourcesButton").addEventListener("click", collect);
  }

  function statusMap(data) {
    const map = new Map();
    for (const item of (data.source_status || [])) if (item.source_id) map.set(item.source_id, item);
    return map;
  }

  function typeLabel(source) {
    const entityLabels = { institution: "Institución", association: "Asociación", sports_club: "Club deportivo", creator: "Creador independiente" };
    const entity = entityLabels[source.entity_type];
    if (entity) return (source.platform ? source.platform + " · " : "") + entity;
    if (source.source_type === "official") return "Oficial";
    if (source.source_type === "media") return "Medio";
    if (source.source_type === "social") return "Social";
    return source.source_type || "Fuente";
  }

  function render(config, posts) {
    const sources = Array.isArray(config.sources) ? config.sources : [];
    const active = sources.filter((x) => x.enabled !== false).length;
    document.getElementById("sourcesSummary").innerHTML = [
      ["Fuentes configuradas", sources.length], ["Activas", active], ["Desactivadas", sources.length - active]
    ].map(([a,b]) => `<div class="metric"><span>${esc(a)}</span><strong>${esc(b)}</strong></div>`).join("");

    const health = statusMap(posts);
    const retainedCounts = new Map();
    for (const post of (posts.posts || [])) {
      retainedCounts.set(post.source_id, (retainedCounts.get(post.source_id) || 0) + 1);
    }
    const list = document.getElementById("sourcesList");
    list.innerHTML = sources.map((source) => {
      const enabled = source.enabled !== false;
      const current = health.get(source.id);
      const count = enabled ? current?.count ?? 0 : retainedCounts.get(source.id) || 0;
      const label = !enabled ? "DESACTIVADA" : current?.ok === false ? "ERROR" : current?.ok === true ? "OK" : "PENDIENTE";
      const cls = !enabled || current?.ok == null ? "pending" : current.ok ? "ok" : "bad";
      return `<article class="post-item">
        <header><h4>${esc(source.name || source.id)}</h4></header>
        <div class="post-meta">${esc(typeLabel(source))} · ${esc(source.type || "")} · ${esc(source.language || "")} · ${esc(count)} publicaciones${enabled ? "" : " conservadas"}</div>
        <div class="post-meta">${esc(source.locality || "Sóller")}</div>
        ${enabled && current?.ok === false ? `<p class="message error">${esc(current.error || "La fuente no responde.")}</p><p class="hint">${esc(current.retained_count || 0)} publicaciones anteriores conservadas. Última revisión: ${esc((current.checked_at || posts.sources_checked_at || posts.fetched_at) ? new Date(current.checked_at || posts.sources_checked_at || posts.fetched_at).toLocaleString("es-ES") : "sin datos")}.</p>` : ""}
        ${enabled && current?.ok === true && current.count === 0 ? '<p class="hint">La fuente responde; no hay publicaciones recientes que cumplan los filtros.</p>' : ""}
        <div class="post-actions"><span class="${cls}">${label}</span><button type="button" data-source-id="${esc(source.id)}" data-source-enabled="${enabled}">${enabled ? "Desactivar" : "Activar"}</button></div>
      </article>`;
    }).join("");
    list.querySelectorAll("[data-source-id]").forEach((button) => button.addEventListener("click", () => toggle(button)));
  }

  function renderSocial(config) {
    const list = document.getElementById("socialSourcesList");
    const sources = Array.isArray(config.sources) ? config.sources : [];
    list.innerHTML = sources.length ? sources.map((source) => `<article class="post-item">
      <header><h4>${esc(source.name || source.account || "Fuente social")}</h4></header>
      <div class="post-meta">${esc(source.platform || "")} · ${esc(source.account || "")}</div>
      <div class="post-actions"><span class="${source.status === "active" ? "ok" : "pending"}">${esc(source.status || "pendiente")}</span></div>
    </article>`).join("") : '<p class="empty">No hay fuentes sociales configuradas.</p>';
  }

  async function load() {
    const button = document.getElementById("refreshSourcesButton");
    if (button) { button.disabled = true; button.textContent = "Actualizando…"; }
    message("");
    try {
      const [config, social, posts] = await Promise.allSettled([
        repoJson("sources.json"), repoJson("social_sources.json"), repoJson("data/posts.json")
      ]);
      if (config.status === "fulfilled") render(config.value, posts.status === "fulfilled" ? posts.value : {});
      else document.getElementById("sourcesList").innerHTML = '<p class="message error">No se han podido cargar las fuentes. Pulsa Actualizar.</p>';
      if (social.status === "fulfilled") renderSocial(social.value);
      else document.getElementById("socialSourcesList").innerHTML = '<p class="message error">No se han podido cargar las fuentes sociales. Pulsa Actualizar.</p>';
      const errors = [config, social, posts].filter((result) => result.status === "rejected");
      if (errors.length) message(errors.map((result) => result.reason.message).join(" "), "error");
      if (!collectionRunning) {
        const health = await api("/health");
        const enabled = health.capabilities?.includes("manual_collection");
        document.getElementById("collectSourcesButton").disabled = !enabled;
        document.getElementById("collectionMessage").textContent = enabled ? "" : "La búsqueda inmediata está pendiente de activación.";
      }
    } catch (error) {
      message(error.message, "error");
    } finally {
      if (button) { button.disabled = false; button.textContent = "Actualizar estado"; }
    }
  }

  async function collect() {
    if (collectionRunning) return;
    const button = document.getElementById("collectSourcesButton");
    const notice = document.getElementById("collectionMessage");
    collectionRunning = true;
    button.disabled = true;
    button.textContent = "Revisando y publicando…";
    try {
      const result = await api("/api/collect", {method:"POST", body:"{}"});
      notice.textContent = result.already_running
        ? "Ya hay una revisión en marcha. Esperando a que termine…"
        : "Búsqueda solicitada. GitHub revisará las fuentes y publicará según las opciones actuales.";
      let runId = result.run?.id || null;
      for (let attempt = 0; attempt < 120; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 5000));
        const state = await api("/api/collect" + (runId ? "?run_id=" + runId : ""));
        const run = state.run;
        if (!run || (result.already_running ? run.id !== result.run.id : run.id === result.previous_run_id)) continue;
        runId = run.id;
        if (run.status !== "completed") continue;
        await load();
        notice.textContent = run.conclusion === "success"
          ? "Revisión terminada. La web está actualizada y se han procesado los envíos permitidos. Instagram puede seguir pendiente si Meta mantiene la pausa."
          : "La revisión ha terminado con una incidencia. Consulta el estado de las fuentes y de los envíos.";
        return;
      }
      notice.textContent = "La solicitud sigue en proceso. Puedes consultar su estado más tarde con Actualizar estado.";
    } catch (error) {
      notice.textContent = error.message;
    } finally {
      collectionRunning = false;
      button.disabled = false;
      button.textContent = "Buscar y publicar ahora";
    }
  }

  async function waitFor(sourceId, enabled) {
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      const config = await repoJson("sources.json");
      const source = (config.sources || []).find((x) => x.id === sourceId);
      if (source && (source.enabled !== false) === enabled) return true;
      message("Esperando confirmación de GitHub…");
    }
    return false;
  }

  async function toggle(button) {
    const sourceId = button.dataset.sourceId;
    const current = button.dataset.sourceEnabled === "true";
    const next = !current;
    if (!confirm("¿Confirmas que quieres " + (next ? "activar" : "desactivar") + " esta fuente?")) return;
    button.disabled = true;
    button.textContent = next ? "Activando…" : "Desactivando…";
    message("Enviando cambio…");
    try {
      await api("/api/source", { method: "POST", body: JSON.stringify({ source_id: sourceId, enabled: next }) });
      if (await waitFor(sourceId, next)) {
        message(next
          ? "Fuente activada correctamente. Volverá a recopilar en las próximas actualizaciones."
          : "Fuente desactivada correctamente. Las publicaciones anteriores se conservarán dentro del límite de antigüedad.", "success");
        await load();
      } else {
        message("El cambio se ha enviado. GitHub todavía está confirmándolo; pulsa Actualizar en unos segundos.", "error");
      }
    } catch (error) {
      message(error.message, "error");
    } finally {
      button.disabled = false;
    }
  }

  inject();
})();
