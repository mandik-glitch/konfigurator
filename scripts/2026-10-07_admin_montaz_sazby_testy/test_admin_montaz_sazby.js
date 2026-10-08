// Admin -> Obecne -> Montaz: VSECHNY TRI sazby montaze u sebe s popisky, kde plati (bot16, 2026-10-07; Robert pres bot9: "v adminu v Obecne -> Montaz ma byt vsech 3 sazeb montaze u sebe s popisky,
// kde plati": (1) vestavby do vozidel = app_settings montaz_pct, (2) stoly z generatoru = stul_montaz_pct pres STAVAJICI API GET/PUT /api/stul/montaz (zadny druhy zdroj pravdy), (3) karty vanDrawee).
// SKUTECNY webapp/admin.html + vsechny webapp/admin/js/*.js v Chromiu proti falesnemu serveru (page.route, zadna sit ani DB).
// Kandidat pred nasazenim: ADMIN_HTML=... CENY_JS=... node test_admin_montaz_sazby.js   (puvodni verze MUSI selhat)   SNIMKY=<slozka> ulozi obrazek sekce
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = { 'ceny.js': process.env.CENY_JS };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const QUILL_ATRAPA = `
  window.Quill = function Quill() {};
  Quill.__icons = {};
  Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; };
  Quill.register = function () {};
`;

async function otevri(scenar = {}) {
  const stav = { settingsPut: [], stulPut: [], stulGet: 0, settingsGet: 0 };
  const chyby = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', d => d.accept());
  await page.route('**/*', async route => {
    const req = route.request(), u = new URL(req.url());
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();
    const p = u.pathname, m = req.method();
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) {
      const cesta = PREPIS[mJs[1]] || path.join(JS_DIR, mJs[1]);
      if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'nenalezeno' });
      return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') });
    }
    if (p === '/api/auth/me') return json(200, { user: { id: 1, role: 'admin', name: 'Test Admin', email: 'test@lokalni', theme_admin: 'dark', permissions: {} } });
    if (p === '/api/admin/field-labels') return json(200, { labels: {}, options: {} });
    if (p === '/api/admin/settings' && m === 'GET') { stav.settingsGet++; return json(200, { montaz_pct: 10, vandrawee_montaz_pct: 14, joint_price_czk: 1, profile_flat_fee_czk: 2, packaging_pct: 3, scene_price_coefficient: 1.2, cart_enabled: true, discount_codes_enabled: true }); }
    if (p === '/api/admin/settings' && m === 'PUT') { stav.settingsPut.push(JSON.parse(req.postData() || '{}')); return json(scenar.settingsPutStatus || 200, scenar.settingsPutStatus ? { error: 'x' } : { status: 'ok' }); }
    if (p === '/api/stul/montaz' && m === 'GET') {
      stav.stulGet++;
      if (scenar.stulGetStatus) return json(scenar.stulGetStatus, { error: 'x' });
      return json(200, { pct: scenar.stulPct != null ? scenar.stulPct : 12, default: 12, available: true, stored: scenar.stulStored !== false });
    }
    if (p === '/api/stul/montaz' && m === 'PUT') {
      const b = JSON.parse(req.postData() || '{}'); stav.stulPut.push(b);
      if (scenar.stulPutStatus === 403) return json(403, { error: 'forbidden' });
      if (scenar.stulPutStatus === 400) return json(400, { error: 'pct_invalid', message: 'Sazba montáže musí být číslo 0 až 100 (0 = montáž se nenabízí).' });
      if (scenar.stulPutAbort) return route.abort();
      return json(200, { pct: Math.round(b.pct * 100) / 100, default: 12, available: b.pct > 0, stored: true });
    }
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
const hodnoty = page => page.evaluate(() => ({ vozidla: document.getElementById('montazPctInput').value, stoly: document.getElementById('stulMontazPctInput') && document.getElementById('stulMontazPctInput').value, vandr: document.getElementById('vandraweeMontazPctInput').value }));
const stat = (page, id) => page.evaluate(i => (document.getElementById(i) || {}).textContent, id);

