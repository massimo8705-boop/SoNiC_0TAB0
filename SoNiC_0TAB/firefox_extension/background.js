// SoNiC_0TAB0 — une sortie Internet par conteneur Firefox + sessions.
// Aucun repli sur « connexion normale » : si la route est injoignable, la requête échoue (pas de fuite d'IP).
let map = {}, backup = {}, mine = [];
const short = p => shortProxy(p);
const ready = initLang();
// actualisation automatique : tabId -> { secs, next, onSwitch }   (en mémoire : propre à cette session de Firefox)
const auto = new Map();
let reloadOnSwitch = false;
browser.storage.local.get("reloadOnSwitch").then(s => { reloadOnSwitch = !!s.reloadOnSwitch; });

async function refresh() {
  const s = await loadState(); map = s.map; backup = s.backup; mine = s.mine;
  await ready; buildMenu(); refreshBadges();
}
refresh();
browser.storage.onChanged.addListener(async ch => {
  if (ch.lang) await initLang();
  if (ch.reloadOnSwitch) reloadOnSwitch = !!ch.reloadOnSwitch.newValue;
  refresh();
});

function notify(message) {
  try { browser.notifications.create({ type: "basic", iconUrl: "icons/icon-96.png", title: "SoNiC_0TAB0", message }); } catch (e) {}
}

// ---- proxy par conteneur ---------------------------------------------------
browser.proxy.onRequest.addListener(details => {
  const raw = (map[details.cookieStoreId] || "").trim();
  if (!raw) return { type: "direct" };
  const main = toProxyInfo(raw);
  if (!main) return [{ type: "http", host: "127.0.0.1", port: 9 }];          // route invalide : on bloque
  const list = [main];
  const sec = toProxyInfo((backup[details.cookieStoreId] || "").trim());      // route de secours (facultative)
  if (sec) list.push(sec);
  list.forEach(i => { i.failoverTimeout = 5; });                              // principale, puis secours ; jamais « direct »
  return list;
}, { urls: ["<all_urls>"] });

let lastWarn = 0;
browser.proxy.onError.addListener(err => {
  const now = Date.now();
  if (now - lastWarn < 60000) return;
  lastWarn = now;
  notify(t("n_route_fail", (err && err.message) || "proxy"));
});

// identifiants des proxys HTTP(S) (les SOCKS les reçoivent directement ci-dessus)
browser.webRequest.onAuthRequired.addListener(details => {
  if (!details.isProxy) return {};
  const d = parseProxy(map[details.cookieStoreId]);
  return d && d.user ? { authCredentials: { username: d.user, password: d.pass || "" } } : {};
}, { urls: ["<all_urls>"] }, ["blocking"]);

// ---- pastille « IP » sur les onglets routés -----------------------------------
browser.browserAction.setBadgeBackgroundColor({ color: "#ffc857" });
if (browser.browserAction.setBadgeTextColor) browser.browserAction.setBadgeTextColor({ color: "#111111" });
function badge(tab) {
  if (!tab) return;
  const p = map[tab.cookieStoreId], bk = backup[tab.cookieStoreId];
  const rl = auto.has(tab.id) ? "⟳" : "";
  browser.browserAction.setBadgeText({ tabId: tab.id, text: (p ? "IP" : "") + rl });
  browser.browserAction.setTitle({ tabId: tab.id,
    title: p ? short(p) + (bk ? "  ↪ " + short(bk) : "") : browser.i18n.getMessage("actionTitle") });
}
async function refreshBadges() { for (const tb of await browser.tabs.query({})) badge(tb); }
browser.tabs.onActivated.addListener(async i => badge(await browser.tabs.get(i.tabId)));
browser.tabs.onUpdated.addListener((id, ch, tab) => badge(tab), { properties: ["status", "url"] });

