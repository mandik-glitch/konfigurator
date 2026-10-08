// Editace nabidky v adminu: pole "Montaz (% z ceny nabidky)" (bot5, 2026-10-01; Robert: "montaz v online nabidce chci pred vytvorenim
// nabidky zvolit jako % castku"). SKUTECNY webapp/admin.html + vsechny webapp/admin/js/*.js v Chromiu proti falesnemu serveru
// (page.route, zadna sit ani DB): okno "Upravit nabidku" se ma otevrit se ulozenou sazbou a PUT musi poslat montaz_pct.
// Kandidat pred nasazenim: ADMIN_HTML=... CRM_NABIDKY_JS=... node test_montaz_pct_admin_editace.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = { 'crm-nabidky.js': process.env.CRM_NABIDKY_JS };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

const QUILL_ATRAPA = `
  window.Quill = function Quill() {};
  Quill.__icons = {};
  Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; };
  Quill.register = function () {};
`;

(async () => {
  const stav = { editData: null, puts: [] };
  const chyby = [];
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', d => d.accept());
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
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
    if (p === '/api/admin/scene-offers/777/edit-data' && m === 'GET') return json(200, stav.editData);
    if (p === '/api/admin/scene-offers/777' && m === 'PUT') { stav.puts.push(JSON.parse(req.postData() || '{}')); return json(200, { status: 'ok', revision_number: 2 }); }
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });
    return route.fulfill({ status: 404, body: '' });
  });
  await page.goto('http://admin.test/admin.html');
  try {
    await page.waitForFunction(() => typeof openOfferEditModal === 'function' && typeof currentOnlineOfferId !== 'undefined', null, { timeout: 15000 });
  } catch (e) {
    console.log('FAIL admin se nenacetl: ' + e.message.split('\n')[0] + ' | chyby: ' + chyby.slice(0, 3).join(' | '));
    process.exit(1);
  }
  await page.waitForTimeout(500);

  const editData = opts => ({
    offer_number: 'Logiman0200', items: [{ name: 'Profil', dim: '1000 mm', qty: '2 ks', unit_price: 500, total: 1000 }], total_price: 1000,
    editable_text: { popis: 'p', patka: 'f' }, revision_number: 1,
    offer_options: { show_qr: true, delivery_term: null, hidden_payment_method: null, hidden_delivery_state: null, fixed_deposit_pct: null, hide_bom_prices: false,
                     is_vehicle_assembly: false, manual_assembled_shipping_czk: null, ...opts },
  });
  const otevri = async opts => {
    stav.editData = editData(opts);
    chyby.length = 0;
    await page.evaluate(() => { currentOnlineOfferId = 777; });
    await page.evaluate(() => openOfferEditModal());
    await page.waitForTimeout(150);
    return page.evaluate(() => ({ hodnota: document.getElementById('offerEditMontazPct') ? document.getElementById('offerEditMontazPct').value : '(pole chybi)',
      otevreno: document.getElementById('offerEditModal').classList.contains('open') }));
  };
  const uloz = async () => {
    const pred = stav.puts.length;
    await page.evaluate(() => document.getElementById('btnOfferEditSave').click());
    await page.waitForTimeout(250);
    return { put: stav.puts.length > pred ? stav.puts[stav.puts.length - 1] : null, stavText: await page.evaluate(() => ({ t: document.getElementById('offerEditStatus').textContent, cls: document.getElementById('offerEditStatus').className,
      tlacitkoVypnuto: document.getElementById('btnOfferEditSave').disabled })) };
  };
  const pockejNaZavreni = () => page.waitForTimeout(1200);       // po uspesnem ulozeni se okno po 700 ms zavre a prekresli seznamy

  over('0 v editaci nabidky je pole offerEditMontazPct (cislo 0-100)', await page.evaluate(() => { const e = document.getElementById('offerEditMontazPct'); return !!e && e.type === 'number' && e.min === '0' && e.max === '100'; }), null);

  // ---- A) otevreni okna: pole se nacte z ulozene volby nabidky
  let o = await otevri({ montaz_pct: 15 });
  over('A1 ulozena sazba 15 se zobrazi v poli', o.otevreno && o.hodnota === '15', o);
  o = await otevri({ montaz_pct: null });
  over('A2 ulozena sazba null (plati vychozi z nastaveni) -> pole prazdne', o.hodnota === '', o);
  o = await otevri({ montaz_pct: 0 });
  over('A3 ulozena sazba 0 (bez montaze) -> pole obsahuje 0, NE prazdne (0 neni "nezvoleno")', o.hodnota === '0', o);
  o = await otevri({});
  over('A4 starsi nabidka bez klice montaz_pct -> pole prazdne, okno se otevre', o.otevreno && o.hodnota === '', o);
  over('A5 bez JS chyb pri otevreni', chyby.length === 0, chyby.slice(0, 3));

  // ---- B) ulozeni: PUT nese montaz_pct a vsechny puvodni volby
  await otevri({ montaz_pct: 15 });
  await page.fill('#offerEditMontazPct', '12.5');
  let r = await uloz();
  over('B1 zmena na 12,5 -> PUT nese offer_options.montaz_pct = 12.5', r.put && r.put.offer_options.montaz_pct === 12.5, r);
  const klice = r.put ? Object.keys(r.put.offer_options).sort() : [];
  over('B2 PUT nese dal vsech 8 puvodnich voleb (show_qr, delivery_term, hidden_payment_method, hidden_delivery_state, fixed_deposit_pct, hide_bom_prices, is_vehicle_assembly, manual_assembled_shipping_czk) + montaz_pct',
       JSON.stringify(klice) === JSON.stringify(['delivery_term', 'fixed_deposit_pct', 'hidden_delivery_state', 'hidden_payment_method', 'hide_bom_prices', 'is_vehicle_assembly', 'manual_assembled_shipping_czk', 'montaz_pct', 'show_qr']), klice);
  over('B3 PUT dal nese polozky a celkovou cenu (beze zmeny)', r.put && r.put.total_price === 1000 && r.put.items.length === 1, r.put && { total: r.put.total_price });
  await pockejNaZavreni();

  await otevri({ montaz_pct: 15 });
  await page.fill('#offerEditMontazPct', '');
  r = await uloz();
  over('B4 prazdne pole -> PUT nese montaz_pct = null (zpet na vychozi sazbu z nastaveni)', r.put && r.put.offer_options.montaz_pct === null, r);
  await pockejNaZavreni();

  await otevri({ montaz_pct: 15 });
  await page.fill('#offerEditMontazPct', '0');
  r = await uloz();
  over('B5 pole 0 -> PUT nese montaz_pct = 0 (ne null)', r.put && r.put.offer_options.montaz_pct === 0 && r.put.offer_options.montaz_pct !== null, r);
  await pockejNaZavreni();

  await otevri({ montaz_pct: 15 });
  r = await uloz();
  over('B6 pole se nezmenilo (15) -> PUT nese montaz_pct = 15 (editace jineho pole sazbu neztrati)', r.put && r.put.offer_options.montaz_pct === 15, r);
  await pockejNaZavreni();

  // ---- C) neplatna hodnota: chyba, nic se neodesle, tlacitko zustane pouzitelne
  for (const [hodnota, popis] of [['150', 'nad 100'], ['-5', 'zaporna'], ['100.5', '100,5']]) {
    await otevri({ montaz_pct: 15 });
    await page.fill('#offerEditMontazPct', hodnota);
    r = await uloz();
    over(`C ${popis}: zadny PUT, hlaska "Montaz musi byt cislo od 0 do 100 %", tlacitko Ulozit zustava aktivni`,
         r.put === null && /Montáž musí být číslo od 0 do 100 %/.test(r.stavText.t) && r.stavText.cls === 'err' && r.stavText.tlacitkoVypnuto === false, r);
  }

  over('D bez JS chyb behem testu (otevreni, ulozeni, neplatne hodnoty)', chyby.filter(e => !/openOnlineOfferStats|loadOnlineOffersList/.test(e)).length === 0, chyby.slice(0, 3));
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK editace nabidky v adminu (montaz %): ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
