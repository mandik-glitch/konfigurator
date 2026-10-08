// Test KOT ve 3D nahledu na strankach Generator stolu 01 / 02 / 03 (bot8, 2026-10-05; Robert: "doplnit do generatoru ve 3D nahledu ... koty v dratenem pohledu").
// SKUTECNA stranka + SKUTECNY modul voleb + SKUTECNY viewer nad SKUTECNYM kodem stolu (api/stul_shop.py, api/stul_koty.py) pres most _most_stul.py (prihlaseny admin).
// Spusteni (DB pres systemd-run; PID40 / PID35 = fiktivni karty systemu 40 / 35 pro stranky 02 a 03, bez nich se zkousi jen stranka 01):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_koty_stranka.js 4934
// Casti: K stranka 01 (prepinac Koty, kóty v obou vzhledech, volba preziva zmenu modelu, hash s vice policemi a panely) | S stranky 02 / 03 (tentyz prepinac, ciselne hodnoty systemu)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };

async function otevri(browser, stranka, hash) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto(`${BASE}/${stranka}?debug=1${hash || ""}`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading && document.querySelectorAll(".v3d-dim").length > 0; }, null, { polling: 300, timeout: 90000 });
  await page.waitForTimeout(800);
  return { ctx, page, errs };
}
const popisky = page => page.evaluate(() => [...document.querySelectorAll(".v3d-dim")].filter(e => getComputedStyle(e).display !== "none" && e.offsetParent !== null).map(e => e.textContent.trim()));
const stav = page => page.evaluate(() => { const s = window.__pdcState.viewer.state(); return { mode: s.mode, dims: s.dims, hudKoty: s.hudKoty }; });
const cisla = a => a.map(x => Number(x.replace(/[^\d]/g, "")));
const ocekavane = (a, b) => JSON.stringify(a.slice().sort((x, y) => x - y)) === JSON.stringify(b.slice().sort((x, y) => x - y));

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## K stranka 01 (system 30)");
    const A = await otevri(browser, "stul-konfigurator.html");
    let st = await stav(A.page);
    t("K1 prepinac Koty je v HUD a koty jsou po nacteni zapnute (uroven Rozmery)", st.hudKoty === true && st.dims === 1, st);
    const seg = await A.page.evaluate(() => { const b = [...document.querySelectorAll('.v3d-hud button[data-grp="dims"]')]; return b.map(x => ({ v: x.dataset.v, text: x.textContent.trim(), hidden: x.hidden || x.offsetParent === null })); });
    t("K2 prepinac ma Vyp a Rozmery, Detail se nenabizi (vsechny koty jsou v urovni Rozmery)", seg.length === 3 && seg.find(b => b.v === "0" && !b.hidden) && seg.find(b => b.v === "1" && !b.hidden) && seg.find(b => b.v === "2").hidden, seg);
    let lab = await popisky(A.page);
    t("K3 vychozi stul: 9 kot s ocekavanymi cisly (840, 1 925, 1 280, 800, 792, 363, 428 a dvakrat 15)", ocekavane(cisla(lab), [840, 1925, 1280, 800, 792, 363, 428, 15, 15]), lab);
    t("K3b kazdy popisek konci na mm", lab.every(x => /\d mm$/.test(x)), lab);
    // Vyp / Rozmery
    await A.page.click('.v3d-hud button[data-grp="dims"][data-v="0"]'); await A.page.waitForTimeout(500);
    lab = await popisky(A.page); st = await stav(A.page);
    t("K4 Vyp: zadna kota neni videt", st.dims === 0 && lab.length === 0, { st, lab });
    await A.page.click('.v3d-hud button[data-grp="dims"][data-v="1"]'); await A.page.waitForTimeout(500);
    lab = await popisky(A.page);
    t("K5 Rozmery: koty zase jsou", lab.length === 9, lab);
    // draty vzhled
    await A.page.click('.v3d-hud button[data-grp="mode"][data-v="wire"]'); await A.page.waitForTimeout(900);
    st = await stav(A.page); lab = await popisky(A.page);
    t("K6 DRATENY vzhled: koty zustavaji (9 popisku, uroven Rozmery)", st.mode === "wire" && st.dims === 1 && lab.length === 9, { st, lab });
    const pixely = await A.page.evaluate(() => { const c = document.querySelector("#stage canvas"); const g = c.getContext("webgl2") || c.getContext("webgl"); return !!g; });
    t("K6b platno ma WebGL (kresleni probehlo)", pixely);
    // zmena rozmeru -> novy model -> koty se prepocitaji, volba Vzhled i Koty preziva
    await A.page.fill('[data-slot=w] .pdc-num', '1400'); await A.page.keyboard.press("Enter");
    await A.page.waitForFunction(() => [...document.querySelectorAll(".v3d-dim")].some(e => /1 ?400 mm/.test(e.textContent)), null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(1200);
    lab = await popisky(A.page); st = await stav(A.page);
    t("K7 po zmene sirky na 1400: delka desky 1 400, mezery panelu (1400-60-1190)/2 = 75, jine koty zustaly", ocekavane(cisla(lab), [840, 1925, 1400, 800, 792, 363, 428, 75, 75]), lab);
    t("K7b volba Drateny a Rozmery prezila vymenu modelu", st.mode === "wire" && st.dims === 1, st);
    await A.page.click('.v3d-hud button[data-grp="mode"][data-v="real"]'); await A.page.waitForTimeout(600);
    lab = await popisky(A.page);
    t("K8 vzhled Skutecny: tytez koty", lab.length === 9, lab);
    // pohledy: celni pohled skryje hloubku (osa kóty miri do kamery), boční pohled sirku
    await A.page.click('.v3d-hud button[data-v="front"]'); await A.page.waitForTimeout(900);
    const lf = await popisky(A.page);
    await A.page.click('.v3d-hud button[data-v="side"]'); await A.page.waitForTimeout(900);
    const ls = await popisky(A.page);
    t("K9 pohledy: zepredu neni videt hloubka (800), z boku neni videt delka (1 400)", !cisla(lf).includes(800) && cisla(lf).includes(1400) && !cisla(ls).includes(1400) && cisla(ls).includes(800), { lf, ls });
    t("K10 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));
    await A.ctx.close();

    console.log("\n## D tazeni ve 3D: koty se behem tazeni vypnou (ukazovaly by puvodni cisla) a vraceji se s presnym modelem");
    const D = await otevri(browser, "stul-konfigurator.html");
    await D.page.waitForFunction(() => { const S = window.__pdcState; return S && S.ov && Object.keys(S.ov.debug().handles).length > 0; }, null, { polling: 200, timeout: 60000 });
    const hc = async id => { const b = await D.page.locator("#v3do_" + id).boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2 }; };
    const sirkaPred = await D.page.evaluate(() => window.__pdcState.sel.w);
    let c = await hc("w");
    await D.page.mouse.move(c.x, c.y); await D.page.mouse.down();
    for (let i = 1; i <= 10; i++) await D.page.mouse.move(c.x + 9 * i, c.y);
    await D.page.waitForTimeout(700);
    st = await stav(D.page); lab = await popisky(D.page);
    t("D1 behem tazeni uchytu Sirka jsou koty vypnute (zadny popisek, uroven 0)", st.dims === 0 && lab.length === 0, { st, lab });
    await D.page.mouse.up();
    await D.page.waitForFunction(() => window.__pdcState.viewer.state().dims === 1 && document.querySelectorAll(".v3d-dim").length > 0, null, { timeout: 60000 }).catch(() => {});
    await D.page.waitForTimeout(900);
    st = await stav(D.page); lab = await popisky(D.page);
    const sirkaPo = await D.page.evaluate(() => window.__pdcState.sel.w);
    t("D2 po pusteni a prichodu presneho modelu jsou koty zpet a ukazuji NOVOU sirku (" + sirkaPred + " -> " + sirkaPo + ")", st.dims === 1 && sirkaPo !== sirkaPred && cisla(lab).includes(Number(sirkaPo)), { st, lab, sirkaPred, sirkaPo });
    // Esc: tazeni se zrusi, hodnota se vrati, koty se vrati
    c = await hc("w");
    await D.page.mouse.move(c.x, c.y); await D.page.mouse.down();
    for (let i = 1; i <= 8; i++) await D.page.mouse.move(c.x - 9 * i, c.y);
    await D.page.waitForTimeout(500);
    st = await stav(D.page);
    t("D3 pri dalsim tazeni jsou koty zase vypnute", st.dims === 0, st);
    await D.page.keyboard.press("Escape");
    await D.page.mouse.up();
    await D.page.waitForFunction(() => window.__pdcState.viewer.state().dims === 1, null, { timeout: 30000 }).catch(() => {});
    await D.page.waitForTimeout(700);
    st = await stav(D.page); lab = await popisky(D.page);
    t("D4 po Esc se hodnota vrati a koty jsou zase videt (uroven 1, popisky " + lab.length + ")", st.dims === 1 && lab.length === 9 && cisla(lab).includes(Number(sirkaPo)), { st, lab });
    // uzivatel mel koty vypnute: tazeni je NEZAPNE
    await D.page.click('.v3d-hud button[data-grp="dims"][data-v="0"]'); await D.page.waitForTimeout(300);
    c = await hc("w");
    await D.page.mouse.move(c.x, c.y); await D.page.mouse.down();
    for (let i = 1; i <= 8; i++) await D.page.mouse.move(c.x + 9 * i, c.y);
    await D.page.waitForTimeout(500); await D.page.mouse.up();
    await D.page.waitForTimeout(4000);
    st = await stav(D.page); lab = await popisky(D.page);
    t("D5 kdyz mel uzivatel koty vypnute (Vyp), tazeni je nezapne", st.dims === 0 && lab.length === 0, { st, lab });
    t("D6 bez chyb JS", D.errs.length === 0, D.errs.slice(0, 3));
    await D.ctx.close();

    console.log("\n## K2 odkaz s vice policemi a panely: #w=2600&d=700&h=1100&shelf=3&drawers=0&panelcount=2");
    const B = await otevri(browser, "stul-konfigurator.html", "#w=2600&d=700&h=1100&shelf=3&drawers=0&panelcount=2");
    lab = await popisky(B.page);
    t("KB1 siroky stul: vysky police 363 / 657 / 952, vnitrni 1 052, mezery 246 / 246 / 100, panely 33 x 4, deska 2 600 x 700, deska 1 100, celek 2 185",
      ocekavane(cisla(lab), [1100, 2185, 2600, 700, 1052, 363, 657, 952, 246, 246, 100, 33, 33, 33, 33]), lab);
    t("KB2 bez chyb JS", B.errs.length === 0, B.errs.slice(0, 3));
    // tlacitko Zpet / mala zmena: kóty drží krok s modelem (stejny pocet po zmene vysky o 100 mm)
    await B.page.fill('[data-slot=h] .pdc-num', '1200'); await B.page.keyboard.press("Enter");
    await B.page.waitForFunction(() => [...document.querySelectorAll(".v3d-dim")].some(e => /1 ?200 mm/.test(e.textContent)), null, { timeout: 60000 }).catch(() => {});
    await B.page.waitForTimeout(1000);
    lab = await popisky(B.page);
    t("KB3 po zmene vysky na 1200 jsou koty nove (deska 1 200, celek 2 285)", cisla(lab).includes(1200) && cisla(lab).includes(2285) && !cisla(lab).includes(1100), lab);
    await B.ctx.close();

    console.log("\n## M mobil (390 px): maly nahled - prepinac Koty je, koty jsou po nacteni vypnute a jdou zapnout");
    {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: "cs-CZ", hasTouch: true, isMobile: true });
      const page = await ctx.newPage(); const errs = [];
      page.on("pageerror", e => errs.push(e.message));
      await page.goto(`${BASE}/stul-konfigurator.html?debug=1`, { waitUntil: "load" });
      await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
      await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { polling: 300, timeout: 90000 });
      await page.waitForTimeout(1500);
      let sm = await stav(page), lm = await popisky(page);
      t("M1 mobil: prepinac Koty v HUD je, koty po nacteni vypnute (dims 0, zadne popisky)", sm.hudKoty === true && sm.dims === 0 && lm.length === 0, { sm, lm });
      const tl = await page.evaluate(() => [...document.querySelectorAll('.v3d-hud button[data-grp="dims"]')].some(b => b.offsetParent !== null));
      t("M2 tlacitko Kóty je v HUD videt", tl);
      await page.evaluate(() => window.__pdcState.viewer.setDims(1)); await page.waitForTimeout(900);
      lm = await popisky(page);
      t("M3 po zapnuti se koty zobrazi (9 popisku)", lm.length === 9, lm);
      t("M4 bez chyb JS", errs.length === 0, errs.slice(0, 3));
      await ctx.close();
    }

    const DALSI = [["stul-konfigurator-40.html", 40, process.env.PID40, [840, 1935, 1280, 790, 782, 363, 418, 5, 5]], ["stul-konfigurator-35.html", 35, process.env.PID35, [840, 1930, 1280, 795, 787, 363, 423, 10, 10]]];
    for (const [stranka, sys, pid, cekano] of DALSI) {
      console.log(`\n## S stranka systemu ${sys}`);
      if (!pid) { console.log(`   (preskoceno: chybi PID${sys})`); continue; }
      const C = await otevri(browser, stranka);
      const s2 = await stav(C.page); lab = await popisky(C.page);
      t(`S${sys}a prepinac Koty a koty zapnute`, s2.hudKoty === true && s2.dims === 1, s2);
      t(`S${sys}b vychozi stul systemu ${sys}: ${cekano.join(", ")}`, ocekavane(cisla(lab), cekano), lab);
      t(`S${sys}c bez chyb JS`, C.errs.length === 0, C.errs.slice(0, 3));
      await C.ctx.close();
    }
  } catch (e) { t("test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 600)); }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
