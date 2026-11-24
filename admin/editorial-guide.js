(() => {
  const form = document.getElementById("socialLinkForm");
  const titleCount = document.getElementById("socialTitleCount");
  const bodyCount = document.getElementById("socialBodyCount");
  const suggestions = document.getElementById("socialTextSuggestions");
  const prepareButton = document.getElementById("socialPrepareTextButton");
  const prepareMessage = document.getElementById("socialPrepareTextMessage");
  if (!form || !titleCount || !bodyCount || !suggestions) return;

  const compact = value => String(value || "").replace(/\s+/gu, " ").trim();
  const comparable = value => compact(value).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const genericTitles = new Set([
    "publicacio de xarxa", "nueva publicacion", "nova publicacio", "publicacion de red social",
    "enlace de redes", "new post", "social post",
  ]);
  let previousSuggestions = "";
  let availablePosts = [];

  function publicationKey(value) {
    try {
      const url = new URL(compact(value));
      if (url.protocol !== "https:" || url.username || url.password) return "";
      url.hostname = url.hostname.replace(/^www\./u, "");
      if (url.hostname === "m.facebook.com") url.hostname = "facebook.com";
      url.hash = "";
      for (const key of Array.from(url.searchParams.keys())) {
        if (/^utm_/iu.test(key) || /^(?:fbclid|igsh|igshid|mibextid|hpir)$/iu.test(key)) url.searchParams.delete(key);
      }
      url.searchParams.sort();
      url.pathname = url.pathname.replace(/\/$/u, "") || "/";
      return url.href;
    } catch (_) { return ""; }
  }

  function clip(value, limit) {
    const text = compact(value);
    if (text.length <= limit) return text;
    const prefix = text.slice(0, limit - 1).replace(/[\uD800-\uDBFF]$/u, "");
    return (prefix.includes(" ") ? prefix.slice(0, prefix.lastIndexOf(" ")) : prefix).replace(/[ ,;:]+$/u, "") + "…";
  }

  function permittedSummary(post) {
    if (!["short_factual_excerpt", "generated_social_summary", "summary_allowed"].includes(post.content_policy)) return "";
    // Recognize the complete Drupal author/timestamp signature, not dates in the prose.
    const text = compact(post.summary).replace(/^\S+\s+(?:dl|dt|dc|dj|dv|ds|dg)\.,\s+\d{1,2}\/\d{1,2}\/\d{4}\s+-\s+\d{1,2}:\d{2}\s+\d{1,2}-[A-Za-zÀ-ÿ]+-\d{4}\s+/u, "");
    if (!text || comparable(text) === comparable(post.title) || /^https?:\/\/\S+$/iu.test(text)) return "";
    let sentences;
    if (typeof Intl.Segmenter === "function") {
      sentences = Array.from(new Intl.Segmenter(post.language || "ca", {granularity:"sentence"}).segment(text), item => item.segment);
    } else {
      sentences = text.split(/(?<=[.!?])\s+(?=[A-ZÀ-Ý¿¡])/u);
    }
    return clip(sentences.slice(0, 2).join(" "), 360);
  }

  function prepareText() {
    if (!prepareMessage) return;
    if (compact(form.elements.title?.value) && compact(form.elements.body?.value)) {
      prepareMessage.textContent = "Ya has escrito el titular y el resumen. Se conserva tu texto.";
      return;
    }
    const key = publicationKey(form.elements.original_url?.value);
    if (!key) {
      prepareMessage.textContent = "Indica primero el enlace HTTPS de la publicación original.";
      return;
    }
    const matches = availablePosts.filter(post => publicationKey(post.original_url) === key || publicationKey(post.url) === key);
    if (matches.some(post => post.source_type === "own")) {
      prepareMessage.textContent = "Este enlace ya aparece como publicación propia. Revisa los enlaces publicados para editarlo y evitar duplicarlo.";
      return;
    }
    const now = Date.now();
    const recent = matches.filter(post => {
      const date = Date.parse(post.published_at);
      if (["expired", "archived"].includes(post.alert_status)
          || post.alert_valid_until && Date.parse(post.alert_valid_until) <= now) return false;
      return Number.isFinite(date) && date <= now && now - date <= 60 * 86400000 && compact(post.title);
    });
    const post = recent.find(item => item.content_policy === "headline_date_link_only") || recent[0];
    if (!post) {
      prepareMessage.textContent = "No hay información verificable disponible para este enlace. El formulario no se ha modificado.";
      return;
    }
    const source = compact(post.source) || "Font original";
    const authoredSource = compact(form.elements.source_name?.value);
    if (authoredSource && comparable(authoredSource) !== comparable(source)) {
      prepareMessage.textContent = `La fuente guardada es «${source}» y no coincide con la cuenta indicada. Revisa la atribución antes de preparar el texto.`;
      return;
    }
    // Preparation is optional. An unsupported locale or malformed text leaves the form intact.
    let summary;
    try { summary = permittedSummary(post); }
    catch (_) {
      prepareMessage.textContent = "No se ha podido preparar el texto. Se conserva el formulario para que puedas continuar.";
      return;
    }
    const language = form.elements.language?.value || "ca";
    const references = {
      ca: `Consulta la publicació original de ${source} per ampliar la informació.`,
      es: `Consulta la publicación original de ${source} para ampliar la información.`,
      en: `See the original post by ${source} for more information.`,
    };
    if (!compact(form.elements.title.value)) form.elements.title.value = clip(post.title, 180);
    if (!compact(form.elements.body.value)) form.elements.body.value = summary || references[language] || references.ca;
    if (!authoredSource) form.elements.source_name.value = source;
    const publishedDay = new Intl.DateTimeFormat("es-ES", {timeZone:"Europe/Madrid"}).format(new Date(post.published_at));
    prepareMessage.textContent = `Publicación original del ${publishedDay}. ` + (summary
      ? "Texto preparado con la información disponible. Conserva el idioma de la fuente; revisa los datos y la redacción antes de publicar."
      : "Titular y referencia preparados. Esta fuente no ofrece un resumen reutilizable; no se han añadido datos al titular. Revisa la propuesta antes de publicar.");
    refresh();
  }

  function refresh() {
    const titleValue = form.elements.title?.value || "";
    const bodyValue = form.elements.body?.value || "";
    const title = compact(titleValue);
    const body = compact(bodyValue);
    const source = compact(form.elements.source_name?.value);
    const originalUrl = compact(form.elements.original_url?.value);
    const instagram = form.elements.instagram;
    const sendToInstagram = instagram?.checked && !instagram.disabled;
    titleCount.textContent = `Titular: ${titleValue.length}/180 caracteres`;
    bodyCount.textContent = `Resumen: ${bodyValue.length} caracteres`;

    const notes = [];
    if (sendToInstagram && (!title || !body)) {
      notes.push("Para publicar también en Instagram necesitas un titular y un resumen propios.");
    } else if (!title && !body) {
      notes.push("Si solo compartes el enlace en la web o Facebook, el titular y el resumen pueden quedar vacíos.");
    } else if (!title) {
      notes.push("Un titular concreto ayuda a reconocer el contenido cuando no se muestra la incrustación.");
    }
    if (title) {
      if (/(?:https?:\/\/|www\.)/iu.test(title)) {
        notes.push("Describe la noticia en el titular y deja la dirección en «Enlace de la publicación original».");
      } else if (title.length < 20 || genericTitles.has(comparable(title))) {
        notes.push("Prueba un titular que explique qué ocurre y dónde, en lugar de una etiqueta genérica.");
      }
    }
    if (body) {
      if (/^(?:https?:\/\/|www\.)\S+$/iu.test(body)) {
        notes.push("Resume con tus palabras qué aporta la publicación; el enlace ya tiene su propio campo.");
      } else if (title && comparable(body) === comparable(title)) {
        notes.push("Añade en el resumen información que complemente el titular.");
      }
    } else if (title && !sendToInstagram) {
      notes.push("Un breve resumen propio ayuda a entender el enlace si la plataforma no permite incrustarlo.");
    }
    if (originalUrl && !source) {
      notes.push("Indica la cuenta o entidad original para que se reconozca la fuente.");
    }
    if (!notes.length) notes.push("Antes de publicar, comprueba los datos, la atribución y el tono del texto.");

    // Announce only changes in the advice, rather than every typed character.
    const nextSuggestions = JSON.stringify(notes);
    if (nextSuggestions !== previousSuggestions) {
      suggestions.replaceChildren(...notes.map(note => {
        const item = document.createElement("li");
        item.textContent = note;
        return item;
      }));
      previousSuggestions = nextSuggestions;
    }
  }

  form.addEventListener("input", refresh);
  form.addEventListener("change", refresh);
  form.addEventListener("reset", () => queueMicrotask(() => {
    if (prepareMessage) prepareMessage.textContent = "";
    refresh();
  }));
  prepareButton?.addEventListener("click", prepareText);
  window.SOLLER_ARA_EDITORIAL_GUIDE = Object.freeze({
    refresh,
    setPosts(posts) { availablePosts = Array.isArray(posts) ? posts.filter(post => post && typeof post === "object") : []; },
  });
  refresh();
})();
