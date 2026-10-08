// schema slots[].auto_on (bot8 2026-10-04): vzpery se po resolve zapnou SAME, kdyz rameno > 500 a vejdou se; rucni odskrtnuti je respektovano; "Zpet na vychozi" to vrati.
// Schema se nad skutecnym API v testu doplni (starsi server auto_on neposila; novy ho posila sam, je stejne); modul bez pole se chova jako dnes.
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID || "9001";
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const MSG = "Při délce ramene nad 500 mm se přidala šikmá vzpěra.";
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await (await browser.newContext({ viewport: { width: 1300, height: 900 } })).newPage(); const errs = [];
  page.on("pageerror", e => errs.push(e.message));
  await page.route("**/api/shop/products/*/configurator*", async (route) => {
    const r = await route.fetch(); const j = await r.json();
    (j.slots || []).forEach(s => { if (s.id === "braces") s.auto_on = { when: { slot: "arm", above: 500 }, message: MSG }; });
    await route.fulfill({ response: r, json: j });
  });
  await page.goto(`${BASE}/miniweb/legal.html?shop=packstations&lang=cs&demo=1`); await page.waitForTimeout(800);
  await page.evaluate(async (pid) => {
    const load = src => new Promise(ok => { const s = document.createElement("script"); s.src = src; s.onload = ok; document.head.appendChild(s); });
    await load("/js/product-configurator.js");
    const stage = document.createElement("div"), panelHost = document.createElement("div"); document.body.appendChild(stage); document.body.appendChild(panelHost);
    window.__pdcDebug = true;
    await PdConfigurator.init({ product: { id: Number(pid), configurator: { available: true, default_view: "configurator" } }, noTurntable: true, lang: "cs",
      dom: { tabsBefore: null, visual: [], stageHost: stage, panelHost: panelHost }, page: { setPrice() {}, setBuyState() {}, toast() {}, onActivate() {}, track() {} },
      assets: { cssNow: ["/css/product-configurator.css"], css: ["/css/v3d.css"], viewer: "/js/v3d/viewer3d.js" } });
  }, PID);
  await page.waitForSelector(".pdc-slot[data-slot=w] .pdc-num", { timeout: 30000 }); await page.waitForTimeout(1500);
  const brace = () => page.evaluate(() => ({ on: window.__pdcState.sel.braces, dis: ((((window.__pdcState.last || {}).options || {}).braces || {}).on || {}).disabled }));
  const setW = async (v) => { await page.locator(".pdc-slot[data-slot=w] .pdc-num").fill(String(v)); await page.locator(".pdc-slot[data-slot=w] .pdc-num").dispatchEvent("change"); await page.waitForTimeout(3500); };
  const led = async () => { await page.locator(".pdc-slot[data-slot=led] input[type=checkbox]").evaluate(e => e.click()); await page.waitForTimeout(3500); };     // LED vypnuta = vzpery se nevejdou (server je odebere)
  const msg = async () => (await page.locator(".pdc-notices").innerText()).includes("šikmá vzpěra");
  // Od 2026-10-05 (bot8 7220a163: panely mezi stojkami) se vzpery vejdou i u nejuzsiho stolu a server auto_on posila sam; stav "nevejdou se" proto vyvolava vypnuti LED osvetleni
  const b0 = await brace();
  ok(b0.on === true && b0.dis === false && await msg(), "A1 výchozí stůl (rameno 560 > 500, vejdou se): vzpěry se zapnou samy hned po načtení a zpráva z auto_on je mezi oznámeními: braces=" + b0.on);
  await led();
  const b1 = await brace(); ok(b1.on === false && b1.dis === true, "A2 vypnutí LED: server vzpěry odebere (nevejdou se): braces=" + b1.on + ", disabled=" + b1.dis);
  await setW(1800);
  const b2 = await brace(); ok(b2.on === false, "A3 jiná šířka, ale LED stále vypnutá: vzpěry se nezapnou (nevejdou se): braces=" + b2.on);
  await led();
  const b3 = await brace(); ok(b3.on === true && await msg(), "A4 LED zase zapnutá (jiná kombinace šířky): vzpěry se zapnou samy a zpráva je mezi oznámeními: braces=" + b3.on);
  await page.locator(".pdc-slot[data-slot=braces] input[type=checkbox]").uncheck({ force: true }); await page.waitForTimeout(2500);
  await setW(1900);
  const b4 = await brace(); ok(b4.on === false, "A5 ručně vypnuté vzpěry zůstanou vypnuté i po další změně šířky (userOff): braces=" + b4.on);
  await page.locator(".pdc-head .pdc-link").click(); await page.waitForTimeout(3500);
  const b5 = await brace(); ok(b5.on === true, "A6 Zpět na výchozí: výchozí stůl má vzpěry zapnuté samy (userOff i pojistka smyčky vynulované): braces=" + b5.on);
  await led(); await setW(1800); await led();
  const b6 = await brace(); ok(b6.on === true, "A8 po resetu zase funguje: vypnutí LED vzpěry odebere, po zapnutí LED při jiné šířce se zapnou samy: braces=" + b6.on);
  await led(); await setW(1300); await setW(1800); await led();
  const b7 = await brace(); ok(b7.on === true, "A9 po návratu na stejnou šířku (přes jinou) se vzpěry zapnou samy znovu (uživatel je nevypnul): braces=" + b7.on);
  ok(!errs.length, "A7 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
