// Storefronty (domeny BEZ znacky): blok "Souvisejici priklady realizaci" na strance produktu storefront-product.html a neutralni fotogalerie storefront-galerie.html (bot16, 2026-10-07; Robert: "v kazde
// sestave do aut ... realna fotografie 4ks a odkaz na fotogalerii vestaveb"). TEXT_FILTR pravidlo 5: zadna zminka znacky v HTML ani v nacitanych .js/.css (QA static_page_brand_leak) - test pouziva STEJNY vzor jako QA
// a navic kontroluje VYSLEDNY DOM (zadna fotka se znackou v nazvu). SKUTECNE soubory + modul v Chromiu, ZIVA galerie (read-only), soubory fotek z disku. Kandidat: SFP_HTML=/cesta/storefront-product.html SFG_HTML=/cesta/storefront-galerie.html RF_JS=/cesta/realizace-foto.js node test_realizace_storefront.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs'), path = require('path');
const { REPO, nactiGalerie, galerieRoute } = require('./harness_realizace');
const SFP = process.env.SFP_HTML || path.join(REPO, 'webapp/storefront-product.html');
const SFG = process.env.SFG_HTML || path.join(REPO, 'webapp/storefront-galerie.html');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };
const ZNACKA = /logiman|konfigur[áa]tor|vandrawee/i, ROZDELENE = /logi\s*(?:<[^>]*>\s*)*man\b/i;      // vzor QA static_page_brand_leak (api/qa_checks.py)
const znacky = t => [...(t.match(new RegExp(ZNACKA.source, 'gi')) || []), ...(t.match(new RegExp(ROZDELENE.source, 'gi')) || [])];

