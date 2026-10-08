// Test tlacitka "Do online nabidky" v ZAMESTNANECKEM Generatoru stolu (bot16, 2026-10-06; Robert: "tlacitko pro promitnuti konfigurace stolu do online nabidky, pro kazdy generator").
// Kontrakt: docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md (bot5). Backend jeste nebezi -> endpoint /api/admin/konfigurace/nabidka se v testu SIMULUJE (page.route); zbytek je SKUTECNY:
// skutecna stranka (stul-konfigurator*.html + js/stul-host.js + js/stul-nabidka.js) + skutecny modul voleb + skutecny viewer nad skutecnym kodem stolu (api/stul_shop.py) pres most
// scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, fiktivni karty, nic se nezapisuje). Spusteni (DB pres systemd-run), kandidat = izolovany worktree:
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --setenv=PID41=9879 --working-directory=<worktree> \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py /opt/konfigurator/scripts/2026-10-06_nabidka_tlacitko_testy/test_nabidka_tlacitko.js 4934
// Casti: A sonda (tlacitko se ukaze JEN po 200 {ok:true}) | B dialog a pozadavek (system 30): telo bez ceny, validace, pole, vysledek, odkazy, chyby, XSS, dvojklik, klavesnice, mobil |
//        C vsechny ctyri systemy (30/35/40/41): spravna karta + vyber + zmena vyberu + stav tlacitka pri prepoctu a neplatne konfiguraci | D staticke kontroly (piny ?v=, bez innerHTML).
// Spusteni jen nekterych casti: ONLY=A,C ; snimky: SHOT=/cesta/predpona.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
const PIDS = { 30: process.env.PID, 35: process.env.PID35, 40: process.env.PID40, 41: process.env.PID41 };
const STRANKY = { 30: "/stul-konfigurator.html", 35: "/stul-konfigurator-35.html", 40: "/stul-konfigurator-40.html", 41: "/stul-konfigurator-41.html" };
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
async function sec(name, fn) { if (process.env.ONLY && !process.env.ONLY.split(",").includes(name[0])) return; console.log("\n## " + name); try { await fn(); } catch (e) { t(name + ": test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 600)); } }
const plain = s => String(s).replace(/[\s  ]+/g, " ").trim();

// odpoved podle SKUTECNEHO kontraktu bota5 (docs/KONTRAKT_NABIDKA_Z_KONFIGURACE.md po commitu 9c422069): online_url je RELATIVNI, admin_url se nevraci, je v3d_duvod
const ONLINE_REL = "/nabidka-online.html?t=TESTTOKEN";
const ONLINE = BASE + ONLINE_REL, ADMIN_LIST = BASE + "/admin.html#onlineoffers";
const OK201 = {
  offer_id: 123, offer_number: "Logiman5015", online_url: ONLINE_REL,
  line: { kod: "S30-TEST", hash: "h1", qty: 1, unit_net_czk: 26180, total_net_czk: 26180 },
  price: { net_czk: 26180, vat_rate: 21, vat_czk: 5498, gross_czk: 31678 }, montaz: { pct: 12, czk: 3142 }, rules_version: "x", v3d: true, v3d_duvod: null
};
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;

async function mk(browser, o) {
  o = o || {};
  const ctx = await browser.newContext({ viewport: { width: o.w || 1400, height: o.h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  if (o.blokovatOkno) await ctx.addInitScript(() => { window.open = () => null; });           // simulace blokatoru oken
  await ctx.route(/\/scene\.html/, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: "<!doctype html><title>scena</title><p>scena" }));      // Scena (bot8) se v testu nenacita, jen se kontroluje adresa
  await ctx.route(/\/nabidka-online\.html/, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: "<!doctype html><title>nabidka</title><p>nabidka" }));      // stranka nabidky (bot5) se v testu nenacita
  await ctx.route(/^https:\/\/(?:[a-z0-9-]+\.)*(?:logiman\.cz|baliace-stoly\.top|packing-tables\.top)\//, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: "<!doctype html><title>x</title><p>x" }));
  const page = await ctx.newPage(); const errs = [], popups = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  ctx.on("page", pg => popups.push(pg));
  const mock = { sonda: { status: 200, body: { ok: true, verze: 1 } }, post: () => ({ status: 201, body: OK201 }), posts: [], sondy: 0, delay: 0, abort: false };
  await page.route("**/api/admin/konfigurace/nabidka", async route => {
    const req = route.request();
    if (req.method() === "GET") {
      mock.sondy++; const s = mock.sonda;
      if (s.abort) return route.abort("failed");
      return route.fulfill({ status: s.status, contentType: "application/json", body: s.raw != null ? s.raw : JSON.stringify(s.body) });
    }
    if (req.method() === "POST") {
      let body = null; try { body = JSON.parse(req.postData() || "null"); } catch (e) { /* nic */ }
      mock.posts.push({ body, ctype: req.headers()["content-type"] || "" });
      if (mock.delay) await new Promise(r => setTimeout(r, mock.delay));
      if (mock.abort) return route.abort("failed");
      const x = mock.post(body);
      return route.fulfill({ status: x.status, contentType: x.raw != null ? "text/html" : "application/json", body: x.raw != null ? x.raw : JSON.stringify(x.body) });
    }
    return route.fulfill({ status: 405, body: "{}" });
  });
  return { ctx, page, trk, errs, popups, mock };
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
const stavTl = page => page.evaluate(() => { const b = document.getElementById("nabidkaBtn"); return b ? { hidden: b.hidden, disabled: b.disabled, title: b.title, text: b.textContent } : null; });
const ocekavano = page => page.evaluate(() => { const S = window.__pdcState; return { sel: JSON.parse(JSON.stringify(S.sel)), rv: S.last.rules_version || S.schema.rules_version, hash: S.last.hash, kod: S.last.kod }; });
async function otevri(p) { await p.page.click("#nabidkaBtn"); await p.page.waitForSelector(".nab-dlg #nabQty", { timeout: 5000 }); }
async function vyplnit(p, n) {
  n = n || {};
  if (n.qty != null) await p.page.fill("#nabQty", String(n.qty));
  if (n.montaz) await p.page.selectOption("#nabMontaz", n.montaz);
  if (n.pct != null) await p.page.fill("#nabMontazPct", String(n.pct));
  if (n.zeme) await p.page.selectOption("#nabZeme", n.zeme);
  if (n.jmeno != null) await p.page.fill("#nabJmeno", n.jmeno);
  if (n.email != null) await p.page.fill("#nabEmail", n.email);
}
// odesle formular; vrati { novych, post, chyba, popup } (po chybe nebo po zobrazeni vysledku)
async function odeslat(p) {
  const n0 = p.mock.posts.length, np0 = p.popups.length;
  await p.page.click("#nabOdeslat");
  await p.page.waitForSelector("#nabChyba:not([hidden]), #nabZavrit", { timeout: 10000 });
  await p.page.waitForTimeout(150);
  const chyba = await p.page.$eval("#nabChyba", e => (e && !e.hidden ? e.innerText : null)).catch(() => null);
  return { novych: p.mock.posts.length - n0, post: p.mock.posts[p.mock.posts.length - 1], chyba, popup: p.popups.length > np0 ? p.popups[p.popups.length - 1] : null };
}
async function zavriDlg(p) { await p.page.keyboard.press("Escape").catch(() => {}); await p.page.waitForSelector(".nab-overlay", { state: "detached", timeout: 4000 }).catch(() => {}); }
const xss = page => page.evaluate(() => window.__xss);

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  await sec("A sonda: tlacitko se ukaze JEN po 200 {ok:true} (statika jde zive driv nez API)", async () => {
    const pripady = [
      ["404 (backend jeste nebezi)", { status: 404, body: {} }, false], ["401 (nepřihlášený)", { status: 401, body: { error: "unauthorized" } }, false],
      ["403 (bez práva nabidky.vytvorit)", { status: 403, body: { error: "forbidden" } }, false], ["500", { status: 500, body: {} }, false],
      ["200 ale ok:false", { status: 200, body: { ok: false } }, false], ["200 ale ok jako text 'true'", { status: 200, body: { ok: "true" } }, false],
      ["200 s rozbitym JSON", { status: 200, raw: "<html>not json" }, false], ["spojeni selze", { abort: true }, false],
      ["200 {ok:true, verze:1}", { status: 200, body: { ok: true, verze: 1 } }, true]
    ];
    for (const [nazev, sonda, ma] of pripady) {
      const p = await mk(browser); p.mock.sonda = sonda;
      await p.page.goto(`${BASE}${STRANKY[30]}?debug=1`, { waitUntil: "domcontentloaded" });
      await p.page.waitForSelector("#nabidkaBtn", { state: "attached", timeout: 30000 });
      const t0 = Date.now(); while (p.mock.sondy < 1 && Date.now() - t0 < 20000) await p.page.waitForTimeout(100);
      await p.page.waitForTimeout(500);
      const vis = await p.page.locator("#nabidkaBtn").isVisible();
      t(`A ${nazev}: tlacitko ${ma ? "je vidět" : "je skryté"}`, vis === ma, vis);
      if (!ma) t(`A ${nazev}: skryte tlacitko nejde ani zaostrit (display:none), dialog neexistuje`, !(await p.page.evaluate(() => { const b = document.getElementById("nabidkaBtn"); b.focus(); return document.activeElement === b; })) && (await p.page.locator(".nab-overlay").count()) === 0);
      await p.ctx.close();
    }
  });

  await sec("B dialog a pozadavek (stranka systemu 30)", async () => {
    const p = await mk(browser); await load(p, STRANKY[30]);
    await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    const st = await stavTl(p.page);
    t("B1 tlacitko 'Do online nabídky' je vidět a povolené po nacteni konfigurace", st && !st.hidden && !st.disabled && /Do online nabídky/.test(st.text), st);
    t("B1b tlacitko je v okne 'Cena a scéna' (pod 'Vložit do Scény')", await p.page.evaluate(() => { const b = document.getElementById("nabidkaBtn"), s = document.getElementById("sceneBtn"); const w = b && b.closest(".nab-wrap"); return !!w && !!s && w.parentNode === s.parentNode && (s.compareDocumentPosition(w) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0; }));
    if (SHOT) await p.page.locator("#nabidkaBtn").scrollIntoViewIfNeeded().then(() => p.page.screenshot({ path: SHOT + "_okno.png" }));
    const exp = await ocekavano(p.page);

    // ---- otevreni, a11y
    await otevri(p);
    const d = await p.page.evaluate(() => { const b = document.querySelector(".nab-dlg"); return { role: b.getAttribute("role"), modal: b.getAttribute("aria-modal"), lab: b.getAttribute("aria-labelledby"), titul: !!document.getElementById("nabTitle"), focus: document.activeElement && document.activeElement.id, info: document.querySelector(".nab-info").textContent, fs: getComputedStyle(b).fontSize }; });
    t("B2 dialog: role=dialog, aria-modal, nadpis, fokus v poli Mnozstvi", d.role === "dialog" && d.modal === "true" && d.lab === "nabTitle" && d.titul && d.focus === "nabQty", d);
    t("B2b dialog ukazuje kod konfigurace a system", d.info.includes(String(exp.kod)) && /systém 30/.test(d.info), d.info);
    t("B2c pismo v dialogu 16 px (pravidlo o jednotnem pisme)", d.fs === "16px", d.fs);
    if (SHOT) await p.page.screenshot({ path: SHOT + "_dialog.png" });
    // klavesnice: Tab uvnitr dialogu se zacykli, Shift+Tab zpet
    await p.page.focus("#nabZrusit"); await p.page.keyboard.press("Tab");
    t("B3 Tab z posledniho prvku se vrati na prvni (focus trap)", (await p.page.evaluate(() => document.activeElement.id)) === "nabQty");
    await p.page.keyboard.press("Shift+Tab");
    t("B3b Shift+Tab z prvniho prvku jde na posledni", (await p.page.evaluate(() => document.activeElement.id)) === "nabZrusit");
    await p.page.keyboard.press("Escape"); await p.page.waitForSelector(".nab-overlay", { state: "detached", timeout: 3000 }).catch(() => {});
    t("B3c Esc dialog zavre a fokus se vrati na tlacitko", (await p.page.locator(".nab-overlay").count()) === 0 && (await p.page.evaluate(() => document.activeElement.id)) === "nabidkaBtn");
    await otevri(p); await p.page.mouse.click(5, 5); await p.page.waitForTimeout(200);
    t("B3d klik mimo dialog (na tmave pozadi) ho zavre", (await p.page.locator(".nab-overlay").count()) === 0);
    await otevri(p); await p.page.click(".nab-dlg h2"); await p.page.waitForTimeout(150);
    t("B3e klik dovnitr dialogu ho nezavre", (await p.page.locator(".nab-overlay").count()) === 1);
    await p.page.click("#nabZrusit"); await p.page.waitForTimeout(150);
    t("B3f tlacitko Zrusit dialog zavre", (await p.page.locator(".nab-overlay").count()) === 0);
    t("B3g zavreni dialogu nic neodeslalo", p.mock.posts.length === 0, p.mock.posts.length);
    await otevri(p); await p.page.fill("#nabQty", "0"); await p.page.press("#nabQty", "Enter"); await p.page.waitForSelector("#nabChyba:not([hidden])", { timeout: 3000 });
    t("B3h Enter v poli spusti odeslani (neplatne mnozstvi 0 -> hlaska, zadny pozadavek)", /Množství/.test(await p.page.$eval("#nabChyba", e => e.innerText)) && p.mock.posts.length === 0);
    await zavriDlg(p);

    // ---- validace: zadny pozadavek, chyba je vidět, dialog zustane
    const NEPLATNE = [
      ["mnozstvi 0", { qty: 0 }, /Množství/], ["mnozstvi 100 (max je 99)", { qty: 100 }, /Množství.*99/], ["mnozstvi 101", { qty: 101 }, /Množství/], ["mnozstvi 1.5", { qty: "1.5" }, /Množství/], ["mnozstvi 1e2 (zapis s exponentem)", { qty: "1e2" }, /Množství/], ["mnozstvi prazdne", { qty: "" }, /Množství/],
      ["vlastni montaz prazdna", { montaz: "custom", pct: "" }, /Sazba montáže/], ["vlastni montaz text", { montaz: "custom", pct: "abc" }, /Sazba montáže/], ["vlastni montaz 101", { montaz: "custom", pct: "101" }, /Sazba montáže/],
      ["vlastni montaz -1", { montaz: "custom", pct: "-1" }, /Sazba montáže/], ["email bez zavinace", { email: "abc" }, /E-mail/], ["email bez domeny", { email: "jan@firma" }, /E-mail/]
    ];
    await otevri(p);
    for (const [nazev, vstup, re] of NEPLATNE) {
      await p.page.fill("#nabQty", "1"); await p.page.selectOption("#nabMontaz", "default"); await p.page.fill("#nabEmail", "");
      await vyplnit(p, vstup);
      const n0 = p.mock.posts.length; await p.page.click("#nabOdeslat"); await p.page.waitForSelector("#nabChyba:not([hidden])", { timeout: 3000 });
      const ch = await p.page.$eval("#nabChyba", e => e.innerText);
      t(`B4 neplatne: ${nazev} -> chyba v dialogu, zadny pozadavek`, re.test(ch) && p.mock.posts.length === n0 && (await p.page.locator(".nab-dlg").count()) === 1, ch);
    }
    await zavriDlg(p);

    // ---- vychozi odeslani: telo pozadavku
    await otevri(p);
    const popupP = p.ctx.waitForEvent("page", { timeout: 5000 }).catch(() => null);
    const r1 = await odeslat(p), popup = await popupP;
    const b = r1.post && r1.post.body;
    t("B5 odeslano prave jednou na POST s JSON", r1.novych === 1 && /application\/json/.test(r1.post.ctype), r1.post && r1.post.ctype);
    t("B5b product_id = karta generatoru (cislo)", b && b.product_id === Number(PIDS[30]), b && b.product_id);
    t("B5c configuration.selection = presne vyber ze stranky, rules_version a hash sedi", b && JSON.stringify(b.configuration.selection) === JSON.stringify(exp.sel) && b.configuration.rules_version === exp.rv && b.hash === exp.hash, { b, exp: { rv: exp.rv, hash: exp.hash } });
    t("B5d vychozi qty 1, montaz_pct null (= vychozi sazba), zeme CZ, bez zakaznika", b && b.qty === 1 && b.montaz_pct === null && b.delivery_country === "CZ" && !("customer" in b), b);
    t("B5e klient neposila cenu, kod, kusovnik ani nazev (jen povolena pole)", b && Object.keys(b).every(k => ["product_id", "configuration", "qty", "montaz_pct", "delivery_country", "customer", "hash"].includes(k)) && Object.keys(b.configuration).every(k => ["selection", "rules_version"].includes(k)), b && Object.keys(b));
    t("B6 uspech: ukaze cislo nabidky, kod konfigurace a mnozstvi", await p.page.evaluate(() => /Logiman5015/.test(document.querySelector(".nab-ok").textContent) && /S30-TEST/.test(document.querySelector(".nab-ok").textContent)));
    const tab = plain(await p.page.$eval(".nab-tab", e => e.innerText));
    t("B6b ceny: bez DPH 26 180 Kc, DPH 21 % 5 498 Kc, s DPH 31 678 Kc", /Cena bez DPH 26 180 Kč/.test(tab) && /DPH 21 % 5 498 Kč/.test(tab) && /Cena s DPH 31 678 Kč/.test(tab), tab);
    t("B6c montaz zvlast, jako volitelna sluzba mimo cenu (12 %, 3 142 Kc)", /Montáž \(volitelná, mimo cenu\) 12 % 3 142 Kč bez DPH/.test(tab), tab);
    const scenaQ = await p.page.evaluate(() => StulDoSceny.dotaz());
    const SCENA = BASE + "/scene.html?stul=" + encodeURIComponent(scenaQ) + "&nabidka_vykresy=123";
    const odk = await p.page.evaluate(() => ({ s: (document.getElementById("nabScena") || {}).href, o: (document.getElementById("nabOnline") || {}).href, a: (document.getElementById("nabAdmin") || {}).href, rel: (document.getElementById("nabOnline") || {}).rel, tg: (document.getElementById("nabOnline") || {}).target }));
    t("B6d odkazy: na zakaznickou stranku (relativni online_url -> absolutni na teto domene) a na seznam Online nabidky v adminu; novy panel, noopener", odk.o === ONLINE && odk.a === ADMIN_LIST && /noopener/.test(odk.rel) && odk.tg === "_blank", odk);
    t("B6h odkaz 'Vykresy ve Scene' = /scene.html?stul=<query jako u Vlozit do Sceny>&nabidka_vykresy=<id nabidky> a poznamka, ze se vykresy dokoncuji ve Scene (nova zalozka)", odk.s === SCENA && /^\d+$/.test(new URL(odk.s).searchParams.get("nabidka_vykresy")) && new URL(odk.s).searchParams.get("stul") === scenaQ && /dokončují ve Scéně \(nová záložka\)/.test(await p.page.$eval("#nabVykresyInfo", e => e.textContent)), { odk, scenaQ });
    t("B6e radek 'Posledni nabidka' pod tlacitkem ma oba odkazy i po zavreni dialogu", await (async () => { await p.page.click("#nabZavrit"); await p.page.waitForTimeout(150); return p.page.evaluate(() => { const s = document.getElementById("nabidkaStav"); return /Logiman5015/.test(s.textContent) && s.querySelectorAll("a[href]").length === 3 && !document.querySelector(".nab-overlay"); }); })());
    t("B7 nova zalozka (otevrena pri kliknuti) nacetla SCENU s vykresy pro tuto nabidku", !!popup && await popup.waitForURL(SCENA, { timeout: 8000 }).then(() => true, () => false), popup && popup.url());
    t("B7b nova zalozka nema pristup k oknu generatoru (opener = null)", !!popup && (await popup.evaluate(() => window.opener === null).catch(() => false)));
    if (popup) await popup.close().catch(() => {});

    // ---- mapovani poli
    const MAPA = [
      ["mnozstvi 3, montaz 'bez montaze' -> montaz_pct 0", { qty: 3, montaz: "none" }, b => b.qty === 3 && b.montaz_pct === 0],
      ["vlastni sazba '15,5' -> 15.5", { montaz: "custom", pct: "15,5" }, b => b.montaz_pct === 15.5],
      ["vlastni sazba 0 -> 0 (montaz se nenabizi)", { montaz: "custom", pct: "0" }, b => b.montaz_pct === 0],
      ["vlastni sazba 100 -> 100", { montaz: "custom", pct: "100" }, b => b.montaz_pct === 100],
      ["zeme PL", { zeme: "PL" }, b => b.delivery_country === "PL"],
      ["zakaznik jmeno + e-mail", { jmeno: "Jan Novák", email: "jan@firma.cz" }, b => b.customer && b.customer.name === "Jan Novák" && b.customer.email === "jan@firma.cz"],
      ["jen jmeno (bez e-mailu)", { jmeno: "Firma s.r.o." }, b => b.customer && b.customer.name === "Firma s.r.o." && !("email" in b.customer)],
      ["mnozstvi 99 (horni mez)", { qty: 99 }, b => b.qty === 99]
    ];
    for (const [nazev, vstup, over] of MAPA) {
      await otevri(p); await vyplnit(p, vstup);
      const pp = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null);
      const r = await odeslat(p); const pop = await pp; if (pop) await pop.close().catch(() => {});
      t(`B8 pole: ${nazev}`, r.novych === 1 && over(r.post.body), r.post && r.post.body);
      await zavriDlg(p);
    }

    // ---- zahranici: montaz se nenabizi (server vynuti 0) -> pole montaze zakazane, montaz_pct = null; po navratu do CZ se povoli
    await otevri(p); await vyplnit(p, { montaz: "custom", pct: "15" });
    await p.page.selectOption("#nabZeme", "PL");
    const zz = await p.page.evaluate(() => ({ m: document.getElementById("nabMontaz").disabled, pct: document.getElementById("nabMontazPct").disabled, note: !document.getElementById("nabMontazNote").hidden }));
    t("B8b zeme PL: volba montaze i sazba jsou zakazane a ukaze se 'Do zahraničí se montáž nenabízí'", zz.m && zz.pct && zz.note, zz);
    { const pp = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); const r = await odeslat(p); const pop = await pp; if (pop) await pop.close().catch(() => {});
      t("B8c zeme PL + driv zadana vlastni sazba 15: posila se montaz_pct null (ne 15) a zeme PL", r.novych === 1 && r.post.body.montaz_pct === null && r.post.body.delivery_country === "PL", r.post && r.post.body); }
    await zavriDlg(p);
    await otevri(p); await vyplnit(p, { montaz: "custom", pct: "15", zeme: "SK" }); await p.page.selectOption("#nabZeme", "CZ");
    const zc = await p.page.evaluate(() => ({ m: document.getElementById("nabMontaz").disabled, pct: document.getElementById("nabMontazPct").disabled, note: !document.getElementById("nabMontazNote").hidden, v: document.getElementById("nabMontazPct").value }));
    t("B8d navrat na CZ: montaz se zase povoli, vlastni sazba zustala (15)", !zc.m && !zc.pct && !zc.note && zc.v === "15", zc);
    await zavriDlg(p);

    // ---- vysledek: vice kusu (ceny za qty kusu + cena za 1 ks) a nabidka bez 3D s duvodem
    p.mock.post = () => ({ status: 201, body: Object.assign({}, OK201, { line: Object.assign({}, OK201.line, { qty: 3, total_net_czk: 78540 }), price: { net_czk: 78540, vat_rate: 21, vat_czk: 16493, gross_czk: 95033 }, montaz: null, v3d: false, v3d_duvod: "model se nepodařilo postavit <b>x</b>" }) });
    await otevri(p); await vyplnit(p, { qty: 3 });
    { const pp = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); await odeslat(p); const pop = await pp; if (pop) await pop.close().catch(() => {}); }
    const t3 = plain(await p.page.$eval(".nab-tab", e => e.innerText)), b3 = await p.page.evaluate(() => ({ ok: document.querySelector(".nab-ok").textContent, bez3d: (document.getElementById("nabBez3d") || {}).textContent, bold: document.querySelectorAll("#nabBez3d b").length }));
    t("B6f vice kusu: radek 'Cena za 1 ks bez DPH 26 180 Kč' a 'Cena bez DPH (3 ks) 78 540 Kč', bez radku montaze (montaz: null)", /Cena za 1 ks bez DPH 26 180 Kč/.test(t3) && /Cena bez DPH \(3 ks\) 78 540 Kč/.test(t3) && /Cena s DPH 95 033 Kč/.test(t3) && !/Montáž/.test(t3) && /· 3 ks/.test(b3.ok), { t3, b3 });
    t("B6g v3d:false: ukaze se, ze nabidka vznikla bez 3D, i duvod (jen text, zadne HTML)", /bez interaktivního 3D/.test(b3.bez3d) && /Důvod: model se nepodařilo postavit <b>x<\/b>/.test(b3.bez3d) && b3.bold === 0, b3);
    await zavriDlg(p); p.mock.post = () => ({ status: 201, body: OK201 });

    // ---- bezpecnost odkazu (jen http(s) na nase domeny) a text bez HTML
    const ODKAZY = [
      ["javascript:", "javascript:window.__xss=4", false], ["data:", "data:text/html,<script>window.__xss=5</script>", false], ["cizi domena", "https://evil.example/nabidka", false],
      ["logiman.cz.evil.com", "https://logiman.cz.evil.com/x", false], ["notlogiman.cz", "https://notlogiman.cz/x", false], ["protokol-relativni cizi", "//evil.example/x", false],
      ["autovestavby.logiman.cz", "https://autovestavby.logiman.cz/x", true], ["www.logiman.cz", "https://www.logiman.cz/x", true], ["baliace-stoly.top", "https://baliace-stoly.top/x", true],
      ["www.packing-tables.top", "https://www.packing-tables.top/x", true], ["relativni (stejna domena)", "/nabidka-online.html?token=a", true]
    ];
    for (const [nazev, url, ok] of ODKAZY) {
      p.mock.post = () => ({ status: 201, body: Object.assign({}, OK201, { online_url: url, admin_url: url, offer_number: "<img src=x onerror=window.__xss=3>" }) });
      await otevri(p); const pp = p.ctx.waitForEvent("page", { timeout: 2500 }).catch(() => null);
      await odeslat(p); const pop = await pp; if (pop) await pop.close().catch(() => {});
      const q = await p.page.evaluate(() => ({ a: [...document.querySelectorAll(".nab-dlg a")].map(x => x.getAttribute("href")), img: document.querySelectorAll(".nab-dlg img").length, txt: document.querySelector(".nab-ok").textContent }));
      t(`B9 odkaz ${nazev}: online_url ${ok ? "povolen (+ staticky odkaz na admin)" : "zahozen (zbyde jen staticky odkaz na admin, admin_url ze serveru se ignoruje)"}`, (ok ? q.a.length === 3 : q.a.length === 2) && q.a.filter(h => /\/admin\.html#onlineoffers$/.test(h)).length === 1 && !q.a.some(h => /evil|^javascript|^data:/.test(h)), q);
      t(`B9 ${nazev}: cislo nabidky s HTML je jen text, zadny <img>, zadny skript`, q.img === 0 && q.txt.includes("<img") && (await xss(p.page)) === undefined);
      await zavriDlg(p);
    }
    p.mock.post = () => ({ status: 201, body: OK201 });

    // ---- chyby serveru
    const CHYBY = [
      ["409 rules_changed", { status: 409, body: { error: "rules_changed", message: "x" } }, /Pravidla generátoru se mezitím změnila/, true],
      ["409 configuration_changed", { status: 409, body: { error: "configuration_changed" } }, /Konfigurace se mezitím změnila/, true],
      ["409 price_on_request", { status: 409, body: { error: "price_on_request" } }, /Cena téhle konfigurace není k dispozici/, false],
      ["403 forbidden", { status: 403, body: { error: "forbidden", message: "x" } }, /nemáš oprávnění/, false],
      ["404 not_configurable", { status: 404, body: { error: "not_configurable" } }, /není konfigurovatelný stůl/, false],
      ["400 invalid_selection + zprava", { status: 400, body: { error: "invalid_selection", message: "qty musi byt 1-100" } }, /Neplatná data.*qty musi byt 1-100/, false],
      ["429 rate_limited", { status: 429, body: { error: "rate_limited" } }, /Limit 30 nabídek za hodinu/, false],
      ["401 bez kodu", { status: 401, body: {} }, /Nejsi přihlášený/, false],
      ["500 HTML", { status: 500, raw: "<html>boom</html>" }, /Nabídku se nepodařilo vytvořit/, false],
      ["502 JSON s neznamym kodem", { status: 502, body: { error: "upstream", message: "backend nebezi" } }, /Nabídku se nepodařilo vytvořit.*backend nebezi/, false]
    ];
    for (const [nazev, odp, re, refresh] of CHYBY) {
      p.mock.post = () => odp; const r0 = p.trk.resolve;
      await otevri(p); const pp = p.ctx.waitForEvent("page", { timeout: 2500 }).catch(() => null);
      const r = await odeslat(p); const pop = await pp;
      t(`B10 ${nazev}: hlaska v dialogu, dialog zustane, tlacitka znovu povolena`, !!r.chyba && re.test(plain(r.chyba)) && await p.page.evaluate(() => !document.getElementById("nabOdeslat").disabled && !document.getElementById("nabZrusit").disabled && document.getElementById("nabOdeslat").textContent === "Vytvořit nabídku"), r.chyba);
      t(`B10 ${nazev}: nova zalozka, otevrena pri odeslani, se po chybe zavrela`, !pop || pop.isClosed() || await pop.waitForEvent("close", { timeout: 3000 }).then(() => true, () => pop.isClosed()));
      if (refresh) { await p.page.waitForTimeout(1500); t(`B10 ${nazev}: konfigurace se nacetla znovu (resolve po chybe)`, p.trk.resolve > r0, { r0, ted: p.trk.resolve }); await idle(p, 800); }
      await zavriDlg(p);
    }
    p.mock.post = () => ({ status: 422, body: { error: "invalid_configuration", errors: [{ slot: "<img src=x onerror=window.__xss=1>", message: "<script>window.__xss=2</script>nelze vyrobit" }, { slot: "w", message: "moc siroke" }] } });
    await otevri(p); const rv = await odeslat(p);
    t("B11 422 invalid_configuration: seznam chyb po slotech", /Tuhle konfiguraci nejde vyrobit/.test(rv.chyba) && /w: moc siroke/.test(rv.chyba), rv.chyba);
    t("B11b chyby od serveru jsou jen text (zadny <img>/<script>, nic se nespustilo)", (await p.page.locator("#nabChyba img, #nabChyba script").count()) === 0 && /<img src=x/.test(rv.chyba) && (await xss(p.page)) === undefined);
    await zavriDlg(p);
    p.mock.post = () => ({ status: 201, body: OK201 });
    p.mock.abort = true; await otevri(p); const rn = await odeslat(p); p.mock.abort = false;
    t("B12 vypadek spojeni: hlaska 'Spojení selhalo', dialog zustane, tlacitka povolena", /Spojení selhalo/.test(rn.chyba) && await p.page.evaluate(() => !document.getElementById("nabOdeslat").disabled), rn.chyba);
    await zavriDlg(p);

    // ---- dvojklik a zpracovani (busy)
    p.mock.delay = 1200; const n0 = p.mock.posts.length; await otevri(p);
    const pp = p.ctx.waitForEvent("page", { timeout: 6000 }).catch(() => null);
    await p.page.click("#nabOdeslat"); await p.page.click("#nabOdeslat", { force: true }).catch(() => {}); await p.page.keyboard.press("Enter").catch(() => {});
    await p.page.waitForTimeout(300);
    const busy = await p.page.evaluate(() => ({ o: document.getElementById("nabOdeslat").disabled, z: document.getElementById("nabZrusit").disabled, tx: document.getElementById("nabOdeslat").textContent }));
    await p.page.keyboard.press("Escape"); await p.page.mouse.click(5, 5); await p.page.waitForTimeout(200);
    t("B13 behem odesilani: tlacitka zakazana ('Vytvářím…'), Esc ani klik mimo dialog nezavrou", busy.o && busy.z && /Vytvářím/.test(busy.tx) && (await p.page.locator(".nab-overlay").count()) === 1, busy);
    await p.page.waitForSelector("#nabZavrit", { timeout: 6000 }); const pop = await pp; if (pop) await pop.close().catch(() => {});
    t("B13b dvojklik/Enter poslal jen JEDNU nabidku", p.mock.posts.length - n0 === 1, p.mock.posts.length - n0);
    p.mock.delay = 0; await zavriDlg(p);
    t("B14 zadne chyby JS ve strance behem celeho testu", p.errs.length === 0, p.errs.slice(0, 4));
    await p.ctx.close();
  });

  await sec("C vsechny ctyri generatory (30 / 35 / 40 / 41): spravna karta, aktualni vyber, stav tlacitka", async () => {
    for (const sys of [30, 35, 40, 41]) {
      if (!PIDS[sys]) { console.log(`PRESKOCENO systém ${sys}: chybí env ${sys === 30 ? "PID" : "PID" + sys} (fiktivní karta mostu)`); continue; }
      const p = await mk(browser); await load(p, STRANKY[sys]);
      await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
      t(`C${sys}a tlacitko je vidět a povolené`, true);
      const vyber = async () => { const e = await ocekavano(p.page); return e; };
      let exp = await vyber();
      await otevri(p); const info = await p.page.$eval(".nab-info", e => e.textContent);
      const pp = p.ctx.waitForEvent("page", { timeout: 5000 }).catch(() => null);
      const r = await odeslat(p), pop = await pp; if (pop) await pop.close().catch(() => {});
      const b = r.post && r.post.body;
      t(`C${sys}b POST ma kartu generatoru ${PIDS[sys]} a presne aktualni vyber, rules_version, hash`, b && b.product_id === Number(PIDS[sys]) && JSON.stringify(b.configuration.selection) === JSON.stringify(exp.sel) && b.configuration.rules_version === exp.rv && b.hash === exp.hash, { b: b && { product_id: b.product_id, hash: b.hash }, exp: { hash: exp.hash } });
      t(`C${sys}c dialog uvadi system ${sys}`, new RegExp("systém " + sys).test(info), info);
      await zavriDlg(p);
      // zmena vyberu: sirka o 100 mm jinak (nahoru, kdyz je na horni mezi dolu) -> dalsi nabidka nese NOVY vyber
      if (await p.page.locator(".pdc-slot[data-slot=w] .pdc-num").count()) {
        const w0 = exp.sel.w;
        for (const w of [Number(w0) + 100, Number(w0) - 100]) {
          await p.page.locator(".pdc-slot[data-slot=w] .pdc-num").fill(String(w)); await p.page.keyboard.press("Tab"); await idle(p, 1500);
          exp = await vyber(); if (String(exp.sel.w) !== String(w0)) break;
        }
        t(`C${sys}d sirka se zmenila (${w0} -> ${exp.sel.w}), tlacitko je po prepoctu zase povolene`, String(exp.sel.w) !== String(w0) && !(await stavTl(p.page)).disabled, { w0, w: exp.sel.w });
        await otevri(p); const pp2 = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); const r2 = await odeslat(p), pop2 = await pp2; if (pop2) await pop2.close().catch(() => {});
        const b2 = r2.post && r2.post.body;
        t(`C${sys}e dalsi nabidka nese NOVY vyber (sirka ${exp.sel.w}) a novy hash`, b2 && String(b2.configuration.selection.w) === String(exp.sel.w) && b2.hash === exp.hash && b2.hash !== (b && b.hash), { w: b2 && b2.configuration.selection.w, exp: exp.sel.w });
        await zavriDlg(p);
      } else console.log(`(systém ${sys}: slot w v panelu není, změna šířky přeskočena)`);
      t(`C${sys}f zadne chyby JS ve strance`, p.errs.length === 0, p.errs.slice(0, 3));
      await p.ctx.close();
    }
    // stav tlacitka pri prepoctu a pri neplatne konfiguraci (system 30)
    const p = await mk(browser); await load(p, STRANKY[30]);
    await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    let rezim = "pomalu";
    await p.page.route(RES_RE, async route => {
      if (rezim === "pomalu") { await new Promise(r => setTimeout(r, 2500)); return route.continue(); }
      if (rezim === "neplatne") { const resp = await route.fetch(); let j = {}; try { j = await resp.json(); } catch (e) { return route.fulfill({ response: resp }); } j.valid = false; j.errors = [{ message: "Zkušební neplatná konfigurace." }]; return route.fulfill({ response: resp, json: j }); }
      return route.continue();
    });
    const w0 = Number((await ocekavano(p.page)).sel.w);
    await p.page.locator(".pdc-slot[data-slot=w] .pdc-num").fill(String(w0 + 100)); await p.page.keyboard.press("Tab"); await p.page.waitForTimeout(900);
    const pocita = await stavTl(p.page);
    t("C-s1 behem prepoctu (resolve jeste bezi) je tlacitko zakazane", pocita.disabled, pocita);
    await idle(p, 1200);
    t("C-s2 po prepoctu je zase povolene", !(await stavTl(p.page)).disabled);
    rezim = "neplatne";
    await p.page.locator(".pdc-slot[data-slot=w] .pdc-num").fill(String(w0)); await p.page.keyboard.press("Tab"); await idle(p, 1500);
    const nepl = await stavTl(p.page);
    t("C-s3 neplatna konfigurace: tlacitko zakazane s vysvetlenim, dialog nejde otevrit", nepl.disabled && /není platná/.test(nepl.title) && await (async () => { await p.page.click("#nabidkaBtn", { force: true }).catch(() => {}); await p.page.waitForTimeout(200); return (await p.page.locator(".nab-overlay").count()) === 0; })(), nepl);
    rezim = "ok";
    await p.ctx.close();
  });

  await sec("E Scena s vykresy: odkaz po vytvoreni nabidky, blokator oken, neplatne id, stul SSE, bezpecne sestaveni adresy", async () => {
    // E1 blokator oken: okno se neotevre -> odkaz na Scenu v dialogu + varovani
    let p = await mk(browser, { blokovatOkno: true }); await load(p, STRANKY[30]);
    await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    await otevri(p); await odeslat(p);
    const e1 = await p.page.evaluate(() => ({ s: (document.getElementById("nabScena") || {}).href, info: (document.getElementById("nabVykresyInfo") || {}).textContent }));
    t("E1 blokator oken: ukaze se odkaz 'Vykresy ve Scene' a varovani, ze zustane nabidka bez vykresu", /scene\.html\?stul=.+&nabidka_vykresy=123$/.test(e1.s || "") && /zablokoval nové okno/.test(e1.info || ""), e1);
    t("E1b zadna nova zalozka se neotevrela", p.popups.length === 0, p.popups.length);
    await p.ctx.close();
    // E2 neplatne id nabidky v odpovedi: zadna Scena, popup jde na stranku nabidky, poznamka
    for (const [nazev, idn] of [["text", "abc"], ["chybi", null], ["pridany retezec", "12;DROP"]]) {
      p = await mk(browser); await load(p, STRANKY[30]);
      await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
      p.mock.post = () => ({ status: 201, body: Object.assign({}, OK201, { offer_id: idn }) });
      await otevri(p); const pp = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); await odeslat(p); const pop = await pp;
      const e2 = await p.page.evaluate(() => ({ s: !!document.getElementById("nabScena"), info: (document.getElementById("nabVykresyInfo") || {}).textContent }));
      t(`E2 id nabidky '${nazev}': bez odkazu na Scenu, poznamka o chybejicich vykresech, popup jde na stranku nabidky`, !e2.s && /nepodařilo připravit/.test(e2.info || "") && !!pop && await pop.waitForURL(ONLINE, { timeout: 6000 }).then(() => true, () => false), { e2, url: pop && pop.url() });
      await p.ctx.close();
    }
    // E3 stul SSE (system 41) se do Sceny nevklada: popup na stranku nabidky, poznamka o SSE
    if (PIDS[41]) {
      p = await mk(browser); await load(p, STRANKY[41]);
      await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
      await otevri(p); const pp = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); await odeslat(p); const pop = await pp;
      const e3 = await p.page.evaluate(() => ({ s: !!document.getElementById("nabScena"), info: (document.getElementById("nabVykresyInfo") || {}).textContent }));
      t("E3 stul SSE: bez odkazu na Scenu, poznamka o SSE, popup jde na stranku nabidky", !e3.s && /stůl SSE/.test(e3.info || "") && !!pop && await pop.waitForURL(ONLINE, { timeout: 6000 }).then(() => true, () => false), { e3, url: pop && pop.url() });
      await p.ctx.close();
    } else console.log("PRESKOCENO E3: chybi env PID41");
    // E4 query se do adresy vklada zakodovane (zadne HTML/JS z query do href ani do stranky)
    p = await mk(browser); await load(p, STRANKY[30]);
    await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    const zle = 'a=1&b="x"<img src=x onerror=window.__xss=1>#frag';
    await p.page.evaluate(q => { window.StulDoSceny.dotaz = () => q; }, zle);
    await otevri(p); const pp4 = p.ctx.waitForEvent("page", { timeout: 4000 }).catch(() => null); await odeslat(p); const pop4 = await pp4;
    const e4 = await p.page.evaluate(() => ({ h: document.getElementById("nabScena").getAttribute("href"), img: document.querySelectorAll(".nab-dlg img").length, xss: window.__xss }));
    const u4 = new URL(e4.h, BASE);
    t("E4 query s uvozovkami, < > a # je v adrese jen zakodovana: stul se vrati beze zmeny, id nabidky je 123, zadne <img>, nic se nespustilo", u4.searchParams.get("stul") === zle && u4.searchParams.get("nabidka_vykresy") === "123" && u4.hash === "" && e4.img === 0 && e4.xss === undefined, e4);
    if (pop4) await pop4.close().catch(() => {});
    await p.ctx.close();
  });

  await sec("D telefon 390 px a staticke kontroly", async () => {
    const p = await mk(browser, { w: 390, h: 800 }); await load(p, STRANKY[30]);
    await p.page.waitForFunction(() => { const b = document.getElementById("nabidkaBtn"); return b && !b.hidden && !b.disabled; }, null, { timeout: 30000 });
    await p.page.locator("#nabidkaBtn").scrollIntoViewIfNeeded(); await otevri(p);
    const g = await p.page.evaluate(() => { const d = document.querySelector(".nab-dlg").getBoundingClientRect(); const bt = document.getElementById("nabOdeslat").getBoundingClientRect(); const inp = document.getElementById("nabQty").getBoundingClientRect();
      return { l: d.left, r: d.right, t: d.top, b: d.bottom, iw: innerWidth, ih: innerHeight, btnH: bt.height, inpH: inp.height, scrollX: document.documentElement.scrollWidth, cols: getComputedStyle(document.querySelector(".nab-cols")).gridTemplateColumns.split(" ").length }; });
    t("D1 mobil: dialog se vejde na sirku obrazovky (bez vodorovneho posuvu), jeden sloupec poli", g.l >= 0 && g.r <= g.iw && g.b <= g.ih && g.cols === 1, g);
    t("D1b mobil: tlacitka a pole maji aspon 44 px", g.btnH >= 44 && g.inpH >= 44, g);
    if (SHOT) await p.page.screenshot({ path: SHOT + "_mobil.png" });
    await p.page.locator("#nabOdeslat").scrollIntoViewIfNeeded(); await odeslat(p);
    if (SHOT) await p.page.screenshot({ path: SHOT + "_mobil_hotovo.png" });
    const g2 = await p.page.evaluate(() => { const d = document.querySelector(".nab-dlg").getBoundingClientRect(); return { l: d.left, r: d.right, iw: innerWidth, ov: document.querySelector(".nab-dlg").scrollWidth > document.querySelector(".nab-dlg").clientWidth }; });
    t("D1c mobil: i vysledek se vejde (bez vodorovneho posuvu v dialogu)", g2.l >= 0 && g2.r <= g2.iw && !g2.ov, g2);
    await p.ctx.close();
    // staticke: piny ?v= v HTML sedi na obsah modulu, modul se nacita pred stul-host.js, v modulu neni innerHTML
    const crypto = require("crypto"), mod = fs.readFileSync(WEB + "/js/stul-nabidka.js");
    const pin = crypto.createHash("md5").update(mod).digest("hex").slice(0, 10);
    for (const sys of [30, 35, 40, 41]) {
      const h = fs.readFileSync(WEB + STRANKY[sys], "utf8"), m = /<script src="\/js\/stul-nabidka\.js\?v=([0-9a-f]{10})"><\/script>/.exec(h);
      t(`D2 stranka systemu ${sys}: modul stul-nabidka.js je nacten s aktualnim pinem ?v=`, !!m && m[1] === pin, m && m[1] + " vs " + pin);
      t(`D2b stranka systemu ${sys}: modul se nacita PRED stul-host.js`, h.indexOf("/js/stul-nabidka.js") > 0 && h.indexOf("/js/stul-nabidka.js") < h.indexOf("/js/stul-host.js"));
    }
    const zdroj = mod.toString("utf8");
    t("D3 modul nepouziva innerHTML / insertAdjacentHTML / document.write / eval / new Function", !/innerHTML|insertAdjacentHTML|document\.write\(|\beval\(|new Function/.test(zdroj));
    t("D3b modul se na mini-shop ani do vlozeneho generatoru (zakaznicke stranky) nenacita", ["/embed/stul.html", "/embed/stul-embed.js", "/miniweb/miniweb-pages.js", "/js/pdc-layout.js", "/js/product-configurator.js"].every(f => { try { return !/stul-nabidka|StulNabidka/.test(fs.readFileSync(WEB + f, "utf8")); } catch (e) { return true; } }));
  });

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})();
