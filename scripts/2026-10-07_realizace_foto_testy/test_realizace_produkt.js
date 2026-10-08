// Blok "Souvisejici priklady realizace" na SKUTECNE strance produktu webapp/product.html (bot16, 2026-10-07; Robert: "v kazde sestave do aut i stolu musi byt ukazana realna fotografie 4ks a odkaz na fotogalerii,
// ty 4 fotky se musi tocit, kolovat ... jako souvisejici priklad realizace"). SKUTECNA stranka + modul v Chromiu; data ZIVA z e-shopu (read-only: /api/categories, /api/shop/products/<id>, /api/gallery),
// soubory fotek z disku; ostatni server je maketa (zadne zapisy). Karty: sestava do auta (koren 184), sestava stolu (generator #4955 + bezny stul), Vandr bez kategorie, profil a dopravnik (BEZ bloku).
// Kandidat: PRODUCT_HTML=/cesta/product.html RF_JS=/cesta/realizace-foto.js node test_realizace_produkt.js   (puvodni stranka MUSI selhat). Snimky: SNIMKY=<slozka>.
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs'), path = require('path');
const { REPO, ZIVE, stahni, nactiGalerie, galerieRoute } = require('./harness_realizace');
const PRODUCT_HTML = process.env.PRODUCT_HTML || path.join(REPO, 'webapp/product.html');
const RF_JS = process.env.RF_JS || '';
const SNIMKY = process.env.SNIMKY || '';
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail).slice(0, 400))); };

