// Pocitadlo luxu na DOTYKOVEM zarizeni (mobil; bot10, 2026-10-06, panel v3 od Johna): tlacitko "Cinnosti pri tomto osvetleni" v souhrnu (.lux-open-panel) musi jit KLEPNOUT i kdyz je 3D zamcene
// (.pdc-lock, na dotykovych zarizenich je stage po nacteni zamcena) a kdyz pres souhrn lezou uchyty ovladani (.pdc-ov > .v3do-layer > .v3do-h). Objev na ostre domene: klepnuti doprostred tlacitka
// trefilo zamek (390 px) nebo uchyt (320-375 px) a panel se neotevrel. SKUTECNA stranka embed (zakaznicky generator) + skutecny viewer pres most _most_stul.py (fiktivni karty, nic se nezapisuje):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PID40=9877 --setenv=PID35=9878 --working-directory=/opt/konfigurator \
//     api/venv/bin/python3 scripts/2026-10-02_stul_testy/_most_stul.py scripts/2026-10-05_luxy/test_luxy_touch.js 4934
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "4934", SHOT = process.env.SHOT || "";
let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)) : ""}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  for (const [w, h] of [[320, 640], [360, 640], [390, 844]]) {
    console.log(`\n## dotyk ${w} x ${h}`);
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, hasTouch: true, isMobile: true, locale: "cs-CZ" });
    const page = await ctx.newPage(); const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !/favicon|Failed to load resource/.test(m.text())) errs.push("console: " + m.text()); });
    await page.goto(`${BASE}/embed/stul.html?debug=1&p=${PID}`, { waitUntil: "load" });
    await page.waitForSelector(".stl-lux-btn", { timeout: 90000 });
    await page.waitForTimeout(2500);
    t(`${w}: 3D je po nacteni zamcene (dotykove zarizeni) - zamek ve strance`, await page.evaluate(() => !!document.querySelector(".pdc-lock") && !document.querySelector(".pdc-stage").classList.contains("pdc-unlocked")));
    await page.click(".stl-lux-btn");
    await page.waitForSelector(".lux-hud .lux-main-number", { timeout: 120000 });
    await page.waitForTimeout(1500);
    const horni = () => page.evaluate(() => { const b = document.querySelector(".lux-open-panel"); if (!b) return { chyba: "tlacitko neni" }; const r = b.getBoundingClientRect(); const out = [];
      for (const [fx, fy] of [[0.5, 0.5], [0.15, 0.5], [0.85, 0.5], [0.5, 0.2], [0.5, 0.8]]) { const e = document.elementFromPoint(r.left + r.width * fx, r.top + r.height * fy); out.push(e === b || b.contains(e) ? "tlacitko" : (e ? e.className || e.tagName : "nic")); }
      return { body: out }; });
    const h0 = await horni();
    t(`${w}: v peti bodech tlacitka "Cinnosti pri tomto osvetleni" je nahore SAMO tlacitko (ne zamek, ne uchyt)`, h0.body && h0.body.every((x) => x === "tlacitko"), h0);
    const box = await page.locator(".lux-open-panel").boundingBox();
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
    await page.waitForTimeout(900);
    const p = await page.evaluate(() => { const e = document.querySelector(".lux-hover"); if (!e || e.hidden) return null; const b = e.getBoundingClientRect(), ov = document.querySelector(".lux-overlay").getBoundingClientRect();
      return { verdikt: (e.querySelector(".lux-verdict") || {}).innerText, uvnitr: b.left >= ov.left - 1 && b.right <= ov.right + 1 && b.top >= ov.top - 1 && b.bottom <= ov.bottom + 1, rolovatelny: e.scrollHeight > e.clientHeight + 1, hscroll: e.scrollWidth > e.clientWidth + 1 }; });
    t(`${w}: klepnuti dotykem otevre panel s verdiktem, uvnitr platna, bez vodorovneho posunu`, !!p && /Lze dělat/.test(p.verdikt || "") && /Nelze dělat/.test(p.verdikt || "") && p.uvnitr && !p.hscroll, p);
    if (SHOT) await page.screenshot({ path: `${SHOT}_${w}.png` });
    if (p) {
      const kz = await page.locator(".lux-close").boundingBox();
      await page.touchscreen.tap(kz.x + kz.width / 2, kz.y + kz.height / 2); await page.waitForTimeout(500);
      t(`${w}: tlacitko x panel zavre`, await page.evaluate(() => { const e = document.querySelector(".lux-hover"); return !e || e.hidden; }));
    }
    t(`${w}: zadne chyby ve strance`, errs.length === 0, errs.slice(0, 3));
    await ctx.close();
  }
  console.log(`\n${total - bad}/${total} kontrol OK` + (bad ? `; SELHALO ${bad}` : ""));
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
