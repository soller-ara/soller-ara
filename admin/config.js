window.SOLLER_ARA_ADMIN_API = "https://soller-ara-admin.infosollerara.workers.dev";
window.SOLLER_ARA_ADMIN_VERSION = "0.91";

window.addEventListener("DOMContentLoaded", () => {
  const version = document.getElementById("adminVersion");
  if (version) version.textContent = "v" + window.SOLLER_ARA_ADMIN_VERSION;

  [
    "./sources-v2.js?v=0.88",
    "./activity-v1.js?v=0.69",
    "./visits-v1.js?v=0.69",
    "./social-auto-v1.js?v=0.89",
  ].forEach((src) => {
    const script = document.createElement("script");
    script.src = src;
    script.defer = true;
    document.body.appendChild(script);
  });
});