(async () => {
  const G = await nactiGalerie();
  const strom = await stahni(ZIVE + '/api/categories');
  const uzly = []; (function sber(a) { a.forEach(n => { uzly.push(n); sber(n.children || []); }); })(strom.tree || []);
  const potomci = (id) => { const o = []; (function sb(n) { (n.children || []).forEach(c => { o.push(c.id); sb(c); }); })(uzly.find(n => n.id === id)); return o; };
  async function prvniProdukty(korenId, kolik) {
    const out = [];
    for (const cid of [korenId, ...potomci(korenId)]) {
      const c = await stahni(ZIVE + '/api/categories/' + cid + '/content').catch(() => null);
      for (const p of ((c && c.products) || [])) { if (p.id && !out.includes(p.id)) out.push(p.id); if (out.length >= kolik) return out; }
    }
    return out;
  }
  const auta = await prvniProdukty(184, 3), stoly = [4930], profily = await prvniProdukty(154, 1), dopravniky = await prvniProdukty(324, 1);
  over('0 zive produkty pro test: >= 2 auta, soucast stolu (#4930 suplikovy box v kat. 200 pod Ergonomickymi stoly), profil, dopravnik', auta.length >= 2 && stoly.length === 1 && profily.length === 1 && dopravniky.length === 1, { auta, stoly, profily, dopravniky });
  const produkty = {};
  for (const id of [...auta, ...stoly, 4934, 4954, 4955, ...profily, ...dopravniky]) produkty[id] = await stahni(ZIVE + '/api/shop/products/' + id);
  const html = fs.readFileSync(PRODUCT_HTML, 'utf8');
  const chyby = {}, zapisy = [];
  async function otevri(id, { sirka = 1440, upravProdukt = null, galerieChyba = false } = {}) {
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const ctx = await browser.newContext({ viewport: { width: sirka, height: 1000 } });
    const page = await ctx.newPage();
    const ch = chyby[id + (upravProdukt ? 'u' : '')] = [];
    page.on('pageerror', e => ch.push(e.message));
    const pozadavky = [];
    await page.route('**/*', async route => {
      const req = route.request(), u = new URL(req.url());
      if (u.hostname === 'fonts.googleapis.com' || u.hostname === 'fonts.gstatic.com') return route.abort();
      if (u.hostname !== 'prod.test') return route.abort();
      pozadavky.push(req.method() + ' ' + u.pathname + u.search);
      if (req.method() !== 'GET' && u.pathname !== '/api/client-errors') zapisy.push(req.method() + ' ' + u.pathname);
      const json = (b, st = 200) => route.fulfill({ status: st, contentType: 'application/json', body: JSON.stringify(b) });
      const p = u.pathname;
      if (p === '/product.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: html });
      if (p === '/js/realizace-foto.js' && RF_JS) return route.fulfill({ status: 200, contentType: 'text/javascript', body: fs.readFileSync(RF_JS) });
      if (p.startsWith('/js/') || p.startsWith('/css/')) { const f = path.join(REPO, 'webapp', p); if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: p.endsWith('.js') ? 'text/javascript' : 'text/css', body: fs.readFileSync(f) }); }
      if (galerieRoute(route, u, G, { galerieChyba })) return;
      if (p === '/api/categories') return json(strom);
      const m = /^\/api\/shop\/products\/(\d+)$/.exec(p);
      if (m && produkty[m[1]]) { const d = JSON.parse(JSON.stringify(produkty[m[1]])); if (upravProdukt) upravProdukt(d); return json(d); }
      if (p === '/api/auth/me') return json({ user: null });
      if (p === '/api/theme-colors') return json({ light: {}, dark: {} });
      if (p === '/api/cart') return json({ items: [], cart_enabled: true });
      if (p.startsWith('/api/')) return json({});
      if (/\.(png|jpe?g|webp|gif|svg)$/i.test(p) || p.startsWith('/content-files/') || p.startsWith('/katalog/')) return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64') });
      return route.fulfill({ status: 404, body: '' });
    });
    await page.goto('http://prod.test/product.html?id=' + id);
    await page.waitForFunction(() => { const t = document.getElementById('pdTitle'); return t && t.textContent && t.textContent !== 'Načítám…'; }, null, { timeout: 20000 }).catch(() => {});
    await page.waitForTimeout(1200);
    return { browser, page, pozadavky };
  }
  const blok = page => page.evaluate(() => {
    const w = document.getElementById('pdRealizaceWrap'); if (!w) return { existuje: false };
    const vid = getComputedStyle(w).display !== 'none' && w.getBoundingClientRect().height > 0;
    const imgs = [...w.querySelectorAll('.rf-foto img')];
    const a = w.querySelector('a.rf-link');
    return { existuje: true, viditelny: vid, nadpis: (w.querySelector('h2') || {}).textContent, fotek: imgs.length, nactene: imgs.filter(i => i.complete && i.naturalWidth > 0).length, ids: [...w.querySelectorAll('.rf-foto')].map(b => b.dataset.rfId), odkaz: a && { href: a.getAttribute('href'), text: a.textContent.trim(), target: a.target }, poradi: (() => { const r = document.getElementById('pdRelatedWrap'), u = document.getElementById('pdUsageWrap'); const k = [...document.getElementById('pdContent').children]; return { dopoRelated: k.indexOf(w) > k.indexOf(r), predUsage: k.indexOf(w) < k.indexOf(u) }; })() };
  });

  // ---- A) auta (koren 184)
  const sadyAut = [];
  for (const id of auta.slice(0, 2)) {
    const { browser, page } = await otevri(id); const b = await blok(page);
    over(`A auto #${id} (${produkty[id].product.name.slice(0, 40)}): blok "Souvisejici priklady realizaci" je videt, 4 fotky vestaveb se nacetly, odkaz na fotogalerii vestaveb`, b.viditelny && /^Související příklady realizací$/.test(String(b.nadpis).trim()) && b.fotek === 4 && b.nactene === 4 && b.odkaz && b.odkaz.href === '/realizace.html?category=vestavby_dodavek' && /vestaveb/.test(b.odkaz.text) && b.odkaz.target === '_blank', b);
    over(`A auto #${id}: blok je pod "Souvisejici produkty" a pred "Ukazkou pouziti"`, b.poradi && b.poradi.dopoRelated && b.poradi.predUsage, b.poradi);
    sadyAut.push(b.ids.join(','));
    if (SNIMKY && id === auta[0]) { await page.evaluate(() => document.getElementById('pdRealizaceWrap').scrollIntoView({ block: 'center' })); await page.waitForTimeout(500); await page.screenshot({ path: path.join(SNIMKY, 'produkt_auto.png') }); }
    await browser.close();
  }
  over('A ruzne karty aut maji RUZNE sady 4 fotek (kazda karta jine)', sadyAut.length === 2 && sadyAut[0] !== sadyAut[1], sadyAut);

  // ---- A2) F5 na karte (Robert 2026-10-08: "reloaduju F5 a nactou se stale tytez"): kazde nacteni stranky ukaze 4 NOVE fotky (stejny prohlizec = sdileny localStorage)
  {
    const { browser, page } = await otevri(auta[0]); const sady = [(await blok(page)).ids.join(',')];
    for (let k = 0; k < 3; k++) { await page.reload(); await page.waitForTimeout(1800); sady.push((await blok(page)).ids.join(',')); }
    const ids = sady.map(x => x.split(',')), spolecne = ids.slice(1).map((x, i) => x.filter(v => ids[i].includes(v)).length);
    over('A2 F5 na karte auta: 4 nacteni za sebou = 4 ruzne sady a zadne dve sousedni nemaji spolecnou fotku', new Set(sady).size === 4 && ids.every(x => x.length === 4) && spolecne.every(n => n === 0), [sady, spolecne]);
    await browser.close();
  }

  // ---- B) stoly: tri generatory (#4934 system 30, #4954 system 40, #4955 system 35 - karty bez category_id, kategorie podle mapovani generatoru) a soucast stolu v kategorii 200
  const sadyStolu = [];
  for (const id of [4955, 4954, 4934, ...stoly]) {
    const { browser, page } = await otevri(id); const b = await blok(page);
    over(`B stul #${id} (${produkty[id].product.name.slice(0, 40)}): blok je videt, 4 fotky stolu a odkaz na fotogalerii stolu`, b.viditelny && b.fotek === 4 && b.nactene === 4 && b.odkaz && b.odkaz.href === '/realizace.html?category=realizace_stolu' && /stolů/.test(b.odkaz.text), b);
    sadyStolu.push(b.ids.join(','));
    if (SNIMKY && id === 4955) { await page.evaluate(() => document.getElementById('pdRealizaceWrap').scrollIntoView({ block: 'center' })); await page.waitForTimeout(500); await page.screenshot({ path: path.join(SNIMKY, 'produkt_stul.png') }); }
    await browser.close();
  }

  over('B ruzne karty stolu maji RUZNE sady 4 fotek (kazda karta jine)', new Set(sadyStolu).size === sadyStolu.length, sadyStolu);

  // ---- C) Vandr karta bez kategorie = vestavby; profil a dopravnik = bez bloku
  { const { browser, page } = await otevri(auta[0], { upravProdukt: d => { d.product.category_id = null; d.product.supplier_name = 'vanDrawee'; } }); const b = await blok(page);
    over('C Vandr karta (dodavatel vanDrawee) bez kategorie: blok s fotkami vestaveb', b.viditelny && b.fotek === 4 && b.odkaz.href.endsWith('vestavby_dodavek'), b); await browser.close(); }
  for (const [nazev, id] of [['profil', profily[0]], ['dopravnik', dopravniky[0]]]) {
    const { browser, page, pozadavky } = await otevri(id); const b = await blok(page);
    over(`C ${nazev} #${id}: BEZ bloku realizaci (neni to sestava do auta ani stul) a galerie se ani nenacita`, b.existuje && !b.viditelny && b.fotek === 0 && !pozadavky.some(r => /\/api\/gallery/.test(r)), [b, pozadavky.filter(r => /gallery/.test(r))]);
    await browser.close();
  }

  // ---- D) mobil a chyba galerie
  { const { browser, page } = await otevri(auta[0], { sirka: 390 });
    const m = await page.evaluate(() => ({ sloupcu: getComputedStyle(document.querySelector('#pdRealizaceWrap .rf-grid')).gridTemplateColumns.split(' ').length, preteka: document.documentElement.scrollWidth > innerWidth + 2 }));
    over('D mobil 390 px: 2 sloupce fotek a nic nepreteka', m.sloupcu === 2 && !m.preteka, m);
    if (SNIMKY) { await page.evaluate(() => document.getElementById('pdRealizaceWrap').scrollIntoView({ block: 'center' })); await page.waitForTimeout(500); await page.screenshot({ path: path.join(SNIMKY, 'produkt_mobil.png') }); }
    await browser.close(); }
  { const { browser, page } = await otevri(auta[0], { galerieChyba: true }); const b = await blok(page);
    over('D galerie nedostupna (500): blok se nezobrazi, stranka produktu funguje dal (nadpis produktu je)', b.existuje && !b.viditelny && (await page.locator('#pdTitle').textContent()).length > 3, b); await browser.close(); }
  over('Z zadny zapis na server a zadne NOVE JS chyby proti puvodni strance (porovnani s puvodni product.html)', zapisy.length === 0, zapisy);
  const nove = Object.entries(chyby).filter(([k, v]) => v.some(e => /RealizaceFoto|realizace|Realizace/.test(e)));
  over('Z zadna JS chyba nesouvisi s blokem realizaci', nove.length === 0, nove);
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK blok realizaci na strance produktu: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
