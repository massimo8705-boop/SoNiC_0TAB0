const COLORS = { blue: "#37adff", turquoise: "#00c79a", green: "#51cd00", yellow: "#ffcb00", orange: "#ff9f00",
                 red: "#ff613d", pink: "#ff4bda", purple: "#af51f5", toolbar: "#7c7c7d" };
const PICK = ["blue", "orange", "green", "purple", "red", "turquoise", "pink", "yellow"];
const $ = s => document.querySelector(s);
let map = {}, backup = {}, mine = [], detectApp = true, appRoutes = null, ids = [], results = {};
const save = () => saveState({ map, backup, mine, detectApp });
function el(tag, props = {}, ...kids) {
  const e = Object.assign(document.createElement(tag), props);
  kids.forEach(k => e.append(k));
  return e;
}

function routeSelect(selected, onPick) {
  const wrap = el("div");
  const sel = el("select");
  const opts = [["", t("route_none")]];
  mine.forEach(r => opts.push([r.proxy, `${r.name} · ${shortProxy(r.proxy)}`]));
  (appRoutes || []).forEach(r => { if (!mine.some(m => m.proxy === r.proxy)) opts.push([r.proxy, t("route_app", r.name)]); });
  if (selected && !opts.some(o => o[0] === selected)) opts.push([selected, shortProxy(selected)]);
  opts.push(["__other", t("route_other")]);
  opts.forEach(([v, x]) => sel.append(el("option", { value: v, textContent: x, selected: v === (selected || "") })));
  const inp = el("input", { placeholder: t("ph_proxy"), hidden: true });
  sel.onchange = () => {
    if (sel.value === "__other") { inp.hidden = false; inp.focus(); } else onPick(sel.value);
  };
  inp.onkeydown = async e => {
    if (e.key !== "Enter" || !inp.value.trim()) return;
    const v = inp.value.trim();
    if (!parseProxy(v)) { inp.style.borderColor = "#ff6b6b"; inp.title = t("bad_addr"); return; }
    if (!mine.some(m => m.proxy === v)) mine.push({ name: shortProxy(v), proxy: v });
    await save(); onPick(v);
  };
  wrap.append(sel, inp);
  wrap.value = () => (sel.value === "__other" ? inp.value.trim() : sel.value);
  return wrap;
}

async function setRoute(id, proxy) {
  if (proxy) map[id] = proxy; else delete map[id];
  delete results[id];
  await save();
  render();
}
const openTab = (id, url) =>
  browser.tabs.create(Object.assign({ url }, id === DEFAULT_ID ? {} : { cookieStoreId: id })).then(() => window.close());

async function testOne(id) {
  results[id] = { busy: true };
  render();
  results[id] = await browser.runtime.sendMessage({ cmd: "testIp", id });
  render();
}
const errText = r => r.code ? t("err_" + r.code) : (r.error || "?");

function resultLine(id) {
  const r = results[id];
  if (!r) return ["", ""];
  if (r.busy) return ["", t("res_testing")];
  if (!r.ok) return ["bad", "✖ " + errText(r)];
  const same = ids.filter(c => c.cookieStoreId !== id && results[c.cookieStoreId] && results[c.cookieStoreId].ok &&
                              results[c.cookieStoreId].ip === r.ip);
  if (id !== DEFAULT_ID && !map[id] && same.every(c => c.cookieStoreId === DEFAULT_ID)) return ["", t("res_normal", r.ip)];
  if (same.length) {
    if (id !== DEFAULT_ID && map[id] && same.some(c => c.cookieStoreId === DEFAULT_ID)) return ["dup", t("res_leak", r.ip)];
    return ["dup", t("res_dup", r.ip, same.map(c => c.name).join(", "))];
  }
  return ["good", t("res_ok", r.ip)];
}

let renderSeq = 0;
async function render() {
  const seq = ++renderSeq;
  let all = [{ cookieStoreId: DEFAULT_ID, name: t("default_container"), color: "toolbar" }];
  let ok = true;
  try {
    const c = await browser.contextualIdentities.query({});
    if (!c) throw new Error("off");
    all = all.concat(c);
  } catch (e) { ok = false; }
  if (seq !== renderSeq) return;                       // un rendu plus récent a pris le relais
  ids = all;
  const list = $("#list");
  list.replaceChildren();
  $("#nocontainers").hidden = ok;
  for (const c of ids) {
    const busy = results[c.cookieStoreId] && results[c.cookieStoreId].busy;
    const [cls, txt] = resultLine(c.cookieStoreId);
    const row = el("div", { className: "row" },
      el("span", { className: "dot", style: `background:${COLORS[c.color] || "#888"}` }),
      el("span", { className: "name", textContent: c.name, title: c.name }),
      el("button", { textContent: t("open"), onclick: () => openTab(c.cookieStoreId) }),
      el("button", { textContent: t("test"), disabled: !!busy, onclick: () => testOne(c.cookieStoreId) }));
    const sel = routeSelect(map[c.cookieStoreId], p => setRoute(c.cookieStoreId, p));
    sel.className = "sel";
    row.append(sel, el("div", { className: "res " + cls, textContent: txt }));
    list.append(row);
  }
  const nr = $("#newroute");
  nr.replaceChildren();
  window.newSel = routeSelect("", () => {}); nr.append(window.newSel);
  const done = ids.filter(c => results[c.cookieStoreId] && results[c.cookieStoreId].ok);
  const ips = new Set(done.map(c => results[c.cookieStoreId].ip));
  $("#summary").textContent = done.length > 1 ? t("summary", ips.size, done.length) : "";
}

