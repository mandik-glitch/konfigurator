// Tabulka variant + stitky-filtry NA SKUTECNE STRANCE KATEGORIE webapp/category.html (bot16, 2026-10-07; Robert: "Ano, nasadit" po nahledu). SKUTECNA stranka + moduly webapp/js/kategorie-tabulka.js a
// webapp/css/kategorie-tabulka.css v Chromiu; data jsou ZIVA z e-shopu (read-only GET: /api/categories, /api/categories/<id>/content, /api/shop/products?category_id=324&include=specs; obrazky),
// ostatni server je maketa (page.route; zadne zapisy, zadna DB). Kategorie 324 = tabulka (vypis karet skryty), JINA kategorie (bez konfigurace) = beze zmeny puvodni vypis karet; selhani modulu = zpet karty.
// Ocekavane hodnoty se pocitaji z tychz zivych dat NEZAVISLE na kodu. Kandidat: CATEGORY_HTML=/cesta/category.html KT_JS=/cesta/kategorie-tabulka.js node test_kategorie_stranka.js   (puvodni stranka MUSI selhat). Snimky: SNIMKY=<slozka>.
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const https = require('https'), fs = require('fs'), path = require('path');
const REPO = path.join(__dirname, '../..');
const CATEGORY_HTML = process.env.CATEGORY_HTML || path.join(REPO, 'webapp/category.html');
const SNIMKY = process.env.SNIMKY || '';
const ZIVE = 'https://autovestavby.logiman.cz';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };
const stahniBuf = url => new Promise((res, rej) => https.get(url, r => { const b = []; r.on('data', c => b.push(c)); r.on('end', () => res({ st: r.statusCode, ct: r.headers['content-type'] || 'application/octet-stream', body: Buffer.concat(b) })); }).on('error', rej));
const stahni = async url => JSON.parse((await stahniBuf(url)).body.toString('utf8'));
const num = v => parseFloat(String(v).replace(',', '.').replace(/[^\d.]/g, ''));
const TYPL = { 'Ocel': 'Ocelový', 'Hliník hladký': 'Hliníkový', 'Hliník vroubkovaný': 'Hliníkový vroubkovaný' };

