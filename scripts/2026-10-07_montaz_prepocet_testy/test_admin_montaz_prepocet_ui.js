// Admin -> Obecne -> Montaz: tlacitka "Ulozit a prepocitat vse" u tri sazeb (bot16, 2026-10-07; Robert: "chci u tech tlacitek za montaze mit nejen ulozit ale prepocitat vse, aby se vsechny karty prekalkulovaly").
// SKUTECNY webapp/admin.html + vsechny webapp/admin/js/*.js v Chromiu proti falesnemu serveru (page.route, zadna sit ani DB). API: GET /api/admin/settings -> montaz_prepocet (priznak, ze server prepocet umi),
// GET /api/admin/montaz/prepocet (nahled), POST (provedeni), PUT /api/admin/settings, GET/PUT /api/stul/montaz.
// Kandidat pred nasazenim: ADMIN_HTML=... CENY_JS=... node test_admin_montaz_prepocet_ui.js   (puvodni verze MUSI selhat)   SNIMKY=<slozka> ulozi obrazek
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = { 'ceny.js': process.env.CENY_JS };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const QUILL_ATRAPA = `window.Quill = function Quill() {}; Quill.__icons = {}; Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; }; Quill.register = function () {};`;
const SAZBY = (process.env.SNIMEK_SAZBY || '10,14,12').split(',').map(Number);
const norm = t => String(t || '').replace(/[\s  ]+/g, ' ').trim();

const NAHLED = { pct: 10, sestav_auto: 530, ke_zmene: 530, bez_zmeny: 0, preskoceno_bez_ceny: 0, preskoceno_rozbita_data: 0,
                 ukazky: [{ id: 57, nazev: 'Regálová vestavba – Ford Connect L1', kod: 'A-57', total_czk: 25904, montaz_stara_czk: 5181, montaz_nova_czk: 2590, pct_stara: 20 },
                          { id: 58, nazev: 'Regálová vestavba – Citroen Jumpy L2', kod: 'A-58', total_czk: 11827, montaz_stara_czk: 2365, montaz_nova_czk: 1183, pct_stara: 20 }] };

async function otevri(scenar = {}) {
  const stav = { volani: [], dialogy: [] };
  const chyby = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', async d => { stav.dialogy.push(d.message()); if (scenar.potvrdit === false) await d.dismiss(); else await d.accept(); });
  await page.route('**/*', async route => {
    const req = route.request(), u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) { const cesta = PREPIS[mJs[1]] || path.join(JS_DIR, mJs[1]); if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'x' }); return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') }); }
    if (p === '/api/auth/me') return json(200, { user: { id: 1, role: 'admin', name: 'Test Admin', email: 'test@lokalni', theme_admin: 'dark', permissions: {} } });
    if (p === '/api/admin/field-labels') return json(200, { labels: {}, options: {} });
    if (p === '/api/admin/settings' && m === 'GET') return json(200, Object.assign({ montaz_pct: SAZBY[0], vandrawee_montaz_pct: SAZBY[1], joint_price_czk: 1, profile_flat_fee_czk: 2, packaging_pct: 3, scene_price_coefficient: 1.2, cart_enabled: true, discount_codes_enabled: true }, scenar.priznak === false ? {} : { montaz_prepocet: true }));
    if (p === '/api/admin/settings' && m === 'PUT') { stav.volani.push(['PUT settings', JSON.parse(req.postData() || '{}')]); return scenar.putChyba ? json(400, { error: 'Montáž musí být číslo.' }) : json(200, { status: 'ok' }); }
    if (p === '/api/stul/montaz' && m === 'GET') return scenar.stulGetStatus ? json(scenar.stulGetStatus, { error: 'x' }) : json(200, { pct: SAZBY[2], default: 12, available: true, stored: true });
    if (p === '/api/stul/montaz' && m === 'PUT') { const b = JSON.parse(req.postData() || '{}'); stav.volani.push(['PUT stul', b]); return json(200, { pct: b.pct, default: 12, available: true, stored: true }); }
    if (p === '/api/admin/montaz/prepocet' && m === 'GET') { stav.volani.push(['GET nahled']); if (scenar.nahledStatus) return json(scenar.nahledStatus, { error: 'montaz_pct_invalid', message: 'Sazba montáže vestaveb (Obecné → Montáž) není číslo 0 až 100 - nejdřív ji ulož.' }); return json(200, scenar.nahled || NAHLED); }
    if (p === '/api/admin/montaz/prepocet' && m === 'POST') { stav.volani.push(['POST prepocet']); if (scenar.postStatus) return json(scenar.postStatus, { error: 'x', message: 'Chyba serveru při přepočtu.' }); return json(200, { pct: 10, zmeneno: scenar.postZmeneno != null ? scenar.postZmeneno : 530, sestav_auto: 530, bez_zmeny: 0, preskoceno_bez_ceny: 0, preskoceno_rozbita_data: 0 }); }
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://admin.test/admin.html');
  try { await page.waitForFunction(() => typeof loadJointPrice === 'function' && document.getElementById('montazPctInput'), null, { timeout: 15000 }); }
  catch (e) { console.log('FAIL admin se nenacetl: ' + e.message.split('\n')[0] + ' | chyby: ' + chyby.slice(0, 3).join(' | ')); process.exit(1); }
  await page.waitForTimeout(700);
  await page.evaluate(() => { const b = [...document.querySelectorAll('[data-tab="settings"]')].find(x => x.offsetParent !== null) || document.querySelector('[data-tab="settings"]'); if (b) b.click(); });
  await page.waitForTimeout(500);
  return { browser, page, stav, chyby };
}
const BTN = { v1: '#btnSaveMontazPctPrepocet' };
const ULOZIT = { v2: '#btnSaveVandraweeMontazPct', stol: '#btnSaveStulMontazPct' };
const STAT = { v1: 'montazPctStatus', v2: 'vandraweeMontazPctStatus', stol: 'stulMontazPctStatus' };
const stat = (page, k) => page.evaluate(i => (document.getElementById(i) || {}).textContent, STAT[k]);
const viditelne = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); return !!(e && e.offsetParent !== null && !e.hidden); }, sel);