(async () => {
  // ---- A) rozlozeni: tri sazby VEDLE SEBE (Robert: "mit vedle sebe v adminu"), jeho nazvy, popisky "Plati pro" pod polem
  let { browser, page, stav, chyby } = await otevri();
  const A = await page.evaluate(() => {
    const ids = ['montazPctInput', 'vandraweeMontazPctInput', 'stulMontazPctInput'], els = ids.map(i => document.getElementById(i));
    if (els.some(e => !e)) return { chybi: ids.filter((i, k) => !els[k]) };
    const r = els.map(e => e.getBoundingClientRect());
    const h3 = [...document.querySelectorAll('h3')].filter(h => /^Montáž/.test(h.textContent.trim()));
    const karta = e => { const k = e.closest('.montaz-sazba'); if (!k) return null; const hint = k.querySelector('p.hint'), form = k.querySelector('.add-form');
      return { nadpis: (k.querySelector('h4') || {}).textContent, popis: hint ? hint.textContent.replace(/\s+/g, ' ').trim() : null, popisPodPolem: !!(hint && form && hint.getBoundingClientRect().top >= e.getBoundingClientRect().bottom - 1), tlacitka: k.querySelectorAll('button').length, sirka: Math.round(k.getBoundingClientRect().width) }; };
    return { naRadku: Math.max(...r.map(x => x.top)) - Math.min(...r.map(x => x.top)) < 6, zleva: r[0].left < r[1].left && r[1].left < r[2].left, viditelne: els.every(e => e.offsetParent !== null), h3: h3.map(h => h.textContent.trim()),
             karty: els.map(karta), stareH3: [...document.querySelectorAll('h3')].map(h => h.textContent.trim()).filter(t => t === 'Montáž' || t === 'Montáž u vanDrawee karet') };
  });
  over('A1 tri sazby montaze jsou v Obecne VEDLE SEBE na jednom radku, zleva: Vestavby 1. vetev, Vestavby 2. vetev (Vandr), Stoly z generatoru', A.naRadku && A.zleva && A.viditelne, A);
  over('A2 jeden spolecny nadpis "Montaz - vychozi sazby" a zadny z puvodnich dvou samostatnych nadpisu "Montaz" / "Montaz u vanDrawee karet"', A.h3 && A.h3.length === 1 && /výchozí sazby/.test(A.h3[0]) && A.stareH3.length === 0, [A.h3, A.stareH3]);
  over('A3 nazvy podle Roberta: "Vestavby - 1. vetev", "Vestavby - 2. vetev (Vandr)", "Stoly z generatoru"', A.karty && A.karty.map(b => b && b.nadpis).join('|') === 'Vestavby – 1. větev|Vestavby – 2. větev (Vandr)|Stoly z generátoru', A.karty);
  over('A4 pod kazdym polem je popisek "Plati pro: ..." (1: sestavy typu AUTO a nepl. pro vanDrawee/stoly; 2: karty vanDrawee, prazdne = 20 %; 3: stoly z Generatoru stolu)', A.karty && A.karty.every(b => b && b.popisPodPolem && /^Platí pro:/.test(b.popis)) && /AUTO/.test(A.karty[0].popis) && /Neplatí pro karty Vandr ani pro stoly/.test(A.karty[0].popis) && /vanDrawee/.test(A.karty[1].popis) && /20 %/.test(A.karty[1].popis) && /Generátoru stolu/.test(A.karty[2].popis), A.karty && A.karty.map(b => b && b.popis));
  over('A5 kazda sazba ma vlastni tlacitko Ulozit, JEN 1. vetev navic skryte tlacitko Ulozit a prepocitat vse (viz test_admin_montaz_prepocet_ui.js), a kartu sirokou aspon 240 px', A.karty && A.karty.every((b, i) => b && b.tlacitka === (i === 0 ? 2 : 1) && b.sirka >= 240), A.karty);
  await page.setViewportSize({ width: 640, height: 900 }); await page.waitForTimeout(300);
  const A6 = await page.evaluate(() => { const c = document.getElementById('montazSazby'), t = ['montazPctInput', 'vandraweeMontazPctInput', 'stulMontazPctInput'].map(i => Math.round(document.getElementById(i).getBoundingClientRect().top)); return { preteka: c.scrollWidth > c.clientWidth + 1, zalamuje: t[2] > t[0] + 20, t }; });
  over('A6 na uzkem okne (640 px) se karty zalomi do dalsiho radku a nic nepreteka', A6.zalamuje && !A6.preteka, A6);
  await page.setViewportSize({ width: 1400, height: 1000 }); await page.waitForTimeout(300);

  // ---- B) nactene hodnoty (montaz_pct 10, stoly 12, vanDrawee 14) + stav "nenastaveno"
  const B = await hodnoty(page);
  over('B1 pole ukazuji nactene hodnoty: vestavby 10, stoly 12 (z GET /api/stul/montaz), vanDrawee 14', B.vozidla === '10' && B.stoly === '12' && B.vandr === '14', B);
  over('B2 pole sazby stolu je po nacteni povolene a hodnota stolu se cetla ze stavajiciho API (GET /api/stul/montaz)', await page.evaluate(() => !document.getElementById('stulMontazPctInput').disabled && !document.getElementById('btnSaveStulMontazPct').disabled) && stav.stulGet >= 1, stav.stulGet);
  if (process.env.SNIMKY) {
    await page.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => /^Montáž – výchozí sazby/.test(x.textContent.trim())); h.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); });
    await page.waitForTimeout(400);
    const box = await page.evaluate(() => { const h = [...document.querySelectorAll('h3')].find(x => /^Montáž – výchozí sazby/.test(x.textContent.trim())); const last = document.getElementById('montazSazby'); const a = h.getBoundingClientRect(), b = last.getBoundingClientRect(); return { x: Math.max(0, a.left - 16), y: Math.max(0, a.top - 8), width: Math.min(innerWidth - Math.max(0, a.left - 16), 1260), height: b.bottom - a.top + 16 }; });
    await page.screenshot({ path: path.join(process.env.SNIMKY, 'admin_montaz_sazby.png'), clip: box });
  }

  // ---- C) ukladani: kazda sazba jde na SVUJ endpoint, jen svuj klic
  await page.fill('#montazPctInput', '11.5'); await page.click('#btnSaveMontazPct'); await page.waitForTimeout(250);
  await page.fill('#vandraweeMontazPctInput', '15'); await page.click('#btnSaveVandraweeMontazPct'); await page.waitForTimeout(250);
  await page.fill('#stulMontazPctInput', '13'); await page.click('#btnSaveStulMontazPct'); await page.waitForTimeout(350);
  over('C1 Ulozit u vestaveb do vozidel: PUT /api/admin/settings s JEDINYM klicem montaz_pct = 11.5', JSON.stringify(stav.settingsPut[0]) === JSON.stringify({ montaz_pct: 11.5 }), stav.settingsPut);
  over('C2 Ulozit u karet vanDrawee: PUT /api/admin/settings s JEDINYM klicem vandrawee_montaz_pct = 15', JSON.stringify(stav.settingsPut[1]) === JSON.stringify({ vandrawee_montaz_pct: 15 }), stav.settingsPut);
  over('C3 Ulozit u stolu: PUT /api/stul/montaz {pct: 13} (stavajici API), NEJDE do /api/admin/settings (zadny druhy zdroj pravdy, klic stul_montaz_pct se tam neposila)', stav.stulPut.length === 1 && stav.stulPut[0].pct === 13 && stav.settingsPut.length === 2 && !stav.settingsPut.some(b => 'stul_montaz_pct' in b), [stav.stulPut, stav.settingsPut]);
  over('C4 po ulozeni stolu stav "ulozeno" a pole ukazuje odpoved serveru', /uloženo ✓/.test(await stat(page, 'stulMontazPctStatus')) && (await hodnoty(page)).stoly === '13', [await stat(page, 'stulMontazPctStatus'), await hodnoty(page)]);

  // ---- D) validace stolu: neplatne hodnoty se NEPOSILAJI; 0 a carka ano
  const putsPred = stav.stulPut.length;
  // pole je type=number: nevalidni text prohlizec zahodi (value = ''), cisla mimo rozsah / s tremi desetinnymi misty se nastavuji primo
  for (const v of ['abc', '101', '-1', '', '12.345']) { await page.evaluate(x => { document.getElementById('stulMontazPctInput').value = x; }, v); await page.click('#btnSaveStulMontazPct'); await page.waitForTimeout(120); }
  over('D1 neplatne hodnoty (text, 101, -1, prazdne, 3 desetinna mista) se neodeslou a ukaze se vysvetleni', stav.stulPut.length === putsPred && /zadej číslo od 0 do 100/.test(await stat(page, 'stulMontazPctStatus')), [stav.stulPut.length - putsPred, await stat(page, 'stulMontazPctStatus')]);
  await page.fill('#stulMontazPctInput', '12.5'); await page.click('#btnSaveStulMontazPct'); await page.waitForTimeout(250);
  over('D2 desetinne cislo "12.5" se posle jako 12.5', stav.stulPut[stav.stulPut.length - 1].pct === 12.5, stav.stulPut);
  await page.fill('#stulMontazPctInput', '0'); await page.click('#btnSaveStulMontazPct'); await page.waitForTimeout(250);
  over('D3 nula se posle (montaz se u stolu nenabizi) a stav to rekne', stav.stulPut[stav.stulPut.length - 1].pct === 0 && /nenabízí/.test(await stat(page, 'stulMontazPctStatus')), [stav.stulPut, await stat(page, 'stulMontazPctStatus')]);
  over('D4 bez neodchycenych JS chyb (hlavni scenar)', chyby.length === 0, chyby);
  await browser.close();

  // ---- E) chyby serveru pri ulozeni stolu
  for (const [nazev, scen, ocek] of [['403 bez opravneni', { stulPutStatus: 403 }, /nemáš oprávnění/], ['400 neplatna hodnota (zprava ze serveru)', { stulPutStatus: 400 }, /Sazba montáže musí být číslo/], ['spojeni selhalo', { stulPutAbort: true }, /chyba:/]]) {
    ({ browser, page, stav, chyby } = await otevri(scen));
    await page.fill('#stulMontazPctInput', '20'); await page.click('#btnSaveStulMontazPct'); await page.waitForTimeout(400);
    const st = await stat(page, 'stulMontazPctStatus');
    over(`E ${nazev}: stav ukaze chybu a nic nespadne`, ocek.test(st) && chyby.length === 0, [st, chyby]);
    await browser.close();
  }

  // ---- F) sazba stolu se nenacetla (starsi server / bez prava): pole zakazane + vysvetleni; ostatni dve sazby funguji dal
  for (const kod of [403, 404, 500]) {
    ({ browser, page, stav, chyby } = await otevri({ stulGetStatus: kod }));
    const F = await page.evaluate(() => ({ dis: document.getElementById('stulMontazPctInput').disabled && document.getElementById('btnSaveStulMontazPct').disabled, st: document.getElementById('stulMontazPctStatus').textContent }));
    const h = await hodnoty(page);
    await page.fill('#montazPctInput', '9'); await page.click('#btnSaveMontazPct'); await page.waitForTimeout(250);
    over(`F GET /api/stul/montaz = ${kod}: pole stolu zakazane s vysvetlenim, vestavby a vanDrawee dal nactene a ulozitelne`, F.dis && /nepodařilo načíst/.test(F.st) && h.vozidla === '10' && h.vandr === '14' && stav.settingsPut.length === 1 && stav.settingsPut[0].montaz_pct === 9 && chyby.length === 0, [F, h, stav.settingsPut, chyby]);
    await browser.close();
  }
  // ---- G) nenastaveno: vychozi sazba je ukazana
  ({ browser, page, stav, chyby } = await otevri({ stulStored: false }));
  over('G stul bez ulozene hodnoty: pole ukazuje vychozi 12 a stav rika "zatim nenastaveno - plati vychozi 12 %"', (await hodnoty(page)).stoly === '12' && /zatím nenastaveno - platí výchozí 12 %/.test(await stat(page, 'stulMontazPctStatus')), [await hodnoty(page), await stat(page, 'stulMontazPctStatus')]);
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK admin Obecne -> Montaz, tri sazby: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
