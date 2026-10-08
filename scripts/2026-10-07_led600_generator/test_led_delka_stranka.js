// Test DELKY LED SVITIDLA na strance Generator stolu 01 + POCITADLA LUXU s LED 600 (bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru").
// SKUTECNA stranka + SKUTECNY modul voleb + viewer + skripty pocitadla luxu nad SKUTECNYM kodem stolu pres most _most_stul.py (prihlaseny admin, produkt 4934).
// Hlida: slot "Delka LED svitidla" (select 600 / 1200 mm; nedostupna delka u uzkeho stolu), volba 600 (2 svitidla, cena, hash v odkazu #ledlen=600), nabidka kratsiho svitidla u zakazaneho prepinace LED,
// 3D menu "Zvolit LED N mm", pocitadlo luxu s LED 600: cifra v HUD = NEZAVISLY vypocet LuxCore + katalog LuxData nad payloadem ze serveru (typ led_600, stupen 16 W), tlacitka stupnu se pri zmene TYPU
// svitidla postavi znovu (1200: 33 W / 21 W, 600: bez voleb, jediny stupen), zvoleny stupen 21 W se pri prechodu na 600 vrati na vychozi, mobil 360 px, zadne chyby JS.
// Spusteni z KANDIDATNIHO korene (prepis webapp s upravenym stul-luxy.js a lux-data.js; viz prepare_cand_web.sh), DB pres systemd-run, pocitadlo potrebuje internet (three.js z jsdelivr):
//   cd $SP/led/mirror2 && systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=$PWD \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_led600_generator/test_led_delka_stranka.js 4934
// (po nasazeni je tentyz test platny i nad zivym stromem: --working-directory=/opt/konfigurator; SNIMKY=/adresar ulozi screenshoty)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const path = require("path");
const fs0 = require("fs");
// koren se bere z pracovniho adresare mostu (kandidatni koren s prepisem webapp: tam je lux-data.js se zaznamem LED600; node resolvuje symlinky, takze __dirname by vedl do zive slozky), jinak z polohy skriptu
const REPO = fs0.existsSync(path.join(process.cwd(), "webapp/js/lux/lux-data.js")) && fs0.existsSync(path.join(process.cwd(), "api")) ? process.cwd() : path.resolve(__dirname, "..", "..");
const LuxCore = require(path.join(REPO, "webapp/js/lux/lux-core.js")), LuxData = require(path.join(REPO, "webapp/js/lux/lux-data.js"));
const BASE = process.env.BASE, SNIMKY = process.env.SNIMKY || "";
const TYP_SKU = { led_1200: "LED1200", led_600: "LED600" };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const selOf = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const nacten = page => page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { timeout: 120000 });
const slotInfo = page => page.evaluate(() => {
  const n = document.querySelector("[data-slot=ledlen]");
  if (!n) return null;
  const s = n.querySelector("select");
  return { hidden: n.offsetParent === null, value: s && s.value, options: s ? [...s.options].map(o => ({ v: o.value, text: o.textContent })) : [], label: (n.querySelector("label") || {}).textContent };
});
const sirka = async (page, w) => {
  await page.fill("[data-slot=w] .pdc-num", String(w)); await page.keyboard.press("Enter");
  await page.waitForFunction(v => window.__pdcState.last && window.__pdcState.last.selection && window.__pdcState.last.selection.w === v && window.__pdcState.sel.w === v, w, { timeout: 180000 });
  await page.waitForTimeout(800);
};
// pocka na odpoved serveru s danou delkou svitidla a na dokonceny model
const cekejDelku = async (page, d) => {
  await page.waitForFunction(v => window.__pdcState.sel.ledlen === v && window.__pdcState.last && window.__pdcState.last.selection && window.__pdcState.last.selection.ledlen === v && !window.__pdcState.pending, d, { timeout: 180000, polling: 200 });
  await nacten(page);
  await page.waitForTimeout(900);
};
const payload = page => page.evaluate(() => { const S = window.__pdcState; return { hash: S.last.hash, o: (S.last.vodici && S.last.vodici.osvetleni) || null, price: (S.last.price || {}).net, sel: S.last.selection }; });
const hudMean = page => page.evaluate(() => { const e = document.querySelector(".lux-hud .lux-main-number"); if (!e) return null; const m = e.textContent.replace(/[\s  ]/g, "").match(/≈(\d+)lx/); return m ? Number(m[1]) : e.textContent; });
const stav = page => page.evaluate(() => window.__stulLux ? window.__stulLux._state() : null);
const modes = page => page.evaluate(() => { const g = document.querySelector(".stl-lux-modes"); return g ? { hidden: g.hidden || g.offsetParent === null, buttons: [...g.querySelectorAll("button")].map(b => [b.getAttribute("data-mode"), b.textContent, b.getAttribute("aria-pressed")]) } : null; });
function vypocet(o, mode) {                                       // NEZAVISLE: LuxCore + katalog LuxData nad payloadem ze serveru
  const input = { version: o.version, units: o.units, workplane: o.workplane, lights: o.lights.map(g => Object.assign({}, LuxData.selectLight(TYP_SKU[g.typ], mode), g, { dimmingFactor: 1 })) };
  return LuxCore.calculate(input, { allowEstimate: true });
}

