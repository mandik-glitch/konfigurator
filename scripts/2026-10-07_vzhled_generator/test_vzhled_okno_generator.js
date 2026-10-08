// Test OKNA "Vzhled online nabidek" v GENERATORU STOLU (js/stul-host.js + kontrola.html?items=mu:...&embed=1; bot10, 2026-10-07; Robert: "to nema byt jen v jedne karte, ale automaticky v kazde",
// "at se to negeneruje porad dokola, muze to byt propojene do generatoru stolu a tam to muze sidlit"). SKUTECNE stranky generatoru + SKUTECNY modul voleb nad SKUTECNYM kodem stolu pres most
// scripts/2026-10-02_stul_testy/_most_stul.py (prihlaseny admin, produkt 4934 = system 30, fiktivni karty PID40 = system 40 a PID45 = system 45, nic se nezapisuje do DB). Spusteni:
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID45=9878 --setenv=PRAVIDLA_TEST={} \
//     --working-directory=<koren s api a webapp> api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_vzhled_generator/test_vzhled_okno_generator.js 4934
// Hlida: okno Vzhled ma jen admin, je sbalene a bez iframe; po rozbaleni se nacte iframe s kontrolni scenou nad modelem TOHOTO generatoru (adresa GLB z resolve), embed rezim, okno Vzhled otevrene
// a viditelne; "Nacist aktualni model" a odkaz do zvlastniho panelu; ?vzhled=1 okno rozbali a ukaze; funguje u vsech generatoru (30 / 40 / 45); zadne chyby ve strance ani v konzoli.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, SHOTS = process.env.SHOTS || "";          // SHOTS=<adresar>: ulozi snimky okna Vzhled (jen pro lidskou kontrolu)
const fs = require("fs");
const shot = async (loc, name) => { if (!SHOTS) return; fs.mkdirSync(SHOTS, { recursive: true }); await loc.screenshot({ path: `${SHOTS}/${name}.png` }).catch(() => {}); };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  const trk = { pending: 0, last: Date.now(), glbUrls: [] };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.pending++; trk.last = Date.now(); } else if (GLB_RE.test(u)) { trk.pending++; trk.last = Date.now(); trk.glbUrls.push(u); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => { const q = quiet || 1200; await p.page.waitForTimeout(q); const t0 = Date.now(); while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); } };
async function load(p, pagePath, query, hash) {
  await p.page.goto(`${BASE}${pagePath}?debug=1${query || ""}${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash && S.last.model && S.last.model.url; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const modelUrl = (p) => p.page.evaluate(() => window.__pdcState.last.model.url);
const okno = (p) => p.page.evaluate(() => { const b = document.querySelector(".mw-win-vzhled"); if (!b) return null; const r = b.getBoundingClientRect(), g = document.querySelector(".mw-pdg").getBoundingClientRect(); return { hidden: b.hidden, zavrene: b.classList.contains("is-closed"), vidim: r.width > 0 && r.height > 0 && getComputedStyle(b).display !== "none",
  titul: (b.querySelector(".mw-win-h") || {}).textContent, iframe: !!document.getElementById("vzhledFrame"), pod: [...document.querySelectorAll(".mw-pdg .mw-win")].filter(x => x !== b && x.offsetParent !== null).every(x => x.getBoundingClientRect().bottom <= r.top + 2) && r.bottom <= g.bottom + 2, sirka: Math.round(r.width), mrizka: Math.round(g.width), top: Math.round(r.top) }; });
async function iframeHotov(p) {
  const fh = await p.page.waitForSelector("#vzhledFrame", { timeout: 20000 });
  const frame = await fh.contentFrame();
  await frame.waitForFunction(() => window.__v3d && window.__v3d.state && window.__v3d.state().ready, null, { timeout: 120000, polling: 200 });
  await frame.waitForFunction(() => !document.querySelector("#vzhledPanel").hidden, null, { timeout: 30000 }).catch(() => {});
  return frame;
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  console.log("\n## 1) generator 02 (system 40): okno Vzhled pro admina, sbalene, bez iframe");
  const p = await mk(browser);
  await load(p, "/stul-konfigurator-40.html", "", "#w=1800&d=900&h=950&shelf=2");
  const o1 = await okno(p);
  t("1a okno 'Vzhled online nabidek' je videt (admin), sbalene a bez iframe (iframe se nacita az po rozbaleni)", o1 && !o1.hidden && o1.vidim && o1.zavrene && !o1.iframe && /Vzhled online nabídek/.test(o1.titul), o1);
  t("1b okno je posledni radek mrizky oken (pod vsemi okny, UVNITR mrizky kvuli liste ceny na mobilu) pres celou sirku (iframe potrebuje misto)", o1 && o1.pod && o1.sirka >= o1.mrizka - 4, o1);

  console.log("\n## 2) rozbaleni: iframe s kontrolni scenou nad modelem TOHOTO generatoru");
  await p.page.click(".mw-win-vzhled .mw-win-h");
  const frame = await iframeHotov(p);
  const url = await modelUrl(p);
  const src = await p.page.evaluate(() => document.getElementById("vzhledFrame").getAttribute("src"));
  const m = /[?&]items=mu:([^&]+)/.exec(src);
  t("2a iframe ma adresu /kontrola.html?items=mu:<adresa GLB>&rezim=nabidka&embed=1&vzhled=1", /^\/kontrola\.html\?/.test(src) && /rezim=nabidka/.test(src) && /embed=1/.test(src) && /vzhled=1/.test(src), src);
  t("2b adresa modelu v iframe = adresa GLB, ktery generator prave ukazuje (nic se nestavi na serveru)", !!m && decodeURIComponent(m[1]) === url && /^\/api\/shop\/configurator\/glb\//.test(url), [m && decodeURIComponent(m[1]), url]);
  const f = await frame.evaluate(() => ({ embed: document.body.classList.contains("embed"), top: getComputedStyle(document.querySelector("#topbar")).display, panel: !document.querySelector("#vzhledPanel").hidden, btn: !document.querySelector("#vzhledBtn").hidden,
    paleta: document.querySelectorAll("#vzhledPal input[type=color]").length, ready: window.__v3d.state().ready, motions: window.__v3d.state().motions.length }));
  t("2c v iframe je embed rezim, okno Vzhled otevrene, tlacitko videt, model nacteny", f.embed && f.top === "none" && f.panel && f.btn && f.ready, f);
  t("2d okno ma paletu barev modelu stolu a posuvniky", f.paleta >= 1 && await frame.evaluate(() => !!document.querySelector("#vzhledSat") && !!document.querySelector("#vzhledAluRefl")), f);
  const o2 = await okno(p);
  t("2e okno je rozbalene a iframe je videt (vyska aspon 520 px)", o2 && !o2.zavrene && o2.iframe && (await p.page.evaluate(() => document.getElementById("vzhledFrame").getBoundingClientRect().height)) >= 520, o2);
  t("2f odkaz 'Otevrit ve zvlastnim panelu' nese tutez adresu a otevira novy panel", await p.page.evaluate((s) => { const a = document.getElementById("vzhledNovy"); return !!a && a.getAttribute("href") === s && a.target === "_blank" && /noopener/.test(a.rel); }, src));
  t("2g generator sam bez chyb (stranka i konzole)", p.errs.length === 0, p.errs.slice(0, 3));
  await p.page.evaluate(() => { const b = document.querySelector(".mw-win-vzhled"); if (b) b.scrollIntoView({ block: "start" }); });
  await p.page.waitForTimeout(800);
  await shot(p.page.locator(".mw-win-vzhled"), "okno_vzhled_generator");

  console.log("\n## 3) Nacist aktualni model: po zmene konfigurace se iframe nacte znovu s novou adresou");
  const puvodni = url;
  await p.page.evaluate(() => { const r = document.querySelector('[data-slot="w"] input.pdc-range'); r.value = "1500"; r.dispatchEvent(new Event("input", { bubbles: true })); r.dispatchEvent(new Event("change", { bubbles: true })); });          // zmena sirky posuvnikem
  await p.page.waitForFunction((u) => window.__pdcState.last && window.__pdcState.last.model && window.__pdcState.last.model.url && window.__pdcState.last.model.url !== u, puvodni, { timeout: 60000, polling: 200 });
  await idle(p, 900);
  const nova = await modelUrl(p);
  const stareSrc = await p.page.evaluate(() => document.getElementById("vzhledFrame").getAttribute("src"));
  t("3a po zmene konfigurace se iframe NEMENI sam (rozdelane upravy by se ztratily)", /items=mu:/.test(stareSrc) && decodeURIComponent(/items=mu:([^&]+)/.exec(stareSrc)[1]) === puvodni && nova !== puvodni, [stareSrc.slice(0, 120), nova.slice(0, 60)]);
  await p.page.click("#vzhledReload");
  await p.page.waitForFunction((u) => { const f = document.getElementById("vzhledFrame"); return f && decodeURIComponent(/items=mu:([^&]+)/.exec(f.getAttribute("src"))[1]) === u; }, nova, { timeout: 20000 });
  const frame2 = await iframeHotov(p);
  t("3b po kliknuti na 'Nacist aktualni model' ma iframe novy model (jina adresa) a bezi", await frame2.evaluate(() => window.__v3d.state().ready), nova.slice(0, 60));
  t("3c bez chyb ve strance ani v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
  await p.ctx.close();

  console.log("\n## 4) odkaz ?vzhled=1 (z karty produktu): okno se rozbali a ukaze samo; hluboky stul systemu 45");
  const q = await mk(browser);
  await load(q, "/stul-konfigurator-45.html", "&vzhled=1", "#w=1800&d=2000&h=840&shelf=1");
  const o4 = await okno(q);
  t("4a okno je pri otevreni uz rozbalene a iframe existuje", o4 && !o4.zavrene && o4.iframe, o4);
  const fr4 = await iframeHotov(q);
  await q.page.waitForTimeout(1200);
  const o4b = await okno(q);
  t("4a2 po nacteni iframe stranka na okno doscrollovala (okno je v dohledu, ne az dole pod mrizkou)", o4b && o4b.top >= -50 && o4b.top < 500, o4b);
  const u4 = await modelUrl(q);
  t("4b iframe ukazuje hluboky stul 45 (adresa modelu = adresa generatoru, token nese system 45)", await fr4.evaluate(() => window.__v3d.state().ready) && (() => { try { const tok = u4.split("/glb/")[1]; const b = tok.split(".")[0].replace(/-/g, "+").replace(/_/g, "/"); return JSON.parse(Buffer.from(b + "=".repeat((4 - b.length % 4) % 4), "base64").toString()).y === 45; } catch (e) { return false; } })(), u4.slice(0, 60));
  t("4c bez chyb ve strance ani v konzoli", q.errs.length === 0, q.errs.slice(0, 3));
  await q.ctx.close();

  console.log("\n## 5) generator 01 (system 30): okno je i tam (automaticky u kazdeho generatoru)");
  const r = await mk(browser);
  await load(r, "/stul-konfigurator.html", "", "");
  const o5 = await okno(r);
  t("5a okno Vzhled je i u generatoru 01 (system 30), sbalene", o5 && !o5.hidden && o5.vidim && o5.zavrene && !o5.iframe, o5);
  await r.page.click(".mw-win-vzhled .mw-win-h");
  const fr5 = await iframeHotov(r);
  t("5b po rozbaleni se nacte a bezi", await fr5.evaluate(() => window.__v3d.state().ready && !document.querySelector("#vzhledPanel").hidden));
  t("5c bez chyb ve strance ani v konzoli", r.errs.length === 0, r.errs.slice(0, 3));
  await r.ctx.close();

  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e); process.exit(2); });
