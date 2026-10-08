// Test CHOVANI NAVLEKU NOHOU (jekl 40x40x2, system 35) v SKUTECNEM prohlizeci na strance Generator stolu 03 (bot10, 2026-10-05): spolecny modul voleb vykresli sloty `sleeve` a `sleevelen`,
// vychozi stav 35 = navlek 300 mm bez koleček, kolecka zakazana s duvodem, vypnuti navleku -> kolecka lze zapnout, delka 400 mm zvysi cenu, nizky stul orizne delku a nakonec navlek odebere
// (oznameni), prepnuti systemu 35 -> 30 -> 35 zahodi / vrati navlek bez chyb. Nad skutecnym kodem stolu pres most scripts/2026-10-02_stul_testy/_most_stul.py (fiktivni karty, nic se nezapisuje do DB):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_system35/test_navlek_stranka.js 4934
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, SHOT = process.env.SHOT || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
const GLB_RE = /\/api\/shop\/configurator\/glb\//, RES_RE = /\/api\/shop\/configurator\/resolve/;
async function mk(browser, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w || 1400, height: h || 900 }, locale: "cs-CZ" });
  await ctx.addInitScript(() => { window.__pdcDebug = true; });
  const page = await ctx.newPage(); const errs = [];
  const trk = { pending: 0, last: Date.now() };
  page.on("pageerror", e => errs.push(e.message));
  page.on("console", m => { if (m.type() === "error") errs.push("console: " + m.text()); });
  page.on("request", r => { const u = r.url(); if (RES_RE.test(u) || GLB_RE.test(u)) { trk.pending++; trk.last = Date.now(); } });
  const done = r => { if (RES_RE.test(r.url()) || GLB_RE.test(r.url())) { trk.pending--; trk.last = Date.now(); } };
  page.on("requestfinished", done); page.on("requestfailed", done);
  return { ctx, page, trk, errs };
}
const idle = async (p, quiet) => {
  const q = quiet || 1200; await p.page.waitForTimeout(q);
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) { if (p.trk.pending <= 0 && Date.now() - p.trk.last > q) return; await p.page.waitForTimeout(100); }
};
async function load(p, pagePath, hash) {
  await p.page.goto(`${BASE}${pagePath}?debug=1${hash || ""}`, { waitUntil: "load" });
  await p.page.waitForSelector("#stage .v3d-root canvas", { timeout: 90000 });
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.hash; }, null, { polling: 200, timeout: 60000 });
  await idle(p, 900);
}
const last = p => p.page.evaluate(() => { const L = window.__pdcState.last; return { sel: L.selection, opt: L.options, notices: L.notices, errors: L.errors, price: L.price && L.price.net, valid: L.valid }; });
const slotInfo = (p, id) => p.page.evaluate(id => {
  const root = document.querySelector(`[data-slot="${id}"]`);
  if (!root) return null;
  const cb = root.querySelector('input[type="checkbox"]'), rng = root.querySelector('input[type="range"]'), num = root.querySelector('input[type="number"]');
  const vis = !!(root.offsetWidth || root.offsetHeight || root.getClientRects().length);
  return { visible: vis && getComputedStyle(root).display !== "none", checked: cb ? cb.checked : null, rng: rng ? { value: rng.value, min: rng.min, max: rng.max, disabled: rng.disabled } : null, num: num ? num.value : null, text: root.innerText.trim().slice(0, 240) };
}, id);
const toggle = async (p, id) => { await p.page.evaluate(id => { const cb = document.querySelector(`[data-slot="${id}"] input[type="checkbox"]`); cb.click(); }, id); await idle(p, 1200); };
const setNum = async (p, id, v) => {
  await p.page.evaluate(({ id, v }) => { const n = document.querySelector(`[data-slot="${id}"] input[type="number"]`); n.value = String(v); n.dispatchEvent(new Event("input", { bubbles: true })); n.dispatchEvent(new Event("change", { bubbles: true })); }, { id, v });
  await idle(p, 1500);
};

