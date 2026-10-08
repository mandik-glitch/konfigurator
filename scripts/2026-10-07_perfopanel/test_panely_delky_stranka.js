// Test VOLBY DELKY PANELU na strance Generator stolu 01 (bot8, 2026-10-07; Robert: dalsi velikosti perforovanych panelu 1481 / 1671 / 1975 mm vedle 1190).
// SKUTECNA stranka + SKUTECNY modul voleb + viewer nad SKUTECNYM kodem stolu pres most _most_stul.py (prihlaseny admin, produkt 4934). Spusteni (DB pres systemd-run):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-07_perfopanel/test_panely_delky_stranka.js 4934
// (kandidat: pustit z kandidatniho stromu, viz hlavicka run_all.sh; SNIMKY=/adresar ulozi screenshoty)
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE;
const SNIMKY = process.env.SNIMKY || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const selOf = page => page.evaluate(() => JSON.parse(JSON.stringify(window.__pdcState.sel)));
const nacten = page => page.waitForFunction(() => { const S = window.__pdcState; return S && S.viewer && S.viewer.state && S.viewer.state().ready && !S.viewer.state().loading; }, null, { timeout: 120000 });
const slotInfo = page => page.evaluate(() => {
  const n = document.querySelector("[data-slot=panellen]");
  if (!n) return null;
  const s = n.querySelector("select");
  return { hidden: n.offsetParent === null, value: s && s.value, options: s ? [...s.options].map(o => ({ v: o.value, text: o.textContent })) : [], label: (n.querySelector("label") || {}).textContent };
});
// zmena sirky: pocka na ODPOVED serveru (resolve) s novou sirkou (pri zatizeni stroje trva i desitky sekund), pak jeste na dokonceny model
const sirka = async (page, w) => {
  await page.fill("[data-slot=w] .pdc-num", String(w)); await page.keyboard.press("Enter");
  await page.waitForFunction(v => window.__pdcState.last && window.__pdcState.last.selection && window.__pdcState.last.selection.w === v && window.__pdcState.sel.w === v, w, { timeout: 180000 });
  await page.waitForTimeout(800);
};

async function otevri(browser, hash, viewport) {
  const ctx = await browser.newContext({ viewport: viewport || { width: 1400, height: 900 }, locale: "cs-CZ" });
  const page = await ctx.newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  await page.goto(`${BASE}/stul-konfigurator.html?debug=1${hash || ""}`, { waitUntil: "load" });
  await page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await nacten(page);
  await page.waitForTimeout(900);
  return { ctx, page, errs };
}

