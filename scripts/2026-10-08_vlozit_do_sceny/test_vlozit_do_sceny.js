// Test: tlacitko "Vlozit do Sceny" v Generatoru stolu, PROTOKOL v2 (webapp/js/stul-do-sceny.js + webapp/js/scene/stul-konfigurator.js; bot10, 2026-10-08).
// Robert 2026-10-08: "klikl jsem na vlozit do sceny, nic se nevlozilo, a napsala se divna veta" ("✔ Stul je vlozeny do otevrene Sceny (vymeni se jen dily stolu, ostatni obsah zustane)").
// Pricina (nginx log 17:56-17:58): v jeho prohlizeci bylo vic karet Sceny; puvodni protokol poslal stul DO VSECH a prvni odpoved do 1,5 s vyhlasil za uspech, aniz rekl, kam se vlozil; navigace "Scena"
// v zahlavi generatoru otevrela vzdy NOVOU, PRAZDNOU Scenu; studena Scena stihla odpovedet az po 1,5 s ("Scena neni otevrena" -> dalsi zbytecne karty).
// Overuje SKUTECNOU Scenu a SKUTECNY generator (stul-konfigurator.html) v Chromiu pres most scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py (API cte Flask, DB se jen cte, zapisy se nepredavaji):
// zadna Scena, jedna viditelna (vlozeni trva > 1,5 s a presto se nehlasi "neni otevrena"), vymena, DVE Sceny (stul jen do viditelne, druha nedotcena), jen SKRYTA Scena (hlaseni "jina karta" + ● v nazvu,
// zmizi po zobrazeni), puvodni protokol (Scena ze starsi verze stranky), Scena s chybou (text hlaseni dojde do generatoru), pomale vlozeni (3,5 s), skutecna chyba API, prohlizec bez BroadcastChannel, piny.
// v3 (Robert 2026-10-08: "nemusim mit otevrenou scenu, proste se otevre scena s tim modelem"): tlacitko "Vlozit do Sceny" VZDY otevre novou kartu Sceny se stolem (sekce A), vlozeni do uz
// otevrene Sceny (protokol v2, sekce 1-7) je maly odkaz pod hlasenim (#sceneVlozitDoOtevrene).
// Spusteni (REPO = koren s api / scripts, WEB_DIR = kandidat statiky):
//   systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRIVATE_FILES_DIR=/tmp/pf_vloz [--setenv=REPO=<koren> --setenv=WEB_DIR=<koren>/webapp] \
//     --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-06_nabidka_vykresy_testy/_most_scena.py /opt/konfigurator/scripts/2026-10-08_vlozit_do_sceny/test_vlozit_do_sceny.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const crypto = require('crypto');
const path = require('path');
const BASE = process.env.BASE, WEB = process.env.WEB_DIR || '/opt/konfigurator/webapp', REPO = process.env.REPO || '/opt/konfigurator';
const STARA_REV = process.env.STARA_REV || '2dde9961';                      // posledni revize prijemce ve Scene PRED protokolem v2 (stary prijemce: ping nezna, na vloz odpovi {type:"ack", ok})
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 700))); };

// viditelnost karty se v headless Chromiu nedeli (vsechny stranky jsou "visible") -> rizeni pres __vis; document.hidden / visibilityState cte kod Sceny
const INIT_VIS = () => { window.__vis = 'visible'; Object.defineProperty(document, 'hidden', { configurable: true, get: () => window.__vis === 'hidden' }); Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => window.__vis }); };

const T = ms => new Promise(r => setTimeout(r, ms));
const chyby = [], dialogy = [];
function chytej(page, jmeno) {
  page.on('pageerror', e => chyby.push(jmeno + ': ' + e.message.slice(0, 200)));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) chyby.push(jmeno + ' console: ' + m.text().slice(0, 200)); });
  page.on('dialog', async d => { dialogy.push(jmeno + ': ' + d.message().slice(0, 200)); await d.dismiss(); });
}

// po nacteni Scena jeste chvili pracuje (modely, prvni snimky): odpoved na ping by pak trvala vterinami - ceka se, az se smycka uklidni (zpozdeni casovace < 80 ms sestkrat po sobe)
async function usad(page, maxMs) {
  await page.evaluate(async limit => { const konec = performance.now() + limit; let dobre = 0; while (performance.now() < konec && dobre < 6) { const t = performance.now(); await new Promise(r => setTimeout(r, 100)); dobre = (performance.now() - t - 100) < 80 ? dobre + 1 : 0; } }, maxMs || 90000);
}