// ---- clic droit : ouvrir un lien / une page via un conteneur routé ---------------
async function buildMenu() {
  await browser.contextMenus.removeAll();
  let ids = [];
  try { ids = (await browser.contextualIdentities.query({})) || []; } catch (e) {}
  browser.contextMenus.create({ id: "td", title: t("menu_title"), contexts: ["link", "page", "tab"] });
  // clic droit sur un onglet → actualisation automatique
  browser.contextMenus.create({ id: "ar", title: t("menu_autoreload"), contexts: ["tab"] });
  for (const secs of RELOAD_SECS) {
    browser.contextMenus.create({ id: "ar:" + secs, parentId: "ar", type: "radio", checked: secs === 0,
      title: t(secs ? "rl_" + secs : "rl_off"), contexts: ["tab"] });
  }
  browser.contextMenus.create({ id: "ar-sep", parentId: "ar", type: "separator", contexts: ["tab"] });
  browser.contextMenus.create({ id: "ar:switch", parentId: "ar", type: "checkbox", checked: false,
    title: t("menu_every_switch"), contexts: ["tab"] });
  for (const c of ids) {
    const p = map[c.cookieStoreId];
    browser.contextMenus.create({ id: "td:" + c.cookieStoreId, parentId: "td",
      title: c.name + (p ? "   ◈ " + short(p) : "   " + t("menu_normal")), contexts: ["link", "page", "tab"] });
  }
}
browser.contextMenus.onClicked.addListener((info, tab) => {
  const id = String(info.menuItemId);
  if (id.startsWith("ar:") && tab) {
    if (id === "ar:switch") {
      const cur = auto.get(tab.id) || { secs: 0, next: 0, onSwitch: false };
      setAuto(tab.id, cur.secs, !cur.onSwitch);
    } else setAuto(tab.id, parseInt(id.slice(3), 10), (auto.get(tab.id) || {}).onSwitch);
    return;
  }
  if (!id.startsWith("td:")) return;
  const url = info.linkUrl || (tab && tab.url) || info.pageUrl;
  browser.tabs.create({ url, cookieStoreId: String(info.menuItemId).slice(3) });
});
for (const ev of ["onCreated", "onRemoved", "onUpdated"]) {
  try { browser.contextualIdentities[ev].addListener(buildMenu); } catch (e) {}
}

// ---- test d'IP réel : onglet invisible DANS le conteneur ------------------------------
async function testIp(cookieStoreId) {
  const create = { url: "https://api.ipify.org/?format=text", active: false };
  if (cookieStoreId && cookieStoreId !== DEFAULT_ID) create.cookieStoreId = cookieStoreId;
  let tab;
  try { tab = await browser.tabs.create(create); }
  catch (e) { return { ok: false, code: "container" }; }
  try {
    await new Promise((resolve, reject) => {
      const to = setTimeout(() => { browser.tabs.onUpdated.removeListener(h); reject(new Error("timeout")); }, 15000);
      function h(id, ch) {
        if (id === tab.id && ch.status === "complete") { clearTimeout(to); browser.tabs.onUpdated.removeListener(h); resolve(); }
      }
      browser.tabs.onUpdated.addListener(h);
    });
    const r = await browser.tabs.executeScript(tab.id, { code: "document.body ? document.body.innerText.trim() : ''" });
    const ip = ((r && r[0]) || "").trim();
    return /^[0-9a-fA-F:.]{3,45}$/.test(ip) ? { ok: true, ip } : { ok: false, code: "unexpected" };
  } catch (e) {
    const m = String((e && e.message) || e);
    return { ok: false, code: m === "timeout" ? "timeout" : "unexpected", detail: m };
  } finally {
    try { await browser.tabs.remove(tab.id); } catch (e) {}
  }
}

// =====================================================================================
// Sessions : onglets + conteneur + route, enregistrés automatiquement
//   last  = dernier état connu · prev = état de la veille (copié au démarrage de Firefox)
//   named = sessions enregistrées à la main
// =====================================================================================
const WEB = /^(https?|ftp):/i;

async function snapshot() {
  let ids = [];
  try { ids = (await browser.contextualIdentities.query({})) || []; } catch (e) {}
  const byId = {}; ids.forEach(c => { byId[c.cookieStoreId] = c; });
  const used = new Set(), windows = [];
  for (const w of await browser.windows.getAll({ populate: true, windowTypes: ["normal"] })) {
    if (w.incognito) continue;
    const tabs = [];
    for (const tb of w.tabs) {
      if (!WEB.test(tb.url || "")) continue;
      const c = byId[tb.cookieStoreId] ? tb.cookieStoreId : null;
      if (c) used.add(c);
      tabs.push({ url: tb.url, title: tb.title || "", pinned: !!tb.pinned, c });
    }
    if (tabs.length) windows.push(tabs);
  }
  const containers = [...used].map(id => ({ id, name: byId[id].name, color: byId[id].color, icon: byId[id].icon,
                                            route: map[id] || "", backup: backup[id] || "" }));
  return { t: Date.now(), containers, windows };
}
const countTabs = s => (s && s.windows ? s.windows.reduce((n, w) => n + w.length, 0) : 0);
const summarize = s => (s ? { t: s.t, count: countTabs(s) } : null);