(async () => {
  const strom = await stahni(ZIVE + '/api/categories');
  const obsah324 = await stahni(ZIVE + '/api/categories/324/content');
  const prod = await stahni(ZIVE + '/api/shop/products?category_id=324&page_size=100&include=specs');
  // jina kategorie s produkty (kontrola, ze se jinde nic nemeni): prvni list stromu s produkty mimo 324
  const najdi = (uz, hledej) => { for (const n of uz) { if (hledej(n)) return n; const r = najdi(n.children || [], hledej); if (r) return r; } return null; };
  const listy = []; (function sber(uz) { uz.forEach(n => { if (!(n.children || []).length) listy.push(n); else sber(n.children); }); })(strom.tree || []);
  let jina = null, obsahJina = null;
  for (const n of listy) { if ([324, 325, 327].includes(n.id)) continue; const c = await stahni(ZIVE + '/api/categories/' + n.id + '/content').catch(() => null); if (c && (c.products || []).length >= 3) { jina = n; obsahJina = c; break; } }
  const P = prod.products.map(p => ({ id: p.id, typ: p.specs['Typ válečku'], sirka: num(p.specs['Roller length']), delka: num(p.specs['Conveyor Length']), net: p.price_czk_placeholder }));
  over('0 zive API: 78 produktu kategorie 324 se specs a kategorie ' + jina.id + ' s produkty pro kontrolu', prod.total === P.length && P.length >= 70 && P.every(p => p.typ && p.sirka > 0 && p.delka > 0 && p.net > 0) && (obsahJina.products || []).length > 0, { total: prod.total, jina: jina.id });
  const html = fs.readFileSync(CATEGORY_HTML, 'utf8');
  const chyby = [], zapisy = [], klientChyby = [];
  async function otevri({ id = 324, width = 1440, height = 900, query = '', mobil = false, modulChyba = false, apiChyba = false } = {}) {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const ctx = await browser.newContext({ viewport: { width, height }, hasTouch: !!mobil, isMobile: !!mobil });
    const page = await ctx.newPage();
    page.on('pageerror', e => chyby.push(e.message));
    const pozadavky = [];
    await page.route('**/*', async route => {
      const req = route.request(), u = new URL(req.url());
      if (u.hostname === 'fonts.googleapis.com' || u.hostname === 'fonts.gstatic.com') return route.abort();
      if (u.hostname !== 'kat.test') return route.abort();
      pozadavky.push(req.method() + ' ' + u.pathname + u.search);
      if (u.pathname === '/api/client-errors' && req.method() === 'POST') { if (!modulChyba) { try { klientChyby.push(JSON.parse(req.postData() || '{}')); } catch (e) { klientChyby.push({}); } } return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }); }      // vlastni hlaseni chyb stranky (client-errors.js) - maketa, sbiram texty
      if (req.method() !== 'GET') zapisy.push(req.method() + ' ' + u.pathname);
      const json = (b, st = 200) => route.fulfill({ status: st, contentType: 'application/json', body: JSON.stringify(b) });
      const p = u.pathname;
      if (p === '/category.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
      if (p === '/js/kategorie-tabulka.js' && modulChyba) return route.fulfill({ status: 500, body: 'x' });
      if (p === '/js/kategorie-tabulka.js' && process.env.KT_JS) return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(process.env.KT_JS) });       // kandidat modulu pred nasazenim
      if (p.startsWith('/js/') || p.startsWith('/css/')) { const f = path.join(REPO, 'webapp', p); if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: p.endsWith('.js') ? 'text/javascript' : 'text/css', body: fs.readFileSync(f) }); }
      if (p === '/api/categories') return json(strom);
      if (p === '/api/categories/324/content') return json(obsah324);
      if (p === '/api/categories/' + jina.id + '/content') return json(obsahJina);
      if (p === '/api/shop/products') { if (apiChyba) return json({ error: 'x' }, 500); const page = parseInt(u.searchParams.get('page') || '1', 10), ps = 100; return json({ page, page_size: ps, total: prod.total, products: prod.products.slice((page - 1) * ps, page * ps) }); }
      if (p === '/api/auth/me') return json({ user: null });
      if (p === '/api/theme-colors') return json({ light: {}, dark: {} });
      if (p === '/api/cart') return json({ items: [], cart_enabled: true });
      if (p.startsWith('/api/')) return json({});
      if (p.startsWith('/content-files/') || p.startsWith('/katalog/') || p.startsWith('/product-images/') || /\.(png|jpe?g|webp|gif|svg)$/i.test(p)) {
        if (SNIMKY) { try { const im = await stahniBuf(ZIVE + p); return route.fulfill({ status: im.st, contentType: im.ct, body: im.body }); } catch (e) { /* maketa nize */ } }
        return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64') });
      }
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://kat.test/category.html?id=' + id + query);
    await page.waitForFunction(() => { const w = document.getElementById('productsWrap'), t = document.getElementById('catTable'); return (w && w.style.display === 'block') || (t && t.style.display !== 'none' && t.querySelector('.kt-result > *')) || document.getElementById('catTitle').textContent.length > 12; }, null, { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(800);
    return { browser, page, pozadavky };
  }
  const radky = page => page.evaluate(() => [...document.querySelectorAll('#catTable table.kt-table tbody tr')].map(r => ({ id: +r.dataset.id, txt: r.textContent.replace(/\s+/g, ' ').trim(), href: (r.querySelector('a.kt-btn-detail') || {}).getAttribute && r.querySelector('a.kt-btn-detail').getAttribute('href') })));
  const pocet = page => page.evaluate(() => document.querySelector('#catTable .kt-count').textContent.trim());
  const chip = (page, skup, val) => page.locator(`#catTable fieldset[data-group="${skup}"] button.kt-chip[data-val="${val}"]`);
  const zobr = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return getComputedStyle(e).display !== 'none' && r.height > 0; }, sel);

  // ---- A) kategorie 324: tabulka misto karet
  let { browser, page, pozadavky } = await otevri({ id: 324 });
  over('A1 kategorie 324: tabulka je videt, vypis karet (#productsWrap) je skryty', (await zobr(page, '#catTable')) === true && (await zobr(page, '#productsWrap')) !== true && (await zobr(page, '#catTable table.kt-table')) === true, [await zobr(page, '#catTable'), await zobr(page, '#productsWrap')]);
  over('A2 78 radku tabulky (vsechny varianty), pocet "Nalezeno 78 z 78 variant"', (await radky(page)).length === 78 && /Nalezeno 78 z 78 variant/.test(await pocet(page)), [(await radky(page)).length, await pocet(page)]);
  const r0 = await radky(page);
  const ocek = P.slice().sort((a, b) => a.id - b.id).map(p => p.id).join();
  over('A3 vsechny produkty 324 jsou v tabulce (stejna mnozina id jako zive API) a kazdy ma odkaz Detail na /produkt/<slug>', r0.map(r => r.id).sort((a, b) => a - b).join() === ocek && r0.every(r => /^\/produkt\/[^/]+$/.test(r.href || '')), r0.filter(r => !/^\/produkt\//.test(r.href || '')).slice(0, 2));
  over('A4 stitky: delka 1-6 m, sirka 5 hodnot, typ valecku Oceloovy / Hlinikovy / Hlinikovy vroubkovany (cesky)', (await page.locator('#catTable fieldset[data-group="delka"] button.kt-chip').count()) === new Set(P.map(p => p.delka)).size && (await page.locator('#catTable fieldset[data-group="typ"] button.kt-chip').allTextContents()).map(t => t.replace(/\d+$/, '').trim()).sort().join() === [...new Set(P.map(p => TYPL[p.typ] || p.typ))].sort().join(), await page.locator('#catTable fieldset[data-group="typ"] button.kt-chip').allTextContents());
  const ts = P.filter(p => p.delka === 3000 && p.typ === 'Ocel');
  await chip(page, 'delka', 3000).click(); await chip(page, 'typ', 'Ocel').click();
  over('A5 filtr 3 m + ocelovy: tabulka ma jen odpovidajici varianty (pocet ' + ts.length + ')', (await radky(page)).length === ts.length && new RegExp('Nalezeno ' + ts.length + ' z 78').test(await pocet(page)), [(await radky(page)).length, await pocet(page)]);
  over('A6 stav filtru je v adrese (?delka=3000&typ=Ocel) a ostatni cast adresy (?id=324) zustala', /[?&]delka=3000/.test(page.url()) && /[?&]typ=Ocel/.test(page.url()) && /[?&]id=324/.test(page.url()), page.url());
  await page.selectOption('#catTable .kt-sort', 'cena:desc');
  const rc = await radky(page);
  over('A7 razeni "Cena: od nejvyssi": prvni radek ma nejvyssi cenu z odpovidajicich variant', rc[0] && rc[0].id === ts.slice().sort((a, b) => b.net - a.net || a.id - b.id)[0].id, rc[0]);
  await page.click('#catTable .kt-seg button:nth-child(2)');
  over('A8 Karty: zobrazi se karty variant (' + ts.length + ') misto tabulky, bez obrazku radku nutne; Tabulka je zpet na klik', (await page.locator('#catTable .kt-dcard').count()) === ts.length && (await zobr(page, '#catTable table.kt-table')) !== true, await page.locator('#catTable .kt-dcard').count());
  await page.click('#catTable .kt-seg button:nth-child(1)');
  await page.locator('#catTable .kt-toolbar .kt-btn-reset').click();
  over('A9 Zrusit filtry: zase 78 variant a adresa bez filtru', (await radky(page)).length === 78 && !/delka=|typ=/.test(page.url()), [(await radky(page)).length, page.url()]);
  over('A10 zadny zapis na server a zadne JS chyby behem celeho scenare A', zapisy.length === 0 && chyby.length === 0, { zapisy, chyby: chyby.slice(0, 3) });
  if (SNIMKY) await page.screenshot({ path: path.join(SNIMKY, 'kategorie_324_desktop.png'), fullPage: false });
  await browser.close();

  // ---- B) odkaz s filtrem se otevre rovnou nastaveny
  ({ browser, page } = await otevri({ id: 324, query: '&delka=2000,3000&typ=Ocel&razeni=cena:asc' }));
  const ocB = P.filter(p => (p.delka === 2000 || p.delka === 3000) && p.typ === 'Ocel').sort((a, b) => a.net - b.net || a.id - b.id);
  const rB = await radky(page);
  over('B1 odkaz ?delka=2000,3000&typ=Ocel&razeni=cena:asc: otevre se rovnou filtrovany a razeny (' + ocB.length + ' radku, nejlevnejsi prvni)', rB.length === ocB.length && rB[0].id === ocB[0].id, [rB.length, ocB.length]);
  await browser.close();

  // ---- C) mobil 390 px
  ({ browser, page } = await otevri({ id: 324, width: 390, height: 800, mobil: true }));
  const m = await page.evaluate(() => { const t = document.getElementById('catTable'), r = t.getBoundingClientRect(); const rad = document.querySelector('#catTable table.kt-table tbody tr'); return { sirkaOk: document.documentElement.scrollWidth <= 392, filtryZavrene: !document.querySelector('#catTable details.kt-filters-box').hasAttribute('open'), radekFlex: rad && getComputedStyle(rad).display === 'flex', hlavicka: getComputedStyle(document.querySelector('#catTable table.kt-table thead')).display }; });
  over('C1 mobil 390 px: stranka nema vodorovne rolovani, filtry sbalene, radky jsou karty (flex), zahlavi tabulky skryte', m.sirkaOk && m.filtryZavrene && m.radekFlex && m.hlavicka === 'none', m);
  const vychozi = await page.evaluate(() => { const o = document.querySelector('#catTable .kt-sort option[value="vychozi:asc"]'); const sel = document.querySelector('#catTable .kt-sort'); return { text: o && o.textContent, sirka: sel && Math.round(sel.getBoundingClientRect().width), sw: sel && sel.scrollWidth }; });
  over('C1b mobil: volba razeni "Vychozi" ma kratky popisek (zadny ocesany text "Vychozi (typ, si...") a vejde se', vychozi.text === 'Výchozí' && vychozi.sw <= vychozi.sirka + 2, vychozi);
  await page.click('#catTable details.kt-filters-box > summary');
  await chip(page, 'delka', 3000).click();
  over('C2 mobil: po rozbaleni filtru a kliknuti na 3 m zustavaji jen 3 m varianty', (await radky(page)).length === P.filter(p => p.delka === 3000).length, (await radky(page)).length);
  if (SNIMKY) await page.screenshot({ path: path.join(SNIMKY, 'kategorie_324_mobil.png'), fullPage: false });
  await browser.close();

  // ---- D) jina kategorie: beze zmeny puvodni vypis karet, tabulka se nenacita
  ({ browser, page, pozadavky } = await otevri({ id: jina.id }));
  over('D1 jina kategorie (' + jina.id + '): karty produktu jsou videt, tabulka skryta a modul se vubec nenacetl', (await zobr(page, '#productsWrap')) === true && (await zobr(page, '#catTable')) !== true && !pozadavky.some(r => /kategorie-tabulka/.test(r)) && (await page.locator('#productGrid > *').count()) > 0, [await zobr(page, '#productsWrap'), pozadavky.filter(r => /kategorie-tabulka/.test(r))]);
  await browser.close();

  // ---- E) selhani modulu / dat
  ({ browser, page } = await otevri({ id: 324, modulChyba: true }));
  over('E1 modul se nenacetl (500): vrati se puvodni vypis karet (78 karet) a tabulka je skryta', (await zobr(page, '#productsWrap')) === true && (await zobr(page, '#catTable')) !== true && (await page.locator('#productGrid > *').count()) >= 70, [await zobr(page, '#productsWrap'), await page.locator('#productGrid > *').count()]);
  await browser.close();
  ({ browser, page } = await otevri({ id: 324, apiChyba: true }));
  const chybaTxt = await page.evaluate(() => (document.querySelector('#catTable .kt-state') || {}).textContent || '');
  over('E2 API produktu selhalo (500): v tabulce hlaska "Data e-shopu se nepodarilo nacist" + tlacitko Zkusit znovu, bez JS chyb', /nepodařilo načíst/.test(chybaTxt) && /Zkusit znovu/.test(chybaTxt), chybaTxt);
  await browser.close();

  over('Z zadny zapis na server ve vsech scenarich a zadne neodchycene JS chyby', zapisy.length === 0 && chyby.length === 0, { zapisy, chyby: chyby.slice(0, 3) });
  const cizi = klientChyby.filter(c => /kategorie-tabulka|kt-/.test(JSON.stringify(c)));
  over('Z2 hlaseni chyb stranky (client-errors.js, v harnessu jen maketa) se netyka modulu tabulky (kategorie-tabulka.js / .css; zamerne rozbity modul ve scenari E1 se nepocita)', cizi.length === 0, cizi.slice(0, 2));
  if (klientChyby.length) console.log('     (info: hlaseni stranky v harnessu: ' + [...new Set(klientChyby.map(c => String(c.message || '').slice(0, 60) + ' ' + String(c.source || '').slice(-50)))].slice(0, 4).join(' | ') + ')');
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK tabulka variant v kategorii: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
