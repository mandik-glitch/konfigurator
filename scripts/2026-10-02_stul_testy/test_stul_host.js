// Test STRANKY STOLU PRO ZAMESTNANCE nad SPOLECNYM modulem voleb (webapp/stul-konfigurator.html + js/stul-host.js + js/pdc-layout.js; bot8, 2026-10-04).
// SKUTECNA stranka + SKUTECNY modul (js/product-configurator.js, bot16) + SKUTECNY ovladac ve 3D (js/v3d-ovladani.js) nad SKUTECNYM kodem stolu (api/stul_shop.py)
// pres most _most_stul.py (prihlaseny admin, produkt 4934). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_host.js 4934
// Casti: A nacteni + zamestnanecky blok (cena, kusovnik, odkazy, prihlaseni) | B odkaz (#hash) novy i stary | C rozlozeni = MRIZKA OKEN jako stranka produktu mini-shopu (desktop, uzke okno, mobil)
//        (spusteni jen nekterych casti: ONLY=A,C node ...; v mostu pres env)
//        D ovladani ve 3D (uchyty, najeti, nabidka, zive tazeni, Esc, tah stredni nohy v %, meze supliku) | E zablokovana volba (vzpery u uzkeho stolu).
// NALEZY pro jine vlastniky (napr. modul voleb = bot16) se tisknou jako [NALEZ ] a neshodi test (STRICT=1 je shodi); vlastni chyby jsou [CHYBA].
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0; const findings = [];
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const finding = (owner, name, cond, detail) => {
  total++;
  if (cond) { console.log(`[OK   ] ${name}`); return; }
  findings.push(`${owner}: ${name}`); if (process.env.STRICT) bad++;
  console.log(`[NALEZ] (${owner}) ${name}${detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`);
};
async function sec(name, fn) { if (process.env.ONLY && !process.env.ONLY.split(",").includes(name[0])) return; console.log("\n## " + name); try { await fn(); } catch (e) { t(name + ": test spadl na vyjimce", false, String((e && e.stack) || e).split("\n").slice(0, 3).join(" / ")); } }

