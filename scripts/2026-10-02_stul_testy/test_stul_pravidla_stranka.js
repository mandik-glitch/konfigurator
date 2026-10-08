// Test okna PRAVIDLA STOLU na strance Generator stolu (bot8, 2026-10-05; Robert: "pravidla stolu konkretni hodnoty chci mit nastavitelne pro jednotlive systemy zvlast, 30/35/40, kazdemu zadam
// individualne; tyto pravidla vidi jen admin"). SKUTECNA stranka (js/stul-host.js) pres most _most_stul.py; routa /api/stul/pravidla se ve VSECH pripadech nahrazuje atrapou v prohlizeci
// (page.route) - PRODUKCNI app_settings se nikdy nectou ani nepisou, zadny PUT nedojde na server. Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_pravidla_stranka.js 4934
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };

const VYCHOZI = { hloubka_stredni_profil: 900, vzpery_od_ramene: 500, cena_vyrez: 0, sirka_stredni_noha: 1500, cena_navlek_200: 370, cena_navlek_400: 550 };
const ROZSAH = { hloubka_stredni_profil: [400, 1600], vzpery_od_ramene: [200, 1500], cena_vyrez: [0, 100000], sirka_stredni_noha: [500, 3000], cena_navlek_200: [0, 100000], cena_navlek_400: [0, 100000] };
const po = (o) => Object.assign({}, VYCHOZI, o || {});
const NOVE = () => ({ pravidla: po(), system: 30, navlek_systemy: [35], vychozi: VYCHOZI, rozsah: ROZSAH,
  systemy: { "30": po({ cena_vyrez: 2800 }), "35": po({ sirka_stredni_noha: 1800, cena_vyrez: 3000, cena_navlek_200: 400 }), "40": po({ hloubka_stredni_profil: 700 }) } });
const STARE = () => ({ pravidla: po({ cena_vyrez: 2800 }), vychozi: VYCHOZI, rozsah: ROZSAH });
const SSE_V = { sirka_stredni_noha: 2000, cena_noha_sse_400: 0, cena_noha_sse_1100: 0 };                        // 2026-10-05: system 41 = stul SSE (vlastni vychozi hodnoty, ceny nohy, bez podper / vzper / vyrezu)
const NOVE4 = () => { const d = NOVE(); d.sse_systemy = [41]; d.systemy["41"] = po({ sirka_stredni_noha: 2000, cena_noha_sse_400: 1000, cena_noha_sse_1100: 1700 }); d.vychozi_systemu = { "30": VYCHOZI, "35": VYCHOZI, "40": VYCHOZI, "41": Object.assign({}, VYCHOZI, SSE_V) };
  d.vychozi = Object.assign({}, VYCHOZI, { cena_noha_sse_400: 0, cena_noha_sse_1100: 0 }); Object.keys(d.systemy).forEach(k => { d.systemy[k] = Object.assign({ cena_noha_sse_400: 0, cena_noha_sse_1100: 0 }, d.systemy[k]); }); return d; };

