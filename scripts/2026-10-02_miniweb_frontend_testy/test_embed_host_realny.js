// Objednavka HOSTA bez registrace a volitelna montaz ve vlozenem generatoru stolu nad SKUTECNYM backendem (api/stul_objednavka_host.py, stul_montaz.py, orders.py, konfigurace_kosik.py) - pres
// bridge_kosik.py (vse nad DOCASNYMI tabulkami, e-maily zachycene, zadna data v provozu). Overuje kontrakt bot5 z pohledu zakaznika: kalkulace, montaz BEZ procenta, souhrn, formular, odeslani,
// cislo objednavky, ze vznikla objednavka s priznakem shipping_review a samostatnym radkem Montaz, ze nic neodeslo e-mail, idempotenci a vypnuti montaze (sazba 0).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID, OUT = process.env.OUT;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const digits = (s) => Number(String(s).replace(/[^\d]/g, ""));
const W = ".pdc-slot[data-slot=w] .pdc-num";
const bridge = (path) => fetch(BASE + path).then(r => r.json());

(async () => {
  await bridge("/__bridge/anon?on=1");                                     // nepřihlášený host
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 900 } });
  const pg = await ctx.newPage(); const errs = []; pg.on("pageerror", e => errs.push(e.message));
  const orderBodies = []; pg.on("request", r => { if (/\/api\/shop\/stul\/order$/.test(r.url()) && r.method() === "POST") orderBodies.push(JSON.parse(r.postData() || "{}")); });
  // po startu se vzpery zapnou SAMY (auto_on, od 2026-10-05 server posila sam a vzpery se vejdou) = druhy vypocet a cena se na okamzik zmeni; cist cenu az po ustaleni
  const settled = async (ctx) => { let last = null, same = 0; for (let i = 0; i < 50 && same < 4; i++) { const t = await ctx.evaluate(() => ((document.querySelector(".emb-price .big") || {}).textContent || "") + "|" + (document.querySelector(".emb-order-btn") || {}).disabled); if (t === last) same++; else { same = 0; last = t; } await new Promise(r => setTimeout(r, 400)); } };
  const ready = async () => { await pg.locator(".mw-win-stage").waitFor({ timeout: 60000 }); await pg.locator(W).waitFor({ timeout: 60000 }); await pg.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 60000 }); await settled(pg); };
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready();
  const shown = await pg.evaluate(() => ({ net: document.querySelector(".emb-price .big").textContent, price: document.querySelector(".mw-win-price").innerText }));
  const netShown = digits(shown.net);

  // 1) montaz v generatoru: castka od serveru, zadne procento
  await pg.locator("#embMontaz").waitFor({ timeout: 30000 });
  const amt = await pg.locator(".emb-montaz-amt").innerText();
  const probe = await pg.evaluate((pid) => fetch("/api/shop/stul/quote", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: [{ product_id: Number(pid), qty: 1, montaz: true, configuration: { selection: window.__pdcState ? window.__pdcState.sel : {}, rules_version: "x" } }] }) }).then(r => r.status), PID);
  ok(/^\+\s?[\d\s ]+Kč bez DPH$/.test(amt.replace(/\s+/g, " ").trim().replace(/ /g, " ")) || /Kč bez DPH/.test(amt), "H1 zatržítko Montáž ukazuje částku od serveru: " + amt.replace(/\s+/g, " "));
  ok(!/%/.test(shown.price) && !/%/.test(await pg.locator(".mw-win-price").innerText()), "H2 zákazník v okně ceny nevidí žádné procento montáže");
  ok(/Cenu dopravy stanovíme po objednávce/.test(await pg.locator(".emb-shipnote").innerText()) && /zálohovou fakturou/.test(await pg.locator(".emb-shipnote").innerText()), "H3 u zatržítka je věta, že cenu dopravy stanovíme po objednávce a uvidí ji ke schválení před zálohovou fakturou");
  const montazNet = digits(amt);
  // doprovodny text volby (Robert 2026-10-05: smontovano / demontovano; zneni bot7 v i18n/cs.json pdc.montazOn/Off): bez montaze demontovany, s montazi smontovany
  const stavOff = (await pg.locator(".emb-montaz-state").innerText()).trim();
  ok(stavOff === "Stůl dodáme demontovaný (rozložený), sestavíte si ho sami.", "H1b bez montáže je pod volbou text o demontovaném stavu: " + stavOff);
  await pg.locator("#embMontaz").check(); await pg.waitForTimeout(300);
  const stavOn = (await pg.locator(".emb-montaz-state").innerText()).trim();
  ok(stavOn === "Stůl dodáme smontovaný.", "H1c po zatržení Montáže se text změní na smontovaný stav: " + stavOn);
  const rows = await pg.locator(".emb-montaz-rows").innerText();
  ok(/Montáž/.test(rows) && /Celkem s montáží/.test(rows) && /bez DPH/.test(rows) && /s DPH/.test(rows) && !/%/.test(rows), "H4 po zatržení: samostatný řádek Montáž a Celkem s montáží, bez DPH i s DPH: " + rows.replace(/\s+/g, " ").slice(0, 160));

  if (OUT) await pg.locator(".mw-win-price").screenshot({ path: OUT + "/host_okno_ceny.png" });
  // 2) Objednat jako nepřihlášený -> objednávka hosta (ne výzva k přihlášení)
  await pg.locator(".emb-order-btn").click(); await pg.locator(".emb-co:not([hidden])").waitFor({ timeout: 30000 });
  ok(await pg.locator(".emb-order-login").isHidden() && await pg.locator(".mw-pdg").evaluate(e => e.hidden), "H5 nepřihlášený: místo výzvy k přihlášení se otevře objednávka hosta (generátor je schovaný)");
  await pg.locator(".emb-co-line").waitFor({ timeout: 20000 }); await pg.locator(".emb-co-totals .emb-co-row").first().waitFor({ timeout: 20000 });
  const co = await pg.locator(".emb-co").innerText();
  ok(/Kód konfigurace: STL-/.test(co) && /Montáž/.test(co) && !/%/.test(co.replace(/DPH 21 %/g, "")), "H6 souhrn: řádek s kódem konfigurace a montáží, bez procenta montáže");
  const tot = await pg.locator(".emb-co-totals").innerText();
  ok(/Stůl bez DPH/.test(tot) && /Montáž bez DPH/.test(tot) && /Celkem bez DPH/.test(tot) && /DPH 21 %/.test(tot) && /Celkem s DPH/.test(tot), "H7 součty ze serveru: stůl, montáž, celkem bez DPH, DPH 21 %, celkem s DPH");
  const lineTxt = await pg.locator(".emb-co-lineprice").first().innerText();
  ok(/bez DPH/.test(lineTxt) && /s DPH/.test(lineTxt), "H7b cena řádku ze serveru je vždy bez DPH i s DPH (spotřebitel): " + lineTxt.replace(/\s+/g, " "));
  ok((await pg.locator(".emb-co-submit").innerText()).toLowerCase() === "objednávka zavazující k platbě", "H7c odesílací tlačítko říká „Objednávka zavazující k platbě“");
  const goodsShown = digits((await pg.locator(".emb-co-totals .emb-co-row").first().innerText()).split("\n").pop());
  ok(goodsShown === netShown, "H8 cena stolu v souhrnu = cena v generátoru (" + goodsShown + " = " + netShown + ")");
  const ships = await pg.locator(".emb-co-ship label").allInnerTexts();
  ok(ships.length === 2 && /po dohodě/i.test(ships[0]) && /Osobní odběr/.test(ships[1]) && !ships.some(t => /Toptrans/.test(t)), "H9 doprava: „po dohodě“ a „osobní odběr“ (Toptrans bez odhadu se nenabízí): " + ships.join(" | "));
  ok(/Cenu dopravy stanovíme po objednávce/.test(await pg.locator(".emb-co-shipnote").innerText()), "H10 v objednávce je věta o ceně dopravy po objednávce");
  if (OUT) await pg.screenshot({ path: OUT + "/host_panel_souhrn.png", fullPage: true });
  // validace
  await pg.locator(".emb-co-submit").click(); await pg.waitForTimeout(300);
  const errTexts = await pg.locator(".emb-co-err:not([hidden])").allInnerTexts();
  ok(errTexts.length >= 6 && orderBodies.length === 0, "H11 prázdný formulář: chyby u polí (" + errTexts.length + "), nic se neodeslalo");
  // vyplneni a odeslani
  await pg.fill("#embCo_name", "Jan Novák"); await pg.fill("#embCo_email", "jan.novak@example.test"); await pg.fill("#embCo_phone", "+420 603 111 222");
  await pg.fill("#embCo_d_street", "Testovací 12"); await pg.fill("#embCo_d_city", "Praha"); await pg.fill("#embCo_d_zip", "110 00"); await pg.fill("#embCo_note", "Test – neposílat");
  await pg.locator("#embCo_consent").check();
  await pg.locator(".emb-co-submit:not([disabled])").waitFor({ timeout: 30000 });
  await pg.locator(".emb-co-submit").click(); await pg.locator(".emb-co-done:not([hidden])").waitFor({ timeout: 60000 });
  if (OUT) await pg.screenshot({ path: OUT + "/host_hotovo.png", fullPage: true });
  const done = await pg.locator(".emb-co-done").innerText();
  const ref = (done.match(/Číslo objednávky:\s*(\S+)/) || [])[1] || "";
  ok(/Děkujeme, objednávka byla přijata/.test(done) && ref.length > 3, "H12 po odeslání: poděkování a číslo objednávky " + ref);
  ok(/Cenu dopravy/.test(done) && /zálohovou fakturu/i.test(done) && !/QR|zaplat(te|it) hned/i.test(done), "H13 hostovi se říká, že cenu dopravy určíme a zálohovou fakturu pošleme po potvrzení dopravy (žádné QR ani platba hned)");
  ok((await pg.evaluate(() => sessionStorage.getItem("stulHostKosik"))) === null, "H14 hostovský košík v prohlížeči se po odeslání vyprázdnil");
  const b1 = orderBodies[0] || {};
  ok(b1.items && b1.items[0].montaz === true && b1.items[0].product_id === Number(PID) && b1.shipping === "quote" && b1.payment === "transfer" && b1.consent === true && b1.billing && b1.billing.same === true && b1.website === "" && typeof b1.expected_total_net === "number" && !("price" in b1.items[0]),
     "H15 tělo objednávky: položka s montáží bez ceny, shipping quote, payment transfer, consent, billing same, honeypot prázdný, expected_total_net");

  // 3) co vzniklo na serveru (docasne tabulky)
  const db = await bridge("/__bridge/orders");
  const o = db.orders[0] || {}, items = o.items || [];
  ok(db.orders.length === 1 && o.order_number === ref && Number(o.shipping_review) === 1 && o.user_id == null, "H16 vznikla 1 objednávka bez účtu (user_id NULL) s příznakem shipping_review=1, číslo " + o.order_number);
  ok(items.length === 2 && /STL-/.test(items[0].product_name_snapshot) && /^Montáž – STL-/.test(items[1].product_name_snapshot), "H17 v objednávce 2 řádky: stůl a samostatný řádek „Montáž – kód“: " + items.map(i => i.product_name_snapshot).join(" | ").slice(0, 160));
  ok(Math.round(Number(items[0].unit_price_czk)) === netShown && items.length > 1 && Math.abs(Number(items[1].unit_price_czk) - montazNet) < 1, "H18 ceny řádků ze serveru: stůl " + items[0].unit_price_czk + " (generátor " + netShown + "), montáž " + (items[1] && items[1].unit_price_czk) + " (zatržítko " + montazNet + ")");
  ok(Math.abs(Number(o.total_czk) - (netShown + montazNet) * 1.21) < 2 || Math.abs(Number(o.total_czk) - (netShown + montazNet)) < 2, "H19 celková cena objednávky " + o.total_czk + " odpovídá stolu + montáži (doprava 0, určí zaměstnanec)");
  ok(/spotřebitel\/bez IČO/.test(o.admin_note || "") && /obchodní podmínky|obchodni podminky/i.test(o.admin_note || ""), "H19b objednávka bez firmy a IČO (spotřebitel) projde; v poznámce zaměstnance je „spotřebitel/bez IČO“ a potvrzení podmínek");
  ok(db.emails.length === 0 && db.queue === 0, "H20 žádný e-mail se neodeslal ani nezařadil (e-mail s fakturou až po schválení dopravy)");
  // idempotence: stejny obsah podruhe
  const rep = await pg.evaluate((body) => fetch("/api/shop/stul/order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then(r => r.json().then(d => ({ st: r.status, d }))), b1);
  ok(rep.st === 200 && rep.d.reference === ref && rep.d.idempotent_replay === true && (await bridge("/__bridge/orders")).orders.length === 1, "H21 stejné odeslání podruhé = původní objednávka (idempotence), nic nového nevzniklo");

  // 4) montaz vypnuta (sazba 0): zatrzitko se vubec neukaze
  await bridge("/__bridge/setting?key=stul_montaz_pct&value=0");
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(); await pg.waitForTimeout(1500);
  ok(await pg.locator(".emb-montaz").isHidden(), "H22 při sazbě montáže 0 se zatržítko Montáž vůbec nenabízí");
  await bridge("/__bridge/setting?key=stul_montaz_pct");                   // smazat = vychozi 12 %

  ok(!errs.length, "H23 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  if (OUT) await pg.screenshot({ path: OUT + "/host_realny.png", fullPage: true });
  await browser.close(); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
