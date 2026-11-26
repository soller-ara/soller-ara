const DEFAULT_ORIGIN = "https://soller-ara.github.io";
const DEFAULT_OWNER = "soller-ara";
const DEFAULT_REPO = "soller-ara";
const DEFAULT_BRANCH = "main";
const SESSION_SECONDS = 8 * 60 * 60;

const failedLogins = new Map();
const watchdogDispatches = new Map();
let watchdogInFlight = null;

export default {
  async scheduled(controller, env) {
    if (controller?.cron === WATCH_CRON) return watchTick(env);
    // The workflow checks freshness again under its existing global lock.
    // That second check also protects against separate Worker instances racing.
    if (watchdogInFlight) return watchdogInFlight;
    watchdogInFlight = collectionWatchdog(env).then((result) => {
      console.log("COLLECTION_WATCHDOG " + JSON.stringify(result));
      return result;
    }).catch(() => {
      console.error("COLLECTION_WATCHDOG: check failed; no further dispatch attempted.");
      throw new Error("Collection watchdog failed");
    }).finally(() => { watchdogInFlight = null; });
    return watchdogInFlight;
  },
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || DEFAULT_ORIGIN;
    const cors = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);

    try {
      if (url.pathname === "/health") {
        return json({ ok: true, service: "soller-ara-admin", version: "0.76", watchdog_stale_after_minutes: 60, capabilities: ["social_settings", "web_analytics", "manual_social_links", "manual_collection", "collection_watchdog", "social_watch"] }, 200, cors);
      }

      if (url.pathname === "/api/login" && request.method === "POST") {
        return await login(request, env, cors);
      }

      const session = await requireSession(request, env);
      if (!session) return json({ error: "Sesión no válida o caducada." }, 401, cors);

      if (url.pathname === "/api/social-watch") return await watchApi(request, env, cors);
      if (url.pathname === "/api/analytics" && request.method === "GET") {
        return await webAnalytics(url, env, cors);
      }

      if (url.pathname === "/api/status" && request.method === "GET") {
        return await status(env, cors);
      }

      if (url.pathname === "/api/check" && request.method === "GET") {
        return await systemCheck(env, cors);
      }

      if (url.pathname === "/api/publish" && request.method === "POST") {
        return await publish(request, env, cors);
      }

      if (url.pathname === "/api/edit" && request.method === "POST") {
        return await editOwn(request, env, cors);
      }

      if (url.pathname === "/api/source" && request.method === "POST") {
        return await manageSource(request, env, cors);
      }

      if (url.pathname === "/api/collect" && ["GET", "POST"].includes(request.method)) {
        return await collectNow(request, env, cors);
      }

      if (url.pathname === "/api/social-settings" && request.method === "POST") {
        return await manageSocialSettings(request, env, cors);
      }

      if (url.pathname === "/api/moderate" && request.method === "POST") {
        return await moderate(request, env, cors);
      }

      return json({ error: "Ruta no encontrada." }, 404, cors);
    } catch (error) {
      console.error(error);
      return json({ error: "Error interno de Administración." }, 500, cors);
    }
  },
};

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
    "Cache-Control": "no-store",
  };
}

