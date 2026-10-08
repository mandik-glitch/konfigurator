// Test RUCNICH SVITIDEL LED na strance Generator stolu 01 (bot8, 2026-10-08; Robert: "svitidla v generatoru se pridavaji automaticky za sebe podle delky, ale chceme aby se pridavali jen rucne
// a mohli se posouvat podel profilu"). SKUTECNA stranka + SKUTECNY modul voleb + viewer + modul ovladani ve 3D nad SKUTECNYM kodem stolu pres most _most_stul.py (prihlaseny admin, produkt 4934).
// Hlida: vychozi stul (1280) ma jedno svitidlo a slider poctu je zamceny (vejde se jen jedno), siroky stul (3000) s LED 600 ma slider poctu 1-4 a vychozi je JEDNO svitidlo (drive se pridavala sama),
// pocet 3 -> tri svitidla + tri slidery polohy (ctvrty skryty), poloha 2. svitidla, odkaz s poctem a polohou (#ledcount=..&ledpos2=..), uchyt svitidla ve 3D (tazeni mysi: stitek ukazuje mezery od
// okraje a od sousedniho svitidla, po pusteni se poloha ulozi a model prekresli), polozky nabidky ve 3D (Pridat svitidlo / Odebrat toto svitidlo: ostatni zustavaji na svych mistech, hodnoty nejsou
// orezane starymi mezemi), mobil 360 px bez vodorovneho posuvu, zadne chyby JS.
// Spusteni z KANDIDATNIHO korene, DB pres systemd-run (viewer potrebuje internet kvuli three.js z jsdelivr):
//   cd $SP/led_rucne/cand2 && systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=$PWD \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-08_led_rucne/test_led_rucne_stranka.js 4934
// (po nasazeni je tentyz test platny i nad zivym stromem: --working-directory=/opt/konfigurator; SNIMKY=/adresar ulozi screenshoty)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, SNIMKY = process.env.SNIMKY || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const selOf = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const lastSel = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.last.selection)));
const nacten = page => page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { timeout: 120000 });
const klidne = async page => { await page.waitForFunction(() => { const S = window.__pdcState; return S && !S.pending && !S.commitPending && S.last; }, null, { timeout: 60000 }).catch(() => {}); await page.waitForTimeout(1500); await nacten(page); };
const slot = (page, id) => page.evaluate(i => {
  const n = document.querySelector(`[data-slot=${i}]`);
  if (!n) return null;
  const num = n.querySelector(".pdc-num");
  return { hidden: n.hidden || n.offsetParent === null, value: num ? num.value : null, text: n.textContent.replace(/\s+/g, " ").trim().slice(0, 120) };
}, id);
const opts = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.last.options)));
const svitidla = page => page.evaluate(() => { const o = window.__pdcState.last.vodici && window.__pdcState.last.vodici.osvetleni; return o ? o.lights.length : 0; });
const nastavCislo = async (page, id, v) => { await page.fill(`[data-slot=${id}] .pdc-num`, String(v)); await page.keyboard.press("Enter"); await klidne(page); };

