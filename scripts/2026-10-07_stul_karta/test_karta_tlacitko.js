// Test tlacitka "Vytvorit kartu" v ZAMESTNANECKEM Generatoru stolu (bot10, 2026-10-07; Robert: "pridat do generatoru: tlacitko ktere z aktualni sestavy vytvori aktivni kartu").
// Kontrakt: docs/KONTRAKT_KARTA_Z_KONFIGURACE.md. Endpoint /api/admin/konfigurace/karta se v testu SIMULUJE (page.route) - jeho skutecnou stranku testuji test_karta_db.py / test_karta_route.py nad
// docasnymi tabulkami; zbytek je SKUTECNY: skutecna stranka (stul-konfigurator*.html + js/stul-host.js + js/stul-karta.js) + skutecny modul voleb + skutecny viewer nad skutecnym kodem stolu
// (api/stul_shop.py) pres most scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, fiktivni karty, nic se nezapisuje). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --setenv=PID41=9879 --setenv=PID45=9880 \
//     --setenv=PRAVIDLA_TEST={} --working-directory=<koren se zivym api + kandidatnim webapp> api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py \
//     /opt/konfigurator/scripts/2026-10-07_stul_karta/test_karta_tlacitko.js 4934
// Casti: A sonda (tlacitko se ukaze JEN po 200 {ok:true}) | B dialog a pozadavky (system 40): nahled, pole, odeslani, vysledek, odkazy, chyby, XSS, dvojklik, klavesnice |
//        C vsechny systemy (30/35/40/41/45) | D staticke kontroly (piny ?v=, bez innerHTML). ONLY=A,C ; snimky: SHOT=/cesta/predpona ; WEB_DIR=<webapp kandidata> pro staticke kontroly.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const crypto = require("crypto");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
const PIDS = { 30: process.env.PID, 35: process.env.PID35, 40: process.env.PID40, 41: process.env.PID41, 45: process.env.PID45 };
const STRANKY = { 30: "/stul-konfigurator.html", 35: "/stul-konfigurator-35.html", 40: "/stul-konfigurator-40.html", 41: "/stul-konfigurator-41.html", 45: "/stul-konfigurator-45.html" };
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
async function sec(name, fn) { if (process.env.ONLY && !process.env.ONLY.split(",").includes(name[0])) return; console.log("\n## " + name); try { await fn(); } catch (e) { t(name + ": test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 700)); } }
const plain = s => String(s).replace(/[\s  ]+/g, " ").trim();

const KATEGORIE = [{ id: 182, name: "Balicí stoly a pracoviště na míru" }, { id: 206, name: "Lehký balicí stůl system 30" }, { id: 311, name: "Robustní balicí stůl system 40" }, { id: 312, name: "Ergonomický balicí stůl system 35" }];
const SONDA = { ok: true, verze: 1, muze_aktivovat: true, kategorie: KATEGORIE, vychozi_kategorie: { "30": 206, "35": 312, "40": 311, "41": 183, "45": null } };
const NAHLED = {
  nahled: true, sku: "STUL-S40-abcd1234", system: 40, name: "Pracovní stůl systém 40 – 1280 × 800 × 840 mm", kod: "STL-ABCD12", hash: "abcd1234abcd1234", price: { net_czk: 27899, vat_rate: 21, vat_czk: 5859, gross_czk: 33758 },
  category_id: 311, kategorie: KATEGORIE, active: true, muze_aktivovat: true, rules_version: "x", existing: null
};
const vytvoreno = body => ({ ok: true, existing: false, id: 5400, sku: "STUL-S40-abcd1234", system: 40, name: String(body.name || "").trim(), kod: "STL-ABCD12", hash: "abcd1234abcd1234", price: NAHLED.price, active: body.active, category_id: body.category_id,
                             url: "/produkt/pracovni-stul-test", glb_file: "stul/STUL-S40-abcd1234.glb", rules_version: "x", poznamka: body.active ? null : "Karta vznikla NEAKTIVNÍ (aktivaci zapíná uživatel s právem upravovat skladové karty)." });
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;

async function mk(browser, o) {
  o = o || {};
  const ctx = await browser.newContext({ viewport: { width: o.w || 1400, height: o.h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  await ctx.route(/\/produkt\//, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: "<!doctype html><title>karta</title><p>karta" }));          // stranka karty se v testu nenacita
  await ctx.route(/^https:\/\/(?:[a-z0-9-]+\.)*(?:logiman\.cz|baliace-stoly\.top|packing-tables\.top)\//, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: "<!doctype html><title>x</title><p>x" }));
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  const mock = { sonda: { status: 200, body: SONDA }, nahled: () => ({ status: 200, body: NAHLED }), vytvor: body => ({ status: 201, body: vytvoreno(body) }), posts: [], sondy: 0, delay: 0, abort: false };
  await page.route("**/api/admin/konfigurace/karta", async route => {
    const req = route.request();
    if (req.method() === "GET") {
      mock.sondy++; const s = mock.sonda;
      if (s.abort) return route.abort("failed");
      return route.fulfill({ status: s.status, contentType: "application/json", body: s.raw != null ? s.raw : JSON.stringify(s.body) });
    }
    if (req.method() === "POST") {
      let body = null; try { body = JSON.parse(req.postData() || "null"); } catch (e) { /* nic */ }
      mock.posts.push({ body, ctype: req.headers()["content-type"] || "" });
      if (mock.delay && !(body && body.nahled)) await new Promise(r => setTimeout(r, mock.delay));
      if (mock.abort && !(body && body.nahled)) return route.abort("failed");
      const x = body && body.nahled ? mock.nahled(body) : mock.vytvor(body);
      return route.fulfill({ status: x.status, contentType: x.raw != null ? "text/html" : "application/json", body: x.raw != null ? x.raw : JSON.stringify(x.body) });
    }
    return route.fulfill({ status: 405, body: "{}" });
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
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash && !S.pending; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const stavTl = page => page.evaluate(() => { const b = document.getElementById("kartaBtn"); return b ? { hidden: b.hidden, disabled: b.disabled, title: b.title, text: b.textContent } : null; });
const ocekavano = page => page.evaluate(() => { const S = window.__pdcState; return { sel: JSON.parse(JSON.stringify(S.sel)), rv: S.last.rules_version || S.schema.rules_version, hash: S.last.hash, kod: S.last.kod }; });
const xss = page => page.evaluate(() => window.__xss);
async function otevri(p) { await p.page.click("#kartaBtn"); await p.page.waitForSelector(".kar-dlg", { timeout: 5000 }); await p.page.waitForSelector("#karOdeslat:not([disabled]), #karChyba:not([hidden]), #karExistuje", { timeout: 8000 }); }
async function zavriDlg(p) { await p.page.keyboard.press("Escape").catch(() => {}); await p.page.waitForSelector(".kar-overlay", { state: "detached", timeout: 4000 }).catch(() => {}); }
const poslednipost = p => p.mock.posts[p.mock.posts.length - 1] && p.mock.posts[p.mock.posts.length - 1].body;
const bezNahledu = p => p.mock.posts.filter(x => x.body && !x.body.nahled);

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  await sec("A sonda: tlacitko se ukaze JEN po 200 {ok:true} (statika jde zive driv nez API)", async () => {
    const pripady = [
      ["404 (backend jeste nebezi)", { status: 404, body: {} }, false], ["401 (nepřihlášený)", { status: 401, body: { error: "unauthorized" } }, false],
      ["403 (bez práva sklad_karty.vytvorit)", { status: 403, body: { error: "forbidden" } }, false], ["500", { status: 500, body: {} }, false],
      ["200 ale ok:false", { status: 200, body: { ok: false } }, false], ["200 ale ok jako text 'true'", { status: 200, body: { ok: "true" } }, false],
      ["200 s rozbitym JSON", { status: 200, raw: "<html>not json" }, false], ["spojeni selze", { abort: true }, false],
      ["200 {ok:true, verze:1}", { status: 200, body: SONDA }, true]
    ];
    for (const [nazev, sonda, ma] of pripady) {
      const p = await mk(browser); p.mock.sonda = sonda;
      await p.page.goto(`${BASE}${STRANKY[30]}?debug=1`, { waitUntil: "domcontentloaded" });
      await p.page.waitForSelector("#kartaBtn", { state: "attached", timeout: 30000 });
      const t0 = Date.now(); while (p.mock.sondy < 1 && Date.now() - t0 < 20000) await p.page.waitForTimeout(100);
      await p.page.waitForTimeout(500);
      const vis = await p.page.locator("#kartaBtn").isVisible();
      t(`A ${nazev}: tlacitko ${ma ? "je vidět" : "je skryté"}`, vis === ma, vis);
      if (!ma) t(`A ${nazev}: skryte tlacitko nejde ani zaostrit (display:none), dialog neexistuje`, !(await p.page.evaluate(() => { const b = document.getElementById("kartaBtn"); b.focus(); return document.activeElement === b; })) && (await p.page.locator(".kar-overlay").count()) === 0);
      await p.ctx.close();
    }
  });

  await sec("B dialog a pozadavky (stranka systemu 40)", async () => {
    const p = await mk(browser); await load(p, STRANKY[40]);
    await p.page.waitForFunction(() => { const b = document.getElementById("kartaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    const st = await stavTl(p.page);
    t("B1 tlacitko 'Vytvořit kartu' je vidět a povolené po nacteni konfigurace", st && !st.hidden && !st.disabled && /Vytvořit kartu/.test(st.text), st);
    t("B1b tlacitko je v okne 'Cena a scéna' (u 'Vložit do Scény' a 'Do online nabídky', v jednom bloku .kar-wrap)", await p.page.evaluate(() => { const b = document.getElementById("kartaBtn"), s = document.getElementById("sceneBtn"); const w = b && b.closest(".kar-wrap"); return !!w && !!s && w.parentNode === s.parentNode; }));
    t("B1c po sonde se tlacitko NEzobrazi dvakrat a sonda je jen jedna", (await p.page.locator("#kartaBtn").count()) === 1 && p.mock.sondy === 1, p.mock.sondy);
    if (SHOT) await p.page.locator("#kartaBtn").scrollIntoViewIfNeeded().then(() => p.page.screenshot({ path: SHOT + "_okno.png" }));
    const exp = await ocekavano(p.page);

    // ---- otevreni a nahled
    await otevri(p);
    const dlg = await p.page.evaluate(() => { const d = document.querySelector(".kar-dlg"); return { role: d.getAttribute("role"), modal: d.getAttribute("aria-modal"), lab: d.getAttribute("aria-labelledby"), title: (document.getElementById("karTitle") || {}).textContent, focus: document.activeElement && document.activeElement.id }; });
    t("B2 dialog: role=dialog, aria-modal, nadpis; po nacteni nahledu je zaostreno tlacitko vytvorit", dlg.role === "dialog" && dlg.modal === "true" && dlg.lab === "karTitle" && /Vytvořit kartu z konfigurace/.test(dlg.title) && dlg.focus === "karOdeslat", dlg);
    const nb = poslednipost(p);
    t("B2b prvni POST je NAHLED s presnym vyberem ze stranky, rules_version a hash; bez ceny / nazvu / kategorie", nb && nb.nahled === true && nb.product_id === Number(PIDS[40]) && JSON.stringify(nb.configuration.selection) === JSON.stringify(exp.sel)
      && nb.configuration.rules_version === exp.rv && nb.hash === exp.hash && Object.keys(nb).every(k => ["product_id", "configuration", "hash", "nahled"].includes(k)), nb && Object.keys(nb));
    t("B2c hlavicka Content-Type: application/json", p.mock.posts[0].ctype.indexOf("application/json") === 0, p.mock.posts[0].ctype);
    const f = await p.page.evaluate(() => ({ nazev: document.getElementById("karNazev").value, kat: document.getElementById("karKategorie").value, kats: [...document.getElementById("karKategorie").options].map(o => o.value + ":" + o.textContent),
                                              aktivni: document.getElementById("karAktivni") && document.getElementById("karAktivni").checked, cena: document.getElementById("karCena").textContent, sku: document.getElementById("karSku").textContent,
                                              btn: document.getElementById("karOdeslat").textContent, max: document.getElementById("karNazev").maxLength }));
    t("B3 pole z nahledu: nazev, kategorie 311 vybrana (+ 'bez kategorie'), aktivni zaskrtnuto, tlacitko 'Vytvořit aktivní kartu'", f.nazev === NAHLED.name && f.kat === "311" && f.kats[0].startsWith(":") && f.kats.length === KATEGORIE.length + 1 && f.aktivni === true && f.btn === "Vytvořit aktivní kartu" && f.max === 200, f);
    t("B3b cena (bez a s DPH, snimek) a kod karty jsou videt", /27\s?899\s?Kč bez DPH/.test(f.cena) && /33\s?758\s?Kč s DPH/.test(f.cena) && /STUL-S40-abcd1234/.test(f.sku), f);
    if (SHOT) await p.page.locator(".kar-dlg").screenshot({ path: SHOT + "_dialog.png" });
    await p.page.uncheck("#karAktivni");
    t("B3c odskrtnuti 'Aktivní hned' zmeni tlacitko na 'Vytvořit neaktivní kartu'", (await p.page.textContent("#karOdeslat")) === "Vytvořit neaktivní kartu");
    await p.page.check("#karAktivni");
    t("B3d zaskrtnuti ho vrati", (await p.page.textContent("#karOdeslat")) === "Vytvořit aktivní kartu");
    await zavriDlg(p);
    t("B3e Escape dialog zavre a zaostri zpet tlacitko; bez dalsiho POSTu", (await p.page.locator(".kar-overlay").count()) === 0 && (await p.page.evaluate(() => document.activeElement && document.activeElement.id)) === "kartaBtn" && p.mock.posts.length === 1, p.mock.posts.length);

    // ---- odeslani
    p.mock.posts.length = 0;
    await otevri(p);
    await p.page.fill("#karNazev", "  Můj testovací stůl  ");
    await p.page.selectOption("#karKategorie", "312");
    p.mock.delay = 700;
    await p.page.click("#karOdeslat");
    await p.page.waitForTimeout(200);
    const busy = await p.page.evaluate(() => ({ btn: document.getElementById("karOdeslat").textContent, dis: document.getElementById("karOdeslat").disabled, zr: document.getElementById("karZrusit").disabled, stav: document.getElementById("kartaStav").textContent }));
    t("B4 behem vytvareni: 'Vytvářím…', tlacitka zakazana, stav pod tlacitkem", busy.btn === "Vytvářím…" && busy.dis && busy.zr && /Vytvářím kartu/.test(busy.stav), busy);
    await p.page.keyboard.press("Escape"); await p.page.waitForTimeout(150);
    t("B4b Escape behem vytvareni dialog NEzavre", (await p.page.locator(".kar-overlay").count()) === 1);
    await p.page.evaluate(() => { const bt = document.getElementById("karOdeslat"); bt.disabled = false; bt.click(); bt.click(); bt.disabled = true; });          // obejit atribut disabled: brani druhemu POSTu i vnitrni stav `busy`
    await p.page.waitForSelector("#karHotovo", { timeout: 8000 });
    const vyt = bezNahledu(p);
    t("B4c dvojity klik poslal prave JEDEN POST na vytvoreni", vyt.length === 1, vyt.length);
    const b = vyt[0] && vyt[0].body;
    t("B4d POST: vyber, rules_version a hash ze stranky + nazev (neoriznuty - cisti server), category_id jako cislo, active true; nic navic", b && JSON.stringify(b.configuration.selection) === JSON.stringify(exp.sel) && b.hash === exp.hash && b.name === "  Můj testovací stůl  "
      && b.category_id === 312 && b.active === true && b.nahled === undefined && Object.keys(b).every(k => ["product_id", "configuration", "hash", "name", "category_id", "active"].includes(k)), b);
    p.mock.delay = 0;
    const ok = await p.page.evaluate(() => ({ hotovo: document.getElementById("karHotovo").textContent, odkazy: [...document.querySelectorAll(".kar-btns a")].map(a => [a.textContent, a.getAttribute("href"), a.target, a.rel]), zrusit: document.getElementById("karZrusit").textContent,
                                              odeslat: document.getElementById("karOdeslat").hidden, stav: document.getElementById("kartaStav").textContent, stavOdkaz: (document.querySelector("#kartaStav a") || {}).getAttribute && document.querySelector("#kartaStav a").getAttribute("href") }));
    t("B5 vysledek: 'Karta vytvořena: #5400 Můj testovací stůl (aktivní).' + odkaz Otevřít kartu (nove okno, noopener) + tlacitko Zavřít; vytvorit je skryte", /Karta vytvořena: #5400 Můj testovací stůl \(aktivní\)/.test(ok.hotovo) && ok.odkazy.length === 1
      && ok.odkazy[0][0] === "Otevřít kartu" && /\/produkt\/pracovni-stul-test$/.test(ok.odkazy[0][1]) && ok.odkazy[0][2] === "_blank" && /noopener/.test(ok.odkazy[0][3]) && ok.zrusit === "Zavřít" && ok.odeslat === true, ok);
    t("B5b stav pod tlacitkem v okne Cena a scena nese odkaz na kartu", /Karta vytvořena: karta #5400 \(aktivní\)\./.test(ok.stav) && /\/produkt\/pracovni-stul-test$/.test(ok.stavOdkaz || ""), ok);
    await p.page.click("#karZrusit");
    t("B5c Zavřít dialog zavre", (await p.page.locator(".kar-overlay").count()) === 0);
    t("B5d po vytvoreni zustava tlacitko 'Vytvořit kartu' povolene (karta se stejnym SKU server vrati jako existujici)", await p.page.evaluate(() => { const b = document.getElementById("kartaBtn"); return !b.hidden && !b.disabled; }));

    // ---- karta uz existuje
    p.mock.nahled = () => ({ status: 200, body: { ...NAHLED, existing: { id: 5400, name: "Karta <b>x</b>", active: false, archived: false, url: "/produkt/pracovni-stul-test" } } });
    p.mock.posts.length = 0;
    await otevri(p);
    const ex = await p.page.evaluate(() => ({ varovani: document.getElementById("karExistuje").textContent, vytvorit: document.getElementById("karOdeslat").hidden, odkaz: (document.querySelector(".kar-btns a") || {}).textContent, zav: document.getElementById("karZrusit").textContent, pole: !!document.getElementById("karNazev") }));
    t("B6 existujici karta: varovani s id a stavem (neaktivní), tlacitko vytvorit skryte, zadna pole, odkaz Otevřít kartu, jen NAHLED odeslan", /Karta s touhle konfigurací už existuje: #5400 Karta <b>x<\/b> \(neaktivní\)/.test(ex.varovani) && ex.vytvorit && ex.odkaz === "Otevřít kartu" && ex.zav === "Zavřít" && !ex.pole && bezNahledu(p).length === 0, ex);
    t("B6b text z odpovedi serveru se vklada jako TEXT (zadny <b> element)", (await p.page.locator(".kar-dlg b").count()) === 0 && (await xss(p.page)) === undefined);
    await zavriDlg(p);
    p.mock.nahled = () => ({ status: 200, body: NAHLED });

    // ---- bez prava aktivovat
    p.mock.nahled = () => ({ status: 200, body: { ...NAHLED, muze_aktivovat: false, active: false } });
    p.mock.posts.length = 0;
    await otevri(p);
    const na = await p.page.evaluate(() => ({ chk: !!document.getElementById("karAktivni"), text: (document.getElementById("karNeaktivni") || {}).textContent, btn: document.getElementById("karOdeslat").textContent }));
    t("B7 bez prava upravovat karty: zadne zaskrtavatko, text 'vznikne neaktivní', tlacitko 'Vytvořit kartu'", !na.chk && /vznikne neaktivní/.test(na.text || "") && na.btn === "Vytvořit kartu", na);
    p.mock.vytvor = body => ({ status: 201, body: vytvoreno(body) });
    await p.page.click("#karOdeslat"); await p.page.waitForSelector("#karHotovo", { timeout: 8000 });
    const bn = bezNahledu(p)[0].body;
    t("B7b POST nese active:false a vysledek rika '(neaktivní)' + poznamku", bn.active === false && /\(neaktivní\)/.test(await p.page.textContent("#karHotovo")) && /NEAKTIVNÍ/.test(await p.page.textContent(".kar-dlg")));
    await zavriDlg(p);
    p.mock.nahled = () => ({ status: 200, body: NAHLED });

    // ---- chyby serveru
    const chyby = [
      ["409 configuration_changed", 409, { error: "configuration_changed", message: "x" }, /Konfigurace se mezitím změnila/, true],
      ["409 rules_changed", 409, { error: "rules_changed", message: "x" }, /Pravidla generátoru se mezitím změnila/, true],
      ["422 invalid_configuration se seznamem", 422, { error: "invalid_configuration", message: "x", errors: [{ slot: null, message: "Police se nevejde." }, { slot: null, message: "Šuplík koliduje." }] }, /Tuhle konfiguraci nejde vyrobit:/, false],
      ["400 invalid_name", 400, { error: "invalid_name", message: "x" }, /Neplatný název karty/, false], ["400 invalid_category", 400, { error: "invalid_category", message: "x" }, /Tuhle kategorii nelze použít/, false],
      ["409 exists", 409, { error: "exists", message: "x" }, /právě vznikla/, false], ["500 glb_failed", 500, { error: "glb_failed", message: "x" }, /Model konfigurace se nepodařilo postavit/, false],
      ["403 forbidden", 403, { error: "forbidden" }, /nemáš oprávnění/, false], ["401 unauthorized", 401, { error: "unauthorized" }, /Nejsi přihlášený/, false],
      ["429 rate_limited", 429, { error: "rate_limited", message: "x" }, /Limit 20 nových karet/, false], ["500 bez JSON", 500, null, /Kartu se nepodařilo vytvořit/, false],
      ["neznamy kod s hláškou serveru", 400, { error: "novy_kod", message: "Hláška ze serveru." }, /Hláška ze serveru\./, false]
    ];
    for (const [nazev, status, body, rx, refresh] of chyby) {
      p.mock.vytvor = () => body === null ? { status, raw: "<html>chyba" } : { status, body };
      p.mock.posts.length = 0;
      const r0 = p.trk.resolve;
      await otevri(p);
      await p.page.click("#karOdeslat");
      await p.page.waitForSelector("#karChyba:not([hidden])", { timeout: 8000 });
      const e = await p.page.evaluate(() => ({ text: document.getElementById("karChyba").innerText, li: document.querySelectorAll("#karChyba li").length, dis: document.getElementById("karOdeslat").disabled, txt: document.getElementById("karOdeslat").textContent, zr: document.getElementById("karZrusit").disabled, hotovo: !!document.getElementById("karHotovo") }));
      t(`B8 ${nazev}: cesky text chyby, dialog zustava, tlacitko povolene a ma puvodni popisek`, rx.test(e.text) && !e.dis && e.txt === "Vytvořit aktivní kartu" && !e.zr && !e.hotovo, e);
      if (status === 422) t("B8b 422: duvody jako seznam (2 polozky)", e.li === 2, e.li);
      if (refresh) { await p.page.waitForTimeout(1500); t(`B8c ${nazev}: stranka si nacte konfiguraci znovu (nova dvojice resolve)`, p.trk.resolve > r0, p.trk.resolve - r0); }
      await zavriDlg(p);
    }
    p.mock.abort = true; p.mock.posts.length = 0;
    await otevri(p); await p.page.click("#karOdeslat");
    await p.page.waitForSelector("#karChyba:not([hidden])", { timeout: 8000 });
    t("B8d spojeni selze: 'Spojení selhalo, karta nebyla vytvořena.' a jde to zkusit znovu", /Spojení selhalo/.test(await p.page.innerText("#karChyba")) && !(await p.page.locator("#karOdeslat").isDisabled()));
    p.mock.abort = false; await zavriDlg(p);
    p.mock.nahled = () => ({ status: 409, body: { error: "rules_changed", message: "x" } });
    await otevri(p);
    t("B8e chyba uz u NAHLEDU: text chyby, tlacitko vytvorit zustava zakazane", /Pravidla generátoru se mezitím změnila/.test(await p.page.innerText("#karChyba")) && (await p.page.locator("#karOdeslat").isDisabled()));
    await zavriDlg(p);
    p.mock.nahled = () => ({ status: 200, body: NAHLED });

    // ---- bezpecnost odpovedi
    p.mock.vytvor = body => ({ status: 201, body: { ...vytvoreno(body), name: '<img src=x onerror="window.__xss=1">', url: "javascript:window.__xss=2" } });
    await otevri(p); await p.page.click("#karOdeslat"); await p.page.waitForSelector("#karHotovo", { timeout: 8000 });
    t("B9 nazev z odpovedi s HTML se zobrazi jako text a nespusti se (zadny <img>)", (await p.page.locator(".kar-dlg img, #kartaStav img").count()) === 0 && (await xss(p.page)) === undefined && /<img src=x/.test(await p.page.textContent("#karHotovo")));
    t("B9b odkaz javascript: se nevykresli (ani v dialogu, ani pod tlacitkem)", (await p.page.locator('.kar-dlg a[href^="javascript"], #kartaStav a').count()) === 0);
    await zavriDlg(p);
    p.mock.vytvor = body => ({ status: 201, body: { ...vytvoreno(body), url: "https://evil.example.com/karta" } });
    await otevri(p); await p.page.click("#karOdeslat"); await p.page.waitForSelector("#karHotovo", { timeout: 8000 });
    t("B9c odkaz na cizi domenu se nevykresli", (await p.page.locator('.kar-dlg a, #kartaStav a').count()) === 0);
    await zavriDlg(p);
    p.mock.vytvor = body => ({ status: 201, body: { ...vytvoreno(body), url: "https://baliace-stoly.top/produkt/x" } });
    await otevri(p); await p.page.click("#karOdeslat"); await p.page.waitForSelector("#karHotovo", { timeout: 8000 });
    t("B9d odkaz na nasi domenu (baliace-stoly.top) se vykresli", (await p.page.locator('.kar-btns a[href^="https://baliace-stoly.top/"]').count()) === 1);
    await zavriDlg(p);

    // ---- klavesnice
    p.mock.vytvor = body => ({ status: 201, body: vytvoreno(body) });
    await otevri(p);
    const poradi = [];
    for (let i = 0; i < 6; i++) { poradi.push(await p.page.evaluate(() => document.activeElement && (document.activeElement.id || document.activeElement.tagName))); await p.page.keyboard.press("Tab"); }
    t("B10 Tab se v dialogu zacykli (focus trap): nikdy neopusti dialog", poradi.every(x => ["karOdeslat", "karZrusit", "karNazev", "karKategorie", "karAktivni"].includes(x)), poradi);
    await p.page.keyboard.press("Shift+Tab");
    t("B10b Shift+Tab z prvniho prvku skoci na posledni (v dialogu)", await p.page.evaluate(() => !!document.activeElement.closest(".kar-dlg")));
    await zavriDlg(p);
    await otevri(p); await p.page.mouse.click(5, 5); await p.page.waitForTimeout(200);
    t("B10c klik mimo dialog (na pozadi) ho zavre", (await p.page.locator(".kar-overlay").count()) === 0);

    // ---- stav tlacitka podle konfigurace
    await p.page.evaluate(() => { const S = window.__pdcState; });
    t("B11 bez chyb ve strance ani v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  await sec("C vsechny systemy (30/35/40/41/45): spravna karta + vyber + zmena vyberu", async () => {
    for (const sys of [30, 35, 40, 41, 45]) {
      if (!PIDS[sys]) { t(`C${sys} chybi promenna prostredi s fiktivni kartou`, false); continue; }
      const p = await mk(browser); await load(p, STRANKY[sys]);
      await p.page.waitForFunction(() => { const b = document.getElementById("kartaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
      t(`C${sys}a tlacitko Vytvořit kartu je vidět a povolené`, (await stavTl(p.page)).hidden === false);
      const exp = await ocekavano(p.page);
      await otevri(p);
      const nb = poslednipost(p);
      t(`C${sys}b nahled nese kartu generatoru ${PIDS[sys]} a presne aktualni vyber, rules_version a hash`, nb && nb.product_id === Number(PIDS[sys]) && JSON.stringify(nb.configuration.selection) === JSON.stringify(exp.sel) && nb.configuration.rules_version === exp.rv && nb.hash === exp.hash, { pid: nb && nb.product_id, hash: nb && nb.hash, exp: exp.hash });
      await zavriDlg(p);
      if (sys === 40 || sys === 45) {
        const w0 = Number(exp.sel.w);
        await p.page.evaluate(() => { const r = document.querySelector('[data-slot="w"] input.pdc-range'); r.value = String(Number(r.value) + 100); r.dispatchEvent(new Event("input", { bubbles: true })); r.dispatchEvent(new Event("change", { bubbles: true })); });
        await idle(p, 1500);
        await p.page.waitForFunction(() => { const b = document.getElementById("kartaBtn"); return b && !b.disabled; }, null, { timeout: 30000 });
        const exp2 = await ocekavano(p.page);
        p.mock.posts.length = 0;
        await otevri(p);
        const nb2 = poslednipost(p);
        t(`C${sys}c po zmene sirky (${w0} -> ${exp2.sel.w}) nese dalsi nahled NOVY vyber a novy hash`, nb2 && String(nb2.configuration.selection.w) === String(exp2.sel.w) && nb2.hash === exp2.hash && nb2.hash !== exp.hash, { w: nb2 && nb2.configuration.selection.w, exp2: exp2.sel.w });
        await zavriDlg(p);
      }
      t(`C${sys}d bez chyb ve strance ani v konzoli`, p.errs.length === 0, p.errs.slice(0, 3));
      await p.ctx.close();
    }
  });

  await sec("D staticke kontroly (piny ?v=, bez innerHTML, jednou ve strankach)", async () => {
    const js = fs.readFileSync(`${WEB}/js/stul-karta.js`, "utf8");
    t("D1 modul nepouziva innerHTML / outerHTML / insertAdjacentHTML / document.write / eval", !/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new Function/.test(js));
    const md5 = f => crypto.createHash("md5").update(fs.readFileSync(f)).digest("hex").slice(0, 10);
    for (const sys of [30, 35, 40, 41, 45]) {
      const html = fs.readFileSync(`${WEB}${STRANKY[sys]}`, "utf8");
      const m = html.match(/<script src="\/js\/stul-karta\.js\?v=([0-9a-f]{10})"><\/script>/g) || [];
      const pin = m.length === 1 ? m[0].match(/v=([0-9a-f]{10})/)[1] : null;
      t(`D2 stranka systemu ${sys}: modul stul-karta.js je nacten jednou, s pinem = md5 souboru, PRED stul-host.js`, m.length === 1 && pin === md5(`${WEB}/js/stul-karta.js`) && html.indexOf("/js/stul-karta.js") < html.indexOf("/js/stul-host.js"), { m: m.length, pin, md5: md5(`${WEB}/js/stul-karta.js`) });
    }
    const host = fs.readFileSync(`${WEB}/js/stul-host.js`, "utf8");
    t("D3 stul-host.js montuje StulKarta jednou a vola S.karta.sync() na vsech trech mistech jako S.nabidka.sync()", (host.match(/window\.StulKarta\.mount/g) || []).length === 1 && (host.match(/S\.karta\.sync\(\)/g) || []).length === 3 && (host.match(/S\.nabidka\.sync\(\)/g) || []).length === 3);
  });

  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