function json(payload, status = 200, extra = {}) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { ...extra, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function sha256(value) {
  const data = new TextEncoder().encode(String(value));
  return new Uint8Array(await crypto.subtle.digest("SHA-256", data));
}

function equalBytes(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function secureEqual(a, b) {
  const [ha, hb] = await Promise.all([sha256(a), sha256(b)]);
  return equalBytes(ha, hb);
}

function clientIp(request) {
  return request.headers.get("CF-Connecting-IP") || "unknown";
}

function loginState(ip) {
  const now = Date.now();
  const item = failedLogins.get(ip);
  if (!item || now - item.first > 15 * 60 * 1000) {
    const fresh = { first: now, count: 0 };
    failedLogins.set(ip, fresh);
    return fresh;
  }
  return item;
}

async function login(request, env, cors) {
  if (!env.ADMIN_PASSWORD || !env.SESSION_SECRET) {
    return json({ error: "Administración no configurada." }, 503, cors);
  }

  const ip = clientIp(request);
  const state = loginState(ip);
  if (state.count >= 5) {
    return json({ error: "Demasiados intentos. Prueba más tarde." }, 429, cors);
  }

  const body = await request.json().catch(() => ({}));
  const supplied = String(body.password || "");

  if (!await secureEqual(supplied, env.ADMIN_PASSWORD)) {
    state.count += 1;
    failedLogins.set(ip, state);
    return json({ error: "Clave incorrecta." }, 401, cors);
  }

  failedLogins.delete(ip);
  const token = await createSession(env.SESSION_SECRET);
  return json({ ok: true, token, expires_in: SESSION_SECONDS }, 200, cors);
}

function base64urlBytes(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64urlText(value) {
  return base64urlBytes(new TextEncoder().encode(value));
}

function decodeBase64urlText(value) {
  const padded = value.replaceAll("-", "+").replaceAll("_", "/") + "===".slice((value.length + 3) % 4);
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

async function hmac(secret, value) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
}

async function createSession(secret) {
  const payload = {
    sub: "admin",
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + SESSION_SECONDS,
  };
  const encoded = base64urlText(JSON.stringify(payload));
  const signature = base64urlBytes(await hmac(secret, encoded));
  return encoded + "." + signature;
}

async function verifySession(secret, token) {
  const [encoded, signature] = String(token || "").split(".");
  if (!encoded || !signature) return null;

  const expected = base64urlBytes(await hmac(secret, encoded));
  if (!await secureEqual(signature, expected)) return null;

  try {
    const payload = JSON.parse(decodeBase64urlText(encoded));
    if (!payload.exp || payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch (_) {
    return null;
  }
}

async function requireSession(request, env) {
  if (!env.SESSION_SECRET) return null;
  const auth = request.headers.get("Authorization") || "";
  if (!auth.startsWith("Bearer ")) return null;
  return verifySession(env.SESSION_SECRET, auth.slice(7));
}

function isSafeHttpsUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password && Boolean(url.hostname);
  } catch (_) {
    return false;
  }
}

function repoParts(env) {
  return {
    owner: env.GITHUB_OWNER || DEFAULT_OWNER,
    repo: env.GITHUB_REPO || DEFAULT_REPO,
    branch: env.GITHUB_BRANCH || DEFAULT_BRANCH,
  };
}

async function rawJson(owner, repo, branch, path, fallback) {
  const url = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${path}?v=${Date.now()}`;
  const response = await fetch(url, { headers: { "Cache-Control": "no-cache" } });
  if (!response.ok) return fallback;
  return response.json();
}

async function systemCheck(env, cors) {
  const checks = [];
  const { owner, repo, branch } = repoParts(env);

  checks.push({
    name: "Cloudflare Worker",
    ok: true,
    detail: "Backend de Administración activo",
  });

  checks.push({
    name: "Clave de Administración",
    ok: Boolean(env.ADMIN_PASSWORD),
    detail: env.ADMIN_PASSWORD ? "Secret configurado" : "Falta ADMIN_PASSWORD",
  });

  checks.push({
    name: "Sesiones",
    ok: Boolean(env.SESSION_SECRET),
    detail: env.SESSION_SECRET ? "SESSION_SECRET configurado" : "Falta SESSION_SECRET",
  });

  if (!env.GITHUB_TOKEN) {
    checks.push({ name: "GitHub", ok: false, detail: "Falta GITHUB_TOKEN" });
    return json({ ok: false, checks }, 200, cors);
  }

  const headers = {
    "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "SollerAra-Admin/0.44",
  };

  const repoResponse = await fetch(`https://api.github.com/repos/${owner}/${repo}`, { headers });
  checks.push({
    name: "GitHub · repositorio",
    ok: repoResponse.ok,
    detail: repoResponse.ok ? `${owner}/${repo} accesible` : `HTTP ${repoResponse.status}`,
  });

  const workflows = [
    "publish-own-content.yml",
    "edit-own-content.yml",
    "manage-posts.yml",
    "manage-sources.yml",
    "manage-social-settings.yml",
    "update-sources.yml",
  ];
  for (const workflow of workflows) {
    const response = await fetch(
      `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}`,
      { headers }
    );
    checks.push({
      name: `Workflow · ${workflow}`,
      ok: response.ok,
      detail: response.ok ? "Disponible para Administración" : `HTTP ${response.status}`,
    });
  }

  const publicData = await fetch(
    `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/data/posts.json?v=${Date.now()}`,
    { headers: { "Cache-Control": "no-cache" } }
  );
  checks.push({
    name: "Datos públicos",
    ok: publicData.ok,
    detail: publicData.ok ? "data/posts.json accesible" : `HTTP ${publicData.status}`,
  });

  return json({ ok: checks.every((item) => item.ok), checks }, 200, cors);
}

async function status(env, cors) {
  const { owner, repo, branch } = repoParts(env);
  const [posts, moderation, socialLog] = await Promise.all([
    rawJson(owner, repo, branch, "data/posts.json", { posts: [], source_status: [], social_integration_status: [] }),
    rawJson(owner, repo, branch, "data/moderation.json", { hidden_post_ids: [] }),
    rawJson(owner, repo, branch, "data/social_publish_log.json", { entries: [] }),
  ]);

  return json({ ok: true, posts, moderation, socialLog }, 200, cors);
}

async function collectionWatchdog(env) {
  if (env.COLLECTION_WATCHDOG_ENABLED === "false") return { action: "disabled" };
  if (!env.GITHUB_TOKEN) return { action: "not_configured" };
  const now = Date.now();
  const staleAfter = 1 * 60 * 60 * 1000;
  const retryAfter = 60 * 60 * 1000;
  const { owner, repo, branch } = repoParts(env);
  const key = `${owner}/${repo}/${branch}`;
  const headers = {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "SollerAra-Watchdog/0.73",
  };
  const dataResponse = await fetch(
    `https://raw.githubusercontent.com/${owner}/${repo}/${encodeURIComponent(branch)}/data/posts.json?v=${now}`,
    { headers: { "Cache-Control": "no-cache" }, signal: AbortSignal.timeout(15000) }
  );
  if (!dataResponse.ok) throw new Error("Cannot read collection data");
  const data = await dataResponse.json();
  // Manual publications refresh fetched_at. It must never mask a stale review.
  const checked = typeof data.sources_checked_at === "string" && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(data.sources_checked_at)
    ? Date.parse(data.sources_checked_at) : NaN;
  if (!Number.isFinite(checked) || checked > now + 5 * 60 * 1000) {
    return { action: "invalid_timestamp" };
  }
  if (now - checked <= staleAfter) return { action: "fresh", sources_checked_at: data.sources_checked_at };
  if (watchdogDispatches.has(key) && now - watchdogDispatches.get(key) < retryAfter) {
    return { action: "recent_attempt" };
  }
  const runsResponse = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/update-sources.yml/runs?branch=${encodeURIComponent(branch)}&per_page=100`,
    { headers, signal: AbortSignal.timeout(15000) }
  );
  if (!runsResponse.ok) throw new Error("Cannot read collection workflow runs");
  const runs = await runsResponse.json();
  if (!Array.isArray(runs.workflow_runs)) throw new Error("Invalid collection workflow response");
  for (const run of runs.workflow_runs) {
    if (!run || !run.id || typeof run.status !== "string") throw new Error("Invalid collection workflow run");
    if (run.status !== "completed") return { action: "already_running", run_id: run.id };
    const created = Date.parse(run.created_at || "");
    const started = run.run_started_at ? Date.parse(run.run_started_at) : created;
    if (!Number.isFinite(created) || !Number.isFinite(started) || Math.max(created, started) > now + 5 * 60 * 1000) {
      throw new Error("Invalid workflow run time");
    }
    if (now - Math.max(created, started) < retryAfter) return { action: "recent_attempt", run_id: run.id };
  }
  // Remember even an uncertain response locally. Do not immediately retry a POST
  // that GitHub might have accepted. The run list provides cross-tick backoff.
  watchdogDispatches.set(key, now);
  await githubDispatch(env, "update-sources.yml", { watchdog: true }, AbortSignal.timeout(20000));
  return { action: "dispatched", sources_checked_at: data.sources_checked_at };
}

async function githubDispatch(env, workflow, inputs, signal) {
  if (!env.GITHUB_TOKEN) throw new Error("Falta GITHUB_TOKEN");
  const { owner, repo, branch } = repoParts(env);

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      ...(signal ? { signal } : {}),
      headers: {
        "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SollerAra-Admin/0.44",
      },
      body: JSON.stringify({ ref: branch, inputs }),
    }
  );

  if (response.status !== 204) {
    const text = await response.text();
    console.error("GitHub dispatch error", response.status, text);
    throw new Error("GitHub no ha aceptado el workflow");
  }
}

async function collectNow(request, env, cors) {
  if (!env.GITHUB_TOKEN) return json({ error: "GitHub no está configurado." }, 503, cors);
  const { owner, repo, branch } = repoParts(env);
  const runId = new URL(request.url).searchParams.get("run_id");
  if (runId && !/^\d+$/.test(runId)) return json({ error: "Revisión no válida." }, 400, cors);
  const tracking = request.method === "GET" && runId;
  const path = tracking ? `actions/runs/${runId}`
    : `actions/workflows/update-sources.yml/runs?branch=${encodeURIComponent(branch)}&per_page=5`;
  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/${path}`,
    { headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "User-Agent": "SollerAra-Admin/0.71" } }
  );
  if (!response.ok) return json({ error: "No se ha podido consultar la revisión. Prueba de nuevo." }, 503, cors);
  const payload = await response.json();
  if (tracking) {
    if (!payload.id || !payload.status) return json({ error: "Respuesta de GitHub no válida." }, 503, cors);
    return json({ ok: true, run: {id: payload.id, status: payload.status, conclusion: payload.conclusion, url: payload.html_url} }, 200, cors);
  }
  if (!Array.isArray(payload.workflow_runs)) return json({ error: "Respuesta de GitHub no válida." }, 503, cors);
  const active = payload.workflow_runs.find((run) => run.status !== "completed");
  const current = active || payload.workflow_runs[0];
  const run = current ? { id: current.id, status: current.status, conclusion: current.conclusion, url: current.html_url } : null;
  if (request.method === "GET") return json({ ok: true, run }, 200, cors);
  if (active) return json({ ok: true, already_running: true, run }, 202, cors);
  await githubDispatch(env, "update-sources.yml", {});
  return json({ ok: true, already_running: false, previous_run_id: current?.id || null }, 202, cors);
}

async function publish(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const title = String(body.title || "").trim();
  const text = String(body.body || "").trim();

  if (title.length > 180) return json({ error: "El título es demasiado largo." }, 400, cors);

  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics", "social"]);
  const allowedLanguages = new Set(["ca", "es", "en"]);
  const category = allowedCategories.has(body.category) ? body.category : "news";
  const language = allowedLanguages.has(body.language) ? body.language : "ca";
  const sourceName = String(body.source_name || "").trim();
  const originalUrl = String(body.original_url || "").trim();
  const contentType = body.content_type === "event_poster"
    ? "event_poster"
    : (sourceName || originalUrl ? "social_link" : "own");
  const imageUrl = String(body.image_url || "").trim();
  const showInNow = body.show_in_now !== false;

  if (sourceName && !originalUrl) {
    return json({ error: "Indica un enlace original junto con la fuente." }, 400, cors);
  }
  if (contentType !== "social_link" && (!title || !text)) {
    return json({ error: "Faltan título o texto." }, 400, cors);
  }
  if (Boolean(body.instagram) && (!title || !text)) {
    return json({ error: "Para publicar también en Instagram añade título y texto propios." }, 400, cors);
  }
  if (sourceName.length > 120) return json({ error: "El nombre de la fuente es demasiado largo." }, 400, cors);
  if (originalUrl && !isSafeHttpsUrl(originalUrl)) {
    return json({ error: "El enlace original debe ser una URL https válida." }, 400, cors);
  }
  if (imageUrl && !isSafeHttpsUrl(imageUrl)) {
    return json({ error: "La imagen debe ser una URL https directa y válida." }, 400, cors);
  }
  if (contentType === "event_poster" && (!imageUrl || !Boolean(body.image_authorized))) {
    return json({ error: "Un cartel requiere URL directa y autorización confirmada." }, 400, cors);
  }

  await githubDispatch(env, "publish-own-content.yml", {
    confirmation: "PUBLICAR",
    title,
    body: text,
    category,
    language,
    image_url: imageUrl,
    facebook: Boolean(body.facebook),
    instagram: Boolean(body.instagram),
    source_name: sourceName,
    original_url: originalUrl,
    content_type: contentType,
    show_in_now: showInNow,
  });

  return json({ ok: true, workflow: "Sóller Ara · publicar contingut propi" }, 202, cors);
}

async function editOwn(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const postId = String(body.post_id || "").trim();
  const title = String(body.title || "").trim();
  const text = String(body.body || "").trim();

  if (!postId) {
    return json({ error: "Falta la publicación que se debe editar." }, 400, cors);
  }
  if (title.length > 180) {
    return json({ error: "El título es demasiado largo." }, 400, cors);
  }

  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics", "social"]);
  const allowedLanguages = new Set(["ca", "es", "en"]);
  const category = allowedCategories.has(body.category) ? body.category : "news";
  const language = allowedLanguages.has(body.language) ? body.language : "ca";
  const sourceName = String(body.source_name || "").trim();
  const originalUrl = String(body.original_url || "").trim();
  const contentType = body.content_type === "event_poster"
    ? "event_poster"
    : (sourceName || originalUrl ? "social_link" : "own");
  const imageUrl = String(body.image_url || "").trim();
  const showInNow = body.show_in_now !== false;
  if (sourceName && !originalUrl) {
    return json({ error: "Indica un enlace original junto con la fuente." }, 400, cors);
  }
  if (contentType !== "social_link" && (!title || !text)) {
    return json({ error: "Faltan título o texto para esta publicación." }, 400, cors);
  }
  if (sourceName.length > 120 || (originalUrl && !isSafeHttpsUrl(originalUrl))) {
    return json({ error: "La fuente o el enlace original no son válidos." }, 400, cors);
  }
  if (imageUrl && !isSafeHttpsUrl(imageUrl)) {
    return json({ error: "La imagen debe ser una URL https directa y válida." }, 400, cors);
  }
  if (contentType === "event_poster" && (!imageUrl || !Boolean(body.image_authorized))) {
    return json({ error: "Un cartel requiere URL directa y autorización confirmada." }, 400, cors);
  }

  await githubDispatch(env, "edit-own-content.yml", {
    confirmation: "GUARDAR",
    post_id: postId,
    title,
    body: text,
    category,
    language,
    image_url: imageUrl,
    source_name: sourceName,
    original_url: originalUrl,
    content_type: contentType,
    show_in_now: showInNow,
  });

  return json({ ok: true, workflow: "Sóller Ara · editar contingut propi" }, 202, cors);
}

async function manageSource(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const sourceId = String(body.source_id || "").trim();
  const enabled = body.enabled;

  if (!sourceId || !/^[a-z0-9][a-z0-9-]{1,79}$/.test(sourceId)) {
    return json({ error: "Fuente no válida." }, 400, cors);
  }
  if (typeof enabled !== "boolean") {
    return json({ error: "Estado de fuente no válido." }, 400, cors);
  }

  await githubDispatch(env, "manage-sources.yml", {
    source_id: sourceId,
    enabled,
    confirmation: "CONFIRMAR",
  });

  return json({ ok: true, workflow: "Sóller Ara · gestionar fonts" }, 202, cors);
}

async function manageSocialSettings(request, env, cors) {
  const body = await request.json().catch(() => null);
  if (!body || typeof body !== "object" || Array.isArray(body)
      || Object.keys(body).some((key) => !["base_version", "enabled", "sources"].includes(key))
      || !Number.isInteger(body.base_version) || body.base_version < 1) {
    return json({ error: "Configuración de redes no válida." }, 400, cors);
  }
  if ("enabled" in body && typeof body.enabled !== "boolean") {
    return json({ error: "El estado de la automatización debe ser sí o no." }, 400, cors);
  }
  const rules = body.sources ?? {};
  if (!rules || typeof rules !== "object" || Array.isArray(rules) || Object.keys(rules).length > 100
      || (!("enabled" in body) && !Object.keys(rules).length)) {
    return json({ error: "No hay cambios válidos para guardar." }, 400, cors);
  }
  const { owner, repo, branch } = repoParts(env);
  const [config, sources] = await Promise.all([
    rawJson(owner, repo, branch, "social_distribution.json", null),
    rawJson(owner, repo, branch, "sources.json", null),
  ]);
  if (!config || !Array.isArray(sources?.sources)) {
    return json({ error: "No se ha podido comprobar la configuración actual. Prueba de nuevo." }, 503, cors);
  }
  if (config.version !== body.base_version) {
    return json({ error: "La configuración ha cambiado. Pulsa Actualizar antes de guardar." }, 409, cors);
  }
  const knownIds = new Set(sources.sources.map((source) => source.id));
  for (const [id, rule] of Object.entries(rules)) {
    if (!knownIds.has(id) || !rule || typeof rule !== "object" || Array.isArray(rule)
        || Object.keys(rule).length !== 2 || typeof rule.facebook !== "boolean" || typeof rule.instagram !== "boolean") {
      return json({ error: "La selección de fuentes o redes no es válida." }, 400, cors);
    }
  }
  const requestId = crypto.randomUUID();
  await githubDispatch(env, "manage-social-settings.yml", {
    confirmation: "GUARDAR", request_id: requestId, change: JSON.stringify(body),
  });
  return json({ ok: true, request_id: requestId }, 202, cors);
}

async function moderate(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const allowed = new Set(["hide", "unhide", "delete-own", "reclassify"]);
  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics", "social"]);
  const action = String(body.action || "");
  const postId = String(body.post_id || "").trim();
  const category = String(body.category || "");

  if (!allowed.has(action) || !postId || (action === "reclassify" && !allowedCategories.has(category))) {
    return json({ error: "Acción de moderación no válida." }, 400, cors);
  }

  await githubDispatch(env, "manage-posts.yml", {
    action,
    post_id: postId,
    note: "",
    category,
    confirmation: "CONFIRMAR",
  });

  return json({ ok: true, workflow: "Sóller Ara · gestionar publicacions" }, 202, cors);
}

// Private read-only analytics. Never send the Cloudflare API credential to browsers.
const analyticsCache = new Map();
async function webAnalytics(url, env, cors) {
  const period = url.searchParams.get("period") || "7d";
  const durations = { "24h": 86400000, "7d": 7 * 86400000 };
  if (!Object.hasOwn(durations, period)) {
    return json({ error: "Periodo no válido." }, 400, cors);
  }
  if (!env.CF_ANALYTICS_API_TOKEN || !/^[a-f0-9]{32}$/i.test(env.CF_ANALYTICS_ACCOUNT_ID || "")) {
    return json({ code: "analytics_not_configured", error: "La consulta de visitas está pendiente de conectar con Cloudflare." }, 503, cors);
  }
  const cached = analyticsCache.get(period);
  if (cached && cached.account === env.CF_ANALYTICS_ACCOUNT_ID &&
      cached.token === env.CF_ANALYTICS_API_TOKEN && Date.now() - cached.at < 300000) {
    return json(cached.payload, 200, cors);
  }
  const end = new Date();
  const start = new Date(end.getTime() - durations[period]);
  const query = `query SollerAraVisits($account: String!, $from: Time!, $to: Time!) {
    viewer { accounts(filter: {accountTag: $account}) {
      totals: rumPageloadEventsAdaptiveGroups(limit: 1, filter: {
        datetime_geq: $from, datetime_lt: $to,
        requestHost: "soller-ara.github.io", requestPath_like: "/soller-ara/%",
        requestPath_notlike: "/soller-ara/admin/%", requestPath_neq: "/soller-ara/admin"
      }) { count sum { visits } }
    } }
  }`;
  try {
    const response = await fetch("https://api.cloudflare.com/client/v4/graphql", {
      method: "POST",
      headers: { Authorization: `Bearer ${env.CF_ANALYTICS_API_TOKEN}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query, variables: {
        account: env.CF_ANALYTICS_ACCOUNT_ID, from: start.toISOString(), to: end.toISOString(),
      } }),
      signal: AbortSignal.timeout(15000),
    });
    const result = await response.json();
    if (!response.ok || result.errors?.length) {
      // Do not expose provider responses: they may contain account or credential details.
      return json({ code: "analytics_unavailable", error: "Cloudflare no ha permitido consultar las visitas. Hay que revisar el permiso de lectura y la configuración de la cuenta." }, 502, cors);
    }
    const accounts = result.data?.viewer?.accounts;
    if (!Array.isArray(accounts) || accounts.length !== 1 || !Array.isArray(accounts[0].totals)) {
      throw new Error("Missing analytics data");
    }
    const rows = accounts[0].totals;
    if (rows.length > 1) throw new Error("Unexpected analytics groups");
    let pageviews = 0, visits = 0;
    if (rows.length) {
      pageviews = rows[0].count;
      visits = rows[0].sum?.visits;
      if (![pageviews, visits].every(n => typeof n === "number" && Number.isFinite(n) && n >= 0)) {
        throw new Error("Invalid analytics metrics");
      }
    }
    const payload = {
      ok: true, period, from: start.toISOString(), to: end.toISOString(),
      fetched_at: new Date().toISOString(), visits: Math.round(visits), pageviews: Math.round(pageviews),
    };
    analyticsCache.set(period, { account: env.CF_ANALYTICS_ACCOUNT_ID, token: env.CF_ANALYTICS_API_TOKEN, at: Date.now(), payload });
    return json(payload, 200, cors);
  } catch (_) {
    return json({ code: "analytics_unavailable", error: "No se han podido leer las visitas. Prueba de nuevo dentro de unos minutos." }, 502, cors);
  }
}

// Private social watch. It owns only the watch_* tables and has no publication or GitHub path.
const WATCH_CRON = "7,22,37,52 * * * *";
const WATCH_DAY = 86400000;
const watchInit = new WeakMap();
const watchCalendar = new Intl.DateTimeFormat("sv-SE", {timeZone:"Europe/Madrid", year:"numeric", month:"2-digit", day:"2-digit"});
function watchSchema(db) {
  if (!watchInit.has(db)) watchInit.set(db, db.batch([
    db.prepare(`CREATE TABLE IF NOT EXISTS watch_accounts (
      id TEXT PRIMARY KEY, profile_key TEXT UNIQUE NOT NULL, network TEXT NOT NULL, handle TEXT NOT NULL,
      page_id TEXT NOT NULL DEFAULT '', label TEXT NOT NULL, profile TEXT NOT NULL, added INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', attempted INTEGER NOT NULL DEFAULT 0, completed INTEGER NOT NULL DEFAULT 0,
      earliest INTEGER NOT NULL DEFAULT 0, due INTEGER NOT NULL DEFAULT 0, lease TEXT NOT NULL DEFAULT '',
      cursor TEXT NOT NULL DEFAULT '', scan_from INTEGER NOT NULL DEFAULT 0, scan_start INTEGER NOT NULL DEFAULT 0, scan_partial INTEGER NOT NULL DEFAULT 0)`),
    db.prepare(`CREATE TABLE IF NOT EXISTS watch_posts (
      account TEXT NOT NULL REFERENCES watch_accounts(id) ON DELETE CASCADE, k TEXT PRIMARY KEY,
      stamp INTEGER NOT NULL, day TEXT NOT NULL, url TEXT NOT NULL, brief TEXT NOT NULL)`),
    db.prepare('CREATE INDEX IF NOT EXISTS watch_dates ON watch_posts(day,stamp,k)'),
  ]).catch(error => { watchInit.delete(db); throw error; }));
  return watchInit.get(db);
}
function watchFail(code, diagnostic) { const e = new Error(code); e.watchCode = code; if(diagnostic)e.watchDiagnostic=diagnostic; return e; }
function watchDiagnostic(error,stage) {
  // Only fixed labels and numeric codes may leave this reader. Never return/log raw errors, URLs or tokens.
  const detail={stage,reason:"unexpected"}, source=error?.watchDiagnostic||{};
  for(const key of ["http_status","meta_code","meta_subcode"])
    if(Number.isSafeInteger(source[key])&&source[key]>=0&&source[key]<=2147483647)detail[key]=source[key];
  if(["Error","TypeError","RangeError","SyntaxError","AbortError","TimeoutError"].includes(error?.name))detail.error_type=error.name;
  if(["AbortError","TimeoutError"].includes(error?.name))detail.reason="timeout";
  else if(["response_format","redirect"].includes(source.reason))detail.reason=source.reason;
  else if(stage==="meta"&&error?.name==="TypeError")
    detail.reason=/header|character|bytestring/i.test(String(error.message||""))?"request_headers":"network";
  const sqlite=String(error?.message||"").match(/\bSQLITE_(?:ERROR|BUSY|LOCKED|CONSTRAINT|FULL|TOOBIG|MISMATCH|RANGE|CORRUPT|IOERR)\b/);
  if(stage==="archive"&&sqlite)detail.db_code=sqlite[0];
  return detail;
}
function watchManualFailure(detail) {
  const message=detail.stage==="archive"?"La lectura se ha interrumpido al guardar en el archivo.":
    detail.stage==="meta"?(detail.reason==="timeout"?"Meta no ha respondido dentro del plazo de lectura.":
      detail.reason==="request_headers"?"El token de lectura no se puede enviar a Meta. Comprueba que se haya copiado completo y en una sola línea.":
      detail.reason==="response_format"?"Meta ha devuelto una respuesta que no se puede interpretar.":"La consulta a Meta no se ha completado."):
    "No se ha podido procesar la respuesta de lectura.";
  const codes=[];
  if(detail.http_status)codes.push("HTTP "+detail.http_status);
  if(detail.meta_code!==undefined)codes.push("Meta "+detail.meta_code);
  if(detail.meta_subcode!==undefined)codes.push("subcódigo "+detail.meta_subcode);
  if(detail.db_code)codes.push(detail.db_code);
  if(detail.error_type)codes.push(detail.error_type);
  return message+(codes.length?" Diagnóstico: "+codes.join(", ")+".":"")+" El archivo anterior se conserva.";
}
function watchUrl(value) {
  if (typeof value !== "string" || value.length > 1800) return null;
  try { const u=new URL(value); if (u.protocol!=="https:" || u.port || u.username || u.password) return null; return u; } catch { return null; }
}
function watchProfile(input) {
  const url=watchUrl(input.profile), label=String(input.name||"").trim().slice(0,90);
  if (!url || url.href.length>350) throw watchFail("profile");
  const host=url.hostname.replace(/^(www\.|m\.)/,""), path=url.pathname.replace(/^\/|\/$/g,"");
  let network, handle, profile, pageId="";
  if (host==="instagram.com" && /^[a-zA-Z0-9._]{1,30}$/.test(path) &&
      !/^(p|reels?|stories|explore|direct|accounts|share|tv|about|developer|legal|directory|web)$/i.test(path)) {
    network="instagram"; handle=path.toLowerCase(); profile="https://www.instagram.com/"+handle+"/";
  } else if (host==="facebook.com") {
    network="facebook"; handle=path;
    if (path==="profile.php") {handle=url.searchParams.get("id")||"";if(!/^\d{1,22}$/.test(handle))throw watchFail("profile");}
    else if (/^(?:pages|people)\/[^/]+\/\d{1,22}$/.test(path)) handle=path.split("/").at(-1);
    if (!/^[a-zA-Z0-9.\-]{1,90}$/.test(handle) || /(?:\.php$|^(?:groups|group|share|posts|watch|reels?|events|stories|marketplace|gaming|pages|people|login|media|photo|videos|plugins|help))$/i.test(handle)) throw watchFail("profile");
    handle=handle.toLowerCase(); const explicit=String(input.page_id||"").trim();
    if (explicit&&!/^\d{1,22}$/.test(explicit)) throw watchFail("page_id");
    const numeric=/^\d{1,22}$/.test(handle);
    if (numeric && explicit && explicit!==handle) throw watchFail("page_id");
    pageId=numeric?handle:explicit;
    profile=numeric?"https://www.facebook.com/profile.php?id="+handle:"https://www.facebook.com/"+handle+"/";
  } else throw watchFail("profile");
  return {network,handle,pageId,profile,label:label||(network==="instagram"?"@":"")+handle,key:network+":"+handle};
}
function watchOriginal(raw, network) {
  const u=watchUrl(raw); if(!u) return "";
  const host=u.hostname.replace(/^(www\.|m\.)/,"");
  if(network==="instagram"&&host==="instagram.com"&&/^\/(?:p|reel|tv)\/[\w-]+\/?$/.test(u.pathname))
    return "https://www.instagram.com"+u.pathname.replace(/\/?$/,"/");
  if(network==="facebook"&&host==="facebook.com"){
    if(/^\/(?:story\.php|permalink\.php|photo(?:\.php)?\/?|watch\/?)$/.test(u.pathname)){
      const q=new URLSearchParams();
      for(const k of ["story_fbid","id","fbid","v"]) {const v=u.searchParams.get(k); if(v&&/^[\w-]{1,180}$/.test(v))q.set(k,v);}
      if(!["story_fbid","fbid","v"].some(k=>q.has(k)))return "";
      return "https://www.facebook.com"+u.pathname+"?"+q.toString();
    }
    if(/^\/(?:[^/]+\/(?:posts|photos|videos)(?:\/[\w.\-]+){1,4}|(?:reel|watch\/live)\/[\w.\-]+)\/?$/.test(u.pathname))
      return "https://www.facebook.com"+u.pathname;
  }
  return "";
}
const watchStop = new Set(("para sobre desde cuando esta este estas estos estamos nuestra nuestro nuestros nuestra avui aquest aquesta amb per del les ses dels des una unes uns molt més també com pel hem que los las con como por sus nos hay más del els sa ses una unas unos somos molt avui dels the and with from that this your our link bio instagram facebook publicación publicació publicado publicadoa reel reels foto vídeo video fotos imatges imagen mira segueix síguenos compartim compartimos http https www post para".split(" ")));
function watchBrief(text, kind) {
  const words=String(text||"").slice(0,2500).replace(/https?:\/\/\S+|@[\p{L}\d._]+/gu," ").match(/[\p{L}\d]+(?:['’·-][\p{L}\d]+)*/gu)||[];
  const terms=[],seen=new Set();for(const w of words){const key=w.toLocaleLowerCase("es");if(key.length<3||watchStop.has(key)||seen.has(key)||/^\d+$/.test(key)||key.length>35)continue;seen.add(key);terms.push(w);if(terms.length===7)break;}
  if(!words.length)return (kind==="VIDEO"?"Vídeo":"Publicación")+" sin descripción de la fuente.";
  // Describe the subject, not an inferred outcome or a copied caption. These are never selection filters.
  const plain=words.join(" ").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
  const topics=[
    [/\b(contacontes|cuentacuentos)\b/,"una sesión de cuentacuentos"],[/\btallers?\b|\btalleres\b/,"un taller"],
    [/\b(inscripcio|inscripcions|inscripcion|inscripciones)\b/,"las inscripciones"],[/\b(horaris?|horarios?)\b/,"los horarios"],
    [/\b(exposicio|exposicion|exposicions|exposiciones)\b/,"una exposición"],[/\bconcerts?\b|\bconciertos?\b/,"un concierto"],
    [/\b(autobus|autobusos|bus|transport|transporte|tren|tramvia|tranvia)\b/,"el transporte"],
    [/\b(partit|partido|partits|partidos|campionat|campeonato|torneig|torneo)\b/,"una competición"],
    [/\b(reunio|reunion|assemblea|asamblea|plenari|plenario)\b/,"una reunión"],
    [/\b(transit|trafico|circulacio|circulacion|aparcaments?|aparcamiento)\b/,"la circulación o el aparcamiento"]
  ].filter(([pattern])=>pattern.test(plain)).map(([,label])=>label).slice(0,2);
  const hour=String(text||"").match(/\b(?:[01]?\d|2[0-3])[:.]([0-5]\d)\s*(?:h(?:oras)?\b)?/i);
  let brief=topics.length?"La publicación trata de "+topics.join(" y ")+".":terms.length?"La publicación menciona: "+terms.slice(0,5).join(", ")+".":"La fuente ha compartido una publicación breve.";
  if(hour)brief+=" Hora mencionada: "+hour[0].trim()+".";
  else if(topics.length&&terms.length>2)brief+=" Referencias: "+terms.slice(0,4).join(", ")+".";
  return brief;
}
function watchValidDay(day) {
  return typeof day==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(Date.parse(day+"T12:00:00Z"))&&new Date(day+"T12:00:00Z").toISOString().slice(0,10)===day;
}
async function watchApi(req,env,cors) {
  const db=env.SOCIAL_WATCH_DB;
  if(!db)return json({code:"watch_storage_setup",error:"El archivo de cuentas compartido aún no está conectado."},503,cors);
  try {
    await watchSchema(db);
    if(req.method==="GET") {
      const u=new URL(req.url),from=u.searchParams.get("from")||"",to=u.searchParams.get("to")||"";
      if(!watchValidDay(from)||!watchValidDay(to)||from>to||Date.parse(to)-Date.parse(from)>6*WATCH_DAY)throw watchFail("dates");
      const before=u.searchParams.get("before")||"";const match=before.match(/^(\d{1,16}):([\w.:_-]{1,220})$/);
      if(before&&!match)throw watchFail("dates");
      const [accounts,posts]=await db.batch([
        db.prepare("SELECT id,label,profile,network,handle,page_id,status,attempted,completed,earliest FROM watch_accounts ORDER BY label COLLATE NOCASE,id"),
        db.prepare(`SELECT p.k,p.stamp,p.url,p.brief,a.label,a.network FROM watch_posts p JOIN watch_accounts a ON a.id=p.account
          WHERE day BETWEEN ? AND ? AND (p.stamp < ? OR (p.stamp=? AND p.k>?)) ORDER BY p.stamp DESC,p.k LIMIT 51`)
          .bind(from,to,match?Number(match[1]):9007199254740991,match?Number(match[1]):9007199254740991,match?match[2]:"")
      ]);
      const rows=posts.results.slice(0,50),last=rows.at(-1);
      return json({accounts:accounts.results,posts:rows,next:posts.results.length>50?last.stamp+":"+last.k:""},200,cors);
    }
    if(req.method!=="POST")return json({error:"Método no permitido."},405,cors);
    let b; try{b=await req.json();}catch{throw watchFail("profile");}if(!b||typeof b!=="object"||Array.isArray(b))throw watchFail("profile");
    if(b.action==="add"){
      const p=watchProfile(b);
      const r=await db.prepare(`INSERT OR IGNORE INTO watch_accounts (id,profile_key,network,handle,page_id,label,profile,added)
        SELECT ?,?,?,?,?,?,?,? WHERE (SELECT count(*) FROM watch_accounts)<100`)
        .bind(crypto.randomUUID(),p.key,p.network,p.handle,p.pageId,p.label,p.profile,Date.now()).run();
      if(!r.meta.changes){const hit=await db.prepare("SELECT id FROM watch_accounts WHERE profile_key=?").bind(p.key).first();return json(hit?{ok:true,existing:true}:{error:"La lista admite hasta 100 cuentas."},hit?200:409,cors);}
      return json({ok:true},201,cors);
    }
    if(!["remove","check"].includes(b.action)||typeof b.id!=="string"||b.id.length>64)throw watchFail("action");
    const a=await db.prepare("SELECT * FROM watch_accounts WHERE id=?").bind(b.id).first();
    if(!a)return json({error:"La cuenta ya no está en la lista."},404,cors);
    if(b.action==="remove"){await db.batch([db.prepare("DELETE FROM watch_posts WHERE account=?").bind(a.id),db.prepare("DELETE FROM watch_accounts WHERE id=?").bind(a.id)]);return json({ok:true},200,cors);}
    if(a.attempted>Date.now()-60000 || (a.lease&&a.due>Date.now()))return json({error:"Esta cuenta se acaba de revisar. Espera un minuto."},429,cors);
    const state=await watchReadAccount(db,env,a,true);
    if(state==="temporary"&&a.watchDiagnostic)
      return json({code:"watch_read_interrupted",state,error:watchManualFailure(a.watchDiagnostic),diagnostic:a.watchDiagnostic},503,cors);
    return json({ok:true,state},200,cors);
  }catch(e){
    const messages={profile:"Pega la dirección del perfil de Instagram o de la página de Facebook, no la de una publicación o grupo.",page_id:"El ID de página debe ser numérico y corresponder a ese perfil.",dates:"Elige un día o una semana válidos.",action:"Acción no válida."};
    return json({error:messages[e.watchCode]||"No se ha podido consultar el archivo de seguimiento."},messages[e.watchCode]?400:503,cors);
  }
}
async function watchGraph(env,path,params) {
  const u=new URL("https://graph.facebook.com/v26.0/"+path);
  for(const [k,v] of Object.entries(params))u.searchParams.set(k,v);
  // Workers does not implement redirect:error. Manual also prevents forwarding credentials to another host.
  const response=await fetch(u.href,{method:"GET",headers:{Authorization:"Bearer "+env.WATCH_META_READ_TOKEN},redirect:"manual",signal:AbortSignal.timeout(9000)});
  if(response.status>=300&&response.status<400)throw watchFail("temporary",{http_status:response.status,reason:"redirect"});
  let data={};try{data=await response.json();}catch{throw watchFail("temporary",{http_status:response.status,reason:"response_format"});}
  if(!response.ok||data.error){
    const code=data.error?.code;
    if(code===190||response.status===401)throw watchFail("credentials");
    if([10,200,294].includes(code)||response.status===403)throw watchFail("permission");
    if([4,17,32,613].includes(code)||response.status===429)throw watchFail("limited");
    if([100,110].includes(code)||response.status===404)throw watchFail("unavailable");
    throw watchFail("temporary",{http_status:response.status,meta_code:code,meta_subcode:data.error?.error_subcode});
  }
  return data;
}
async function watchPage(env,a,cursor,from,until){
  if(!env.WATCH_META_READ_TOKEN || (a.network==="instagram"&&!/^\d{1,24}$/.test(env.WATCH_INSTAGRAM_ID||"")))throw watchFail("credentials");
  const fields="id,caption,permalink,timestamp,media_type";
  if(cursor&&!/^[A-Za-z0-9_+=.\/~:-]{1,1800}$/.test(cursor))throw watchFail("cursor");
  if(a.network==="instagram"){
    const field=`business_discovery.username(${a.handle}){username,media.limit(35)${cursor?".after("+cursor+")":""}{${fields}}}`;
    const v=await watchGraph(env,env.WATCH_INSTAGRAM_ID,{fields:field});
    if(!v.business_discovery||v.business_discovery.username?.toLowerCase()!==a.handle || !Array.isArray(v.business_discovery.media?.data))throw watchFail("unavailable");
    return v.business_discovery.media;
  }
  let pageId=a.page_id;
  if(!/^\d{1,22}$/.test(a.handle)){
    const v=await watchGraph(env,pageId||a.handle,{fields:"id,link"});
    if(!/^\d{1,22}$/.test(v.id||"") || (pageId&&v.id!==pageId))throw watchFail("unavailable");
    if(pageId){
      let verified; try{verified=watchProfile({profile:v.link});}catch{}
      if(verified?.handle!==a.handle)throw watchFail("unavailable");
    }
    pageId=v.id;
  }
  const v=await watchGraph(env,pageId+"/posts",{fields:"id,created_time,permalink_url,message,story",limit:"35",since:String(Math.floor(from/1000)),until:String(Math.ceil(until/1000)),...(cursor?{after:cursor}:{})});
  if(!Array.isArray(v.data))throw watchFail("unavailable"); return v;
}
async function watchReadAccount(db,env,a,manual=false){
  const now=Date.now(), lease=crypto.randomUUID();
  const lock=await db.prepare(`UPDATE watch_accounts SET lease=?,due=?,attempted=? WHERE id=? AND
    ((lease='' AND (due<=? OR ?=1)) OR due<=?) AND (?=0 OR attempted<=?)`).bind(lease,now+180000,now,a.id,now,manual?1:0,now,manual?1:0,now-60000).run();
  if(!lock.meta.changes)return "busy";
  let cursor=a.cursor||"", from=a.scan_from||(a.completed?Math.max(1,a.completed-2*WATCH_DAY):now-30*WATCH_DAY), start=a.scan_start||now, stage="meta";
  try{
    for(let n=0;n<2;n++){
      stage="meta";
      const page=await watchPage(env,a,cursor,from,start), statements=[], records=[];let valid=0, older=0,skipped=false;
      stage="process";
      for(const v of page.data){
        const stamp=Date.parse(v.timestamp||v.created_time||"");
        if(!Number.isFinite(stamp)){skipped=true;continue;}
        valid++;if(stamp<from){older++;continue;}if(stamp>start)continue;
        const url=watchOriginal(v.permalink||v.permalink_url,a.network);
        if(!url||!v.id||!/^[\w-]{1,120}$/.test(v.id)){skipped=true;continue;}
        records.push([a.id+":"+v.id,stamp,watchCalendar.format(new Date(stamp)),url,watchBrief(v.caption||v.message||v.story,v.media_type)]);
      }
      if(records.length) statements.push(db.prepare(`INSERT INTO watch_posts(account,k,stamp,day,url,brief)
        SELECT a.id,j.value->>0,j.value->>1,j.value->>2,j.value->>3,j.value->>4
        FROM watch_accounts a,json_each(?) j WHERE a.id=? AND a.lease=? AND true
        ON CONFLICT(k) DO UPDATE SET url=excluded.url,brief=excluded.brief`).bind(JSON.stringify(records),a.id,lease));
      // Business Discovery supplies after cursors without paging.next. Stop on an empty terminal page.
      const more=page.data.length>0&&Boolean(a.network==="instagram"?(page.paging?.cursors?.after||page.paging?.next):page.paging?.next);
      const next=more?String(page.paging?.cursors?.after||""):"";
      if(more&&(!next||next===cursor||!/^[A-Za-z0-9_+=.\/~:-]{1,1800}$/.test(next)))throw watchFail("cursor");
      const done=!next||(valid>0 && older===page.data.length && (a.network==="facebook"||!!cursor));
      // Unusable rows must never turn into a claim of complete coverage.
      const partial=skipped||Boolean(a.scan_partial);
      if(done)statements.push(db.prepare(`UPDATE watch_accounts SET completed=?,earliest=CASE WHEN earliest=0 THEN ? ELSE min(earliest,?) END,
        status=?,due=?,lease='',cursor='',scan_from=0,scan_start=0,scan_partial=0 WHERE id=? AND lease=?`).bind(start,from,from,partial?"incomplete":"ready",now+3600000,a.id,lease));
      else statements.push(db.prepare("UPDATE watch_accounts SET status=?,due=?,cursor=?,scan_from=?,scan_start=?,scan_partial=?,lease=? WHERE id=? AND lease=?")
        .bind(partial?"partial_rows":"catching_up",n===1?now+60000:now+180000,next,from,start,partial?1:0,n===1?"":lease,a.id,lease));
      stage="archive";
      await db.batch(statements);
      if(done)return partial?"incomplete":"ready";
      a.scan_partial=partial?1:0; cursor=next;
    }
    return "catching_up";
  }catch(e){
    const status=["credentials","permission","limited","unavailable","cursor"].includes(e.watchCode)?e.watchCode:"temporary";
    if(status==="temporary"){
      a.watchDiagnostic=watchDiagnostic(e,stage);
      console.warn("SOCIAL_WATCH_READ "+JSON.stringify(a.watchDiagnostic));
    }
    const delay=status==="credentials"||status==="permission"||status==="unavailable"?12*3600000:status==="limited"?2*3600000:30*60000;
    const reset=status==="cursor"||(status==="unavailable"&&cursor);
    await db.prepare("UPDATE watch_accounts SET status=?,due=?,lease='',cursor=CASE WHEN ? THEN '' ELSE cursor END WHERE id=? AND lease=?")
      .bind(status,now+delay,reset?1:0,a.id,lease).run();return status;
  }
}
async function watchTick(env) {
  const db=env.SOCIAL_WATCH_DB;if(!db)return {action:"watch_not_configured"};
  await watchSchema(db);
  const {results}=await db.prepare("SELECT * FROM watch_accounts WHERE due<=? ORDER BY due,id LIMIT 3").bind(Date.now()).all();
  for(const a of results)await watchReadAccount(db,env,a);
  return {action:"social_watch",accounts:results.length};
}