(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const p = await mk(browser);
  console.log("\n## 1) vychozi stav generatoru 03: navlek 300 mm, bez koleček");
  await load(p, "/stul-konfigurator-35.html", "");
  let L = await last(p);
  t("1a vychozi vyber 35: navlek zapnuty, 300 mm, kolecka a patky vypnute", L.sel.sleeve === true && L.sel.sleevelen === 300 && L.sel.wheels === false && L.sel.feet === false, L.sel);
  let sl = await slotInfo(p, "sleeve"), ll = await slotInfo(p, "sleevelen"), wh = await slotInfo(p, "wheels");
  t("1b prepinac 'Navlek nohou' je videt a zapnuty, posuvnik delky videt s hodnotou 300", sl && sl.visible && sl.checked === true && ll && ll.visible && ll.num === "300" && ll.rng.min === "200" && ll.rng.max === "400", [sl, ll]);
  t("1c popisky slotu (cs)", /Návlek nohou/i.test(sl.text) && /Délka návleku/i.test(ll.text), [sl.text, ll.text]);
  t("1d kolecka jsou vypnuta a zapnout je nejde: options.wheels zakazano s duvodem", wh && wh.checked === false && L.opt.wheels.on.disabled === true && /Návlek/.test(L.opt.wheels.on.reason), L.opt.wheels);
  const cena300 = L.price;
  const bom = await p.page.evaluate(() => document.getElementById("bomBody").innerText);
  t("1e kusovnik pro zamestnance ma radek navleku 4 x 460 = 1840 a hmotnost/odkazy nejsou rozbite", /Návlek nohy – jekl 40×40×2, délka 300 mm/.test(bom) && /1 840/.test(bom.replace(/ /g, " ")), bom.slice(0, 600));
  t("1f zadne chyby ve strance", p.errs.length === 0, p.errs.slice(0, 3));
  if (SHOT) await p.page.screenshot({ path: SHOT + "_1.png", fullPage: true });

  console.log("\n## 2) vypnuti navleku -> kolecka, delka 400, zpet");
  await toggle(p, "sleeve");
  L = await last(p); wh = await slotInfo(p, "wheels"); ll = await slotInfo(p, "sleevelen");
  t("2a navlek vypnuty: kolecka stale vypnuta (nevraci se sama), zapnout je jde, posuvnik delky zamcen / skryty", L.sel.sleeve === false && L.sel.wheels === false && L.opt.wheels.on.disabled === false && (!ll || !ll.visible || (ll.rng && (ll.rng.disabled || ll.rng.min === ll.rng.max))), [L.sel, L.opt.wheels, ll]);
  await toggle(p, "wheels");
  L = await last(p);
  t("2b kolecka zapnuta: navlek vypnuty, cena se zmenila", L.sel.wheels === true && L.sel.sleeve === false && L.price !== cena300, [L.sel, L.price, cena300]);
  await toggle(p, "sleeve");
  L = await last(p); wh = await slotInfo(p, "wheels");
  t("2c navlek znovu zapnuty: kolecka se vytlacila (vypnuta a zakazana), navlek 300", L.sel.sleeve === true && L.sel.wheels === false && L.sel.sleevelen === 300 && L.opt.wheels.on.disabled === true && wh.checked === false, [L.sel, wh]);
  const cenaZpet = L.price;
  t("2d stejny vyber = stejna cena jako na zacatku", cenaZpet === cena300, [cenaZpet, cena300]);
  await setNum(p, "sleevelen", 400);
  L = await last(p);
  // presne jednotkove ceny (370 / 460 / 550 / 415) a linearitu hlida test_shop_navlek.py; tady jen: cena roste, o mene nez 4 x 90 Kc navic (profily nohou jsou kratsi, balne v %), a o vic nez nic
  t("2e delka 400 mm: vyber 400, cena je vyssi nez u 300 mm (rozdil mezi 100 a 450 Kc: 4 x 90 Kc minus kratsi profily nohou)", L.sel.sleevelen === 400 && L.price - cena300 > 100 && L.price - cena300 < 450, [L.sel.sleevelen, L.price - cena300]);
  const bom4 = await p.page.evaluate(() => document.getElementById("bomBody").innerText.replace(/ /g, " "));
  t("2f kusovnik: navlek 400 mm po 550 Kc = 2200", /délka 400 mm/.test(bom4) && /2 200/.test(bom4), bom4.slice(0, 400));

  console.log("\n## 3) nizky stul: orez delky, odebrani navleku");
  await setNum(p, "h", 500);
  L = await last(p); ll = await slotInfo(p, "sleevelen");
  t("3a vyska 500: delka se orizla na 370, posuvnik ma max 370, v oznamenich je info", L.sel.sleeve === true && L.sel.sleevelen === 370 && L.opt.sleevelen.max === 370 && L.notices.some(n => n.slot === "sleevelen" && /370/.test(n.message)) && ll.rng.max === "370", [L.sel.sleevelen, L.opt.sleevelen, L.notices.map(n => n.message)]);
  await setNum(p, "h", 300);
  L = await last(p); sl = await slotInfo(p, "sleeve");
  t("3b vyska 300: navlek se nevejde a byl odebran s oznamenim, volba je zakazana s duvodem", L.sel.sleeve === false && L.valid && L.notices.some(n => n.slot === "sleeve" && n.action === "removed") && L.opt.sleeve.on.disabled === true, [L.sel.sleeve, L.valid, L.notices.map(n => n.slot + ":" + n.action), L.opt.sleeve.on]);
  t("3c zadne chyby ve strance po zmenach", p.errs.length === 0, p.errs.slice(0, 3));
  await setNum(p, "h", 840);
  L = await last(p);
  t("3d vyska zpet 840: navlek zustal vypnuty (sam se nevraci), jde zapnout", L.sel.sleeve === false && L.opt.sleeve.on.disabled === false, [L.sel.sleeve, L.opt.sleeve.on]);

  console.log("\n## 4) prepnuti systemu 35 -> 30 -> 35");
  await p.page.goto("about:blank");
  await load(p, "/stul-konfigurator-35.html", "#w=1800&d=900&h=1000&shelf=2&sleevelen=250");
  L = await last(p);
  t("4a odkaz s #sleevelen=250: navlek 250 mm, vyber (w 1800, h 1000, 2 police) se nacetl", L.sel.sleeve === true && L.sel.sleevelen === 250 && L.sel.w === 1800 && L.sel.h === 1000 && L.sel.shelf === 2, L.sel);
  const href30 = await p.page.evaluate(() => document.querySelector('#sysSwitch a[data-system="30"]').getAttribute("href"));
  await p.page.click('#sysSwitch a[data-system="30"]');
  await p.page.waitForFunction(() => window.StulHost && window.StulHost.system === 30, null, { timeout: 30000 }).catch(() => {});
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && S.last.selection.w === 1800; }, null, { timeout: 90000, polling: 200 });
  await idle(p, 1500);
  L = await last(p); const s30 = await slotInfo(p, "sleeve");
  t("4b system 30: zadny slot navleku, vyber se zachoval, zadne klice navleku v odpovedi, bez chyb", s30 === null && !("sleeve" in L.sel) && !("sleevelen" in L.sel) && L.sel.w === 1800 && L.sel.h === 1000 && L.valid && p.errs.length === 0, [s30, L.sel, p.errs.slice(0, 2)]);
  await p.page.click('#sysSwitch a[data-system="35"]');
  await p.page.waitForFunction(() => window.StulHost && window.StulHost.system === 35, null, { timeout: 30000 }).catch(() => {});
  await p.page.waitForFunction(() => { const S = window.__pdcState; return S && S.last && S.last.selection && "sleeve" in S.last.selection; }, null, { timeout: 90000, polling: 200 });
  await idle(p, 1500);
  L = await last(p);
  t("4c zpet na system 35: vychozi koncovka = navlek (300 mm; klic navleku se z 30 nepreneslo), vyber zachovan, kolecka z 30 vytlacena", L.sel.sleeve === true && L.sel.sleevelen === 300 && L.sel.wheels === false && L.sel.w === 1800 && L.sel.h === 1000 && L.valid, L.sel);
  t("4d zadne chyby ve strance po prepnuti", p.errs.length === 0, p.errs.slice(0, 3));
  if (SHOT) await p.page.screenshot({ path: SHOT + "_4.png", fullPage: true });

  console.log("\n## 5) mobil 360 px: sloty navleku se vejdou, bez vodorovneho posuvniku");
  const pm = await mk(browser, 360, 780);
  await load(pm, "/stul-konfigurator-35.html", "");
  const m = await pm.page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: innerWidth, sl: !!document.querySelector('[data-slot="sleeve"]') }));
  t("5a mobil 360 px: bez vodorovneho posuvniku a slot navleku existuje", m.sw <= m.iw + 1 && m.sl, m);
  t("5b mobil: zadne chyby", pm.errs.length === 0, pm.errs.slice(0, 3));
  await browser.close();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})();
