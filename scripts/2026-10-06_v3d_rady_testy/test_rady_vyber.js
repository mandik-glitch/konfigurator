// 3D prohlizec online nabidky / kontrolni sceny: tlacitka pohybu ve VICE RADACH podle strany (motions[].g) + VYBER KOMPONENTU s jeho rozmery (bot10, 2026-10-06; Robert: "interaktivni tlacitka musi byt ve
// vice radach a rozlisena pro kterou jsou stranu, zaroven nech se vybranemu komponentu zobrazi rozmery"). SKUTECNA stranka kontrola.html (rezim=nabidka) + SKUTECNY viewer3d.js v prohlizeci proti falesnemu
// serveru (zadna sit, zadna DB); testovaci GLB vyrabi vyrob_glb.py (slouceni dvou hotovych modelu pres api/v3d_merge.py + doplneni g). Kandidat pred nasazenim:
//   VIEWER_JS=<viewer3d.js> V3D_CSS=<v3d.css> node test_rady_vyber.js
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const REPO = path.resolve(__dirname, "..", ".."), WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const over = {};
if (process.env.VIEWER_JS) over["/js/v3d/viewer3d.js"] = process.env.VIEWER_JS;
if (process.env.V3D_CSS) over["/css/v3d.css"] = process.env.V3D_CSS;
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), "rady_glb_"));
cp.execFileSync(path.join(REPO, "api/venv/bin/python3"), ["-B", path.join(__dirname, "vyrob_glb.py"), TMP], { stdio: ["ignore", "pipe", "inherit"] });
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
let glb = "dvoustrane";
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ product: { id: +m[1], name: "Atrapa karta " + m[1] } })); }
  if (/^\/api\/kontrola-scena\/v3d\/[\d+]+\.glb$/.test(p)) { res.writeHead(200, { "Content-Type": "model/gltf-binary" }); return res.end(fs.readFileSync(path.join(TMP, glb + ".glb"))); }
  if (p === "/api/public/v3d-vzhled") { res.writeHead(200, { "Content-Type": "application/json" }); return res.end('{"env":null,"alu":null,"ao":null}'); }
  if (p.startsWith("/api/")) { res.writeHead(404, { "Content-Type": "application/json" }); return res.end("{}"); }
  const f = over[p] || path.join(WEB, p);
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
const SHOT = process.env.SHOT || "";
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  async function otevri(variant, w, h, items) {
    glb = variant;
    const ctx = await browser.newContext({ viewport: { width: w || 1280, height: h || 800 }, locale: "cs-CZ" });
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
    await page.goto(`${base}/kontrola.html?items=${items || "vd:4965+4964"}&rezim=nabidka`, { waitUntil: "load" });
    await page.waitForFunction(() => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText), null, { timeout: 120000 });
    await page.waitForTimeout(1500);
    return { ctx, page, errs };
  }
  const radky = (page) => page.evaluate(() => [...document.querySelectorAll(".v3d-chiprow")].map((r) => ({ cls: r.className, lbl: (r.querySelector(".v3d-chiprow__lbl") || {}).textContent || null,
    chips: [...r.querySelectorAll("[data-motion]")].map((b) => b.textContent.trim()), vse: [...r.querySelectorAll("[data-act]")].map((b) => b.getAttribute("data-act") + ":" + (b.getAttribute("data-g") || "")),
    otevrene: r.querySelectorAll("[data-motion].is-open").length, vybrany: [...r.querySelectorAll("[data-motion].is-sel")].map((b) => b.textContent.trim()) })));
  const cislovani = (chips) => { const m = {}; chips.forEach((c) => { const mm = /^(.*) (\d+)$/.exec(c); if (mm) (m[mm[1]] = m[mm[1]] || []).push(+mm[2]); }); return Object.keys(m).every((k) => m[k].join() === m[k].map((_, i) => i + 1).join()); };
  const cekejSel = (page, n) => page.waitForFunction((n) => document.querySelectorAll('.v3d-dim--sel').length === n, n, { timeout: 15000, polling: 100 }).catch(() => {});      // popisky kot (CSS2D) se do DOM dostanou az pri dalsim vykresleni
  const sel = (page) => page.evaluate(() => ({ id: window.__v3d.selectedMotion(), labels: window.__v3d.selDimsLabels(), dom: [...document.querySelectorAll(".v3d-dim--sel")].map((e) => e.textContent), chips: document.querySelectorAll(".v3d-chip.is-sel").length }));

  console.log("\n## A) dvoustranna scena (leva + prava), 1280 x 800");
  let c = await otevri("dvoustrane");
  let r = await radky(c.page);
  t("A1 dve rady: Levá strana a Pravá strana (barevne tridy left / right), obe s cipy", r.length === 2 && /--left/.test(r[0].cls) && /--right/.test(r[1].cls) && r[0].lbl === "Levá strana" && r[1].lbl === "Pravá strana" && r[0].chips.length === 39 && r[1].chips.length === 41, r.map((x) => [x.cls, x.lbl, x.chips.length]));
  t("A2 cislovani cipu zacina v kazde rade znovu od 1 (po druhu: Suplik 1..N)", cislovani(r[0].chips) && cislovani(r[1].chips) && r[0].chips.includes("Šuplík 1") && r[1].chips.includes("Šuplík 1"), [r[0].chips.slice(0, 4), r[1].chips.slice(0, 4)]);
  t("A3 kazda rada ma SVE Otevrit vse + Zavrit vse (data-g left / right), zadne spolecne mimo rady", r[0].vse.join() === "openall:left,closeall:left" && r[1].vse.join() === "openall:right,closeall:right" && await c.page.evaluate(() => document.querySelectorAll(".v3d-chips > .v3d-chipall").length === 0));
  const geo = await c.page.evaluate(() => { const br = document.querySelector(".v3d-br").getBoundingClientRect(), ch = document.querySelector(".v3d-chips").getBoundingClientRect(); return { brBottom: Math.round(br.bottom), chipsTop: Math.round(ch.top), h: getComputedStyle(document.querySelector(".v3d-root")).getPropertyValue("--v3d-chips-h").trim(), hscroll: document.documentElement.scrollWidth > innerWidth + 1 }; });
  t("A4 zoom tlacitka vpravo jsou NAD vicerady (nepreklapaji se), promenna vysky nastavena, bez vodorovneho posunu stranky", geo.brBottom <= geo.chipsTop + 1 && /^\d+px$/.test(geo.h) && parseInt(geo.h, 10) > 80 && !geo.hscroll, geo);
  if (SHOT) await c.page.screenshot({ path: SHOT + "_dvoustrane.png", timeout: 60000 }).catch(() => {});
  await c.page.click('[data-act="openall"][data-g="left"]'); await c.page.waitForTimeout(2500);
  r = await radky(c.page);
  t("A5 Otevrit vse v rade LEVE strany otevre jen levou stranu (prava zustane zavrena)", r[0].otevrene >= 1 && r[1].otevrene === 0, r.map((x) => x.otevrene));
  await c.page.click('[data-act="openall"][data-g="right"]'); await c.page.waitForTimeout(2500);
  r = await radky(c.page);
  t("A6 Otevrit vse v rade PRAVE strany otevre pravou, leva zustane otevrena", r[0].otevrene >= 1 && r[1].otevrene >= 1, r.map((x) => x.otevrene));
  await c.page.click('[data-act="closeall"][data-g="left"]'); await c.page.waitForTimeout(2500);
  r = await radky(c.page);
  t("A7 Zavrit vse v rade leve strany zavre jen levou", r[0].otevrene === 0 && r[1].otevrene >= 1, r.map((x) => x.otevrene));
  await c.page.click('[data-act="closeall"][data-g="right"]'); await c.page.waitForTimeout(2000);
  // vyber komponentu
  await c.page.locator(".v3d-chiprow--right [data-motion]").first().click(); await cekejSel(c.page, 3);
  let s = await sel(c.page); r = await radky(c.page);
  t("A8 klik na cip prave strany vybere komponent: prave jeden cip is-sel (v prave rade) a 3 rozmery (sirka, vyska, hloubka) v obraze", s.chips === 1 && r[1].vybrany.length === 1 && r[0].vybrany.length === 0 && s.labels.length === 3 && s.dom.length === 3 && s.dom.every((x) => /^[\d  ]+ mm$/.test(x)), [s, r.map((x) => x.vybrany)]);
  if (SHOT) await c.page.screenshot({ path: SHOT + "_vyber.png", timeout: 60000 }).catch(() => {});
  await c.page.locator(".v3d-chiprow--left [data-motion]").first().click(); await c.page.waitForFunction(() => window.__v3d.selectedMotion() && document.querySelector(".v3d-chiprow--left .is-sel"), null, { timeout: 15000 }).catch(() => {}); await cekejSel(c.page, 3);
  s = await sel(c.page); r = await radky(c.page);
  t("A9 vyber jineho komponentu (leva strana) presune vyber, stare rozmery zmizi (porad jen 3 popisky)", s.chips === 1 && r[0].vybrany.length === 1 && r[1].vybrany.length === 0 && s.dom.length === 3, [s, r.map((x) => x.vybrany)]);
  await c.page.click('[data-grp="dims"][data-v="0"]'); await c.page.waitForTimeout(1500); await cekejSel(c.page, 3);
  s = await sel(c.page);
  t("A10 rozmery vybraneho komponentu zustavaji videt i kdyz jsou Koty vypnute (Vyp)", s.dom.length === 3 && await c.page.evaluate(() => [...document.querySelectorAll(".v3d-dim--sel")].every((e) => getComputedStyle(e).display !== "none" && e.parentNode && e.offsetParent !== null || e.getBoundingClientRect().width > 0)), s);
  await c.page.mouse.click(40, 430); await cekejSel(c.page, 0);
  s = await sel(c.page);
  t("A11 klik do prazdna (mimo model) zrusi vyber: zadny is-sel, zadne rozmery komponentu", s.id === null && s.chips === 0 && s.dom.length === 0, s);
  await c.page.locator(".v3d-chiprow--right [data-motion]").nth(2).click(); await c.page.waitForTimeout(800);
  t("A12 (priprava) vybrany komponent", (await sel(c.page)).chips === 1);
  await c.page.click('[data-act="reset"]'); await cekejSel(c.page, 0);
  s = await sel(c.page);
  t("A13 tlacitko Vychozi pohled vyber zrusi", s.id === null && s.chips === 0 && s.dom.length === 0, s);
  t("A14 bez chyb ve strance", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## B) tri strany (leva + prava + prepazka)");
  c = await otevri("trojstrane"); r = await radky(c.page);
  t("B1 tri rady v poradi Leva, Prava, Prepazka s popisky a vlastnim Otevrit/Zavrit vse; zadna rada bez strany", r.length === 3 && r.map((x) => x.lbl).join() === "Levá strana,Pravá strana,Přepážka" && /--bulkhead/.test(r[2].cls) && r.every((x) => x.vse.length === 2) && r[2].chips.length === 13, r.map((x) => [x.lbl, x.chips.length, x.vse]));
  if (SHOT) await c.page.screenshot({ path: SHOT + "_trojstrane.png", timeout: 60000 }).catch(() => {});
  t("B2 bez chyb", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## C) model bez g (jedna strana / jednotliva karta): dosavadni jedna rada");
  c = await otevri("bez_g"); r = await radky(c.page);
  const ch = await c.page.evaluate(() => ({ rows: document.querySelectorAll(".v3d-chiprow").length, modeRows: document.querySelector(".v3d-chips").classList.contains("v3d-chips--rows"), vseGlobalni: [...document.querySelectorAll(".v3d-chips > .v3d-chipall [data-act]")].map((b) => b.getAttribute("data-act") + ":" + (b.getAttribute("data-g") || "")),
    chipsH: document.querySelector(".v3d-root").style.getPropertyValue("--v3d-chips-h"), cipu: document.querySelectorAll("[data-motion]").length }));
  t("C1 bez g: zadne rady stran, jedna lista s jednim Otevrit vse + Zavrit vse (bez data-g), vyska radu se nenastavuje (vychozi 52 px)", ch.rows === 0 && !ch.modeRows && ch.vseGlobalni.join() === "openall:,closeall:" && ch.chipsH === "" && ch.cipu === 80, ch);
  await c.page.locator("[data-motion]").first().click(); await cekejSel(c.page, 3);
  s = await sel(c.page);
  t("C2 vyber komponentu a jeho rozmery funguje i bez g (jednotliva karta)", s.chips === 1 && s.dom.length === 3, s);
  t("C3 bez chyb", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## D) neplatne g (cizi retezec / cislo) se ignoruje");
  c = await otevri("spatne_g"); r = await radky(c.page);
  t("D1 neplatne g: zadne rady stran (jako bez g), cipy jsou vsechny", r.length === 0 && await c.page.evaluate(() => document.querySelectorAll("[data-motion]").length === 80), r.length);
  t("D2 bez chyb", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log("\n## E) mobil 390 x 844, dvoustranna scena");
  c = await otevri("dvoustrane", 390, 844); r = await radky(c.page);
  const mob = await c.page.evaluate(() => { const ch = document.querySelector(".v3d-chips").getBoundingClientRect(), br = document.querySelector(".v3d-br").getBoundingClientRect(), root = document.querySelector(".v3d-root").getBoundingClientRect(), lbl = document.querySelector(".v3d-chiprow__lbl").getBoundingClientRect();
    const rows = [...document.querySelectorAll(".v3d-chiprow")].map((x) => ({ w: Math.round(x.getBoundingClientRect().width), scroll: x.scrollWidth > x.clientWidth })); return { chipsInside: ch.left >= root.left - 1 && ch.right <= root.right + 1, brAbove: br.bottom <= ch.top + 1, lblW: Math.round(lbl.width), rows, hscroll: document.documentElement.scrollWidth > innerWidth + 1 }; });
  t("E1 mobil: rady uvnitr platna, zoom nad nimi, popisek strany neslisovany, kazda rada se da posouvat do strany, stranka bez vodorovneho posunu", r.length === 2 && mob.chipsInside && mob.brAbove && mob.lblW >= 60 && mob.rows.every((x) => x.scroll && x.w <= 390) && !mob.hscroll, mob);
  if (SHOT) await c.page.screenshot({ path: SHOT + "_mobil.png", timeout: 60000 }).catch(() => {});
  t("E2 bez chyb", c.errs.length === 0, c.errs); await c.ctx.close();

  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  await browser.close(); server.close(); fs.rmSync(TMP, { recursive: true, force: true });
  process.exit(bad ? 1 : 0);
})();