// ---- sessions ---------------------------------------------------------------------
const fmt = ts => new Date(ts).toLocaleString(LANG === "fr" ? "fr-FR" : "en-GB", { dateStyle: "short", timeStyle: "short" });
function flash(text) { $("#smsg").textContent = text; setTimeout(() => { $("#smsg").textContent = ""; }, 4000); }
async function renderSessions() {
  const s = await browser.runtime.sendMessage({ cmd: "sessions" });
  const box = $("#slist"); box.replaceChildren();
  $("#sprev").disabled = !(s.prev && s.prev.count);
  $("#sprev").title = s.prev && s.prev.count ? `${fmt(s.prev.t)} — ${t("sess_tabs", s.prev.count)}` : t("sess_prev_none");
  if (!s.named.length) { box.append(el("div", { className: "hint", textContent: t("sess_none") })); return; }
  for (const n of s.named) {
    box.append(el("div", { className: "srow" },
      el("span", { className: "n", textContent: n.name, title: fmt(n.t) }),
      el("small", { textContent: t("sess_tabs", n.count) }),
      el("button", { textContent: t("sess_restore"), onclick: async () => {
        flash(t("sess_restored", await browser.runtime.sendMessage({ cmd: "restore", which: "named", name: n.name }))); } }),
      el("button", { textContent: "✕", title: t("sess_delete"), onclick: async () => {
        await browser.runtime.sendMessage({ cmd: "delete", name: n.name }); renderSessions(); } })));
  }
}
$("#sprev").onclick = async () => {
  const n = await browser.runtime.sendMessage({ cmd: "restore", which: "prev" });
  flash(n ? t("sess_restored", n) : t("sess_nothing"));
};
$("#ssave").onclick = async () => {
  const name = $("#sname").value.trim() || new Date().toLocaleString();
  const n = await browser.runtime.sendMessage({ cmd: "save", name });
  $("#sname").value = ""; flash(t("sess_saved", n)); renderSessions();
};

// ---- actualisation de l'onglet actif ------------------------------------------------
const SECS = [0, 15, 30, 60, 120, 300, 600, 1800];
let curTab = null;
async function renderReload() {
  const [tb] = await browser.tabs.query({ active: true, currentWindow: true });
  curTab = tb || null;
  const sel = $("#rlsecs"); sel.replaceChildren();
  const a = curTab ? await browser.runtime.sendMessage({ cmd: "getAuto", tabId: curTab.id }) : { secs: 0, onSwitch: false };
  sel.append(el("option", { value: "-1", textContent: t("rl_auto") + " — " + t("rl_off").toLowerCase(), selected: !a.secs }));
  SECS.filter(x => x).forEach(x => sel.append(el("option", { value: String(x), textContent: t("rl_" + x), selected: x === a.secs })));
  $("#rlsw").checked = !!a.onSwitch;
  [$("#rlnow"), $("#rlhard"), sel, $("#rlsw")].forEach(e => { e.disabled = !curTab; });
}
const rlFlash = txt => { $("#rlmsg").textContent = txt; setTimeout(() => { $("#rlmsg").textContent = ""; }, 2500); };
async function doReload(hard) {
  if (!curTab) return rlFlash(t("rl_notab"));
  await browser.runtime.sendMessage({ cmd: "reloadTab", tabId: curTab.id, hard });
  rlFlash(t("rl_done"));
}
$("#rlnow").onclick = () => doReload(false);
$("#rlhard").onclick = () => doReload(true);
const saveAuto = () => curTab && browser.runtime.sendMessage({ cmd: "setAuto", tabId: curTab.id,
  secs: Math.max(0, parseInt($("#rlsecs").value, 10)), onSwitch: $("#rlsw").checked });
$("#rlsecs").onchange = saveAuto;
$("#rlsw").onchange = saveAuto;

async function init() {
  await initLang();
  bindLang($("#lang"), () => { renderAll(); });
  const s = await loadState();
  map = s.map; backup = s.backup; mine = s.mine; detectApp = s.detectApp;
  const st = $("#state");
  if (detectApp) {
    appRoutes = await fetchAppRoutes();
    if (appRoutes !== null) {
      st.hidden = false; st.className = "ok";
      st.textContent = appRoutes.length ? t("app_ok", appRoutes.length) : t("app_none");
    }
  }
  applyI18n();
  bindHelpLinks();
  await render();
  renderSessions();
  renderReload();
}
function renderAll() {
  const st = $("#state");
  if (!st.hidden) st.textContent = appRoutes && appRoutes.length ? t("app_ok", appRoutes.length) : t("app_none");
  bindHelpLinks(); render(); renderSessions(); renderReload();
}
function bindHelpLinks() {
  $("#opts").onclick = e => { e.preventDefault(); browser.runtime.openOptionsPage(); window.close(); };
  const o2 = $("#opts2"); if (o2) o2.onclick = $("#opts").onclick;
}

$("#testall").onclick = async () => {
  $("#testall").disabled = true;
  await Promise.all(ids.map(c => testOne(c.cookieStoreId)));
  $("#testall").disabled = false;
};
$("#create").onclick = async () => {
  const name = $("#newname").value.trim();
  if (!name) { $("#newname").focus(); return; }
  const ci = await browser.contextualIdentities.create({ name, color: PICK[ids.length % PICK.length], icon: "circle" });
  const p = window.newSel.value();
  if (p) { map[ci.cookieStoreId] = p; await save(); }
  openTab(ci.cookieStoreId);
};
init();