async function scena(ctx, jmeno, skryta) {
  const page = await ctx.newPage();
  chytej(page, jmeno);
  await page.addInitScript(INIT_VIS);
  await page.goto(BASE + '/scene.html');
  await page.waitForFunction(() => window.StulKonf && typeof CATALOG !== 'undefined' && CATALOG.length > 0, null, { timeout: 240000 });
  await page.waitForTimeout(1200);
  await usad(page);
  if (skryta) await page.evaluate(() => { window.__vis = 'hidden'; document.dispatchEvent(new Event('visibilitychange')); });
  return page;
}

async function generator(ctx, bezBC, zablokovanaOkna) {
  const page = await ctx.newPage();
  chytej(page, 'generator');
  if (bezBC) await page.addInitScript(() => { delete window.BroadcastChannel; });
  if (zablokovanaOkna) await page.addInitScript(() => { window.open = () => null; });             // blokator oken: window.open vraci null
  await page.goto(BASE + '/stul-konfigurator.html');
  await page.waitForFunction(() => window.StulDoSceny && window.StulDoSceny.dotaz() && document.getElementById('sceneBtn'), null, { timeout: 240000 });
  await page.waitForTimeout(500);
  return page;
}

// klik na "Vlozit do Sceny" a cekani na KONCOVE hlaseni (ne "Hledam..." / "Vkladam..." / "Posilam...")
async function klik(gen, ocekavano) {
  const t0 = Date.now();
  await gen.evaluate(() => document.getElementById('sceneVlozitDoOtevrene').click());
  await gen.waitForFunction(() => { const t = document.getElementById('sceneStatus').textContent; return t && !/^(Hledám|Vkládám|Posílám)/.test(t); }, null, { timeout: 120000 });
  const st = await gen.evaluate(() => { const e = document.getElementById('sceneStatus'); const a = e.querySelector('a'); return { text: [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''), odkaz: a ? { href: a.getAttribute('href'), text: a.textContent, target: a.target } : null, barva: e.style.color }; });
  st.ms = Date.now() - t0;
  return st;
}
const stavScena = page => page.evaluate(() => ({ inserted: window.StulKonf.state.inserted, placed: placed.length, own: window.StulKonf.state.own.length, titul: document.title, id: window.StulKonf.sceneId }));

// zastupna karta Sceny (kazda ve vlastni strance stejneho puvodu): odpovida podle zadani, aniz by vkladala
async function falesna(ctx, jmeno, kod) {
  const page = await ctx.newPage();
  chytej(page, jmeno);
  await page.route(BASE + '/__falesna.html', r => r.fulfill({ contentType: 'text/html', body: '<!doctype html><title>falesna</title>' }));
  await page.goto(BASE + '/__falesna.html');
  await page.evaluate(kod);
  return page;
}