async function otevri(browser, { api, me, status }) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [], puts = [], gets = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/status of 40[13]/.test(m.text())) errs.push("console: " + m.text()); });
  await page.route("**/api/stul/pravidla", async (route) => {
    const rq = route.request();
    if (rq.method() === "PUT") { puts.push(JSON.parse(rq.postData() || "{}")); return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api) }); }
    gets.push(rq.url());
    if (status && status !== 200) return route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ error: "x" }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(api) });
  });
  if (me) await page.route("**/api/auth/me", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: me }) }));
  await page.addInitScript(() => { Object.defineProperty(window, "__reloads", { value: [], writable: true }); });
  await page.goto(`${BASE}/stul-konfigurator.html?debug=1`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await page.waitForTimeout(1500);
  const okno = await page.evaluate(() => { const b = document.querySelector(".mw-win-rules"); return !!b && !b.hidden && b.offsetParent !== null; });
  if (okno) { await page.locator(".mw-win-rules .mw-win-fold").click(); await page.waitForTimeout(300); }          // okno Pravidla stolu je po nacteni sklopene
  return { ctx, page, errs, puts, gets, okno };
}
const val = (page, id) => page.evaluate(i => { const e = document.getElementById(i); return e ? { v: e.value, shown: e.style.display !== "none" && e.offsetParent !== null } : null; }, id);
const boxVisible = page => page.evaluate(() => { const b = document.getElementById("pravUloz"); return !!b && b.offsetParent !== null; });
const pressed = page => page.evaluate(() => [30, 35, 40].filter(n => document.getElementById("pravSys" + n).getAttribute("aria-pressed") === "true"));

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## A pravidla po systemech (nove API)");
    const A = await otevri(browser, { api: NOVE() });
    t("A1 admin vidi okno Pravidla stolu (po rozbaleni jsou videt pole)", A.okno && await boxVisible(A.page));
    t("A2 prepinac systemu 30 / 35 / 40 je videt, predvolen je system stranky (30)", JSON.stringify(await pressed(A.page)) === "[30]" && await A.page.evaluate(() => [30, 35, 40].every(n => document.getElementById("pravSys" + n).offsetParent !== null)), await pressed(A.page));
    let h = await val(A.page, "pravHloubka"), c = await val(A.page, "pravVyrez"), s = await val(A.page, "pravStredni"), n2 = await val(A.page, "pravNavlek200");
    t("A3 system 30: hloubka 900, sirka 1500, cena vyrezu 2800; ceny navleku nejsou (jen system 35)", h.v === "900" && s.v === "1500" && c.v === "2800" && n2 && !n2.shown, { h, s, c, n2 });
    await A.page.click("#pravSys35"); await A.page.waitForTimeout(200);
    h = await val(A.page, "pravHloubka"); c = await val(A.page, "pravVyrez"); s = await val(A.page, "pravStredni"); n2 = await val(A.page, "pravNavlek200");
    t("A4 system 35: sirka 1800, cena vyrezu 3000, cena navleku 200 mm = 400 a ukazuje se", JSON.stringify(await pressed(A.page)) === "[35]" && s.v === "1800" && c.v === "3000" && n2.v === "400" && n2.shown && h.v === "900", { s, c, n2, h });
    await A.page.click("#pravSys40"); await A.page.waitForTimeout(200);
    h = await val(A.page, "pravHloubka"); n2 = await val(A.page, "pravNavlek200");
    t("A5 system 40: hloubka 700, ceny navleku skryte", h.v === "700" && !n2.shown && JSON.stringify(await pressed(A.page)) === "[40]", { h, n2 });
    const vych = await A.page.textContent("#pravVychozi");
    t("A6 tlacitko Vychozi nese system a nema ceny navleku u systemu 40", /systém 40/.test(vych) && !/370/.test(vych), vych);
    // uprava a ulozeni systemu 35
    await A.page.click("#pravSys35"); await A.page.waitForTimeout(150);
    await A.page.fill("#pravHloubka", "750");
    await A.page.click("#pravSys40"); await A.page.waitForTimeout(200);
    const msg = await A.page.textContent("#pravStav");
    t("A7 neulozena zmena systemu 35 zabrani prepnuti na 40 (vypise hlasku, zustane 35)", /neuložené změny systému 35/.test(msg) && JSON.stringify(await pressed(A.page)) === "[35]", { msg, p: await pressed(A.page) });
    await A.page.click("#pravUloz"); await A.page.waitForTimeout(400);
    const put = A.puts[0];
    t("A8 Ulozit poslal JEN system 35 a jeho sest hodnot", A.puts.length === 1 && put.system === 35 && put.pravidla && put.pravidla.hloubka_stredni_profil === 750 && put.pravidla.sirka_stredni_noha === 1800 && put.pravidla.cena_vyrez === 3000 && put.pravidla.cena_navlek_200 === 400 && Object.keys(put.pravidla).length === 6, put);
    t("A9 po ulozeni se stranka prepocita (znovu nacte)", await A.page.waitForNavigation({ timeout: 8000, waitUntil: "load" }).then(() => true).catch(() => false));
    t("A10 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));
    await A.ctx.close();

    console.log("\n## B Vychozi pro system a neplatne hodnoty");
    const B = await otevri(browser, { api: NOVE() });
    await B.page.click("#pravSys40"); await B.page.waitForTimeout(200);
    await B.page.click("#pravVychozi"); await B.page.waitForTimeout(400);
    const put2 = B.puts[0];
    t("B1 Vychozi pro system 40 posila prazdne hodnoty JEN 40 a bez klicu navleku", B.puts.length === 1 && put2.system === 40 && Object.keys(put2.pravidla).sort().join() === "cena_vyrez,hloubka_stredni_profil,sirka_stredni_noha,vzpery_od_ramene" && Object.values(put2.pravidla).every(v => v === ""), put2);
    await B.ctx.close();
    const B2 = await otevri(browser, { api: NOVE() });
    await B2.page.fill("#pravHloubka", "abc"); await B2.page.click("#pravUloz"); await B2.page.waitForTimeout(300);
    t("B2 neplatna hodnota se neodesle (hlaska u pole, zadny PUT)", B2.puts.length === 0 && /hloubku v mm/.test(await B2.page.textContent("#pravStav")), await B2.page.textContent("#pravStav"));
    await B2.ctx.close();

    console.log("\n## C starsi API (jedna sada pro vsechny systemy): formular jako dosud, plochy PUT");
    const C = await otevri(browser, { api: STARE() });
    t("C1 starsi API: okno je, prepinac systemu neni, hodnoty jsou", await boxVisible(C.page) && !(await C.page.evaluate(() => document.getElementById("pravSys30").offsetParent !== null)) && (await val(C.page, "pravVyrez")).v === "2800", await pressed(C.page));
    await C.page.fill("#pravHloubka", "800"); await C.page.click("#pravUloz"); await C.page.waitForTimeout(400);
    t("C2 starsi API: PUT je plochy slovnik bez klice system", C.puts.length === 1 && C.puts[0].system === undefined && C.puts[0].hloubka_stredni_profil === 800 && C.puts[0].pravidla === undefined, C.puts[0]);
    await C.ctx.close();

    console.log("\n## F system 41 = stul SSE (4. tlacitko, vlastni pole a vychozi hodnoty)");
    const F = await otevri(browser, { api: NOVE4() });
    const vis = id => F.page.evaluate(i => { const e = document.getElementById(i); return !!e && e.offsetParent !== null && e.style.display !== "none"; }, id);
    t("F1 ctvrte tlacitko SSE je videt a prepinac ma 4 tlacitka", await vis("pravSys41") && await vis("pravSys30") && (await F.page.textContent("#pravSys41")) === "SSE", await F.page.textContent("#pravSys41"));
    await F.page.click("#pravSys41"); await F.page.waitForTimeout(200);
    const pole41 = {}; for (const id of ["pravHloubka", "pravVzpery", "pravVyrez", "pravStredni", "pravNavlek200", "pravNavlek400", "pravNoha400", "pravNoha1100"]) pole41[id] = await vis(id);
    t("F2 system 41 ukazuje JEN sirku pro stredni nohu a dve ceny nohy SSE (zadna hloubka podper, vzpery, vyrez ani navlek)", pole41.pravStredni && pole41.pravNoha400 && pole41.pravNoha1100 && !pole41.pravHloubka && !pole41.pravVzpery && !pole41.pravVyrez && !pole41.pravNavlek200 && !pole41.pravNavlek400, pole41);
    t("F3 hodnoty systemu 41: stredni noha 2000, cena nohy 1000 / 1700", (await val(F.page, "pravStredni")).v === "2000" && (await val(F.page, "pravNoha400")).v === "1000" && (await val(F.page, "pravNoha1100")).v === "1700", [await val(F.page, "pravStredni"), await val(F.page, "pravNoha400")]);
    t("F4 tlacitko Vychozi nese SSE (ne 'system 41') a jeho vychozi hodnoty (2000, 0, 0)", /Výchozí pro SSE \(2000, 0, 0\)/.test(await F.page.textContent("#pravVychozi")) && !/syst[eé]m\s*41/i.test(await F.page.textContent("#pravVychozi")), await F.page.textContent("#pravVychozi"));
    await F.page.click("#pravSys30"); await F.page.waitForTimeout(200);
    const pole30 = {}; for (const id of ["pravHloubka", "pravVzpery", "pravVyrez", "pravStredni", "pravNoha400", "pravNoha1100"]) pole30[id] = await vis(id);
    t("F5 system 30: dosavadni pole, zadna pole nohy SSE", pole30.pravHloubka && pole30.pravVzpery && pole30.pravVyrez && pole30.pravStredni && !pole30.pravNoha400 && !pole30.pravNoha1100, pole30);
    t("F6 vychozi hodnoty systemu 30 beze zmeny (900, 1500, 500, 0)", /systém 30 \(900, 1500, 500, 0\)/.test(await F.page.textContent("#pravVychozi")), await F.page.textContent("#pravVychozi"));
    await F.page.click("#pravSys41"); await F.page.waitForTimeout(150);
    await F.page.fill("#pravNoha400", "1200"); await F.page.fill("#pravNoha1100", "2100");
    await F.page.click("#pravUloz"); await F.page.waitForTimeout(400);
    const pf = F.puts[0];
    t("F7 Ulozit poslal JEN system 41 a jeho tri hodnoty", F.puts.length === 1 && pf.system === 41 && Object.keys(pf.pravidla).sort().join() === "cena_noha_sse_1100,cena_noha_sse_400,sirka_stredni_noha" && pf.pravidla.cena_noha_sse_400 === 1200 && pf.pravidla.cena_noha_sse_1100 === 2100 && pf.pravidla.sirka_stredni_noha === 2000, pf);
    await F.ctx.close();
    const F2 = await otevri(browser, { api: NOVE4() });
    await F2.page.click("#pravSys41"); await F2.page.waitForTimeout(150);
    await F2.page.fill("#pravNoha400", "abc"); await F2.page.click("#pravUloz"); await F2.page.waitForTimeout(300);
    t("F8 neplatna cena nohy SSE se neodesle (hlaska, zadny PUT)", F2.puts.length === 0 && /cenu nohy SSE/.test(await F2.page.textContent("#pravStav")), await F2.page.textContent("#pravStav"));
    await F2.page.click("#pravSys30"); await F2.page.waitForTimeout(150);
    t("F8b neulozena zmena v systemu 41 zabrani prepnuti na 30", /neuložené změny systému 41/.test(await F2.page.textContent("#pravStav")), await F2.page.textContent("#pravStav"));
    await F2.ctx.close();
    const F3 = await otevri(browser, { api: NOVE4() });
    await F3.page.click("#pravVychozi"); await F3.page.waitForTimeout(300);                         // vychozi stranka je system 30
    t("F9 Vychozi pro system 30 neposila klice nohy SSE", F3.puts.length === 1 && F3.puts[0].system === 30 && !("cena_noha_sse_400" in F3.puts[0].pravidla) && Object.keys(F3.puts[0].pravidla).length === 4, F3.puts[0]);
    await F3.ctx.close();
    const G4 = await otevri(browser, { api: NOVE() });                                 // API bez systemu SSE (zatim nenasazene): ctvrte tlacitko se neukazuje
    t("F10 starsi po-systemove API bez systemu 41: tlacitko SSE se neukazuje", !(await G4.page.evaluate(() => { const e = document.getElementById("pravSys41"); return !!e && e.offsetParent !== null && e.style.display !== "none"; })), "");
    await G4.ctx.close();

    console.log("\n## D pravidla vidi jen admin");
    const D = await otevri(browser, { api: NOVE(), me: { id: 7, email: "remeslnik@example.test", role: "remeslnik", name: "R", permissions: { nastaveni: true } } });
    t("D1 uzivatel s pravem nastaveni, ale ne admin: okno pravidel se NEUKAZUJE a nic se nenacita", !D.okno && !(await boxVisible(D.page)) && D.gets.length === 0, { okno: D.okno, gets: D.gets.length });
    await D.ctx.close();
    const E = await otevri(browser, { api: NOVE(), status: 403 });
    t("E1 server vrati 403: pole zustanou skryta, bez chyby JS", (await val(E.page, "pravHloubka")).shown === false && E.errs.length === 0, E.errs.slice(0, 3));
    await E.ctx.close();
  } catch (e) { t("test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 700)); }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
