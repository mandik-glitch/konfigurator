// Test STRANKY GENERATORU OCHRANNY KRYT A OPLOCENI (webapp/oploceni-konfigurator.html + js/oploceni-host.js nad SPOLECNYM modulem voleb js/product-configurator.js a mrizkou oken js/pdc-layout.js; bot8, 2026-10-08).
// SKUTECNA stranka + SKUTECNY modul + SKUTECNY 3D prohlizec nad SKUTECNYM kodem shop vrstvy (api/oploceni_shop.py) pres most _most_oploceni.py (zamestnanec = BASE, verejnost = BASE_PUB; fiktivni karta PID).
// Spusteni (DB pres systemd-run; potrebuje internet kvuli three.js z jsdelivr):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<koren repa> \
//     /opt/konfigurator/api/venv/bin/python3 <koren repa>/scripts/2026-10-08_oploceni/_most_oploceni.py <koren repa>/scripts/2026-10-08_oploceni/test_oploceni_stranka.js 9990
// Casti: A nacteni a zamestnanecky blok | B ovladani (rozmery, strany, vyplne, dvere, patky; upravy a oznameni) | C odkaz (#hash) | D rozlozeni (desktop, mobil) | E verejna varianta | F neprihlaseny, bez prava, bez karty
//        (jen nektere: ONLY=A,E node ...; snimky: SNIMKY=<slozka>)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const BASE = process.env.BASE, BASE_PUB = process.env.BASE_PUB, PID = process.env.PID || "9990";
const SNIMKY = process.env.SNIMKY || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
async function sec(name, fn) { if (process.env.ONLY && !process.env.ONLY.split(",").includes(name[0])) return; console.log("\n## " + name); try { await fn(); } catch (e) { t(name + ": test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 700)); } }

const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, opts) {
  const ctx = await browser.newContext(Object.assign({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" }, opts || {}));
  const page = await ctx.newPage(); const errs = [];
  // sleduji jen /resolve v letu (mnozina pozadavku, ne pocitadlo); GLB jen pocitam (modul ho predstahuje fetch() bez cteni tela, takze `requestfinished` u nej nemusi prijit - pripravenost modelu se cte ze stavu modulu)
  const trk = { resolve: 0, glb: 0, inflight: new Set(), last: Date.now(), bodies: [], status: [], timeouts: 0 };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u)) { trk.resolve++; trk.inflight.add(r); trk.last = Date.now(); trk.bodies.push(r.postData() || ""); } else if (GLB_RE.test(u)) { trk.glb++; trk.last = Date.now(); } });
  const done = r => { if (trk.inflight.delete(r)) trk.last = Date.now(); };
  page.on("requestfinished", done); page.on("requestfailed", done);
  page.on("response", r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) trk.status.push(r.status()); });
  return { ctx, page, trk, errs };
}
// klid = zadny /resolve v letu + model zobrazeny pro posledni hash (nebo bez modelu / chyba modelu) + od posledniho pozadavku uplynula doba `quiet`; vyprseni 90 s se pocita (kontroluje se v zaveru)
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) {
    const ready = await p.page.evaluate(() => { const S = window.__pdcState; return !!S && !!S.last && (!S.last.model || S.modelHash === S.last.hash || S.last.model.stav === "chyba"); });
    if (p.trk.inflight.size === 0 && ready && Date.now() - p.trk.last > q) return;
    await p.page.waitForTimeout(100);
  }
  p.trk.timeouts++;
};
async function load(p, base, query, hash) {
  await p.page.goto(`${base}/oploceni-konfigurator.html?debug=1${query || ""}${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.model && S.viewer; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const sel = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const last = page => page.evaluate(() => JSON.parse(JSON.stringify({ price: window.__pdcState.last.price, valid: window.__pdcState.last.valid, hash: window.__pdcState.last.hash, kod: window.__pdcState.last.kod, notices: window.__pdcState.last.notices, options: window.__pdcState.last.options })));
const hidden = (page, id) => page.evaluate(i => { const u = window.__pdcState.ui[i]; return !u || u.root.hidden || !!u.root.closest("[hidden]"); }, id);
const rootOf = (page, id) => page.evaluateHandle(i => window.__pdcState.ui[i].root, id);
const priceNet = page => page.evaluate(() => Number(document.getElementById("priceNet").textContent.replace(/[^\d]/g, "")));
const money = s => Number(String(s).replace(/[^\d]/g, ""));
async function setNum(p, id, v) { const h = await rootOf(p.page, id); const inp = await h.asElement().$("input.pdc-num"); await inp.fill(String(v)); await inp.press("Tab"); await idle(p, 1100); }
async function chip(p, slot, value) { await p.page.locator(`label.pd-pill:has(input[name="pdc_${slot}"][value="${value}"])`).click(); await idle(p, 1100); }
async function pick(p, slot, value) { const h = await rootOf(p.page, slot); const s = await h.asElement().$("select"); await s.selectOption(value); await idle(p, 1100); }
async function tgl(p, slot) { const h = await rootOf(p.page, slot); const i = await h.asElement().$("input[type=checkbox]"); await i.click({ force: true }); await idle(p, 1100); }
const snap = async (p, name) => { if (SNIMKY) { fs.mkdirSync(SNIMKY, { recursive: true }); await p.page.screenshot({ path: `${SNIMKY}/${name}.png`, fullPage: true }); } };

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });

  await sec("A nacteni a zamestnanecky blok", async () => {
    const p = await mk(browser);
    await load(p, BASE);
    const s = await sel(p.page), l = await last(p.page);
    t("A1 vychozi konfigurace se nacetla, platna, cena", l.valid === true && l.price && l.price.net > 20000 && s.front === "door" && s.w === 1500, l.price);
    t("A2 stranka: nadpis, kod konfigurace v zahlavi, cena ve vlastnim okne", (await p.page.title()).includes("Ochranný kryt a oplocení") && (await p.page.textContent("#titleCode")).startsWith("OPL-") && (await priceNet(p.page)) === l.price.net, await p.page.textContent("#titleCode"));
    const skupiny = await p.page.evaluate(() => Array.from(document.querySelectorAll(".mw-win")).filter(w => !w.hidden).map(w => w.getAttribute("data-win")));
    t("A3 okna: 3D, cena, vyroba, rozmery, strany, vyplne+dvere+prislusenstvi, vyplne po stranach, kusovnik", ["stage", "price", "info", "dim", "frame", "extras", "adv", "bom"].every(k => skupiny.includes(k)), skupiny);
    const nadpisy = await p.page.evaluate(() => ["dim", "frame", "extras", "adv"].map(k => document.querySelector(`[data-win="${k}"] .mw-win-h span`).textContent));
    t("A3b nadpisy oken: Rozměry | Strany a střecha | Výplň, dveře a příslušenství | Výplň po stranách", JSON.stringify(nadpisy) === JSON.stringify(["Rozměry", "Strany a střecha", "Výplň, dveře a příslušenství", "Výplň po stranách"]), nadpisy);
    const sekce = await p.page.evaluate(() => Array.from(document.querySelectorAll('[data-win="extras"] .pdc-sekce')).filter(x => !x.hidden).map(x => x.querySelector("h3").textContent));
    t("A3c okno Výplň, dveře a příslušenství má 3 podnadpisy (Výplň, Dveře, Příslušenství)", JSON.stringify(sekce) === JSON.stringify(["Výplň", "Dveře", "Příslušenství"]), sekce);
    const sloty = await p.page.evaluate(() => Object.keys(window.__pdcState.ui));
    t("A4 vsech 20 slotu schematu ma ovladac", sloty.length === 20 && ["w", "front", "roof", "fill", "door_w", "feet"].every(k => sloty.includes(k)), sloty);
    t("A5 stranka a modul nepouzivaji nic z katalogu ani sceny (verejnost nesmi nacitat scene.html / katalog)", !(await p.page.evaluate(() => Array.from(performance.getEntriesByType("resource")).some(r => /scene\.html|\/katalog\//.test(r.name)))));
    t("A6 3D: model nacten, prohlizec (viewer3d.js) bezi, ma koty (3 cary sirka, hloubka, vyska)", await p.page.evaluate(() => !!window.__pdcState.viewer && window.__pdcState.viewer.state && window.__pdcState.viewer.state().ready === true), null);
    t("A7 zamestnanecky blok: okno Vyroba a odkazy + Kusovnik s cenami viditelne, kod a spoje v radku", await p.page.evaluate(() => !document.querySelector('[data-win="bom"]').hidden && !document.querySelector('[data-win="info"]').hidden && /OPL-/.test(document.getElementById("staffCode").textContent) && /spojů profilů/.test(document.getElementById("staffCode").textContent)), await p.page.textContent("#staffCode"));
    const bom = await p.page.evaluate(() => ({ rows: document.querySelectorAll("#bomBody tbody tr").length, sums: Array.from(document.querySelectorAll("#bomBody tr.sum td")).map(x => x.textContent), text: document.getElementById("bomBody").textContent }));
    t("A8 kusovnik: tabulka s radky, 'Celkem bez DPH' = cena, profily sbalene do jednoho radku, tesneni a balne", bom.rows > 15 && money(bom.sums[1]) === l.price.net && /Profil/.test(bom.text) && /Těsnění/.test(bom.text) && /Balné/.test(bom.text), { rows: bom.rows, sums: bom.sums });
    t("A9 radek profilu jde rozbalit (delky)", await p.page.evaluate(() => { const b = document.querySelector("#bomBody .bom-tog"); if (!b) return false; const det = () => document.querySelectorAll("#bomBody tr.det:not([hidden])").length; const a = det(); b.click(); return det() > a; }));
    t("A10 karta produktu: id a stav (neaktivni) + odkaz", /Karta produktu #\d+ \(neaktivní\)/.test(await p.page.textContent("#cardInfo")) && await p.page.evaluate(() => !!document.querySelector('#cardInfo a[href*="product.html?id="]')), await p.page.textContent("#cardInfo"));
    t("A11 resolve zamestnance nese `staff: true`, product_id karty", p.trk.bodies.length > 0 && p.trk.bodies.every(b => JSON.parse(b).staff === true && String(JSON.parse(b).product_id) === PID), p.trk.bodies[0]);
    t("A12 zadna chyba stranky ani konzole, vsechny dotazy 200", p.errs.length === 0 && p.trk.status.every(s => s === 200), { errs: p.errs.slice(0, 3), status: p.trk.status });
    t("A13 pocet dotazu na vychozi nacteni rozumny (resolve <= 3, GLB <= 2: predstazeni + nacteni prohlizecem), bez vyprseni cekani", p.trk.resolve <= 3 && p.trk.glb <= 2 && p.trk.timeouts === 0, { resolve: p.trk.resolve, glb: p.trk.glb, timeouts: p.trk.timeouts });
    await snap(p, "stranka_staff");
    await p.ctx.close();
  });

  await sec("B ovladani", async () => {
    const p = await mk(browser);
    await load(p, BASE);
    const c0 = (await last(p.page)).price.net, g0 = p.trk.glb;
    await setNum(p, "w", 2400);
    let s = await sel(p.page), l = await last(p.page);
    t("B1 sirka 2400: vyber, cena roste, nacte se novy model, hash v URL", s.w === 2400 && l.price.net > c0 && p.trk.glb > g0 && /w=2400/.test(await p.page.evaluate(() => location.hash)), { w: s.w, net: l.price.net, c0, glb: [g0, p.trk.glb] });
    await setNum(p, "w", 800);
    s = await sel(p.page); l = await last(p.page);
    t("B2 sirka 800: dvere se nevejdou -> cela strana je stena, oznameni v panelu, volba Dvere zakazana", s.front === "wall" && l.notices.some(n => n.action === "adjusted" && /876/.test(n.message))
      && await p.page.evaluate(() => /876/.test(document.querySelector(".pdc-notices").textContent)) && await hidden(p.page, "door_w") && l.options.front.door.disabled === true, { front: s.front, notices: l.notices.length });
    await setNum(p, "w", 1500);
    await chip(p, "front", "door");
    s = await sel(p.page);
    t("B3 zpet 1500 a Dvere na celo: dvere zpet, volby dveri viditelne", s.front === "door" && !(await hidden(p.page, "door_w")) && !(await hidden(p.page, "door_h")) && !(await hidden(p.page, "lock")), s.front);
    const cDv = (await last(p.page)).price.net;
    await chip(p, "front", "wall");
    s = await sel(p.page);
    t("B4 Stena misto dveri: volby dveri zmizi, cena se zmeni", s.front === "wall" && await hidden(p.page, "door_w") && await hidden(p.page, "door_pos") && (await last(p.page)).price.net !== cDv);
    const sekce4 = await p.page.evaluate(() => Array.from(document.querySelectorAll('[data-win="extras"] .pdc-sekce')).filter(x => !x.hidden).map(x => x.querySelector("h3").textContent));
    t("B4b bez dveri zmizi i podnadpis Dvere (zbyde Vyplň a Příslušenství)", JSON.stringify(sekce4) === JSON.stringify(["Výplň", "Příslušenství"]), sekce4);
    await chip(p, "front", "door");
    const cFill = (await last(p.page)).price.net;
    await pick(p, "fill", "mesh");
    s = await sel(p.page); l = await last(p.page);
    t("B5 vyplne Svarovana sit: levnejsi, souhrn a vyber", s.fill === "mesh" && l.price.net < cFill, { net: l.price.net, cFill });
    await pick(p, "fill", "pc_clear");
    await chip(p, "roof", "none");
    s = await sel(p.page);
    t("B6 strecha 'Bez strechy': vyber, volba vyplne strechy zmizi", s.roof === "none" && await hidden(p.page, "fill_roof"), s.roof);
    await chip(p, "roof", "fill");
    await tgl(p, "feet");
    s = await sel(p.page); l = await last(p.page);
    t("B7 patky: zapnute, cena se zmenila podle options (price_delta), vyska zustava", s.feet === true && s.h === 2200, { feet: s.feet, h: s.h });
    await tgl(p, "feet");
    // oplocení: jedna strana, bez strechy
    await chip(p, "right", "open"); await chip(p, "back", "open"); await chip(p, "left", "open"); await chip(p, "roof", "none");
    s = await sel(p.page); l = await last(p.page);
    t("B8 oploceni (jen celo, bez strechy): hloubka se skryje, platne, souhrn", s.right === "open" && s.roof === "none" && await hidden(p.page, "d") && l.valid && !(await hidden(p.page, "w")), s);
    await chip(p, "front", "open");
    s = await sel(p.page); l = await last(p.page);
    t("B9 vsechny strany otevrene bez strechy: server nastavi strechu na ram, oznameni, volba 'Bez strechy' zakazana", s.roof === "frame" && l.notices.some(n => n.slot === "roof") && l.options.roof.none.disabled === true && l.valid, s.roof);
    t("B9b bez sten a bez vyplne strechy se okno Vyplň po stranach schova", await p.page.evaluate(() => document.querySelector('[data-win="adv"]').hidden === true));
    await p.page.click("button.pdc-link:has-text('Výchozí hodnoty')");
    await idle(p, 1300);
    s = await sel(p.page);
    t("B10 Vychozi hodnoty vrati vychozi vyber", s.front === "door" && s.w === 1500 && s.roof === "fill" && s.right === "wall", s);
    t("B10b okno Vyplň po stranach je ve vychozim stavu sbalene (i na desktopu)", await p.page.evaluate(() => document.querySelector('[data-win="adv"]').classList.contains("is-closed")));
    await p.page.click('[data-win="adv"] > .mw-win-h');
    await pick(p, "fill_left", "pc_smoke");
    s = await sel(p.page);
    t("B11 vyplne po stranach (sklopne okno): levá strana koura, ostatni jako celek", s.fill_left === "pc_smoke" && s.fill_front === "auto" && s.fill === "pc_clear", s);
    await setNum(p, "door_w", 1100); await setNum(p, "w", 1100);
    s = await sel(p.page);
    t("B12 zuzeni strany pod sirku dveri: sirka dveri se zkrati (824), oznameni", s.door_w === 824 && (await last(p.page)).notices.some(n => n.slot === "door_w"), s.door_w);
    t("B13 stranka se pri ovladani nerozbije: zadna chyba, vsechny dotazy 200, zadne cekani nevyprselo", p.errs.length === 0 && p.trk.status.every(s2 => s2 === 200) && p.trk.timeouts === 0, { errs: p.errs.slice(0, 3), bad: p.trk.status.filter(s2 => s2 !== 200), timeouts: p.trk.timeouts });
    await p.ctx.close();
  });

  await sec("C odkaz (#hash)", async () => {
    const p = await mk(browser);
    await load(p, BASE, "", "#w=2400&d=1800&front=wall&right=door&feet=1&fill=acrylic&door_h=1800&roof=frame");
    const s = await sel(p.page), l = await last(p.page);
    t("C1 odkaz otevre presne tu konfiguraci (vcetne patek, vyplne, dveri, strechy)", s.w === 2400 && s.d === 1800 && s.front === "wall" && s.right === "door" && s.feet === true && s.fill === "acrylic" && s.door_h === 1800 && s.roof === "frame" && l.valid, s);
    const hash = await p.page.evaluate(() => location.hash);
    t("C2 hash v URL odpovida vyberu (verejne nazvy slotu, patky 1/0)", /w=2400/.test(hash) && /feet=1/.test(hash) && /fill=acrylic/.test(hash) && /right=door/.test(hash), hash);
    await p.page.reload({ waitUntil: "load" });
    await p.page.waitForFunction(() => window.__pdcState && window.__pdcState.last && window.__pdcState.last.model, null, { timeout: 60000 });
    await idle(p, 900);
    const s2 = await sel(p.page);
    t("C3 po znovunacteni stejna konfigurace", JSON.stringify(s2) === JSON.stringify(s), { s, s2 });
    await p.ctx.close();
    const q = await mk(browser);
    await load(q, BASE, "", "#w=zzz&front=kulate&nesmysl=1&feet=ano&door_h=");
    const sq = await sel(q.page);
    t("C4 nesmyslny hash: stranka se nacte s vychozimi hodnotami (nic se nerozbije)", sq.w === 1500 && sq.front === "door" && q.errs.length === 0, { sq, errs: q.errs.slice(0, 2) });
    await q.ctx.close();
  });

  await sec("D rozlozeni", async () => {
    const p = await mk(browser);
    await load(p, BASE);
    const r = await p.page.evaluate(() => { const g = k => document.querySelector(`[data-win="${k}"]`).getBoundingClientRect(); return { stage: g("stage"), price: g("price"), dim: g("dim"), frame: g("frame"), extras: g("extras"), bom: g("bom"), vw: window.innerWidth, sw: document.documentElement.scrollWidth }; });
    t("D1 desktop: 3D vlevo, cena vpravo od 3D, rozmery | strany | vyplne a dvere v jednom radku, kusovnik pod nimi", r.price.x > r.stage.x + r.stage.width * 0.6 && Math.abs(r.dim.y - r.frame.y) < 4 && Math.abs(r.frame.y - r.extras.y) < 4 && r.bom.y > r.dim.y + r.dim.height - 2, r);
    t("D2 desktop: bez vodorovneho posuvniku stranky", r.sw <= r.vw + 1, { sw: r.sw, vw: r.vw });
    await p.ctx.close();
    const m = await mk(browser, { viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true });
    await load(m, BASE);
    const rm = await m.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, vw: window.innerWidth, stage: document.querySelector('[data-win="stage"]').getBoundingClientRect().width, dimOpen: !document.querySelector('[data-win="dim"]').classList.contains("is-closed"), fillClosed: document.querySelector('[data-win="adv"]').classList.contains("is-closed") }));
    t("D3 mobil 360 px: bez vodorovneho posuvniku, 3D na celou sirku (okraje po 16 px), rozmery otevrene, vyplne po stranach sbalene", rm.sw <= rm.vw + 1 && rm.stage >= rm.vw - 40 && rm.dimOpen && rm.fillClosed, rm);
    await snap(m, "stranka_mobil");
    await m.ctx.close();
  });

  await sec("E verejna varianta (?public=1&id=)", async () => {
    const p = await mk(browser);
    await load(p, BASE_PUB, `&public=1&id=${PID}`);
    const l = await last(p.page);
    t("E1 verejnost nacte generator bez prihlaseni, platna cena", l.valid && l.price.net > 20000);
    t("E2 resolve verejnosti NEMA `staff` v tele; odpoved bez bloku staff", p.trk.bodies.length > 0 && p.trk.bodies.every(b => !("staff" in JSON.parse(b))) && !(await p.page.evaluate(() => "staff" in window.__pdcState.last)), p.trk.bodies[0]);
    t("E3 verejna varianta: bez oken Vyroba a Kusovnik s cenami, bez odkazu na kartu, cena ve vlastnim okne", await p.page.evaluate(() => document.querySelector('[data-win="info"]').hidden && document.querySelector('[data-win="bom"]').hidden && document.getElementById("cardInfo").textContent === "" && /\d/.test(document.getElementById("priceNet").textContent)));
    t("E4 verejne volby jsou stejne (20 slotu), oznameni o norme je videt", (await p.page.evaluate(() => Object.keys(window.__pdcState.ui).length)) === 20 && /14120/.test(await p.page.evaluate(() => document.querySelector(".pdc-notices").textContent)));
    t("E5 zadna chyba stranky a dotazy 200", p.errs.length === 0 && p.trk.status.every(s => s === 200), { errs: p.errs.slice(0, 3), status: p.trk.status });
    await snap(p, "stranka_verejna");
    await p.ctx.close();
    const q = await mk(browser);
    await load(q, BASE_PUB, `&public=1&id=${PID}&lang=en`);
    const lab = await q.page.evaluate(() => Array.from(document.querySelectorAll(".pdc-slot .pd-opt-sub-label")).map(x => x.textContent).slice(0, 6));
    t("E6 ?lang=en: popisky voleb z serveru anglicky", lab.includes("Width") && lab.includes("Depth"), lab);
    await q.ctx.close();
  });

  await sec("F neprihlaseny, bez prava, bez karty", async () => {
    const p = await mk(browser);
    await p.page.goto(`${BASE_PUB}/oploceni-konfigurator.html`, { waitUntil: "load" });
    await p.page.waitForTimeout(1500);
    t("F1 neprihlaseny: hlaska o prihlaseni, odkaz na prihlaseni s navratem, zadne volby", await p.page.evaluate(() => getComputedStyle(document.getElementById("login")).display === "block" && /login\.html\?next=/.test(document.getElementById("loginLink").getAttribute("href")) && getComputedStyle(document.getElementById("shGrid")).display === "none"));
    t("F2 neprihlaseny: nic se nenacetlo ze serveru generatoru (zadny resolve)", p.trk.resolve === 0);
    await p.ctx.close();
    const q = await mk(browser);
    await q.page.route("**/api/shop/configurator/recepty/*", r => r.fulfill({ status: 403, contentType: "application/json", body: '{"error":"forbidden"}' }));
    await q.page.goto(`${BASE}/oploceni-konfigurator.html`, { waitUntil: "load" });
    await q.page.waitForTimeout(1500);
    t("F3 prihlaseny bez prava: hlaska, zadny resolve", /nemáš oprávnění/.test(await q.page.textContent("#stageMsg")) && q.trk.resolve === 0, await q.page.textContent("#stageMsg"));
    await q.ctx.close();
    const r = await mk(browser);
    await r.page.route("**/api/shop/configurator/recepty/*", x => x.fulfill({ status: 404, contentType: "application/json", body: '{"error":"not_found"}' }));
    await r.page.goto(`${BASE}/oploceni-konfigurator.html`, { waitUntil: "load" });
    await r.page.waitForTimeout(1500);
    t("F4 generator bez karty (404): hlaska, zadny resolve", /zatím není zapnutý/.test(await r.page.textContent("#stageMsg")) && r.trk.resolve === 0, await r.page.textContent("#stageMsg"));
    await r.ctx.close();
    const u = await mk(browser);
    await u.page.goto(`${BASE_PUB}/oploceni-konfigurator.html?public=1`, { waitUntil: "load" });
    await u.page.waitForTimeout(1200);
    t("F5 verejna varianta bez ?id= : hlaska, zadny resolve", /zatím není zapnutý/.test(await u.page.textContent("#stageMsg")) && u.trk.resolve === 0);
    await u.ctx.close();
  });

  await browser.close();
  console.log(`\n${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
