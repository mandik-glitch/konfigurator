// "Ulozit konfiguraci" ve vlozenem generatoru (Robert 2026-10-05) nad SKUTECNYM backendem (api/stul_ulozeni.py) a docasnymi tabulkami (bridge_kosik.py; registry a DNS podstrcene, zadny
// e-mail). Overuje: tlacitko jen kdyz backend funkci ma, validace v prohlizeci (nic neodejde), chyby ze serveru u spravnych poli (IC neznamy v registru, domena e-mailu), uspech s odkazem
// pro navrat, zaznam + lead v CRM, obnoveni z odkazu ?ulozena=, neplatny odkaz, a ze se konfigurace po zavreni prohlizece neuchova (sessionStorage, ne localStorage).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const BASE = process.env.BASE, PID = process.env.PID;
let bad = 0, total = 0; const ok = (c, t) => { total++; if (!c) bad++; console.log(`[${c ? "OK   " : "CHYBA"}] ${t}`); };
const W = ".pdc-slot[data-slot=w] .pdc-num";
const reg = (q) => fetch(`${BASE}/__bridge/registry?${q}`).then(r => r.json());
const dbg = () => fetch(`${BASE}/__bridge/ulozeni`).then(r => r.json());
(async () => {
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const ctx = await browser.newContext({ viewport: { width: 1300, height: 1000 } });
  const posts = []; ctx.on("request", r => { if (r.method() === "POST" && /configurator\/ulozit/.test(r.url())) posts.push(r.postDataJSON()); });
  const pg = await ctx.newPage(); const errs = []; pg.on("pageerror", e => errs.push(e.message));
  const ready = async (p) => { await p.locator(W).waitFor({ timeout: 90000 }); await p.locator(".emb-order-btn:not([disabled])").waitFor({ timeout: 90000 }); };
  await reg("ares=ok&rpo=ok&doh=ok&dig=ok");
  await pg.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(pg);
  await pg.locator(".pdc-save:not([hidden])").waitFor({ timeout: 30000 });
  ok(await pg.locator(".pdc-save-btn").isVisible() && (await pg.locator(".pdc-save-btn").innerText()) === "Uložit konfiguraci", "U1 tlačítko „Uložit konfiguraci“ je vidět (backend funkci má)");
  ok(await pg.locator(".pdc-save-form").isHidden(), "U2 formulář je zavřený, dokud zákazník nekliknul");
  await pg.locator(W).fill("1700"); await pg.locator(W).blur(); await pg.waitForTimeout(2000);
  await pg.locator(".pdc-save-btn").click();
  ok(await pg.locator(".pdc-save-form").isVisible() && await pg.locator("#pdcSave_ico").isVisible() && await pg.locator("#pdcSave_email").isVisible() && await pg.locator("#pdcSave_phone").isVisible(), "U3 po kliknutí je formulář s IČO, e-mailem a telefonem");
  ok(/neuchová/.test(await pg.locator(".pdc-save-intro").innerText()), "U4 úvod říká, že se konfigurace po zavření prohlížeče neuchová");
  // prazdny formular: chyby v prohlizeci, na server nic neodejde
  await pg.locator(".pdc-save-go").click(); await pg.waitForTimeout(300);
  const chyby = await pg.$$eval(".pdc-save-err", e => e.map(x => x.textContent).filter(Boolean));
  ok(chyby.length === 4 && posts.length === 0, "U5 prázdný formulář: čtyři chyby u polí (IČO, e-mail, telefon, souhlas), na server nic neodešlo: " + chyby.join(" | "));
  // chyby ze serveru
  await pg.locator("#pdcSave_ico").fill("12345678"); await pg.locator("#pdcSave_email").fill("zakaznik@example.cz"); await pg.locator("#pdcSave_phone").fill("603 230 059"); await pg.locator("#pdcSave_consent").check();
  await pg.locator(".pdc-save-go").click(); await pg.locator("#pdcSaveErr_ico:not(:empty)").waitFor({ timeout: 15000 });
  ok(posts.length === 1 && /nemá platný tvar/.test(await pg.locator("#pdcSaveErr_ico").innerText()), "U6 IČO se špatnou kontrolní číslicí: server vrátí ico_invalid a chyba je u pole IČO: " + await pg.locator("#pdcSaveErr_ico").innerText());
  await pg.locator("#pdcSave_ico").fill("28337638"); await reg("ares=404");
  await pg.locator(".pdc-save-go").click(); await pg.locator("#pdcSaveErr_ico:not(:empty)").waitFor({ timeout: 15000 });
  ok(/nenašlo/.test(await pg.locator("#pdcSaveErr_ico").innerText()), "U7 IČO, které registr nezná: „" + await pg.locator("#pdcSaveErr_ico").innerText() + "“");
  await reg("ares=down");
  await pg.locator(".pdc-save-go").click(); await pg.locator("#pdcSaveErr_ico:not(:empty)").waitFor({ timeout: 15000 });
  ok(/nedostupný/.test(await pg.locator("#pdcSaveErr_ico").innerText()) && (await dbg()).saved.length === 0, "U8 registr nedostupný: hláška „zkuste to za chvíli“ a nic se neuložilo");
  await reg("ares=ok&doh=nx");
  await pg.locator(".pdc-save-go").click(); await pg.locator("#pdcSaveErr_email:not(:empty)").waitFor({ timeout: 15000 });
  ok(/nepřijímá poštu/.test(await pg.locator("#pdcSaveErr_email").innerText()) && !(await pg.locator("#pdcSaveErr_ico").innerText()), "U9 doména e-mailu neexistuje: chyba je u pole E-mail (IČO už je v pořádku)");
  // uspech
  await reg("ares=ok&doh=ok");
  await pg.locator(".pdc-save-go").click(); await pg.locator(".pdc-save-done:not([hidden])").waitFor({ timeout: 20000 });
  const link = await pg.locator(".pdc-save-link").inputValue();
  ok(/Konfigurace je uložena/.test(await pg.locator(".pdc-save-ok").innerText()) && /TESTOVAC/i.test(await pg.locator(".pdc-save-firma").innerText()) && /[?&]ulozena=[A-Za-z0-9_-]{22}$/.test(link), "U10 uloženo: potvrzení, firma z registru a odkaz pro návrat: " + link.replace(BASE, ""));
  ok(/-mailem ho automaticky neposíláme/i.test(await pg.locator(".pdc-save-note").innerText()), "U11 poznámka: odkaz se e-mailem automaticky neposílá");
  const d = await dbg();
  ok(d.saved.length === 1 && d.saved[0].ico === "28337638" && d.saved[0].email === "zakaznik@example.cz" && d.saved[0].phone === "+420603230059" && JSON.parse(d.saved[0].selection_json).w === 1700, "U12 na serveru: záznam s ověřeným IČO, e-mailem, telefonem a výběrem (šířka 1700)");
  ok(d.leads.length === 1 && d.leads[0].source === "stul_ulozeni" && d.messages.length === 1 && /Odkaz pro návrat/.test(d.messages[0].body), "U13 pro zaměstnance vznikl lead v CRM (source stul_ulozeni) s odkazem");
  // obnoveni z odkazu
  const p2 = await ctx.newPage(); p2.on("pageerror", e => errs.push(e.message));
  await p2.goto(link); await ready(p2); await p2.locator(".pdc-save-notice:not([hidden])").waitFor({ timeout: 20000 });
  ok((await p2.locator(W).inputValue()) === "1700" && /načtena/.test(await p2.locator(".pdc-save-notice").innerText()), "U14 odkaz vrátí uloženou konfiguraci (šířka 1700) a ukáže zprávu, že byla načtena");
  const p3 = await ctx.newPage(); p3.on("pageerror", e => errs.push(e.message));
  await p3.goto(`${BASE}/embed/stul.html?p=${PID}&ulozena=ZZZZZZZZZZZZZZZZZZZZZZ`); await ready(p3); await p3.locator(".pdc-save-notice:not([hidden])").waitFor({ timeout: 20000 });
  ok(/neplatí|vypršel/.test(await p3.locator(".pdc-save-notice").innerText()) && (await p3.locator(W).inputValue()) !== "1700", "U15 neplatný odkaz: zpráva „neplatí nebo vypršel“, generátor ukáže výchozí konfiguraci");
  // prohlizec konfiguraci nedrzi: pending a kosik hosta jen v relaci
  await p3.evaluate(() => { localStorage.setItem("stulEmbedPending", "x"); localStorage.setItem("stulHostKosik", "x"); }); await p3.reload(); await ready(p3);
  ok(await p3.evaluate(() => localStorage.getItem("stulEmbedPending") === null && localStorage.getItem("stulHostKosik") === null), "U16 staré klíče konfigurace v localStorage (přežily by zavření prohlížeče) se při načtení smažou");
  // stara stranka (po zmene pravidel generatoru, bot8 rules_version 2026-10-05.1): server vrati 409 rules_changed -> existujici text pdc.rulesChanged (ne "sluzba nedostupna"), modul nacte nove schema (resolve), druhy pokus projde
  const p5 = await ctx.newPage(); p5.on("pageerror", e => errs.push(e.message));
  let stale = true, resolves = 0;
  await p5.route("**/configurator/ulozit", async (route) => { if (stale) { stale = false; const b = JSON.parse(route.request().postData()); b.configuration.rules_version = "stara-verze"; return route.continue({ postData: JSON.stringify(b) }); } return route.continue(); });
  p5.on("request", r => { if (/configurator\/resolve/.test(r.url()) && r.method() === "POST") resolves++; });
  await p5.goto(`${BASE}/embed/stul.html?p=${PID}`); await ready(p5); await p5.locator(".pdc-save:not([hidden])").waitFor({ timeout: 30000 });
  await p5.locator(".pdc-save-btn").click();
  await p5.locator("#pdcSave_ico").fill("28337638"); await p5.locator("#pdcSave_email").fill("zakaznik@example.cz"); await p5.locator("#pdcSave_phone").fill("603 230 059"); await p5.locator("#pdcSave_consent").check();
  const r0 = resolves;
  await p5.locator(".pdc-save-go").click(); await p5.locator(".pdc-save-status.is-bad").waitFor({ timeout: 15000 });
  await p5.waitForTimeout(1500);
  const hlaska = await p5.locator(".pdc-save-status").innerText();
  ok(/Nabídka voleb se změnila/.test(hlaska) && !/později/.test(hlaska) && resolves > r0 && await p5.locator(".pdc-save-form").isVisible(), "U17 409 rules_changed: hláška „" + hlaska + "“, modul načetl nové schéma (resolve +" + (resolves - r0) + "), formulář zůstal vyplněný");
  ok(await p5.locator("#pdcSave_ico").inputValue() === "28337638", "U18 údaje ve formuláři zůstaly");
  await p5.locator(".pdc-save-go").click(); await p5.locator(".pdc-save-done:not([hidden])").waitFor({ timeout: 20000 });
  ok(/[?&]ulozena=[A-Za-z0-9_-]{22}$/.test(await p5.locator(".pdc-save-link").inputValue()) && (await dbg()).saved.length === 2, "U19 po načtení nového schématu druhé uložení projde (na serveru 2 záznamy)");
  ok(!errs.length, "U20 bez JS chyb" + (errs[0] ? " | " + errs[0] : ""));
  await Promise.race([browser.close(), new Promise(r => setTimeout(r, 15000))]); console.log(`\n==> ${total - bad}/${total} kontrol OK`); process.exit(bad ? 1 : 0);
})();