async function otevri(browser, hash, viewport) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 1400, height: 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  await page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await nacten(page);
  await page.waitForTimeout(900);
  return { ctx, page, errs };
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## A) slot Delka LED svitidla, volba 600, odkaz, 3D menu");
    const A = await otevri(browser);
    let si = await slotInfo(A.page);
    t("A1 slot Delka LED svitidla je ve formulari: select 600 / 1200 mm, vychozi 1200", !!si && !si.hidden && si.value === "1200" && si.options.map(o => o.v).join() === "600,1200" && /Délka LED svítidla/.test(si.label || ""), si);
    t("A2 u vychoziho stolu (1280) jsou obe delky dostupne", !!si && si.options.every(o => !/nedostupné/.test(o.text)), si && si.options);
    const p0 = await payload(A.page);
    t("A3 vychozi odpoved: 1 svitidlo typu led_1200 a selection.ledlen 1200", p0.o && p0.o.lights.length === 1 && p0.o.lights[0].typ === "led_1200" && p0.sel.ledlen === "1200", p0.o && p0.o.lights.map(l => l.typ));
    await A.page.selectOption("[data-slot=ledlen] select", "600");
    await cekejDelku(A.page, "600");
    const p1 = await payload(A.page);
    const st1 = await A.page.evaluate(() => ({ hash: location.hash, valid: window.__pdcState.last.valid, errors: window.__pdcState.last.errors.length }));
    t("A4 po vyberu 600: 1 svitidlo typu led_600 (od 2026-10-08 je pocet svitidel RUCNI, vychozi 1), platna konfigurace, cena jina, delka v odkazu (#...ledlen=600)", p1.o.lights.length === 1 && p1.o.lights.every(l => l.typ === "led_600" && l.nominalLengthMm === 600 && l.housingLengthMm === 647) && st1.valid && st1.errors === 0 && p1.price !== p0.price && /ledlen=600/.test(st1.hash), { typ: p1.o.lights.map(l => l.typ), st1, price: [p0.price, p1.price] });
    if (SNIMKY) { require("fs").mkdirSync(SNIMKY, { recursive: true }); await A.page.screenshot({ path: SNIMKY + "/stranka_led600.png" }); }
    const menu = await A.page.evaluate(() => { const w = window.__pdcState.last.vodici && window.__pdcState.last.vodici.ovladani; return w ? w.casti.filter(c => c.id === "led").map(c => c.menu.map(m => m.text)) : null; });
    t("A5 3D menu svitidla nabizi 'Zvolit LED 1200 mm' (a ne 600, ktera je vybrana)", !!menu && menu[0].includes("Zvolit LED 1200 mm") && !menu[0].includes("Zvolit LED 600 mm"), menu);
    t("A6 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));

    console.log("\n## B) pocitadlo luxu s LED 600: cifry, stupne podle typu svitidla");
    await A.page.click(".stl-lux-btn");
    await A.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 60000 });
    await A.page.waitForTimeout(900);
    let s = await stav(A.page), m = await modes(A.page);
    const ref6 = vypocet(p1.o, "16W");
    t("B1 zapnuto s LED 600: stav bezi, stupen 16W (jediny stupen typu), skupina tlacitek stupnu je schovana (jediny stupen)", s.enabled && s.running && s.mode === "16W" && m && m.hidden, { s, m });
    t("B2 cifra v HUD = nezavisly vypocet LuxCore pro LED 600 (16 W, " + Math.round(ref6.meanLux) + " lx)", (await hudMean(A.page)) === Math.round(ref6.meanLux), [await hudMean(A.page), ref6.meanLux]);
    await A.page.selectOption("[data-slot=ledlen] select", "1200");
    await cekejDelku(A.page, "1200");
    await A.page.waitForFunction(() => { const x = window.__stulLux._state(); return x.running && !x.stale && x.shownHash === window.__pdcState.last.hash; }, null, { timeout: 60000, polling: 200 });
    const p2 = await payload(A.page);
    s = await stav(A.page); m = await modes(A.page);
    t("B3 zpet na 1200: tlacitka stupnu se postavila znovu (33 W stisknute, 21 W), stupen 33W", s.running && s.mode === "33W" && m && !m.hidden && JSON.stringify(m.buttons) === JSON.stringify([["33W", "33 W", "true"], ["21W", "21 W", "false"]]), { s, m });
    const ref12 = vypocet(p2.o, "33W");
    t("B4 cifra = nezavisly vypocet pro LED 1200 (33 W, " + Math.round(ref12.meanLux) + " lx)", (await hudMean(A.page)) === Math.round(ref12.meanLux), [await hudMean(A.page), ref12.meanLux]);
    await A.page.click('.stl-lux-modes button[data-mode="21W"]');
    await A.page.waitForTimeout(500);
    t("B5 stupen 21 W u LED 1200: cifra = nezavisly vypocet", (await hudMean(A.page)) === Math.round(vypocet(p2.o, "21W").meanLux), [await hudMean(A.page)]);
    await A.page.selectOption("[data-slot=ledlen] select", "600");
    await cekejDelku(A.page, "600");
    await A.page.waitForFunction(() => { const x = window.__stulLux._state(); return x.running && !x.stale && x.shownHash === window.__pdcState.last.hash; }, null, { timeout: 60000, polling: 200 });
    s = await stav(A.page); m = await modes(A.page);
    const p3 = await payload(A.page);
    t("B6 z 21 W na LED 600: stupen se vratil na vychozi 16W (typ 21 W nema), pocitadlo bezi, cifra = nezavisly vypocet", s.running && s.mode === "16W" && m.hidden && (await hudMean(A.page)) === Math.round(vypocet(p3.o, "16W").meanLux), { s, m, hud: await hudMean(A.page) });
    await A.page.selectOption("[data-slot=ledlen] select", "1200");
    await cekejDelku(A.page, "1200");
    await A.page.waitForFunction(() => { const x = window.__stulLux._state(); return x.running && !x.stale && x.shownHash === window.__pdcState.last.hash; }, null, { timeout: 60000, polling: 200 });
    s = await stav(A.page); m = await modes(A.page);
    t("B7 a zase zpet na 1200: stupen 33W (16 W 1200 nema), tlacitka 33 W / 21 W, bez chyb", s.running && s.mode === "33W" && !m.hidden && m.buttons.length === 2 && A.errs.length === 0, { s, m, errs: A.errs.slice(0, 3) });
    await A.ctx.close();

    console.log("\n## C) uzky stul: delka, ktera se nevejde, a nabidka kratsiho svitidla");
    const C = await otevri(browser, "#w=900&ledlen=600");
    si = await slotInfo(C.page);
    const pc = await payload(C.page);
    t("C1 odkaz #w=900&ledlen=600: svitidlo 600 je na stole (1 ks), select ukazuje 600 a 1200 je nedostupna", pc.o && pc.o.lights.length === 1 && pc.o.lights[0].typ === "led_600" && si.value === "600" && si.options.filter(o => /nedostupné/.test(o.text)).map(o => o.v).join() === "1200", { n: pc.o && pc.o.lights.length, si });
    await C.page.evaluate(() => { const cb = document.querySelector('[data-slot="led"] input[type="checkbox"]'); if (cb && cb.checked) cb.click(); });
    await C.page.waitForFunction(() => window.__pdcState.last && window.__pdcState.last.selection && window.__pdcState.last.selection.led === false, null, { timeout: 120000, polling: 200 });
    await C.page.waitForTimeout(900);
    const sug = await C.page.evaluate(() => { const b = document.querySelector('[data-slot="led"] .pdc-suggest-btn'); return b && !b.closest(".pdc-suggest").hidden ? b.textContent.trim() : null; });
    t("C2 LED vypnuta na 900 mm: u prepinace je nabidka 'Zapnout kratsi LED 600 mm'", sug === "Zapnout kratší LED 600 mm", sug);
    await C.page.click('[data-slot="led"] .pdc-suggest-btn');
    await C.page.waitForFunction(() => window.__pdcState.last && window.__pdcState.last.selection && window.__pdcState.last.selection.led === true && window.__pdcState.last.selection.ledlen === "600", null, { timeout: 120000, polling: 200 });
    await nacten(C.page);
    const pc2 = await payload(C.page);
    t("C3 po kliknuti na nabidku je LED zapnuta a je to svitidlo 600 (1 ks), platna konfigurace", pc2.o && pc2.o.lights.length === 1 && pc2.o.lights[0].typ === "led_600" && (await C.page.evaluate(() => window.__pdcState.last.valid)), pc2.o && pc2.o.lights.map(l => l.typ));
    t("C4 bez chyb JS", C.errs.length === 0, C.errs.slice(0, 3));
    await C.ctx.close();

    console.log("\n## D) siroky stul a mobil");
    const D = await otevri(browser, "#w=2000&ledlen=600&ledcount=3");
    const pd = await payload(D.page);
    t("D1 odkaz #w=2000&ledlen=600&ledcount=3: 3 svitidla 600", pd.o && pd.o.lights.length === 3 && pd.o.lights.every(l => l.typ === "led_600") && pd.sel.ledlen === "600", pd.o && pd.o.lights.length);
    await D.ctx.close();
    const M = await otevri(browser, "#w=2000", { width: 360, height: 800 });
    const mob = await slotInfo(M.page);
    const pretece = await M.page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    t("D2 na uzkem okne (360 px) je slot Delka LED svitidla ve formulari (skupina Prislusenstvi je na mobilu sbalena) a stranka se neposouva do strany", !!mob && mob.options.length === 2 && !pretece, { mob, pretece });
    await M.page.click(".stl-lux-btn");
    await M.page.waitForSelector(".lux-hud .lux-main-number", { timeout: 60000 });
    await M.page.selectOption("[data-slot=ledlen] select", "600").catch(() => {});
    t("D3 bez chyb JS (mobil)", M.errs.length === 0, M.errs.slice(0, 3));
    await M.ctx.close();
  } finally {
    await browser.close();
  }
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e.message); process.exit(2); });