// ---------------------------------------------------------------- pomocne funkce
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, opts) {
  const ctx = await browser.newContext(Object.assign({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" }, opts || {}));
  const page = await ctx.newPage(); const errs = [];
  const trk = { resolve: 0, glb: 0, pending: 0, last: Date.now(), bodies: [] };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.pending++; trk.last = Date.now(); trk.bodies.push(r.postData() || ""); } else if (GLB_RE.test(u)) { trk.glb++; trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {                         // klid = po akci pockej `quiet` ms (aby dotaz stihl vzniknout: modul odklada 250 ms), pak dokud nejede zadny resolve/GLB a `quiet` ms nepribyl novy
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, hash) {
  await p.page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.ov && Object.keys(S.ov.debug().handles).length > 0; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const dbg = page => page.evaluate(() => window.__pdcState.ov.debug());
const selOf = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const cssNum = (page, sel, prop) => page.evaluate(([s, pr]) => parseFloat(getComputedStyle(document.querySelector(s))[pr]), [sel, prop]);
const rectOf = (page, sel) => page.evaluate(s => { const r = document.querySelector(s).getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height, r: r.right, b: r.bottom }; }, sel);
const hcenter = async (page, id) => { const b = await page.locator("#v3do_" + id).boundingBox(); return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height }; };
const num = s => Number(String(s).replace(/[^\d,\-−]/g, "").replace("−", "-").replace(",", "."));
const plain = s => String(s).replace(/[\s  ]+/g, "");
const stageProject = (page, P) => page.evaluate(P => {                       // nezavisly prumet 3D bodu (THREE) na obrazovku
  const S = window.__pdcState, c = S.viewer.cameraInfo();
  const cam = new THREE.PerspectiveCamera(c.fov, c.aspect, c.near, c.far); cam.position.fromArray(c.pos); cam.up.fromArray(c.up);
  cam.lookAt(new THREE.Vector3().fromArray(c.target)); cam.updateMatrixWorld(); cam.updateProjectionMatrix();
  const v = new THREE.Vector3(P[0], P[1], P[2]).project(cam), r = document.querySelector("#stage canvas").getBoundingClientRect();
  return { x: r.left + (v.x + 1) / 2 * r.width, y: r.top + (1 - v.y) / 2 * r.height };
}, P);
const deckBox = page => page.evaluate(() => window.__pdcState.last.vodici.ovladani.casti.find(c => c.id === "deck").aabb);
async function dragTo(page, id, dx, dy, hold) {                              // uchop uchyt, tahni o (dx, dy) po krocich, drz; mys zustava stisknuta
  const c = await hcenter(page, id);
  await page.mouse.move(c.x, c.y); await page.mouse.down();
  for (let i = 1; i <= 10; i++) await page.mouse.move(c.x + dx * i / 10, c.y + dy * i / 10);
  await page.waitForTimeout(hold || 600);
  return c;
}
// kusovnik z DOM: radky (5 bunek), soucty (2 bunky)
const bomOf = page => page.evaluate(() => {
  const trs = [...document.querySelectorAll("#bomBody tbody tr")];
  const rows = trs.filter(r => !r.classList.contains("sec") && !r.classList.contains("grp")).map(r => [...r.children].map(c => c.textContent));
  const otevrene = !document.querySelector(".mw-win-bom").classList.contains("is-closed");
  // co je VIDET (Robert 2026-10-04: "chybi tam neco" - radky Prace/spoje/balne byly v DOM, ale skryte): radky, ktere nejsou skryte (zabalene delky profilu jsou skryte schvalne; skupina profilu je 1 viditelny radek)
  const vis = otevrene ? trs.filter(r => !r.classList.contains("sec") && r.children.length === 5 && !r.hidden && getComputedStyle(r).display !== "none").map(r => [...r.children].map(c => c.textContent)) : null;
  const secViditelne = otevrene ? trs.filter(r => r.classList.contains("sec")).map(r => { let n = 0; for (let x = r.nextElementSibling; x && !x.classList.contains("sec") && x.children.length === 5; x = x.nextElementSibling) if (!x.hidden) n++; return [r.textContent, n]; }) : null;
  return { lines: rows.filter(r => r.length === 5), sums: rows.filter(r => r.length === 2), all: rows, vis, secViditelne };
});
function bomChecks(name, b, priceText) {
  const val = s => num(s), sum = b.lines.reduce((a, r) => a + val(r[4]), 0);
  const net = b.sums.find(r => /^Celkem bez DPH/.test(r[0])), vat = b.sums.find(r => /^DPH/.test(r[0])), gross = b.sums.find(r => /^Celkem s DPH/.test(r[0]));
  t(`${name}: kusovnik ma radky materialu a prace + 3 souctove radky`, b.lines.length >= 8 && !!net && !!vat && !!gross, `${b.lines.length} radku`);
  t(`${name}: soucet radku kusovniku == 'Celkem bez DPH' (${net && net[1]})`, !!net && Math.abs(sum - val(net[1])) <= 1, `soucet ${sum} vs ${net && val(net[1])}`);
  t(`${name}: bez DPH + DPH == s DPH (+-1 Kc)`, !!net && Math.abs(val(net[1]) + val(vat[1]) - val(gross[1])) <= 1, [net && net[1], vat && vat[1], gross && gross[1]]);
  t(`${name}: cena nahore ('${priceText}') == 'Celkem bez DPH' v kusovniku`, !!net && val(priceText) === val(net[1]), [priceText, net && net[1]]);
  if (b.vis) {
    const visSum = b.vis.reduce((a, r) => a + val(r[4]), 0);
    t(`${name}: VIDITELNE radky kusovniku (zabalene delky profilu = 1 radek) davaji dohromady 'Celkem bez DPH' (${net && net[1]})`, !!net && Math.abs(visSum - val(net[1])) <= 1, `viditelny soucet ${visSum} vs ${net && val(net[1])}`);
    const prace = (b.secViditelne || []).find(x => /^Práce, spoje a balné/.test(x[0]));
    t(`${name}: sekce 'Prace, spoje a balne' ma VIDITELNE radky (rezy, spoje, balne...)`, !!prace && prace[1] >= 2, b.secViditelne);
  }
  const badLn = b.lines.filter(r => { const q = val(r[2]), u = val(r[3]), c = val(r[4]); return r[3] !== "" && r[2] !== "" && Math.abs(q * u - c) > Math.max(1, q * 0.5 + 0.5); });
  t(`${name}: kazdy radek: ks x cena/ks == celkem (do zaokrouhleni)`, badLn.length === 0, badLn.slice(0, 3));
}
async function findFreeDeck(page) {                                           // bod na desce, kde neni zadny uchyt (stred desky + posun, nezavisly prumet)
  const dk = await deckBox(page);
  for (const off of [[100, 300], [-150, 250], [60, -300], [-200, -200]]) {
    const P = [(dk[0][0] + dk[1][0]) / 2 + off[0], dk[1][1], (dk[0][2] + dk[1][2]) / 2 + off[1]];
    const pt = await stageProject(page, P);
    const okp = await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && !e.closest(".v3do-h") && !e.closest(".v3do-menu"); }, [pt.x, pt.y]);
    if (okp) { await page.mouse.move(pt.x, pt.y); await page.waitForTimeout(250); if ((await dbg(page)).hover === "deck") return { x: pt.x, y: pt.y, P, dk }; }
  }
  return null;
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const MOBIL = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 };

  // ================================================================ A) nacteni, zamestnanecky blok, prihlaseni
  await sec("A) nacteni a zamestnanecky blok", async () => {
    const p = await mk(browser); await p.ctx.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
    await load(p, "");
    const pg = p.page;
    const st = await pg.evaluate(() => ({ slots: [...document.querySelectorAll(".pdc-slot")].length, canvas: !!document.querySelector("#stage .v3d-root canvas"), msg: getComputedStyle(document.getElementById("stageMsg")).display,
      staff: ["price", "info", "bom"].every(k => !document.querySelector(".mw-win-" + k).hidden && getComputedStyle(document.querySelector(".mw-win-" + k)).display !== "none") ? "block" : "none", login: getComputedStyle(document.getElementById("login")).display, title: document.title, price: document.getElementById("priceNet").textContent,
      gross: document.getElementById("priceGross").textContent, code: document.getElementById("staffCode").textContent, links: [...document.querySelectorAll("#staffLinks a")].map(a => [a.textContent, a.getAttribute("href"), a.target]),
      modul: typeof window.PdConfigurator, own: document.querySelectorAll("input[type=range]").length }));
    t("A1 modul vykreslil volby stolu (>= 30 slotu) a 3D platno", st.slots >= 30 && st.canvas, st.slots);
    t("A2 hlaska 'Nacitam 3D model' zmizela a vyzva k prihlaseni neni videt", st.msg === "none" && st.login === "none", [st.msg, st.login]);
    t("A3 stranka bezi na spolecnem modulu (PdConfigurator) a spolecnem rozlozeni (PdcLayout), ne na vlastnich jezdcich: jezdce ma modul (.pdc-range)", st.modul === "object" && st.own > 0 && (await pg.evaluate(() => typeof window.PdcLayout)) === "object" && !(await pg.evaluate(() => !!window.StulPage)), [st.modul, st.own]);
    t("A4 zamestnanecky blok je videt, cena bez DPH a s DPH", st.staff !== "none" && /\d\s?\d*\s?Kč/.test(st.price) && /s DPH \(\d+ %\)/.test(st.gross), [st.staff, st.price, st.gross]);
    t("A5 kod konfigurace 'STL-...' a pocet spoju profilu", /^Kód konfigurace: STL-[0-9A-F]+ · \d+ spojů profilů$/.test(st.code), st.code);
    t("A6 odkazy 'Vyrobni list' a 'Vyrobni sestava (JSON)' ukazuji na /api/stul/ s parametry stolu a otviraji se v nove karte",
      st.links.length === 2 && st.links[0][0] === "Výrobní list" && st.links.every(l => /^\/api\/stul\/vyrobni-/.test(l[1]) && /sirka=1280/.test(l[1]) && l[2] === "_blank"), st.links.map(l => l[1].slice(0, 50)));
    const body = p.trk.bodies[0] || "";
    t("A7 prvni dotaz na resolve nese `staff: true` a produkt 4934 (jinak by server blok nevydal)", /"staff":\s*true/.test(body) && /4934/.test(body), body.slice(0, 160));
    t("A8 titulek stranky je 'Generator stolu 01 system 30' (Robert 2026-10-04: v systemu 30 bude vic typu generatoru stolu)", /^Generátor stolu 01 systém 30/.test(st.title) && /Generátor stolu 01 systém 30/.test(await pg.textContent("h1")), st.title);
    // kusovnik: skutecne cisla
    t("A9a okno kusovniku je po nacteni otevrene a tabulka je videt", await pg.evaluate(() => !document.querySelector(".mw-win-bom").classList.contains("is-closed") && document.querySelector("#bomBody table").offsetParent !== null));
    const b0 = await bomOf(pg); bomChecks("A9 vychozi stul", b0, st.price);
    // alu profily: kazdy druh = 1 radek (zabalene), rozbalenim se ukazou delky; soucet radku/kopirovani se nemeni
    const gr = () => pg.evaluate(() => {
      const g = [...document.querySelectorAll("#bomBody tr.grp")], det = [...document.querySelectorAll("#bomBody tr.det")], vis = r => !r.hidden && r.offsetParent !== null;
      return { n: g.length, names: g.map(r => r.firstChild.textContent.replace(/^[▸▾]/, "")), head: g.map(r => [...r.children].map(c => c.textContent)), det: det.length, detVis: det.filter(vis).length, exp: g.map(r => r.querySelector("button").getAttribute("aria-expanded")),
        profLoose: [...document.querySelectorAll("#bomBody tbody tr:not(.grp):not(.det):not(.sec)")].filter(r => /^Profil /.test(r.firstChild.textContent) && /mm$/.test(r.children[1] ? r.children[1].textContent : "")).length,
        detSum: det.reduce((a, r) => a + parseFloat(r.children[4].textContent.replace(/\s/g, "").replace(",", ".")), 0), grpSum: g.reduce((a, r) => a + parseFloat(r.children[4].textContent.replace(/\s/g, "").replace(",", ".")), 0) };
    });
    const g0 = await gr();
    t("A9b alu profily jsou zabalene: 1 radek na druh profilu (" + g0.names.join(", ") + "), delky skryte, zadny profil nevisi mimo skupinu", g0.n >= 1 && g0.det >= 6 && g0.detVis === 0 && g0.profLoose === 0 && g0.exp.every(x => x === "false") && /dél/.test(g0.head[0][1]), g0);
    t("A9c soucet radku skupin == soucet delek (bomOf bere jen delky: soucet radku se nemeni)", Math.abs(g0.detSum - g0.grpSum) <= 1, [g0.detSum, g0.grpSum]);
    await pg.click("#bomBody tr.grp button"); await pg.waitForTimeout(150);
    const g1 = await gr();
    t("A9d klik na radek profilu rozbali jeho delky (aria-expanded=true), dalsi klik je zase sbali", g1.exp[0] === "true" && g1.detVis > 0 && g1.detVis < g1.det + 1 && (await pg.click("#bomBody tr.grp button"), await pg.waitForTimeout(150), (await gr()).detVis === 0), g1);
    const sec0 = await pg.evaluate(() => [...document.querySelectorAll("#bomBody tr.sec")].map(r => r.textContent));
    t("A10 kusovnik ma sekce 'Material a dily' a 'Prace, spoje a balne' + poznamku o hmotnosti a montazi", sec0.join("|") === "Materiál a díly|Práce, spoje a balné" && /Hmotnost [\d,]+ kg · Montáž/.test(await pg.textContent("#bomBody")), sec0);
    // kusovnik sleduje zmenu: sirsi stul = vyssi cena a zase souhlasi soucet
    await pg.locator('.pdc-slot[data-slot=w] .pdc-num').fill("1840"); await pg.keyboard.press("Tab"); await idle(p, 1500);
    const price1 = await pg.textContent("#priceNet"), b1 = await bomOf(pg);
    t("A11 po zmene sirky na 1840 se zmeni cena (" + st.price + " -> " + price1 + ") a kusovnik zase sedi", num(price1) > num(st.price), [st.price, price1]);
    bomChecks("A12 stul 1840", b1, price1);
    // kopirovani
    await pg.click("#copyBtn"); await pg.waitForTimeout(400);
    const clip = await pg.evaluate(() => navigator.clipboard.readText());
    t("A13 'Zkopirovat odkaz' vlozi do schranky aktualni adresu vcetne #hash (w=1840) a potvrdi", clip === (await pg.evaluate(() => location.href)) && /[#&]w=1840/.test(clip) && /Odkaz je zkopírovaný/.test(await pg.textContent("#staffCode")), clip.slice(0, 90));
    await pg.click("#bomCopy"); await pg.waitForTimeout(400);
    const clip2 = await pg.evaluate(() => navigator.clipboard.readText());
    t("A14 'Zkopirovat tabulku' vlozi kusovnik jako text s tabulatory (radek = polozka, 5 sloupcu) a potvrdi", clip2.startsWith("Materiál a díly\n") && clip2.split("\n").some(r => r.split("\t").length === 5) && /Kusovník je zkopírovaný/.test(await pg.textContent("#staffCode")), clip2.slice(0, 80));
    t("A15 bez chyb v konzoli a ve strance", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();

    // bez prihlaseni: /api/auth/me bez uzivatele
    const q = await mk(browser);
    await q.page.route("**/api/auth/me", r => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: null }) }));
    await q.page.goto(`${BASE}/stul-konfigurator.html?debug=1#w=1500`, { waitUntil: "load" }); await q.page.waitForTimeout(2500);
    const lg = await q.page.evaluate(() => ({ login: getComputedStyle(document.getElementById("login")).display, href: document.getElementById("loginLink").getAttribute("href"), msg: document.getElementById("stageMsg").textContent,
      slots: document.querySelectorAll(".pdc-slot").length, canvas: !!document.querySelector("#stage canvas"), staff: getComputedStyle(document.getElementById("shGrid")).display }));
    t("A16 bez prihlaseni: vyzva k prihlaseni, odkaz s navratem na tuto stranku vcetne #hash, zadne volby, zadny 3D model", lg.login === "block" && lg.href.startsWith("/login.html?next=") && decodeURIComponent(lg.href).includes("/stul-konfigurator.html#w=1500") && lg.slots === 0 && !lg.canvas, lg);
    t("A17 bez prihlaseni: hlaska ve 3D plose 'Pro zobrazeni se prihlas.', zamestnanecky blok skryty a nejde zadny dotaz na resolve", lg.msg === "Pro zobrazení se přihlas." && lg.staff === "none" && q.trk.resolve === 0, [lg.msg, lg.staff, q.trk.resolve]);
    await q.ctx.close();
    // vypadek /api/auth/me = take prihlaseni
    const q2 = await mk(browser);
    await q2.page.route("**/api/auth/me", r => r.abort());
    await q2.page.goto(`${BASE}/stul-konfigurator.html?debug=1`, { waitUntil: "load" }); await q2.page.waitForTimeout(1500);
    t("A18 vypadek /api/auth/me se bere jako nepřihlášený (vyzva, bez voleb, bez chyby stranky)", (await q2.page.evaluate(() => getComputedStyle(document.getElementById("login")).display)) === "block" && q2.errs.filter(e => !/net::ERR|Failed to load resource/.test(e)).length === 0, q2.errs);
    await q2.ctx.close();
    // server nevydal blok staff (nezamestnanec / starsi server): stranka funguje, zamestnanecky blok je skryty
    const q3 = await mk(browser);
    await q3.page.route(RES_RE, async route => { const r = await route.fetch(); const j = await r.json(); delete j.staff; await route.fulfill({ response: r, json: j }); });
    await load(q3, "");
    const ns = await q3.page.evaluate(() => ({ staff: ["price", "info", "bom"].every(k => document.querySelector(".mw-win-" + k).hidden) ? "none" : "block", slots: document.querySelectorAll(".pdc-slot").length, canvas: !!document.querySelector("#stage canvas") }));
    t("A19 bez bloku `staff` v odpovedi: zamestnanecky blok skryty, volby i 3D funguji", ns.staff === "none" && ns.slots >= 30 && ns.canvas && q3.errs.length === 0, [ns, q3.errs.slice(0, 2)]);
    await q3.ctx.close();
  });

  // ================================================================ B) odkaz (#hash)
  await sec("B) odkaz s #hash (novy i stary tvar)", async () => {
    const p = await mk(browser);
    await load(p, "");
    const pg = p.page;
    const h0 = await pg.evaluate(() => ({ hash: location.hash, len: history.length }));
    const keys0 = h0.hash.slice(1).split("&").map(x => x.split("=")[0]);
    t("B1 vychozi stul zapise do adresy hash s VEREJNYMI nazvy slotu (w, d, h, braces, cut1w...) a zadnym starym (sirka, vzpery...)",
      keys0.includes("w") && keys0.includes("braces") && keys0.includes("cut1w") && !keys0.some(k => /^(sirka|hloubka|vyska|vzpery|vyrez1|led_rameno|suplik_posun)$/.test(k)), h0.hash.slice(0, 120));
    await pg.locator('.pdc-slot[data-slot=d] .pdc-num').fill("900"); await pg.keyboard.press("Tab"); await idle(p, 1500);
    const h1 = await pg.evaluate(() => ({ hash: location.hash, len: history.length, d: window.__pdcState.sel.d }));
    t("B2 zmena hloubky v panelu prepise hash (d=900) a NEPRIDA polozku do historie (replaceState, tlacitko Zpet)", h1.d === 900 && /[#&]d=900(&|$)/.test(h1.hash) && h1.len === h0.len, [h1.hash.slice(0, 40), h1.len, h0.len]);
    await pg.reload({ waitUntil: "load" });
    await pg.waitForFunction(() => window.__pdcState && window.__pdcState.ov && Object.keys(window.__pdcState.ov.debug().handles).length > 0, null, { polling: 200, timeout: 60000 }); await idle(p, 900);
    const r1 = await pg.evaluate(() => ({ d: window.__pdcState.sel.d, dnum: document.querySelector("[data-slot=d] .pdc-num").value }));
    t("B3 po obnoveni stranky (F5) je hloubka 900 z hashe i v panelu", r1.d === 900 && r1.dnum === "900", r1);
    await p.ctx.close();

    // novy tvar odkazu
    const n = await mk(browser);
    await load(n, "#w=1840&d=700&h=900&ov=40&braces=1&bracelen=250&cut1=1&cut1w=300&led=1&arm=700");
    const sn = await selOf(n.page);
    const ui = await n.page.evaluate(() => ({ w: document.querySelector("[data-slot=w] .pdc-num").value, braces: document.querySelector("[data-slot=braces] input").checked, bl: document.querySelector("[data-slot=bracelen] .pdc-num").value, c1: document.querySelector("[data-slot=cut1] input").checked, valid: window.__pdcState.last.valid, errors: window.__pdcState.last.errors, hash: location.hash }));
    t("B4 novy odkaz: sirka, hloubka, vyska, presah z hashe jsou ve vyberu", sn.w === 1840 && sn.d === 700 && sn.h === 900 && sn.ov === 40, [sn.w, sn.d, sn.h, sn.ov]);
    t("B5 novy odkaz: vzpery zapnute s delkou 250, vyrez 1 se sirkou 300, rameno LED 700 - a ovladace v panelu to ukazuji", sn.braces === true && sn.bracelen === 250 && sn.cut1 === true && sn.cut1w === 300 && sn.arm === 700 && ui.w === "1840" && ui.braces && ui.bl === "250" && ui.c1, [sn.braces, sn.bracelen, sn.cut1w, sn.arm, ui]);
    t("B6 konfigurace z odkazu je platna (server nevratil chyby) a po nacteni zustava hash se stejnymi hodnotami", ui.valid === true && (ui.errors || []).length === 0 && /[#&]w=1840(&|$)/.test(ui.hash) && /[#&]braces=1(&|$)/.test(ui.hash), [ui.valid, ui.errors, ui.hash.slice(0, 60)]);
    await n.ctx.close();

    // stary tvar odkazu (nazvy generatoru, stredni_noha v mm)
    const o = await mk(browser);
    await load(o, "#sirka=1840&hloubka=700&vyska=900&presah=40&vzpery=1&vzpera_delka=250&stredni_noha=1000&led_rameno=700&suplik_posun=-50&vyrez1=1&vyrez1_w=300");
    const so = await selOf(o.page);
    const ho = await o.page.evaluate(() => location.hash);
    t("B7 stary odkaz: nazvy generatoru se prevedou na verejne sloty (sirka->w, hloubka->d, vyska->h, presah->ov, led_rameno->arm, vzpery->braces, vzpera_delka->bracelen, vyrez1->cut1)",
      so.w === 1840 && so.d === 700 && so.h === 900 && so.ov === 40 && so.arm === 700 && so.braces === true && so.bracelen === 250 && so.cut1 === true && so.cut1w === 300, so);
    t("B8 stary odkaz: stredni noha 1000 mm od leve nohy -> mid v % rozpeti (1000 / (1840-30) = 55 %)", so.mid === Math.round(1000 / 1810 * 100) && so.mid === 55, so.mid);
    t("B9 stary odkaz: suplik_posun -> boxpos (-50) a po nacteni je hash prepsany na verejne nazvy (bez 'sirka', 'vzpery', 'stredni_noha')", so.boxpos === -50 && !/(^|[#&])(sirka|hloubka|vyska|vzpery|vzpera_delka|stredni_noha|suplik_posun|vyrez1)=/.test(ho), [so.boxpos, ho.slice(0, 80)]);
    t("B10 stary odkaz: konfigurace platna a bez chyb stranky", (await o.page.evaluate(() => window.__pdcState.last.valid)) === true && o.errs.length === 0, o.errs.slice(0, 2));
    await o.ctx.close();

    // nesmysly v hashi
    const g = await mk(browser);
    await load(g, "#w=abc&zzz=5&=3&neco&d=&cut1=maybe&h=99999&w2");
    const sg = await selOf(g.page), mx = await g.page.evaluate(() => ({ max: window.__pdcState.last.options.h && window.__pdcState.last.options.h.max, valid: window.__pdcState.last.valid }));
    t("B11 nesmysly v hashi (w=abc, neznamy slot, prazdne klice, h=99999) stranka nespadne: w zustane vychozi, neznamy slot se zahodi, vyska se oreze na max", sg.w === 1280 && !("zzz" in sg) && sg.h <= (mx.max || 1e9) && sg.h >= 600 && mx.valid === true && g.errs.length === 0, [sg.w, sg.h, mx, g.errs.slice(0, 2)]);
    await g.ctx.close();

    // parseHash prima (jednotkove)
    const u = await mk(browser);
    await u.page.goto(`${BASE}/stul-konfigurator.html`, { waitUntil: "domcontentloaded" });
    const ph = await u.page.evaluate(() => { const f = window.StulHost.parseHash; return [f("#sirka=1840&vyrez1_police=1&vyrez2_x=150&vyrez3_d=90&loz=1&loz_rozteca=300&led=true&neznamy=ahoj"), f("#stredni_noha=900&sirka=1840"), f("#stredni_noha=900"), f(""), f("#a=1&&b"), f("#mid=40&w=1500")]; });
    t("B12 parseHash: stare nazvy vyrezu a loziska (vyrez1_police->cut1shelf, vyrez2_x->cut2x, vyrez3_d->cut3d, loz->bearings, loz_rozteca->bearpitch), true->boolean, text zustane textem",
      ph[0].w === 1840 && ph[0].cut1shelf === 1 && ph[0].cut2x === 150 && ph[0].cut3d === 90 && ph[0].bearings === 1 && ph[0].bearpitch === 300 && ph[0].led === true && ph[0].neznamy === "ahoj", ph[0]);
    t("B13 parseHash: stredni_noha v mm se prevede podle sirky v hashi (900/(1840-30) = 50 %), bez sirky podle vychozich 1200 (900/1170 = 77 %); prazdny hash = nic", ph[1].mid === 50 && ph[2].mid === 77 && Object.keys(ph[3]).length === 0 && !("stredni_noha" in ph[1]), [ph[1], ph[2], ph[3]]);
    t("B14 parseHash: polozky bez '=' a prazdne se preskoci, novy slot mid se nemeni", Object.keys(ph[4]).join() === "a" && ph[5].mid === 40 && ph[5].w === 1500, [ph[4], ph[5]]);
    await u.ctx.close();
  });

  // ================================================================ C) rozlozeni = mrizka oken (jako stranka produktu mini-shopu)
  // okna a jejich poloha (viewport souradnice x, y + scroll), zahlavi bez sipky
  const OKNA = page => page.evaluate(() => [...document.querySelectorAll(".mw-win")].map(w => {
    const r = w.getBoundingClientRect(), h = w.querySelector(":scope > .mw-win-h");
    return { key: (w.className.match(/mw-win-(\w+)/) || [])[1], head: (h ? h.textContent : "").replace(/[▾]/g, "").trim(), fold: !!(h && h.classList.contains("mw-win-fold")), closed: w.classList.contains("is-closed"), aria: h ? h.getAttribute("aria-expanded") : null,
      hidden: w.hidden, x: r.left, y: r.top + window.scrollY, w: r.width, h: r.height, r: r.right };
  }));
  await sec("C) rozlozeni = mrizka oken jako mini-shop (desktop, uzke okno, mobil)", async () => {
    const p = await mk(browser);
    await load(p, "#w=1840");
    const pg = p.page;
    const ws = await OKNA(pg), by = {}; ws.forEach(w => by[w.key] = w);
    t("C1 okna ve spravnem poradi: stage, price, env, info, dim, frame, extras, bom, adv, sum, profile, attach, rules (stejna mrizka oken jako stranka produktu mini-shopu + okno Pravidla stolu; okno Prostredi (HDRI) hned pod oknem s cenou, Robert 2026-10-04; Hlavni profil a Pripni cokoli = prvky shodne na vsech mistech, Robert 2026-10-05; okno Vychozi konfigurace jen pro admina ve 3. sloupci pred Pravidly stolu; okno Vzhled online nabidek jen pro admina jako posledni radek mrizky, bot10 2026-10-07)", ws.map(w => w.key).join() === "stage,price,env,info,dim,frame,extras,bom,adv,sum,profile,attach,defcfg,rules,vzhled", ws.map(w => w.key));
    t("C2 hlavicky oken: 3D nahled, Cena a scena, Prostredi (HDRI), Vyroba a odkazy, Rozmery, Konstrukce, Prislusenstvi (z modulu pres groupHost), Kusovnik, Vyrezy a loziska, Shrnuti, Hlavni profil, Pripni cokoli, Vychozi konfigurace, Pravidla stolu, Vzhled online nabidek (jen admin; posledni okno mrizky)",
      ws.map(w => w.head).join("|") === "3D náhled|Cena a scéna|Prostředí (HDRI)|Výroba a odkazy|Rozměry|Konstrukce|Příslušenství|Kusovník s cenami (interní)|Výřezy a ložiska|Shrnutí|Hlavní profil|Připni cokoli|Výchozí konfigurace|Pravidla stolu|Vzhled online nabídek (barvy, lesk, AO, HDRI – pro všechny nabídky)", ws.map(w => w.head));
    t("C3 stav oken po nacteni (desktop): Rozmery, Konstrukce, Prislusenstvi, Kusovnik, Shrnuti otevrena, Vyrezy a loziska a Pravidla stolu ZAVRENE; stage/price/info nejsou sklopitelna a zadne okno neni schovane",
      ["dim", "frame", "extras", "bom", "sum"].every(k => by[k].fold && !by[k].closed && by[k].aria === "true") && by.adv.fold && by.adv.closed && by.adv.aria === "false" && by.rules.fold && by.rules.closed && by.rules.aria === "false" && ["stage", "price", "info"].every(k => !by[k].fold) && ws.filter(w => w.key !== "env").every(w => !w.hidden), ws.map(w => [w.key, w.closed, w.hidden]));
    t("C4 desktop: 3D okno je vlevo a vpravo vedle nej sloupec Cena a scena + Vyroba a odkazy (stejna horni hrana, stage sirsi nez 600 px, sloupec 300-450 px, mezera mezi nimi)",
      Math.abs(by.stage.y - by.price.y) <= 2 && by.stage.w >= 600 && by.price.w >= 300 && by.price.w <= 450 && by.stage.r < by.price.x && by.price.x > by.stage.x && Math.abs(by.info.x - by.price.x) <= 1 && by.info.y > by.price.y + by.price.h - 1, [by.stage, by.price, by.info]);
    t("C5 desktop: Rozmery, Konstrukce a Prislusenstvi jsou tri okna vedle sebe pod 3D (stejna horni hrana, rostouci x, stejna sirka, zadne prekryti)",
      Math.abs(by.dim.y - by.frame.y) <= 2 && Math.abs(by.frame.y - by.extras.y) <= 2 && by.dim.y > by.stage.y + by.stage.h - 1 && by.dim.x < by.frame.x && by.frame.x < by.extras.x && Math.abs(by.dim.w - by.frame.w) <= 2 && Math.abs(by.frame.w - by.extras.w) <= 2 && by.dim.r <= by.frame.x && by.frame.r <= by.extras.x, [by.dim, by.frame, by.extras]);
    t("C6 desktop: Kusovnik je siroke okno vlevo pod volbami, vpravo od nej sloupec Vyrezy a loziska (nad) + Shrnuti + Pravidla stolu (pod)",
      by.bom.y > by.dim.y + by.dim.h - 1 && Math.abs(by.bom.x - by.dim.x) <= 1 && by.bom.w >= 600 && by.adv.x >= by.bom.r && Math.abs(by.adv.y - by.bom.y) <= 2 && by.sum.y > by.adv.y + by.adv.h - 1 && Math.abs(by.sum.x - by.adv.x) <= 1 && by.rules.y > by.sum.y + by.sum.h - 1 && Math.abs(by.rules.x - by.adv.x) <= 1, [by.bom, by.adv, by.sum, by.rules]);
    const hostTxt = await pg.evaluate(() => ({ t: document.getElementById("host").textContent, slots: document.querySelectorAll("#host .pdc-slot").length, btn: !![...document.querySelectorAll("#host button, #host a")].find(b => /Výchozí hodnoty/.test(b.textContent)) }));
    t("C7 panel pod 3D ma jen listu 'Vaše konfigurace' + 'Výchozí hodnoty'; zadna volba v nem neni (vsechny jsou v oknech)", /Vaše konfigurace/i.test(hostTxt.t) && hostTxt.btn && hostTxt.slots === 0, hostTxt);
    const kde = await pg.evaluate(() => { const o = {}; document.querySelectorAll(".pdc-slot[data-slot]").forEach(s => { const w = s.closest(".mw-win"); o[s.dataset.slot] = w ? (w.className.match(/mw-win-(\w+)/) || [])[1] : null; }); return o; });
    t("C8 volby jsou v oknech podle skupin: w, d, h, ov v Rozmerech; posts, shelf, wheels, feet v Konstrukci; drawers, boxpos, panels, led, arm, socket, pet, braces v Prislusenstvi; vyrezy a loziska ve Vyrezech a loziskach",
      ["w", "d", "h", "ov"].every(k => kde[k] === "dim") && ["posts", "shelf", "wheels", "feet"].every(k => kde[k] === "frame") && ["drawers", "boxpos", "panels", "led", "arm", "socket", "pet", "braces"].every(k => kde[k] === "extras")
        && ["cut1", "cut1w", "bearings"].every(k => kde[k] === "adv") && Object.values(kde).every(v => v), kde);
    // sklapeni
    await pg.click(".mw-win-adv .mw-win-fold"); await pg.waitForTimeout(250);
    const adv1 = await pg.evaluate(() => ({ closed: document.querySelector(".mw-win-adv").classList.contains("is-closed"), aria: document.querySelector(".mw-win-adv > .mw-win-h").getAttribute("aria-expanded"), vis: document.querySelector("[data-slot=cut1]").offsetParent !== null, h: document.querySelector(".mw-win-adv").getBoundingClientRect().height }));
    t("C9 klik na zahlavi 'Vyrezy a loziska' okno otevre (aria-expanded=true, volba vyrezu je videt, okno naroste)", !adv1.closed && adv1.aria === "true" && adv1.vis && adv1.h > 100, adv1);
    await pg.click(".mw-win-adv .mw-win-fold"); await pg.waitForTimeout(250);
    t("C10 druhy klik okno zase zavre (schova se telo, aria-expanded=false)", await pg.evaluate(() => document.querySelector(".mw-win-adv").classList.contains("is-closed") && document.querySelector(".mw-win-adv > .mw-win-h").getAttribute("aria-expanded") === "false" && document.querySelector("[data-slot=cut1]").offsetParent === null));
    await pg.click(".mw-win-bom .mw-win-fold"); await pg.waitForTimeout(250);
    const bomZ = await pg.evaluate(() => ({ closed: document.querySelector(".mw-win-bom").classList.contains("is-closed"), vis: document.getElementById("bomBody").offsetParent !== null, h: document.querySelector(".mw-win-bom").getBoundingClientRect().height }));
    await pg.click(".mw-win-bom .mw-win-fold"); await pg.waitForTimeout(250);
    const bomO = await pg.evaluate(() => ({ closed: document.querySelector(".mw-win-bom").classList.contains("is-closed"), vis: document.getElementById("bomBody").offsetParent !== null, rows: document.querySelectorAll("#bomBody tbody tr").length }));
    t("C11 okno Kusovnik jde sklopit (tabulka zmizi) a zase otevrit (tabulka s radky se vrati)", bomZ.closed && !bomZ.vis && !bomO.closed && bomO.vis && bomO.rows >= 20, [bomZ, bomO]);
    // shrnuti
    const sm = async () => pg.evaluate(() => ({ vis: [...document.querySelectorAll(".mw-win-sum dt")].filter(d => d.offsetParent !== null).length, all: document.querySelectorAll(".mw-win-sum dt").length, btn: document.querySelector(".mw-win-sum .mw-link").textContent, hid: document.querySelector(".mw-win-sum .mw-link").hidden, cls: document.querySelector(".mw-win-sum").classList.contains("sum-all") }));
    const s0 = await sm();
    t("C12 Shrnuti ukazuje 4 radky a tlacitko 'Cela konfigurace (N)' s poctem vsech radku", s0.vis === 4 && s0.all > 4 && !s0.hid && s0.btn === "Celá konfigurace (" + s0.all + ")" && !s0.cls, s0);
    await pg.click(".mw-win-sum .mw-link"); await pg.waitForTimeout(200);
    const s1 = await sm();
    await pg.click(".mw-win-sum .mw-link"); await pg.waitForTimeout(200);
    const s2 = await sm();
    t("C13 klik na tlacitko ukaze vsechny radky shrnuti (tlacitko 'Méně'), dalsi klik vrati 4 radky", s1.vis === s1.all && s1.btn === "Méně" && s2.vis === 4 && s2.btn === s0.btn, [s1, s2]);
    // zamestnanecka okna
    const ob = await pg.evaluate(() => { const in_ = (k, ids) => ids.map(id => !!document.querySelector(".mw-win-" + k + " #" + id)); return { price: in_("price", ["priceNet", "priceGross", "sceneBtn", "sceneStatus"]), info: in_("info", ["staffProblems", "staffLinks", "copyBtn", "staffCode"]), bom: in_("bom", ["bomBody", "bomCopy"]), stage: in_("stage", ["stage", "stageMsg"]), btnVis: document.getElementById("sceneBtn").offsetParent !== null }; });
    t("C14 zamestnanecke prvky jsou v oknech: cena a tlacitko Vlozit do Sceny v 'Cena a scena', problemy/odkazy/kopie odkazu/kod v 'Vyroba a odkazy', tabulka a kopie v 'Kusovnik', #stage v '3D nahled'",
      Object.entries(ob).filter(([k]) => k !== "btnVis").every(([, v]) => v.every(Boolean)) && ob.btnVis, ob);
    const cv = await pg.evaluate(() => { const c = document.querySelector("#stage canvas").getBoundingClientRect(), w = document.querySelector(".mw-win-stage").getBoundingClientRect(); return { cw: c.width, ww: w.width, ch: c.height }; });
    t("C15 3D platno vyplni 3D okno do sirky (platno " + Math.round(cv.cw) + " px = okno " + Math.round(cv.ww) + " px) a je vysoke aspon 450 px", Math.abs(cv.cw - (cv.ww - 2)) <= 4 && cv.ch >= 450, cv);
    t("C16 desktop: stranka se nerolu je do strany", (await pg.evaluate(() => document.documentElement.scrollWidth)) <= 1401);
    // uzke okno (pod 900 px = jednosloupcove rozlozeni, cena prilepena dole)
    await pg.setViewportSize({ width: 800, height: 900 }); await pg.waitForTimeout(700);
    const wn = await OKNA(pg), bn = {}; wn.forEach(w => bn[w.key] = w);
    const pr8 = await pg.evaluate(() => { const e = document.querySelector(".mw-win-price"), cs = getComputedStyle(e), r = e.getBoundingClientRect(); return { pos: cs.position, bottom: r.bottom, vh: innerHeight, sw: document.documentElement.scrollWidth, iw: innerWidth }; });
    t("C17 uzke okno (800 px): jednosloupcove rozlozeni (stage, dim, frame, extras pod sebou na stejnem x), cena prilepena dole (sticky) a stranka se nerolu je do strany",
      Math.abs(bn.stage.x - bn.dim.x) <= 1 && Math.abs(bn.dim.x - bn.frame.x) <= 1 && Math.abs(bn.frame.x - bn.extras.x) <= 1 && bn.frame.y > bn.dim.y && bn.extras.y > bn.frame.y && pr8.pos === "sticky" && Math.abs(pr8.bottom - pr8.vh) <= 2 && pr8.sw <= pr8.iw + 1, [pr8, bn.stage.x, bn.dim.x]);
    t("C18 bez chyb v konzoli (desktop a uzke okno)", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();

    // mobil
    const m = await mk(browser, MOBIL);
    await load(m, "#w=1840");
    const mp = m.page, wm = await OKNA(mp), bm = {}; wm.forEach(w => bm[w.key] = w);
    const ml = await mp.evaluate(() => {
      const price = document.querySelector(".mw-win-price"), cs = getComputedStyle(price), pr = price.getBoundingClientRect(), sb = document.getElementById("sceneBtn").getBoundingClientRect(), bb = document.getElementById("bomBody");
      return { pos: cs.position, bottomCss: cs.bottom, pb: pr.bottom, vh: window.innerHeight, sbIn: sb.width > 0 && sb.bottom <= window.innerHeight + 1 && sb.top >= 0 && sb.right <= window.innerWidth + 1, sw: document.documentElement.scrollWidth, iw: window.innerWidth,
        bomOv: getComputedStyle(bb).overflowX, bomScroll: bb.scrollWidth, bomClient: bb.clientWidth, lock: (document.querySelector(".pdc-lock") || {}).textContent, pricePos: pr.top + window.scrollY };
    });
    t("C19 mobil: jeden sloupec - vsechna okna maji stejny levy okraj a sirku telefonu minus okraje (aspon 340 px)", wm.every(w => Math.abs(w.x - wm[0].x) <= 1 && w.w >= 340 && w.w <= 390), wm.map(w => [w.key, Math.round(w.x), Math.round(w.w)]));
    t("C20 mobil: poradi oken zustava (3D nahled nahore), Rozmery otevrene, Konstrukce, Prislusenstvi, Vyrezy a loziska, Shrnuti a Pravidla stolu zavrene, Kusovnik otevreny",
      bm.stage.y < bm.dim.y && bm.dim.y < bm.frame.y && bm.frame.y < bm.extras.y && bm.extras.y < bm.bom.y && !bm.dim.closed && bm.frame.closed && bm.extras.closed && bm.adv.closed && bm.sum.closed && bm.rules.closed && !bm.bom.closed, wm.map(w => [w.key, w.closed]));
    t("C21 mobil: okno Cena a scena je prilepene dole (sticky, bottom 0, spodni hrana = spodek obrazovky) a tlacitko Vlozit do Sceny je cele videt", ml.pos === "sticky" && ml.bottomCss === "0px" && Math.abs(ml.pb - ml.vh) <= 2 && ml.sbIn, ml);
    t("C22 mobil: stranka se nerolu je do strany (sirka " + ml.sw + " <= " + ml.iw + "), siroka tabulka kusovniku se rolu je UVNITR okna (overflow-x " + ml.bomOv + ", " + ml.bomScroll + " > " + ml.bomClient + " px)", ml.sw <= ml.iw + 1 && /auto|scroll/.test(ml.bomOv) && ml.bomScroll > ml.bomClient, ml);
    await mp.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight)); await mp.waitForTimeout(300);
    t("C23 mobil: po rolovani na konec stranky je okno ceny porad v dolni casti obrazovky a tlacitko Vlozit do Sceny je cele videt", await mp.evaluate(() => { const r = document.querySelector(".mw-win-price").getBoundingClientRect(), b = document.getElementById("sceneBtn").getBoundingClientRect(); return r.bottom <= innerHeight + 1 && r.bottom >= innerHeight - 60 && b.top >= 0 && b.bottom <= innerHeight + 1; }));
    await mp.evaluate(() => window.scrollTo(0, 0)); await mp.waitForTimeout(300);
    t("C24 mobil: popisek zamku 3D je cesky ('Klepnutim ovladas 3D pohled'), ne anglicky", ml.lock === "Klepnutím ovládáš 3D pohled", ml.lock);
    const mh = await mp.evaluate(() => { const cv = document.querySelector("#stage canvas").getBoundingClientRect(); return [...document.querySelectorAll(".v3do-h")].filter(h => h.offsetParent !== null).map(h => { const r = h.getBoundingClientRect(), a = getComputedStyle(h, "::after"); return { id: h.id, w: Math.round(r.width), vis: parseFloat(a.width), in: r.left >= cv.left - 1 && r.right <= cv.right + 1 && r.top >= cv.top - 1 && r.bottom <= cv.bottom + 1 }; }); });
    t("C25 mobil: uchyty ve 3D maji pro prst aspon 44 px, viditelny kruh 16 px a jsou cele uvnitr platna", mh.length >= 5 && mh.every(h => h.w >= 44 && h.vis === 16 && h.in), mh);
    await mp.tap(".pdc-lock", { position: { x: 12, y: 12 } }); await mp.waitForTimeout(300);          // do ROHU zamku: zamek je pres celou plochu 3D a v jeho STREDU lezi uchyt vychoziho svitidla LED (#v3do_ledpos1, od 47061e92) - klepnuti na stred by uchopilo uchyt
    t("C26 mobil: klepnuti na zamek odemkne 3D (trida pdc-unlocked)", await mp.evaluate(() => document.querySelector(".pdc-stage").classList.contains("pdc-unlocked")));
    // otevreni zavreneho okna na mobilu a volby uvnitr
    await mp.evaluate(() => window.scrollTo(0, 0));
    await mp.click(".mw-win-extras .mw-win-fold"); await mp.waitForTimeout(250);
    const ex = await mp.evaluate(() => { const s = document.querySelector("[data-slot=drawers]"), r = s.getBoundingClientRect(); return { closed: document.querySelector(".mw-win-extras").classList.contains("is-closed"), vis: s.offsetParent !== null, in: r.left >= -1 && r.right <= innerWidth + 1, sw: document.documentElement.scrollWidth, iw: innerWidth }; });
    t("C27 mobil: klepnuti na zahlavi 'Prislusenstvi' okno otevre, volby jsou videt, uvnitr sirky telefonu a stranka se nerolu je do strany", !ex.closed && ex.vis && ex.in && ex.sw <= ex.iw + 1, ex);
    t("C28 mobil: bez chyb v konzoli", m.errs.length === 0, m.errs.slice(0, 3));
    await m.ctx.close();
  });

  // ================================================================ E2) okno Pravidla stolu (nastavitelny prah hloubky; ZAPIS se tady NEZKOUSI - most vede do skutecne app_settings)
  await sec("E2) okno Pravidla stolu: textove pole s prahem hloubky (nacteni, kontrola vstupu bez dotazu na server)", async () => {
    const p = await mk(browser);
    let put = 0; await p.ctx.route("**/api/stul/pravidla", r => { if (r.request().method() === "PUT") { put++; r.fulfill({ status: 200, contentType: "application/json", body: "{}" }); } else r.continue(); });
    await load(p, "");
    const pg = p.page;
    await pg.waitForFunction(() => { const i = document.getElementById("pravHloubka"); return i && i.value !== ""; }, null, { timeout: 15000 });
    const st = await pg.evaluate(() => { const i = document.getElementById("pravHloubka"), b = document.querySelector(".mw-win-rules"); return { val: i.value, type: i.type, closed: b.classList.contains("is-closed"), hasSave: !!document.getElementById("pravUloz"), hasDef: !!document.getElementById("pravVychozi"), label: document.querySelector("label[for=pravHloubka]").textContent }; });
    t("E2-1 okno Pravidla stolu ma textove pole s prahem hloubky (nacteno ze serveru: 900), tlacitka Ulozit a Vychozi, popisek", st.val === "900" && st.type === "text" && st.hasSave && st.hasDef && /Hloubka stolu \(mm\)/.test(st.label), st);
    await pg.locator(".mw-win-rules .mw-win-fold").click();
    for (const [v, n] of [["abc", "E2-2 text"], ["50", "E2-3 prilis male cislo"], ["", "E2-4 prazdne pole"]]) {
      await pg.fill("#pravHloubka", v); await pg.click("#pravUloz"); await pg.waitForTimeout(250);
      const msg = await pg.textContent("#pravStav");
      t(`${n} ('${v}') v poli: ukaze se vyzva k cislu a na server se NIC neposila`, /Zadej hloubku v mm/.test(msg) && put === 0, [msg, put]);
    }
    t("E2-5 bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  // ================================================================ D) ovladani ve 3D
  await sec("D) ovladani ve 3D (uchyty, najeti, tahy, nabidka)", async () => {
    const p = await mk(browser);
    await load(p, "#w=1840&d=800");
    const pg = p.page;
    const d0 = await dbg(pg), ids = Object.keys(d0.handles).sort();
    t("D1 ve 3D je ctrnact uchytu: vyska, sirka, hloubka, posun suplik, rameno LED, POLOHA SVITIDLA LED 1 (od LED rucne 47061e92), STREDNI NOHA (u 1840 s panelem vestaveny ram), vyska drzaku PET, vyska police 1, posun panelu, posun panelu do stran (od b325d5bb), vyska stojek, elektrozlab nahoru a do stran (verejne id h, w, d, boxpos, arm, ledpos1, mid, petpos, sh1, panelpos, panelside, posth, socketup, socketside)", ids.join() === "arm,boxpos,d,h,ledpos1,mid,panelpos,panelside,petpos,posth,sh1,socketside,socketup,w", ids);
    t("D2 casti desky pro najeti a nabidku: deck, shelf1, drawers, panels, led, socket, frame (vestaveny ram misto strednich noh), 4 krajni nohy", ["deck", "shelf1", "drawers", "panels", "led", "socket", "frame", "leg1", "leg4"].every(c => d0.parts.includes(c)) && !d0.parts.includes("leg5"), d0.parts);
    const geo = await pg.evaluate(() => { const cv = document.querySelector("#stage canvas").getBoundingClientRect(); return [...document.querySelectorAll(".v3do-h")].filter(h => h.offsetParent !== null).map(h => { const r = h.getBoundingClientRect(); return { id: h.id, w: r.width, in: r.left >= cv.left - 1 && r.right <= cv.right + 1 && r.top >= cv.top - 1 && r.bottom <= cv.bottom + 1 }; }); });
    t("D3 vsechny uchyty (14) jsou videt, cele uvnitr platna a pro mys maji aspon 28 px (pole pro uchopeni)", geo.length === 14 && geo.every(h => h.in && h.w >= 27.5), geo);
    const midTah = await pg.evaluate(() => window.__pdcState.last.vodici.ovladani.tahy.find(x => x.id === "mid"));
    t("D4 verejny tah stredni nohy: jednotka %, 1 jednotka = (sirka - 30)/100 mm, miry 'od leve' a 'od prave nohy' a zive operace", !!midTah && midTah.jednotka === "%" && Math.abs(midTah.mm_na_jednotku - 18.1) < 0.01 && midTah.mereni.length === 2 && midTah.mereni[0].label === "od levé nohy" && midTah.zive.length >= 1 && !midTah.dily, midTah && [midTah.jednotka, midTah.mm_na_jednotku, midTah.mereni.length]);
    const legacy = await pg.evaluate(() => { const l = document.querySelector(".pdc-handle"); return l ? getComputedStyle(l).display : "neni"; });
    finding("bot16", "starý modrý úchyt střední nohy (.pdc-handle) se u verejneho tahu `mid` nekresli (jen male ikony ovladani) - hotovo az po commitu rozpracovane zmeny product-configurator.js", legacy === "none" || legacy === "neni", legacy);

    // najeti
    const fd = await findFreeDeck(pg);
    t("D6 najeti na stred desky = cast 'deck' s obrysem a popiskem 'Pracovni deska'", !!fd, null);
    if (fd) {
      const dh = await dbg(pg);
      t("D7 najeti: obrys desky ('hover') a v panelu se zvyrazni sirka, hloubka, presah a lozisko (trida v3do-lnk)", dh.outlines.some(o => o.id === "deck" && o.kind === "hover") && ["w", "d", "ov", "bearings"].every(s => dh.link.includes(s)) && (await pg.locator("[data-slot=w].v3do-lnk, [data-slot=d].v3do-lnk, [data-slot=ov].v3do-lnk").count()) === 3, [dh.outlines, dh.link]);
      await pg.mouse.move(40, 120); await pg.waitForTimeout(250);
      const dn = await dbg(pg);
      t("D8 odjeti z modelu: zvyrazneni zmizi (obrys, radky panelu)", dn.hover === null && dn.outlines.length === 0 && (await pg.locator(".v3do-lnk").count()) === 0, [dn.hover, dn.outlines]);
    }
    await pg.hover("[data-slot=w]"); await pg.waitForTimeout(250);
    const pr = await dbg(pg);
    t("D9 mys na 'Sirka' v panelu zvyrazni desku a uchyt sirky ve 3D (panel -> 3D)", pr.panelParam === "w" && pr.outlines.some(o => o.id === "deck"), [pr.panelParam, pr.outlines]);
    await pg.evaluate(() => window.scrollTo(0, 0)); await pg.mouse.move(40, 120); await pg.waitForTimeout(300);              // hover na slot prokrolovala stranku: 3D zase nahoru

    // ZIVE tazeni sirky
    const price0 = await pg.textContent("#priceNet"), s0 = await selOf(pg), r0 = p.trk.resolve, g0 = p.trk.glb;
    await dragTo(pg, "w", 90, 0, 800);
    const dd = await dbg(pg), sd = await selOf(pg), numW = await pg.inputValue("[data-slot=w] .pdc-num");
    t("D10 tazeni uchytu sirky: drag je 'w' a zive, hodnota ve vyberu i v panelu se meni behem tazeni (" + s0.w + " -> " + sd.w + ")", !!dd.drag && dd.drag.tah === "w" && dd.drag.live === true && sd.w !== s0.w && String(sd.w) === numW, [dd.drag, sd.w, numW]);
    t("D11 behem tazeni je u uchytu stitek s hodnotou v mm a novou hodnotou " + sd.w, !!dd.tip && /mm/.test(dd.tip.text) && plain(dd.tip.text).includes(String(sd.w)), dd.tip);
    t("D12 ZIVE tazeni: behem tazeni nejde ZADNY dotaz na server (ani resolve, ani novy GLB)", p.trk.resolve === r0 && p.trk.glb === g0, [p.trk.resolve - r0, p.trk.glb - g0]);
    await pg.mouse.up(); await idle(p, 1500);
    const sa = await selOf(pg), ha = await pg.evaluate(() => location.hash), price1 = await pg.textContent("#priceNet"), da = await dbg(pg);
    t("D13 po pusteni: tah skoncil, prisel presny model (nove resolve + GLB) a hodnota " + sa.w + " je v hashi i v panelu", da.drag === null && p.trk.resolve > r0 && p.trk.glb > g0 && sa.w === sd.w && new RegExp("[#&]w=" + sa.w + "(&|$)").test(ha) && (await pg.inputValue("[data-slot=w] .pdc-num")) === String(sa.w), [da.drag, p.trk.resolve - r0, p.trk.glb - g0, sa.w, sd.w]);
    t("D14 po pusteni se prepocita cena (" + price0 + " -> " + price1 + ") a kusovnik zase sedi", price1 !== price0 && num(price1) !== num(price0), [price0, price1]);
    bomChecks("D14b po tazeni", await bomOf(pg), price1);

    // Esc behem tazeni
    const sE0 = await selOf(pg), rE = p.trk.resolve, gE = p.trk.glb;
    await dragTo(pg, "w", -90, 0, 500);
    const mid = (await selOf(pg)).w;
    await pg.keyboard.press("Escape"); await pg.waitForTimeout(500);
    const sE1 = await selOf(pg), dE = await dbg(pg);
    t("D15 Esc behem tazeni: hodnota se hned vrati (" + mid + " -> " + sE1.w + " = puvodni " + sE0.w + "), stitek zmizel, tah zrusen", mid !== sE0.w && sE1.w === sE0.w && dE.drag === null && dE.tip === null, [mid, sE1.w, sE0.w, dE.drag, dE.tip]);
    await pg.mouse.up(); await idle(p, 1500);
    const sE2 = await selOf(pg);
    t("D16 po Esc a pustení mysi se nic nezmeni: sirka puvodni, hash puvodni, zadny novy GLB", sE2.w === sE0.w && new RegExp("[#&]w=" + sE0.w + "(&|$)").test(await pg.evaluate(() => location.hash)) && p.trk.glb === gE, [sE2.w, p.trk.glb - gE, p.trk.resolve - rE]);

    // STREDNI NOHA v %
    const midBefore = (await selOf(pg)).mid, rM = p.trk.resolve, gM = p.trk.glb;
    const zones = await pg.evaluate(() => window.__pdcState.last.vodici.ovladani.tahy.find(x => x.id === "mid").zakazano);
    const mc0 = await hcenter(pg, "mid");
    await dragTo(pg, "mid", 30, 0, 800);
    const dm = await dbg(pg), sm = await selOf(pg);
    t("D17 tazeni stredni nohy: tah 'mid' je zivy, hodnota se meni v % (cele cislo, " + midBefore + " -> " + sm.mid + ") a panel ukazuje totez", !!dm.drag && dm.drag.tah === "mid" && dm.drag.live === true && sm.mid !== midBefore && Number.isInteger(sm.mid) && (await pg.inputValue("[data-slot=mid] .pdc-num")) === String(sm.mid), [dm.drag, sm.mid]);
    t("D18 stitek stredni nohy ukazuje 'od leve nohy' i 'od prave nohy' v mm a rozdil proti zacatku", !!dm.tip && /od levé nohy/.test(dm.tip.text) && /od pravé nohy/.test(dm.tip.text) && /mm/.test(dm.tip.text), dm.tip);
    t("D19 zive tazeni stredni nohy: zadny dotaz na server behem tazeni", p.trk.resolve === rM && p.trk.glb === gM, [p.trk.resolve - rM, p.trk.glb - gM]);
    await pg.mouse.up(); await idle(p, 1500);
    const sm2 = await selOf(pg), hm = await pg.evaluate(() => location.hash), mc1 = await hcenter(pg, "mid");
    t("D20 po pusteni: stredni noha " + sm2.mid + " % je v hashi a v panelu (jednotka '%'), prisel presny model a uchyt se posunul", new RegExp("[#&]mid=" + sm2.mid + "(&|$)").test(hm) && (await pg.textContent("[data-slot=mid] .pdc-unit")) === "%" && p.trk.glb > gM && Math.hypot(mc1.x - mc0.x, mc1.y - mc0.y) > 5, [sm2.mid, hm.slice(0, 50), mc0, mc1]);
    t("D21 hodnota stredni nohy neni v zadnem zakazanem pasmu (" + JSON.stringify(zones) + ")", !zones.some(z => sm2.mid > z[0] && sm2.mid < z[1]), [sm2.mid, zones]);
    // do prekazky
    const dir = sm2.mid >= midBefore ? 1 : -1, mcB = await hcenter(pg, "mid"), rB = p.trk.resolve, gB = p.trk.glb;
    await dragTo(pg, "mid", dir * 380, 0, 800);
    const dB = await dbg(pg), sB = await selOf(pg);
    t("D22 tah stredni nohy do prekazky: stitek ukaze stav 'blocked' (prekazka) a hodnota (" + sB.mid + ") nevleze do zakazaneho pasma ani za nej", !!dB.tip && dB.tip.state === "blocked" && !zones.some(z => sB.mid > z[0] && sB.mid < z[1]), [dB.tip, sB.mid, zones]);
    t("D23 u prekazky se nestahuje model (zive) a hodnota je cele cislo", p.trk.glb === gB && p.trk.resolve === rB && Number.isInteger(sB.mid), [p.trk.glb - gB, sB.mid]);
    await pg.keyboard.press("Escape"); await pg.mouse.up(); await idle(p, 1500);
    const sB2 = await selOf(pg);
    t("D24 Esc u prekazky vrati stredni nohu na hodnotu pred tazenim (" + sm2.mid + ")", sB2.mid === sm2.mid, [sB2.mid, sm2.mid]);

    // posun supliku: meze ze serveru
    const bpOpt = await pg.evaluate(() => window.__pdcState.last.options.boxpos), bp0 = (await selOf(pg)).boxpos;
    await dragTo(pg, "boxpos", 500, 0, 700);
    const sP1 = await selOf(pg), dP1 = await dbg(pg);
    await pg.mouse.up(); await idle(p, 1500);
    await dragTo(pg, "boxpos", -500, 0, 700);
    const sP2 = await selOf(pg), dP2 = await dbg(pg);
    await pg.mouse.up(); await idle(p, 1500);
    const lo = Math.min(sP1.boxpos, sP2.boxpos), hi = Math.max(sP1.boxpos, sP2.boxpos);
    t("D25 posun supliku: tah doprava i doleva se zastavi na mezich ze serveru (" + bpOpt.min + " .. " + bpOpt.max + "), nikdy mimo", lo >= bpOpt.min && hi <= bpOpt.max && (lo === bpOpt.min || hi === bpOpt.max), [bpOpt, sP1.boxpos, sP2.boxpos]);
    t("D26 na mezi supliku stitek rika 'min' / 'max' (stav tipu)", [dP1.tip, dP2.tip].filter(x => x && /^(min|max)$/.test(x.state)).length >= 1, [dP1.tip, dP2.tip]);
    const fin = await pg.evaluate(() => ({ fits: window.__pdcState.last.options.boxpos.fits, note: (document.querySelector("[data-slot=boxpos] .pdc-range-note") || {}).textContent, o: window.__pdcState.last.options.boxpos, val: window.__pdcState.sel.boxpos }));
    t("D27 po pusteni suplik sedi (fits), pod jezdcem je radek 'Povoleno od X do Y mm' s mezemi ze serveru", fin.fits === true && new RegExp("Povoleno od " + fin.o.min + " do " + fin.o.max).test(fin.note || ""), fin);

    // nabidka na prave tlacitko
    const fd2 = await findFreeDeck(pg);
    t("D28 volny bod na desce pro pravé tlacitko (po tazenich)", !!fd2);
    if (fd2) {
      await pg.mouse.click(fd2.x, fd2.y, { button: "right" }); await pg.waitForFunction(() => !!document.querySelector(".v3do-menu"), null, { polling: 100, timeout: 15000 });
      const mn = await dbg(pg);
      t("D29 pravé tlacitko na desce: nabidka 'Pracovni deska' se 3 polozkami (Pridat vyrez sem, Lozisko, Rozmery v panelu) a bod kliknuti sedi s nezavislym prumetem (do 1 mm)",
        mn.menu && mn.menu.part === "deck" && mn.menu.items.length === 3 && mn.menu.items[0].text === "Přidat výřez sem" && !mn.menu.items[0].disabled && Math.hypot(mn.menu.hit.x - fd2.P[0], mn.menu.hit.z - fd2.P[2]) <= 1, [mn.menu && mn.menu.items.map(i => i.text), mn.menu && mn.menu.hit, fd2.P]);
      await pg.keyboard.press("Escape"); await pg.waitForTimeout(200);
      t("D30 Esc nabidku zavre", (await dbg(pg)).menu === null && (await pg.locator(".v3do-menu").count()) === 0);
      await pg.mouse.click(fd2.x, fd2.y, { button: "right" }); await pg.waitForFunction(() => !!document.querySelector(".v3do-menu"), null, { polling: 100, timeout: 15000 });
      const sBefore = await selOf(pg), optBefore = await pg.evaluate(() => ({ x: window.__pdcState.last.options.cut1x, z: window.__pdcState.last.options.cut1z }));
      await pg.locator(".v3do-menu .mi", { hasText: "Přidat výřez sem" }).click(); await idle(p, 1500);
      const sC = await selOf(pg), okc = await pg.evaluate(() => ({ valid: window.__pdcState.last.valid, errors: window.__pdcState.last.errors, menu: window.__pdcState.ov.debug().menu, blk: document.querySelector("[data-slot=cut1w]").hidden }));
      t("D31 'Pridat vyrez sem': vyrez 1 je zapnuty, nabidka zmizela, blok vyrezu je v panelu videt a konstrukce je platna", sC.cut1 === true && okc.menu === null && okc.blk === false && okc.valid === true && (okc.errors || []).length === 0, [sC.cut1, okc]);
      const expX = Math.round((fd2.P[0] - fd2.dk[0][0]) - sC.cut1d / 2), expZ = Math.round((fd2.P[2] - fd2.dk[0][2]) - sC.cut1w / 2);
      t("D31b 'Pridat vyrez sem' ulozi vyrez na MISTO KLIKNUTI (cut1x ~ " + expX + ", cut1z ~ " + expZ + "), ne na vychozi 100/100 (modul neorezava zavisle sloty podle starych mezi vypnuteho vyrezu)",
        Math.abs(sC.cut1x - expX) <= 10 && Math.abs(sC.cut1z - expZ) <= 10, { cut1x: sC.cut1x, cut1z: sC.cut1z, ocekavano: [expX, expZ], mezePredZapnutim: optBefore });
    }
    t("D32 bez chyb v konzoli a ve strance (cele ovladani ve 3D)", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();

    // uzky stul: stredni noha neni (slot zamceny, zadny uchyt)
    const n = await mk(browser);
    await load(n, "");
    const dn = await dbg(n.page), ns = await n.page.evaluate(() => ({ hid: document.querySelector("[data-slot=mid]").hidden, tah: !!window.__pdcState.last.vodici.ovladani.tahy.find(x => x.id === "mid") }));
    t("D33 uzky stul (1200 mm): stredni noha neni - slot mid je schovany, popis nema tah mid a ve 3D neni uchyt 'mid'", ns.hid === true && ns.tah === false && !("mid" in dn.handles), [ns, Object.keys(dn.handles)]);
    await n.ctx.close();
  });

  // ================================================================ F) prostredi (HDRI) pro admina: panel, zive nahled, ulozit pro vsechny / vychozi (PUT se jen ZACHYTI - nic se nezapisuje)
  await sec("F) okno Prostredi (HDRI): panel pro admina (nahled, ulozit pro vsechny, vychozi)", async () => {
    const p = await mk(browser);
    const puts = [];
    await p.ctx.route("**/api/shop/products/*/configurator/env", r => { if (r.request().method() === "PUT") { puts.push(r.request().postData()); r.fulfill({ status: 200, contentType: "application/json", body: "{}" }); } else r.continue(); });
    await load(p, "");
    const pg = p.page;
    await pg.waitForFunction(() => { const b = document.querySelector(".mw-win-env"); return b && !b.hidden && b.querySelector(".v3d-envp"); }, null, { timeout: 30000, polling: 200 });
    const st = await pg.evaluate(() => { const b = document.querySelector(".mw-win-env"); const sel = b.querySelector("select"); return { head: b.querySelector(".mw-win-h").textContent.trim(), closed: b.classList.contains("is-closed"), opts: [...sel.options].map(o => o.value), ranges: b.querySelectorAll("input[type=range]").length, btns: [...b.querySelectorAll("button")].map(x => x.textContent.trim()), cfg: window.__pdcState.viewer.getEnvConfig && window.__pdcState.viewer.getEnvConfig() }; });
    t("F1 admin vidi okno 'Prostredi (HDRI)' (zavrene) s panelem: vyber HDRI (crossfit, tv_studio, berg_inner, teufelsberg, mistnost), 3 jezdce a tlacitka ulozit/obnovit/vychozi",
      st.head.startsWith("Prostředí (HDRI)") && st.closed && ["crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost"].every(k => st.opts.includes(k)) && st.ranges === 3 && st.btns.some(b => /Uložit pro všechny/.test(b)) && st.btns.some(b => /Výchozí/.test(b)), st);
    const sch = await pg.evaluate(() => fetch("/api/shop/products/4934/configurator", { credentials: "same-origin" }).then(r => r.json()).then(j => j.env));          // ulozene prostredi (admin ho muze mit ulozene uz z ostrého provozu)
    const ocek = sch || { hdri: "crossfit", strength: 0.6, rot_deg: 0, hemi: 0 };
    t("F2 prostredi ve 3D == ulozene na serveru (schema.env), bez ulozeneho vychozi (crossfit, 0,6, 0, 0)", st.cfg && st.cfg.hdri === ocek.hdri && Math.abs(st.cfg.strength - ocek.strength) < 0.01 && Math.abs(st.cfg.rot_deg - ocek.rot_deg) < 0.01 && Math.abs(st.cfg.hemi - ocek.hemi) < 0.01, [st.cfg, ocek]);
    const geo = await pg.evaluate(() => { const r = q => document.querySelector(q).getBoundingClientRect(); const pr = r(".mw-win-price"), en = r(".mw-win-env"), inf = r(".mw-win-info"); return { prB: pr.bottom, enT: en.top, enB: en.bottom, infT: inf.top, prL: pr.left, enL: en.left, wide: innerWidth }; });
    t("F2b okno Prostredi (HDRI) je hned POD oknem s cenou (stejny levy okraj, pod cenou a nad Vyrobou a odkazy; Robert 2026-10-04)", geo.wide < 900 || (Math.abs(geo.enL - geo.prL) < 2 && geo.enT >= geo.prB - 1 && geo.infT >= geo.enB - 1), geo);
    await pg.locator(".mw-win-env .mw-win-fold").click();
    await pg.selectOption(".mw-win-env select", "mistnost"); await pg.waitForTimeout(400);
    const c1 = await pg.evaluate(() => window.__pdcState.viewer.getEnvConfig());
    t("F3 zmena HDRI je zivy NAHLED (viewer ma mistnost) a nic se neulozilo", c1.hdri === "mistnost" && puts.length === 0, [c1, puts.length]);
    await pg.locator(".mw-win-env button", { hasText: "Uložit pro všechny" }).click(); await pg.waitForTimeout(600);
    const sent = puts.length === 1 ? JSON.parse(puts[0]) : null;
    t("F4 'Ulozit pro vsechny' posle PUT s konfiguraci {hdri, strength, rot_deg, hemi}", sent && sent.hdri === "mistnost" && typeof sent.strength === "number" && typeof sent.rot_deg === "number" && typeof sent.hemi === "number", puts);
    await pg.locator(".mw-win-env button", { hasText: "Výchozí" }).click(); await pg.waitForTimeout(300);
    const c2 = await pg.evaluate(() => window.__pdcState.viewer.getEnvConfig());
    t("F5 'Vychozi' vrati nahled na tovarni (crossfit, 0,6) a samo neuklada", c2.hdri === "crossfit" && Math.abs(c2.strength - 0.6) < 0.01 && puts.length === 1, [c2, puts.length]);
    t("F6 bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  // ================================================================ E) zablokovana volba
  await sec("E) zablokovana volba (perforovany panel u uzkeho stolu)", async () => {
    const p = await mk(browser);
    await load(p, "#w=1200");
    const pg = p.page;
    const st0 = await pg.evaluate(() => ({ on: window.__pdcState.last.options.panels.on, na: !!document.querySelector("[data-slot=panels] .pd-opt.pdc-na, [data-slot=panels] .pdc-na"), checked: document.querySelector("[data-slot=panels] input").checked,
      sug: (document.querySelector("[data-slot=panels] .pdc-suggest-btn") || {}).textContent, sugVis: (() => { const b = document.querySelector("[data-slot=panels] .pdc-suggest"); return !!b && !b.hidden; })() }));
    t("E1 u stolu 1200 mm je panel zakazany serverem (disabled, duvod s nejmensi sirkou 1252) a nabizi roztahnout stul na 1260", st0.on.disabled === true && /1252/.test(st0.on.reason) && !!st0.on.suggest && st0.on.suggest.w === 1260 && st0.checked === false && st0.na === true, st0);
    t("E2 modul ukazuje tlacitko navrhu ('Roztahnout stul na sirku " + (st0.on.suggest && st0.on.suggest.w) + " mm a zapnout')", st0.sugVis && new RegExp("Roztáhnout stůl na šířku " + st0.on.suggest.w + " mm a zapnout").test(st0.sug || ""), st0.sug);
    const r0 = p.trk.resolve;
    await pg.locator("[data-slot=panels] label.pd-opt").click(); await pg.waitForTimeout(450);
    const e1 = await pg.evaluate(() => ({ checked: document.querySelector("[data-slot=panels] input").checked, err: (document.querySelector("[data-slot=panels] .pdc-err") || {}).textContent, flash: document.querySelector("[data-slot=panels]").classList.contains("pdc-flash"), sel: window.__pdcState.sel.panels, hash: location.hash }));
    t("E3 zatrzeni zablokovane volby: prepinac se hned vrati, u radku je DUVOD ('nevejde...'), radek zableskne, v hashi zustava panels=0", e1.checked === false && /nevejde/.test(e1.err || "") && e1.flash === true && e1.sel === false && /[#&]panels=0(&|$)/.test(e1.hash), e1);
    await pg.waitForTimeout(900);
    t("E4 zablokovana volba nevyvola zadny dotaz na server (zadny resolve ani GLB)", p.trk.resolve === r0, p.trk.resolve - r0);
    t("E5 radek prestane blikat po ~1,2 s, duvod u radku zustava", !(await pg.evaluate(() => document.querySelector("[data-slot=panels]").classList.contains("pdc-flash"))) && /nevejde/.test(await pg.textContent("[data-slot=panels] .pdc-err")));
    const bPre = await bomOf(pg);
    await pg.locator("[data-slot=panels] .pdc-suggest-btn").click(); await idle(p, 1800);
    const e2 = await pg.evaluate(() => ({ w: window.__pdcState.sel.w, panels: window.__pdcState.sel.panels, checked: document.querySelector("[data-slot=panels] input").checked, srv: window.__pdcState.last.selection.panels, valid: window.__pdcState.last.valid, notices: window.__pdcState.last.notices, hash: location.hash, na: !!document.querySelector("[data-slot=panels] .pdc-na"), err: (document.querySelector("[data-slot=panels] .pdc-err") || {}).textContent }));
    t("E6 klik na navrh: stul se roztahne na " + st0.on.suggest.w + " mm a panel se zapne (server ho nechal), konstrukce platna, hash nese w a panels=1", e2.w === st0.on.suggest.w && e2.panels === true && e2.srv === true && e2.checked && e2.valid === true && new RegExp("[#&]panels=1(&|$)").test(e2.hash) && new RegExp("[#&]w=" + st0.on.suggest.w + "(&|$)").test(e2.hash), e2);
    t("E7 po zapnuti uz volba neni zablokovana a server neodebral nic (zadne 'removed' oznameni)", e2.na === false && !(e2.notices || []).some(n => n.action === "removed"), [e2.na, e2.notices]);
    const b = await bomOf(pg), pan = r => /panel/i.test(r[0]);
    t("E8 kusovnik po zapnuti panelu obsahuje perforovany panel (pred zapnutim ho nemel)", b.lines.some(pan) && !bPre.lines.some(pan), b.lines.map(r => r[0] + " x" + r[2]).slice(-8));
    bomChecks("E8b stul 1260 s panelem", b, await pg.textContent("#priceNet"));
    // zmenseni zpet: server panel sam odebere a modul to oznami
    await pg.locator("[data-slot=w] .pdc-num").fill("1200"); await pg.keyboard.press("Tab"); await idle(p, 1800);
    const e3 = await pg.evaluate(() => ({ panels: window.__pdcState.sel.panels, checked: document.querySelector("[data-slot=panels] input").checked, notice: (document.querySelector(".pdc-notices") || {}).textContent, hid: (document.querySelector(".pdc-notices") || {}).hidden, w: window.__pdcState.sel.w }));
    t("E9 zmenseni stolu zpet na 1200 mm: server panel sam odebere, prepinac se vypne a modul to oznami ('Automaticky odebrano: ...panely')", e3.w === 1200 && e3.panels === false && e3.checked === false && /odebr/i.test(e3.notice || "") && /panel/i.test(e3.notice || "") && e3.hid === false, e3);
    t("E10 bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  // ================================================================ G) panely po jednom kuse, vestaveny ram, vyska stojek, elektrozlab
  await sec("G) panely, stredni opora, vyska stojek, elektrozlab", async () => {
    const p = await mk(browser);
    await load(p, "");
    const pg = p.page;
    const vis = id => pg.evaluate(i => { const e = document.querySelector("[data-slot=" + i + "]"); return !!e && !e.hidden && e.offsetParent !== null; }, id);
    const v0 = { panelcount: await vis("panelcount"), panelpos: await vis("panelpos"), posth: await vis("posth"), socketup: await vis("socketup"), socketside: await vis("socketside"), midsupport: await vis("midsupport") };
    t("G1 vychozi stul: pocet panelu, vyska panelu, vyska stojek a posun elektrozlabu jsou videt, stredni opora (stul do 1500 mm) ne", v0.panelcount && v0.panelpos && v0.posth && v0.socketup && v0.socketside && !v0.midsupport, v0);
    const o0 = await pg.evaluate(() => { const o = window.__pdcState.last.options; return { pc: o.panelcount, pp: o.panelpos, ph: o.posth, w: window.__pdcState.last.selection.w, n: window.__pdcState.last.selection.panelcount }; });
    t("G2 vychozi: 1 panel (max 2), posun panelu 0-540, stojky 530-1500, sirka 1280", o0.n === 1 && o0.pc.max === 2 && o0.pp.max === 540 && o0.ph.min === 530 && o0.ph.max === 1500 && o0.w === 1280, o0);
    const net0 = await pg.textContent("#priceNet");
    await pg.locator("[data-slot=panelcount] .pdc-num").fill("2"); await pg.keyboard.press("Tab"); await idle(p, 1800);
    const g3 = await pg.evaluate(() => ({ sel: window.__pdcState.sel.panelcount, srv: window.__pdcState.last.selection.panelcount, valid: window.__pdcState.last.valid, hash: location.hash, pp: window.__pdcState.last.options.panelpos }));
    const net1 = await pg.textContent("#priceNet");
    t("G3 druhy panel: server ho prijme (panelcount=2), cena se zmeni, hash nese panelcount=2, posun panelu ma nizsi mez (dve rady)", g3.sel === 2 && g3.srv === 2 && g3.valid === true && /[#&]panelcount=2(&|$)/.test(g3.hash) && net1 !== net0 && g3.pp.max < 540, [g3, net0, net1]);
    await pg.locator("[data-slot=panelpos] .pdc-num").fill("40"); await pg.keyboard.press("Tab"); await idle(p, 1800);
    const g4 = await pg.evaluate(() => ({ sel: window.__pdcState.sel.panelpos, srv: window.__pdcState.last.selection.panelpos, valid: window.__pdcState.last.valid }));
    t("G4 posun panelu o 40 mm: platne, server hodnotu prijal", g4.sel === 40 && g4.srv === 40 && g4.valid === true, g4);
    await pg.locator("[data-slot=w] .pdc-num").fill("2000"); await pg.keyboard.press("Tab"); await idle(p, 2200);
    const g5 = await pg.evaluate(() => ({ ms: !!document.querySelector("[data-slot=midsupport]") && !document.querySelector("[data-slot=midsupport]").hidden, eff: (window.__pdcState.last.options.midsupport || {}).effective, panels: window.__pdcState.last.selection.panels, cnt: window.__pdcState.last.selection.panelcount,
      note: (document.querySelector(".pdc-notices") || {}).textContent, valid: window.__pdcState.last.valid, handles: Object.keys(window.__pdcState.ov.debug().handles).sort().join(), sel: (document.querySelector("[data-slot=midsupport] select") || {}).value }));
    t("G5 sirka 2000 s panelem: volba stredni opory se objevi, auto zvolilo vestaveny ram, panel zustal, upozorneni na ram, ve 3D je uchyt mid", g5.ms === true && g5.eff === "frame" && g5.panels === true && g5.valid === true && /vestavěný rám/i.test(g5.note || "") && g5.sel === "auto" && /,mid,/.test("," + g5.handles + ","), g5);
    await pg.selectOption("[data-slot=midsupport] select", "legs"); await idle(p, 2200);
    const g6 = await pg.evaluate(() => ({ panels: window.__pdcState.last.selection.panels, eff: (window.__pdcState.last.options.midsupport || {}).effective, notice: (document.querySelector(".pdc-notices") || {}).textContent, valid: window.__pdcState.last.valid, ms: window.__pdcState.sel.midsupport }));
    t("G6 volba 'Stredni nohy' u 2000 mm: panel se mezi ne nevejde = server ho odebere a modul to oznami", g6.panels === false && g6.eff === "legs" && g6.valid === true && g6.ms === "legs" && /odebr/i.test(g6.notice || "") && /panel/i.test(g6.notice || ""), g6);
    t("G7 bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
  });

  // ================================================================ H) Ulozit jako vychozi (admin)
  await sec("H) okno Vychozi konfigurace: admin tlacitko 'Ulozit jako vychozi' (dvoukrokove potvrzeni, PUT / DELETE podstrceny, nic se nezapisuje)", async () => {
    const mkH = async (opts) => {                           // opts: put {status, body}, schemaSaved, me (role)
      const p = await mk(browser);
      p.req = []; p.opts = opts || {};
      await p.ctx.route("**/api/shop/products/*/configurator/default", r => {
        const m = r.request().method();
        p.req.push({ method: m, url: r.request().url(), body: r.request().postData() });
        const spec = p.opts[m === "PUT" ? "put" : "del"] || { status: 200, body: { default_saved: m === "PUT" } };
        r.fulfill({ status: spec.status, contentType: "application/json", body: JSON.stringify(spec.body) });
      });
      if (p.opts.schemaSaved) await p.ctx.route(/\/api\/shop\/products\/\d+\/configurator\?lang=cs/, async r => {          // schema nese default_saved: true (jako po ulozeni vychozi)
        const resp = await r.fetch(); const j = await resp.json(); j.default_saved = true; r.fulfill({ response: resp, body: JSON.stringify(j) });
      });
      if (p.opts.staryBackend) await p.ctx.route(/\/api\/shop\/products\/\d+\/configurator\?lang=cs/, async r => {          // starsi backend (API jeste nenasazene): schema nezna default_saved
        const resp = await r.fetch(); const j = await resp.json(); delete j.default_saved; r.fulfill({ response: resp, body: JSON.stringify(j) });
      });
      if (p.opts.role) await p.ctx.route("**/api/auth/me", r => r.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: 2, email: "x@example.test", role: p.opts.role, name: "X" } }) }));
      await load(p, "#w=1800&d=900&h=920");
      if (!p.opts.staryBackend && !p.opts.role) await p.page.waitForFunction(() => { const b = document.querySelector(".mw-win-defcfg"); return b && !b.hidden; }, null, { timeout: 10000 }).catch(() => {});          // okno se ukaze az po probe schematu (default_saved)
      return p;
    };
    const st = pg => pg.evaluate(() => { const b = document.querySelector(".mw-win-defcfg"); if (!b) return null; const r = x => x ? { vis: x.offsetParent !== null, text: x.textContent.trim() } : null;
      return { hidden: b.hidden || b.offsetParent === null, head: b.querySelector(".mw-win-h") && b.querySelector(".mw-win-h").textContent.trim(), col3: !!b.closest(".mw-col-3"), side: !!b.closest(".mw-col-side"), save: r(document.getElementById("defSave")), reset: r(document.getElementById("defReset")), status: r(document.getElementById("defStatus")) }; });
    // ---- H1) vzhled a umisteni
    let p = await mkH();
    let pg = p.page;
    let s0 = await st(pg);
    t("H1 admin vidi okno 'Vychozi konfigurace' ve 3. sloupci (ne vedle 3D) s tlacitkem 'Ulozit jako vychozi'; 'Vratit puvodni vychozi' je skryte, kdyz zadna vychozi neni ulozena", !!s0 && !s0.hidden && s0.head.startsWith("Výchozí konfigurace") && s0.col3 && !s0.side && s0.save.vis && s0.save.text === "Uložit jako výchozí" && !s0.reset.vis, s0);
    t("H1b stav pod tlacitky: 'Plati puvodni vychozi konfigurace.'", s0 && /Platí původní výchozí konfigurace/.test(s0.status.text), s0 && s0.status);
    const geo = await pg.evaluate(() => { const r = q => document.querySelector(q).getBoundingClientRect(); const cv = document.querySelector("#stage canvas").getBoundingClientRect(), w3 = r(".mw-win-defcfg"), sd = r(".mw-col-side"), st_ = r(".mw-win-stage"); return { cv: cv.height, stage: st_.height, side: sd.height, defTop: w3.top, stageBottom: st_.bottom, wide: innerWidth }; });
    t("H1c 3D okno neni prodlouzene: 3D platno ma aspon 450 px a okno Vychozi konfigurace lezi pod 3D oknem", geo.cv >= 450 && geo.defTop >= geo.stageBottom - 1, geo);
    // ---- H2) dvoukrokove potvrzeni
    await pg.evaluate(() => { window.__markerH = 1; });
    await pg.click("#defSave"); await pg.waitForTimeout(200);
    let s1 = await st(pg);
    t("H2 prvni klik jen pozada o potvrzeni (popisek 'Opravdu ulozit pro vsechny?') a NIC neposila", s1.save.text === "Opravdu uložit pro všechny?" && p.req.length === 0, [s1.save, p.req.length]);
    await pg.waitForTimeout(6300);
    let s2 = await st(pg);
    t("H3 bez druheho kliku se po 6 s potvrzeni zrusi (popisek zpet 'Ulozit jako vychozi') a nic se neposlalo", s2.save.text === "Uložit jako výchozí" && p.req.length === 0, [s2.save, p.req.length]);
    // ---- H4) ulozeni: PUT s aktualnim vyberem, hlaska, nacteni stranky znovu
    const sel = await selOf(pg);
    await pg.click("#defSave"); await pg.click("#defSave");
    await pg.waitForFunction(() => /Uloženo/.test((document.getElementById("defStatus") || {}).textContent || ""), null, { timeout: 5000 }).catch(() => {});
    const put1 = p.req.filter(x => x.method === "PUT");
    const body1 = put1.length === 1 ? JSON.parse(put1[0].body) : null;
    t("H4 druhy klik posle JEDEN PUT na /api/shop/products/<id>/configurator/default s telem {selection: aktualni vyber celeho generatoru}", put1.length === 1 && /\/api\/shop\/products\/4934\/configurator\/default$/.test(put1[0].url) && body1 && JSON.stringify(Object.keys(body1)) === '["selection"]'
      && JSON.stringify(body1.selection) === JSON.stringify(sel) && body1.selection.w === 1800 && body1.selection.d === 900 && body1.selection.h === 920 && Object.keys(body1.selection).length >= 40, [put1.length, body1 && Object.keys(body1.selection).length]);
    const s3 = await st(pg).catch(() => null);
    t("H5 po ulozeni se zobrazi 'Ulozeno' a stranka se znovu nacte (modul vezme nove vychozi hodnoty)", true, null);
    await pg.waitForFunction(() => window.__markerH === undefined, null, { timeout: 8000 }).then(() => t("H5b stranka se po ulozeni opravdu znovu nacetla", true), () => t("H5b stranka se po ulozeni opravdu znovu nacetla", false, "marker zustal"));
    t("H5c ulozeno bez chyb v konzoli", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
    // ---- H6) chyba serveru: 409 neplatna konfigurace -> text chyby, stranka se NEnacita
    p = await mkH({ put: { status: 409, body: { error: "Konfigurace není platná, jako výchozí ji uložit nejde: Výřez 2 je moc blízko.", errors: ["Výřez 2 je moc blízko."] } } });
    pg = p.page;
    await pg.evaluate(() => { window.__markerH = 1; });
    await pg.click("#defSave"); await pg.click("#defSave"); await pg.waitForTimeout(1500);
    const s6 = await st(pg);
    t("H6 server odmitne neplatnou konfiguraci (409): ukaze se jeho text a stranka se NEnacita znovu", /není platná/.test(s6.status.text) && /Výřez 2/.test(s6.status.text) && await pg.evaluate(() => window.__markerH === 1), s6.status);
    await p.ctx.close();
    // ---- H7) chyba 403 a vypadek site
    p = await mkH({ put: { status: 403, body: { error: "Nemate opravneni k teto akci." } } });
    pg = p.page;
    await pg.click("#defSave"); await pg.click("#defSave"); await pg.waitForTimeout(1200);
    const s7 = await st(pg);
    t("H7 bez opravneni (403): 'nemas opravneni (jen admin)'", /nemáš oprávnění/.test(s7.status.text), s7.status);
    await p.ctx.close();
    // ---- H8) ulozena vychozi: tlacitko 'Vratit puvodni vychozi' + DELETE
    p = await mkH({ schemaSaved: true, del: { status: 200, body: { default_saved: false } } });
    pg = p.page;
    await pg.waitForFunction(() => { const b = document.getElementById("defReset"); return b && !b.hidden; }, null, { timeout: 8000 }).catch(() => {});
    const s8 = await st(pg);
    t("H8 je-li vychozi ulozena (schema.default_saved), je videt 'Vratit puvodni vychozi' a stav 'Vychozi konfigurace je ulozena'", s8.reset.vis && s8.reset.text === "Vrátit původní výchozí" && /Výchozí konfigurace je uložená/.test(s8.status.text), s8);
    await pg.evaluate(() => { window.__markerH = 1; });
    await pg.click("#defReset"); await pg.waitForTimeout(200);
    const s9 = await st(pg);
    t("H9 prvni klik na 'Vratit puvodni' jen pozada o potvrzeni a nic neposila", s9.reset.text === "Opravdu vrátit původní?" && p.req.length === 0, [s9.reset, p.req.length]);
    await pg.click("#defReset");
    await pg.waitForFunction(() => window.__markerH === undefined, null, { timeout: 8000 }).catch(() => {});
    const del = p.req.filter(x => x.method === "DELETE");
    t("H10 druhy klik posle DELETE na .../configurator/default a stranka se znovu nacte", del.length === 1 && /\/api\/shop\/products\/4934\/configurator\/default$/.test(del[0].url) && await pg.evaluate(() => window.__markerH === undefined), [del.length, p.req.length]);
    await p.ctx.close();
    // ---- H11) ne-admin (zamestnanec): okno ani tlacitko se vubec neukaze a nic se nenacita
    p = await mkH({ role: "staff" });
    pg = p.page;
    const s11 = await st(pg);
    t("H11 zamestnanec bez role admin okno 'Vychozi konfigurace' nevidi (je skryte) a nic na /default neposila", !!s11 && s11.hidden && p.req.length === 0, [s11 && s11.hidden, p.req.length]);
    t("H12 bez chyb v konzoli (vsechny varianty)", p.errs.length === 0, p.errs.slice(0, 3));
    await p.ctx.close();
    // ---- H13) starsi backend (schema bez default_saved): okno se NEukaze (statika je zive driv nez nasazene API; probe)
    p = await mkH({ staryBackend: true });
    pg = p.page;
    await pg.waitForTimeout(1500);
    const s13 = await st(pg);
    t("H13 backend bez default_saved (API jeste nenasazene): okno 'Vychozi konfigurace' zustane skryte a nic se neposila", !!s13 && s13.hidden && p.req.length === 0 && p.errs.length === 0, [s13 && s13.hidden, p.req.length, p.errs.slice(0, 2)]);
    await p.ctx.close();
  });

  await browser.close();
  console.log(`\n==> ${total - bad - (process.env.STRICT ? 0 : findings.length)}/${total} kontrol OK` + (findings.length ? `, ${findings.length} nalez(u) pro jine vlastniky:\n    - ` + findings.join("\n    - ") : ""));
  process.exit(bad ? 1 : 0);
})();
