const $ = s => document.querySelector(s);
let st = { map: {}, backup: {}, mine: [], detectApp: true };
const mk = (tag, props = {}) => Object.assign(document.createElement(tag), props);
const cell = (...k) => { const td = mk("td"); td.append(...k); return td; };
function input(v, ph, w) { const i = mk("input", { type: "text", value: v || "", placeholder: ph }); i.style.width = w; return i; }

function drawRoutes() {
  const tbl = $("#routes"); tbl.replaceChildren();
  st.mine.forEach((r, i) => {
    const n = input(r.name, t("ph_name"), "180px"), p = input(r.proxy, "socks5://IP:PORT", "320px");
    n.oninput = () => (r.name = n.value);
    p.oninput = () => { r.proxy = p.value; p.style.borderColor = !p.value || parseProxy(p.value) ? "" : "#ff6b6b"; };
    const del = mk("button", { textContent: "✕", title: "✕" });
    del.onclick = () => { st.mine.splice(i, 1); drawRoutes(); drawMap(); };
    const tr = mk("tr"); tr.append(cell(n), cell(p), cell(del)); tbl.append(tr);
  });
  if (!st.mine.length) { const tr = mk("tr"); tr.append(cell(mk("span", { className: "muted", textContent: t("no_routes") }))); tbl.append(tr); }
}

async function drawMap() {
  const tbl = $("#t"); tbl.replaceChildren();
  let ids = [];
  try { ids = (await browser.contextualIdentities.query({})) || []; } catch (e) {}
  if (!ids.length) { const tr = mk("tr"); tr.append(cell(mk("span", { className: "muted", textContent: t("no_cont") }))); tbl.append(tr); return; }
  const app = st.detectApp ? await fetchAppRoutes() : null;
  for (const c of ids) {
    const sel = mk("select"); sel.style.width = "380px";
    const opts = [["", t("normal")]];
    st.mine.filter(r => parseProxy(r.proxy)).forEach(r => opts.push([r.proxy, `${r.name} · ${shortProxy(r.proxy)}`]));
    (app || []).forEach(r => { if (!st.mine.some(m => m.proxy === r.proxy)) opts.push([r.proxy, t("route_app", r.name)]); });
    const cur = st.map[c.cookieStoreId] || "";
    if (cur && !opts.some(o => o[0] === cur)) opts.push([cur, shortProxy(cur)]);
    opts.forEach(([v, x]) => sel.append(mk("option", { value: v, textContent: x, selected: v === cur })));
    sel.onchange = () => { if (sel.value) st.map[c.cookieStoreId] = sel.value; else delete st.map[c.cookieStoreId]; };

    const sel2 = mk("select"); sel2.style.width = "380px";
    const curB = st.backup[c.cookieStoreId] || "";
    [["", t("no_backup")]].concat(opts.filter(o => o[0])).forEach(([v, x]) =>
      sel2.append(mk("option", { value: v, textContent: x, selected: v === curB })));
    sel2.onchange = () => { if (sel2.value) st.backup[c.cookieStoreId] = sel2.value; else delete st.backup[c.cookieStoreId]; };

    const tr = mk("tr"); tr.append(cell(c.name), cell(sel)); tbl.append(tr);
    const tr2 = mk("tr"); tr2.append(cell(mk("small", { textContent: t("backup_label") })), cell(sel2)); tbl.append(tr2);
  }
}

async function drawSessInfo() {
  const { last, autoRestore, reloadOnSwitch } = await browser.storage.local.get(["last", "autoRestore", "reloadOnSwitch"]);
  $("#reloadsw").checked = !!reloadOnSwitch;
  $("#autorestore").checked = autoRestore !== false;
  const n = last && last.windows ? last.windows.reduce((a, w) => a + w.length, 0) : 0;
  $("#sinfo").textContent = last ? t("sess_info", new Date(last.t).toLocaleString(LANG === "fr" ? "fr-FR" : "en-GB"), n) : t("sess_info_none");
}

function drawPresets() {
  const p = $("#preset"); p.replaceChildren(mk("option", { value: "", textContent: t("preset") }));
  PRESETS.forEach(x => p.append(mk("option", { value: x.proxy, textContent: x.name })));
}
function drawAll() { document.title = t("title"); drawPresets(); drawRoutes(); drawMap(); drawSessInfo(); }

async function init() {
  await initLang();
  bindLang($("#lang"), drawAll);
  st = await loadState();
  $("#detect").checked = st.detectApp;
  $("#detect").onchange = () => { st.detectApp = $("#detect").checked; drawMap(); };
  $("#reloadsw").onchange = () => browser.storage.local.set({ reloadOnSwitch: $("#reloadsw").checked });
  $("#autorestore").onchange = () => browser.storage.local.set({ autoRestore: $("#autorestore").checked });
  applyI18n();
  drawAll();
}
$("#addroute").onclick = () => {
  const p = $("#preset");
  const preset = PRESETS.find(x => x.proxy === p.value);
  st.mine.push({ name: preset ? preset.name : "", proxy: preset ? preset.proxy : "" });
  p.value = ""; drawRoutes();
};
$("#save").onclick = async () => {
  const bad = st.mine.filter(r => r.proxy.trim() && !parseProxy(r.proxy));
  if (bad.length) { $("#ok").className = "bad"; $("#ok").textContent = t("bad_addr") + " : " + bad[0].proxy; return; }
  st.mine = st.mine.filter(r => r.proxy.trim()).map(r => ({ name: r.name.trim() || shortProxy(r.proxy), proxy: r.proxy.trim() }));
  await saveState(st);
  $("#ok").className = "good"; $("#ok").textContent = t("saved");
  drawRoutes(); drawMap();
  setTimeout(() => ($("#ok").textContent = ""), 2500);
};
$("#export").onclick = () => {
  const blob = new Blob([JSON.stringify({ app: "SoNiC_0TAB0", version: 2, mine: st.mine, map: st.map, backup: st.backup }, null, 2)], { type: "application/json" });
  const a = mk("a", { href: URL.createObjectURL(blob), download: "sonic_0tab0_settings.json" });
  a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("#import").onchange = async e => {
  try {
    const d = JSON.parse(await e.target.files[0].text());
    if (!Array.isArray(d.mine)) throw new Error("?");
    st.mine = d.mine.filter(r => r && parseProxy(r.proxy)).map(r => ({ name: String(r.name || ""), proxy: String(r.proxy) }));
    // les identifiants de conteneur sont propres à chaque profil : on ne reprend que ceux qui existent ici
    const known = new Set(((await browser.contextualIdentities.query({})) || []).map(c => c.cookieStoreId));
    st.map = {}; st.backup = {};
    Object.entries(d.map || {}).forEach(([k, v]) => { if (known.has(k) && parseProxy(v)) st.map[k] = v; });
    Object.entries(d.backup || {}).forEach(([k, v]) => { if (known.has(k) && parseProxy(v)) st.backup[k] = v; });
    await saveState(st);
    $("#imsg").className = "good"; $("#imsg").textContent = t("import_ok", st.mine.length);
    drawRoutes(); drawMap();
  } catch (err) { $("#imsg").className = "bad"; $("#imsg").textContent = t("import_fail", err.message); }
};
init();
