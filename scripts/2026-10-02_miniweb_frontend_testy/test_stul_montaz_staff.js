// Pole "Montaz (% z ceny stolu)" v zamestnaneckem Generatoru stolu (webapp/js/stul-montaz-staff.js; Robert 2026-10-04): jen kdyz server odpovi, validace, PUT {pct}, hlasky.
// Samostatny modul proti falesnemu API (GET/PUT /api/stul/montaz, kontrakt bot5); stranka generatoru ho jen pripoji (StulMontazStaff.mount).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch(); const ctx = await browser.newContext(); const puts = [];
  let getMode = { status: 200, body: { pct: 12, default: 12, available: true, stored: false } }, putMode = { status: 200 };
  await ctx.route("http://localhost.test/**", r => r.fulfill({ status: 200, contentType: "text/html", body: "<!doctype html><body></body>" }));
  await ctx.route("**/api/stul/montaz", async (route) => {
    const m = route.request().method();
    if (m === "GET") return route.fulfill({ status: getMode.status, contentType: "application/json", body: JSON.stringify(getMode.body || {}) });
    const body = JSON.parse(route.request().postData() || "{}"); puts.push(body);
    if (putMode.status !== 200) return route.fulfill({ status: putMode.status, contentType: "application/json", body: JSON.stringify(putMode.body || {}) });
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ pct: body.pct, default: 12, available: body.pct > 0, stored: true }) });
  });
  async function open() { const pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message)); await pg.goto("http://localhost.test/x"); await pg.setContent('<!doctype html><html><body><div id="h"></div></body></html>'); await pg.addScriptTag({ path: "/opt/konfigurator/webapp/js/stul-montaz-staff.js" }); await pg.evaluate(() => window.StulMontazStaff.mount(document.getElementById("h"))); await pg.waitForTimeout(400); return pg; }

  getMode = { status: 404, body: {} };
  let pg = await open();
  ok(await pg.locator("#staffMontaz").isHidden(), "M1 starý server (404) nebo bez práva (403): pole zůstane skryté"); await pg.close();
  getMode = { status: 403, body: { error: "forbidden" } }; pg = await open();
  ok(await pg.locator("#staffMontaz").isHidden(), "M1b bez oprávnění (403): pole zůstane skryté"); await pg.close();

  getMode = { status: 200, body: { pct: 12, default: 12, available: true, stored: false } }; pg = await open();
  const t = await pg.locator("#staffMontaz").innerText();
  ok(await pg.locator("#montazPct").inputValue() === "12" && /Montáž \(% z ceny stolu\)/.test(t) && /Zákazník vidí jen částku, ne procento/.test(t) && /platí výchozí sazba 12 %/.test(t), "M2 server odpověděl: pole s hodnotou 12, vysvětlení a poznámka ‚zatím nenastaveno‘");
  await pg.fill("#montazPct", "15"); await pg.click("#montazUloz"); await pg.waitForTimeout(300);
  ok(puts.length === 1 && puts[0].pct === 15 && /Uloženo: 15 %/.test(await pg.locator("#montazStav").innerText()), "M3 Uložit 15 → PUT {pct:15} a hláška ‚Uloženo: 15 %‘");
  puts.length = 0;
  for (const v of ["abc", "120", "-1", "", "12,345"]) { await pg.fill("#montazPct", v); await pg.click("#montazUloz"); await pg.waitForTimeout(150); }
  ok(puts.length === 0 && /od 0 do 100/.test(await pg.locator("#montazStav").innerText()), "M4 neplatné hodnoty (abc, 120, -1, prázdné, 12,345) se neposílají, hláška ‚číslo od 0 do 100‘");
  await pg.fill("#montazPct", "12,5"); await pg.click("#montazUloz"); await pg.waitForTimeout(300);
  ok(puts.length === 1 && puts[0].pct === 12.5, "M5 desetinná čárka 12,5 → PUT {pct:12.5}"); puts.length = 0;
  await pg.fill("#montazPct", "0"); await pg.click("#montazUloz"); await pg.waitForTimeout(300);
  ok(puts[0] && puts[0].pct === 0 && /montáž se zákazníkům nenabízí/.test(await pg.locator("#montazStav").innerText()), "M6 0 → PUT {pct:0} a hláška, že se montáž zákazníkům nenabízí"); puts.length = 0;
  await pg.click("#montazVychozi"); await pg.waitForTimeout(300);
  ok(puts[0] && puts[0].pct === 12 && await pg.locator("#montazPct").inputValue() === "12" && /Výchozí \(12\)/.test(await pg.locator("#montazVychozi").innerText()), "M7 tlačítko Výchozí (12) uloží 12");
  putMode = { status: 400, body: { error: "pct_invalid" } }; await pg.fill("#montazPct", "20"); await pg.click("#montazUloz"); await pg.waitForTimeout(300);
  ok(/od 0 do 100/.test(await pg.locator("#montazStav").innerText()), "M8 server odmítne (400 pct_invalid): srozumitelná hláška");
  putMode = { status: 403, body: { error: "forbidden" } }; await pg.click("#montazUloz"); await pg.waitForTimeout(300);
  ok(/nemáš oprávnění/.test(await pg.locator("#montazStav").innerText()) && !(await pg.locator("#montazUloz").isDisabled()), "M9 bez oprávnění (403): hláška, tlačítko zase použitelné");
  ok(!pg.errs.length, "M10 bez JS chyb" + (pg.errs[0] ? " | " + pg.errs[0] : "")); await pg.close();
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