async function otevri(browser, hash, viewport) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 1400, height: 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
  await page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await nacten(page);
  await page.waitForTimeout(900);
  return { ctx, page, errs };
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## A) vychozi stul a siroky stul: svitidla uz se nepridavaji sama");
    const A = await otevri(browser);
    let s = await selOf(A.page);
    t("A1 vychozi vyber: ledcount 1, polohy null", s.ledcount === 1 && [1, 2, 3, 4].every(k => s["ledpos" + k] === null), s);
    t("A2 vychozi stul 1280: jedno svitidlo; slider poctu je zamceny (vejde se jen jedno) a neukazuje se", (await svitidla(A.page)) === 1 && ((await slot(A.page, "ledcount")) || { hidden: true }).hidden, await slot(A.page, "ledcount"));
    const p1 = await slot(A.page, "ledpos1");
    t("A3 slider Poloha svitidla LED 1 je videt a je v rezimu 'automaticky' (-31,7)", !!p1 && !p1.hidden && /Poloha svítidla LED 1/.test(p1.text) && /automaticky/i.test(p1.text), p1);
    t("A4 sloty ledpos2-4 se neukazuji (svitidla nejsou)", (await Promise.all([2, 3, 4].map(k => slot(A.page, "ledpos" + k)))).every(x => !x || x.hidden), await Promise.all([2, 3, 4].map(k => slot(A.page, "ledpos" + k))));
    await nastavCislo(A.page, "w", 3000);
    s = await selOf(A.page);
    t("A5 siroky stul 3000 s LED 1200: VYCHOZI JE 1 SVITIDLO (drive 2 automaticky); slider poctu 1-2", s.w === 3000 && (await svitidla(A.page)) === 1 && (await opts(A.page)).ledcount.max === 2 && !((await slot(A.page, "ledcount")) || { hidden: true }).hidden, [s.w, await svitidla(A.page), (await opts(A.page)).ledcount]);
    await A.page.selectOption("[data-slot=ledlen] select", "600");
    await klidne(A.page);
    t("A6 LED 600 na stole 3000: jedno svitidlo, slider poctu 1-4", (await svitidla(A.page)) === 1 && (await opts(A.page)).ledcount.max === 4, [await svitidla(A.page), (await opts(A.page)).ledcount]);
    await nastavCislo(A.page, "ledcount", 3);
    s = await selOf(A.page);
    t("A7 pocet 3: tri svitidla, selection.ledcount 3, tri slidery polohy (4. skryty)", (await svitidla(A.page)) === 3 && s.ledcount === 3 && !(await slot(A.page, "ledpos3")).hidden && ((await slot(A.page, "ledpos4")) || { hidden: true }).hidden, [await svitidla(A.page), s.ledcount]);
    const hash = await A.page.evaluate(() => location.hash);
    t("A8 pocet je v odkazu (#...ledcount=3)", /ledcount=3/.test(hash), hash);
    const o3 = await opts(A.page);
    t("A9 options.ledpos1-3 maji celou mez stredu (stejnou) a auto, ledpos4 hidden", [1, 2, 3].every(k => o3["ledpos" + k].auto === true && o3["ledpos" + k].min === o3.ledpos1.min && o3["ledpos" + k].max === o3.ledpos1.max) && o3.ledpos4.hidden === true, o3);
    if (SNIMKY) { require("fs").mkdirSync(SNIMKY, { recursive: true }); await A.page.screenshot({ path: SNIMKY + "/stranka_led_3x600.png" }); }
    await nastavCislo(A.page, "ledpos2", 150);
    s = await selOf(A.page);
    const o4 = await opts(A.page);
    t("A10 poloha 2. svitidla 150 mm: ulozena, jina svitidla zustanou 'automaticky' nebo se odsunou, platna konfigurace", s.ledpos2 === 150 && (await lastSel(A.page)).ledpos2 === 150 && o4.ledpos2.auto === false && (await A.page.evaluate(() => window.__pdcState.last.valid)), [s.ledpos2, o4.ledpos2]);
    t("A11 poloha je v odkazu (#...ledpos2=150)", /ledpos2=150/.test(await A.page.evaluate(() => location.hash)), await A.page.evaluate(() => location.hash));
    t("A12 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));
    await A.ctx.close();

    console.log("\n## B) uchyt svitidla ve 3D: tazeni mysi");
    const B = await otevri(browser, "#w=3000&ledlen=600&ledcount=2");
    t("B1 odkaz #w=3000&ledlen=600&ledcount=2: dve svitidla", (await svitidla(B.page)) === 2 && (await selOf(B.page)).ledcount === 2, [await svitidla(B.page), await selOf(B.page)]);
    await B.page.waitForFunction(() => window.__pdcState.ov && Object.keys(window.__pdcState.ov.debug().handles).some(k => /^ledpos/.test(k)), null, { timeout: 60000 }).catch(() => {});
    const uchyty = await B.page.evaluate(() => Object.keys(window.__pdcState.ov.debug().handles));
    t("B2 ve 3D jsou uchyty ledpos1 a ledpos2", uchyty.includes("ledpos1") && uchyty.includes("ledpos2"), uchyty);
    const pred = await opts(B.page);
    const bx = await B.page.locator("#v3do_ledpos2").boundingBox();
    t("B3 uchyt ledpos2 je na strance videt", !!bx && bx.width > 4 && bx.height > 4, bx);
    if (bx) {
      await B.page.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await B.page.mouse.down();
      for (let i = 1; i <= 10; i++) await B.page.mouse.move(bx.x + bx.width / 2 + 8 * i, bx.y + bx.height / 2);
      await B.page.waitForTimeout(700);
      const tip = await B.page.evaluate(() => [...document.querySelectorAll(".pdc-ov .v3do-lbl, .pdc-ov .v3do-tip")].filter(l => getComputedStyle(l).display !== "none").map(l => l.textContent.replace(/\s+/g, " ")).join(" / "));
      t("B4 behem tazeni stitek ukazuje mezery od okraje stolu a od sousedniho svitidla", /od (pravého|levého) okraje stolu/.test(tip) && /od levého svítidla/.test(tip), tip);
      await B.page.mouse.up();
      await klidne(B.page);
      const po = await opts(B.page), sel = await selOf(B.page);
      t("B5 po pusteni se poloha 2. svitidla zmenila (smerem doprava), je v mezich a ulozena v selection", sel.ledpos2 !== null && po.ledpos2.value !== pred.ledpos2.value && po.ledpos2.value <= po.ledpos2.max && po.ledpos2.value >= po.ledpos1.value + 640, { pred: pred.ledpos2.value, po: po.ledpos2.value, sel: sel.ledpos2 });
      t("B6 1. svitidlo se netaženim nepohlo", Math.abs(po.ledpos1.value - pred.ledpos1.value) < 0.3, [pred.ledpos1.value, po.ledpos1.value]);
    }
    t("B7 bez chyb JS", B.errs.length === 0, B.errs.slice(0, 3));
    await B.ctx.close();

    console.log("\n## C) nabidka ve 3D: Pridat svitidlo / Odebrat toto svitidlo");
    const C = await otevri(browser, "#w=3000&ledlen=600");
    const menuPatch = (page, cast, text) => page.evaluate(([c, tx]) => { const o = window.__pdcState.last.vodici.ovladani; const ca = o.casti.find(x => x.id === c); const m = ca && ca.menu.find(x => x.text === tx); return m ? { zakazano: m.zakazano, nastav: m.nastav } : null; }, [cast, text]);
    const pr = await menuPatch(C.page, "led", "Přidat svítidlo LED");
    t("C1 nabidka 'Pridat svitidlo LED' u jednoho svitidla: povolena, patch nese pocet 2 a vyslovne polohy obou svitidel", !!pr && !pr.zakazano && pr.nastav.ledcount === 2 && pr.nastav.ledpos1 !== null && pr.nastav.ledpos2 !== null, pr);
    await C.page.evaluate(p => window.__pdcApplyPatch(p, { source: "menu" }), pr.nastav);
    await klidne(C.page);
    const sC = await selOf(C.page), oC = await opts(C.page);
    t("C2 po pridani jsou dve svitidla, 1. zustalo na miste (-31,7) a 2. je tesne vedle", (await svitidla(C.page)) === 2 && sC.ledcount === 2 && Math.abs(oC.ledpos1.value + 31.7) < 0.3 && Math.abs((oC.ledpos2.value - oC.ledpos1.value) - 647) < 0.5, [await svitidla(C.page), oC.ledpos1.value, oC.ledpos2.value]);
    const pr3 = await menuPatch(C.page, "led", "Přidat svítidlo LED");
    await C.page.evaluate(p => window.__pdcApplyPatch(p, { source: "menu" }), pr3.nastav);
    await klidne(C.page);
    t("C3 dalsi pridani: tri svitidla", (await svitidla(C.page)) === 3 && (await selOf(C.page)).ledcount === 3, [await svitidla(C.page)]);
    const pozice3 = await opts(C.page);
    const od = await menuPatch(C.page, "ledlamp1", "Odebrat toto svítidlo");
    t("C4 nabidka 'Odebrat toto svitidlo' 1. svitidla: patch nese pocet 2 a polohy zbylych dvou (ne orezane starymi mezemi)", !!od && od.nastav.ledcount === 2 && Math.abs(od.nastav.ledpos1 - pozice3.ledpos2.value) < 0.3 && Math.abs(od.nastav.ledpos2 - pozice3.ledpos3.value) < 0.3, od);
    await C.page.evaluate(p => window.__pdcApplyPatch(p, { source: "menu" }), od.nastav);
    await klidne(C.page);
    const oD = await opts(C.page);
    t("C5 po odebrani 1. svitidla zustala dalsi dve presne tam, kde byla (druhe a treti)", (await svitidla(C.page)) === 2 && Math.abs(oD.ledpos1.value - pozice3.ledpos2.value) < 0.3 && Math.abs(oD.ledpos2.value - pozice3.ledpos3.value) < 0.3, [oD.ledpos1.value, oD.ledpos2.value, pozice3.ledpos2.value, pozice3.ledpos3.value]);
    const vr = await menuPatch(C.page, "ledlamp1", "Vrátit svítidlo na výchozí místo");
    t("C6 nabidka 'Vratit svitidlo na vychozi misto' nastavuje null", !!vr && JSON.stringify(vr.nastav) === JSON.stringify({ ledpos1: null }), vr);
    t("C7 bez chyb JS", C.errs.length === 0, C.errs.slice(0, 3));
    await C.ctx.close();

    console.log("\n## D) mobil 360 px");
    const D = await otevri(browser, "#w=3000&ledlen=600&ledcount=3", { width: 360, height: 780 });
    const sirkaStr = await D.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    t("D1 na mobilu 360 px je stranka bez vodorovneho posuvu", sirkaStr.sw <= sirkaStr.cw + 1, sirkaStr);
    t("D2 sloty poctu a polohy jsou na mobilu v dokumentu (3 svitidla)", !!(await slot(D.page, "ledcount")) && !!(await slot(D.page, "ledpos3")) && (await svitidla(D.page)) === 3, [await slot(D.page, "ledcount"), await svitidla(D.page)]);
    t("D3 bez chyb JS", D.errs.length === 0, D.errs.slice(0, 3));
    await D.ctx.close();
  } catch (e) { t("test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 900)); }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
