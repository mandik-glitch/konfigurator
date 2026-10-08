// Dlazdice slouceneho modelu "Vestavby pro Ducato, Jumper, Boxer" (kategorie 233) ukazuje 3 znackova loga vedle sebe (Fiat, Citroën, Peugeot) - bot16, 2026-10-06.
// Robert: "vytvori se slucena vcetne 3 log u sebe". Dve cesty musi davat totez (DRZET SYNCHRONNI): klient webapp/category.html (renderSubcats) a SSR api/storefront_pages.py (_brand_thumb_html).
// SKUTECNA stranka category.html v Chromiu proti falesnemu API (page.route, zadna DB, zadna sit) + SSR pomocna funkce vytazena ze zdroje a spustena bez aplikace.
// Kandidat pred nasazenim:  CATEGORY_HTML=<kandidat>/category.html SSR_PY=<kandidat>/storefront_pages.py node test_vice_log.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const REPO = path.join(__dirname, '../..');
const WEB = path.join(REPO, 'webapp');
const HTML = fs.readFileSync(process.env.CATEGORY_HTML || path.join(WEB, 'category.html'), 'utf8');
const SSR = process.env.SSR_PY || path.join(REPO, 'api/storefront_pages.py');
const TYPY = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp' };
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

const uzel = (id, name, slug, deti) => ({ id, name, slug, nav_label: name, children: deti || [], image_url: null });
const STROM = [uzel(184, 'Vestavby do dodávek, aut', 'vestavby-do-dodavek-aut', [
  uzel(247, 'Regály do auta', 'regaly-do-auta'),
  uzel(267, 'Vestavby podle vozidla', 'vestavby-podle-vozidla', [
    uzel(233, 'Vestavby pro Ducato, Jumper, Boxer', 'vestavby-pro-ducato-jumper-boxer'),
    uzel(268, 'Vestavby pro Citroën', 'vestavby-pro-citroen', [uzel(272, 'Vestavby pro Citroën Jumpy', 'vestavby-pro-citroen-jumpy')]),
    uzel(269, 'Vestavby pro Fiat', 'vestavby-pro-fiat', [uzel(273, 'Vestavby pro Fiat Doblò', 'vestavby-pro-fiat-doblo')]),
    uzel(288, 'Vestavby pro Peugeot', 'vestavby-pro-peugeot', [uzel(310, 'Vestavby pro Peugeot Expert', 'vestavby-pro-peugeot-expert')]),
    uzel(270, 'Vestavby pro Mercedes', 'vestavby-pro-mercedes', []),
  ]),
])];
const nazev = id => { const f = (u) => { for (const n of u) { if (n.id === id) return n; const x = f(n.children || []); if (x) return x; } return null; }; return f(STROM); };

