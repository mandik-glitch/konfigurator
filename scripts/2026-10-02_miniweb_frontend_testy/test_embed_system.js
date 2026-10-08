// Vlozeny generator stolu a SYSTEM profilu karty (bot16 2026-10-04): titulek stranky podle systemu produktu (?p=<karta>), ne napevno "systém 30" (nalez bot10 pro ?p=4954).
// Nad skutecnym schematem a generatorem (bridge.py mapuje PID na recept stul_system30 a PID40 = PID+1 na stul_system40).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID, PID40 = process.env.PID40;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } }); const errs = [];
  for (const [pid, sys] of [[PID, 30], [PID40, 40]]) {
    const pg = await ctx.newPage(); pg.on("pageerror", e => errs.push(e.message));
    const sch = await (await fetch(`${BASE}/api/shop/products/${pid}/configurator?lang=cs`)).json();
    ok(sch.system === sys && sch.profile === `${sys}x${sys}`, `Y${sys}a schéma karty ${pid} je systém ${sys} (profil ${sch.profile})`);
    await pg.goto(`${BASE}/embed/stul.html?p=${pid}`); await pg.waitForSelector(".emb-order-btn:not([disabled])", { timeout: 60000 });
    ok((await pg.title()) === `Generátor stolu – systém ${sys}`, `Y${sys}b titulek stránky pro ?p=${pid}: „${await pg.title()}“`);
    await pg.close();
  }
  ok(!errs.length, "Y9 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
