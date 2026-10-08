// Test kontrolni sceny rezim=nabidka po zmene "model s pohyby si postavi server" (bot10, 2026-10-06; Robert: "automatizovat proces bez zasahu rucne botem
// na kazdou FBX"): kontrola.html si pro kazdou kartu vd:<id> vyzada GET /api/kontrola-scena/v3d/<id>.glb (build + cache na serveru), soubor
// katalog/vandr/v3d_nahled/<id>.glb je jen zaloha, kdyz server tu trasu nema (HTML 404); chyba trasy (JSON {error}) se ukaze NAHLAS bez zalohy.
// SKUTECNY prohlizec + SKUTECNY viewer3d.js (CDN three r128) + SKUTECNE zakaznicke GLB (v3d_nahled/4918, 4921 - vystup stejneho buildu); server je ATRAPA
// (trasa /api/kontrola-scena/... je simulovana, brana pro zamestnance je ve Flasku a tu tenhle test nezkousi - ta ma vlastni testy v test_kontrola_route.py).
//   node scripts/2026-10-02_v3d_testy/test_kontrola_nabidka_auto.js        (env KONTROLA_HTML=<cesta> = kandidat stranky pred nasazenim; SHOT=<predpona> ulozi snimky)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path");
const WEB = process.env.WEB_DIR || "/opt/konfigurator/webapp", SHOT = process.env.SHOT || "";          // kandidat pred nasazenim: WEB_DIR=<prekryv webapp>
const over = {};
if (process.env.KONTROLA_HTML) over["/kontrola.html"] = process.env.KONTROLA_HTML;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".hdr": "application/octet-stream" };
// "vyrobene serverem": karta -> skutecny zakaznicky GLB (jine pohyby, aby se dalo poznat, ktery model je videt)
const SERVER_GLB = { 4965: "4918", 4964: "4921", 4963: "4918", 4967: "4921", 4968: "4918" };
const motionsOf = (id) => {
  const b = fs.readFileSync(path.join(WEB, "katalog/vandr/v3d_nahled", id + ".glb"));
  const js = JSON.parse(b.slice(20, 20 + b.readUInt32LE(12)).toString("utf-8"));
  return js.scenes[0].extras.v3d.motions.length;
};
const M4918 = motionsOf("4918"), M4921 = motionsOf("4921");
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };

let scenario = "ok", zpozdeni = {};
let spolScenario = "ok", spolZpozdeni = 0;
const spolPosty = [];
let prehledScenario = "ok"; let prehledPozadavku = 0;
const MASTER = "Regálová vestavba – Renault Master L2H2", VW = "Regálová vestavba – VW Crafter L3H3 FWD";
const PREHLED = { kartas: [
  { shop_product_id: 4965, name: MASTER, umisteni_kod: "RL", umisteni_nazev: "Regál levý", glb: true, cena: true, web: true },
  { shop_product_id: 4964, cena_czk: 22563, name: MASTER, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: true, cena: true, web: true },
  { shop_product_id: 4963, cena_czk: 23245, name: MASTER, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: true, cena: true, web: true },
  { shop_product_id: 4962, name: MASTER, umisteni_kod: "RL", umisteni_nazev: "Regál levý", glb: true, cena: true, web: true },
  { shop_product_id: 4925, cena_czk: 30614, name: MASTER, umisteni_kod: "RK", umisteni_nazev: "Regál — kabina (za přepážkou)", glb: true, cena: true, web: true },
  { shop_product_id: 4960, cena_czk: 51000, name: MASTER, umisteni_kod: null, umisteni_nazev: "", glb: true, cena: true, web: true },       // bez umisteni (kombinace) se nenabizi
  { shop_product_id: 4966, name: MASTER, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: false, cena: true, web: true },
  { shop_product_id: 4961, name: MASTER, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: true, cena: false, web: true },
  { shop_product_id: null, name: MASTER, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: true, cena: true, web: true },
  { shop_product_id: 4967, name: VW, umisteni_kod: "RL", umisteni_nazev: "Regál levý", glb: true, cena: true, web: true },
  { shop_product_id: 4968, name: VW, umisteni_kod: "RP", umisteni_nazev: "Regál pravý", glb: true, cena: true, web: true } ] };