async function otevri(browser, id, w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, locale: 'cs-CZ' });
  const page = await ctx.newPage(); const chyby = [];
  page.on('pageerror', e => chyby.push(e.message));
  await page.route('**/*', route => {
    const u = new URL(route.request().url());
    if (u.hostname !== 'kat.test') return route.abort();
    const p = u.pathname, json = b => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(b) });
    if (p === '/category.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: HTML });
    if (p === '/api/categories') return json({ tree: STROM, cart_enabled: true });
    const m = /^\/api\/categories\/(\d+)\/content$/.exec(p);
    if (m) { const n = nazev(+m[1]); return json({ category: { id: +m[1], name: n ? n.name : 'x', slug: n ? n.slug : 'x', intro_html: '', body_html: '', bottom_body_html: '' }, products: [], gallery_items: [], files: [], usage_images: [], page: { intro_html: '', body_html: '', bottom_body_html: '' }, facets: { cross_sections: [], groove_families: [] }, total_products: 0 }); }
    if (p.startsWith('/api/')) return json({});
    const f = path.join(WEB, p === '/' ? 'index.html' : p);
    if (f.startsWith(WEB) && fs.existsSync(f) && fs.statSync(f).isFile()) return route.fulfill({ status: 200, contentType: TYPY[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
    return route.fulfill({ status: 404, body: 'nf' });
  });
  await page.goto('http://kat.test/category.html?id=' + id, { waitUntil: 'load' });
  await page.waitForSelector('#subcatsList li', { timeout: 15000 });
  await page.waitForTimeout(300);
  return { ctx, page, chyby };
}
const dlazdice = page => page.evaluate(() => [...document.querySelectorAll('#subcatsList li')].map(li => {
  const m = li.querySelector('.cs-media'); const sv = m ? [...m.querySelectorAll('svg')] : [];
  const r = m ? m.getBoundingClientRect() : null;
  return { href: li.querySelector('a').getAttribute('href'), nazev: li.querySelector('.cs-name').textContent, brand: !!(m && m.classList.contains('cs-media-brand')), multi: !!(m && m.classList.contains('cs-media-brand-multi')),
    svg: sv.map(s => s.innerHTML), rects: sv.map(s => { const b = s.getBoundingClientRect(); return { l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width }; }), tile: r ? { l: r.left, r: r.right, t: r.top, b: r.bottom } : null };
}));

(async () => {
  const browser = await chromium.launch();
  console.log('== A) klient (category.html): strom Vestavby podle vozidla (kategorie 267)');
  for (const [w, h] of [[1400, 900], [390, 800]]) {
    const { ctx, page, chyby } = await otevri(browser, 267, w, h);
    const d = await dlazdice(page);
    const L = await page.evaluate(() => { const n = x => { const t = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); t.innerHTML = BRAND_LOGOS[x]; return t.innerHTML; }; return { f: n(269), c: n(268), p: n(288) }; });   // innerHTML normalizovane prohlizecem (<path/> -> <path></path>)
    const sl = d.find(x => x.href.includes('vestavby-pro-ducato-jumper-boxer'));
    over(`A ${w}px: sloucena dlazdice je mezi podkategoriemi 267 (${d.length} dlazdic)`, !!sl && d.length === 5, d.map(x => x.nazev));
    over(`A ${w}px: ma 3 loga v poradi Fiat, Citroën, Peugeot (cesty z BRAND_LOGOS 269, 268, 288)`, sl && sl.brand && sl.multi && sl.svg.length === 3 && sl.svg[0] === L.f && sl.svg[1] === L.c && sl.svg[2] === L.p, sl && sl.svg.map(s => s.slice(0, 20)));
    over(`A ${w}px: loga se vejdou do dlazdice a nepretinaji se`, sl && sl.rects.length === 3 && sl.tile && sl.rects.every(r => r.l >= sl.tile.l - 0.5 && r.r <= sl.tile.r + 0.5 && r.t >= sl.tile.t - 0.5 && r.b <= sl.tile.b + 0.5) && sl.rects[0].r <= sl.rects[1].l + 0.5 && sl.rects[1].r <= sl.rects[2].l + 0.5, sl && { rects: sl.rects, tile: sl.tile });
    const brand = d.filter(x => !x.href.includes('ducato-jumper-boxer') && x.brand);
    over(`A ${w}px: ostatni znackove dlazdice maji jedno logo (beze zmeny)`, brand.length === 4 && brand.every(x => !x.multi && x.svg.length === 1), brand.map(x => [x.nazev, x.svg.length]));
    over(`A ${w}px: zadne chyby JS`, chyby.length === 0, chyby.slice(0, 2));
    if (process.env.SNIMKY_DIR) await page.locator('#subcatsWrap').screenshot({ path: path.join(process.env.SNIMKY_DIR, 'dlazdice_' + w + '.png') });
    await ctx.close();
  }
  console.log('== B) klient: model-level podkategorie dedi logo rodice (beze zmeny)');
  {
    const { ctx, page } = await otevri(browser, 269, 1400, 900);
    const d = await dlazdice(page); const L = await page.evaluate(() => { const t = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); t.innerHTML = BRAND_LOGOS[269]; return t.innerHTML; });
    over('B Fiat -> Doblò: jedno logo Fiatu zdedene od rodice', d.length === 1 && d[0].brand && !d[0].multi && d[0].svg.length === 1 && d[0].svg[0] === L, d.map(x => [x.nazev, x.svg.length]));
    await ctx.close();
  }
  console.log('== C) SSR (api/storefront_pages.py): _brand_thumb_html bez spusteni aplikace');
  const zdrojPy = fs.readFileSync(SSR, 'utf8');
  const kod = (() => { const i = zdrojPy.indexOf('BRAND_LOGOS = {'), j = zdrojPy.indexOf('\n\n\n# QA nalez (2026-09-05, SEO_IMAGES_NOT_LAZY)'); return zdrojPy.slice(i, j); })();
  const skript = kod + `
import json
out = {"multi": _brand_thumb_html(233, 267), "dite": _brand_thumb_html(272, 268), "znacka": _brand_thumb_html(269, 267), "nic": _brand_thumb_html(999999, 267),
       "L": {"f": BRAND_LOGOS[269], "c": BRAND_LOGOS[268], "p": BRAND_LOGOS[288]}, "MULTI": {str(k): list(v) for k, v in BRAND_LOGOS_MULTI.items()}}
print(json.dumps(out))`;
  const ssr = JSON.parse(execFileSync('python3', ['-c', skript], { encoding: 'utf8' }));
  const svgs = h => (h.match(/<svg[\s\S]*?<\/svg>/g) || []);
  over('C SSR: 233 -> jedna dlazdice se 3 logy v poradi Fiat, Citroën, Peugeot', ssr.multi && ssr.multi.startsWith('<div class="cs-media cs-media-brand cs-media-brand-multi"><span class="cs-brand-corner"></span>') && svgs(ssr.multi).length === 3 && svgs(ssr.multi).map(s => s.replace(/^<svg[^>]*>|<\/svg>$/g, '')).join('|') === [ssr.L.f, ssr.L.c, ssr.L.p].join('|'), ssr.multi && ssr.multi.slice(0, 120));
  const STARE = z => `<div class="cs-media cs-media-brand"><span class="cs-brand-corner"></span><svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">${z}</svg></div>`;
  over('C SSR: znackova dlazdice (Fiat) a dite (Jumpy pod Citroënem) maji PRESNE puvodni HTML (jedno logo)', ssr.znacka === STARE(ssr.L.f) && ssr.dite === STARE(ssr.L.c), { znacka: (ssr.znacka || '').slice(0, 90) });
  over('C SSR: kategorie bez loga -> None (pouzije se obrazek jako dosud)', ssr.nic === null, ssr.nic);
  const jsMulti = /const BRAND_LOGOS_MULTI = (\{[^}]*\});/.exec(HTML);
  const jsM = jsMulti ? JSON.parse(jsMulti[1].replace(/(\d+):/g, '"$1":')) : null;
  over('C klient a SSR maji STEJNOU tabulku BRAND_LOGOS_MULTI (233: Fiat 269, Citroën 268, Peugeot 288)', jsM && JSON.stringify(jsM) === JSON.stringify(ssr.MULTI) && JSON.stringify(jsM) === '{"233":[269,268,288]}', { jsM, py: ssr.MULTI });
  const logaJs = [...HTML.matchAll(/^  (\d{3}): '(<path[^']*)'/gm)].reduce((o, m) => (o[m[1]] = m[2], o), {});
  over('C klient a SSR maji STEJNE cesty log (BRAND_LOGOS 268, 269, 288)', ['268', '269', '288'].every(k => logaJs[k] === (k === '269' ? ssr.L.f : k === '268' ? ssr.L.c : ssr.L.p)), Object.keys(logaJs));
  await browser.close();
  console.log(`\nVYSLEDEK vice log u slouceneho modelu: ${vysl.filter(Boolean).length}/${vysl.length} OK`);
  process.exit(vysl.every(Boolean) ? 0 : 1);
})();
