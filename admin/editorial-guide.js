(() => {
  const form = document.getElementById("socialLinkForm");
  const titleCount = document.getElementById("socialTitleCount");
  const bodyCount = document.getElementById("socialBodyCount");
  const suggestions = document.getElementById("socialTextSuggestions");
  if (!form || !titleCount || !bodyCount || !suggestions) return;

  const compact = value => String(value || "").replace(/\s+/gu, " ").trim();
  const comparable = value => compact(value).normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const genericTitles = new Set([
    "publicacio de xarxa", "nueva publicacion", "nova publicacio", "publicacion de red social",
    "enlace de redes", "new post", "social post",
  ]);
  let previousSuggestions = "";

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
      notes.push("Si solo compartes el enlace en la web, el titular y el resumen pueden quedar vacíos.");
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
  form.addEventListener("reset", () => queueMicrotask(refresh));
  window.SOLLER_ARA_EDITORIAL_GUIDE = Object.freeze({ refresh });
  refresh();
})();
