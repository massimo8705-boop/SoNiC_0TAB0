// Fonctions partagées (fond, popup, options). Aucune dépendance externe.
const DEFAULT_ID = "firefox-default";
const APP_API = "http://127.0.0.1:10800/routes.json";   // application SoNiC_0TAB0 (facultative)
const PRESETS = [
  { name: "Tor (service)", proxy: "socks5://127.0.0.1:9050" },
  { name: "Tor Browser", proxy: "socks5://127.0.0.1:9150" },
  { name: "Proxy local HTTP", proxy: "http://127.0.0.1:8080" },
];

// "user:pass@host:port", "socks5://host:1080", "http://host:3128"… -> objet, ou null si invalide
function parseProxy(p) {
  p = (p || "").trim();
  if (!p) return null;
  if (!p.includes("://")) p = "http://" + p;
  let u;
  try { u = new URL(p); } catch (e) { return null; }
  if (!u.hostname) return null;
  const scheme = u.protocol.replace(":", "").toLowerCase();
  const type = scheme === "socks4" ? "socks4" : scheme.startsWith("socks") ? "socks" : scheme === "https" ? "https" : "http";
  const def = type.startsWith("socks") ? 1080 : type === "https" ? 443 : 8080;
  return { type, host: u.hostname, port: parseInt(u.port, 10) || def,
           user: u.username ? decodeURIComponent(u.username) : null,
           pass: u.password ? decodeURIComponent(u.password) : null };
}
// version affichable, sans mot de passe
function shortProxy(p) {
  const d = parseProxy(p);
  return d ? `${d.type === "socks" ? "socks5" : d.type}://${d.host}:${d.port}` : String(p || "");
}

async function loadState() {
  const st = await browser.storage.local.get(["map", "backup", "mine", "custom", "detectApp"]);
  let mine = st.mine || [];
  if (!st.mine && Array.isArray(st.custom)) {                 // migration de l'ancienne liste
    mine = st.custom.map(p => ({ name: shortProxy(p), proxy: p }));
  }
  return { map: st.map || {}, backup: st.backup || {}, mine, detectApp: st.detectApp !== false };
}
async function saveState(s) {
  await browser.storage.local.set({ map: s.map, backup: s.backup || {}, mine: s.mine, detectApp: s.detectApp });
}
async function fetchAppRoutes() {                           // [] si l'application n'est pas lancée
  try {
    const r = await fetch(APP_API, { cache: "no-store" });
    return (await r.json()).routes || [];
  } catch (e) { return null; }
}

// objet « proxy » attendu par Firefox ; null si l'adresse est invalide
function toProxyInfo(raw) {
  const d = parseProxy(raw);
  if (!d) return null;
  const info = { type: d.type, host: d.host, port: d.port, proxyDNS: d.type.startsWith("socks") };
  if (d.type.startsWith("socks") && d.user) { info.username = d.user; info.password = d.pass || ""; }
  return info;
}