const pozadavky = [], vydane = {};
const server = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"), p = decodeURIComponent(u.pathname);
  pozadavky.push(p);
  if (req.method === "GET" && p === "/api/admin/vandr-vyroba/prehled") {                 // vyber dalsi strany spolecne nabidky (sourozenecke karty)
    prehledPozadavku++;
    if (prehledScenario === "403") { res.writeHead(403, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ error: "Nemáte oprávnění." })); }
    if (prehledScenario === "500") { res.writeHead(500, { "Content-Type": "text/html" }); return res.end("<h1>chyba</h1>"); }
    if (prehledScenario === "sit") return req.socket.destroy();
    res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify(prehledScenario === "prazdne" ? { kartas: [] } : PREHLED));
  }
  if (req.method === "POST" && p === "/api/admin/vandr-vyroba/nabidka-spolecna") {       // spolecna nabidka (tlacitko v horni liste u skupiny karet)
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      spolPosty.push({ ct: req.headers["content-type"], body });
      setTimeout(() => {
        const J = (st, o) => { res.writeHead(st, { "Content-Type": "application/json" }); res.end(JSON.stringify(o)); };
        let karty = []; try { karty = JSON.parse(body).karty; } catch (e) { /* test chyby */ }
        if (spolScenario === "sit") return req.socket.destroy();
        if (spolScenario === "html502") { res.writeHead(502, { "Content-Type": "text/html" }); return res.end("<h1>Bad Gateway</h1>"); }
        if (spolScenario === "chyba400") return J(400, { error: "Karty jsou pro různá vozidla (Renault Master, VW Crafter) – do společné nabídky patří jen karty téhož vozu." });
        if (spolScenario === "chyba-xss") return J(400, { error: "<b>tučně</b><img src=x onerror=window.__xss=1>" });
        if (spolScenario === "401") return J(401, { error: "Neprihlaseno.", code: "unauthorized" });
        const o = { status: "ok", offer_id: 7, offer_number: "N-2026-0007", online_url: "/nabidka-online.html?t=TOKENTOKEN1234", karty, cena_celkem: 70394, v3d: true, v3d_duvod: null };
        if (spolScenario === "bez3d") Object.assign(o, { v3d: false, v3d_duvod: "uložení 3D modelu selhalo: disk plný" });
        if (spolScenario === "xss") Object.assign(o, { offer_number: "<img src=x onerror=window.__xss=1>", online_url: "javascript:window.__xss=1" });
        return J(201, o);
      }, spolZpozdeni);
    });
    return;
  }
  let m = /^\/api\/kontrola-scena\/vd\/(\d+)$/.exec(p);
  if (m) { res.writeHead(200, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ product: { id: +m[1], name: "Atrapa karta " + m[1] } })); }
  m = /^\/api\/kontrola-scena\/v3d\/(\d+)((?:\+\d+){0,2})\.glb$/.exec(p);
  if (m) {
    const id = +m[1];                       // u skupiny karet (4965+4964) atrapa vrati model PRVNI karty (slouceni ma vlastni testy)
    if (scenario === "chybi-trasa") { res.writeHead(404, { "Content-Type": "text/html" }); return res.end("<!doctype html><title>404</title><h1>Not Found</h1>"); }
    if (scenario === "chyba-500") { res.writeHead(500, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ error: "3D model nevznikl: Blender: chybí materiál X" })); }
    if (scenario === "chyba-401") { res.writeHead(401, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ error: "Neprihlaseno.", code: "unauthorized" })); }
    const f = SERVER_GLB[id] && path.join(WEB, "katalog/vandr/v3d_nahled", SERVER_GLB[id] + ".glb");
    if (!f) { res.writeHead(400, { "Content-Type": "application/json" }); return res.end(JSON.stringify({ error: "Karta ještě nemá hotový 3D model (konverze nedoběhla)." })); }
    vydane[id] = (vydane[id] || 0) + 1;
    return setTimeout(() => { res.writeHead(200, { "Content-Type": "model/gltf-binary", "Cache-Control": "private, no-store", "X-V3D-Cache": vydane[id] > 1 ? "hit" : "miss" }); res.end(fs.readFileSync(f)); }, zpozdeni[id] || 0);
  }
  const f = over[p] || path.join(WEB, p);
  if (!over[p] && !path.resolve(f).startsWith(WEB)) { res.writeHead(403); return res.end(); }
  fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nenalezeno"); } res.writeHead(200, { "Content-Type": MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
});
const info = (page) => page.evaluate(() => document.querySelector("#topbar").innerText);
const status = (page) => page.evaluate(() => { const s = document.querySelector("#status"); return { text: s.textContent, err: s.classList.contains("err") }; });
const pockej = (page, fn, arg, ms) => page.waitForFunction(fn, arg, { timeout: ms || 60000, polling: 150 });
const pocet = (re) => pozadavky.filter((p) => re.test(p)).length;