let autosaveReady = false, timer = null;
setTimeout(() => { autosaveReady = true; scheduleSave(); }, 15000);   // laisse Firefox finir sa propre restauration
function scheduleSave() {
  if (!autosaveReady) return;
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const s = await snapshot();
    if (countTabs(s)) await browser.storage.local.set({ last: s });
  }, 4000);
}
for (const ev of ["onCreated", "onRemoved", "onMoved", "onAttached", "onDetached"]) browser.tabs[ev].addListener(scheduleSave);
browser.tabs.onUpdated.addListener(scheduleSave, { properties: ["url", "pinned"] });
browser.windows.onRemoved.addListener(scheduleSave);

async function restore(sess, onlyMissing) {
  if (!sess || !countTabs(sess)) return 0;
  const existing = (await browser.contextualIdentities.query({})) || [];
  const idMap = {};
  let changed = false;
  for (const c of sess.containers || []) {
    let cur = existing.find(x => x.cookieStoreId === c.id && x.name === c.name) || existing.find(x => x.name === c.name);
    if (!cur) {
      try { cur = await browser.contextualIdentities.create({ name: c.name, color: c.color, icon: c.icon }); existing.push(cur); }
      catch (e) { continue; }
    }
    idMap[c.id] = cur.cookieStoreId;
    if (c.route && !map[cur.cookieStoreId]) { map[cur.cookieStoreId] = c.route; changed = true; }          // on ne touche pas aux routes déjà réglées
    if (c.backup && !backup[cur.cookieStoreId]) { backup[cur.cookieStoreId] = c.backup; changed = true; }
  }
  if (changed) await browser.storage.local.set({ map, backup });

  const have = new Set();
  if (onlyMissing) for (const tb of await browser.tabs.query({})) have.add((tb.cookieStoreId || DEFAULT_ID) + "|" + tb.url);
  let opened = 0;
  const open = async (tab, winId, first) => {
    const cs = tab.c ? idMap[tab.c] : null;
    if (tab.c && !cs) return;
    if (have.has((cs || DEFAULT_ID) + "|" + tab.url)) return;
    const o = { url: tab.url, pinned: tab.pinned, active: first, windowId: winId };
    if (cs) o.cookieStoreId = cs;
    if (!first) { o.discarded = true; if (tab.title) o.title = tab.title; }          // chargés à la demande : léger
    try { await browser.tabs.create(o); opened++; }
    catch (e) { try { delete o.discarded; delete o.title; await browser.tabs.create(o); opened++; } catch (e2) {} }
  };
  if (onlyMissing) {
    const cur = await browser.windows.getLastFocused({ windowTypes: ["normal"] });
    for (const w of sess.windows) for (const tab of w) await open(tab, cur.id, false);
  } else {
    for (const w of sess.windows) {
      const win = await browser.windows.create({});
      const blank = win.tabs && win.tabs[0] && win.tabs[0].id;
      let first = true;
      for (const tab of w) { await open(tab, win.id, first); first = false; }
      if (blank && opened) { try { await browser.tabs.remove(blank); } catch (e) {} }
    }
  }
  scheduleSave();
  return opened;
}

browser.runtime.onStartup.addListener(async () => {
  const st = await browser.storage.local.get(["last", "autoRestore"]);
  if (st.last) await browser.storage.local.set({ prev: st.last });       // avant toute sauvegarde automatique
  setTimeout(async () => {
    const s = await browser.storage.local.get(["prev", "autoRestore"]);
    if (s.autoRestore !== false && s.prev) {
      const n = await restore(s.prev, true);
      if (n) { await ready; notify(t("n_restored", n)); }
    }
  }, 8000);
});

async function namedSave(name) {
  const s = await snapshot();
  const { named } = await browser.storage.local.get("named");
  const all = named || {};
  all[name] = s;
  const keys = Object.keys(all).sort((a, b) => all[b].t - all[a].t).slice(0, 30);   // 30 sessions au plus
  const kept = {}; keys.forEach(k => { kept[k] = all[k]; });
  await browser.storage.local.set({ named: kept });
  return countTabs(s);
}

