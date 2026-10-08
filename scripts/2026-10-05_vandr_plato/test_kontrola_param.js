// Test rezimu rezim=param v kontrola.html (parametricky komponent: vysuvne plato Vandr, sirka na posuvniku) - bot10, 2026-10-05.
// SKUTECNY prohlizec + SKUTECNY viewer3d.js (CDN three r128) + SKUTECNE GLB; staticky server si stranku a GLB bere z webapp/ (brana pro zamestnance je v Flasku a tu tenhle test
// obchazi - testuje se jen stranka). Prepis souboru: KONTROLA_HTML=<cesta>, PLATO_GLB=<cesta> (kandidat pred nasazenim do webapp/).
//   node scripts/2026-10-05_vandr_plato/test_kontrola_param.js          (env SHOT=<predpona> ulozi snimky pro vizualni kontrolu)
// Hlida: natazeni podle roviny na skutecnych vrcholech (profily a dno se prodlouzi PRESNE o zmenu sirky, nohy se jen posunou o pulku zmeny a nezmeni rozmer),
// celkova sirka = zvolena, posuvnik / cislo / predvolby jsou propojene, mimo rozsah se oreze, zadne chyby ve strance, mobil bez horizontalniho posuvu.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const WEB = "/opt/konfigurator/webapp", SHOT = process.env.SHOT || "";
const GLB_URL = "/katalog/vandr/param/plato_vysuvne.glb";
const over = {};
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
if (process.env.PLATO_GLB) over[GLB_URL] = process.env.PLATO_GLB;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream", ".svg": "image/svg+xml" };
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const blizko = (a, b, eps) => Math.abs(a - b) <= (eps || 0.03);
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const f = over[p] || path.join(WEB, p);
  if (!over[p] && !path.resolve(f).startsWith(WEB)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nenalezeno"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
const nacti = async (page, base, w, h) => {
  await page.setViewportSize({ width: w, height: h });
  await page.goto(`${base}/kontrola.html?rezim=param&model=plato_vysuvne`, { waitUntil: "load" });
  await page.waitForFunction(() => window.__plato && window.__plato.state().hotovo, null, { timeout: 90000, polling: 200 });
  await page.waitForTimeout(1500);
};
const mesh = (page) => page.evaluate(() => window.__plato.mesh());
const najdi = (m, jmeno) => m.filter((x) => x.jmeno === jmeno);
(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "cs-CZ" });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource.*404/.test(m.text())) errs.push("console: " + m.text()); });

  console.log("\n## 1) nacteni: model, parametrizace, vychozi stav");
  await nacti(page, base, 1280, 800);
  const st = await page.evaluate(() => window.__plato.state());
  t("1a model nese parametrizaci a 33 casti", st.param && st.meshy === 33 && st.W === st.param.w0, [st.meshy, st.W]);
  t("1b parametrizace: osa z, rovina 0, vychozi 1057, rozsah 449-1679 (delka profilu 20x40 300-1530, Robert)", st.param.os === 2 && st.param.rovina === 0 && st.param.w0 === 1057 && st.param.wmin === 449 && st.param.wmax === 1679, st.param);
  t("1c natahuji se prave podelne profily (2 ks, 908) a dno CUB6 (1 ks, 917)", JSON.stringify(st.param.natahovane.map((n) => [n.dil, n.ks, n.delka0])) === JSON.stringify([["20x40x908_Zx4", 2, 908], ["CUB6_915x413", 1, 917]]), st.param.natahovane);
  const m0 = await mesh(page);
  const delka0 = (jm) => najdi(m0, jm).map((x) => x.zmax - x.zmin);
  t("1d vychozi delky: profily 908, dno 917", delka0("20x40x908_Zx4").concat(delka0("20x40x908_Zx4_2")).every((d) => blizko(d, 908, 0.05)) && blizko(delka0("CUB6_915x413")[0], 917, 0.05), [delka0("20x40x908_Zx4"), delka0("CUB6_915x413")]);
  const vse0 = [Math.min(...m0.map((x) => x.zmin)), Math.max(...m0.map((x) => x.zmax))];
  const nohy0 = m0.filter((x) => x.jmeno.startsWith("45x45x1700_noha")).sort((a, b) => a.zmin - b.zmin);       // three.js druhe nohe prida priponu (_1)
  t("1e dve nohy 45 mm tlusté (predni a zadni), vzdalenost = svetlost 967 + 45", nohy0.length === 2 && nohy0.every((n) => blizko(n.zmax - n.zmin, 45, 0.05)) && blizko(Math.max(...nohy0.map((n) => n.zmin)) - Math.min(...nohy0.map((n) => n.zmax)), 967, 0.1), nohy0);
  t("1f HUD: posuvnik, cislo a 4 predvolby, bez horizontalniho posuvu", await page.evaluate(() => !!document.querySelector('#paramBar input[type=range]') && !!document.querySelector('#paramBar input[type=number]') && document.querySelectorAll('#paramBar button').length === 4 && document.documentElement.scrollWidth <= window.innerWidth + 1));
  if (SHOT) await page.screenshot({ path: SHOT + "_1057.png" });

  console.log("\n## 2) zmena sirky: kontrola na skutecnych vrcholech");
  for (const W of [1679, 449, 780, 1100]) {
    await page.evaluate((w) => window.__plato.setW(w), W);
    const d = W - 1057, m = await mesh(page);
    const dl = (jm) => najdi(m, jm).map((x) => x.zmax - x.zmin);
    t(`2a W=${W}: podelne profily ${908 + d} mm (2 ks), dno ${917 + d} mm`, dl("20x40x908_Zx4").concat(dl("20x40x908_Zx4_2")).every((x) => blizko(x, 908 + d)) && blizko(dl("CUB6_915x413")[0], 917 + d), [dl("20x40x908_Zx4"), dl("20x40x908_Zx4_2"), dl("CUB6_915x413")]);
    const vse = [Math.min(...m.map((x) => x.zmin)), Math.max(...m.map((x) => x.zmax))];
    t(`2b W=${W}: celkova sirka se zmenila PRESNE o ${d} mm`, blizko((vse[1] - vse[0]) - (vse0[1] - vse0[0]), d), (vse[1] - vse[0]) - (vse0[1] - vse0[0]));
    const nohy = m.filter((x) => x.jmeno.startsWith("45x45x1700_noha")).sort((a, b) => a.zmin - b.zmin);
    t(`2c W=${W}: nohy se jen odsunuly o ${d / 2} mm na stranu, rozmer 45 mm nezmenen`, nohy.length === 2 && blizko(nohy[0].zmin - nohy0[0].zmin, -d / 2) && blizko(nohy[1].zmin - nohy0[1].zmin, d / 2) && nohy.every((n) => blizko(n.zmax - n.zmin, 45, 0.05)), nohy);
    const tuhe = m.filter((x) => !["20x40x908_Zx4", "20x40x908_Zx4_2", "CUB6_915x413"].includes(x.jmeno));
    const tuhe0 = m0.filter((x) => !["20x40x908_Zx4", "20x40x908_Zx4_2", "CUB6_915x413"].includes(x.jmeno));
    t(`2d W=${W}: ostatnich ${tuhe.length} dilu zachovalo rozmer (jen posun, zadna deformace)`, tuhe.length === tuhe0.length && tuhe.every((x, i) => blizko(x.zmax - x.zmin, tuhe0[i].zmax - tuhe0[i].zmin, 0.02)));
    t(`2e W=${W}: posuvnik, cislo i vypis ukazuji ${W}`, await page.evaluate((w) => Number(document.querySelector("#paramBar input[type=range]").value) === w && Number(document.querySelector("#paramBar input[type=number]").value) === w && document.querySelector("#paramBar .pb-sirka").textContent.includes(String(w)) && document.querySelector("#paramBar .pb-info").textContent.includes(String(908 + w - 1057)), W));
    if (SHOT && (W === 1679 || W === 449)) await page.screenshot({ path: SHOT + "_" + W + ".png" });
  }

  console.log("\n## 2b) kusovnik, cena a vaha podle sirky (pravidla Vandru; ocekavani se pocita NEZAVISLE z JSON ceniku a pevneho seznamu delkove zavislych dilu)");
  const KUS = JSON.parse(fs.readFileSync(path.join(__dirname, "kusovnik_plato.json"), "utf-8"));
  const DELKOVE = ["20x40x908_Zx4", "CUB6_917x413"];                      // dily, ktere se se sirkou protahuji (podelne profily 20x40, dno CUB6 tl. 6 mm)
  const ocekavej = (d) => {
    let cena = 0, vaha = 0; const jmena = [];
    for (const r of KUS.radky) {
      let c = r.cena, v = r.vaha, jm = r.dil;
      if (DELKOVE.includes(r.dil)) { c += r.material.cena_za_mm * d; v += r.material.vaha_za_mm * d; jm = r.dil === "CUB6_917x413" ? "CUB6_" + (917 + d) + "x413" : "20x40x" + (908 + d) + "_Zx4"; }
      cena += c * r.ks; vaha += v * r.ks; jmena.push(jm);
    }
    return { cena, vaha, jmena };
  };
  t("2f vychozi sirka: cena = cena komponentu ve Vandru (4 677,59 Kc) a vaha 7 363,94 g", Math.abs(ocekavej(0).cena - KUS.cena0) < 0.005 && Math.abs(ocekavej(0).vaha - KUS.vaha0_g) < 0.005 && KUS.cena0 === 4677.59, [ocekavej(0), KUS.cena0]);
  for (const W of [1057, 1679, 449, 900, 1234]) {
    await page.evaluate((w) => window.__plato.setW(w), W);
    const d = W - 1057, e = ocekavej(d);
    const k = await page.evaluate(() => window.__plato.kus());
    t(`2g W=${W}: cena ${e.cena.toFixed(2)} Kc, vaha ${(e.vaha / 1000).toFixed(3)} kg = nezavisly vypocet; ${k.radky.length} radku kusovniku`, k && Math.abs(k.cena - e.cena) < 0.005 && Math.abs(k.vaha - e.vaha) < 0.005 && k.radky.length === KUS.radky.length, [k && k.cena, e.cena, k && k.vaha, e.vaha]);
    t(`2h W=${W}: nazvy protazenych dilu v kusovniku (${e.jmena[3]}, ${e.jmena[4]}) a ostatni radky beze zmeny`, k.radky.map((r) => r.jm).join("|") === e.jmena.join("|") && k.radky.filter((r) => r.zmena).length === 2, k.radky.map((r) => r.jm));
    const dom = await page.evaluate(() => ({ cena: document.querySelector("#paramBar .pb-cena").textContent, radku: document.querySelectorAll("#paramBar table.pb-tab tbody tr").length, celkem: document.querySelector("#paramBar table.pb-tab tfoot td:last-child").textContent }));
    const nahrad = (x) => x.replace(/[\s  ]/g, "").replace(",", ".");
    t(`2i W=${W}: DOM ukazuje cenu a soucet tabulky = ${e.cena.toFixed(2)} Kc`, nahrad(dom.cena).includes(e.cena.toFixed(2)) && Math.abs(Number(nahrad(dom.celkem)) - e.cena) < 0.006 && dom.radku === KUS.radky.length, dom);
  }
  t("2j rozdil ceny za 1 mm sirky = 1,328 Kc (2 x profil 0,313 + dno 0,702 Kc/mm) a vahy 3,112 g/mm", await page.evaluate(() => { window.__plato.setW(1058); const a = window.__plato.kus(); window.__plato.setW(1057); const b = window.__plato.kus(); return Math.abs((a.cena - b.cena) - (2 * 0.31302 + 0.7021)) < 1e-6 && Math.abs((a.vaha - b.vaha) - (2 * 0.73 + 1.652)) < 1e-6; }));
  await page.evaluate(() => { document.querySelector("#paramBar details.pb-kus").open = true; });
  await page.waitForTimeout(500);
  t("2k po rozbaleni kusovniku se platno prizpusobi (nezasahuje pod listu) a tabulka je videt", await page.evaluate(() => { const v = document.querySelector("#viewer").getBoundingClientRect(), b = document.querySelector("#paramBar").getBoundingClientRect(); return v.bottom <= b.top + 2 && v.height > 150 && b.bottom <= window.innerHeight + 1 && document.querySelector("#paramBar table.pb-tab").getBoundingClientRect().height > 100; }));
  await page.evaluate(() => { document.querySelector("#paramBar details.pb-kus").open = false; });
  await page.waitForTimeout(300);
  if (SHOT) { await page.evaluate(() => { window.__plato.setW(1679); document.querySelector("#paramBar details.pb-kus").open = true; }); await page.waitForTimeout(400); await page.screenshot({ path: SHOT + "_kusovnik.png" }); await page.evaluate(() => { document.querySelector("#paramBar details.pb-kus").open = false; window.__plato.setW(1057); }); }

  console.log("\n## 3) ovladani: posuvnik, cislo, predvolby, meze");
  await page.evaluate(() => { const s = document.querySelector("#paramBar input[type=range]"); s.value = "900"; s.dispatchEvent(new Event("input", { bubbles: true })); });
  t("3a posuvnik 900 -> W = 900 a profily 751", (await page.evaluate(() => window.__plato.state().W)) === 900 && blizko(najdi(await mesh(page), "20x40x908_Zx4")[0].zmax - najdi(await mesh(page), "20x40x908_Zx4")[0].zmin, 908 - 157));
  await page.evaluate(() => { const n = document.querySelector("#paramBar input[type=number]"); n.value = "1234"; n.dispatchEvent(new Event("change", { bubbles: true })); });
  t("3b cislo 1234 -> W = 1234, posuvnik 1234", (await page.evaluate(() => [window.__plato.state().W, Number(document.querySelector("#paramBar input[type=range]").value)])).join() === "1234,1234");
  await page.evaluate(() => { const n = document.querySelector("#paramBar input[type=number]"); n.value = "5000"; n.dispatchEvent(new Event("change", { bubbles: true })); });
  t("3c mimo rozsah (5000) se orizne na 1679", (await page.evaluate(() => window.__plato.state().W)) === 1679);
  await page.evaluate(() => { const n = document.querySelector("#paramBar input[type=number]"); n.value = "100"; n.dispatchEvent(new Event("change", { bubbles: true })); });
  t("3d mimo rozsah (100) se orizne na 449", (await page.evaluate(() => window.__plato.state().W)) === 449);
  await page.click('#paramBar button[data-w="1057"]');
  const mz = await mesh(page);
  t("3e predvolba 1057 vrati puvodni geometrii (rozdil od vychozi do 0,02 mm)", mz.every((x, i) => blizko(x.zmin, m0[i].zmin, 0.02) && blizko(x.zmax, m0[i].zmax, 0.02)));
  t("3f predvolba 1057 je oznacena (aria-pressed)", await page.evaluate(() => document.querySelector('#paramBar button[data-w="1057"]').getAttribute("aria-pressed") === "true"));
  t("3g zadne chyby ve strance", errs.length === 0, errs.slice(0, 3));

  console.log("\n## 4) mobil 390 x 844");
  await nacti(page, base, 390, 844);
  t("4a mobil: bez horizontalniho posuvu a bar viditelny cely", await page.evaluate(() => { const b = document.querySelector("#paramBar").getBoundingClientRect(); return document.documentElement.scrollWidth <= window.innerWidth + 1 && b.left >= 0 && b.right <= window.innerWidth + 1 && b.bottom <= window.innerHeight + 1; }));
  t("4b mobil: platno nezasahuje do dolni listy", await page.evaluate(() => { const v = document.querySelector("#viewer").getBoundingClientRect(), b = document.querySelector("#paramBar").getBoundingClientRect(); return v.bottom <= b.top + 2 && v.height > 200; }));
  await page.evaluate(() => window.__plato.setW(1679));
  if (SHOT) await page.screenshot({ path: SHOT + "_mobil_1357.png" });
  t("4c mobil: zadne chyby", errs.length === 0, errs.slice(0, 3));

  console.log("\n## 5) neplatne volani");
  await page.goto(`${base}/kontrola.html?rezim=param&model=../../etc/passwd`, { waitUntil: "load" });
  await page.waitForTimeout(500);
  t("5a neplatny nazev modelu = chybova hlaska, zadny dotaz na soubor", await page.evaluate(() => /Neplatný název modelu/.test(document.querySelector("#status").textContent)));
  await page.goto(`${base}/kontrola.html?items=cs:1`, { waitUntil: "load" });
  await page.waitForTimeout(300);
  t("5b bez rezim=param se stranka chova jako dosud (bez posuvniku)", await page.evaluate(() => document.querySelector("#paramBar").hidden === true && !window.__plato));
  await browser.close(); server.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})();
