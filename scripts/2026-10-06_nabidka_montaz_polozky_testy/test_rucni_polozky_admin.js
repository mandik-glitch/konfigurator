// RUCNI POLOZKY v online nabidce - editor v adminu (bot8, 2026-10-06; Robert: admin pripise do nabidky polozku z katalogu s 3D modelem / volny text s 1-2 obrazky a cenou).
// SKUTECNY webapp/admin.html + vsechny webapp/admin/js/*.js v Chromiu proti falesnemu serveru (page.route, zadna sit ani DB, nic se nezapisuje): okno "Upravit nabidku" ukaze editor
// JEN kdyz edit-data nese priznak `rucni_polozky` (staticky kod je zivy driv nez API), polozky z katalogu se hledaji napovedou, volny text ma 1-2 obrazky (nahrani, zmenseni velkych fotek,
// odebrani), ceny a celkovy soucet se prepocitavaji, poradi jde menit, PUT nese obycejne radky beze zmeny + rucni polozky na konci.
// Kandidat pred nasazenim: ADMIN_HTML=... CRM_NABIDKY_JS=... node test_rucni_polozky_admin.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = { 'crm-nabidky.js': process.env.CRM_NABIDKY_JS };
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

const QUILL_ATRAPA = `
  window.Quill = function Quill() {};
  Quill.__icons = {};
  Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; };
  Quill.register = function () {};
`;
const PRODUKTY = [
  { id: 3091, sku: '2.3.001.40.S10', name: 'Záslepka 40x40 S10', description: '<p>Záslepka <b>40x40</b> (z materiálu plast, hmotnost cca 6 g).</p>\n<p>Plastová záslepka profilu.</p>', price_czk_placeholder: 5, glb_file: 'product_3091.glb', unit: 'ks' },
  { id: 3092, sku: '2.3.001.40.S11', name: 'Záslepka 40x40 S11 bez modelu', description: null, price_czk_placeholder: null, glb_file: null, unit: 'ks' },
  { id: 3093, sku: 'ZAS-3', name: 'Záslepka dlouhý název ' + 'x'.repeat(240), description: 'Popis', price_czk_placeholder: 12.5, glb_file: 'product_3093.glb', unit: 'ks' },
];
const REG = [{ name: 'Profil 40x40mm', dim: '1000 mm', qty: '2 ks', unit_price: 500, total: 1000, mesh_group: 1 }, { name: 'Balné (3 %)', dim: '-', qty: '-', total: 30 }];
const TEXT_ULOZENY = { name: 'Zaměření', dim: '1× výjezd', qty: '2 ks', unit_price: 1500, total: 3000, manual: { typ: 'text', popis: 'Zaměření u zákazníka', obrazky: ['polozka_777_0123456789abcdef.png'] } };
const KAT_ULOZENY = { name: 'Záslepka 40x40 S10', dim: '', qty: '4 ks', unit_price: 5, total: 20, product_id: 3091, layer: 'produkt', manual: { typ: 'katalog', popis: 'Černá', model: true } };

