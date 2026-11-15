(() => {
  const form = document.getElementById("webDiscoveryForm");
  if (!form) return;

  const topic = document.getElementById("webDiscoveryTopic");
  const area = document.getElementById("webDiscoveryArea");
  const days = document.getElementById("webDiscoveryDays");
  const engine = document.getElementById("webDiscoveryEngine");
  const query = document.getElementById("webDiscoveryQuery");
  const timeFilter = document.getElementById("webDiscoveryTimeFilter");
  const submit = document.getElementById("webDiscoverySubmit");

  const soller = ["Sóller", "Soller", "Sòller", "sollerics", "solleriques"];
  const deia = ["Deià", "Deia"];
  const local = [...soller, "Fornalutx", "Biniaraix", ...deia];
  const areas = new Map([
    ["all", local],
    ["soller", soller],
    ["port", ["Port de Sóller", "Port de Soller", "Puerto de Sóller", "Puerto de Soller"]],
    ["fornalutx", ["Fornalutx"]],
    ["biniaraix", ["Biniaraix"]],
    ["deia", deia],
    ["serra", ["Serra de Tramuntana", "Sierra de Tramuntana", "Sierra Tramontana"]],
  ]);
  const engines = new Map([
    ["brave", "https://search.brave.com/search"],
    ["google", "https://www.google.com/search"],
  ]);
  const calendar = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit",
  });

  function range(period) {
    const parts = Object.fromEntries(calendar.formatToParts(new Date()).map(({ type, value }) => [type, value]));
    const today = Date.UTC(+parts.year, +parts.month - 1, +parts.day);
    const day = offset => new Date(today + offset * 86400000).toISOString().slice(0, 10);
    return { since: day(-period), until: day(0), tomorrow: day(1) };
  }

  function phrases(names) {
    const quoted = names.map(name => '"' + name + '"');
    return quoted.length === 1 ? quoted[0] : "(" + quoted.join(" OR ") + ")";
  }

  form.addEventListener("submit", event => {
    const names = areas.get(area.value);
    const target = engines.get(engine.value);
    const period = Number(days.value);
    if (!names || !target || ![7, 30, 60].includes(period)) {
      event.preventDefault();
      return;
    }

    // Tema en texto libre: los campos de la búsqueda fijan zona, fechas y destino.
    const words = topic.value.trim().normalize("NFC").slice(0, 140)
      .match(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu) || [];
    const subject = words.filter(word => !["AND", "OR", "NOT"].includes(word)).join(" ");
    const clauses = [subject, phrases(names)];
    if (area.value === "serra") clauses.push(phrases(local));

    const { since, until, tomorrow } = range(period);
    const brave = engine.value === "brave";
    const search = clauses.filter(Boolean).join(brave ? " AND " : " ");
    query.value = brave ? search : search + " after:" + since + " before:" + tomorrow;
    timeFilter.disabled = !brave;
    timeFilter.value = brave ? since + "to" + until : "";
    form.action = target;
    // La navegación GET nativa mantiene abierta la administración y evita popups de JavaScript.
  });

  submit.disabled = false;
})();