(async () => {
  const G = await nactiGalerie();
  const sfpHtml = fs.readFileSync(SFP, 'utf8'), sfgHtml = fs.existsSync(SFG) ? fs.readFileSync(SFG, 'utf8') : '';
  const RF_JS = process.env.RF_JS || path.join(REPO, 'webapp/js/realizace-foto.js');
  const modul = fs.readFileSync(RF_JS, 'utf8');
  over('0 QA vzor znacky (logiman / konfigurator / vandrawee, rozdelene logo): ZADNY vyskyt v storefront-product.html, storefront-galerie.html ani v js/realizace-foto.js', znacky(sfpHtml).length === 0 && znacky(sfgHtml).length === 0 && znacky(modul).length === 0, [znacky(sfpHtml), znacky(sfgHtml), znacky(modul)]);
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const chyby = [], zapisy = [];
  async function otevri(url, html, { produkt = null, galerieChyba = false, sirka = 1280 } = {}) {
    const ctx = await browser.newContext({ viewport: { width: sirka, height: 900 } });
    const page = await ctx.newPage();
    page.on('pageerror', e => chyby.push(e.message));
    await page.route('**/*', async route => {
      const req = route.request(), u = new URL(req.url());
      if (u.hostname !== 'sf.test') return route.abort();
      if (req.method() !== 'GET' && u.pathname !== '/api/client-errors') zapisy.push(req.method() + ' ' + u.pathname);
      const p = u.pathname;
      if (p === '/produkt') { let h = html; if (produkt) h = h.replace('<div id="sfPdCartBtn"></div>', '<div id="sfPdCartBtn"><button class="sf-add-cart-btn" data-product-id="' + produkt + '">Do košíku</button></div>'); return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: h }); }
      if (p === '/storefront-galerie.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
      if (p === '/js/realizace-foto.js') return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(RF_JS) });
      if (p.startsWith('/js/')) { const f = path.join(REPO, 'webapp', p); if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(f) }); }
      if (galerieRoute(route, u, G, { galerieChyba })) return;
      if (p.startsWith('/api/')) return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://sf.test' + url);
    await page.waitForTimeout(1500);
    return { page, ctx };
  }
  const blok = page => page.evaluate(() => { const w = document.getElementById('sfRealizace'); if (!w) return { existuje: false }; const imgs = [...w.querySelectorAll('.rf-foto img')], a = w.querySelector('a.rf-link');
    return { existuje: true, viditelny: !w.hidden && w.getBoundingClientRect().height > 0, nadpis: (w.querySelector('h2') || {}).textContent, fotek: imgs.length, nactene: imgs.filter(i => i.complete && i.naturalWidth > 0).length, ids: [...w.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId).join(','), srcs: imgs.map(i => i.getAttribute('src')), odkaz: a && { href: a.getAttribute('href'), text: a.textContent.trim() } }; });

  // ---- A) produkt storefrontu
  const sady = [];
  for (const id of [4499, 4515]) {
    const { page, ctx } = await otevri('/produkt', sfpHtml, { produkt: id }); const b = await blok(page);
    over(`A karta #${id}: blok "Souvisejici priklady realizaci" je videt, 4 fotky vestaveb, odkaz "Zobrazit fotogalerii vestaveb" vede na neutralni /storefront-galerie.html`, b.viditelny && /^Související příklady realizací$/.test(String(b.nadpis).trim()) && b.fotek === 4 && b.nactene === 4 && b.odkaz.href === '/storefront-galerie.html' && /vestaveb/.test(b.odkaz.text), b);
    over(`A karta #${id}: v ZADNE ze 4 zobrazenych fotek neni v nazvu souboru znacka (vybirani bezZnacky)`, b.srcs.every(s => !ZNACKA.test(s) && !/vandr/i.test(s)), b.srcs);
    sady.push(b.ids);
    if (process.env.SNIMKY && id === 4499) { await page.evaluate(() => document.getElementById('sfRealizace').scrollIntoView({ block: 'center' })); await page.waitForTimeout(400); await page.screenshot({ path: path.join(process.env.SNIMKY, 'storefront_produkt.png') }); }
    await ctx.close();
  }
  over('A ruzne karty maji RUZNE sady 4 fotek', sady[0] !== sady[1], sady);
  { const { page, ctx } = await otevri('/produkt', sfpHtml, { produkt: 4499, galerieChyba: true }); const b = await blok(page);
    over('A galerie nedostupna (500): blok zustane skryty', b.existuje && !b.viditelny, b); await ctx.close(); }
  { const { page, ctx } = await otevri('/produkt', sfpHtml, { produkt: 4499, sirka: 390 }); const m = await page.evaluate(() => ({ sloupcu: getComputedStyle(document.querySelector('#sfRealizace .rf-grid')).gridTemplateColumns.split(' ').length, preteka: document.documentElement.scrollWidth > innerWidth + 2 }));
    over('A mobil 390 px: 2 sloupce fotek a nic nepreteka', m.sloupcu === 2 && !m.preteka, m); await ctx.close(); }

  // ---- B) neutralni galerie
  { const { page, ctx } = await otevri('/storefront-galerie.html', sfgHtml);
    const g = await page.evaluate(() => ({ vyl: window.RealizaceFoto.VYLOUCENE.vestavby, ids: [...document.querySelectorAll('#sfGalerie .rf-foto')].map(b => Number(b.dataset.rfId)), fotek: document.querySelectorAll('#sfGalerie .rf-foto img').length, stav: document.getElementById('sfGalerieStav').textContent, srcs: [...document.querySelectorAll('#sfGalerie .rf-foto img')].map(i => i.getAttribute('src')), titulek: document.title, h1: document.querySelector('h1').textContent, html: document.documentElement.outerHTML }));
    const bez = G.vestavby.images.filter(i => !ZNACKA.test(i.filename + ' ' + (i.title || '') + ' ' + (i.alt_text || '')) && !/vandr/i.test(i.filename + ' ' + (i.title || '') + ' ' + (i.alt_text || '')) && !g.vyl.includes(i.id)).length;
    over(`B galerie: zobrazeny VSECHNY fotky bez znacky v nazvu a bez vyloucenych rendru (${bez} z ${G.vestavby.images.length}), zadna se znackou v nazvu ani vyloucena, stav "Nacitam" zmizel`, g.fotek === bez && g.srcs.every(s => !ZNACKA.test(s) && !/vandr/i.test(s)) && g.ids.every(i => !g.vyl.includes(i)) && g.stav === '', [g.fotek, bez, g.stav, g.ids.filter(i => g.vyl.includes(i))]);
    over('B galerie: VYSLEDNY DOM (po nacteni fotek) neobsahuje zadnou zminku znacky (pravidlo 5)', znacky(g.html).length === 0, znacky(g.html));
    await page.locator('#sfGalerie .rf-foto').nth(2).click();
    const lb = await page.evaluate(() => { const l = document.querySelector('.rf-lb'); return { otevreno: l && l.classList.contains('rf-open'), cap: l && l.querySelector('figcaption').textContent }; });
    over('B galerie: klik na fotku otevre zvetseni s poctem "(3 / N)"', lb.otevreno && /\(3 \/ \d+\)/.test(lb.cap), lb);
    if (process.env.SNIMKY) { await page.keyboard.press('Escape'); await page.screenshot({ path: path.join(process.env.SNIMKY, 'storefront_galerie.png') }); }
    await ctx.close(); }
  { const { page, ctx } = await otevri('/storefront-galerie.html', sfgHtml, { galerieChyba: true });
    const stav = await page.evaluate(() => document.getElementById('sfGalerieStav').textContent);
    over('B galerie nedostupna (500): srozumitelna hlaska misto prazdne stranky', /nepodařilo načíst/.test(stav), stav); await ctx.close(); }
  over('Z zadne zapisy na server a zadne neodchycene JS chyby', zapisy.length === 0 && chyby.length === 0, { zapisy, chyby: chyby.slice(0, 3) });
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK realizace na storefrontech: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
