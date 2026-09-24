const DEFAULT_ORIGIN = "https://soller-ara.github.io";
const DEFAULT_OWNER = "soller-ara";
const DEFAULT_REPO = "soller-ara";
const DEFAULT_BRANCH = "main";
const SESSION_SECONDS = 8 * 60 * 60;

const failedLogins = new Map();

export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || DEFAULT_ORIGIN;
    const cors = corsHeaders(origin);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);

    try {
      if (url.pathname === "/health") {
        return json({ ok: true, service: "soller-ara-admin", version: "0.70", capabilities: ["social_settings", "web_analytics", "manual_social_links"] }, 200, cors);
      }

      if (url.pathname === "/api/login" && request.method === "POST") {
        return await login(request, env, cors);
      }

      const session = await requireSession(request, env);
      if (!session) return json({ error: "Sesión no válida o caducada." }, 401, cors);

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

async function githubDispatch(env, workflow, inputs) {
  if (!env.GITHUB_TOKEN) throw new Error("Falta GITHUB_TOKEN");
  const { owner, repo, branch } = repoParts(env);

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
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

async function publish(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const title = String(body.title || "").trim();
  const text = String(body.body || "").trim();

  if (!title || !text) return json({ error: "Faltan título o texto." }, 400, cors);
  if (title.length > 180) return json({ error: "El título es demasiado largo." }, 400, cors);

  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics"]);
  const allowedLanguages = new Set(["ca", "es", "en"]);
  const category = allowedCategories.has(body.category) ? body.category : "news";
  const language = allowedLanguages.has(body.language) ? body.language : "ca";
  const sourceName = String(body.source_name || "").trim();
  const originalUrl = String(body.original_url || "").trim();

  if ((sourceName && !originalUrl) || (!sourceName && originalUrl)) {
    return json({ error: "Indica la fuente y el enlace original juntos." }, 400, cors);
  }
  if (sourceName.length > 120) return json({ error: "El nombre de la fuente es demasiado largo." }, 400, cors);
  if (originalUrl && !isSafeHttpsUrl(originalUrl)) {
    return json({ error: "El enlace original debe ser una URL https válida." }, 400, cors);
  }

  await githubDispatch(env, "publish-own-content.yml", {
    confirmation: "PUBLICAR",
    title,
    body: text,
    category,
    language,
    image_url: String(body.image_url || "").trim(),
    facebook: Boolean(body.facebook),
    instagram: Boolean(body.instagram),
    source_name: sourceName,
    original_url: originalUrl,
  });

  return json({ ok: true, workflow: "Sóller Ara · publicar contingut propi" }, 202, cors);
}

async function editOwn(request, env, cors) {
  const body = await request.json().catch(() => ({}));
  const postId = String(body.post_id || "").trim();
  const title = String(body.title || "").trim();
  const text = String(body.body || "").trim();

  if (!postId || !title || !text) {
    return json({ error: "Faltan datos para editar la publicación." }, 400, cors);
  }
  if (title.length > 180) {
    return json({ error: "El título es demasiado largo." }, 400, cors);
  }

  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics"]);
  const allowedLanguages = new Set(["ca", "es", "en"]);
  const category = allowedCategories.has(body.category) ? body.category : "news";
  const language = allowedLanguages.has(body.language) ? body.language : "ca";

  await githubDispatch(env, "edit-own-content.yml", {
    confirmation: "GUARDAR",
    post_id: postId,
    title,
    body: text,
    category,
    language,
    image_url: String(body.image_url || "").trim(),
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
  const allowedCategories = new Set(["news", "agenda", "alerts", "services", "culture", "sports", "commerce", "politics"]);
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