(async () => {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const novyKontext = () => browser.newContext({ viewport: { width: 1500, height: 900 } });
  let ctx, gen, pozn;

  // ---------------------------------------------------------------- 0) piny skriptu na strankach generatoru (md5-10 obsahu)
  console.log('\n## 0) piny');
  const md5 = f => crypto.createHash('md5').update(fs.readFileSync(path.join(WEB, f))).digest('hex').slice(0, 10);
  const piny = ['stul-konfigurator.html', 'stul-konfigurator-35.html', 'stul-konfigurator-40.html', 'stul-konfigurator-41.html', 'stul-konfigurator-45.html'].map(h => {
    const m = /\/js\/stul-do-sceny\.js\?v=([0-9a-f]{10})/.exec(fs.readFileSync(path.join(WEB, h), 'utf8')); return [h, m && m[1]]; });
  over('0.1 vsech 5 stranek generatoru stolu ma pin js/stul-do-sceny.js = md5-10 obsahu souboru (scripts/stul_verze.py)', piny.every(x => x[1] === md5('js/stul-do-sceny.js')), { ocekavano: md5('js/stul-do-sceny.js'), piny });

  // ---------------------------------------------------------------- A) primarni tlacitko: VZDY nova karta Sceny se stolem
  console.log('\n## A) tlacitko "Vlozit do Sceny" otevre novou Scenu se stolem');
  const STAV = gen => gen.evaluate(() => { const e = document.getElementById('sceneStatus'); const a = e.querySelector('a'); return { text: [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''), odkaz: a ? { href: a.getAttribute('href'), text: a.textContent } : null }; });
  ctx = await novyKontext(); gen = await generator(ctx);
  const qA = await gen.evaluate(() => window.StulDoSceny.dotaz());
  const [popup] = await Promise.all([gen.waitForEvent('popup', { timeout: 15000 }), gen.evaluate(() => document.getElementById('sceneBtn').click())]);
  chytej(popup, 'nova-scena'); await popup.addInitScript(INIT_VIS).catch(() => {});
  const u = new URL(popup.url());
  over('A.1 klik NEPOTREBUJE otevrenou Scenu: hned se otevre nova karta /scene.html?stul=<dotaz generatoru>', u.pathname === '/scene.html' && u.searchParams.get('stul') === qA, { url: popup.url().slice(0, 120) });
  await popup.waitForFunction(() => window.StulKonf && window.StulKonf.state && window.StulKonf.state.inserted, null, { timeout: 240000 });
  const pa = await popup.evaluate(() => ({ inserted: window.StulKonf.state.inserted, placed: placed.length, own: window.StulKonf.state.own.length }));
  over('A.2 nova Scena obsahuje stul cely (placed = own > 30)', pa.inserted && pa.placed === pa.own && pa.own > 30, pa);
  const sa0 = await STAV(gen);
  over('A.3 hlaseni "✔ Scena se stolem se otevrela v nove karte prohlizece." (bez odkazu)', sa0.text === '✔ Scéna se stolem se otevřela v nové kartě prohlížeče.' && !sa0.odkaz, sa0);
  over('A.4 pod hlasenim je maly odkaz "nebo vlozit do uz otevrene Sceny (vymeni jen dily stolu)"', await gen.evaluate(() => { const a = document.getElementById('sceneVlozitDoOtevrene'); return !!a && a.textContent === 'nebo vložit do už otevřené Scény (vymění jen díly stolu)' && a.closest('.mw-win-price') !== null; }));
  await ctx.close();
  // uz otevrena Scena (jina karta) se primarnim tlacitkem NEMENI - otevre se vzdy nova
  ctx = await novyKontext(); const S1 = await scena(ctx, 'ScenaA-stara'); gen = await generator(ctx);
  const [popup2] = await Promise.all([gen.waitForEvent('popup', { timeout: 15000 }), gen.evaluate(() => document.getElementById('sceneBtn').click())]);
  chytej(popup2, 'nova-scena-2');
  await popup2.waitForFunction(() => window.StulKonf && window.StulKonf.state && window.StulKonf.state.inserted, null, { timeout: 240000 });
  const s1 = await stavScena(S1);
  over('A.5 i kdyz uz je Scena otevrena, primarni tlacitko otevre NOVOU kartu se stolem a stara Scena zustane nedotcena', !s1.inserted && s1.placed === 0, s1);
  await ctx.close();
  // blokator oken
  ctx = await novyKontext(); gen = await generator(ctx, false, true);
  await gen.evaluate(() => document.getElementById('sceneBtn').click());
  const sb0 = await STAV(gen);
  over('A.6 prohlizec zablokoval nove okno: hlaseni + odkaz "Otevrit Scenu s timto stolem" (/scene.html?stul=...)', sb0.text === 'Prohlížeč zablokoval nové okno – otevři Scénu odkazem:' && sb0.odkaz && sb0.odkaz.text === 'Otevřít Scénu s tímto stolem' && sb0.odkaz.href.startsWith('/scene.html?stul='), sb0);
  await ctx.close();
  // stul SSE (system 41): tlacitko zakazane, zadny odkaz "vlozit do otevrene"
  ctx = await novyKontext(); const g41 = await ctx.newPage(); chytej(g41, 'generator41'); await g41.goto(BASE + '/stul-konfigurator-41.html');
  await g41.waitForFunction(() => document.getElementById('sceneBtn') && document.getElementById('sceneStatus').textContent, null, { timeout: 240000 });
  over('A.7 stul SSE (system 41): tlacitko zakazane, hlaseni "Stul SSE se do Sceny zatim nevklada" a ZADNY odkaz na vlozeni do otevrene Sceny', await g41.evaluate(() => document.getElementById('sceneBtn').disabled && /SSE se do Scény zatím nevkládá/.test(document.getElementById('sceneStatus').textContent) && !document.getElementById('sceneVlozitDoOtevrene')));
  await ctx.close();

  // ---------------------------------------------------------------- 1) zadna Scena
  console.log('\n## 1) (odkaz "vlozit do uz otevrene Sceny") zadna Scena neni otevrena');
  ctx = await novyKontext(); gen = await generator(ctx);
  let r = await klik(gen);
  const dotaz = await gen.evaluate(() => window.StulDoSceny.dotaz());
  over('1.1 hlaseni "Zadna Scena neni otevrena" + odkaz "Otevrit Scenu s timto stolem" (nova karta, /scene.html?stul=<dotaz generatoru>)', /^Žádná Scéna není otevřená/.test(r.text) && r.odkaz && r.odkaz.text === 'Otevřít Scénu s tímto stolem'
       && r.odkaz.href === '/scene.html?stul=' + encodeURIComponent(dotaz) && r.odkaz.target === '_blank', r);
  over('1.2 hlaseni po ~4 s (ping ceka nejvyse 2,5 s + puvodni protokol 1,5 s; pod zatezi ne dele nez ~9 s)', r.ms >= 3500 && r.ms < 9000, r.ms);
  await ctx.close();

  // ---------------------------------------------------------------- 2) jedna viditelna Scena: vlozeni (studena Scena trva > 1,5 s) a vymena
  console.log('\n## 2) jedna viditelna Scena');
  ctx = await novyKontext(); const A = await scena(ctx, 'ScenaA'); gen = await generator(ctx);
  r = await klik(gen);
  let sa = await stavScena(A);
  over('2.1 hlaseni "✔ Stul je vlozeny do Sceny." bez "jine karty", bez odkazu', r.text === '✔ Stůl je vložený do Scény.' && !r.odkaz, r);
  over('2.2 stul JE ve Scene: inserted, vsechny dily vlastni (placed = own > 30), titul karty bez ●', sa.inserted && sa.placed === sa.own && sa.own > 30 && !sa.titul.startsWith('●'), sa);
  over(`2.3 vkladani trvalo ${r.ms} ms: studena Scena nacita modely, hlaseni "Scena neni otevrena" se NEobjevilo (drive limit 1,5 s)`, r.ms > 900, r.ms);
  const pocet1 = sa.placed;
  r = await klik(gen);
  sa = await stavScena(A);
  over('2.4 druhy klik = VYMENA: "✔ Stul ve Sceni je vymeneny za tuto konfiguraci (ostatni obsah Sceny zustal)." a pocet dilu stejny (nic se nezdvojilo)', r.text === '✔ Stůl ve Scéně je vyměněný za tuto konfiguraci (ostatní obsah Scény zůstal).' && sa.placed === pocet1, { r, pocet1, placed: sa.placed });
  await gen.evaluate(() => document.getElementById('sceneVlozitDoOtevrene').click());                // dvojklik: druhy klik prebije prvni pozadavek
  await T(300);
  await gen.evaluate(() => document.getElementById('sceneVlozitDoOtevrene').click());
  await gen.waitForFunction(() => { const t = document.getElementById('sceneStatus').textContent; return t && !/^(Hledám|Vkládám|Posílám)/.test(t); }, null, { timeout: 120000 });
  await T(1500);
  const dv = await gen.evaluate(() => [...document.getElementById('sceneStatus').childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''));
  sa = await stavScena(A);
  over('2.5 dvojklik: vysledek je JEDNO hlaseni uspechu (prebite pozadavky neprepisou), stul ve Scene jednou (placed = own = ' + pocet1 + ', nic se nezdvojilo)', /^✔ Stůl/.test(dv) && sa.placed === pocet1 && sa.own === pocet1, { dv, pocet1, sa });
  await ctx.close();

  // ---------------------------------------------------------------- 3) dve Sceny: viditelna + skryta
  console.log('\n## 3) dve karty Sceny (viditelna a skryta)');
  ctx = await novyKontext(); const B = await scena(ctx, 'ScenaB-skryta', true); const A2 = await scena(ctx, 'ScenaA-viditelna'); gen = await generator(ctx);
  r = await klik(gen);
  const sb = await stavScena(B), sa2 = await stavScena(A2);
  over('3.1 stul je JEN ve viditelne Scene, skryta karta zustala nedotcena (nic nevlozeno, titul beze zmeny)', sa2.inserted && sa2.own > 30 && !sb.inserted && sb.placed === 0 && !sb.titul.startsWith('●'), { viditelna: sa2, skryta: sb });
  over('3.2 hlaseni rika, ze Scen je 2 a vlozilo se do viditelne', r.text === '✔ Stůl je vložený do Scény. Otevřených Scén je 2, vložilo se do viditelné.' && !r.odkaz, r);
  await ctx.close();

  // ---------------------------------------------------------------- 4) jen skryta Scena
  console.log('\n## 4) jen skryta karta Sceny (jina karta prohlizece)');
  ctx = await novyKontext(); const C = await scena(ctx, 'ScenaC-skryta', true); gen = await generator(ctx);
  r = await klik(gen);
  let sc = await stavScena(C);
  over('4.1 hlaseni "Je v JINE KARTE prohlizece - prepni se na ni (karta ma pred nazvem ●)" + odkaz "Otevrit novou Scenu s timto stolem"', r.text === '✔ Stůl je vložený do Scény. Je v JINÉ KARTĚ prohlížeče – přepni se na ni (karta má před názvem ●).'
       && r.odkaz && r.odkaz.text === 'Otevřít novou Scénu s tímto stolem' && r.odkaz.href.startsWith('/scene.html?stul='), r);
  over('4.2 stul je ve skryte Scene a karta ma pred nazvem "● "', sc.inserted && sc.own > 30 && sc.titul.startsWith('● '), sc);
  await C.evaluate(() => { window.__vis = 'visible'; document.dispatchEvent(new Event('visibilitychange')); });
  sc = await stavScena(C);
  over('4.3 po zobrazeni karty znacka zmizi (titul zpet bez ●)', !sc.titul.startsWith('●') && sc.titul.length > 5, sc);
  await ctx.close();

  // ---------------------------------------------------------------- 5) puvodni protokol (Scena ze starsi verze stranky)
  console.log('\n## 5) Scena ze starsi verze stranky (zna jen puvodni protokol)');
  for (const [ok, text] of [[true, '✔ Stůl je vložený do otevřené Scény (v jiné kartě prohlížeče – přepni se na ni).'], [false, 'Scéna stůl nepřijala (hlášení je v jejím panelu Generátor stolu).']]) {
    ctx = await novyKontext(); await falesna(ctx, 'stara', `(() => { const OK = ${ok}; const bc = new BroadcastChannel('stul-konfigurace'); bc.onmessage = ev => { const m = ev.data; if (m && m.type === 'vloz' && typeof m.query === 'string') bc.postMessage({ type: 'ack', ok: OK }); }; window.__bc = bc; })()`);
    gen = await generator(ctx);
    r = await klik(gen);
    over(`5.${ok ? 1 : 2} puvodni protokol, ack ok=${ok}: "${text}"`, r.text === text && (ok ? r.odkaz && r.odkaz.text === 'Otevřít novou Scénu s tímto stolem' : !r.odkaz), r);
    await ctx.close();
  }

  // pozdni odpoved: stara / vytizena Scena odpovi az po 1,5 s okne puvodniho protokolu -> hlaseni "Zadna Scena neni otevrena" se opravi
  ctx = await novyKontext(); await falesna(ctx, 'stara-pomala', `(() => { const bc = new BroadcastChannel('stul-konfigurace'); bc.onmessage = ev => { const m = ev.data; if (m && m.type === 'vloz' && typeof m.query === 'string') setTimeout(() => bc.postMessage({ type: 'ack', ok: true }), 3500); }; window.__bc = bc; })()`);
  gen = await generator(ctx);
  r = await klik(gen);
  over('5.3a pomala stara Scena: nejdriv hlaseni "Zadna Scena neni otevrena" (odpoved nestihla okno 1,5 s)', /^Žádná Scéna není otevřená/.test(r.text), r);
  await gen.waitForFunction(() => /^✔/.test([...document.getElementById('sceneStatus').childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('')), null, { timeout: 15000 }).catch(() => {});
  const po = await gen.evaluate(() => { const e = document.getElementById('sceneStatus'); const a = e.querySelector('a'); return { text: [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''), odkaz: a && a.textContent }; });
  over('5.3b pozdni odpoved hlaseni OPRAVI: "✔ Stul je vlozeny do otevrene Sceny (v jine karte prohlizece - prepni se na ni)." + odkaz na novou Scenu', po.text === '✔ Stůl je vložený do otevřené Scény (v jiné kartě prohlížeče – přepni se na ni).' && po.odkaz === 'Otevřít novou Scénu s tímto stolem', po);
  await ctx.close();

  // SKUTECNA stara Scena (prijemce z revize pred protokolem v2): prechodne obdobi - karty Sceny otevrene pred nasazenim ping neznaji
  let staryKod = null;
  try { staryKod = require('child_process').execFileSync('git', ['-C', REPO, 'show', STARA_REV + ':webapp/js/scene/stul-konfigurator.js'], { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024 }); } catch (e) { staryKod = null; }
  if (!staryKod) console.log('PRESKOCENO 5.5: git show ' + STARA_REV + ' nedostupne');
  else {
    ctx = await novyKontext();
    const S0 = await ctx.newPage(); chytej(S0, 'stara-scena'); await S0.addInitScript(INIT_VIS);
    await S0.route('**/js/scene/stul-konfigurator.js', r => r.fulfill({ contentType: 'text/javascript; charset=utf-8', body: staryKod }));
    await S0.goto(BASE + '/scene.html');
    await S0.waitForFunction(() => window.StulKonf && typeof CATALOG !== 'undefined' && CATALOG.length > 0, null, { timeout: 240000 });
    await S0.waitForTimeout(1200); await usad(S0);
    over('5.5a stary prijemce je skutecne nacteny (zadne window.StulKonf.sceneId)', await S0.evaluate(() => window.StulKonf.sceneId === undefined));
    gen = await generator(ctx);
    r = await klik(gen);
    await gen.waitForFunction(() => /^✔/.test([...document.getElementById('sceneStatus').childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('')), null, { timeout: 60000 }).catch(() => {});
    const ps = await gen.evaluate(() => { const e = document.getElementById('sceneStatus'); const a = e.querySelector('a'); return { text: [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''), odkaz: a && a.textContent }; });
    const so = await S0.evaluate(() => ({ inserted: window.StulKonf.state.inserted, placed: placed.length, own: window.StulKonf.state.own.length }));
    over('5.5b stara Scena (bez pongu) dostane stul puvodnim protokolem a generator hlasi "✔ ... v jine karte prohlizece" (i kdyz nejdriv "Zadna Scena", pokud odpovi az po 1,5 s)', ps.text === '✔ Stůl je vložený do otevřené Scény (v jiné kartě prohlížeče – přepni se na ni).' && ps.odkaz === 'Otevřít novou Scénu s tímto stolem', { prvni: r.text, ps });
    over('5.5c stul je ve stare Scene cely (placed = own > 30)', so.inserted && so.placed === so.own && so.own > 30, so);
    await ctx.close();
  }

  // vytizena Scena v2 (na ping odpovi az po 6 s, vlozeni potvrdi po 3,5 s zalozni cestou - verejny kanal s req): hlaseni "Zadna Scena neni otevrena" se opravi NOVYM textem (viditelnost)
  ctx = await novyKontext(); await falesna(ctx, 'v2-vytizena', `(() => { const id = 'fv2' + Math.random().toString(36).slice(2, 8); const bc = new BroadcastChannel('stul-konfigurace');
    bc.onmessage = ev => { const m = ev.data; if (!m) return; if (m.type === 'ping') setTimeout(() => bc.postMessage({ type: 'pong', req: m.req, id: id, viditelna: true, aktivni: Date.now() }), 6000);
      else if (m.type === 'vloz' && typeof m.req === 'string' && m.v === 2) setTimeout(() => bc.postMessage({ type: 'ack', req: m.req, ok: true, viditelna: true, vymena: false, zprava: '' }), 3500); };
    window.__bc = bc; })()`);
  gen = await generator(ctx);
  r = await klik(gen);
  over('5.4a vytizena Scena v2 (pong az po 6 s): generator nejdriv hlasi "Zadna Scena neni otevrena" a posle zalozni zpravu s req a v:2', /^Žádná Scéna není otevřená/.test(r.text), r);
  await gen.waitForFunction(() => /^✔/.test([...document.getElementById('sceneStatus').childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('')), null, { timeout: 15000 }).catch(() => {});
  const pv = await gen.evaluate(() => { const e = document.getElementById('sceneStatus'); return { text: [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(''), odkaz: !!e.querySelector('a') }; });
  over('5.4b pozdni ack Sceny v2 (verejny kanal, s req) hlaseni OPRAVI na "✔ Stul je vlozeny do Sceny." (viditelna Scena = bez odkazu); pozdni pong se neprecenuje', pv.text === '✔ Stůl je vložený do Scény.' && !pv.odkaz, pv);
  await ctx.close();

  // ---------------------------------------------------------------- 6) Scena protokolu v2 odpovi chybou / pomalu
  console.log('\n## 6) Scena odpovi chybou a pomalym vlozenim');
  const V2 = (ok, zprava, zpozdeniMs) => `(() => { const id = 'falesna' + Math.random().toString(36).slice(2, 8); const bc = new BroadcastChannel('stul-konfigurace'), pc = new BroadcastChannel('stul-konfigurace-' + id);
    bc.onmessage = ev => { const m = ev.data; if (m && m.type === 'ping') bc.postMessage({ type: 'pong', req: m.req, id: id, viditelna: true, aktivni: Date.now() }); };
    pc.onmessage = ev => { const m = ev.data; if (m && m.type === 'vloz') setTimeout(() => pc.postMessage({ type: 'ack', req: m.req, ok: ${ok}, viditelna: true, vymena: false, zprava: ${JSON.stringify(zprava)} }), ${zpozdeniMs}); };
    window.__bc = [bc, pc]; })()`;
  ctx = await novyKontext(); await falesna(ctx, 'v2-chyba', V2(false, 'Do Scény nejde vložit díl stolu, který katalog nezná: product_1.', 0)); gen = await generator(ctx);
  r = await klik(gen);
  over('6.1 Scena ohlasi chybu: generator ukaze jeji TEXT (panel Generator stolu bývá zavřený) + odkaz na novou Scenu', r.text === 'Scéna stůl nepřijala: Do Scény nejde vložit díl stolu, který katalog nezná: product_1.' && r.odkaz && r.odkaz.text === 'Otevřít novou Scénu s tímto stolem' && r.barva !== '', r);
  await ctx.close();
  ctx = await novyKontext(); await falesna(ctx, 'v2-pomala', V2(true, '', 3500)); gen = await generator(ctx);
  r = await klik(gen);
  over(`6.2 pomale vlozeni (3,5 s) se NEhlasi jako "Scena neni otevrena": "✔ Stul je vlozeny do Sceny." po ${r.ms} ms`, r.text === '✔ Stůl je vložený do Scény.' && r.ms >= 3500, r);
  await ctx.close();

  // ---------------------------------------------------------------- 7) skutecna chyba API + prohlizec bez BroadcastChannel
  console.log('\n## 7) skutecna chyba serveru, prohlizec bez BroadcastChannel');
  ctx = await novyKontext(); const D = await scena(ctx, 'ScenaD'); gen = await generator(ctx);
  await gen.evaluate(() => { window.StulHost.state.staff.vyrobni_list_url = '/x?sirka=999999&hloubka=800'; });
  r = await klik(gen);
  const sd = await stavScena(D);
  over('7.1 server odmitne konfiguraci: generator ukaze skutecny text chyby ze Sceny ("Scena stul nepřijala: Chyba: ..."), nic se nevlozilo', /^Scéna stůl nepřijala: Chyba: /.test(r.text) && !sd.inserted && sd.placed === 0, { r, sd });
  await ctx.close();
  ctx = await novyKontext(); gen = await generator(ctx, true);
  r = await klik(gen);
  over('7.2 prohlizec bez BroadcastChannel: puvodni hlaseni + odkaz na novou Scenu', r.text === 'Tento prohlížeč neumí poslat stůl do otevřené Scény.' && r.odkaz && r.odkaz.text === 'Otevřít Scénu s tímto stolem', r);
  await ctx.close();

  over('8 bez chyb ve strankach a v konzoli, bez neocekavanych dialogu', chyby.length === 0 && dialogy.length === 0, { chyby: chyby.slice(0, 5), dialogy });
  console.log('\n%d/%d OK', vysl.filter(Boolean).length, vysl.length);
  await browser.close();
  process.exit(vysl.every(Boolean) ? 0 : 1);
})().catch(e => { console.error('SELHALO', e); process.exit(1); });
