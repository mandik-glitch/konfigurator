// Test VYCHOZIHO UHLU POHLEDU 3D v generatorech (viewer3d.js 1.17.0 + js/product-configurator.js + js/stul-host.js; bot10, 2026-10-08; Robert: "chci nastavit vychozi uhel pohledu 3D v generatorech").
// SKUTECNY viewer + skutecna stranka Generator stolu + skutecny modul voleb nad skutecnym kodem stolu pres most scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, fiktivni karty, nic se
// nezapisuje); ulozeny pohled (`view` ve schematu) a PUT / DELETE /api/shop/configurator/view se v testu SIMULUJI (page.route) - skutecny backend testuje test_pohled_api.py nad docasnymi tabulkami.
// Spusteni (DB pres systemd-run; kandidat = koren s upravenym api + webapp):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID45=9880 --setenv=PRAVIDLA_TEST={} --setenv=WEB_DIR=<koren>/webapp \
//     --working-directory=<koren> api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py /opt/konfigurator/scripts/2026-10-08_vychozi_pohled/test_pohled_stranka.js 4934
// Casti: A viewer (API: version, normalizeIsoAngles, isoAngles, currentAngles, setIsoAngles, pohledy) | B modul pouzije schema.view pri mountu | C okno Vychozi konfigurace (blok Vychozi pohled 3D: sonda, ulozeni,
//        vraceni, chyby, zive hodnoty) | D staticke kontroly (verze, piny ?v=). ONLY=A,C ; snimky: SHOT=/cesta/predpona.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const crypto = require("crypto");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
const PID40 = process.env.PID40, PID45 = process.env.PID45;
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp";
let bad = 0, total = 0;
// dvoukrokova tlacitka (potvrzeni do 6 s) se v testu mackaji PO SOBE: `force` preskoci cekani na ustalenou animaci (pod zatizenim VPS s SwiftShader trva jeden snimek sekundy a druhy klik by prisel po uplynuti 6 s)
const klik = (page, sel) => page.click(sel, { force: true });
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
async function sec(name, fn) { if (process.env.ONLY && !process.env.ONLY.split(",").includes(name[0])) return; console.log("\n## " + name); try { await fn(); } catch (e) { t(name + ": test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 700)); } }
const blizko = (a, b, tol) => Math.abs(a - b) <= (tol == null ? 0.6 : tol);
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;

// mk(browser, {view: <hodnota pole view ve schematu | undefined = beze zmeny | "CHYBI" = klic odstranit>, put: fn(body)->{status, body}, del: fn()->{status, body}})
async function mk(browser, o) {
  o = o || {};
  const ctx = await browser.newContext({ viewport: { width: o.w || 1400, height: o.h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  const mock = { calls: [], put: o.put || (b => ({ status: 200, body: { view: b } })), del: o.del || (() => ({ status: 200, body: { view: null } })), view: o.view, delay: 0, abort: false };
  await page.route(/\/api\/shop\/products\/\d+\/configurator\?lang=/, async route => {                  // schema: skutecne + pole view podle testu
    const r = await route.fetch(); const j = await r.json();
    if (mock.view === "CHYBI") delete j.view; else if (mock.view !== undefined) j.view = mock.view;
    return route.fulfill({ response: r, json: j });
  });
  await page.route("**/api/shop/configurator/view", async route => {
    const req = route.request(); let body = null; try { body = JSON.parse(req.postData() || "null"); } catch (e) { /* nic */ }
    mock.calls.push({ method: req.method(), body, ctype: req.headers()["content-type"] || "" });
    if (mock.delay) await new Promise(r => setTimeout(r, mock.delay));
    if (mock.abort) return route.abort("failed");
    const x = req.method() === "PUT" ? mock.put(body) : mock.del();
    return route.fulfill({ status: x.status, contentType: x.raw != null ? "text/html" : "application/json", body: x.raw != null ? x.raw : JSON.stringify(x.body) });
  });
  return { ctx, page, trk, errs, mock };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, strana) {
  await p.page.goto(`${BASE}${strana}?debug=1`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash && !S.pending && S.viewer && S.viewer.state().ready; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
  await p.page.waitForFunction(() => !window.__pdcState.viewer.state().flying, null, { polling: 100, timeout: 20000 });
}
const uhly = page => page.evaluate(() => window.__pdcState.viewer.currentAngles());
const iso = page => page.evaluate(() => window.__pdcState.viewer.state().isoAngles);
const konec = page => page.waitForFunction(() => !window.__pdcState.viewer.state().flying, null, { polling: 80, timeout: 10000 });
async function letet(p, a, fly) { const ok = await p.page.evaluate(([a_, f_]) => window.__pdcState.viewer.setIsoAngles(a_, f_), [a, fly]); await p.page.waitForTimeout(150); await konec(p.page); return ok; }

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const STR = { 40: "/stul-konfigurator-40.html", 45: "/stul-konfigurator-45.html" };

  await sec("A viewer 1.17.0: isoAngles, currentAngles, setIsoAngles, pohledy", async () => {
    const p = await mk(browser, { view: "CHYBI" }); await load(p, STR[40]);
    const v = await p.page.evaluate(() => ({ ver: V3D.version, n: [V3D.normalizeIsoAngles({ az: 190, el: 10 }), V3D.normalizeIsoAngles({ az: -180, el: 0 }), V3D.normalizeIsoAngles({ az: 35.04, el: 24.96 }), V3D.normalizeIsoAngles({ az: 0, el: -15 }), V3D.normalizeIsoAngles({ az: 0, el: 85 })] }));
    t("A1 verze 1.17.0 a V3D.normalizeIsoAngles: 190 -> -170, -180 -> 180, zaokrouhleni 0,1, krajni meze -15 / 85 platne", v.ver === "1.17.0" && JSON.stringify(v.n) === JSON.stringify([{ az: -170, el: 10 }, { az: 180, el: 0 }, { az: 35, el: 25 }, { az: 0, el: -15 }, { az: 0, el: 85 }]), v);
    const bad = await p.page.evaluate(() => [null, undefined, "x", 5, [], {}, { az: 1 }, { el: 1 }, { az: "1", el: 2 }, { az: NaN, el: 1 }, { az: 1, el: Infinity }, { az: true, el: 1 }, { az: 0, el: -15.1 }, { az: 0, el: 85.1 }].map(x => V3D.normalizeIsoAngles(x)));
    t("A2 normalizeIsoAngles: spatny tvar / mimo meze = null (nic se potichu neorezava)", bad.every(x => x === null), bad);
    t("A3 bez volby: state().isoAngles = puvodnich 35 / 25 a po nacteni je kamera presne na 3D pohledu (currentAngles 35 / 25)", JSON.stringify(await iso(p.page)) === JSON.stringify({ az: 35, el: 25 }) && blizko((await uhly(p.page)).az, 35) && blizko((await uhly(p.page)).el, 25), [await iso(p.page), await uhly(p.page)]);
    t("A4 setIsoAngles({az: -50, el: 15}, true) = true, kamera preleti na novy pohled (currentAngles -50 / 15) a state().isoAngles se zmeni", await letet(p, { az: -50, el: 15 }, true) === true && blizko((await uhly(p.page)).az, -50) && blizko((await uhly(p.page)).el, 15) && JSON.stringify(await iso(p.page)) === JSON.stringify({ az: -50, el: 15 }), [await iso(p.page), await uhly(p.page)]);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("front")); await konec(p.page); await p.page.waitForTimeout(150);
    const f = await uhly(p.page);
    t("A5 pohled Predni: currentAngles = otoceni 0, naklon 0 (kamera primo proti celu modelu)", blizko(f.az, 0, 0.3) && blizko(f.el, 0, 0.3), f);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("side")); await konec(p.page); await p.page.waitForTimeout(150);
    const sd = await uhly(p.page);
    t("A6 pohled Bok: otoceni +-90, naklon 0", blizko(Math.abs(sd.az), 90, 0.3) && blizko(sd.el, 0, 0.3), sd);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("top")); await konec(p.page); await p.page.waitForTimeout(150);
    const tp = await uhly(p.page);
    t("A7 pohled Shora: naklon 90 (prave nad modelem)", blizko(tp.el, 90, 0.3), tp);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("iso")); await konec(p.page); await p.page.waitForTimeout(150);
    t("A8 pohled 3D (iso) se vraci na NOVY uhel -50 / 15, ne na puvodni", blizko((await uhly(p.page)).az, -50) && blizko((await uhly(p.page)).el, 15), await uhly(p.page));
    await p.page.evaluate(() => window.__pdcState.viewer.setView("reset")); await konec(p.page); await p.page.waitForTimeout(150);
    t("A9 setView('reset') = takyz novy uhel", blizko((await uhly(p.page)).az, -50) && blizko((await uhly(p.page)).el, 15));
    const nep = await p.page.evaluate(() => [window.__pdcState.viewer.setIsoAngles({ az: 10, el: 99 }, true), window.__pdcState.viewer.setIsoAngles("x"), window.__pdcState.viewer.setIsoAngles({ az: 1 }, true)]);
    t("A10 neplatny uhel: setIsoAngles vraci false a nic se nezmeni (isoAngles zustava -50 / 15)", nep.every(x => x === false) && JSON.stringify(await iso(p.page)) === JSON.stringify({ az: -50, el: 15 }), nep);
    t("A11 setIsoAngles(null, true) = puvodnich 35 / 25 a kamera tam preleti", await letet(p, null, true) === true && blizko((await uhly(p.page)).az, 35) && blizko((await uhly(p.page)).el, 25) && JSON.stringify(await iso(p.page)) === JSON.stringify({ az: 35, el: 25 }), [await iso(p.page), await uhly(p.page)]);
    await letet(p, { az: 120, el: 40 }, false);
    t("A12 setIsoAngles(a, false) uhel jen ulozi (kamera zustava), dalsi pohled 3D pouzije novy", blizko((await uhly(p.page)).az, 35) && JSON.stringify(await iso(p.page)) === JSON.stringify({ az: 120, el: 40 }), [await iso(p.page), await uhly(p.page)]);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("iso")); await konec(p.page); await p.page.waitForTimeout(150);
    t("A13 po setView('iso') je kamera na 120 / 40 (zaber celeho modelu zachovan: model je cely videt)", blizko((await uhly(p.page)).az, 120) && blizko((await uhly(p.page)).el, 40), await uhly(p.page));
    // rucni otoceni mysi: currentAngles se meni
    const c = await p.page.evaluate(() => { const r = document.querySelector("#stage canvas").getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
    const pred = await uhly(p.page);
    await p.page.mouse.move(c.x, c.y); await p.page.mouse.down(); await p.page.mouse.move(c.x + 120, c.y - 40, { steps: 8 }); await p.page.mouse.up(); await p.page.waitForTimeout(400);
    const po = await uhly(p.page);
    t("A14 otoceni modelu mysi zmeni currentAngles (otoceni i naklon) - to, co admin ulozi", Math.abs(po.az - pred.az) > 5 && Math.abs(po.el - pred.el) > 1, { pred, po });
    t("A15 bez chyb ve strance ani v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  await sec("B modul pouzije schema.view pri mountu", async () => {
    for (const [popis, view, az, el] of [["ulozeny pohled {-60, 10}", { az: -60, el: 10 }, -60, 10], ["ulozeny pohled {150, 45}", { az: 150, el: 45 }, 150, 45], ["view null = puvodni", null, 35, 25], ["klic view chybi (starsi backend) = puvodni", "CHYBI", 35, 25],
                                          ["neplatny view ve schematu {az: 'x'} = puvodni (viewer ho zahodi)", { az: "x", el: 10 }, 35, 25], ["view mimo meze {el: 120} = puvodni", { az: 10, el: 120 }, 35, 25]]) {
      const p = await mk(browser, { view }); await load(p, STR[40]);
      const u = await uhly(p.page), i = await iso(p.page);
      t(`B ${popis}: prvni zaber je na ${az} / ${el} (kamera i state().isoAngles)`, blizko(u.az, az) && blizko(u.el, el) && blizko(i.az, az) && blizko(i.el, el), { u, i });
      if (view && view !== "CHYBI" && az === -60) {
        await p.page.evaluate(() => window.__pdcState.viewer.setView("front")); await konec(p.page);
        await p.page.evaluate(() => window.__pdcState.viewer.setView("iso")); await konec(p.page); await p.page.waitForTimeout(150);
        t("B tlacitko 3D (setView iso) se vraci na ulozeny pohled -60 / 10", blizko((await uhly(p.page)).az, -60) && blizko((await uhly(p.page)).el, 10), await uhly(p.page));
        // zmena rozmeru nesmi vratit uzivatelovu kameru (pohled se nastavuje jen pri prvnim zaberu)
        await p.page.evaluate(() => window.__pdcState.viewer.setIsoAngles({ az: 5, el: 5 }, true)); await konec(p.page);
        const w = await p.page.evaluate(() => { const r = document.querySelector('[data-slot="w"] input.pdc-range'); r.value = String(Number(r.value) + 100); r.dispatchEvent(new Event("input", { bubbles: true })); r.dispatchEvent(new Event("change", { bubbles: true })); return r.value; });
        await idle(p, 1500); await konec(p.page);
        t("B po zmene sirky stolu (model se vymeni) zustava kamera tam, kde ji uzivatel nechal (5 / 5), ne zpet na ulozeny pohled", blizko((await uhly(p.page)).az, 5, 1.5) && blizko((await uhly(p.page)).el, 5, 1.5), { w, u: await uhly(p.page) });
      }
      t(`B ${popis}: bez chyb ve strance ani v konzoli`, p.errs.length === 0, p.errs.slice(0, 3));
      await p.ctx.close();
    }
    const p45 = await mk(browser, { view: { az: -20, el: 30 } }); await load(p45, STR[45]);
    t("B generator 45 (Robustni): stejne nastaveni -20 / 30 (jedno pro vsechny generatory)", blizko((await uhly(p45.page)).az, -20) && blizko((await uhly(p45.page)).el, 30), await uhly(p45.page));
    await p45.ctx.close();
  });

  await sec("C okno Vychozi konfigurace: blok Vychozi pohled 3D", async () => {
    const stav = page => page.evaluate(() => { const b = document.getElementById("pohledBlok"); return b ? { hidden: b.hidden, visible: b.offsetParent !== null, status: document.getElementById("pohledStatus").textContent, aktualni: document.getElementById("pohledAktualni").textContent,
      save: document.getElementById("pohledSave").textContent, reset: { hidden: document.getElementById("pohledReset").hidden, text: document.getElementById("pohledReset").textContent }, okno: !document.querySelector(".mw-win-defcfg").hidden } : null; });
    // C1: starsi backend (bez klice view): blok skryty, okno Vychozi konfigurace funguje dal
    let p = await mk(browser, { view: "CHYBI" }); await load(p, STR[40]);
    await p.page.waitForFunction(() => { const w = document.querySelector(".mw-win-defcfg"); return w && !w.hidden; }, null, { timeout: 30000 });
    let s = await stav(p.page);
    t("C1 starsi backend (schema bez klice view): blok pohledu je skryty, okno Vychozi konfigurace zustava", s && s.hidden && !s.visible && s.okno, s);
    await p.ctx.close();
    // C2: view null: blok viditelny, puvodni pohled, zive hodnoty
    p = await mk(browser, { view: null }); await load(p, STR[40]);
    await p.page.waitForSelector("#pohledBlok:not([hidden])", { timeout: 30000 });
    s = await stav(p.page);
    t("C2 view null: blok je videt, 'Platí původní výchozí pohled (otočení 35°, náklon 25°).', tlacitko Vratit je skryte, tlacitko 'Uložit aktuální pohled jako výchozí'", s.visible && /Platí původní výchozí pohled \(otočení 35°, náklon 25°\)\./.test(s.status) && s.reset.hidden && s.save === "Uložit aktuální pohled jako výchozí", s);
    t("C2b aktualni uhel kamery je videt a odpovida kamere ('Aktuální pohled: otočení 35°, náklon 25°')", /Aktuální pohled: otočení 3[45](?:\.\d)?°, náklon 2[45](?:\.\d)?°/.test(s.aktualni), s.aktualni);
    await letet(p, { az: 20, el: 30 }, true); await p.page.waitForTimeout(300);
    s = await stav(p.page);
    t("C2c po preletu kamery se aktualni uhel prepise (otočení 20°, náklon 30°)", /otočení 20(?:\.\d)?°, náklon 30(?:\.\d)?°/.test(s.aktualni), s.aktualni);
    if (SHOT) await p.page.locator("#pohledBlok").screenshot({ path: SHOT + "_blok.png" });
    // C3: ulozeni (dvoukrokove)
    p.mock.put = body => ({ status: 200, body: { view: body } });
    await klik(p.page, "#pohledSave");
    t("C3 prvni klik jen zmeni popisek ('Opravdu uložit pro všechny?') a NIC neposle", (await p.page.textContent("#pohledSave")) === "Opravdu uložit pro všechny?" && p.mock.calls.length === 0, p.mock.calls.length);
    await klik(p.page, "#pohledSave"); await p.page.waitForFunction(() => /Uloženo/.test(document.getElementById("pohledStatus").textContent), null, { timeout: 15000 });
    const put = p.mock.calls[0];
    t("C3b druhy klik: PUT /api/shop/configurator/view s presne aktualnim uhlem kamery {az, el} (nic jineho), JSON", put && put.method === "PUT" && put.ctype.indexOf("application/json") === 0 && Object.keys(put.body).sort().join() === "az,el" && blizko(put.body.az, 20) && blizko(put.body.el, 30), put);
    s = await stav(p.page);
    t("C3c po ulozeni: 'Výchozí pohled je uložený', tlacitko Vratit se objevi, popisek ulozit je puvodni", /Uloženo – generátory se teď otevírají s pohledem: otočení 20(?:\.\d)?°, náklon 30(?:\.\d)?°/.test(s.status) && !s.reset.hidden && s.save === "Uložit aktuální pohled jako výchozí", s);
    t("C3d viewer ma novy iso uhel (tlacitko 3D se vraci na ulozeny pohled)", blizko((await iso(p.page)).az, 20) && blizko((await iso(p.page)).el, 30), await iso(p.page));
    await p.page.evaluate(() => window.__pdcState.viewer.setView("front")); await konec(p.page);
    await p.page.evaluate(() => window.__pdcState.viewer.setView("iso")); await konec(p.page); await p.page.waitForTimeout(150);
    t("C3e setView('iso') po ulozeni vrati kameru na ulozeny pohled 20 / 30", blizko((await uhly(p.page)).az, 20) && blizko((await uhly(p.page)).el, 30), await uhly(p.page));
    // C4: vraceni puvodniho
    p.mock.calls.length = 0;
    await klik(p.page, "#pohledReset");
    t("C4 'Vrátit původní pohled': prvni klik popisek 'Opravdu vrátit původní?', nic se neposle", (await p.page.textContent("#pohledReset")) === "Opravdu vrátit původní?" && p.mock.calls.length === 0);
    await klik(p.page, "#pohledReset"); await p.page.waitForFunction(() => /Vrácen původní pohled/.test(document.getElementById("pohledStatus").textContent), null, { timeout: 15000 });
    await konec(p.page); await p.page.waitForTimeout(200);
    s = await stav(p.page);
    t("C4b druhy klik: DELETE, stav 'Vrácen původní pohled', tlacitko Vratit zase skryte, kamera preletela na puvodnich 35 / 25 a iso se vratilo", p.mock.calls.length === 1 && p.mock.calls[0].method === "DELETE" && s.reset.hidden && blizko((await uhly(p.page)).az, 35) && blizko((await uhly(p.page)).el, 25)
      && blizko((await iso(p.page)).az, 35) && blizko((await iso(p.page)).el, 25), { calls: p.mock.calls, s, u: await uhly(p.page) });
    // C5: chyby
    for (const [nazev, put_, rx] of [["403 bez prava", () => ({ status: 403, body: { error: "forbidden" } }), /nemáš oprávnění/], ["401", () => ({ status: 401, body: { error: "unauthorized" } }), /nemáš oprávnění/], ["400 s textem", () => ({ status: 400, body: { error: "el 90 je mimo rozsah" } }), /el 90 je mimo rozsah/],
                                     ["500 bez JSON", () => ({ status: 500, raw: "<html>x" }), /Uložení se nepovedlo/]]) {
      p.mock.put = put_;
      await klik(p.page, "#pohledSave"); await klik(p.page, "#pohledSave");
      await p.page.waitForFunction(rxs => new RegExp(rxs).test(document.getElementById("pohledStatus").textContent), rx.source, { timeout: 15000 });
      const e = await stav(p.page);
      t(`C5 ${nazev}: text chyby cervene v okne a stav se NEzmenil (tlacitko Vratit skryte, iso beze zmeny)`, rx.test(e.status) && e.reset.hidden && blizko((await iso(p.page)).az, 35), e);
    }
    p.mock.abort = true;
    await klik(p.page, "#pohledSave"); await klik(p.page, "#pohledSave");
    await p.page.waitForFunction(() => /Spojení selhalo/.test(document.getElementById("pohledStatus").textContent), null, { timeout: 15000 });
    t("C5b spojeni selze: 'Spojení selhalo.'", true);
    p.mock.abort = false;
    t("C5c bez chyb ve strance ani v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
    // C6: ulozeny pohled pri nacteni, stav v okne
    p = await mk(browser, { view: { az: -60, el: 10 } }); await load(p, STR[40]);
    await p.page.waitForSelector("#pohledBlok:not([hidden])", { timeout: 30000 });
    s = await stav(p.page);
    t("C6 ulozeny pohled -60 / 10 pri nacteni: 'Výchozí pohled je uložený: otočení -60°, náklon 10°.' a tlacitko Vratit je videt", /Výchozí pohled je uložený: otočení -60°, náklon 10°\./.test(s.status) && !s.reset.hidden, s);
    await p.ctx.close();
  });

  await sec("D staticke kontroly (verze, piny ?v=)", async () => {
    const md5 = f => crypto.createHash("md5").update(fs.readFileSync(f)).digest("hex").slice(0, 10);
    const v = fs.readFileSync(`${WEB}/js/v3d/viewer3d.js`, "utf8");
    t("D1 viewer3d.js: V3D.version 1.17.0 a hlavicka popisuje 1.17.0 (isoAngles, setIsoAngles, currentAngles)", /V3D\.version = '1\.17\.0'/.test(v) && /1\.17\.0: VYCHOZI UHEL POHLEDU 3D/.test(v) && /setIsoAngles/.test(v) && /currentAngles/.test(v));
    t("D2 viewDir('iso') pouziva promenne isoAz / isoEl, ne konstanty (puvodni 35 / 25 jen jako vychozi)", /rotAboutUp\(front, isoAz\)/.test(v) && /Math\.cos\(isoEl \* DEG\)/.test(v) && !/rotAboutUp\(front, ISO_AZ\)/.test(v));
    const pc = fs.readFileSync(`${WEB}/js/product-configurator.js`, "utf8");
    t("D3 product-configurator.js predava schema.view jako opts.isoAngles (viewerOpts ma prednost)", /!\("isoAngles" in o\) && S\.schema && S\.schema\.view/.test(pc) && /o\.isoAngles = S\.schema\.view/.test(pc));
    const host = fs.readFileSync(`${WEB}/js/stul-host.js`, "utf8");
    t("D4 stul-host.js: blok pohledu v okne Vychozi konfigurace, sonda `view` in sc, PUT / DELETE /api/shop/configurator/view", /id="pohledBlok"|"pohledBlok"/.test(host) && /"view" in sc/.test(host) && /\/api\/shop\/configurator\/view/.test(host));
    for (const f of ["stul-konfigurator.html", "stul-konfigurator-35.html", "stul-konfigurator-40.html", "stul-konfigurator-41.html", "stul-konfigurator-45.html"]) {
      const h = fs.readFileSync(`${WEB}/${f}`, "utf8");
      const m = /\/js\/product-configurator\.js\?v=([0-9a-f]{10})/.exec(h), m2 = /\/js\/stul-host\.js\?v=([0-9a-f]{10})/.exec(h);
      t(`D5 ${f}: piny ?v= product-configurator.js a stul-host.js = md5 souboru`, m && m2 && m[1] === md5(`${WEB}/js/product-configurator.js`) && m2[1] === md5(`${WEB}/js/stul-host.js`), { m: m && m[1], m2: m2 && m2[1] });
    }
    const hv = /viewer: "\/js\/v3d\/viewer3d\.js\?v=([0-9a-f]{10})"/.exec(host);
    t("D6 stul-host.js: pin viewer3d.js = md5 noveho souboru (jinak by prohlizec nacetl starou cache bez isoAngles)", hv && hv[1] === md5(`${WEB}/js/v3d/viewer3d.js`), hv && hv[1]);
    for (const f of ["embed/stul.html", "miniweb/product.html"]) {
      const h = fs.readFileSync(`${WEB}/${f}`, "utf8");
      const mm = /\/js\/v3d\/viewer3d\.js\?v=([0-9a-f]{10})/.exec(h);
      t(`D7 ${f}: pin viewer3d.js = md5 noveho souboru (mini-shop a vlozeny generator dostanou nove API)`, mm && mm[1] === md5(`${WEB}/js/v3d/viewer3d.js`), mm && mm[1]);
    }
  });

  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
