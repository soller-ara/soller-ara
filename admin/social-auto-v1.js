(() => {
  const API = String(window.SOLLER_ARA_ADMIN_API || "").replace(/\/$/, "");
  const LIVE_REPO_API = "https://api.github.com/repos/soller-ara/soller-ara/contents/";
  const TOKEN_KEY = "sollerAraAdminSession";
  const repoJson = window.SOLLER_ARA_READ_JSON;
  const categoryNames = {news: "Noticias", agenda: "Agenda", alerts: "Avisos", services: "Servicios", culture: "Cultura", sports: "Deportes", commerce: "Comercio", politics: "Política", social: "Redes"};
  let rendering = false;
  let state = null;

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#039;");

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");
    const token = sessionStorage.getItem(TOKEN_KEY) || "";
    if (token) headers.set("Authorization", "Bearer " + token);
    const response = await fetch(API + path, {...options, headers, cache: "no-store", mode: "cors"});
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(payload.error || `Error de Administración (${response.status}).`);
    return payload;
  }

  async function liveRepoJson(path) {
    const url = new URL(path, LIVE_REPO_API);
    url.searchParams.set("ref", "main");
    url.searchParams.set("v", Date.now());
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "omit",
      headers: {Accept: "application/vnd.github.raw+json"},
      signal: AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error(`GitHub no ha devuelto ${path} (${response.status}).`);
    const payload = await response.json();
    if (!payload?.content || payload.encoding !== "base64") return payload;
    const binary = atob(String(payload.content).replaceAll("\n", ""));
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(bytes));
  }

  async function findCard() {
    for (let attempt = 0; attempt < 50; attempt++) {
      const heading = [...document.querySelectorAll("#sources .panel-card h3")]
        .find((item) => item.textContent.includes("Distribución automática"));
      if (heading) return heading.closest(".panel-card");
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    return null;
  }

  function row(title, detail, status, kind = "") {
    return `<div class="status-row"><span><strong>${esc(title)}</strong><small>${detail}</small></span><strong class="${kind}">${esc(status)}</strong></div>`;
  }

  function platformRow(config, entries, platform, logAvailable, cooldowns = {}) {
    const name = platform === "facebook" ? "Facebook" : "Instagram";
    const enabled = config.platforms?.[platform] === true;
    const count = Object.values(config.sources || {}).filter((item) => item?.[platform] === true).length;
    let detail = `${count} fuentes autorizadas` + (platform === "instagram" ? " · tarjetas propias de Sóller Ara" : "");
    let status = !enabled ? "DESACTIVADA" : config.enabled ? "PENDIENTE" : "EN PAUSA";
    let kind = "pending";
    const last = entries.filter((item) => item.platform === platform && item.mode === "automatic_collected")
      .sort((a, b) => String(b.recorded_at).localeCompare(String(a.recorded_at)))[0];
    if (enabled && config.enabled && !logAvailable) {
      status = "SIN DATOS";
      detail += "<br>No se ha podido consultar el registro de envíos.";
    } else if (enabled && config.enabled && last) {
      const date = new Date(last.recorded_at);
      const when = Number.isNaN(date.getTime()) ? "" : date.toLocaleString("es-ES");
      if (last.status === "success") {
        status = "ENVIADO";
        kind = "ok";
        detail += `<br>Último envío confirmado: ${esc(when)}.`;
        if (last.title) detail += `<br>${esc(last.title)}`;
        try {
          const url = new URL(last.remote_url);
          if (url.protocol === "https:" && ["www.facebook.com", "www.instagram.com", "facebook.com", "instagram.com"].includes(url.hostname)) {
            detail += ` <a href="${esc(url.href)}" target="_blank" rel="noopener noreferrer">Ver publicación</a>`;
          }
        } catch (_) {}
      } else {
        status = "ERROR";
        kind = "bad";
        detail += `<br>Último intento: ${esc(when)}. ${esc(last.error || "No se ha podido completar el envío.")}`;
      }
    } else if (enabled && config.enabled) {
      detail += "<br>A la espera de contenido reciente que cumpla los filtros.";
    }
    const pauseUntil = new Date(cooldowns.instagram_until || "");
    if (platform === "instagram" && enabled && config.enabled && pauseUntil > new Date()) {
      status = "EN PAUSA · META";
      kind = "pending";
      detail += `<br>Límite temporal de Meta hasta ${esc(pauseUntil.toLocaleString("es-ES"))}. Facebook continúa activo.`;
    }
    return row(name, detail, status, kind);
  }

  function currentRules() {
    const rules = {};
    document.querySelectorAll("#socialSourceControls [data-social-source]").forEach((item) => {
      const id = item.dataset.socialSource;
      rules[id] ||= {facebook: false, instagram: false};
      rules[id][item.dataset.platform] = item.checked;
    });
    return rules;
  }

  function isAlreadySent(postId, platform) {
    const post = state.posts.find((item) => item.id === postId);
    return state.entries.some((item) => item.platform === platform && item.status === "success"
      && (item.post_id === postId || (post?.source_id && post?.url
        && item.source_id === post.source_id && item.post_url === post.url)));
  }

  function nextPreview(rules) {
    const now = Date.now();
    const oldest = now - Number(state.config.max_age_hours || 6) * 3600000;
    const active = new Set(state.sources.filter((source) => source.enabled !== false).map((source) => source.id));
    return state.posts.filter((post) => {
      const time = new Date(post.published_at).getTime();
      if (!post.id || post.source_type === "own" || !active.has(post.source_id) || !Number.isFinite(time) || time < oldest || time > now) return false;
      if (state.config.categories?.[post.category || "news"] === false) return false;
      const rule = rules[post.source_id] || {};
      return ["facebook", "instagram"].some((platform) => state.config.platforms?.[platform] && rule[platform] && !isAlreadySent(post.id, platform));
    }).sort((a, b) => new Date(b.published_at) - new Date(a.published_at))[0] || null;
  }

  function safeSummary(post) {
    return post.content_policy === "headline_date_link_only" ? "" : String(post.summary || "").trim().slice(0, 500);
  }

  function renderPreview() {
    const target = document.getElementById("socialPreview");
    if (!target || !state) return;
    const rules = currentRules();
    const post = nextPreview(rules);
    if (!post) {
      target.innerHTML = '<p class="empty">Ahora no hay ninguna publicación pendiente de las últimas horas que cumpla la selección.</p>';
      return;
    }
    const selected = ["facebook", "instagram"].filter((platform) => state.config.platforms?.[platform]
      && rules[post.source_id]?.[platform] && !isAlreadySent(post.id, platform));
    const summary = safeSummary(post);
    const text = [post.title, summary, `Fuente: ${post.source || "Fuente original"}`, `Información original: ${post.url || ""}`].filter(Boolean).join("\n\n");
    target.innerHTML = `<div class="social-preview-grid">
      ${selected.includes("facebook") ? `<article class="network-preview"><strong>Facebook</strong><p>${esc(text)}</p><a href="${esc(post.url)}" target="_blank" rel="noopener noreferrer">${esc(post.url)}</a></article>` : ""}
      ${selected.includes("instagram") ? `<article class="network-preview instagram"><strong>Instagram · tarjeta propia</strong><div class="instagram-card"><img src="../assets/brand/logo-soller-ara-web.png" width="54" height="54" alt="" /><small>SÓLLER ARA · ${esc(categoryNames[post.category] || "Actualidad")}</small><h4>${esc(post.title)}</h4><p>Fuente: ${esc(post.source || "Fuente original")}</p></div><p>${esc(text)}\n\n#Sóller #SollerAra</p></article>` : ""}
    </div><p class="hint">Vista previa de la siguiente candidata según la configuración mostrada. Revisarla no publica ni reserva la noticia.</p>`;
  }

  function sourceControls(config, sources) {
    return `<div id="socialSourceControls" class="social-source-list">${sources.map((source) => {
      const configured = Object.prototype.hasOwnProperty.call(config.sources || {}, source.id);
      const rule = config.sources?.[source.id] || {};
      const inactive = source.enabled === false;
      const selected = Boolean(rule.facebook || rule.instagram);
      const detail = inactive ? "Fuente desactivada"
        : !configured ? "Pendiente de decidir su distribución social"
        : selected ? esc(source.locality || "Sóller")
        : `${esc(source.locality || "Sóller")} · sin distribución social`;
      return `<div class="social-source-row"><span><strong>${esc(source.name || source.id)}</strong><small>${detail}</small></span>
        <label class="check"><input type="checkbox" data-social-source="${esc(source.id)}" data-platform="facebook" ${rule.facebook ? "checked" : ""} ${inactive ? "disabled" : ""}/> Facebook</label>
        <label class="check"><input type="checkbox" data-social-source="${esc(source.id)}" data-platform="instagram" ${rule.instagram ? "checked" : ""} ${inactive ? "disabled" : ""}/> Instagram</label></div>`;
    }).join("")}</div>`;
  }

  async function waitForSave(requestId) {
    for (let attempt = 0; attempt < 30; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const results = await liveRepoJson("data/social_settings_results.json")
        .catch(() => repoJson("data/social_settings_results.json"))
        .catch(() => ({entries: []}));
      const result = (results.entries || []).find((entry) => entry.request_id === requestId);
      if (result) {
        if (!result.ok) throw new Error(result.error || "No se ha guardado el cambio.");
        const config = await liveRepoJson("social_distribution.json")
          .catch(() => repoJson("social_distribution.json"));
        if (config.version >= result.version) return config;
      }
      const message = document.getElementById("socialSettingsMessage");
      if (message) message.textContent = "Guardando y comprobando el cambio…";
    }
    throw new Error("GitHub sigue procesando el cambio. Pulsa Actualizar dentro de unos segundos.");
  }

  async function save() {
    const button = document.getElementById("saveSocialSettings");
    const message = document.getElementById("socialSettingsMessage");
    button.disabled = true;
    message.className = "message";
    message.textContent = "Enviando configuración…";
    try {
      const response = await api("/api/social-settings", {method: "POST", body: JSON.stringify({
        base_version: state.config.version,
        enabled: document.getElementById("socialAutomationEnabled").checked,
        sources: currentRules(),
      })});
      await waitForSave(response.request_id);
      message.className = "message success";
      message.textContent = "Configuración guardada y comprobada.";
      await render(true);
    } catch (error) {
      message.className = "message error";
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function render(force = false) {
    if (rendering && !force) return;
    rendering = true;
    try {
      const card = await findCard();
      if (!card) return;
      let target = document.getElementById("socialAutoStatus");
      if (!target) {
        target = document.createElement("div");
        target.id = "socialAutoStatus";
        target.setAttribute("aria-live", "polite");
        card.appendChild(target);
      }
      target.innerHTML = '<p class="empty">Cargando configuración…</p>';
      const [configResult, logResult, sourcesResult, postsResult, healthResult] = await Promise.allSettled([
        liveRepoJson("social_distribution.json").catch(() => repoJson("social_distribution.json")), repoJson("data/social_publish_log.json"),
        repoJson("sources.json"), repoJson("data/posts.json"),
        fetch(API + "/health", {cache: "no-store", mode: "cors"}).then((response) => response.ok ? response.json() : {}),
      ]);
      if (configResult.status !== "fulfilled" || sourcesResult.status !== "fulfilled" || postsResult.status !== "fulfilled") {
        target.innerHTML = '<p class="message error">No se ha podido cargar la configuración completa. Pulsa Actualizar.</p>';
        return;
      }
      const config = configResult.value;
      const entries = logResult.status === "fulfilled" ? logResult.value.entries || [] : [];
      const sources = sourcesResult.value.sources || [];
      const posts = postsResult.value.posts || [];
      const settingsReady = healthResult.status === "fulfilled" && healthResult.value.capabilities?.includes("social_settings");
      state = {config, entries, sources, posts, settingsReady};
      const missingSources = sources.filter((source) => source.enabled !== false
        && !Object.prototype.hasOwnProperty.call(config.sources || {}, source.id));
      const categories = Object.entries(config.categories || {}).filter(([, enabled]) => enabled === true).map(([key]) => categoryNames[key] || key);
      target.innerHTML = `<div class="status-list">${row("Automatización", config.enabled ? "Revisión programada cada hora; los envíos se confirman debajo." : "La publicación automática está pausada.", config.enabled ? "ACTIVA" : "EN PAUSA", config.enabled ? "ok" : "pending")
        + platformRow(config, entries, "facebook", logResult.status === "fulfilled", logResult.status === "fulfilled" ? logResult.value.cooldowns || {} : {})
        + platformRow(config, entries, "instagram", logResult.status === "fulfilled", logResult.status === "fulfilled" ? logResult.value.cooldowns || {} : {})
        + row("Ritmo máximo", `Contenido de las últimas ${esc(config.max_age_hours || 6)} h, sin repetir envíos confirmados.`, `${config.max_posts_per_run || 3} noticias / ejecución`)}</div>
      <div class="social-settings"><div class="social-settings-heading"><div><h4>Control de envíos</h4><p class="hint">La pausa no detiene la recopilación de la web. Las casillas solo autorizan la distribución a cada red.</p></div>
        <label class="switch-label"><input id="socialAutomationEnabled" type="checkbox" ${config.enabled ? "checked" : ""}/><span>${config.enabled ? "Automatización activa" : "Automatización en pausa"}</span></label></div>
        ${missingSources.length ? `<p class="message error">Hay ${missingSources.length} ${missingSources.length === 1 ? "fuente activa pendiente" : "fuentes activas pendientes"} de decidir para redes. Revisa sus casillas y guarda la configuración.</p>` : ""}
        ${sourceControls(config, sources)}<div class="social-settings-actions"><button id="saveSocialSettings" class="primary-button" type="button" ${settingsReady ? "" : "disabled"}>Guardar configuración</button><span id="socialSettingsMessage" class="message ${settingsReady ? "" : "error"}" aria-live="polite">${settingsReady ? "" : "Servidor pendiente de actualizar. Puedes revisar la selección, pero todavía no guardarla."}</span></div></div>
      <div class="social-preview"><h4>Vista previa del siguiente envío</h4><div id="socialPreview"></div></div>
      <p class="hint">Categorías activas: ${esc(categories.join(", ") || "ninguna")}. Máximo una noticia por fuente en cada ejecución.</p>`;
      document.getElementById("saveSocialSettings").addEventListener("click", save);
      document.getElementById("socialAutomationEnabled").addEventListener("change", (event) => {
        event.target.nextElementSibling.textContent = event.target.checked ? "Automatización activa" : "Automatización en pausa";
      });
      document.getElementById("socialSourceControls").addEventListener("change", renderPreview);
      renderPreview();
    } finally {
      rendering = false;
    }
  }

  render();
  document.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button?.dataset.view === "sources" || button?.id === "refreshSourcesButton") render();
  });
})();