(async () => {
  // ---- A) starsi server (bez priznaku montaz_prepocet): tlacitka a vysvetleni skryta, Ulozit funguje, zadne volani prepoctu
  let { browser, page, stav, chyby } = await otevri({ priznak: false });
  over('A1 server bez priznaku montaz_prepocet: tlacitko "Ulozit a prepocitat vse" i vysvetleni pod kartami jsou SKRYTA', !(await viditelne(page, BTN.v1)) && !(await viditelne(page, '#montazPrepocetHint')), null);
  await page.fill('#montazPctInput', '12'); await page.click('#btnSaveMontazPct'); await page.waitForTimeout(300);
  over('A2 obycejne Ulozit funguje beze zmeny (PUT montaz_pct) a nevola zadny prepocet', JSON.stringify(stav.volani) === JSON.stringify([['PUT settings', { montaz_pct: 12 }]]), stav.volani);
  over('A3 bez neodchycenych JS chyb', chyby.length === 0, chyby);
  await browser.close();

  // ---- B) server s prepoctem: tlacitka viditelna, tok Ulozit -> nahled -> potvrzeni -> POST
  ({ browser, page, stav, chyby } = await otevri());
  over('B1 tlacitko "Ulozit a prepocitat vse" je viditelne JEN u "Vestavby - 1. vetev" (u Vandr a stolu neexistuje) a pod kartami je vysvetleni', (await viditelne(page, BTN.v1)) && (await page.locator('.montaz-prepocet-btn').count()) === 1 && (await page.locator('#btnSaveVandraweeMontazPctPrepocet, #btnSaveStulMontazPctPrepocet').count()) === 0 && (await viditelne(page, '#montazPrepocetHint')), await page.locator('.montaz-prepocet-btn').count());
  const text = await page.evaluate(() => document.getElementById('montazPrepocetHint').textContent.replace(/\s+/g, ' '));
  over('B2 vysvetleni rika: tlacitko je jen u 1. vetve, prepocita ulozenou montaz karet vestaveb (AUTO), ukaze se pocet a priklady a musi se potvrdit, Vandr a stoly se pocitaji zive', /je jen u sazby „Vestavby – 1\. větev“/.test(text) && /uloženou/.test(text) && /sestavy typu AUTO/.test(text) && /je nutné potvrdit/.test(text) && /Karty Vandr a stoly počítají montáž živě/.test(text), text);
  if (process.env.SNIMKY) {
    const box = await page.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => /^Montáž – výchozí sazby/.test(x.textContent.trim())); h.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); const a = h.getBoundingClientRect(), b = document.getElementById('montazPrepocetHint').getBoundingClientRect(); return { x: Math.max(0, a.left - 16), y: Math.max(0, a.top - 8), width: 1260, height: b.bottom - a.top + 16 }; });
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(process.env.SNIMKY, 'admin_montaz_prepocet.png'), clip: box });
  }
  await page.fill('#montazPctInput', '11'); await page.click(BTN.v1); await page.waitForTimeout(500);
  over('B3 poradi volani: PUT ulozeni sazby -> GET nahled -> (potvrzeni) -> POST prepocet', JSON.stringify(stav.volani.map(v => v[0])) === JSON.stringify(['PUT settings', 'GET nahled', 'POST prepocet']) && stav.volani[0][1].montaz_pct === 11, stav.volani);
  const dlg = norm(stav.dialogy[0]);
  over('B4 potvrzovaci okno: pocet karet (530 z 530), sazba, priklady "stara -> nova castka" a poznamka, ze objednavky a ceny bez montaze se nemeni', /Přepočítat montáž u 530 z 530 karet vestaveb podle sazby 10 % \(Vestavby – 1\. větev\)/.test(dlg) && /Regálová vestavba – Ford Connect L1: 5 181 → 2 590 Kč/.test(dlg) && /Citroen Jumpy L2: 2 365 → 1 183 Kč/.test(dlg) && /Ceny karet bez montáže se nemění, stejně jako už odeslané objednávky\./.test(dlg), dlg);
  over('B5 vysledek: "ulozeno a prepocitano: montaz zmenena u 530 karet vestaveb (sazba 10 %)"', /uloženo ✓ a přepočítáno: montáž změněna u 530 karet vestaveb \(sazba 1\. větve 10 %\)/.test(await stat(page, 'v1')), await stat(page, 'v1'));
  over('B6 bez neodchycenych JS chyb', chyby.length === 0, chyby);
  await browser.close();

  // ---- C) zruseni potvrzeni, nic ke zmene, chyby
  ({ browser, page, stav, chyby } = await otevri({ potvrdit: false }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C1 potvrzeni zruseno: sazba ulozena, nahled nacten, ZADNY POST, stav rika "prepocet karet zrusen"', JSON.stringify(stav.volani.map(v => v[0])) === JSON.stringify(['PUT settings', 'GET nahled']) && /přepočet karet zrušen/.test(await stat(page, 'v1')), [stav.volani.map(v => v[0]), await stat(page, 'v1')]);
  await browser.close();
  ({ browser, page, stav, chyby } = await otevri({ nahled: Object.assign({}, NAHLED, { ke_zmene: 0, ukazky: [], bez_zmeny: 530 }) }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C2 karty uz maji aktualni montaz (ke zmene 0): bez potvrzovaciho okna a bez POST, stav to rekne', stav.dialogy.length === 0 && !stav.volani.some(v => v[0] === 'POST prepocet') && /už mají aktuální montáž \(10 %\), není co přepočítávat/.test(await stat(page, 'v1')), [stav.dialogy, stav.volani.map(v => v[0]), await stat(page, 'v1')]);
  await browser.close();
  ({ browser, page, stav, chyby } = await otevri({ putChyba: true }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C3 ulozeni sazby selhalo (server 400): chyba se ukaze, prepocet se NESPUSTI (zadny nahled, zadny POST)', JSON.stringify(stav.volani.map(v => v[0])) === JSON.stringify(['PUT settings']) && /chyba: Montáž musí být číslo/.test(await stat(page, 'v1')), [stav.volani.map(v => v[0]), await stat(page, 'v1')]);
  await browser.close();
  ({ browser, page, stav, chyby } = await otevri({ nahledStatus: 409 }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C4 nahled vratil 409 (neplatna sazba): "ulozeno, ale prepocet karet selhal" se zpravou serveru, zadny POST, zadna JS chyba', !stav.volani.some(v => v[0] === 'POST prepocet') && /uloženo, ale přepočet karet selhal: Sazba montáže vestaveb/.test(await stat(page, 'v1')) && chyby.length === 0, [await stat(page, 'v1'), chyby]);
  await browser.close();
  ({ browser, page, stav, chyby } = await otevri({ postStatus: 500 }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C5 POST prepoctu selhal (500): stav ukaze "ulozeno, ale prepocet karet selhal" se zpravou serveru', /uloženo, ale přepočet karet selhal: Chyba serveru při přepočtu/.test(await stat(page, 'v1')) && chyby.length === 0, [await stat(page, 'v1'), chyby]);
  await browser.close();

  // ---- C6) skloňování: 1 karta ("u 1 z 1 karty", "u 1 karty") vs. vice ("u 2 z 5 karet")
  ({ browser, page, stav, chyby } = await otevri({ nahled: Object.assign({}, NAHLED, { ke_zmene: 1, sestav_auto: 1, ukazky: NAHLED.ukazky.slice(0, 1) }), postZmeneno: 1 }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C6 jedna karta: potvrzeni "u 1 z 1 karty vestaveb", vysledek "montaz zmenena u 1 karty vestaveb"', /Přepočítat montáž u 1 z 1 karty vestaveb/.test(norm(stav.dialogy[0])) && /změněna u 1 karty vestaveb/.test(await stat(page, 'v1')), [norm(stav.dialogy[0]), await stat(page, 'v1')]);
  await browser.close();
  ({ browser, page, stav, chyby } = await otevri({ nahled: Object.assign({}, NAHLED, { ke_zmene: 2, sestav_auto: 5 }), postZmeneno: 2 }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('C7 vice karet: potvrzeni "u 2 z 5 karet vestaveb", vysledek "u 2 karet vestaveb"', /Přepočítat montáž u 2 z 5 karet vestaveb/.test(norm(stav.dialogy[0])) && /změněna u 2 karet vestaveb/.test(await stat(page, 'v1')), [norm(stav.dialogy[0]), await stat(page, 'v1')]);
  await browser.close();

  // ---- D) Vandr a stoly: JEN Ulozit (Robert 2026-10-07 23:05: tlacitko u stolu nesmi prepocitavat vestavby) - ulozi SVOJI sazbu SVYM endpointem a NIC nepocita; rozepsana neulozena hodnota 1. vetve se nepouzije
  ({ browser, page, stav, chyby } = await otevri());
  await page.fill('#vandraweeMontazPctInput', '15'); await page.click(ULOZIT.v2); await page.waitForTimeout(400);
  over('D1 Vandr: Ulozit = PUT vandrawee_montaz_pct 15 (jediny klic) a ZADNY nahled ani prepocet vestaveb', JSON.stringify(stav.volani) === JSON.stringify([['PUT settings', { vandrawee_montaz_pct: 15 }]]), stav.volani);
  stav.volani.length = 0;
  await page.fill('#stulMontazPctInput', '13'); await page.click(ULOZIT.stol); await page.waitForTimeout(400);
  over('D2 stoly: Ulozit = PUT /api/stul/montaz {pct: 13} (stavajici API) a ZADNY nahled ani prepocet vestaveb', JSON.stringify(stav.volani) === JSON.stringify([['PUT stul', { pct: 13 }]]), stav.volani);
  stav.volani.length = 0;
  await page.fill('#montazPctInput', '15'); await page.fill('#stulMontazPctInput', '8'); await page.click(ULOZIT.stol); await page.waitForTimeout(400);
  over('D3 REGRESE (Robertuv snimek 23:04): rozepsana neulozena sazba 1. vetve (15) + klik na Ulozit u stolu (8) => ulozi se jen sazba stolu, vestavby se neprepocitaji a sazba 1. vetve se NEulozi', JSON.stringify(stav.volani) === JSON.stringify([['PUT stul', { pct: 8 }]]) && stav.dialogy.length === 0, [stav.volani, stav.dialogy]);
  stav.volani.length = 0;
  await page.fill('#stulMontazPctInput', '999'); await page.click(ULOZIT.stol); await page.waitForTimeout(300);
  over('D4 stoly s neplatnou hodnotou (999): nic se neposle', stav.volani.length === 0 && /zadej číslo od 0 do 100/.test(await stat(page, 'stol')), [stav.volani, await stat(page, 'stol')]);
  over('D5 bez neodchycenych JS chyb', chyby.length === 0, chyby);
  await browser.close();
  // ---- E) sazba stolu se nenacetla: zakazano i tlacitko prepoctu stolu; ostatni funguji
  ({ browser, page, stav, chyby } = await otevri({ stulGetStatus: 403 }));
  const dis = await page.evaluate(() => ({ ulozit: document.getElementById('btnSaveStulMontazPct').disabled && document.getElementById('stulMontazPctInput').disabled }));
  await page.click(BTN.v1); await page.waitForTimeout(450);
  over('E sazba stolu se nenacetla (403): pole i Ulozit u stolu zakazane s hlaskou "sazbu stolu se nepodarilo nacist", tlacitko prepoctu vestaveb funguje dal', dis.ulozit && /sazbu stolů se nepodařilo načíst/.test(await stat(page, 'stol')) && stav.volani.some(v => v[0] === 'POST prepocet') && chyby.length === 0, [dis, stav.volani.map(v => v[0]), chyby]);
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK admin - Ulozit a prepocitat vse (montaz): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