(async () => {
  const browser = await chromium.launch({ args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  try {
    console.log("\n## D1 slot Delka panelu a zakazane delky u vychoziho stolu (1280 mm)");
    const A = await otevri(browser);
    let si = await slotInfo(A.page);
    t("D1 slot Delka panelu je ve formulari, select s 4 volbami a hodnotou 1190", !!si && !si.hidden && si.value === "1190" && si.options.map(o => o.v).join() === "1190,1481,1671,1975" && /Délka panelu/.test(si.label || ""), si);
    t("D2 u 1280 mm jsou 1481 / 1671 / 1975 oznacene jako nedostupne, 1190 ne", !!si && si.options.filter(o => /nedostupné/.test(o.text)).map(o => o.v).join() === "1481,1671,1975", si && si.options);
    await A.page.selectOption("[data-slot=panellen] select", "1975");
    await A.page.waitForTimeout(700);
    si = await slotInfo(A.page);
    const upoz = await A.page.evaluate(() => document.body.innerText);
    t("D3 vyber nedostupne delky (1975) se vrati na 1190 a ukaze duvod s nejmensi sirkou 2037 mm", si.value === "1190" && (await selOf(A.page)).panellen === "1190" && /2037/.test(upoz), { value: si.value, najde: /2037/.test(upoz) });

    console.log("\n## D2 siroky stul: vsechny delky, vyber 1975");
    await sirka(A.page, 2100);
    si = await slotInfo(A.page);
    t("D4 u 2100 mm neni zadna delka nedostupna", si.options.every(o => !/nedostupné/.test(o.text)), si.options);
    const cena0 = await A.page.evaluate(() => (window.__pdcState.last.price || {}).net);
    await A.page.selectOption("[data-slot=panellen] select", "1975");
    await A.page.waitForFunction(() => window.__pdcState.sel.panellen === "1975" && window.__pdcState.last.selection.panellen === "1975", null, { timeout: 180000 }).catch(() => {});
    await nacten(A.page);
    await A.page.waitForTimeout(1500);
    const st = await A.page.evaluate(() => ({ sel: window.__pdcState.sel.panellen, net: (window.__pdcState.last.price || {}).net, valid: window.__pdcState.last.valid, hash: location.hash, errors: window.__pdcState.last.errors.length }));
    t("D5 po vyberu 1975: vyber 1975, platna konfigurace, cena vyssi, delka v odkazu (#...panellen=1975)", st.sel === "1975" && st.valid && st.errors === 0 && st.net > cena0 && /panellen=1975/.test(st.hash), { st, cena0 });
    if (SNIMKY) { require("fs").mkdirSync(SNIMKY, { recursive: true }); await A.page.screenshot({ path: SNIMKY + "/stranka_1975.png" }); }
    const dims = await A.page.evaluate(() => [...document.querySelectorAll(".v3d-dim")].filter(e => getComputedStyle(e).display !== "none" && e.offsetParent !== null).map(e => e.textContent.trim()));
    t("D6 ve 3D jsou koty mezer panelu od noh (po 1975 mm panelu zbyva ~32 mm z kazde strany)", dims.some(x => /^3[0-4] ?mm$/.test(x)), dims);
    const lenInfo = await A.page.evaluate(() => { const w = window.__pdcState.last.vodici && window.__pdcState.last.vodici.ovladani; return w ? w.casti.filter(c => c.id === "panels").map(c => c.menu.map(m => m.text)) : null; });
    t("D7 3D menu panelu nabizi ostatni delky (Zvolit panel 1190 / 1481 / 1671 mm)", !!lenInfo && lenInfo[0].filter(x => /^Zvolit panel/.test(x)).join("|") === "Zvolit panel 1190 mm|Zvolit panel 1481 mm|Zvolit panel 1671 mm", lenInfo);

    console.log("\n## D3 zuzeni stolu: delka se snizi, panel zustane");
    await sirka(A.page, 1600);
    await A.page.waitForFunction(() => window.__pdcState.sel.panellen === "1481" && window.__pdcState.last.selection.panellen === "1481", null, { timeout: 180000 }).catch(() => {});
    await A.page.waitForTimeout(1200);
    const st2 = await A.page.evaluate(() => ({ sel: window.__pdcState.sel, notices: (window.__pdcState.last.notices || []).filter(n => n.slot === "panellen").map(n => n.message), valid: window.__pdcState.last.valid }));
    t("D8 stul zuzen na 1600: delka snizena na 1481, panely zustaly zapnute, oznameni o snizeni", st2.sel.panellen === "1481" && st2.sel.panels === true && st2.valid && st2.notices.length === 1 && /1481/.test(st2.notices[0]), st2);
    const texty = await A.page.evaluate(() => document.body.innerText);
    t("D9 oznameni o snizeni delky je videt na strance", /Délka panelů snížena na 1481 mm/.test(texty), texty.slice(0, 200));
    t("D10 bez chyb JS", A.errs.length === 0, A.errs.slice(0, 3));
    await A.ctx.close();

    console.log("\n## D4 odkaz s delkou a mobil");
    const B = await otevri(browser, "#w=2100&panellen=1671");
    const sb = await selOf(B.page);
    const sib = await slotInfo(B.page);
    t("D11 odkaz #w=2100&panellen=1671 nacte stul s panelem 1671", sb.panellen === "1671" && sb.w === 2100 && sib.value === "1671", { sb: sb.panellen, w: sb.w, sib: sib && sib.value });
    const panelPrvek = await B.page.evaluate(() => { const l = window.__pdcState.last; return { hash: l.hash, selection: l.selection.panellen, errs: l.errors.length }; });
    t("D12 server vratil vyber 1671 bez chyb", panelPrvek.selection === "1671" && panelPrvek.errs === 0, panelPrvek);
    await B.ctx.close();
    const M = await otevri(browser, "#w=2100", { width: 360, height: 800 });
    const mob = await slotInfo(M.page);
    const pretece = await M.page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    t("D13 na uzkem okne (360 px) je slot Delka panelu ve formulari (skupina Prislusenstvi je na mobilu sbalena) a stranka se neposouva do strany", !!mob && mob.options.length === 4 && !pretece, { mob, pretece });
    t("D14 bez chyb JS (mobil)", M.errs.length === 0, M.errs.slice(0, 3));
    await M.ctx.close();
  } finally {
    await browser.close();
  }
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error("TEST SPADL:", e.message); process.exit(2); });