browser.commands.onCommand.addListener(async cmd => {
  await ready;
  if (cmd === "save-session") {
    const d = new Date(), p = n => String(n).padStart(2, "0");
    const n = await namedSave(`${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`);
    notify(t("n_saved", n));
  } else if (cmd === "test-ip") {
    const [tb] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tb) return;
    let name = "—";
    try { name = (await browser.contextualIdentities.get(tb.cookieStoreId)).name; } catch (e) { name = t("default_container"); }
    const r = await testIp(tb.cookieStoreId);
    notify(r.ok ? t("n_test", name, r.ip) : t("n_test_fail", name, r.code || "?"));
  }
});

browser.runtime.onMessage.addListener(async msg => {
  if (!msg) return;
  if (msg.cmd === "testIp") return testIp(msg.id);
  if (msg.cmd === "sessions") {
    const s = await browser.storage.local.get(["last", "prev", "named"]);
    const named = Object.entries(s.named || {}).map(([name, v]) => ({ name, t: v.t, count: countTabs(v) }))
                        .sort((a, b) => b.t - a.t);
    return { last: summarize(s.last), prev: summarize(s.prev || s.last), named };
  }
  if (msg.cmd === "save") return namedSave(String(msg.name || "").trim().slice(0, 60) || "session");
  if (msg.cmd === "restore") {
    const s = await browser.storage.local.get(["last", "prev", "named"]);
    const sess = msg.which === "named" ? (s.named || {})[msg.name] : (s.prev || s.last);
    return restore(sess, false);
  }
  if (msg.cmd === "delete") {
    const { named } = await browser.storage.local.get("named");
    if (named) { delete named[msg.name]; await browser.storage.local.set({ named }); }
    return true;
  }
});

// =====================================================================================
// Actualisation : alternative à F5 + actualisation automatique + « à chaque retour sur l'onglet »
// =====================================================================================
const RELOAD_SECS = [0, 15, 30, 60, 120, 300, 600, 1800];

function setAuto(tabId, secs, onSwitch) {
  if (!secs && !onSwitch) auto.delete(tabId);
  else auto.set(tabId, { secs, next: Date.now() + secs * 1000, onSwitch: !!onSwitch });
  browser.tabs.get(tabId).then(badge).catch(() => {});
}
async function reloadTab(tabId, hard) {
  try { await browser.tabs.reload(tabId, { bypassCache: !!hard }); return true; } catch (e) { return false; }
}
setInterval(async () => {
  const now = Date.now();
  for (const [id, a] of auto) {
    if (a.secs && now >= a.next) {
      a.next = now + a.secs * 1000;                       // reprogrammé d'abord : pas de rafale
      if (!(await reloadTab(id, false))) auto.delete(id);   // onglet fermé
    }
  }
}, 1000);
browser.tabs.onRemoved.addListener(id => auto.delete(id));
browser.tabs.onActivated.addListener(async info => {
  const a = auto.get(info.tabId);
  if (!(reloadOnSwitch || (a && a.onSwitch))) return;
  setTimeout(async () => {                                 // laisse Firefox charger un onglet « endormi » avant de décider
    try {
      const tb = await browser.tabs.get(info.tabId);
      if (tb.active && tb.status !== "loading" && /^(https?|ftp|file):/i.test(tb.url || "")) await reloadTab(info.tabId, false);
    } catch (e) {}
  }, 400);
});
// menu clic droit : coche l'intervalle de l'onglet visé
try {
  browser.menus.onShown.addListener(async (info, tab) => {
    if (!tab || !info.contexts.includes("tab")) return;
    const a = auto.get(tab.id) || { secs: 0, onSwitch: false };
    for (const secs of RELOAD_SECS) { try { await browser.menus.update("ar:" + secs, { checked: secs === a.secs }); } catch (e) {} }
    try { await browser.menus.update("ar:switch", { checked: !!a.onSwitch }); } catch (e) {}
    browser.menus.refresh();
  });
} catch (e) {}

browser.commands.onCommand.addListener(async cmd => {
  if (cmd !== "reload-tab") return;
  const [tb] = await browser.tabs.query({ active: true, currentWindow: true });
  if (tb) reloadTab(tb.id, false);
});
browser.runtime.onMessage.addListener(async msg => {
  if (!msg) return;
  if (msg.cmd === "reloadTab") return reloadTab(msg.tabId, msg.hard);
  if (msg.cmd === "getAuto") return auto.get(msg.tabId) || { secs: 0, onSwitch: false };
  if (msg.cmd === "setAuto") { setAuto(msg.tabId, msg.secs, msg.onSwitch); return true; }
});
