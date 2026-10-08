// Test STRANKY GENERATOR STOLU 04 (system 41, ergonomicky stul SSE) v SKUTECNEM prohlizeci (bot8, 2026-10-05): spolecny modul voleb vykresli jen sloty SSE (rozmery, stredni noha, spodni police, supliky),
// vychozi stav 2000 x 900 x 830, kota mezery mezi nohami 1 570 v 3D, zmena rozmeru / police / supliku meni cenu a model, stredni noha u sirky nad prahem, hash v URL, "Vlozit do Sceny" je zakazano,
// prepinac systemu nese hash, mobil 360 px. Nad skutecnym kodem stolu pres most scripts/2026-10-02_stul_testy/_most_stul.py (fiktivni karta 9879, nic se nezapisuje do DB):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID41=9879 --setenv=PID40=9877 --setenv=PRAVIDLA_TEST={} --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_sse/test_sse_stranka.js 4934
// PRAVIDLA_TEST={} je POVINNE: test pocita s VYCHOZIMI pravidly stolu (cena nohy SSE nezadana -> upozorneni v kusovniku, prah stredni nohy 2000 mm), nikoli se zivymi z app_settings
// (Robert 2026-10-05 zadal v Pravidlech ceny noh a prah 2600 mm -> kontroly 1l a 2a padaly); kontrola 0a to hlasi hned na zacatku.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w || 1400, height: h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  const trk = { pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  // pending se pocita jen u resolve; GLB jen posouva `last` (viewer nacita model dvakrat a jeden pozadavek Playwright nikdy neukonci -> pending by zustalo 1 a kazde cekani by trvalo 90 s)
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) trk.pending++; if (RES_RE.test(u) || GLB_RE.test(u)) trk.last = Date.now(); });
  const done = r => { const u = r.url(); if (RES_RE.test(u)) trk.pending--; if (RES_RE.test(u) || GLB_RE.test(u)) trk.last = Date.now(); };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
  console.log("   (idle: limit 90 s vyprsel, pending=" + p.trk.pending + ")");
};
async function load(p, pagePath, hash) {
  await p.page.goto("about:blank");                                         // jina jen cast #hash by stranku znovu nenacetla (stejny dokument)
  await p.page.goto(`${BASE}${pagePath}?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const last = p => p.page.evaluate(() => { const L = window.__pdcState.last; return { sel: L.selection, opt: L.options, notices: L.notices, errors: L.errors, price: L.price && L.price.net, valid: L.valid, hash: L.hash, ovl: !!(L.vodici && L.vodici.ovladani) }; });
const slotInfo = (p, id) => p.page.evaluate(id => {
  const root = document.querySelector(`[data-slot="${id}"]`);
  if (!root) return null;
  const cb = root.querySelector('input[type="checkbox"]'), rng = root.querySelector('input[type="range"]'), num = root.querySelector('input[type="number"]');
  const vis = !!(root.offsetWidth || root.offsetHeight || root.getClientRects().length);
  return { visible: vis && getComputedStyle(root).display !== "none", checked: cb ? cb.checked : null, rng: rng ? { value: rng.value, min: rng.min, max: rng.max, disabled: rng.disabled } : null, num: num ? num.value : null, text: root.innerText };
}, id);
const toggle = async (p, id) => { await p.page.evaluate(id => { const cb = document.querySelector(`[data-slot="${id}"] input[type="checkbox"]`); cb.click(); }, id); await idle(p, 1200); };
const setNum = async (p, id, v) => {
  await p.page.evaluate(({ id, v }) => { const n = document.querySelector(`[data-slot="${id}"] input[type="number"]`); n.value = String(v); n.dispatchEvent(new Event("input", { bubbles: true })); n.dispatchEvent(new Event("change", { bubbles: true })); }, { id, v });
  await idle(p, 1500);
};
const slotIds = p => p.page.evaluate(() => Array.from(document.querySelectorAll("[data-slot]")).map(e => e.getAttribute("data-slot")));
const koty = p => p.page.evaluate(() => { const V = window.__pdcState && window.__pdcState.viewer; return V && V.state ? Array.from(document.querySelectorAll(".v3d-dim, .v3d-dim-label, [class*='dim']")).map(e => (e.textContent || "").trim()).filter(x => /\d/.test(x)) : []; });

(async () => {
  console.log("\n## 0) predpoklad testu: vychozi pravidla stolu (PRAVIDLA_TEST={}), ne zive z app_settings");
  const pr = await (await fetch(`${BASE}/api/stul/pravidla?system=41`)).json().catch(() => ({}));
  const rv = pr.pravidla || {};
  t("0a pravidla systemu 41 jsou vychozi (cena nohy SSE nezadana, prah stredni nohy 2000 mm) - jinak spustit s PRAVIDLA_TEST={} (viz hlavicka)",
    Number(rv.cena_noha_sse_400) === 0 && Number(rv.cena_noha_sse_1100) === 0 && Number(rv.sirka_stredni_noha) === 2000, rv);
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const p = await mk(browser);
  console.log("\n## 1) vychozi stav generatoru 04 (stul SSE)");
  await load(p, "/stul-konfigurator-41.html", "");
  let L = await last(p);
  t("1a vychozi vyber SSE: 2000 x 900 x 830, police a supliky zapnute, 2 supliky", L.sel.w === 2000 && L.sel.d === 900 && L.sel.h === 830 && L.sel.shelf === 1 && L.sel.drawers === true && L.sel.drawercount === 2 && L.valid === true, L.sel);
  const ids = await slotIds(p);
  t("1b stranka ukazuje JEN sloty SSE (zadne stojky, panely, LED, kolecka, vyrezy, loziska)", ["w", "d", "h", "shelf", "drawers", "drawercount", "boxpos", "drawleft"].every(s => ids.includes(s)) && !ids.some(s => /^(posts|wheels|feet|panels|led|ledlight|socket|pet|braces|bracelen|sleeve|cut\d|bearings|arm|ov|panel|posth|sh\d)/.test(s)), ids);
  const w = await slotInfo(p, "w"), d = await slotInfo(p, "d"), h = await slotInfo(p, "h");
  t("1c posuvniky: sirka 800-3000, hloubka 480-1180, vyska 700-1000", w.rng.min === "800" && w.rng.max === "3000" && d.rng.min === "480" && d.rng.max === "1180" && h.rng.min === "700" && h.rng.max === "1000", [w.rng, d.rng, h.rng]);
  const sh = await slotInfo(p, "shelf");
  t("1d spodni police je prepinac (ne posuvnik poctu) a je zapnuta", sh && sh.visible && sh.checked === true && sh.rng === null, sh);
  const mid = await slotInfo(p, "mid");
  t("1e poloha stredni nohy se u sirky 2000 mm neukazuje (jen dve nohy)", !mid || !mid.visible, mid);
  t("1f cena je", L.price > 0, L.price);
  t("1g 3D ovladani (vodici) je pripojeno", L.ovl === true);
  const titul = await p.page.evaluate(() => ({ h1: document.querySelector("h1").textContent, title: document.title, brand: document.querySelector(".mw-brand").textContent, sysSw: document.getElementById("sysSwitch").innerText, scene: document.getElementById("sceneBtn") && { dis: document.getElementById("sceneBtn").disabled, st: document.getElementById("sceneStatus").textContent } }));
  t("1h zahlavi: Generator stolu 04 - ergonomicky stul SSE (viditelne se nejmenuje 'system 41', Robert 2026-10-08)", /04/.test(titul.h1) && /SSE/.test(titul.h1) && /04/.test(titul.title) && /04/.test(titul.brand) && !/syst[eé]m\s*41/i.test([titul.h1, titul.title, titul.brand].join(" ")), titul);
  const viditelny = await p.page.evaluate(() => document.title + "\n" + document.body.innerText);
  t("1h2 nikde na strance SSE neni viditelne 'system 41' (titulek, nadpis, prepinac, hlasky, kusovnik)", !/syst[eé]m\s*41/i.test(viditelny), (viditelny.match(/.{0,40}syst[eé]m\s*41.{0,40}/i) || [])[0]);
  t("1i 'Vlozit do Sceny' je zakazano s vysvetlenim", titul.scene && titul.scene.dis === true && /SSE/.test(titul.scene.st), titul.scene);
  t("1j prepinac nabizi system 40 (karta PID40), ne sebe", /systém 40/.test(titul.sysSw) && !/systém 41/.test(titul.sysSw), titul.sysSw);
  const labels = await p.page.evaluate(() => Array.from(document.querySelectorAll(".v3d-root *")).map(e => (e.children.length === 0 ? (e.textContent || "").trim() : "")).filter(x => /^[0-9 ]+( mm)?$/.test(x)));
  t("1k koty ve 3D: 830, 2 000, 900, 772, 285, 1 570 (mezera mezi nohami)", ["830", "2 000", "900", "772", "285", "1 570"].every(k => labels.some(x => x.replace(/ mm$/, "") === k)), labels);
  const bom = await p.page.evaluate(() => document.getElementById("bomBody").innerText);
  t("1l kusovnik pro zamestnance: profily, desky a UPOZORNENI na nezadanou cenu noh SSE", /profil 40/i.test(bom) && /laminodeska|Laminovaná/i.test(bom) && /Cena nohou SSE není zadaná/.test(bom), bom.slice(-500));
  const st = await p.page.evaluate(() => document.getElementById("staffProblems") ? document.getElementById("staffProblems").innerText : "");
  t("1m zadne chyby JS ve strance", p.errs.length === 0, p.errs.slice(0, 3));
  const cena0 = L.price, hash0 = L.hash;
  if (SHOT) await p.page.screenshot({ path: SHOT + "_1.png", fullPage: true });

  console.log("\n## 2) zmena rozmeru, police, supliku");
  await setNum(p, "w", 2400);
  L = await last(p);
  const mid2 = await slotInfo(p, "mid");
  t("2a sirka 2400 mm: stredni noha (slot mid je videt), hash a cena se zmenily, oznameni o deleni desek", mid2 && mid2.visible && L.hash !== hash0 && L.price !== cena0 && L.notices.some(n => n.slot === "mid" && n.action === "info"), [mid2 && mid2.visible, L.price, L.notices]);
  await setNum(p, "w", 2000);
  await toggle(p, "shelf");
  L = await last(p);
  t("2b spodni police vypnuta: vyber shelf=0, cena je nizsi", L.sel.shelf === 0 && L.price < cena0, [L.sel.shelf, L.price, cena0]);
  await toggle(p, "shelf");
  L = await last(p);
  t("2c police zapnuta zpet: stejna cena jako na zacatku", L.sel.shelf === 1 && L.price === cena0, [L.price, cena0]);
  await setNum(p, "d", 600);
  L = await last(p);
  const dr = await slotInfo(p, "drawers");
  t("2d hloubka 600 mm: supliky se nevejdou a odeberou se s oznamenim a duvodem (zadne supliky)", L.sel.drawers === false && L.notices.some(n => n.slot === "drawers" && n.action === "removed" && /hloubku stolu aspoň/.test(n.message)) && L.opt.drawers.on.disabled === true, [L.sel.drawers, L.notices, L.opt.drawers]);
  await setNum(p, "d", 900);
  await toggle(p, "drawers");
  L = await last(p);
  t("2e hloubka 900 mm: supliky lze znovu zapnout a jejich pocet / posun jsou videt", L.sel.drawers === true && L.opt.drawercount.max === 3 && (await slotInfo(p, "boxpos")).visible, L.sel);
  await setNum(p, "drawercount", 3);
  L = await last(p);
  t("2f tri supliky: vyber drawercount 3, cena vyssi", L.sel.drawercount === 3 && L.price > cena0, [L.sel.drawercount, L.price, cena0]);
  await setNum(p, "h", 1000);
  L = await last(p);
  t("2g vyska 1000 mm: platna a model se obnovil (hash jiny)", L.sel.h === 1000 && L.valid === true && L.hash !== hash0, [L.sel.h, L.valid]);
  const hashUrl = await p.page.evaluate(() => location.hash);
  t("2h hash v URL nese jen sloty SSE (#d=900&drawercount=3&h=1000...), zadne stojky / panely / kolecka / vyrezy", /h=1000/.test(hashUrl) && /drawercount=3/.test(hashUrl) && /w=2000/.test(hashUrl) && !/panels|posts|wheels|cut|bear|brace|petleg|sleeve/.test(hashUrl), hashUrl);
  t("2i zadne chyby JS", p.errs.length === 0, p.errs.slice(0, 3));

  console.log("\n## 3) hash z odkazu a prepnuti systemu");
  await load(p, "/stul-konfigurator-41.html", "#w=2600&d=1000&h=900&shelf=0&drawers=0");
  L = await last(p);
  t("3a hash #w=2600&d=1000&h=900&shelf=0&drawers=0 se nacetl", L.sel.w === 2600 && L.sel.d === 1000 && L.sel.h === 900 && L.sel.shelf === 0 && L.sel.drawers === false, L.sel);
  await load(p, "/stul-konfigurator-41.html", "#w=1800&posts=1&panels=1&led=1&wheels=1&cut1=1");
  L = await last(p);
  t("3b vyber z jineho systemu (stojky, panely, LED, kolecka, vyrez) se bez chyby zahodi, rozmer zustane", L.sel.w === 1800 && L.valid === true && L.sel.panels === false && L.sel.posts === false && L.sel.wheels === false && L.sel.cut1 === false, L.sel);
  const href = await p.page.evaluate(() => { const a = document.querySelector("#sysSwitch a[data-system='40']"); return a && a.getAttribute("href"); });
  t("3c odkaz na system 40 nese stejny hash", href && /^\/stul-konfigurator-40\.html#/.test(href) && /w=1800/.test(href), href);
  await load(p, "/stul-konfigurator-40.html", "#w=1800&d=900&h=950");
  const sw40 = await p.page.evaluate(() => document.getElementById("sysSwitch").innerText);
  t("3d generator 02 nabizi prepnuti na stul SSE (kdyz ma kartu), bez 'system 41'", (/SSE/.test(sw40) || sw40 === "") && !/syst[eé]m\s*41/i.test(sw40), sw40);

  console.log("\n## 3e) Ulozit jako vychozi (admin) na strance SSE: PUT podstrceny, nic se nezapisuje");
  const pk = await mk(browser);
  const putSse = [];
  await pk.ctx.route("**/api/shop/products/*/configurator/default", r => { putSse.push({ m: r.request().method(), u: r.request().url(), b: r.request().postData() }); r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ default_saved: true }) }); });
  await load(pk, "/stul-konfigurator-41.html", "#w=2200&d=800&h=860&drawers=0");
  await pk.page.waitForFunction(() => { const b = document.querySelector(".mw-win-defcfg"); return b && !b.hidden; }, null, { timeout: 15000 }).catch(() => {});
  const selK = await pk.page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
  await pk.page.click("#defSave"); await pk.page.click("#defSave"); await pk.page.waitForTimeout(900);
  const bodyK = putSse.length === 1 && putSse[0].m === "PUT" ? JSON.parse(putSse[0].b) : null;
  t("3e stranka SSE: admin ma okno 'Vychozi konfigurace' (3. sloupec) a druhy klik na 'Ulozit jako vychozi' posle JEDEN PUT s celym vyberem SSE (2200 x 800 x 860, supliky vypnute)",
    !!bodyK && /\/api\/shop\/products\/\d+\/configurator\/default$/.test(putSse[0].u) && JSON.stringify(bodyK.selection) === JSON.stringify(selK) && bodyK.selection.w === 2200 && bodyK.selection.d === 800 && bodyK.selection.h === 860
    && bodyK.selection.drawers === false && ["w", "d", "h", "mid", "shelf", "drawers", "drawercount", "boxpos", "drawleft"].every(k => k in bodyK.selection), [putSse.length, bodyK && Object.keys(bodyK.selection)]);
  t("3f stranka SSE: bez chyb JS pri ulozeni", pk.errs.length === 0, pk.errs.slice(0, 3));
  await pk.ctx.close();

  console.log("\n## 4) mobil 360 px");
  await p.ctx.close();
  const pm = await mk(browser, 360, 780);
  await load(pm, "/stul-konfigurator-41.html", "");
  const sc = await pm.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  t("4a mobil: bez horizontalniho posunu", sc.sw <= sc.cw + 1, sc);
  t("4b mobil: zadne chyby JS", pm.errs.length === 0, pm.errs.slice(0, 3));
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("SPADLO", e); process.exit(1); });
