// Vlozitelny generator stolu (webapp/embed/stul.html) nad SKUTECNYM verejnym API (bridge.py): bez zamestnaneckych oken, cena, vyska rodici, povoleny jen rodic logiman.cz.
// Rodicovske stranky se simuluji pres page.route na https://www.logiman.cz/ a https://evil.example/ (zadna skutecna sit).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const parentHtml = `<!doctype html><title>rodic</title><iframe id="f" src="https://embed.test/embed/stul.html?p=${PID}" style="width:1200px;height:500px;border:0"></iframe>
<script>window.__h=[];addEventListener("message",e=>{if(e.data&&e.data.type==="stul-embed-height")window.__h.push(e.data.height)})</script>`;
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  // Chrome blokuje (Local Network Access) iframe z verejne stranky na http://127.0.0.1: generator proto bezi na falesne https://embed.test, ktere se proxuje na bridge
  await ctx.route("https://embed.test/**", async (route) => { const u = new URL(route.request().url()); await route.fulfill({ response: await route.fetch({ url: BASE + u.pathname + u.search }) }); });
  async function open(url, html) {
    const pg = await ctx.newPage(); pg.errs = []; pg.on("pageerror", e => pg.errs.push(e.message));
    await pg.route(url, r => r.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html }));
    await pg.goto(url); return pg;
  }
  // 1) povoleny rodic
  let pg = await open("https://www.logiman.cz/test-stul.html", parentHtml);
  const fr = pg.frameLocator("#f");
  await fr.locator(".mw-win-stage").waitFor({ timeout: 40000 }); await fr.locator(".pdc-slot[data-slot=w] .pdc-num").waitFor({ timeout: 40000 }); await pg.waitForTimeout(3500);
  const info = await pg.frames().find(f => f.url().includes("/embed/stul.html")).evaluate(() => ({
    wins: [...document.querySelectorAll(".mw-win")].map(e => e.dataset.win + (e.hidden ? "(skryto)" : "")), body: document.body.innerText.replace(/\s+/g, " "), header: !!document.getElementById("mwHeader") || !!document.querySelector("header"), footer: !!document.querySelector("footer"),
    login: /přihlas/i.test(document.body.innerText) }));
  ok(info.wins.includes("stage") && info.wins.includes("price") && info.wins.some(w => /^dim$/.test(w)), "E1 vložený generátor vykreslí 3D, cenu a okna voleb: " + info.wins.join(","));
  ok(!info.header && !info.footer && !info.login, "E2 bez hlavičky, patičky a přihlašování");
  ok(!info.wins.some(w => /^(bom|rules|env|info)/.test(w)), "E3 žádná zaměstnanecká okna (kusovník, pravidla, HDRI)");
  ok(/Kč bez DPH/.test(info.body) && /Kód konfigurace/.test(info.body), "E4 cena v Kč bez DPH a kód konfigurace: " + (info.body.match(/[\d  ]+ Kč bez DPH/) || [""])[0]);
  const heights = await pg.evaluate(() => window.__h);
  ok(heights.length >= 1 && heights[heights.length - 1] > 400, "E5 rodič dostává výšku (postMessage): " + heights.slice(-3).join(", ") + " px");
  ok(!pg.errs.length, "E6 bez JS chyb na straně rodiče" + (pg.errs[0] ? " | " + pg.errs[0] : "")); await pg.close();
  // 2) cizi rodic
  pg = await open("https://evil.example/x.html", parentHtml);
  await pg.waitForTimeout(2500);
  const blocked = await pg.frames().find(f => f.url().includes("/embed/stul.html")).evaluate(() => ({ t: document.body.innerText, wins: document.querySelectorAll(".mw-win").length }));
  ok(/jen na stránky logiman\.cz/.test(blocked.t) && blocked.wins === 0, "E7 cizí rodič (evil.example): generátor se nenačte, ukáže se hláška"); await pg.close();
  // 3) primo otevreno (nahled)
  pg = await ctx.newPage(); const e3 = []; pg.on("pageerror", e => e3.push(e.message));
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}&theme=light`); await pg.locator(".mw-win-stage").waitFor({ timeout: 40000 }); await pg.waitForTimeout(1500);
  ok(await pg.evaluate(() => document.documentElement.getAttribute("data-theme")) === "light" && !e3.length, "E8 přímo otevřená stránka funguje, ?theme=light přepne motiv" + (e3[0] ? " | " + e3[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