(async () => {
  const stav = { editData: null, puts: [], posty: [], uploadOdpoved: null, uploadZdrzeni: 0, putOdpoved: null, vyhledavani: [], dalsiKlic: 1 };
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
    if (p === '/api/admin/scene-offers/777' && m === 'PUT') { stav.puts.push(JSON.parse(req.postData() || '{}')); return stav.putOdpoved ? json(stav.putOdpoved.status, stav.putOdpoved.body) : json(200, { status: 'ok', revision_number: 2 }); }
    if (p === '/api/admin/scene-offers/777/item-images' && m === 'POST') {
      stav.posty.push(JSON.parse(req.postData() || '{}'));
      if (stav.uploadZdrzeni) await new Promise(r => setTimeout(r, stav.uploadZdrzeni));
      if (stav.uploadOdpoved) return json(stav.uploadOdpoved.status, stav.uploadOdpoved.body);
      const key = `polozka_777_${String(stav.dalsiKlic++).padStart(16, '0')}.png`;
      return json(201, { key, url: `/api/admin/scene-offers/777/item-images/${key}` });
    }
    if (/^\/api\/admin\/scene-offers\/777\/item-images\//.test(p) && m === 'GET') return route.fulfill({ status: 200, contentType: 'image/png', body: PNG });
    if (p === '/api/shop/products' && m === 'GET') {
      const q = (u.searchParams.get('q') || '').toLowerCase();
      stav.vyhledavani.push({ q, all: u.searchParams.get('all'), page_size: u.searchParams.get('page_size') });
      return json(200, { products: PRODUKTY.filter(x => x.name.toLowerCase().includes(q) || x.sku.toLowerCase().includes(q)), total: 3, page: 1, page_size: 12 });
    }
    const mProd = /^\/api\/shop\/products\/(\d+)$/.exec(p);
    if (mProd && m === 'GET') { const x = PRODUKTY.find(z => String(z.id) === mProd[1]); return x ? json(200, { product: x, gallery: [] }) : json(404, { error: 'Produkt neexistuje.' }); }
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

  const editData = (items, rucni = { max: 20, obrazky_max: 2 }, opts = {}) => ({
    offer_number: 'Logiman0200', items, total_price: items.reduce((s, i) => s + (i.total || 0), 0), editable_text: { popis: 'p', patka: 'f' }, revision_number: 1,
    offer_options: { show_qr: true, delivery_term: null, hidden_payment_method: null, hidden_delivery_state: null, fixed_deposit_pct: null, hide_bom_prices: false, is_vehicle_assembly: false, manual_assembled_shipping_czk: null, montaz_pct: null, ...opts },
    ...(rucni ? { rucni_polozky: rucni } : {}),
  });
  const otevri = async (items, rucni) => {
    stav.editData = editData(JSON.parse(JSON.stringify(items)), rucni);
    chyby.length = 0;
    await page.evaluate(() => { currentOnlineOfferId = 777; });
    await page.evaluate(() => openOfferEditModal());
    await page.waitForTimeout(250);
  };
  const stavDialogu = () => page.evaluate(() => ({
    wrapVidet: getComputedStyle(document.getElementById('offerEditManualWrap')).display !== 'none',
    radkuTabulky: document.querySelectorAll('#offerEditItemsBody tr').length,
    karty: [...document.querySelectorAll('#offerEditManualList .oe-mi')].map(c => ({
      typ: c.querySelector('.oe-mi-typ').textContent, name: c.querySelector('.oe-mi-name').value, dim: c.querySelector('.oe-mi-dim').value, qty: c.querySelector('.oe-mi-qty').value,
      price: c.querySelector('.oe-mi-price').value, total: c.querySelector('.oe-mi-total').textContent.replace(/\s/g, ' '), popis: c.querySelector('.oe-mi-popis').value,
      model: c.querySelector('.oe-mi-model') ? { checked: c.querySelector('.oe-mi-model').checked, disabled: c.querySelector('.oe-mi-model').disabled, hint: c.querySelector('.oe-mi-hint').textContent } : null,
      obrazky: [...c.querySelectorAll('.oe-mi-img')].map(i => i.dataset.key), pridat: !!c.querySelector('.oe-mi-add'), nahoru: !c.querySelector('.oe-mi-up').disabled, dolu: !c.querySelector('.oe-mi-down').disabled,
    })),
    celkem: document.getElementById('offerEditTotal').textContent.replace(/\s/g, ' '),
    hledaniOff: document.getElementById('offerEditManualSearch').disabled, textOff: document.getElementById('btnOfferEditManualText').disabled,
    stav: document.getElementById('offerEditManualStatus').textContent,
  }));
  const uloz = async () => {
    const pred = stav.puts.length;
    await page.evaluate(() => document.getElementById('btnOfferEditSave').click());
    await page.waitForTimeout(300);
    return { put: stav.puts.length > pred ? stav.puts[stav.puts.length - 1] : null, text: await page.evaluate(() => ({ t: document.getElementById('offerEditStatus').textContent, cls: document.getElementById('offerEditStatus').className, off: document.getElementById('btnOfferEditSave').disabled })) };
  };
  const pockejNaZavreni = () => page.waitForTimeout(1200);
  const nahrajSoubor = (selektor, nazev, mime, buf) => page.setInputFiles(selektor, { name: nazev, mimeType: mime, buffer: buf });

  // ------------------------------------------------------------------------------------------------ A) priznak backendu
  await otevri(REG, null);
  let d = await stavDialogu();
  over('A1 edit-data BEZ priznaku rucni_polozky (starsi backend): editor je skryty, tabulka ma jen obycejne radky', !d.wrapVidet && d.radkuTabulky === 2 && d.karty.length === 0, d);
  await page.evaluate(() => document.getElementById('btnOfferEditCancel').click());
  await otevri(REG);
  d = await stavDialogu();
  over('A2 s priznakem: editor viditelny, zatim bez polozek, hledani i tlacitko Volny text aktivni', d.wrapVidet && d.karty.length === 0 && !d.hledaniOff && !d.textOff && d.radkuTabulky === 2, d);
  over('A3 puvodni celkova cena = soucet radku (1 030 Kc)', /1 030 Kč/.test(d.celkem), d.celkem);

  // ------------------------------------------------------------------------------------------------ B) ulozene rucni polozky
  await otevri([...REG, TEXT_ULOZENY, KAT_ULOZENY]);
  d = await stavDialogu();
  over('B1 ulozene rucni polozky NEJSOU v hlavni tabulce (jen 2 obycejne radky), jsou v editoru ve stejnem poradi', d.radkuTabulky === 2 && d.karty.length === 2 && d.karty[0].name === 'Zaměření' && d.karty[1].name === 'Záslepka 40x40 S10', d);
  over('B2 volny text: typ, rozmer, mnozstvi "2 ks" -> 2, cena, celkem, popis, obrazek s nahledem', d.karty[0].typ === 'Volný text' && d.karty[0].dim === '1× výjezd' && d.karty[0].qty === '2' && d.karty[0].price === '1500' && d.karty[0].total === '3 000 Kč'
     && d.karty[0].popis === 'Zaměření u zákazníka' && JSON.stringify(d.karty[0].obrazky) === JSON.stringify(['polozka_777_0123456789abcdef.png']) && d.karty[0].pridat, d.karty[0]);
  over('B3 z katalogu: typ s cislem produktu, 3D model zatrhnuty', d.karty[1].typ === 'Z katalogu · #3091' && d.karty[1].model && d.karty[1].model.checked && d.karty[1].qty === '4' && d.karty[1].popis === 'Černá', d.karty[1]);
  over('B4 poradi: prvni nema sipku nahoru, posledni nema sipku dolu', !d.karty[0].nahoru && d.karty[0].dolu && d.karty[1].nahoru && !d.karty[1].dolu, d.karty.map(k => [k.nahoru, k.dolu]));
  over('B5 celkem = obycejne radky + rucni (1 030 + 3 000 + 20 = 4 050)', /4 050 Kč/.test(d.celkem), d.celkem);
  const src = await page.evaluate(() => document.querySelector('.oe-mi-img img').getAttribute('src'));
  over('B6 nahled obrazku jde pres admin endpoint teto nabidky', src === '/api/admin/scene-offers/777/item-images/polozka_777_0123456789abcdef.png', src);
  over('B7 bez JS chyb pri otevreni', chyby.length === 0, chyby.slice(0, 3));

  // ------------------------------------------------------------------------------------------------ C) pridani z katalogu
  await otevri(REG);
  stav.vyhledavani.length = 0;
  await page.fill('#offerEditManualSearch', 'z');
  await page.waitForTimeout(500);
  over('C1 jedno pismeno se nehleda (min. 2 znaky)', stav.vyhledavani.length === 0 && !(await page.evaluate(() => document.getElementById('offerEditManualSuggest').classList.contains('open'))), stav.vyhledavani);
  await page.fill('#offerEditManualSearch', '');
  stav.vyhledavani.length = 0;
  await page.type('#offerEditManualSearch', 'zaslepk', { delay: 40 });            // pise se po znacich - dotaz se odesle az po odmlce, ne po kazdem znaku
  await page.waitForTimeout(600);
  over('C2 hledani ceka na odmlku (jediny dotaz) a dotaz nese all=1, q, page_size=12', stav.vyhledavani.length === 1 && stav.vyhledavani[0].q === 'zaslepk' && stav.vyhledavani[0].all === '1' && stav.vyhledavani[0].page_size === '12', stav.vyhledavani);
  await page.fill('#offerEditManualSearch', 'záslepka');
  await page.waitForSelector('#offerEditManualSuggest .ps-row', { timeout: 3000 });
  const nav = await page.evaluate(() => [...document.querySelectorAll('#offerEditManualSuggest .ps-row')].map(r => r.textContent.replace(/\s+/g, ' ').trim()));
  over('C3 napoveda ukaze nazev, SKU, znacku 3D a cenu (u produktu bez ceny "bez ceny")', nav.length === 3 && /Záslepka 40x40 S10 \(2\.3\.001\.40\.S10\) 3D · 5 Kč/.test(nav[0]) && /bez ceny/.test(nav[1]) && !/3D/.test(nav[1]), nav);
  await page.click('#offerEditManualSuggest .ps-row[data-id="3091"]');
  await page.waitForTimeout(250);
  d = await stavDialogu();
  const k = d.karty[0];
  over('C4 vybrany produkt = nova polozka na konci: nazev z katalogu, mnozstvi 1, cena z katalogu 5, celkem 5 Kc', d.karty.length === 1 && k.typ === 'Z katalogu · #3091' && k.name === 'Záslepka 40x40 S10' && k.qty === '1' && k.price === '5' && k.total === '5 Kč', d);
  over('C5 popis predvyplnen z katalogu BEZ HTML znacek', k.popis === 'Záslepka 40x40 (z materiálu plast, hmotnost cca 6 g). Plastová záslepka profilu.', k.popis);
  over('C6 3D model je u produktu s modelem zatrhnuty a pouzitelny', k.model.checked && !k.model.disabled && k.model.hint === '', k.model);
  over('C7 napoveda se po vyberu zavre a pole hledani vyprazdni', (await page.evaluate(() => ({ v: document.getElementById('offerEditManualSearch').value, o: document.getElementById('offerEditManualSuggest').classList.contains('open') }))).v === '', null);
  over('C8 celkova cena se prepocitala (1 030 + 5 = 1 035 Kc)', /1 035 Kč/.test(d.celkem), d.celkem);

  await page.fill('#offerEditManualSearch', 'bez modelu');
  await page.waitForSelector('#offerEditManualSuggest .ps-row[data-id="3092"]', { timeout: 3000 });
  await page.click('#offerEditManualSuggest .ps-row[data-id="3092"]');
  await page.waitForTimeout(250);
  d = await stavDialogu();
  over('C9 produkt BEZ modelu: zatrhavatko vypnute a odskrtnute s napovedou, cena 0 (katalog ji nema)', d.karty.length === 2 && d.karty[1].model && !d.karty[1].model.checked && d.karty[1].model.disabled && /nemá 3D model/.test(d.karty[1].model.hint) && d.karty[1].price === '0', d.karty[1]);
  await page.fill('#offerEditManualSearch', 'dlouhý název');
  await page.waitForSelector('#offerEditManualSuggest .ps-row[data-id="3093"]', { timeout: 3000 });
  await page.click('#offerEditManualSuggest .ps-row[data-id="3093"]');
  await page.waitForTimeout(250);
  d = await stavDialogu();
  over('C10 nazev nad 200 znaku se oriznul na 200 (server by ho jinak odmitl), cena 12,5 z katalogu, celkem 13 Kc (zaokrouhleno)', d.karty[2].name.length === 200 && d.karty[2].price === '12.5' && d.karty[2].total === '13 Kč', [d.karty[2].name.length, d.karty[2].price, d.karty[2].total]);
  await page.fill('#offerEditManualSearch', 'neexistuje');
  await page.waitForSelector('#offerEditManualSuggest .ps-empty', { timeout: 3000 });
  over('C11 hledani bez vysledku ukaze hlasku', /Žádný produkt/.test(await page.textContent('#offerEditManualSuggest')), null);
  await page.fill('#offerEditManualSearch', '');
  over('C12 bez JS chyb pri pridavani z katalogu', chyby.length === 0, chyby.slice(0, 3));

  // ------------------------------------------------------------------------------------------------ D) volny text + ceny
  await otevri(REG);
  await page.click('#btnOfferEditManualText');
  d = await stavDialogu();
  over('D1 "+ Volny text": nova polozka s prazdnym nazvem, mnozstvi 1, cena 0, bez obrazku, tlacitko pridat obrazek', d.karty.length === 1 && d.karty[0].typ === 'Volný text' && d.karty[0].name === '' && d.karty[0].qty === '1' && d.karty[0].price === '0' && d.karty[0].pridat && d.karty[0].obrazky.length === 0, d);
  over('D2 pole Nazev je rovnou aktivni (focus)', await page.evaluate(() => document.activeElement && document.activeElement.classList.contains('oe-mi-name')), null);
  await page.fill('.oe-mi-name', 'Doprava na místo');
  await page.fill('.oe-mi-dim', '1× výjezd');
  await page.fill('.oe-mi-qty', '3');
  await page.fill('.oe-mi-price', '1234.5');
  await page.fill('.oe-mi-popis', 'První řádek\nDruhý řádek');
  d = await stavDialogu();
  over('D3 3 ks x 1 234,5 = 3 704 Kc (zaokrouhleno), v editoru i v celkove cene (1 030 + 3 704 = 4 734)', d.karty[0].total === '3 704 Kč' && /4 734 Kč/.test(d.celkem), [d.karty[0].total, d.celkem]);
  over('D4 prepis mnozstvi na prazdne = 0 ks -> celkem 0 (server pak odmitne, formular nespadne)', await (async () => { await page.fill('.oe-mi-qty', ''); const x = await stavDialogu(); await page.fill('.oe-mi-qty', '3'); return x.karty[0].total === '0 Kč'; })(), null);

  // ------------------------------------------------------------------------------------------------ E) obrazky
  await nahrajSoubor('.oe-mi-file', 'foto.png', 'image/png', PNG);
  await page.waitForSelector('.oe-mi-img', { timeout: 3000 });
  d = await stavDialogu();
  over('E1 nahrany obrazek: POST s data URI (png), v editoru nahled s klicem ze serveru, tlacitko Pridat zustava (1 z 2)', stav.posty.length === 1 && /^data:image\/png;base64,/.test(stav.posty[0].image) && d.karty[0].obrazky.length === 1 && /^polozka_777_0{15}1\.png$/.test(d.karty[0].obrazky[0]) && d.karty[0].pridat, [stav.posty.length, d.karty[0].obrazky]);
  over('E2 male PNG se posila beze zmeny (nezmensuje se)', stav.posty[0].image === 'data:image/png;base64,' + PNG.toString('base64'), null);
  await nahrajSoubor('.oe-mi-file', 'foto2.jpg', 'image/jpeg', Buffer.concat([Buffer.from([0xff, 0xd8, 0xff, 0xe0]), Buffer.alloc(100)]));
  await page.waitForFunction(() => document.querySelectorAll('.oe-mi-img').length === 2, null, { timeout: 3000 });
  d = await stavDialogu();
  over('E3 po 2 obrazcich tlacitko "Pridat obrazek" zmizi', d.karty[0].obrazky.length === 2 && !d.karty[0].pridat, d.karty[0]);
  await page.click('.oe-mi-img[data-key] .oe-mi-img-del');
  d = await stavDialogu();
  over('E4 odebrani obrazku (x): zbyde druhy, tlacitko Pridat se vrati', d.karty[0].obrazky.length === 1 && /2\.png$/.test(d.karty[0].obrazky[0]) && d.karty[0].pridat, d.karty[0]);
  over('E5 bez JS chyb pri obrazcich', chyby.length === 0, chyby.slice(0, 3));

  // velka fotka se zmensi: v prohlizeci se vyrobi sum 3000 x 2000 jako JPEG (vic nez 1,5 MB) a vlozi do pole souboru
  const pred = stav.posty.length;
  await page.evaluate(async () => {
    const c = document.createElement('canvas'); c.width = 3000; c.height = 2000;
    const g = c.getContext('2d'), id = g.createImageData(3000, 2000);
    for (let i = 0; i < id.data.length; i += 4) { id.data[i] = Math.random() * 255; id.data[i + 1] = Math.random() * 255; id.data[i + 2] = Math.random() * 255; id.data[i + 3] = 255; }
    g.putImageData(id, 0, 0);
    const blob = await new Promise(r => c.toBlob(r, 'image/jpeg', 1));
    window.__velkaVelikost = blob.size;
    const dt = new DataTransfer(); dt.items.add(new File([blob], 'velka.jpg', { type: 'image/jpeg' }));
    const inp = document.querySelector('.oe-mi-file'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForFunction(() => document.querySelectorAll('.oe-mi-img').length === 2, null, { timeout: 15000 });
  const velka = await page.evaluate(() => window.__velkaVelikost);
  const odeslano = stav.posty[stav.posty.length - 1].image;
  const rozmer = await page.evaluate(src => new Promise(r => { const i = new Image(); i.onload = () => r([i.naturalWidth, i.naturalHeight]); i.onerror = () => r(null); i.src = src; }), odeslano);
  over('E6 velka fotka (3000x2000, vic nez 1,5 MB) se pred odeslanim zmensi na max 1600 px jako JPEG a je mnohem mensi', stav.posty.length === pred + 1 && velka > 1500 * 1024 && /^data:image\/jpeg;base64,/.test(odeslano) && rozmer && Math.max(...rozmer) === 1600 && odeslano.length < velka * 1.37 / 3, { velka, odeslano: odeslano.length, rozmer });
  // spatny typ: bez POSTu, hlaska
  await page.click('.oe-mi-img[data-key] .oe-mi-img-del');
  const pred2 = stav.posty.length;
  await page.evaluate(() => {
    const dt = new DataTransfer(); dt.items.add(new File(['GIF89a'], 'a.gif', { type: 'image/gif' }));
    const inp = document.querySelector('.oe-mi-file'); inp.files = dt.files; inp.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await page.waitForTimeout(300);
  d = await stavDialogu();
  over('E7 GIF: zadny POST, hlaska "PNG nebo JPEG", nic se nepridalo', stav.posty.length === pred2 && /PNG nebo JPEG/.test(d.stav) && d.karty[0].obrazky.length === 1, [stav.posty.length - pred2, d.stav]);
  // chyba serveru pri nahravani
  stav.uploadOdpoved = { status: 400, body: { error: 'Obsah souboru neodpovídá obrázku.' } };
  await nahrajSoubor('.oe-mi-file', 'zly.png', 'image/png', PNG);
  await page.waitForTimeout(400);
  d = await stavDialogu();
  over('E8 server odmitne obrazek (400): hlaska ze serveru, obrazek se nepridal', /Obsah souboru neodpovídá obrázku/.test(d.stav) && d.karty[0].obrazky.length === 1, d.stav);
  stav.uploadOdpoved = null;

  // ------------------------------------------------------------------------------------------------ F) poradi, mazani, strop
  await otevri([...REG, TEXT_ULOZENY, KAT_ULOZENY]);
  await page.click('.oe-mi:nth-child(2) .oe-mi-up');
  d = await stavDialogu();
  over('F1 sipka nahoru prohodi rucni polozky (katalog pred text), poradi sipek se prepocita', d.karty[0].name === 'Záslepka 40x40 S10' && d.karty[1].name === 'Zaměření' && !d.karty[0].nahoru && !d.karty[1].dolu, d.karty.map(x => x.name));
  await page.click('.oe-mi:nth-child(1) .oe-mi-down');
  d = await stavDialogu();
  over('F2 sipka dolu je vrati', d.karty[0].name === 'Zaměření' && d.karty[1].name === 'Záslepka 40x40 S10', d.karty.map(x => x.name));
  await page.click('.oe-mi:nth-child(1) .oe-mi-del');
  d = await stavDialogu();
  over('F3 odebrani polozky (x): zbyde 1 rucni, celkova cena klesne o 3 000 (1 030 + 20 = 1 050)', d.karty.length === 1 && d.karty[0].name === 'Záslepka 40x40 S10' && /1 050 Kč/.test(d.celkem) && d.radkuTabulky === 2, [d.karty.length, d.celkem]);
  stav.editData = editData([...REG, TEXT_ULOZENY, KAT_ULOZENY], { max: 3, obrazky_max: 1 });
  await page.evaluate(() => openOfferEditModal()); await page.waitForTimeout(250);
  d = await stavDialogu();
  over('F4 strop poctu z backendu (max 3): po 2 ulozenych je jeste mozne pridat', !d.hledaniOff && !d.textOff && d.karty.length === 2, d);
  await page.click('#btnOfferEditManualText');
  d = await stavDialogu();
  over('F5 po dosazeni stropu (3) je hledani i "+ Volny text" vypnute', d.karty.length === 3 && d.hledaniOff && d.textOff, d);
  over('F6 obrazky_max z backendu (1): u polozky s 1 obrazkem uz neni "Pridat obrazek"', !d.karty[0].pridat && d.karty[0].obrazky.length === 1, d.karty[0]);
  await page.click('.oe-mi:nth-child(3) .oe-mi-del');
  d = await stavDialogu();
  over('F7 po odebrani se tlacitka opet zapnou', !d.hledaniOff && !d.textOff, d);

  // ------------------------------------------------------------------------------------------------ G) ulozeni (PUT)
  await otevri(REG);
  await page.fill('#offerEditManualSearch', 'záslepka');
  await page.waitForSelector('#offerEditManualSuggest .ps-row[data-id="3091"]');
  await page.click('#offerEditManualSuggest .ps-row[data-id="3091"]');
  await page.fill('.oe-mi:nth-child(1) .oe-mi-qty', '4');
  await page.click('#btnOfferEditManualText');
  await page.fill('.oe-mi:nth-child(2) .oe-mi-name', 'Doprava');
  await page.fill('.oe-mi:nth-child(2) .oe-mi-price', '1500');
  await nahrajSoubor('.oe-mi:nth-child(2) .oe-mi-file', 'foto.png', 'image/png', PNG);
  await page.waitForSelector('.oe-mi:nth-child(2) .oe-mi-img');
  let r = await uloz();
  const it = r.put && r.put.items;
  over('G1 PUT: obycejne radky na zacatku beze zmeny (2x), rucni za nimi (2x) v poradi z editoru', it && it.length === 4 && JSON.stringify(it[0]) === JSON.stringify(REG[0]) && JSON.stringify(it[1]) === JSON.stringify(REG[1]) && it[2].name === 'Záslepka 40x40 S10' && it[3].name === 'Doprava', it && it.map(x => x.name));
  over('G2 rucni z katalogu: product_id, mnozstvi 4, cena 5, celkem 20, manual {typ katalog, popis, model true}', it && it[2].product_id === 3091 && it[2].qty === 4 && it[2].unit_price === 5 && it[2].total === 20 && it[2].manual.typ === 'katalog' && it[2].manual.model === true && /plast/.test(it[2].manual.popis), it && it[2]);
  over('G3 rucni volny text: manual {typ text, popis, obrazky: [klic]} bez product_id, cena 1500, celkem 1500', it && it[3].manual.typ === 'text' && it[3].product_id === undefined && it[3].unit_price === 1500 && it[3].total === 1500 && it[3].manual.obrazky.length === 1 && /^polozka_777_/.test(it[3].manual.obrazky[0]), it && it[3]);
  over('G4 total_price = soucet vsech radku (1 030 + 20 + 1 500 = 2 550) a volby nabidky dal odchazeji', r.put && r.put.total_price === 2550 && r.put.offer_options && r.put.offer_options.show_qr === true && 'montaz_pct' in r.put.offer_options, r.put && r.put.total_price);
  await pockejNaZavreni();

  // kolem dokola: to, co server vrati (qty "N ks"), se v editoru zobrazi stejne a znovu se ulozi
  await otevri([...REG, { ...it[2], qty: '4 ks' }, { ...it[3], qty: '1 ks' }]);
  d = await stavDialogu();
  over('G5 po ulozeni a znovu-otevreni (qty "4 ks" / "1 ks") editor ukaze stejna cisla, bez zmeny jde znovu ulozit', d.karty.length === 2 && d.karty[0].qty === '4' && d.karty[1].qty === '1' && d.karty[1].obrazky.length === 1, d.karty);
  r = await uloz();
  over('G6 beze zmeny se rucni polozky posilaji tak, jak prisly (qty "4 ks" zustava)', r.put && r.put.items[2].qty === '4 ks' && r.put.items[3].qty === '1 ks' && r.put.total_price === 2550, r.put && r.put.items.slice(2).map(x => x.qty));
  await pockejNaZavreni();

  // chyba serveru: hlaska a tlacitko pouzitelne
  stav.putOdpoved = { status: 400, body: { error: 'Ruční položka 1: chybí název.' } };
  await otevri(REG);
  await page.click('#btnOfferEditManualText');
  r = await uloz();
  over('G7 server odmitne (400 "chybi nazev"): hlaska se ukaze, formular zustane otevreny, Ulozit je zase aktivni', r.put && /chybí název/.test(r.text.t) && r.text.cls === 'err' && r.text.off === false && await page.evaluate(() => document.getElementById('offerEditModal').classList.contains('open')), r);
  stav.putOdpoved = null;

  // ulozeni behem nahravani obrazku se pocka
  await otevri(REG);
  await page.click('#btnOfferEditManualText');
  stav.uploadZdrzeni = 1200;
  await nahrajSoubor('.oe-mi-file', 'foto.png', 'image/png', PNG);
  await page.waitForTimeout(200);
  const pocetPutu = stav.puts.length;
  r = await uloz();
  over('G8 behem nahravani obrazku se ulozeni NEodesle ("Pockejte, nahrava se obrazek")', stav.puts.length === pocetPutu && /nahrává se obrázek/.test(r.text.t) && r.text.cls === 'err', r);
  await page.waitForSelector('.oe-mi-img', { timeout: 5000 });
  stav.uploadZdrzeni = 0;
  await page.fill('.oe-mi-name', 'Foto');
  r = await uloz();
  over('G9 po dokonceni nahravani se ulozi a nese klic obrazku', r.put && r.put.items[2].manual.obrazky.length === 1, r.put && r.put.items.slice(2));
  await pockejNaZavreni();

  // ------------------------------------------------------------------------------------------------ I) obycejne radky: mnozstvi "N ks" ze sceny (drive prazdne pole -> uprava ceny vynulovala radek)
  await otevri([{ name: 'Profil 40x40mm', dim: '1000 mm', qty: '2 ks', unit_price: 500, total: 1000, mesh_group: 1 }, { name: 'Vandr sestava', dim: '-', qty: 1, unit_price: 5000, total: 5000 }, { name: 'Balné (3 %)', dim: '-', qty: '-', total: 30 }]);
  const mn = await page.evaluate(() => [...document.querySelectorAll('#offerEditItemsBody tr')].map(tr => ({ qty: tr.querySelector('.oe-qty') ? tr.querySelector('.oe-qty').value : null, plosny: !!tr.querySelector('.oe-total-flat') })));
  over('I1 mnozstvi "2 ks" ze sceny se v poli ukaze jako 2 (drive prazdne), cislo 1 zustane 1, plosny radek bez pole mnozstvi', mn[0].qty === '2' && mn[1].qty === '1' && mn[2].qty === null && mn[2].plosny, mn);
  await page.fill('#offerEditItemsBody tr:nth-child(1) .oe-price', '600');
  let tr1 = await page.evaluate(() => ({ celkem: document.querySelector('#offerEditItemsBody tr:nth-child(1) .oe-row-total').textContent.replace(/\s/g, ' '), soucet: document.getElementById('offerEditTotal').textContent.replace(/\s/g, ' ') }));
  over('I2 uprava ceny radku ze sceny: 2 ks x 600 = 1 200 (radek se nevynuluje), celkem 1 200 + 5 000 + 30 = 6 230', tr1.celkem === '1 200 Kč' && /6 230 Kč/.test(tr1.soucet), tr1);
  r = await uloz();
  over('I3 PUT nese mnozstvi ve stejnem tvaru "2 ks" (ne holou 2), cenu 600 a celkem 1 200', r.put && r.put.items[0].qty === '2 ks' && r.put.items[0].unit_price === 600 && r.put.items[0].total === 1200 && r.put.total_price === 6230, r.put && r.put.items[0]);
  await pockejNaZavreni();
  await otevri([{ name: 'Profil 40x40mm', dim: '1000 mm', qty: '2 ks', unit_price: 500, total: 1000, mesh_group: 1 }, { name: 'Vandr sestava', dim: '-', qty: 1, unit_price: 5000, total: 5000 }]);
  await page.fill('#offerEditItemsBody tr:nth-child(1) .oe-qty', '3');
  await page.fill('#offerEditItemsBody tr:nth-child(2) .oe-price', '6000');
  r = await uloz();
  over('I4 zmena mnozstvi na 3 -> "3 ks", 3 x 500 = 1 500; radek s cislem (Vandr) zustane cislem 1, cena 6 000', r.put && r.put.items[0].qty === '3 ks' && r.put.items[0].total === 1500 && r.put.items[1].qty === 1 && r.put.items[1].total === 6000 && r.put.total_price === 7500, r.put && r.put.items);
  await pockejNaZavreni();

  // ------------------------------------------------------------------------------------------------ J) uvozovky a znacky v textech (nazev z katalogu muze obsahovat " a '; nesmi z atributu value vyskocit)
  const ZLY = { name: 'Profil "S" onfocus="window.__x=1" a\'b', dim: '5" x 3\'', qty: '1 ks', unit_price: 1, total: 1, manual: { typ: 'text', popis: '</textarea><img src=x onerror="window.__x=2">', obrazky: [] } };
  await otevri([...REG, ZLY]);
  const zly = await page.evaluate(() => { const i = document.querySelector('.oe-mi-name'); return { v: i.value, atributy: i.getAttributeNames(), dim: document.querySelector('.oe-mi-dim').value, x: window.__x, popis: document.querySelector('.oe-mi-popis').value, img: document.querySelectorAll('#offerEditManualList img').length }; });
  over('J1 nazev a rozmer s uvozovkami / apostrofem se v poli ukazou CELE a nevznikne zadny cizi atribut (onfocus), nic se nespusti', zly.v === ZLY.name && !zly.atributy.includes('onfocus') && zly.dim === ZLY.dim && zly.x === undefined, zly);
  over('J2 popis se znackou </textarea><img onerror> zustane textem v poli (zadny obrazek, nic se nespusti)', zly.popis === ZLY.manual.popis && zly.img === 0 && zly.x === undefined, zly);
  r = await uloz();
  over('J3 beze zmeny se nazev a rozmer ulozi tak, jak byly (uvozovky zachovany)', r.put && r.put.items[2].name === ZLY.name && r.put.items[2].dim === ZLY.dim, r.put && r.put.items[2]);
  await pockejNaZavreni();

  // ------------------------------------------------------------------------------------------------ H) mobil + chyby
  await page.setViewportSize({ width: 390, height: 800 });
  await otevri([...REG, TEXT_ULOZENY, KAT_ULOZENY]);
  const sirka = await page.evaluate(() => { const b = document.getElementById('offerEditBox'); return { scroll: b.scrollWidth, client: b.clientWidth, okno: innerWidth }; });
  over('H1 uzka obrazovka (390 px): okno upravy nabidky se nerozjizdi do sirky (bez horizontalniho posunu)', sirka.scroll <= sirka.client + 1 && sirka.client <= sirka.okno, sirka);
  over('H2 bez JS chyb behem testu', chyby.filter(e => !/openOnlineOfferStats|loadOnlineOffersList/.test(e)).length === 0, chyby.slice(0, 3));
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK rucni polozky v online nabidce - editor v adminu: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
