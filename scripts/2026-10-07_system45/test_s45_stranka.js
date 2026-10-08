// Test STRANKY GENERATORU STOLU 05 (system 45 = hluboky stul az 2500 mm) a PREPINANI TEHOZ VYBERU mezi nim a generatory 02 (system 40) a 01 (system 30) (bot10, 2026-10-07).
// SKUTECNE stranky (webapp/stul-konfigurator*.html) + SKUTECNY modul voleb a ovladani ve 3D nad SKUTECNYM kodem stolu (api/stul_shop.py) pres most
// scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, produkt 4934 = system 30, fiktivni karty PID40 = system 40 a PID45 = system 45, nic se nezapisuje do DB). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID45=9878 --setenv=PRAVIDLA_TEST={} \
//     --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_system45/test_s45_stranka.js 4934
// Hlida: stranka 05 bere kartu ze schema.systems (ne pevne ID), posuvnik hloubky do 2500 mm (40 do 1500), resolve nese produkt 45, token modelu nese system 45, hluboky stul (d=2000) je platny
// a stranka ukaze informaci o stredni rade noh, prepinac v zahlavi nese TENTYZ hash (do 40 se hloubka zkrati na 1500), starsi odkaz se stredni nohou v mm pocita rozpeti s profilem 40 (ne 45),
// admin vidi v Pravidlech stolu tlacitko systemu 45, kusovnik je ze systemu 40 (profil 40x40), zadne chyby v konzoli.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const BASE = process.env.BASE, PID40 = Number(process.env.PID40 || 9877), PID45 = Number(process.env.PID45 || 9878), SHOTS = process.env.SHOTS || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
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
const shot = async (p, name) => { if (SHOTS) { fs.mkdirSync(SHOTS, { recursive: true }); await p.page.locator("#stage").screenshot({ path: `${SHOTS}/${name}.png` }).catch(() => {}); } };

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  // ---------------------------------------------------------------- 1) generator 05 (system 45)
  console.log("\n## 1) stranka Generator stolu 05 systém 45");
  const p45 = await mk(browser);
  await load(p45, "/stul-konfigurator-45.html", "");
  const s45 = await p45.page.evaluate(() => ({
    sys: window.StulHost.system, productId: window.StulHost.state.productId, title: document.title, h1: document.querySelector("h1").textContent, brand: document.querySelector(".mw-brand").textContent.trim(),
    schema: window.__pdcState.schema && { system: window.__pdcState.schema.system, profile: window.__pdcState.schema.profile, ids: window.__pdcState.schema.slots.map(s => s.id),
      d: (window.__pdcState.schema.slots.find(s => s.id === "d") || {}).slider, systems: window.__pdcState.schema.systems },
    price: document.getElementById("priceNet").textContent, code: document.getElementById("staffCode").textContent, stageMsg: getComputedStyle(document.getElementById("stageMsg")).display,
    sw40: (() => { const a = document.querySelector('#sysSwitch a[data-system="40"]'); return a && { hidden: a.hidden, text: a.textContent, href: a.getAttribute("href") }; })(),
    sw30: (() => { const a = document.querySelector('#sysSwitch a[data-system="30"]'); return a && { hidden: a.hidden, text: a.textContent, href: a.getAttribute("href") }; })(),
    bom: [...document.querySelectorAll("#bomBody tbody tr")].map(r => r.textContent).join("|")
  }));
  t("1a stranka je generator 05 systém 45 – Robustní (data-system, titulek, nadpis, znacka; Robert 2026-10-07: system 45 nazyvame tez Robustni)", s45.sys === 45 && /^Generátor stolu 05 systém 45 – Robustní$/.test(s45.title) && s45.h1 === "Generátor stolu 05 systém 45 – Robustní" && /05 systém 45 – Robustní/.test(s45.brand), [s45.sys, s45.title, s45.h1, s45.brand]);
  t("1b karta systemu 45 se vzala ze schema.systems (ne pevne ID): productId = " + PID45, s45.productId === PID45, s45.productId);
  t("1c schema 45: system 45, profil 40x40, vsechny sloty jako v systemu 40 (vzpery, vyrezy...)", s45.schema && s45.schema.system === 45 && s45.schema.profile === "40x40" && ["braces", "bracelen", "w", "d", "h", "shelf", "cut1d"].every(x => s45.schema.ids.includes(x)), s45.schema && [s45.schema.system, s45.schema.profile]);
  t("1d posuvnik hloubky je 400 az 2500 mm po 10", s45.schema && s45.schema.d && s45.schema.d.min === 400 && s45.schema.d.max === 2500 && s45.schema.d.step === 10, s45.schema && s45.schema.d);
  t("1e schema.systems nese karty 45 a 40 (stranka vi o obou)", s45.schema.systems.some(x => x.system === 45 && x.card_id === PID45) && s45.schema.systems.some(x => x.system === 40 && x.card_id === PID40), s45.schema.systems);
  t("1f cena a kod konfigurace jsou videt, hlaska o nacitani zmizela", /\d/.test(s45.price) && /^Kód konfigurace: STL-[0-9A-F]+ · \d+ spojů profilů$/.test(s45.code) && s45.stageMsg === "none", [s45.price, s45.code, s45.stageMsg]);
  t("1g kusovnik je z profilu 40x40 (jako system 40): Profil 40x40, spojka 40x40, matice do drazky 10", /Profil 40x40/.test(s45.bom) && /40x40 Rohová spojka/.test(s45.bom) && /drážka 10/.test(s45.bom) && !/Profil 30x30/.test(s45.bom), s45.bom.slice(0, 300));
  t("1h prvni resolve nese produkt 45 a staff: true", p45.trk.bodies.length > 0 && p45.trk.bodies.every(b => new RegExp(`"product_id":\\s*${PID45}`).test(b)) && /"staff":\s*true/.test(p45.trk.bodies[0]), p45.trk.bodies[0] && p45.trk.bodies[0].slice(0, 120));
  t("1i token 3D modelu nese system 45 (y = 45)", p45.trk.glbUrls.length > 0 && p45.trk.glbUrls.every(u => tokenSystem(u) === 45), p45.trk.glbUrls.map(tokenSystem));
  t("1j prepinac v zahlavi: viditelny, nabizi system 40 a system 30 a nese odkazy na druhe generatory", s45.sw40 && !s45.sw40.hidden && /systém 40/.test(s45.sw40.text) && /^\/stul-konfigurator-40\.html/.test(s45.sw40.href) && s45.sw30 && /^\/stul-konfigurator\.html/.test(s45.sw30.href), [s45.sw40, s45.sw30]);
  const vinfo = await p45.page.evaluate(() => document.getElementById("staffLinks").innerHTML);
  t("1k odkazy na vyrobni list nesou system=45", /system=45/.test(vinfo), vinfo.slice(0, 200));
  t("1l zadne chyby ve strance ani v konzoli", p45.errs.length === 0, p45.errs.slice(0, 3));

  // ---------------------------------------------------------------- 2) Pravidla stolu: tlacitko systemu 45 (admin)
  console.log("\n## 2) Pravidla stolu pro admina");
  const prav = await p45.page.evaluate(() => { const b = document.getElementById("pravSys45"), b40 = document.getElementById("pravSys40"); return { ma45: !!b, vis45: b && getComputedStyle(b).display !== "none", pressed45: b && b.getAttribute("aria-pressed"), pressed40: b40 && b40.getAttribute("aria-pressed"), label: b && b.textContent, title: b && b.title }; });
  t("2a admin vidi v Pravidlech stolu tlacitko systemu 45 (vybrane jako system teto stranky)", prav.ma45 && prav.vis45 && prav.pressed45 === "true" && prav.pressed40 === "false" && prav.label === "45", prav);
  await p45.page.evaluate(() => { const b = document.querySelector(".mw-win-rules"); if (b && b.classList.contains("is-closed")) b.querySelector(".mw-win-h").click(); });          // okno Pravidla stolu je sklopitelne
  await p45.page.click("#pravSys40"); await p45.page.waitForTimeout(300);
  const prav2 = await p45.page.evaluate(() => ({ p40: document.getElementById("pravSys40").getAttribute("aria-pressed"), p45: document.getElementById("pravSys45").getAttribute("aria-pressed"), vych: document.getElementById("pravVychozi").textContent }));
  t("2b prepnuti na pravidla systemu 40 a zpet na 45 funguje", prav2.p40 === "true" && prav2.p45 === "false" && /systém 40/.test(prav2.vych), prav2);
  await p45.page.click("#pravSys45"); await p45.page.waitForTimeout(300);
  const prav3 = await p45.page.evaluate(() => ({ p45: document.getElementById("pravSys45").getAttribute("aria-pressed"), vych: document.getElementById("pravVychozi").textContent, hl: document.getElementById("pravHloubka").value }));
  t("2c pravidla systemu 45 maji vychozi hodnoty jako 40 (prah podper 900 mm)", prav3.p45 === "true" && /systém 45/.test(prav3.vych) && prav3.hl === "900", prav3);

  const polia = async () => p45.page.evaluate(() => { const v = (id) => { const e = document.getElementById(id); return !!e && e.style.display !== "none"; }; const h = (id) => (document.getElementById(id) || {}).value;
    return { rada: v("pravStredniRada"), rozpon: v("pravRozpon"), odstup: v("pravOdstupSt"), sirka: v("pravStredni"), hloubka: v("pravHloubka"), vals: [h("pravStredniRada"), h("pravRozpon"), h("pravOdstupSt")] }; });
  const f45 = await polia();
  t("2d Pravidla 45: zlomove miry (hloubka stredni rady 1500, nejvetsi usek desky 800, odstup stredni nohy 150) jsou videt a maji vychozi hodnoty", f45.rada && f45.rozpon && f45.odstup && f45.sirka && f45.hloubka && f45.vals.join(",") === "1500,800,150", f45);
  if (SHOTS) { await p45.page.locator(".mw-win-rules").screenshot({ path: `${SHOTS}/pravidla_system45.png` }).catch(() => {}); }
  await p45.page.click("#pravSys40"); await p45.page.waitForTimeout(300);
  const f40 = await polia();
  t("2e Pravidla 40: pole 'hloubka stredni rady noh' se neukazuje (jen hluboky system 45), ostatni zlomove miry ano", !f40.rada && f40.rozpon && f40.odstup && f40.sirka && f40.hloubka, f40);
  await p45.page.click("#pravSys45"); await p45.page.waitForTimeout(200);

  // ---------------------------------------------------------------- 3) hluboky stul odkazem s hashem
  console.log("\n## 3) hluboky stul (d = 2000) odkazem");
  await p45.page.goto("about:blank");
  await p45.page.goto(`${BASE}/stul-konfigurator-45.html?debug=1#w=1800&d=2000&h=950&shelf=2`, { waitUntil: "load" });
  await p45.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p45, 900);
  const deep = await p45.page.evaluate(() => ({ sel: window.__pdcState.last.selection, valid: window.__pdcState.last.valid, kod: window.__pdcState.last.kod, price: document.getElementById("priceNet").textContent,
    text: document.body.innerText, hrefSw40: document.querySelector('#sysSwitch a[data-system="40"]').getAttribute("href"), probl: document.getElementById("staffProblems").textContent }));
  t("3a hash #w=1800&d=2000&h=950&shelf=2 se nacetl do vyberu (hloubka 2000 se zachovala) a stul je platny", deep.sel.w === 1800 && deep.sel.d === 2000 && deep.sel.h === 950 && deep.valid === true, [deep.sel.w, deep.sel.d, deep.sel.h, deep.valid]);
  t("3b stranka ukazuje informaci o stredni rade noh nad 1500 mm", /Při hloubce nad 1500 mm přibude uprostřed hloubky na každé straně střední noha/.test(deep.text), deep.text.slice(0, 200));
  t("3c prepinac do systemu 40 nese stejny hash (vcetne d=2000)", /^\/stul-konfigurator-40\.html#/.test(deep.hrefSw40) && /d=2000/.test(deep.hrefSw40) && /w=1800/.test(deep.hrefSw40), deep.hrefSw40);
  t("3d staff stranka nehlasi zadne problemy konstrukce", deep.probl.trim() === "", deep.probl);
  await shot(p45, "hluboky_stul_2000");
  const cena45 = deep.price, kod45 = deep.kod;
  t("3e zadne chyby ve strance ani v konzoli", p45.errs.length === 0, p45.errs.slice(0, 3));

  // ---------------------------------------------------------------- 4) prepnuti 45 -> 40: hloubka se zkrati na 1500, zbytek zustane
  console.log("\n## 4) prepnuti na generator 02 (system 40) se stejnym vyberem");
  await Promise.all([p45.page.waitForNavigation({ waitUntil: "load" }), p45.page.click('#sysSwitch a[data-system="40"]')]);
  await p45.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p45.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p45, 900);
  const s40 = await p45.page.evaluate(() => ({ url: location.pathname + location.hash, sys: window.StulHost.system, productId: window.StulHost.state.productId, sel: window.__pdcState.last.selection, kod: window.__pdcState.last.kod,
    swb: (() => { const a = document.querySelector('#sysSwitch a[data-system="45"]'); return a && { hidden: a.hidden, text: a.textContent, href: a.getAttribute("href") }; })(), dmax: (window.__pdcState.schema.slots.find(s => s.id === "d") || {}).slider.max }));
  t("4a po kliknuti jsme na generatoru 02 (system 40, karta " + PID40 + ") se stejnym vyberem; hloubka 2000 se zkratila na nejvetsi hloubku systemu 40 (1500)", /^\/stul-konfigurator-40\.html#/.test(s40.url) && s40.sys === 40 && s40.productId === PID40 && s40.sel.w === 1800 && s40.sel.h === 950 && s40.sel.d === 1500 && s40.dmax === 1500, [s40.url, s40.sys, s40.productId, s40.sel, s40.dmax]);
  t("4b prepinac na generatoru 02 nabizi system 45 a nese hash", s40.swb && !s40.swb.hidden && /systém 45/.test(s40.swb.text) && /^\/stul-konfigurator-45\.html#/.test(s40.swb.href) && /w=1800/.test(s40.swb.href), s40.swb);

  // ---------------------------------------------------------------- 5) stejny stul do hloubky 1500: v 40 i 45 stejna cena, ruzny kod (system je v hashi)
  console.log("\n## 5) stejny vyber v obou systemech");
  const pc = await mk(browser);
  await load(pc, "/stul-konfigurator-40.html", "#w=1800&d=1200&h=950&shelf=2");
  const c40 = await pc.page.evaluate(() => ({ price: document.getElementById("priceNet").textContent, kod: window.__pdcState.last.kod, hrefSw: document.querySelector('#sysSwitch a[data-system="45"]').getAttribute("href") }));
  await Promise.all([pc.page.waitForNavigation({ waitUntil: "load" }), pc.page.click('#sysSwitch a[data-system="45"]')]);
  await pc.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await pc.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(pc, 900);
  const c45 = await pc.page.evaluate(() => ({ url: location.pathname + location.hash, sys: window.StulHost.system, price: document.getElementById("priceNet").textContent, kod: window.__pdcState.last.kod, sel: window.__pdcState.last.selection }));
  t("5a prepnuti 40 -> 45 nese stejny vyber (w 1800, d 1200, h 950)", /^\/stul-konfigurator-45\.html#/.test(c45.url) && c45.sys === 45 && c45.sel.w === 1800 && c45.sel.d === 1200 && c45.sel.h === 950, c45);
  t("5b stejny stul do hloubky 1500 ma v obou systemech STEJNOU cenu a RUZNY kod konfigurace", c45.price === c40.price && c45.kod !== c40.kod, [c40.price, c45.price, c40.kod, c45.kod]);
  t("5c zadne chyby ve strance ani v konzoli (oba prechody)", pc.errs.length === 0, pc.errs.slice(0, 3));

  // ---------------------------------------------------------------- 6) starsi odkaz se stredni nohou v mm: system 45 pocita rozpeti sirka - 40 (profil 40, ne cislo systemu)
  console.log("\n## 6) starsi odkaz se stredni nohou v mm");
  const pm = await mk(browser);
  await load(pm, "/stul-konfigurator-45.html", "#sirka=2000&stredni_noha=900");
  const mid = await pm.page.evaluate(() => ({ mid: window.__pdcState.last.selection.mid, w: window.__pdcState.last.selection.w }));
  t("6a stredni_noha 900 mm u sirky 2000 = 900 / (2000 - 40) = 46 % (system 45 ma profil 40, rozpeti mezi osami noh = sirka - 40, ne - 45)", mid.w === 2000 && mid.mid === Math.round(900 / (2000 - 40) * 100), mid);
  t("6b zadne chyby ve strance ani v konzoli", pm.errs.length === 0, pm.errs.slice(0, 3));

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
