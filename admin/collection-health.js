(() => {
  const limit = 2 * 60 * 60 * 1000;
  let latest = null;
  let readFailed = false;
  let reading = false;

  function render() {
    const notice = document.getElementById("collectionFreshness");
    if (!notice) return;
    const raw = latest?.sources_checked_at;
    const checked = typeof raw === "string" && raw.trim() ? Date.parse(raw) : NaN;
    const age = Date.now() - checked;
    let text;
    let warning = true;
    if (!Number.isFinite(checked) || age < -5 * 60 * 1000) {
      text = "No consta una fecha válida de revisión de fuentes. No se puede confirmar que la recogida automática esté al día.";
    } else {
      const when = new Intl.DateTimeFormat("es-ES", {
        dateStyle: "short", timeStyle: "short", timeZone: "Europe/Madrid",
      }).format(new Date(checked));
      const failures = (Array.isArray(latest.source_status) ? latest.source_status : []).filter(item => item?.ok === false).length;
      if (age > limit) {
        text = "Revisión de fuentes retrasada: han pasado más de 2 horas. Última revisión: " + when + " (hora de Mallorca). La revisión está programada cada hora. Puedes usar Buscar y publicar ahora en Fuentes.";
      } else {
        warning = failures > 0;
        text = "Última revisión de fuentes: " + when + " (hora de Mallorca).";
      }
      if (failures) text += " La última revisión registró " + failures + " fuentes con incidencias; consulta Fuentes.";
    }
    if (readFailed) {
      warning = true;
      text = "No se ha podido comprobar el estado actual. " + text;
    }
    notice.textContent = text;
    notice.className = "collection-health" + (warning ? " warning" : "");
    notice.dataset.state = warning ? "warning" : "recent";
  }

  window.SOLLER_ARA_RENDER_COLLECTION_HEALTH = data => {
    latest = data || {};
    readFailed = false;
    render();
  };

  async function refresh() {
    if (reading || document.hidden || document.getElementById("adminView")?.hidden !== false) return;
    const read = window.SOLLER_ARA_READ_JSON;
    if (!read) return;
    reading = true;
    try {
      latest = await read("data/posts.json");
      readFailed = false;
    } catch (_) {
      readFailed = true;
    } finally {
      reading = false;
      render();
    }
  }

  setInterval(refresh, 60000);
  document.addEventListener("visibilitychange", refresh);
})();
