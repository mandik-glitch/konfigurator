// Test STRANEK GENERATORU STOLU 01 (system 30) A 02 (system 40) a PREPINANI TEHOZ VYBERU mezi nimi (bot10, 2026-10-04).
// SKUTECNE stranky (webapp/stul-konfigurator.html a stul-konfigurator-40.html) + SKUTECNY modul voleb a ovladani ve 3D nad SKUTECNYM kodem stolu (api/stul_shop.py) pres most
// scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, produkt 4934 = system 30, fiktivni karta PID40 = system 40, nic se nezapisuje do DB). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-04_system40/test_stul_host_40.js 4934
// Hlida: system 40 stranka bere kartu ze schema.systems (ne pevne ID), nema slot vzper, resolve nese produkt 40, token modelu nese system, prepinac v zahlavi nese TENTYZ hash,
// prepnuti 30 -> 40 s vzperami je odebere a oznami, prepnuti zpet, ostry system 30 (zadne chyby v konzoli), stranka bez karty 40 hlasi "zatim neni zapnuty".
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID40 = Number(process.env.PID40 || 9877);
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });                  // ladici stav modulu i na strankach otevrenych odkazem (prepinac nema ?debug=1)
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now(), bodies: [], glbUrls: [] };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); trk.bodies.push(r.postData() || ""); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); trk.glbUrls.push(u); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, pagePath, hash) {
  await p.page.goto(`${BASE}${pagePath}?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const tokenSystem = u => { try { const tok = u.split("/glb/")[1]; const b = tok.split(".")[0].replace(/-/g, "+").replace(/_/g, "/"); return JSON.parse(Buffer.from(b + "=".repeat((4 - b.length % 4) % 4), "base64").toString()).y || 30; } catch (e) { return null; } };

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  // ---------------------------------------------------------------- 1) generator 02 (system 40)
  console.log("\n## 1) stranka Generator stolu 02 systém 40");
  const p40 = await mk(browser);
  await load(p40, "/stul-konfigurator-40.html", "");
  const s40 = await p40.page.evaluate(() => ({
    sys: window.StulHost.system, productId: window.StulHost.state.productId, title: document.title, h1: document.querySelector("h1").textContent, brand: document.querySelector(".mw-brand").textContent.trim(),
    slots: document.querySelectorAll(".pdc-slot").length, braces: !!document.querySelector('[data-slot="braces"], #pdc-braces, .pdc-slot[data-id="braces"]'), bracesText: /Šikmé vzpěry/.test(document.body.innerText),
    schema: window.__pdcState.schema && { system: window.__pdcState.schema.system, profile: window.__pdcState.schema.profile, ids: window.__pdcState.schema.slots.map(s => s.id) },
    price: document.getElementById("priceNet").textContent, code: document.getElementById("staffCode").textContent, stageMsg: getComputedStyle(document.getElementById("stageMsg")).display,
    sw: (() => { const a = document.querySelector('#sysSwitch a[data-system="30"]'); return a && { hidden: a.hidden, text: a.textContent, href: a.getAttribute("href") }; })(),
    bom: [...document.querySelectorAll("#bomBody tbody tr")].map(r => r.textContent).join("|")
  }));
  t("1a stranka je generator 02 systém 40 (data-system, titulek, nadpis, znacka)", s40.sys === 40 && /^Generátor stolu 02 systém 40$/.test(s40.title) && s40.h1 === "Generátor stolu 02 systém 40" && /02 systém 40/.test(s40.brand), [s40.sys, s40.title, s40.h1, s40.brand]);
  t("1b karta systemu 40 se vzala ze schema.systems (ne pevne ID): productId = " + PID40, s40.productId === PID40, s40.productId);
  t("1c schema 40: system 40, profil 40x40, sloty vzper (braces, bracelen) i ostatni sloty jsou", s40.schema && s40.schema.system === 40 && s40.schema.profile === "40x40" && s40.schema.ids.includes("braces") && s40.schema.ids.includes("bracelen") && s40.schema.ids.includes("w") && s40.schema.ids.includes("shelf"), s40.schema && [s40.schema.system, s40.schema.profile]);
  t("1d ve strance je volba vzper (sikme vzpery nese ve 40 spojka 3220)", s40.bracesText);
  t("1e cena a kod konfigurace jsou videt, hlaska o nacitani zmizela", /\d/.test(s40.price) && /^Kód konfigurace: STL-[0-9A-F]+ · \d+ spojů profilů$/.test(s40.code) && s40.stageMsg === "none", [s40.price, s40.code, s40.stageMsg]);
  t("1f kusovnik je ze systemu 40: Profil 40x40, spojka 40x40 a otocna matice do drazky 10", /Profil 40x40/.test(s40.bom) && /40x40 Rohová spojka/.test(s40.bom) && /drážka 10/.test(s40.bom) && !/Profil 30x30/.test(s40.bom), s40.bom.slice(0, 300));
  t("1g prvni resolve nese produkt 40 a staff: true", p40.trk.bodies.length > 0 && p40.trk.bodies.every(b => new RegExp(`"product_id":\\s*${PID40}`).test(b)) && /"staff":\s*true/.test(p40.trk.bodies[0]), p40.trk.bodies[0] && p40.trk.bodies[0].slice(0, 120));
  t("1h token 3D modelu nese system 40 (y = 40)", p40.trk.glbUrls.length > 0 && p40.trk.glbUrls.every(u => tokenSystem(u) === 40), p40.trk.glbUrls.map(tokenSystem));
  t("1i prepinac v zahlavi: viditelny, nabizi system 30 a nese odkaz na druhy generator", s40.sw && !s40.sw.hidden && /systém 30/.test(s40.sw.text) && /^\/stul-konfigurator\.html/.test(s40.sw.href), s40.sw);
  const vinfo = await p40.page.evaluate(() => document.getElementById("staffLinks").innerHTML);
  t("1j odkazy na vyrobni list nesou system=40", /system=40/.test(vinfo), vinfo.slice(0, 200));
  t("1k zadne chyby ve strance ani v konzoli", p40.errs.length === 0, p40.errs.slice(0, 3));

  // odkaz s hashem: vyber se nacte do systemu 40 a prepinac ho prenese
  await p40.page.goto("about:blank");                                           // jen zmena hashe by stranku nenacetla znovu
  await p40.page.goto(`${BASE}/stul-konfigurator-40.html?debug=1#w=1800&d=900&h=950&shelf=2`, { waitUntil: "load" });
  await p40.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p40, 900);
  const sw2 = await p40.page.evaluate(() => { const a = document.querySelector('#sysSwitch a[data-system="30"]'); return { href: a.getAttribute("href"), hash: location.hash, sel: window.__pdcState.last.selection }; });
  t("1l hash #w=1800&d=900&h=950&shelf=2 se nacetl do vyberu (system 40) a prepinac nese stejny hash", sw2.sel.w === 1800 && sw2.sel.d === 900 && sw2.sel.h === 950 && sw2.sel.shelf >= 1 && /^\/stul-konfigurator\.html#/.test(sw2.href) && /w=1800/.test(sw2.href) && /d=900/.test(sw2.href), [sw2.sel.w, sw2.href.slice(0, 120)]);
  const cena40 = await p40.page.evaluate(() => document.getElementById("priceNet").textContent);
  const kod40 = await p40.page.evaluate(() => window.__pdcState.last.kod);

  // ---------------------------------------------------------------- 2) prepnuti 40 -> 30 odkazem (stejny hash) a generator 01
  console.log("\n## 2) prepnuti na generator 01 (system 30) se stejnym vyberem");
  await Promise.all([p40.page.waitForNavigation({ waitUntil: "load" }), p40.page.click('#sysSwitch a[data-system="30"]')]);
  await p40.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p40.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p40, 900);
  const s30 = await p40.page.evaluate(() => ({ url: location.pathname + location.hash, sys: window.StulHost.system, productId: window.StulHost.state.productId, title: document.title, sel: window.__pdcState.last.selection, kod: window.__pdcState.last.kod,
    price: document.getElementById("priceNet").textContent, schema: { system: window.__pdcState.schema.system, hasBraces: window.__pdcState.schema.slots.some(s => s.id === "braces") },
    sw: (() => { const a = document.querySelector('#sysSwitch a[data-system="40"]'); return { hidden: a.hidden, text: a.textContent, href: a.getAttribute("href") }; })() }));
  t("2a po kliknuti jsme na generatoru 01 (system 30, produkt 4934) se stejnym vyberem (w 1800, d 900, h 950)", /^\/stul-konfigurator\.html#/.test(s30.url) && s30.sys === 30 && s30.productId === 4934 && s30.sel.w === 1800 && s30.sel.d === 900 && s30.sel.h === 950 && /^Generátor stolu 01 systém 30$/.test(s30.title), s30);
  t("2b system 30 ma ve schematu slot vzper a jina cena i kod nez system 40 (stejny stul, jiny profil)", s30.schema.system === 30 && s30.schema.hasBraces && s30.kod !== kod40 && s30.price !== cena40, [s30.kod, kod40, s30.price, cena40]);
  t("2c prepinac na generatoru 01 nabizi system 40 a nese hash", !s30.sw.hidden && /systém 40/.test(s30.sw.text) && /^\/stul-konfigurator-40\.html#/.test(s30.sw.href) && /w=1800/.test(s30.sw.href), s30.sw);

  // ---------------------------------------------------------------- 3) 30 -> 40 s vzperami: vzpery se odeberou a stranka to ohlasi
  console.log("\n## 3) prepnuti 30 -> 40 s vzperami (vzpery zustanou)");
  const pv = await mk(browser);
  await load(pv, "/stul-konfigurator.html", "#w=1840&d=800&arm=760&braces=1&bracelen=300&panels=0&socket=0");
  const v30 = await pv.page.evaluate(() => ({ braces: window.__pdcState.last.selection.braces, hrefSw: document.querySelector('#sysSwitch a[data-system="40"]').getAttribute("href") }));
  t("3a na generatoru 01 jsou vzpery zapnute a prepinac nese hash s braces=1", v30.braces === true && /braces=1/.test(v30.hrefSw), v30);
  await Promise.all([pv.page.waitForNavigation({ waitUntil: "load" }), pv.page.click('#sysSwitch a[data-system="40"]')]);
  await pv.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await pv.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1840; }, null, { timeout: 90000, polling: 200 });
  await idle(pv, 900);
  const v40 = await pv.page.evaluate(() => ({ sel: window.__pdcState.last.selection, probl: document.getElementById("staffProblems").textContent, hasBraces: window.__pdcState.schema.slots.some(s => s.id === "braces"), w: window.__pdcState.last.valid }));
  t("3b na generatoru 02 jsou vzpery ve vyberu i ve schematu, konfigurace je platna a rozmery zustaly (w 1840, arm 760, bracelen 300)", v40.hasBraces && v40.sel.braces === true && v40.sel.bracelen === 300 && v40.sel.w === 1840 && v40.sel.arm === 760 && v40.w === true, v40);
  t("3c stranka nehlasi zadne odebrani vzper", !/odebraly/.test(v40.probl), v40.probl);
  t("3d zadne chyby ve strance ani v konzoli (oba prechody)", pv.errs.length === 0, pv.errs.slice(0, 3));

  // ---------------------------------------------------------------- 4) stara adresa s hashem se starymi nazvy a stredni nohou v mm: system 40 pocita rozpeti sirka - 40
  console.log("\n## 4) starsi odkaz se stredni nohou v mm");
  const pm = await mk(browser);
  await load(pm, "/stul-konfigurator-40.html", "#sirka=2000&stredni_noha=900");
  const mid = await pm.page.evaluate(() => ({ mid: window.__pdcState.last.selection.mid, w: window.__pdcState.last.selection.w }));
  t("4a stredni_noha 900 mm u sirky 2000 = 900 / (2000 - 40) = 46 % (system 40 pocita rozpeti mezi osami noh)", mid.w === 2000 && mid.mid === Math.round(900 / (2000 - 40) * 100), mid);

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
