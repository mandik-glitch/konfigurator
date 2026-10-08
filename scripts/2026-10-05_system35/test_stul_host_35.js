// Test STRANKY GENERATORU STOLU 03 (system 35) a PREPINANI TEHOZ VYBERU mezi systemy 30 / 35 / 40 (bot10, 2026-10-05).
// SKUTECNE stranky (webapp/stul-konfigurator.html a stul-konfigurator-40.html) + SKUTECNY modul voleb a ovladani ve 3D nad SKUTECNYM kodem stolu (api/stul_shop.py) pres most
// scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, produkt 4934 = system 30, fiktivni karty PID40 = system 40 a PID35 = system 35, nic se nezapisuje do DB). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_system35/test_stul_host_35.js 4934
// Hlida: stranka 35 bere kartu ze schema.systems (ne pevne ID), ma slot vzper (sikme vzpery nese spojka 3254 ze systemu 30), resolve nese produkt 35, token modelu nese system (y = 35), zahlavi nabizi
// prepnuti na 30 a na 40 s TEMZE hashem, prepnuti 35 -> 40 -> 30 -> 35 zachova vyber (i vzpery), kusovnik je ze systemu 35, odkazy na vyrobni list nesou system=35.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID40 = Number(process.env.PID40 || 9877), PID35 = Number(process.env.PID35 || 9878);
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
const SW = s => `#sysSwitch a[data-system="${s}"]`;

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  // ---------------------------------------------------------------- 1) generator 03 (system 35)
  console.log("\n## 1) stranka Generator stolu 03 systém 35");
  const p35 = await mk(browser);
  await load(p35, "/stul-konfigurator-35.html", "");
  const s35 = await p35.page.evaluate(() => ({
    sys: window.StulHost.system, productId: window.StulHost.state.productId, title: document.title, h1: document.querySelector("h1").textContent, brand: document.querySelector(".mw-brand").textContent.trim(),
    bracesText: /Šikmé vzpěry/.test(document.body.innerText),
    schema: window.__pdcState.schema && { system: window.__pdcState.schema.system, profile: window.__pdcState.schema.profile, ids: window.__pdcState.schema.slots.map(s => s.id), systems: (window.__pdcState.schema.systems || []).map(x => x.system) },
    price: document.getElementById("priceNet").textContent, code: document.getElementById("staffCode").textContent, stageMsg: getComputedStyle(document.getElementById("stageMsg")).display,
    sw: [...document.querySelectorAll("#sysSwitch a")].map(a => ({ system: a.getAttribute("data-system"), text: a.textContent, href: a.getAttribute("href") })), swHidden: document.getElementById("sysSwitch").hidden,
    bom: [...document.querySelectorAll("#bomBody tbody tr")].map(r => r.textContent).join("|")
  }));
  t("1a stranka je generator 03 systém 35 (data-system, titulek, nadpis, znacka)", s35.sys === 35 && /^Generátor stolu 03 systém 35$/.test(s35.title) && s35.h1 === "Generátor stolu 03 systém 35" && /03 systém 35/.test(s35.brand), [s35.sys, s35.title, s35.h1, s35.brand]);
  t("1b karta systemu 35 se vzala ze schema.systems (ne pevne ID): productId = " + PID35, s35.productId === PID35, s35.productId);
  t("1c schema 35: system 35, profil 35x35, sloty vzper (braces, bracelen) i ostatni sloty jsou; schema.systems ma vsechny 3 systemy (30 / 35 / 40; stul SSE 41 je navic, je-li k dispozici)", s35.schema && s35.schema.system === 35 && s35.schema.profile === "35x35" && s35.schema.ids.includes("braces") && s35.schema.ids.includes("bracelen") && s35.schema.ids.includes("w") && s35.schema.ids.includes("shelf") && JSON.stringify([...s35.schema.systems].filter(x => x !== 41).sort()) === "[30,35,40]", s35.schema);
  t("1d ve strance je volba vzper (sikme vzpery nese ve 35 spojka 3254 ze systemu 30)", s35.bracesText);
  t("1e cena a kod konfigurace jsou videt, hlaska o nacitani zmizela", /\d/.test(s35.price) && /^Kód konfigurace: STL-[0-9A-F]+ · \d+ spojů profilů$/.test(s35.code) && s35.stageMsg === "none", [s35.price, s35.code, s35.stageMsg]);
  t("1f kusovnik je ze systemu 35: Profil 35x35 a rohova spojka 30x30 (ze systemu 30) s maticemi do drazky 8, ne profil 30x30 ani 40x40", /Profil 35x35/.test(s35.bom) && /Rohová spojka 30 x 30/.test(s35.bom) && /drážka 8/.test(s35.bom) && !/Profil 30x30/.test(s35.bom) && !/Profil 40x40/.test(s35.bom), s35.bom.slice(0, 300));
  t("1g prvni resolve nese produkt 35 a staff: true", p35.trk.bodies.length > 0 && p35.trk.bodies.every(b => new RegExp(`"product_id":\\s*${PID35}`).test(b)) && /"staff":\s*true/.test(p35.trk.bodies[0]), p35.trk.bodies[0] && p35.trk.bodies[0].slice(0, 120));
  t("1h token 3D modelu nese system 35 (y = 35)", p35.trk.glbUrls.length > 0 && p35.trk.glbUrls.every(u => tokenSystem(u) === 35), p35.trk.glbUrls.map(tokenSystem));
  t("1i zahlavi: viditelne, nabizi prepnuti na system 30 a na system 40 (ne na sebe; kdyz ma kartu i stul SSE 41, nabizi i ten) a nese odkazy na druhe generatory", !s35.swHidden && s35.sw.filter(x => x.system !== "41").length === 2 && s35.sw.every(x => x.system !== "41" || /^\/stul-konfigurator-41\.html/.test(x.href)) && s35.sw.some(x => x.system === "30" && /systém 30/.test(x.text) && /^\/stul-konfigurator\.html/.test(x.href)) && s35.sw.some(x => x.system === "40" && /systém 40/.test(x.text) && /^\/stul-konfigurator-40\.html/.test(x.href)), s35.sw);
  const vinfo = await p35.page.evaluate(() => document.getElementById("staffLinks").innerHTML);
  t("1j odkazy na vyrobni list nesou system=35", /system=35/.test(vinfo), vinfo.slice(0, 200));
  t("1k zadne chyby ve strance ani v konzoli", p35.errs.length === 0, p35.errs.slice(0, 3));

  // odkaz s hashem: vyber se nacte do systemu 35 a prepinace ho prenesou
  await p35.page.goto("about:blank");
  await p35.page.goto(`${BASE}/stul-konfigurator-35.html?debug=1#w=1800&d=900&h=950&shelf=2`, { waitUntil: "load" });
  await p35.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p35, 900);
  const sw2 = await p35.page.evaluate(() => ({ h30: document.querySelector('#sysSwitch a[data-system="30"]').getAttribute("href"), h40: document.querySelector('#sysSwitch a[data-system="40"]').getAttribute("href"), sel: window.__pdcState.last.selection }));
  t("1l hash #w=1800&d=900&h=950&shelf=2 se nacetl do vyberu (system 35) a oba prepinace nesou stejny hash", sw2.sel.w === 1800 && sw2.sel.d === 900 && sw2.sel.h === 950 && sw2.sel.shelf >= 1 && /^\/stul-konfigurator\.html#/.test(sw2.h30) && /w=1800/.test(sw2.h30) && /^\/stul-konfigurator-40\.html#/.test(sw2.h40) && /d=900/.test(sw2.h40), [sw2.sel.w, sw2.h30.slice(0, 100), sw2.h40.slice(0, 100)]);
  const kod35 = await p35.page.evaluate(() => window.__pdcState.last.kod), cena35 = await p35.page.evaluate(() => document.getElementById("priceNet").textContent);

  // ---------------------------------------------------------------- 2) 35 -> 40 -> 30 -> 35 odkazy (stejny vyber)
  console.log("\n## 2) prepnuti 35 -> 40 -> 30 -> 35 se stejnym vyberem");
  const kody = { 35: kod35 }, ceny = { 35: cena35 };
  const kroky = [[40, "/stul-konfigurator-40.html"], [30, "/stul-konfigurator.html"], [35, "/stul-konfigurator-35.html"]];
  let od = 35;
  for (const [cil, cesta] of kroky) {
    await Promise.all([p35.page.waitForNavigation({ waitUntil: "load" }), p35.page.click(SW(cil))]);
    await p35.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
    await p35.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
    await idle(p35, 900);
    const x = await p35.page.evaluate(() => ({ url: location.pathname + location.hash, sys: window.StulHost.system, productId: window.StulHost.state.productId, title: document.title, sel: window.__pdcState.last.selection, kod: window.__pdcState.last.kod,
      price: document.getElementById("priceNet").textContent, schema: { system: window.__pdcState.schema.system, hasBraces: window.__pdcState.schema.slots.some(s => s.id === "braces") },
      sw: [...document.querySelectorAll("#sysSwitch a")].map(a => a.getAttribute("data-system")) }));
    kody[cil] = x.kod; ceny[cil] = x.price;
    const pidOcek = cil === 30 ? 4934 : (cil === 35 ? PID35 : PID40);
    t(`2.${od}->${cil} po kliknuti jsme na generatoru systemu ${cil} (produkt ${pidOcek}) se stejnym vyberem (w 1800, d 900, h 950)`, new RegExp("^" + cesta.replace(/[.]/g, "\\.") + "#").test(x.url) && x.sys === cil && x.productId === pidOcek && x.sel.w === 1800 && x.sel.d === 900 && x.sel.h === 950 && x.schema.system === cil && x.schema.hasBraces, x);
    t(`2.${od}->${cil}b zahlavi nabizi zbyvajici dva systemy (30 / 35 / 40; stul SSE 41 je navic, je-li k dispozici)`, JSON.stringify([...x.sw].filter(s => s !== "41").sort()) === JSON.stringify([30, 35, 40].filter(s => s !== cil).map(String)), x.sw);
    od = cil;
  }
  t("2a tri ruzne kody a ruzne ceny pro stejny vyber v systemech 30 / 35 / 40", new Set(Object.values(kody)).size === 3 && ceny[30] !== ceny[35] && ceny[35] !== ceny[40], [kody, ceny]);

  // ---------------------------------------------------------------- 3) vzpery zustanou pri prepnuti mezi vsemi systemy
  console.log("\n## 3) vzpery pri prepnuti 30 -> 35 -> 40");
  const pv = await mk(browser);
  await load(pv, "/stul-konfigurator.html", "#w=1840&d=800&arm=760&braces=1&bracelen=300&panels=0&socket=0");
  const v30 = await pv.page.evaluate(() => ({ braces: window.__pdcState.last.selection.braces, hrefSw: document.querySelector('#sysSwitch a[data-system="35"]').getAttribute("href") }));
  t("3a na generatoru 01 jsou vzpery zapnute a prepinac na 35 nese hash s braces=1", v30.braces === true && /braces=1/.test(v30.hrefSw) && /^\/stul-konfigurator-35\.html#/.test(v30.hrefSw), v30);
  await Promise.all([pv.page.waitForNavigation({ waitUntil: "load" }), pv.page.click(SW(35))]);
  await pv.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await pv.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1840; }, null, { timeout: 90000, polling: 200 });
  await idle(pv, 900);
  const v35 = await pv.page.evaluate(() => ({ sel: window.__pdcState.last.selection, probl: document.getElementById("staffProblems").textContent, hasBraces: window.__pdcState.schema.slots.some(s => s.id === "braces"), valid: window.__pdcState.last.valid }));
  t("3b na generatoru 03 jsou vzpery ve vyberu i ve schematu, konfigurace je platna a rozmery zustaly (w 1840, arm 760, bracelen 300)", v35.hasBraces && v35.sel.braces === true && v35.sel.bracelen === 300 && v35.sel.w === 1840 && v35.sel.arm === 760 && v35.valid === true, v35);
  t("3c stranka nehlasi zadne odebrani vzper", !/odebraly/.test(v35.probl), v35.probl);
  await Promise.all([pv.page.waitForNavigation({ waitUntil: "load" }), pv.page.click(SW(40))]);
  await pv.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await pv.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1840; }, null, { timeout: 90000, polling: 200 });
  await idle(pv, 900);
  const v40 = await pv.page.evaluate(() => ({ sel: window.__pdcState.last.selection, hasBraces: window.__pdcState.schema.slots.some(s => s.id === "braces"), valid: window.__pdcState.last.valid, probl: document.getElementById("staffProblems").textContent }));
  t("3d i na generatoru 02 (40) vzpery zustanou (spojka 3220) a konfigurace je platna", v40.hasBraces && v40.sel.braces === true && v40.sel.bracelen === 300 && v40.valid === true && !/odebraly/.test(v40.probl), v40);
  t("3e zadne chyby ve strance ani v konzoli (vsechny prechody)", pv.errs.length === 0 && p35.errs.length === 0, [...pv.errs, ...p35.errs].slice(0, 3));

  // ---------------------------------------------------------------- 4) starsi odkaz se stredni nohou v mm: system 35 pocita rozpeti sirka - 35
  console.log("\n## 4) starsi odkaz se stredni nohou v mm");
  const pm = await mk(browser);
  await load(pm, "/stul-konfigurator-35.html", "#sirka=2000&stredni_noha=900");
  const mid = await pm.page.evaluate(() => ({ mid: window.__pdcState.last.selection.mid, w: window.__pdcState.last.selection.w }));
  t("4a stredni_noha 900 mm u sirky 2000 = 900 / (2000 - 35) = 46 % (system 35 pocita rozpeti mezi osami noh)", mid.w === 2000 && mid.mid === Math.round(900 / (2000 - 35) * 100), mid);

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
