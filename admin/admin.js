(() => {
  const API = String(window.SOLLER_ARA_ADMIN_API || "").replace(/\/$/, "");
  const TOKEN_KEY = "sollerAraAdminSession";

  const loginView = document.getElementById("loginView");
  const adminView = document.getElementById("adminView");
  const loginForm = document.getElementById("loginForm");
  const loginMessage = document.getElementById("loginMessage");
  const setupMessage = document.getElementById("setupMessage");
  const logoutButton = document.getElementById("logoutButton");
  const refreshButton = document.getElementById("refreshButton");
  const systemCheckButton = document.getElementById("systemCheckButton");
  const systemCheckResult = document.getElementById("systemCheckResult");
  const publishForm = document.getElementById("publishForm");
  const publishMessage = document.getElementById("publishMessage");
  const moderationMessage = document.getElementById("moderationMessage");
  const postSearch = document.getElementById("postSearch");
  const previewTitle = document.getElementById("previewTitle");
  const previewBody = document.getElementById("previewBody");
  const publishHeading = document.getElementById("publishHeading");
  const editModeNote = document.getElementById("editModeNote");
  const publishSubmitButton = document.getElementById("publishSubmitButton");
  const cancelEditButton = document.getElementById("cancelEditButton");
  const facebookInput = publishForm.querySelector('input[name="facebook"]');
  const instagramInput = publishForm.querySelector('input[name="instagram"]');
  const socialLinkForm = document.getElementById("socialLinkForm");
  const socialLinkMessage = document.getElementById("socialLinkMessage");
  const socialLinkHeading = document.getElementById("socialLinkHeading");
  const socialLinkEditNote = document.getElementById("socialLinkEditNote");
  const socialLinkSubmitButton = document.getElementById("socialLinkSubmitButton");
  const cancelSocialLinkEditButton = document.getElementById("cancelSocialLinkEditButton");
  const socialLinkList = document.getElementById("socialLinkList");

  let statusPayload = null;
  let editPostId = "";
  let socialLinkEditPostId = "";

  function getToken() {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(token) {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  }

  function setMessage(element, text, kind = "") {
    element.textContent = text || "";
    element.className = "message" + (kind ? " " + kind : "");
  }


  async function readPublicState() {
    const stamp = Date.now();
    const [postsResponse, moderationResponse] = await Promise.all([
      fetch("../data/posts.json?v=" + stamp, { cache: "no-store" }),
      fetch("../data/moderation.json?v=" + stamp, { cache: "no-store" }),
    ]);

    if (!postsResponse.ok || !moderationResponse.ok) {
      throw new Error("No se ha podido leer el estado público actualizado.");
    }

    const [posts, moderation] = await Promise.all([
      postsResponse.json(),
      moderationResponse.json(),
    ]);

    return { posts, moderation };
  }

  async function mergePublicState(data) {
    try {
      const publicState = await readPublicState();
      data.posts = publicState.posts;
      data.moderation = publicState.moderation;
    } catch (_) {
      // Si GitHub Pages está desplegando todavía, conservamos temporalmente
      // el estado recibido del backend y volveremos a intentarlo en el siguiente refresco.
    }
    return data;
  }

  async function api(path, options = {}) {
    if (!API) throw new Error("Backend de Administración no configurado.");

    const headers = new Headers(options.headers || {});
    headers.set("Content-Type", "application/json");
    const token = getToken();
    if (token) headers.set("Authorization", "Bearer " + token);

    const response = await fetch(API + path, {
      ...options,
      headers,
      mode: "cors",
      cache: "no-store",
    });

    let payload = {};
    try { payload = await response.json(); } catch (_) {}

    if (response.status === 401) {
      setToken("");
      showLogin();
      throw new Error(payload.error || "La sesión ha caducado.");
    }

    if (!response.ok) {
      throw new Error(payload.error || "Error de Administración (" + response.status + ").");
    }

    return payload;
  }

  function showLogin() {
    loginView.hidden = false;
    adminView.hidden = true;
  }

  function showAdmin() {
    loginView.hidden = true;
    adminView.hidden = false;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatDate(value) {
    if (!value) return "—";
    try {
      return new Intl.DateTimeFormat("es-ES", {
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value));
    } catch (_) {
      return value;
    }
  }

  function renderMetrics(data) {
    const posts = Array.isArray(data.posts?.posts) ? data.posts.posts : [];
    const sources = Array.isArray(data.posts?.source_status) ? data.posts.source_status : [];
    const failedSources = sources.filter((item) => item.ok === false).length;
    const ownPosts = posts.filter((item) => item.source_type === "own").length;

    document.getElementById("metrics").innerHTML = [
      ["Publicaciones", posts.length],
      ["Contenido propio", ownPosts],
      ["Fuentes con error", failedSources],
      ["Última actualización", formatDate(data.posts?.fetched_at)],
    ].map(([label, value]) => `
      <div class="metric">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `).join("");
  }

  function renderSources(data) {
    const sources = Array.isArray(data.posts?.source_status) ? data.posts.source_status : [];
    const target = document.getElementById("sourceStatus");

    if (!sources.length) {
      target.innerHTML = '<p class="empty">Sin datos de fuentes.</p>';
      return;
    }

    target.innerHTML = sources.map((item) => `
      <div class="status-line">
        <div>
          <strong>${escapeHtml(item.name || item.source_id || "Fuente")}</strong><br />
          <small>${escapeHtml(item.method || "")} · ${escapeHtml(item.count ?? 0)} publicaciones</small>
        </div>
        <span class="${item.ok ? "ok" : "bad"}">${item.ok ? "OK" : "ERROR"}</span>
      </div>
    `).join("");
  }

  function renderSocial(data) {
    const statuses = Array.isArray(data.posts?.social_integration_status)
      ? data.posts.social_integration_status
      : [];
    const log = Array.isArray(data.socialLog?.entries) ? data.socialLog.entries : [];
    const target = document.getElementById("socialStatus");

    const latestByPlatform = {};
    for (const entry of log) {
      const platform = entry.platform || "social";
      if (!latestByPlatform[platform] || new Date(entry.recorded_at) > new Date(latestByPlatform[platform].recorded_at)) {
        latestByPlatform[platform] = entry;
      }
    }

    const blocks = [];

    for (const item of statuses) {
      blocks.push(`
        <div class="status-line">
          <div><strong>${escapeHtml(item.name || item.source_id || "Meta")}</strong><br />
          <small>${escapeHtml(item.error || item.status || "")}</small></div>
          <span class="${item.ok ? "ok" : item.error ? "bad" : "pending"}">${item.ok ? "OK" : item.error ? "ERROR" : "PENDIENTE"}</span>
        </div>
      `);
    }

    for (const [platform, entry] of Object.entries(latestByPlatform)) {
      blocks.push(`
        <div class="status-line">
          <div><strong>Última publicación ${escapeHtml(platform)}</strong><br />
          <small>${escapeHtml(formatDate(entry.recorded_at))}</small></div>
          <span class="${entry.status === "success" ? "ok" : "bad"}">${escapeHtml(entry.status || "")}</span>
        </div>
      `);
    }

    target.innerHTML = blocks.length ? blocks.join("") : '<p class="empty">Sin actividad social registrada.</p>';
  }

  function filteredPosts() {
    const posts = Array.isArray(statusPayload?.posts?.posts) ? statusPayload.posts.posts : [];
    const query = String(postSearch.value || "").trim().toLocaleLowerCase("es");
    if (!query) return posts;
    return posts.filter((post) => {
      const haystack = [post.title, post.summary, post.source, post.category].join(" ").toLocaleLowerCase("es");
      return haystack.includes(query);
    });
  }

  function renderPosts() {
    const target = document.getElementById("postList");
    const posts = filteredPosts().slice(0, 120);

    if (!posts.length) {
      target.innerHTML = '<p class="empty">No hay publicaciones.</p>';
    } else {
      target.innerHTML = posts.map((post) => {
        const own = post.source_type === "own";
        return `
          <article class="post-item">
            <header><h4>${escapeHtml(post.title || "Sin título")}</h4></header>
            <div class="post-meta">${escapeHtml(post.source || "")} · ${escapeHtml(post.category || "")} · ${escapeHtml(formatDate(post.published_at))}</div>
            <div class="post-actions">
              ${post.url ? `<a class="button-link" href="${escapeHtml(post.url)}" target="_blank" rel="noopener">Abrir</a>` : ""}
              <label>Tipo
                <select id="post-category-${escapeHtml(post.id)}" data-category-select>
                  ${["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics"].map((category) =>
                    `<option value="${category}"${post.category === category ? " selected" : ""}>${({news:"Noticias", agenda:"Agenda", alerts:"Avisos", services:"Servicios", culture:"Cultura", sports:"Deportes", commerce:"Comercio", politics:"Política"})[category]}</option>`
                  ).join("")}
                </select>
              </label>
              <button type="button" data-action="reclassify" data-post-id="${escapeHtml(post.id)}">Guardar tipo</button>
              ${own
                ? `<button type="button" data-edit-id="${escapeHtml(post.id)}">Editar</button>
                   <button class="danger" type="button" data-action="delete-own" data-post-id="${escapeHtml(post.id)}">Eliminar</button>`
                : `<button type="button" data-action="hide" data-post-id="${escapeHtml(post.id)}">Ocultar</button>`
              }
            </div>
          </article>
        `;
      }).join("");
    }

    target.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const select = document.getElementById("post-category-" + button.dataset.postId);
        moderate(button.dataset.action, button.dataset.postId, select?.value || "");
      });
    });
    target.querySelectorAll("[data-edit-id]").forEach((button) => {
      button.addEventListener("click", () => startEdit(button.dataset.editId));
    });

    renderHidden();
    renderSocialLinkPosts();
  }

  function renderSocialLinkPosts() {
    const posts = Array.isArray(statusPayload?.posts?.posts) ? statusPayload.posts.posts : [];
    const links = posts.filter((post) => post.source_type === "own" && post.original_url);
    if (!links.length) {
      socialLinkList.innerHTML = '<p class="empty">Todavía no hay enlaces de redes publicados.</p>';
      return;
    }
    socialLinkList.innerHTML = links.slice(0, 80).map((post) => `
      <article class="post-item">
        <header><h4>${escapeHtml(post.title || "Sin título")}</h4></header>
        <div class="post-meta">${escapeHtml(post.source || "")} · ${escapeHtml(post.category || "")} · ${escapeHtml(formatDate(post.published_at))}</div>
        <div class="post-actions">
          ${post.url ? `<a class="button-link" href="${escapeHtml(post.url)}" target="_blank" rel="noopener">Abrir en la web</a>` : ""}
          <a class="button-link" href="${escapeHtml(post.original_url)}" target="_blank" rel="noopener">Original</a>
          <button type="button" data-social-link-edit-id="${escapeHtml(post.id)}">Editar</button>
          <button class="danger" type="button" data-action="delete-own" data-post-id="${escapeHtml(post.id)}">Eliminar</button>
        </div>
      </article>
    `).join("");
    socialLinkList.querySelectorAll("[data-social-link-edit-id]").forEach((button) => {
      button.addEventListener("click", () => startSocialLinkEdit(button.dataset.socialLinkEditId));
    });
    socialLinkList.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => moderate(button.dataset.action, button.dataset.postId));
    });
  }

  function renderHidden() {
    const target = document.getElementById("hiddenList");
    const hidden = Array.isArray(statusPayload?.moderation?.hidden_post_ids)
      ? statusPayload.moderation.hidden_post_ids
      : [];
    const archived = statusPayload?.moderation?.hidden_posts || {};

    if (!hidden.length) {
      target.innerHTML = '<p class="empty">No hay publicaciones ocultadas.</p>';
      return;
    }

    target.innerHTML = hidden.map((id) => {
      const post = archived[id] || {};
      return `
        <article class="post-item">
          <h4>${escapeHtml(post.title || id)}</h4>
          <div class="post-meta">${escapeHtml(post.source || "Publicación")} · Ocultada del feed</div>
          <div class="post-actions">
            <button type="button" data-unhide-id="${escapeHtml(id)}">Restaurar</button>
          </div>
        </article>
      `;
    }).join("");

    target.querySelectorAll("[data-unhide-id]").forEach((button) => {
      button.addEventListener("click", () => moderate("unhide", button.dataset.unhideId));
    });
  }


  function openModule(viewId) {
    document.querySelectorAll(".nav-button").forEach((item) => {
      item.classList.toggle("active", item.dataset.view === viewId);
    });
    document.querySelectorAll(".module").forEach((item) => {
      item.classList.toggle("active", item.id === viewId);
    });
  }

  function resetEditMode(resetForm = false) {
    editPostId = "";
    publishHeading.textContent = "Nueva publicación";
    editModeNote.hidden = true;
    publishSubmitButton.textContent = "Publicar";
    cancelEditButton.hidden = true;
    facebookInput.disabled = false;
    instagramInput.disabled = false;

    if (resetForm) {
      publishForm.reset();
      previewTitle.textContent = "Título de la publicación";
      previewBody.textContent = "El texto aparecerá aquí.";
    }
    setMessage(publishMessage, "");
  }

  function startEdit(postId) {
    const posts = Array.isArray(statusPayload?.posts?.posts) ? statusPayload.posts.posts : [];
    const post = posts.find((item) => item.id === postId && item.source_type === "own");
    if (!post) {
      setMessage(moderationMessage, "No se ha podido cargar esta publicación propia.", "error");
      return;
    }

    editPostId = postId;
    publishForm.elements.title.value = post.title || "";
    publishForm.elements.body.value = post.summary || "";
    publishForm.elements.category.value = post.category || "news";
    publishForm.elements.language.value = post.language || "ca";
    const mediaUrl = String(post.media_url || "");
    publishForm.elements.image_url.value = mediaUrl.includes("/assets/generated/") ? "" : mediaUrl;
    facebookInput.checked = false;
    instagramInput.checked = false;
    facebookInput.disabled = true;
    instagramInput.disabled = true;

    publishHeading.textContent = "Editar publicación";
    editModeNote.hidden = false;
    publishSubmitButton.textContent = "Guardar cambios";
    cancelEditButton.hidden = false;
    previewTitle.textContent = post.title || "Título de la publicación";
    previewBody.textContent = post.summary || "El texto aparecerá aquí.";
    setMessage(publishMessage, "");
    openModule("publish");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetSocialLinkEditMode(resetForm = false) {
    socialLinkEditPostId = "";
    socialLinkHeading.textContent = "Enlace de una red social";
    socialLinkEditNote.hidden = true;
    socialLinkSubmitButton.textContent = "Publicar propuesta revisada";
    cancelSocialLinkEditButton.hidden = true;
    socialLinkForm.elements.source_name.readOnly = false;
    socialLinkForm.elements.original_url.readOnly = false;
    socialLinkForm.elements.instagram.disabled = false;
    if (resetForm) socialLinkForm.reset();
    setMessage(socialLinkMessage, "");
  }

  function startSocialLinkEdit(postId) {
    const posts = Array.isArray(statusPayload?.posts?.posts) ? statusPayload.posts.posts : [];
    const post = posts.find((item) => item.id === postId && item.source_type === "own" && item.original_url);
    if (!post) {
      setMessage(socialLinkMessage, "No se ha podido cargar este enlace de redes.", "error");
      return;
    }
    socialLinkEditPostId = postId;
    socialLinkForm.elements.source_name.value = post.source || "";
    socialLinkForm.elements.original_url.value = post.original_url || "";
    socialLinkForm.elements.title.value = post.title || "";
    socialLinkForm.elements.body.value = post.summary || "";
    socialLinkForm.elements.category.value = post.category || "politics";
    socialLinkForm.elements.language.value = post.language || "ca";
    socialLinkForm.elements.instagram.checked = false;
    socialLinkForm.elements.source_name.readOnly = true;
    socialLinkForm.elements.original_url.readOnly = true;
    socialLinkForm.elements.instagram.disabled = true;
    socialLinkHeading.textContent = "Editar enlace de redes";
    socialLinkEditNote.hidden = false;
    socialLinkSubmitButton.textContent = "Guardar cambios";
    cancelSocialLinkEditButton.hidden = false;
    setMessage(socialLinkMessage, "");
    openModule("social-links");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function waitForOwnEdit(postId, expected, messageElement = publishMessage) {
    for (let attempt = 1; attempt <= 15; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      const publicState = await readPublicState();
      const post = (publicState.posts?.posts || []).find((item) => item.id === postId);
      if (
        post &&
        post.title === expected.title &&
        post.summary === expected.body &&
        post.category === expected.category &&
        post.language === expected.language
      ) {
        return true;
      }
      setMessage(messageElement, "Guardando cambios… " + attempt + "/15");
    }
    return false;
  }

  async function runSystemCheck() {
    systemCheckButton.disabled = true;
    systemCheckButton.textContent = "Comprobando…";
    systemCheckResult.hidden = false;
    systemCheckResult.innerHTML = "<p>Comprobando Cloudflare, GitHub y workflows…</p>";

    try {
      const result = await api("/api/check");
      const checks = Array.isArray(result.checks) ? result.checks : [];
      systemCheckResult.innerHTML = `
        <h3>Comprobación del sistema</h3>
        ${checks.map((item) => `
          <div class="status-line">
            <div>
              <strong>${escapeHtml(item.name || "Comprobación")}</strong><br />
              <small>${escapeHtml(item.detail || "")}</small>
            </div>
            <span class="${item.ok ? "ok" : "bad"}">${item.ok ? "OK" : "ERROR"}</span>
          </div>
        `).join("")}
      `;
    } catch (error) {
      systemCheckResult.innerHTML = '<p class="bad">' + escapeHtml(error.message) + '</p>';
    } finally {
      systemCheckButton.disabled = false;
      systemCheckButton.textContent = "Comprobar sistema";
    }
  }

  async function loadStatus() {
    const buttonText = refreshButton.textContent;
    refreshButton.disabled = true;
    refreshButton.textContent = "Actualizando…";
    try {
      statusPayload = await api("/api/status");
      statusPayload = await mergePublicState(statusPayload);
      renderMetrics(statusPayload);
      renderSources(statusPayload);
      renderSocial(statusPayload);
      renderPosts();
    } catch (error) {
      document.getElementById("connectionState").textContent = "Error";
      document.getElementById("connectionState").className = "status-pill bad";
      setMessage(moderationMessage, error.message, "error");
    } finally {
      refreshButton.disabled = false;
      refreshButton.textContent = buttonText;
    }
  }

  function moderationApplied(data, action, postId, category = "") {
    const posts = Array.isArray(data?.posts?.posts) ? data.posts.posts : [];
    const hidden = Array.isArray(data?.moderation?.hidden_post_ids)
      ? data.moderation.hidden_post_ids
      : [];
    const targetPost = posts.find((post) => post.id === postId);
    const present = Boolean(targetPost);
    const isHidden = hidden.includes(postId);

    if (action === "hide") return isHidden && !present;
    if (action === "unhide") return !isHidden && present;
    if (action === "delete-own") return !present && !isHidden;
    if (action === "reclassify") return present && targetPost.category === category;
    return false;
  }

  async function waitForModeration(action, postId, category = "") {
    const attempts = 12;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      const data = await api("/api/status");
      await mergePublicState(data);
      statusPayload = data;
      renderMetrics(data);
      renderSources(data);
      renderSocial(data);
      renderPosts();

      if (moderationApplied(data, action, postId, category)) return true;
      setMessage(
        moderationMessage,
        "Procesando en GitHub… " + attempt + "/" + attempts
      );
    }
    return false;
  }

  async function moderate(action, postId, category = "") {
    const labels = {
      "delete-own": "eliminar definitivamente esta publicación propia",
      "hide": "ocultar esta publicación",
      "unhide": "restaurar esta publicación",
      "reclassify": "cambiar el tipo de esta publicación a " + category,
    };
    if (!confirm("¿Confirmas que quieres " + (labels[action] || "realizar esta acción") + "?")) return;

    setMessage(moderationMessage, "Enviando acción…");
    try {
      await api("/api/moderate", {
        method: "POST",
        body: JSON.stringify({ action, post_id: postId, category }),
      });

      const applied = await waitForModeration(action, postId, category);
      if (applied) {
        const doneLabels = {
          "hide": "Publicación ocultada correctamente.",
          "unhide": "Publicación restaurada correctamente.",
          "delete-own": "Publicación eliminada correctamente.",
          "reclassify": "Tipo de publicación actualizado correctamente.",
        };
        setMessage(moderationMessage, doneLabels[action] || "Acción completada.", "success");
      } else {
        setMessage(
          moderationMessage,
          "La acción se ha enviado, pero está tardando más de lo previsto. Pulsa Actualizar en unos segundos.",
          "error"
        );
      }
    } catch (error) {
      setMessage(moderationMessage, error.message, "error");
    }
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setMessage(loginMessage, "Comprobando…");
    const password = new FormData(loginForm).get("password");

    try {
      const result = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setToken(result.token || "");
      loginForm.reset();
      setMessage(loginMessage, "");
      showAdmin();
      await loadStatus();
    } catch (error) {
      setMessage(loginMessage, error.message, "error");
    }
  });

  logoutButton.addEventListener("click", () => {
    setToken("");
    showLogin();
  });

  refreshButton.addEventListener("click", loadStatus);
  systemCheckButton.addEventListener("click", runSystemCheck);
  postSearch.addEventListener("input", renderPosts);

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => openModule(button.dataset.view));
  });

  cancelEditButton.addEventListener("click", () => {
    resetEditMode(true);
    openModule("moderation");
  });

  cancelSocialLinkEditButton.addEventListener("click", () => {
    resetSocialLinkEditMode(true);
  });

  async function manualLinksReady() {
    try {
      const response = await fetch(API + "/health", { cache: "no-store", mode: "cors" });
      const health = await response.json();
      return Boolean(health?.capabilities?.includes("manual_social_links"));
    } catch (_) {
      return false;
    }
  }

  socialLinkForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!await manualLinksReady()) {
      setMessage(socialLinkMessage, "El módulo está listo en la web, pero falta desplegar el Worker actualizado en Cloudflare. No se ha publicado nada.", "error");
      return;
    }
    const data = new FormData(socialLinkForm);
    const payload = {
      source_name: String(data.get("source_name") || "").trim(),
      original_url: String(data.get("original_url") || "").trim(),
      title: String(data.get("title") || "").trim(),
      body: String(data.get("body") || "").trim(),
      category: String(data.get("category") || "politics"),
      language: String(data.get("language") || "ca"),
      image_url: "",
      facebook: false,
      instagram: data.get("instagram") === "on",
    };
    if (!payload.source_name || !payload.original_url || !payload.title || !payload.body) return;

    const editing = Boolean(socialLinkEditPostId);
    if (editing) {
      payload.post_id = socialLinkEditPostId;
      payload.instagram = false;
      if (!confirm("¿Guardar los cambios de este enlace en Sóller Ara?")) return;
    } else if (!confirm("¿Publicar esta propuesta revisada en Sóller Ara" + (payload.instagram ? " e Instagram" : "") + "?")) {
      return;
    }

    socialLinkSubmitButton.disabled = true;
    setMessage(socialLinkMessage, editing ? "Enviando cambios…" : "Enviando publicación…");
    try {
      if (editing) {
        await api("/api/edit", { method: "POST", body: JSON.stringify(payload) });
        const applied = await waitForOwnEdit(socialLinkEditPostId, payload, socialLinkMessage);
        if (!applied) {
          setMessage(socialLinkMessage, "Los cambios están tardando más de lo previsto. Actualiza en unos segundos.", "error");
          return;
        }
        setMessage(socialLinkMessage, "Enlace actualizado correctamente en Sóller Ara.", "success");
        resetSocialLinkEditMode(true);
        await loadStatus();
      } else {
        const result = await api("/api/publish", { method: "POST", body: JSON.stringify(payload) });
        setMessage(socialLinkMessage, "Publicación enviada. Workflow: " + (result.workflow || "iniciado") + ".", "success");
        socialLinkForm.reset();
        setTimeout(loadStatus, 4500);
      }
    } catch (error) {
      setMessage(socialLinkMessage, error.message, "error");
    } finally {
      socialLinkSubmitButton.disabled = false;
    }
  });

  publishForm.addEventListener("input", () => {
    const data = new FormData(publishForm);
    previewTitle.textContent = data.get("title") || "Título de la publicación";
    previewBody.textContent = data.get("body") || "El texto aparecerá aquí.";
  });

  publishForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(publishForm);
    const payload = {
      title: String(data.get("title") || "").trim(),
      body: String(data.get("body") || "").trim(),
      category: String(data.get("category") || "news"),
      language: String(data.get("language") || "ca"),
      image_url: String(data.get("image_url") || "").trim(),
      facebook: data.get("facebook") === "on",
      instagram: data.get("instagram") === "on",
    };

    if (!payload.title || !payload.body) return;

    const editing = Boolean(editPostId);
    if (editing) {
      payload.post_id = editPostId;
      payload.facebook = false;
      payload.instagram = false;
      if (!confirm("¿Guardar los cambios de esta publicación en Sóller Ara?")) return;
    } else if (!confirm("¿Publicar ahora en Sóller Ara" +
      (payload.facebook ? ", Facebook" : "") +
      (payload.instagram ? " e Instagram" : "") + "?")) {
      return;
    }

    setMessage(publishMessage, editing ? "Enviando cambios…" : "Enviando publicación…");
    publishSubmitButton.disabled = true;

    try {
      if (editing) {
        await api("/api/edit", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        const applied = await waitForOwnEdit(editPostId, payload);
        if (!applied) {
          setMessage(publishMessage, "Los cambios están tardando más de lo previsto. Actualiza en unos segundos.", "error");
          return;
        }
        setMessage(publishMessage, "Publicación actualizada correctamente.", "success");
        resetEditMode(true);
        await loadStatus();
        openModule("moderation");
      } else {
        const result = await api("/api/publish", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setMessage(publishMessage, "Publicación enviada. Workflow: " + (result.workflow || "iniciado") + ".", "success");
        publishForm.reset();
        previewTitle.textContent = "Título de la publicación";
        previewBody.textContent = "El texto aparecerá aquí.";
        setTimeout(loadStatus, 4500);
      }
    } catch (error) {
      setMessage(publishMessage, error.message, "error");
    } finally {
      publishSubmitButton.disabled = false;
    }
  });

  if (!API) {
    setupMessage.hidden = false;
    loginForm.querySelector("button").disabled = true;
    setMessage(loginMessage, "Falta conectar el backend privado.");
    return;
  }

  if (getToken()) {
    showAdmin();
    loadStatus().catch(() => showLogin());
  } else {
    showLogin();
  }
})();
