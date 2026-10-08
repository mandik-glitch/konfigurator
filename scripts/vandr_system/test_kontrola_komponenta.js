// Test kontrolni sceny pro komponentu z registru Vandr systemu u nas: kontrola.html?rezim=param&komponenta=kufrik-3x43-vysuv-d459 (bot10, 2026-10-05; docs/VANDR_SYSTEM.md).
// SKUTECNY prohlizec + SKUTECNY viewer3d.js (CDN three r128) + SKUTECNE GLB z webapp/katalog/vandr/komponenty/; staticky server (brana pro zamestnance je ve Flasku, tady se testuje jen stranka).
//   node scripts/vandr_system/test_kontrola_komponenta.js          (env SHOT=<predpona> ulozi snimky pro vizualni kontrolu; KONTROLA_HTML=<cesta> prepise stranku kandidatem)
// Ocekavani cen se pocitaji NEZAVISLE z JSON snimku ceniku (scripts/2026-10-05_vandr_plato/kusovnik_plato.json) a pevneho seznamu delkove zavislych dilu.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const WEB = "/opt/konfigurator/webapp", SHOT = process.env.SHOT || "";
const KOD = "kufrik-3x43-vysuv-d459";
const over = {};
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream" };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const blizko = (a, b, eps) => Math.abs(a - b) <= (eps || 0.03);
const pozadavky = [];
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  pozadavky.push(p);
  const f = over[p] || path.join(WEB, p);
  if (!over[p] && !path.resolve(f).startsWith(WEB)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nenalezeno"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
const nacti = async (page, base, w, h, query) => {
  await page.setViewportSize({ width: w, height: h });
  await page.goto(`${base}/kontrola.html?${query}`, { waitUntil: "load" });
  await page.waitForFunction(() => window.__plato && window.__plato.state().hotovo, null, { timeout: 90000, polling: 200 });
  await page.waitForTimeout(1500);
};
const mesh = (page) => page.evaluate(() => window.__plato.mesh());
const dlzka = (m, pred) => m.filter((x) => pred(x.jmeno)).map((x) => x.zmax - x.zmin);
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "cs-CZ" });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource.*404/.test(m.text())) errs.push("console: " + m.text()); });
  const KUS = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/2026-10-05_vandr_plato/kusovnik_plato.json", "utf-8"));
  const DELKOVE = ["20x40x908_Zx4", "CUB6_917x413"];
  const ocekavej = (d) => {
    let cena = 0, vaha = 0; const jmena = [];
    for (const r of KUS.radky) {
      let c = r.cena, v = r.vaha, jm = r.dil;
      if (DELKOVE.includes(r.dil)) { c += r.material.cena_za_mm * d; v += r.material.vaha_za_mm * d; jm = r.dil === "CUB6_917x413" ? "CUB6_" + (917 + d) + "x413" : "20x40x" + (908 + d) + "_Zx4"; }
      cena += c * r.ks; vaha += v * r.ks; jmena.push(jm);
    }
    return { cena, vaha, jmena };
  };

  console.log("\n## 1) nacteni komponenty z registru");
  await nacti(page, base, 1280, 800, "rezim=param&komponenta=" + KOD);
  const st = await page.evaluate(() => window.__plato.state());
  t("1a pozadavek na model jde do katalog/vandr/komponenty/ (ne param/)", pozadavky.some((p) => p === `/katalog/vandr/komponenty/${KOD}.glb`) && !pozadavky.some((p) => p.startsWith("/katalog/vandr/param/")), pozadavky.filter((p) => p.includes("katalog")));
  t("1b 15 casti a ZADNE nohy (jen plato)", st.meshy === 15, st.meshy);
  const m0 = await mesh(page);
  t("1c v modelu nejsou nohy 45x45x1700", !m0.some((x) => x.jmeno.startsWith("45x45x1700")), m0.map((x) => x.jmeno));
  t("1d parametry: vychozi 1057, rozsah 449-1679, svetlost 967 (= vnejsi - 90)", st.param && st.W === 1057 && st.param.wmin === 449 && st.param.wmax === 1679 && st.param.svetlost0 === 967 && st.param.w0 - st.param.svetlost0 === 90, st.param && [st.W, st.param.wmin, st.param.wmax, st.param.svetlost0]);
  const dom0 = await page.evaluate(() => ({ info: document.querySelector("#paramBar .pb-info").textContent, mala: document.querySelector("#paramBar .pb-small").textContent, top: document.querySelector("#topbar").textContent, cena: document.querySelector("#paramBar .pb-cena").textContent }));
  t("1e poznamka rika, ze komponenta je bez noh (svetla sirka = sirka - 90 mm), ne 'nohy se odsouvaji'", /komponenta je bez noh/.test(dom0.mala) && /− 90 mm/.test(dom0.mala) && !/nohy se jen odsouvají/.test(dom0.mala), dom0.mala);
  t("1f vypis ukazuje svetlost 967 mm a cenu 4 677,59 Kc", /světlost mezi nohama 967 mm/.test(dom0.info) && dom0.cena.replace(/[\s  ]/g, "").includes("4677,59"), [dom0.info, dom0.cena]);
  const vse0 = [Math.min(...m0.map((x) => x.zmin)), Math.max(...m0.map((x) => x.zmax))];
  t("1g vychozi sirka modelu 1057 mm", blizko(vse0[1] - vse0[0], 1057, 0.05), vse0[1] - vse0[0]);
  if (SHOT) await page.screenshot({ path: SHOT + "_1057.png" });

  console.log("\n## 2) natazeni a cena na krajnich sirkach (svetla 359 / 1589 mm = profil 300 / 1530 mm)");
  for (const W of [449, 1679, 780, 1100]) {
    await page.evaluate((w) => window.__plato.setW(w), W);
    const d = W - 1057, m = await mesh(page), e = ocekavej(d);
    const prof = dlzka(m, (j) => j.startsWith("20x40x908_Zx4"));
    t(`2a W=${W}: podelne profily ${908 + d} mm (2 ks), dno ${917 + d} mm`, prof.length === 2 && prof.every((x) => blizko(x, 908 + d)) && blizko(dlzka(m, (j) => j === "CUB6_915x413")[0], 917 + d), [prof, dlzka(m, (j) => j === "CUB6_915x413")]);
    const vse = [Math.min(...m.map((x) => x.zmin)), Math.max(...m.map((x) => x.zmax))];
    t(`2b W=${W}: celkova sirka PRESNE ${W} mm`, blizko(vse[1] - vse[0], W, 0.05), vse[1] - vse[0]);
    const tuhe = m.filter((x) => !["20x40x908_Zx4", "20x40x908_Zx4_2", "CUB6_915x413"].includes(x.jmeno)), tuhe0 = m0.filter((x) => !["20x40x908_Zx4", "20x40x908_Zx4_2", "CUB6_915x413"].includes(x.jmeno));
    t(`2c W=${W}: ostatnich ${tuhe.length} dilu zachovalo rozmer (jen posun)`, tuhe.length === tuhe0.length && tuhe.every((x, i) => blizko(x.zmax - x.zmin, tuhe0[i].zmax - tuhe0[i].zmin, 0.02)));
    const k = await page.evaluate(() => window.__plato.kus());
    t(`2d W=${W}: cena ${e.cena.toFixed(2)} Kc a vaha ${(e.vaha / 1000).toFixed(3)} kg = nezavisly vypocet, 11 radku`, k && Math.abs(k.cena - e.cena) < 0.005 && Math.abs(k.vaha - e.vaha) < 0.005 && k.radky.length === 11, [k && k.cena, e.cena]);
    t(`2e W=${W}: nazvy protazenych dilu v kusovniku`, k.radky.map((r) => r.jm).join("|") === e.jmena.join("|"), k.radky.map((r) => r.jm));
    const dom = await page.evaluate(() => ({ cena: document.querySelector("#paramBar .pb-cena").textContent, info: document.querySelector("#paramBar .pb-info").textContent }));
    t(`2f W=${W}: DOM ukazuje cenu ${e.cena.toFixed(2)} Kc a svetlost ${W - 90} mm`, dom.cena.replace(/[\s  ]/g, "").replace(",", ".").includes(e.cena.toFixed(2)) && dom.info.includes("světlost mezi nohama " + (W - 90) + " mm"), dom);
    if (SHOT && (W === 449 || W === 1679)) await page.screenshot({ path: SHOT + "_" + W + ".png" });
  }
  t("2g ceny na krajich: 3 870,08 Kc (svetla 359) a 5 503,69 Kc (svetla 1589)", Math.abs(ocekavej(449 - 1057).cena - 3870.08) < 0.006 && Math.abs(ocekavej(1679 - 1057).cena - 5503.69) < 0.006, [ocekavej(-608).cena, ocekavej(622).cena]);
  t("2h zadne chyby ve strance", errs.length === 0, errs.slice(0, 3));

  console.log("\n## 3) mobil 390 x 844");
  await nacti(page, base, 390, 844, "rezim=param&komponenta=" + KOD);
  t("3a mobil: bez horizontalniho posuvu, bar cely videt, platno nezasahuje pod listu", await page.evaluate(() => { const b = document.querySelector("#paramBar").getBoundingClientRect(), v = document.querySelector("#viewer").getBoundingClientRect(); return document.documentElement.scrollWidth <= window.innerWidth + 1 && b.left >= 0 && b.right <= window.innerWidth + 1 && b.bottom <= window.innerHeight + 1 && v.bottom <= b.top + 2 && v.height > 200; }));
  await page.evaluate(() => window.__plato.setW(1679));
  if (SHOT) await page.screenshot({ path: SHOT + "_mobil_1679.png" });
  t("3b mobil: zadne chyby", errs.length === 0, errs.slice(0, 3));

  console.log("\n## 4) neplatna a nezname volani");
  pozadavky.length = 0;
  for (const zly of ["../../etc/passwd", "Abc", "a_b", "a--b", "-a", "a.glb", "a%2f..%2fb"]) {
    await page.goto(`${base}/kontrola.html?rezim=param&komponenta=${zly}`, { waitUntil: "load" });
    await page.waitForTimeout(400);
    t(`4a komponenta=${zly}: chybova hlaska a zadny dotaz na model`, await page.evaluate(() => /Neplatný kód komponenty/.test(document.querySelector("#status").textContent)) && !pozadavky.some((p) => p.endsWith(".glb")), pozadavky.filter((p) => p.endsWith(".glb")));
  }
  await page.goto(`${base}/kontrola.html?rezim=param&komponenta=neexistuje-xyz`, { waitUntil: "load" });
  await page.waitForFunction(() => /nepodařilo načíst/.test(document.querySelector("#status").textContent), null, { timeout: 60000, polling: 200 });
  t("4b neexistujici komponenta: hlaska s cestou webapp/katalog/vandr/komponenty/neexistuje-xyz.glb", await page.evaluate(() => /webapp\/katalog\/vandr\/komponenty\/neexistuje-xyz\.glb/.test(document.querySelector("#status").textContent)));
  await page.goto(`${base}/kontrola.html?rezim=param`, { waitUntil: "load" });
  await page.waitForFunction(() => window.__plato && window.__plato.state().hotovo, null, { timeout: 90000, polling: 200 });
  t("4c bez komponenta= zustava puvodni plato s nohama (33 casti, katalog/vandr/param/)", (await page.evaluate(() => window.__plato.state().meshy)) === 33 && pozadavky.some((p) => p === "/katalog/vandr/param/plato_vysuvne.glb"));
  await browser.close(); server.close();
  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