(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: "cs-CZ" });
  const page = await ctx.newPage();
  let dialogOdpoved = "dismiss"; const dialogy = [];       // confirm() u tlacitka spolecne nabidky: vychozi = zamitnout (nic se nezaklada)
  page.on("dialog", async (d) => { dialogy.push(d.message()); if (dialogOdpoved === "accept") await d.accept(); else await d.dismiss(); });
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  const otevri = async (query) => { pozadavky.length = 0; Object.keys(vydane).forEach((k) => delete vydane[k]); await page.goto(`${base}/kontrola.html?${query}`, { waitUntil: "load" }); };

  console.log("\n## 1) server postavi model (trasa existuje)");
  scenario = "ok"; zpozdeni = {};
  await otevri("items=vd:4965,vd:4964&rezim=nabidka");
  await pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  let i = await info(page);
  t("1a model karty 4965 se vyzadal ze serveru (trasa /api/kontrola-scena/v3d/4965.glb)", pocet(/^\/api\/kontrola-scena\/v3d\/4965\.glb$/) === 1, pozadavky.filter((p) => p.includes("4965")));
  t("1b hotovy soubor v3d_nahled se NEpouzil (model ze serveru ma prednost)", pocet(/v3d_nahled\/4965\.glb/) === 0 && pocet(/v3d_nahled\/\d+\.glb/) === 0, pozadavky.filter((p) => p.includes("v3d_nahled")));
  t("1c popisek: karta 4965, jmeno z API, pohyblivych dilu = pohyby modelu ze serveru, 'postaveno serverem (novy build)'",
    /karta 4965/.test(i) && /Atrapa karta 4965/.test(i) && new RegExp("pohyblivých dílů " + M4918 + "\\b").test(i) && /postaveno serverem \(nový build\)/.test(i), i);
  t("1d zadna chyba ve stavovem radku", (await status(page)).text === "", await status(page));
  if (SHOT) await page.screenshot({ path: SHOT + "_server_4965.png" });
  await page.click("#nextBtn");
  await pockej(page, () => /karta 4964/.test(document.querySelector("#topbar").innerText) && /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  i = await info(page);
  t("1e dalsi polozka (4964) se postavi take serverem a ukazuje svoje pohyby", pocet(/^\/api\/kontrola-scena\/v3d\/4964\.glb$/) === 1 && new RegExp("pohyblivých dílů " + M4921 + "\\b").test(i), i);
  await page.click("#prevBtn");
  await pockej(page, () => /karta 4965/.test(document.querySelector("#topbar").innerText) && /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  t("1f navrat na 4965 je z pameti stranky (zadny dalsi dotaz na server) a pohyby sedi", pocet(/^\/api\/kontrola-scena\/v3d\/4965\.glb$/) === 1 && new RegExp("pohyblivých dílů " + M4918 + "\\b").test(await info(page)), pozadavky.filter((p) => p.includes("v3d/")));

  console.log("\n## 2) rychle prepnuti: pomaly model se nesmi prepsat na jiny (race)");
  scenario = "ok"; zpozdeni = { 4965: 1800, 4964: 150 };
  await otevri("items=vd:4965,vd:4964&rezim=nabidka");
  await page.waitForTimeout(300);
  await page.click("#nextBtn");                       // 4965 jeste stavi (1,8 s), prepnuto na 4964
  await pockej(page, () => /karta 4964/.test(document.querySelector("#topbar").innerText) && /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  await page.waitForTimeout(2500);                    // pomala odpoved 4965 mezitim dorazila
  i = await info(page);
  t("2a po dobehnuti pomale odpovedi zustava 4964 (karta 4964, jeho pohyby)", /karta 4964/.test(i) && new RegExp("pohyblivých dílů " + M4921 + "\\b").test(i) && !/karta 4965/.test(i), i);
  zpozdeni = {};

  console.log("\n## 3) server tu trasu nema (pred nasazenim API) -> zaloha: hotovy soubor");
  scenario = "chybi-trasa";
  await otevri("items=vd:4918&rezim=nabidka");
  await pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  i = await info(page);
  t("3a zkusi se trasa, pak soubor katalog/vandr/v3d_nahled/4918.glb", pocet(/^\/api\/kontrola-scena\/v3d\/4918\.glb$/) === 1 && pocet(/^\/katalog\/vandr\/v3d_nahled\/4918\.glb$/) === 1, pozadavky.filter((p) => p.includes("4918")));
  t("3b popisek rika 'ze souboru (stary postup ...)' a ukazuje pohyby souboru", /ze souboru \(starý postup/.test(i) && new RegExp("pohyblivých dílů " + M4918 + "\\b").test(i), i);
  t("3c bez chyby ve stavovem radku", (await status(page)).text === "", await status(page));

  console.log("\n## 4) chyba trasy se ukaze nahlas, na soubor se NEpada");
  scenario = "chyba-500";
  await otevri("items=vd:4918&rezim=nabidka");
  await pockej(page, () => document.querySelector("#status").textContent !== "");
  let s = await status(page);
  t("4a stavovy radek: 'Model karty 4918: 3D model nevznikl: Blender: chybi material X' (cerveny)", s.err && s.text === "Model karty 4918: 3D model nevznikl: Blender: chybí materiál X", s);
  t("4b hotovy soubor se nepouzil (kontrola nesmi tise ukazat jiny model, nez uvidi zakaznik)", pocet(/v3d_nahled\/4918\.glb/) === 0, pozadavky.filter((p) => p.includes("v3d_nahled")));
  scenario = "chyba-401";
  await otevri("items=vd:4918&rezim=nabidka");
  await pockej(page, () => document.querySelector("#status").textContent !== "");
  s = await status(page);
  t("4c neprihlaseny (401): 'Model karty 4918: Neprihlaseno.' a zadny soubor", s.err && s.text === "Model karty 4918: Neprihlaseno." && pocet(/v3d_nahled/) === 0, s);
  scenario = "ok";
  await otevri("items=vd:9999&rezim=nabidka");          // karta bez hotoveho modelu: server vraci JSON 400
  await pockej(page, () => document.querySelector("#status").textContent !== "");
  s = await status(page);
  t("4d karta bez hotoveho modelu: ceska veta ze serveru, bez zalohy", s.err && /ještě nemá hotový 3D model/.test(s.text) && pocet(/v3d_nahled/) === 0, s);

  console.log("\n## 5) ostatni chovani beze zmeny");
  await otevri("items=cs:1&rezim=nabidka");
  await page.waitForTimeout(800);
  s = await status(page);
  t("5a nativni polozky (cs:/pa:) hlasi dosavadni text a nevolaji trasu", /Režim nabídka zatím umí jen Vandr karty/.test(s.text) && pocet(/kontrola-scena\/v3d/) === 0, s);
  t("5b zadne chyby ve strance (JS)", errs.length === 0, errs.slice(0, 3));
  console.log("\n## 6) skupina karet vd:a+b (spolecna nabidka): jeden slouceny model, '+' z adresy (v query = mezera)");
  scenario = "ok"; zpozdeni = {};
  await otevri("items=vd:4965+4964&rezim=nabidka");
  await pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  i = await info(page);
  t("6a jeden pozadavek na model skupiny /api/kontrola-scena/v3d/4965+4964.glb (ne dva samostatne)", pocet(/^\/api\/kontrola-scena\/v3d\/4965\+4964\.glb$/) === 1 && pocet(/^\/api\/kontrola-scena\/v3d\/\d+\.glb$/) === 0, pozadavky.filter((p) => p.includes("v3d/")));
  t("6b popisek: 'karty 4965 + 4964', jmeno prvni karty '(+1 další)', 'postaveno serverem'", /karty 4965 \+ 4964/.test(i) && /Atrapa karta 4965 \(\+1 další\)/.test(i) && /postaveno serverem/.test(i), i);
  t("6c popisek v dolni liste: vd:4965+4964 (jedna polozka, bez tlacitek dalsi/predchozi)", await page.evaluate(() => document.querySelector("#hud").hidden === true), await page.evaluate(() => document.querySelector("#hud").hidden));
  await otevri("items=vd:4965%2B4964,vd:4965&rezim=nabidka");               // '+' zakodovane jako %2B + druha polozka
  await pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  t("6d '%2B' funguje stejne, dve polozky v prepinaci (1 / 2) a popisek 'vd:4965+4964'", await page.evaluate(() => /1 \/ 2/.test(document.querySelector("#idxLabel").textContent) && /vd:4965\+4964/.test(document.querySelector("#nameLabel").textContent)), await page.evaluate(() => [document.querySelector("#idxLabel").textContent, document.querySelector("#nameLabel").textContent]));
  for (const [q, nazev] of [["items=vd:4965+4965&rezim=nabidka", "duplicita"], ["items=vd:1+2+3+4&rezim=nabidka", "ctyri karty"], ["items=vd:4965+4964", "skupina mimo rezim=nabidka"], ["items=cs:1+2&rezim=nabidka", "skupina nativnich"], ["items=vd:4965+x&rezim=nabidka", "neplatne id"]]) {
    await otevri(q);
    await page.waitForTimeout(500);
    s = await status(page);
    t(`6e ${nazev}: 'Neplatný formát ?items=' a zadny dotaz na model`, /Neplatný formát \?items=/.test(s.text) && pocet(/kontrola-scena\/v3d/) === 0, [s.text, pozadavky.filter((p) => p.includes("v3d/"))]);
  }
  console.log("\n## 7) tlacitko 'Vytvorit spolecnou nabidku' u skupiny karet (POST /api/admin/vandr-vyroba/nabidka-spolecna)");
  const spolStavTxt = () => page.evaluate(() => { const b = document.querySelector("#spolBtn"), st = document.querySelector("#spolStav");
    return { jeBtn: !!b && !!b.offsetParent, disabled: b ? b.disabled : null, text: st ? st.textContent : "", cls: st ? st.className : "", html: st ? st.innerHTML : "",
             odkazy: st ? [...st.querySelectorAll("a")].map((a) => ({ href: a.getAttribute("href"), target: a.target, rel: a.rel, text: a.textContent })) : [], xss: !!window.__xss }; });
  const cekejModel = () => pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  const klikSpol = async (odpoved) => { dialogOdpoved = odpoved; dialogy.length = 0; await page.click("#spolBtn"); };
  scenario = "ok"; zpozdeni = {}; spolScenario = "ok"; spolZpozdeni = 0; spolPosty.length = 0;
  await otevri("items=vd:4965&rezim=nabidka"); await cekejModel();
  let sp = await spolStavTxt();
  t("7a jedna karta: tlacitko spolecne nabidky se NEukazuje", sp.jeBtn === false, sp);
  await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
  sp = await spolStavTxt();
  t("7b skupina karet: v horni liste je povolene tlacitko, bez stavu", sp.jeBtn && !sp.disabled && sp.text === "", sp);
  await klikSpol("dismiss"); await page.waitForTimeout(400);
  t("7c zamitnuty dialog: otazka s cisly karet, zadny POST, zadny stav", dialogy.length === 1 && /karet 4965 \+ 4964/.test(dialogy[0]) && spolPosty.length === 0 && (await spolStavTxt()).text === "", [dialogy, spolPosty.length]);
  await klikSpol("accept");
  await pockej(page, () => /Hotovo/.test(document.querySelector("#spolStav").textContent));
  sp = await spolStavTxt();
  t("7d potvrzeno: JEDEN POST s telem {karty:[4965,4964]} a JSON hlavickou", spolPosty.length === 1 && JSON.stringify(JSON.parse(spolPosty[0].body)) === '{"karty":[4965,4964]}' && /application\/json/.test(spolPosty[0].ct), spolPosty);
  t("7e vysledek: cislo nabidky, soucet cen, odkaz /nabidka-online.html?t=... (novy panel, noopener), zelene, tlacitko zase povolene",
    /nabídka č\. N-2026-0007/.test(sp.text) && /70[\s ]394 Kč/.test(sp.text) && sp.odkazy.length === 1 && sp.odkazy[0].href === "/nabidka-online.html?t=TOKENTOKEN1234" && sp.odkazy[0].target === "_blank" && /noopener/.test(sp.odkazy[0].rel)
    && sp.cls === "ok" && !sp.disabled, sp);
  await klikSpol("dismiss"); await page.waitForTimeout(300);
  t("7f dalsi klik: dialog upozorni, ze nabidka N-2026-0007 uz vznikla; po zamitnuti zadny dalsi POST", dialogy.length === 1 && /už na této stránce vznikla nabídka č\. N-2026-0007/.test(dialogy[0]) && spolPosty.length === 1, [dialogy, spolPosty.length]);
  t("7g nahore ani dole zadna chyba stranky (JS)", errs.length === 0, errs);
  for (const [sc, ocek, nazev] of [["chyba400", /Nabídka nevznikla: Karty jsou pro různá vozidla \(Renault Master, VW Crafter\)/, "chyba 400 s ceskou vetou ze serveru"], ["html502", /Nabídka nevznikla: HTTP 502/, "HTML 502 bez JSON tela"],
                                    ["401", /Nabídka nevznikla: Neprihlaseno\./, "401 nepřihlášen"], ["sit", /Nabídka nevznikla: spojení se serverem selhalo\./, "spadle spojeni"]]) {
    await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
    spolScenario = sc; spolPosty.length = 0;
    await klikSpol("accept");
    await pockej(page, () => /Nabídka nevznikla/.test(document.querySelector("#spolStav").textContent));
    sp = await spolStavTxt();
    t(`7h ${nazev}: cervena hlaska, zadny odkaz, tlacitko zase povolene`, ocek.test(sp.text) && sp.cls === "err" && sp.odkazy.length === 0 && !sp.disabled, sp);
  }
  spolScenario = "bez3d";
  await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
  await klikSpol("accept");
  await pockej(page, () => /Hotovo/.test(document.querySelector("#spolStav").textContent));
  sp = await spolStavTxt();
  t("7i nabidka vznikla, ale BEZ 3D: cervene varovani s duvodem + odkaz na nabidku", /POZOR: vznikla BEZ 3D \(uložení 3D modelu selhalo: disk plný\)/.test(sp.text) && sp.cls === "err" && sp.odkazy.length === 1, sp);
  spolScenario = "xss";
  await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
  await klikSpol("accept");
  await pockej(page, () => /Hotovo/.test(document.querySelector("#spolStav").textContent));
  sp = await spolStavTxt();
  t("7j cizi data se vkladaji jako TEXT: zadny prvek, zadny skript, nebezpecny odkaz (javascript:) se nevytvori", !/<img/i.test(sp.html.replace(/&lt;img/g, "")) && sp.html.includes("&lt;img") && sp.odkazy.length === 0 && /odkaz se nepodařilo přečíst/.test(sp.text) && sp.xss === false, sp);
  spolScenario = "chyba-xss";
  await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
  await klikSpol("accept");
  await pockej(page, () => /Nabídka nevznikla/.test(document.querySelector("#spolStav").textContent));
  sp = await spolStavTxt();
  t("7k text chyby ze serveru se vklada jako TEXT (zadne <b>, <img>)", sp.html.includes("&lt;b&gt;") && !/<b>|<img/i.test(sp.html) && sp.xss === false, sp);
  spolScenario = "ok"; spolZpozdeni = 1500; spolPosty.length = 0;
  await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel();
  await klikSpol("accept");
  await page.waitForTimeout(300);
  sp = await spolStavTxt();
  t("7l behem stavby: tlacitko je zakazane a stav rika 'Vytvarim'; druhy klik nic nezalozi", sp.disabled === true && /Vytvářím nabídku/.test(sp.text), sp);
  await page.click("#spolBtn", { force: true, timeout: 2000 }).catch(() => {});
  await pockej(page, () => /Hotovo/.test(document.querySelector("#spolStav").textContent));
  t("7m po dokonceni presne JEDEN POST", spolPosty.length === 1, spolPosty.length);
  spolZpozdeni = 9000; spolPosty.length = 0;
  await otevri("items=vd:4965+4964,vd:4967+4968&rezim=nabidka"); await cekejModel();
  await klikSpol("accept");
  await page.waitForTimeout(200);
  await page.click("#nextBtn");
  await pockej(page, () => /karty 4967 \+ 4968/.test(document.querySelector("#topbar").innerText));      // jen popisek druhe skupiny, model se jeste nacita
  sp = await spolStavTxt();
  t("7n prepnuti na druhou skupinu behem stavby: druhá skupina nema cizi stav a tlacitko je zakazane (jedna stavba naraz)", sp.text === "" && sp.disabled === true, sp);
  await pockej(page, () => !document.querySelector("#spolBtn").disabled, null, 30000);
  sp = await spolStavTxt();
  t("7o po dokonceni je druhá skupina porad bez stavu a tlacitko povolene", sp.text === "" && sp.disabled === false, sp);
  await pockej(page, () => /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  await page.click("#prevBtn");
  await pockej(page, () => /karty 4965 \+ 4964/.test(document.querySelector("#topbar").innerText) && /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  sp = await spolStavTxt();
  t("7p navrat na prvni skupinu: vysledek stavby je videt (cislo nabidky + odkaz)", /Hotovo: nabídka č\. N-2026-0007/.test(sp.text) && sp.odkazy.length === 1, sp);
  t("7q behem sekce 7 zadna chyba stranky (JS)", errs.length === 0, errs);
  console.log("\n## 8) vyber dalsi strany (select) - sloucit sestavy bez psani do URL");
  const vyberInfo = () => page.evaluate(() => { const e = document.querySelector("#spolPridat"), b = document.querySelector("#spolBtn");
    return { jeSelect: !!e && !e.hidden && !!e.offsetParent, moznosti: e ? [...e.options].map((o) => o.textContent) : [], hodnoty: e ? [...e.options].map((o) => o.value) : [], jeBtn: !!b && !b.hidden && !!b.offsetParent }; });
  const vyberCekej = () => pockej(page, () => { const e = document.querySelector("#spolPridat"); return !!e && e.options.length > 0 && document.querySelector("#spolAkce") && document.querySelector("#spolAkce").offsetParent !== null; }, null, 20000);
  scenario = "ok"; zpozdeni = {}; spolScenario = "ok"; spolZpozdeni = 0; prehledScenario = "ok";
  await otevri("items=vd:4965&rezim=nabidka"); await cekejModel(); await page.waitForTimeout(600);
  let vy = await vyberInfo();
  t("8a jedna karta (levy regal): select nabizi jen sourozence TEHOZ vozu s jinym umistenim, GLB a cenou (pravy x2, kabina), bez druheho leveho, bez karet bez GLB / ceny / id a bez jineho vozu; tlacitko Vytvorit se neukazuje",
    vy.jeSelect && JSON.stringify(vy.hodnoty) === JSON.stringify(["", "4964", "4963", "4925"]) && vy.moznosti[1].replace(/[\s\u00a0]/g, " ") === "Regál pravý · #4964 · 22 563 Kč" && vy.moznosti[3].replace(/[\s\u00a0]/g, " ") === "Regál — kabina (za přepážkou) · #4925 · 30 614 Kč" && !vy.jeBtn, vy);
  const q0 = pozadavky.length;
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.selectOption("#spolPridat", "4964")]);
  await cekejModel();
  const url8 = page.url();
  t("8b vyber 4964: stranka se nacte znovu se skupinou 4965 + 4964, adresa nese obe karty, slouceny model se vyzada serverem", /items=vd:4965(%2B|\+)4964/.test(url8) && /rezim=nabidka/.test(url8) && pocet(/^\/api\/kontrola-scena\/v3d\/4965\+4964\.glb$/) === 1 && /karty 4965 \+ 4964/.test(await info(page)), [url8, pozadavky.slice(-6)]);
  await page.waitForTimeout(600);
  vy = await vyberInfo();
  t("8c skupina 4965 + 4964: tlacitko Vytvorit je videt, select nabizi uz jen prepazku (4963 je taky pravy = uz obsazeno, 4962 taky levy)", vy.jeBtn && vy.jeSelect && JSON.stringify(vy.hodnoty) === JSON.stringify(["", "4925"]), vy);
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.selectOption("#spolPridat", "4925")]);
  await cekejModel(); await page.waitForTimeout(600);
  vy = await vyberInfo();
  t("8d skupina o trech kartach: select uz se nenabizi (max 3), tlacitko Vytvorit je", /items=vd:4965(%2B|\+)4964(%2B|\+)4925/.test(page.url()) && vy.jeBtn && !vy.jeSelect, [page.url(), vy]);
  await otevri("items=vd:4965,vd:4967&rezim=nabidka"); await cekejModel(); await page.waitForTimeout(600);
  await Promise.all([page.waitForNavigation({ waitUntil: "load" }), page.selectOption("#spolPridat", "4964")]);
  await cekejModel();
  t("8e vice polozek: vyber u prvni prida stranu jen k ni, druha polozka (vd:4967) zustane beze zmeny", /items=vd:4965(%2B|\+)4964,vd:4967/.test(page.url()) && /karty 4965 \+ 4964/.test(await info(page)) && /1 \/ 2/.test(await page.evaluate(() => document.querySelector("#idxLabel").textContent)), page.url());
  await page.click("#nextBtn");
  await pockej(page, () => /karta 4967/.test(document.querySelector("#topbar").innerText) && /pohyblivých dílů/.test(document.querySelector("#topbar").innerText));
  await page.waitForTimeout(500);
  vy = await vyberInfo();
  t("8f druha polozka (VW levy regal): select nabizi jen pravy regal VW (4968), ne Master; karta bez ceny v prehledu = popisek bez ceny", vy.jeSelect && JSON.stringify(vy.hodnoty) === JSON.stringify(["", "4968"]) && vy.moznosti[1] === "Regál pravý · #4968", vy);
  t("8g seznam karet se nacte JEDNOU na stranku (i pri prepinani polozek)", prehledPozadavku >= 1 && await page.evaluate(() => performance.getEntriesByType("resource").filter((r) => /vandr-vyroba\/prehled/.test(r.name)).length) === 1, await page.evaluate(() => performance.getEntriesByType("resource").filter((r) => /vandr-vyroba\/prehled/.test(r.name)).length));
  for (const [sc, nazev] of [["403", "403 bez prava"], ["500", "HTML 500"], ["sit", "spadle spojeni"], ["prazdne", "prazdny seznam"]]) {
    prehledScenario = sc; errs.length = 0;
    await otevri("items=vd:4965+4964&rezim=nabidka"); await cekejModel(); await page.waitForTimeout(800);
    vy = await vyberInfo();
    t(`8h prehled ${nazev}: select se neukazuje, tlacitko Vytvorit u skupiny funguje a stranka bez chyb`, !vy.jeSelect && vy.jeBtn && errs.length === 0, [vy, errs]);
  }
  prehledScenario = "ok";
  t("8i behem sekce 8 zadna chyba stranky (JS)", errs.length === 0, errs);
  await browser.close(); server.close();
  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
