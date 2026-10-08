// Test PRIPINACE 'Desky na spodnich policich' (slot shelfboard) na strance Generator stolu 01 v prohlizeci (bot8, 2026-10-07; Robert: spodni police ma mit volbu byt bez desky, jen profily / ram).
// SKUTECNA stranka + SKUTECNY modul voleb nad SKUTECNYM kodem stolu (api/stul_shop.py) pres most _most_stul.py (prihlaseny zamestnanec, produkt 4934).
// Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_police_bez_desky/test_police_bez_desky_stranka.js 4934
// Hlida: pripinac je v panelu hned za poctem polic, vychozi zapnuty; vypnuti = nova cena a kod, jiny model, nabidka ve 3D 'Vratit desku police'; bez polic je pripinac skryty a hodnota se vraci
// na 'zapnuto'; odkaz (#hash) nese vypnutou desku a po nacteni ji obnovi; 'Vychozi hodnoty' ji vrati; bez JS chyb.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, opts) {
  const ctx = await browser.newContext(Object.assign({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" }, opts || {}));
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, hash) {
  await p.page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.ov && Object.keys(S.ov.debug().handles).length > 0; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
// vychozi stul ma rameno 560 > 500, proto modul voleb po nacteni SAM zapne sikme vzpery (auto_on; druhy dotaz): snimky stavu se berou az po nem, jinak se cena a kod porovnavaji napric zapnutymi / vypnutymi vzperami
const settled = async (p) => {
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.sel && S.sel.braces === true && S.last && S.last.selection && S.last.selection.braces === true; }, null, { polling: 200, timeout: 90000 });
  await idle(p, 1500);
};
const sel = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const stav = page => page.evaluate(() => {
  const S = window.__pdcState, l = S.last || {}, sl = document.querySelector("[data-slot=shelfboard]");
  const cast = (((l.vodici || {}).ovladani || {}).casti || []).find(c => c.id === "shelf1");
  return { price: l.price && l.price.net, kod: l.kod, hash: l.hash, valid: l.valid, delta: ((l.options || {}).shelfboard || {}).on && l.options.shelfboard.on.price_delta, hidden: ((l.options || {}).shelfboard || {}).hidden,
           slot: !!sl, slotHidden: sl ? (sl.hidden || sl.offsetParent === null) : null, checked: sl ? sl.querySelector("input").checked : null, label: sl ? (sl.querySelector("label") || sl).textContent.trim() : null,
           menu: cast ? cast.menu.map(m => ({ text: m.text, nastav: m.nastav })) : null, param: cast ? cast.param : null, locHash: location.hash };
});
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const p = await mk(browser);
  try {
    await load(p);
    await settled(p);
    const pg = p.page;
    // ---- A) vychozi stav
    const a = await stav(pg);
    t("A1 pripinac 'Desky na spodnich policich' je v panelu, zapnuty, viditelny", a.slot && a.checked === true && a.slotHidden === false && /Desky na spodních policích/.test(a.label), a);
    const poradi = await pg.evaluate(() => { const ids = Array.from(document.querySelectorAll(".pdc-slot[data-slot]")).map(s => s.dataset.slot), i = ids.indexOf("shelf"); return { i, dalsi: ids[i + 1], ids: ids.slice(0, 14) }; });
    t("A2 pripinac je v panelu hned za poctem polic (shelf -> shelfboard)", poradi.i >= 0 && poradi.dalsi === "shelfboard", poradi);
    t("A3 vychozi vyber: shelfboard = true, v hashi odkazu je shelfboard=1; ve 3D casti police je nabidka 'Odebrat desku police' a param nese shelfboard",
      (await sel(pg)).shelfboard === true && /[#&]shelfboard=1(&|$)/.test(a.locHash) && !!a.menu && a.menu.some(m => m.text === "Odebrat desku police" && m.nastav && m.nastav.shelfboard === false) && a.param.includes("shelfboard"), { menu: a.menu && a.menu.map(m => m.text), param: a.param, hashKonec: a.locHash.slice(-70) });
    const model0 = p.trk.glb, res0 = p.trk.resolve;
    // ---- B) vypnuti desky
    await pg.locator("[data-slot=shelfboard] label").first().click(); await idle(p, 1500);
    const b = await stav(pg);
    t("B1 vypnuti desky: vyber shelfboard = false, platne, nova cena (nizsi) a jiny kod", (await sel(pg)).shelfboard === false && b.valid === true && b.price < a.price && b.kod !== a.kod, [a.price, b.price, a.kod, b.kod]);
    t("B2 prisel novy dotaz i novy model (3D se prekreslilo)", p.trk.resolve > res0 && p.trk.glb > model0, [res0, p.trk.resolve, model0, p.trk.glb]);
    t("B3 nabidka 'vratit desku' stoji presne uspoReny rozdil (options.shelfboard.on.price_delta) a pripinac zustava zapnuty/odskrtnuty viditelne", Math.abs(b.delta - (a.price - b.price)) < 0.011 && b.checked === false && b.slotHidden === false, [b.delta, a.price - b.price, b.checked]);
    t("B4 ve 3D casti police je nabidka 'Vratit desku police' (nastav shelfboard=true)", !!b.menu && b.menu.some(m => m.text === "Vrátit desku police" && m.nastav && m.nastav.shelfboard === true) && !b.menu.some(m => m.text === "Odebrat desku police"), b.menu);
    t("B5 odkaz (#hash) nese vypnutou desku (shelfboard=0)", /[#&]shelfboard=0(&|$)/.test(b.locHash), b.locHash.slice(-70));
    const hashB = b.locHash;
    // ---- C) odkaz obnovi stav
    const p2 = await mk(browser);
    await load(p2, hashB);
    const c = await stav(p2.page);
    t("C1 nacteni odkazu s vypnutou deskou: vyber shelfboard = false, odskrtnuto, stejna cena a kod", (await sel(p2.page)).shelfboard === false && c.checked === false && c.price === b.price && c.kod === b.kod, [c, b.price, b.kod]);
    await p2.ctx.close();
    // ---- D) bez polic je pripinac skryty a hodnota se vraci na zapnuto
    await pg.locator("[data-slot=shelf] .pdc-num").fill("0"); await pg.keyboard.press("Tab"); await idle(p, 1500);
    const d = await stav(pg);
    t("D1 bez spodnich polic: pripinac je skryty (options.shelfboard.hidden) a server hodnotu vratil na zapnuto", d.slotHidden === true && d.hidden === true && (await sel(pg)).shelfboard === true, [d.slotHidden, d.hidden, await sel(pg)]);
    await pg.locator("[data-slot=shelf] .pdc-num").fill("1"); await pg.keyboard.press("Tab"); await idle(p, 1500);
    const e = await stav(pg);
    t("D2 po vraceni police je pripinac zase videt a zapnuty (volba se pri 0 polic zahodila)", e.slotHidden === false && e.checked === true && e.price === a.price && e.kod === a.kod, [e.slotHidden, e.checked, e.price, a.price, e.kod, a.kod]);
    // ---- E) 'Vychozi hodnoty' vrati desku
    await pg.locator("[data-slot=shelfboard] label").first().click(); await idle(p, 1500);
    t("E1 (priprava) deska je zase vypnuta", (await sel(pg)).shelfboard === false);
    await pg.locator(".pdc-head .pdc-link").first().click(); await settled(p);
    const f = await stav(pg);
    t("E2 'Vychozi hodnoty': deska je zase zapnuta, cena i kod jako na zacatku", (await sel(pg)).shelfboard === true && f.checked === true && f.price === a.price && f.kod === a.kod, [f.checked, f.price, a.price, f.kod, a.kod]);
    t("F1 bez JS chyb na strance", p.errs.length === 0, p.errs.slice(0, 3));
  } catch (e) {
    t("test spadl na vyjimce", false, String((e && e.stack) || e).split("\n").slice(0, 4).join(" | "));
  }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
