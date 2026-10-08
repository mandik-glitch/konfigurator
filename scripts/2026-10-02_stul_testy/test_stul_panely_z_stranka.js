// Test VODOROVNEHO POSUNU PANELU na strance Generator stolu 01 (bot8, 2026-10-05; Robert: "panely chceme pohyblive, pokud maji mezeru mezi nohama"; kóty ukazuji mezery od noh).
// SKUTECNA stranka + SKUTECNY modul voleb + viewer nad SKUTECNYM kodem stolu pres most _most_stul.py (prihlaseny admin, produkt 4934). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-02_stul_testy/test_stul_panely_z_stranka.js 4934
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const cisla = a => a.map(x => Number(x.replace(/[^\d]/g, "")));
const popisky = page => page.evaluate(() => [...document.querySelectorAll(".v3d-dim")].filter(e => getComputedStyle(e).display !== "none" && e.offsetParent !== null).map(e => e.textContent.trim()));
const selOf = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const stav = page => page.evaluate(() => { const s = window.__pdcState.viewer.state(); return { dims: s.dims, mode: s.mode }; });

async function otevri(browser, hash) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading && document.querySelectorAll(".v3d-dim").length > 0 && S.ov && Object.keys(S.ov.debug().handles).length > 0; }, null, { polling: 300, timeout: 90000 });
  await page.waitForTimeout(800);
  return { ctx, page, errs };
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## P1 slot a posun z panelu");
    const A = await otevri(browser);
    const slot = await A.page.evaluate(() => { const n = document.querySelector("[data-slot=panelside]"); if (!n) return null; const num = n.querySelector(".pdc-num"); const rng = n.querySelector("input[type=range]"); return { hidden: n.offsetParent === null, val: num && num.value, min: rng && rng.min, max: rng && rng.max, step: rng && rng.step, label: (n.querySelector("label, .pdc-label") || {}).textContent }; });
    t("P1 slot Panely do stran je ve formulari (pod panely), vychozi 0, rozsah z options (+-14 mm), krok 1", !!slot && slot.val === "0" && Number(slot.max) === 14 && Number(slot.min) === -14 && Number(slot.step) === 1, slot);
    let lab = await popisky(A.page);
    t("P2 vychozi koty: mezery panelu od noh 15 a 15", cisla(lab).filter(v => v === 15).length === 2, lab);
    // zmena posuvniku
    await A.page.fill("[data-slot=panelside] .pdc-num", "10"); await A.page.keyboard.press("Enter");
    await A.page.waitForFunction(() => [...document.querySelectorAll(".v3d-dim")].some(e => /^25 mm$/.test(e.textContent.trim())), null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(900);
    lab = await popisky(A.page);
    const sel = await selOf(A.page);
    t("P3 posun 10 mm: vyber panelside = 10 a koty ukazuji mezery 25 mm vlevo a 5 mm vpravo", sel.panelside === 10 && cisla(lab).includes(25) && cisla(lab).includes(5) && !cisla(lab).includes(15), { sel: sel.panelside, lab });
    const hash = await A.page.evaluate(() => location.hash);
    t("P4 hodnota je v odkazu (#...panelside=10)", /panelside=10/.test(hash), hash);
    // mimo meze se orizne
    await A.page.fill("[data-slot=panelside] .pdc-num", "500"); await A.page.keyboard.press("Enter");
    await A.page.waitForFunction(() => [...document.querySelectorAll(".v3d-dim")].some(e => /^29 mm$/.test(e.textContent.trim())), null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(600);
    lab = await popisky(A.page);
    t("P5 hodnota 500 se orizne na 14 mm (mezera od prave nohy 1 mm)", (await selOf(A.page)).panelside === 14 && cisla(lab).includes(1) && cisla(lab).includes(29), lab);
    t("P6 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));

    console.log("\n## P2 uchyt ve 3D");
    await A.page.fill("[data-slot=panelside] .pdc-num", "0"); await A.page.keyboard.press("Enter");
    await A.page.waitForFunction(() => window.__pdcState.sel.panelside === 0, null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(1200);
    const hasH = await A.page.evaluate(() => Object.keys(window.__pdcState.ov.debug().handles));
    t("U1 ve 3D je uchyt panelside (Panely do stran)", hasH.includes("panelside"), hasH);
    const b = await A.page.locator("#v3do_panelside").boundingBox();
    await A.page.mouse.move(b.x + b.width / 2, b.y + b.height / 2); await A.page.mouse.down();
    for (let i = 1; i <= 8; i++) await A.page.mouse.move(b.x + b.width / 2 + 6 * i, b.y + b.height / 2);
    await A.page.waitForTimeout(700);
    const st1 = await stav(A.page), lab1 = await popisky(A.page);
    const tip = await A.page.evaluate(() => [...document.querySelectorAll(".pdc-ov .v3do-lbl, .pdc-ov .v3do-tip")].filter(l => getComputedStyle(l).display !== "none").map(l => l.textContent.replace(/\s+/g, " ")).join(" / "));
    t("U2 behem tazeni jsou koty vypnute a stitek ukazuje mezery od obou noh (mm)", st1.dims === 0 && lab1.length === 0 && /od levé nohy/.test(tip) && /od pravé nohy/.test(tip), { st1, tip });
    await A.page.mouse.up();
    await A.page.waitForFunction(() => window.__pdcState.viewer.state().dims === 1 && document.querySelectorAll(".v3d-dim").length > 0, null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(1200);
    const sel2 = await selOf(A.page), lab2 = await popisky(A.page);
    t("U3 po pusteni je posun panelu nenulovy, v mezich +-14 a koty ukazuji soucet mezer 30 mm (" + sel2.panelside + ")", sel2.panelside > 0 && sel2.panelside <= 14 && cisla(lab2).includes(15 + sel2.panelside) && cisla(lab2).includes(15 - sel2.panelside), { sel2: sel2.panelside, lab2 });
    // nabidka: vratit doprostred (patch jako z nabidky ve 3D)
    await A.page.evaluate(() => window.__pdcApplyPatch({ panelside: 0 }));
    await A.page.waitForFunction(() => window.__pdcState.sel.panelside === 0, null, { timeout: 60000 }).catch(() => {});
    await A.page.waitForTimeout(1500);
    lab = await popisky(A.page);
    t("U4 Panely vratit doprostred: posun 0, mezery zase 15 + 15", (await selOf(A.page)).panelside === 0 && cisla(lab).filter(v => v === 15).length === 2, lab);
    t("U5 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));
    await A.ctx.close();

    console.log("\n## P3 odkaz s posunem a siroky stul se strednimi nohami");
    const B = await otevri(browser, "#panelside=-9");
    lab = await popisky(B.page);
    t("L1 odkaz #panelside=-9: mezery 6 mm vlevo a 24 mm vpravo", cisla(lab).includes(6) && cisla(lab).includes(24), lab);
    await B.ctx.close();
    const C = await otevri(browser, "#w=2600&panelcount=2&midsupport=legs&panelside=10");
    lab = await popisky(C.page);
    const sC = await selOf(C.page);
    t("L2 dva panely u stredni nohy: ctyri mezery (32,5 +- 10 -> 43 / 23 mm, 2x)", sC.panelside === 10 && cisla(lab).filter(v => v === 43 || v === 23 || v === 42 || v === 22).length >= 4, { panelside: sC.panelside, lab });
    t("L3 bez chyb JS", C.errs.length === 0 && B.errs.length === 0, C.errs.concat(B.errs).slice(0, 3));
    await C.ctx.close();
  } catch (e) { t("test spadl na vyjimce", false, String((e && e.stack) || e).slice(0, 700)); }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
