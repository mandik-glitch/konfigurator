// Harness skladove karty produktu: SKUTECNY webapp/admin.html + vsechny skripty z webapp/admin/js/ v Chromiu
// proti falesnemu serveru (page.route, zadna sit, zadna DB). Stav "DB" drzi tenhle soubor v Node.
//
// DULEZITE: odpoved /api/shop/stock/movements?product_id= (z ni karta bere `data.product`) se sklada ze
// sloupcu, ktere vraci SKUTECNY SELECT v api/products.py (parsuje se za behu) - mock tedy nelže o tom, co
// backend posila. Dokud tam chybi `unit`, chybi i tady (presne tak vznikla chyba "karta desky vzdy rika
// 'za celou tabuli'").
//
// Kandidat pred nasazenim (nic se nezapise do zivych souboru):
//   ADMIN_HTML=... SKLAD_PRODUKTY_JS=... PRODUCTS_PY=... node test_karta_produktu.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PRODUCTS_PY = process.env.PRODUCTS_PY || path.join(REPO, 'api/products.py');
const PREPIS = { 'sklad-produkty.js': process.env.SKLAD_PRODUKTY_JS, 'dashboard.js': process.env.DASHBOARD_JS, 'crm-nabidky.js': process.env.CRM_NABIDKY_JS };

// jako api/product_slug.py: bez diakritiky, male pismo, pomlcky
const slugMock = t => (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'produkt';

const QUILL_ATRAPA = `
  window.Quill = function Quill() {};
  Quill.__icons = {};
  Quill.import = function (n) { return n === 'ui/icons' ? Quill.__icons : class BlockEmbed { static create() { return document.createElement('div'); } }; };
  Quill.register = function () {};
`;

// sloupce, ktere skutecne vraci GET /api/shop/stock/movements?product_id= (products.py, shop_stock_movements_list)
function sloupceMovements() {
  const src = fs.readFileSync(PRODUCTS_PY, 'utf8');
  const f = src.indexOf('def shop_stock_movements_list');
  const a = src.indexOf('SELECT id, name, sku,', f);
  const k = src.indexOf('FROM shop_products WHERE id=%s', a);
  if (f < 0 || a < 0 || k < 0) throw new Error('harness: v products.py nenalezen SELECT produktu pro skladovou kartu (shop_stock_movements_list)');
  return src.slice(a + 'SELECT '.length, k).split(',').map(s => s.trim()).filter(Boolean);
}

function vychoziProdukty() {
  const zaklad = {
    manufacturer: null, supplier_name: null, warranty: null, ean: null, category_path: null,
    availability_text: null, alternative_product_codes: null, related_product_codes: null,
    has_variants: 0, variant_count: 0, fbx_original_name: null, fbx_uploaded_at: null, visible_in_scene: 0,
    price_source_url: null, price_last_refreshed_at: null, color_hex: null, cutting_material_key: null,
    cfg_dily_id: null, length_mm: null, width_mm: null, height_mm: null, price_visible_default: 0,
    hover_show_price: 1, hover_show_availability: 0, meta_title: null, meta_description: null,
    dealer_discount_percent: null, sale_price_czk: null, sale_price_from: null, sale_price_until: null,
    dogus_url: null, dogus_stock_code: null, dogus_image_render_url: null, dogus_image_schema_url: null,
    product_specs_json: null, dogus_matched_at: null, dogus_list_price_usd: null, dogus_price_rate_used: null,
    is_archived: 0, active: 1, stock_qty: 0, min_stock: null, max_stock: null, weight_g: null,
    is_board_material: 0, board_sheet_width_mm: null, board_sheet_height_mm: null, glb_file: null, category_id: 207,
  };
  return [
    // 3671: v DB je unit='m2' (po chybnem kliknuti), cena 5000 je ale ZA TABULI
    { ...zaklad, id: 3671, sku: 'Laminodeska.SEDA.25', name: 'Laminovaná deska šedá 25mm', slug: 'laminovana-deska-seda-25mm',
      unit: 'm2', price_czk_placeholder: 5000, is_board_material: 1, board_sheet_width_mm: 2070, board_sheet_height_mm: 2800,
      cutting_material_key: 'lamino_seda_25', glb_file: 'product_3671.glb', visible_in_scene: 1 },
    // PR10: deska s cenou za tabuli (unit ks)
    { ...zaklad, id: 3539, sku: 'PR10', name: 'Překližka 10 mm', slug: 'prekliska-10', unit: 'ks', price_czk_placeholder: 3093.75,
      is_board_material: 1, board_sheet_width_mm: 1250, board_sheet_height_mm: 2500, cutting_material_key: 'preklizka_10' },
    // 4933: nova karta laminodesky - neni oznacena jako deska, bez rozmeru tabule a bez GLB
    { ...zaklad, id: 4933, sku: 'Laminodeska.SEDA.18', name: 'Laminovaná dřevotříska 18mm', slug: 'laminovana-drevotriska-18mm',
      unit: 'ks', price_czk_placeholder: 4000 },
    // zbozi prodavane na metry
    { ...zaklad, id: 5001, sku: 'LISTA-M', name: 'Lišta na metry', slug: 'lista-na-metry', unit: 'm', price_czk_placeholder: 120 },
  ];
}

async function otevriAdmin(opts = {}) {
  const produkty = opts.produkty || vychoziProdukty();
  const cols = sloupceMovements();
  const log = [];          // "METODA /cesta?dotaz"
  const puts = [];         // { id, body }
  const posts = [];        // { path, body }
  const chyby = [];
  const dialogy = [];
  const stav = { produkty, dalsiId: 6000, duplikatOdpoved: opts.duplikatOdpoved || null, putOdpoved: opts.putOdpoved || null, normalizeOdpoved: opts.normalizeOdpoved || null };

  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', async d => {
    dialogy.push({ typ: d.type(), text: d.message() });
    if (opts.dialogOdpoved === 'zrusit') await d.dismiss(); else await d.accept();
  });

  const movementsProduct = p => {
    const o = {};
    cols.forEach(c => { o[c] = p[c] === undefined ? null : p[c]; });
    o.is_board_material = !!p.is_board_material;   // skutecny endpoint to tak preklada na bool
    o.images = [];
    return o;
  };

  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    // Quill (CDN) je pro nacteni sklad-produkty.js NUTNY: skript na radku ~347 pri nacteni vola Quill.import/register
    // a bez nej spadne, takze se nikdy nedostane k definicim seznamu produktu a karty. Staci atrapa.
    if (u.hostname === 'cdn.jsdelivr.net' && /quill@1\.3\.7\/dist\/quill\.min\.js$/.test(u.pathname)) {
      return route.fulfill({ status: 200, contentType: 'application/javascript', body: QUILL_ATRAPA });
    }
    if (u.hostname === 'cdn.jsdelivr.net' && /\.css$/.test(u.pathname)) return route.fulfill({ status: 200, contentType: 'text/css', body: '' });
    if (u.hostname !== 'admin.test') return route.abort();          // zadna skutecna sit
    const p = u.pathname;
    const m = req.method();
    log.push(m + ' ' + p + u.search);
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
    if (p === '/api/shop/products' && m === 'GET') {
      return json(200, { products: stav.produkty.map(x => ({ ...x })), total: stav.produkty.length, page: 1, page_size: 50 });
    }
    let mm = /^\/api\/shop\/products\/(\d+)$/.exec(p);
    if (mm) {
      const pr = stav.produkty.find(x => x.id === +mm[1]);
      if (!pr) return json(404, { error: 'Produkt neexistuje.' });
      if (m === 'GET') return json(200, { product: { ...pr } });
      if (m === 'PUT') {
        const body = JSON.parse(req.postData() || '{}');
        puts.push({ id: pr.id, body });
        if (stav.putOdpoved) { const o = stav.putOdpoved(pr, body); if (o) return json(o.status, o.body); }
        const predNazev = pr.name, predSlug = pr.slug;
        Object.assign(pr, body);
        const odp = { status: 'ok' };
        // server (product_slug.py): adresa SLEDUJE nazev - prejmenovani i aktivace produktu bez adresy vytvori novou
        if (body.name && body.name !== predNazev) { pr.slug = slugMock(body.name); if (pr.slug !== predSlug) odp.slug = pr.slug; }
        else if (body.active && !predSlug) { pr.slug = slugMock(pr.name); odp.slug = pr.slug; }
        return json(200, odp);
      }
    }
    if (p === '/api/shop/products/normalize-slugs' && m === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      posts.push({ path: p, body });
      if (stav.normalizeOdpoved) {
        const o = stav.normalizeOdpoved(body, stav);
        if (o.raw !== undefined) return route.fulfill({ status: o.status, contentType: 'text/html', body: o.raw });   // prosta 404 pred restartem
        return json(o.status, o.body);
      }
      const zmeny = (opts.slugZmeny || []).filter(z => !body.ids || body.ids.includes(z.id));
      if (body.dry_run === false) zmeny.forEach(z => { const pr = stav.produkty.find(x => x.id === z.id); if (pr) pr.slug = z.new; });
      return json(200, { status: 'ok', dry_run: body.dry_run !== false, count: zmeny.length, changes: zmeny });
    }
    mm = /^\/api\/shop\/products\/(\d+)\/duplicate$/.exec(p);
    if (mm && m === 'POST') {
      posts.push({ path: p, id: +mm[1] });
      if (stav.duplikatOdpoved) {
        const o = stav.duplikatOdpoved(+mm[1], stav);
        if (o.raw !== undefined) return route.fulfill({ status: o.status, contentType: 'text/html', body: o.raw });   // napr. prosta 404 pred restartem
        return json(o.status, o.body);
      }
      const zdroj = stav.produkty.find(x => x.id === +mm[1]);
      const novy = { ...zdroj, id: stav.dalsiId++, sku: zdroj.sku + '-kopie', name: zdroj.name + ' (kopie)', slug: zdroj.slug + '-kopie', active: 0 };
      stav.produkty.push(novy);
      return json(201, { status: 'ok', id: novy.id, sku: novy.sku, name: novy.name, slug: novy.slug,
        copied: { categories: 1, images: 2, usage_images: 0, documents: 0, gallery: 3 }, missing_files: 0 });
    }
    if (p === '/api/shop/stock/movements' && m === 'GET') {
      const pr = stav.produkty.find(x => x.id === +u.searchParams.get('product_id'));
      if (!pr) return json(404, { error: 'Produkt neexistuje.' });
      return json(200, { product: movementsProduct(pr), movements: [] });
    }
    if (p === '/api/gallery-items') return json(200, { items: [] });
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });   // ostatni cast adminu: prazdne odpovedi
    return route.fulfill({ status: 404, body: '' });
  });

  await page.goto('http://admin.test/admin.html' + (opts.query || ''));
  try {
    await page.waitForFunction(() => typeof ADMIN_USER !== 'undefined' && !!ADMIN_USER && typeof shopProductsCache !== 'undefined' && shopProductsCache.length > 0, null, { timeout: 15000 });
  } catch (e) {
    const skripty = log.filter(r => /\.js/.test(r));
    throw new Error('harness: admin se nenacetl (ADMIN_USER / seznam produktu). ' + e.message.split('\n')[0]
      + '\n  nactene skripty: ' + skripty.length + ' (sklad-produkty.js: ' + skripty.some(r => /sklad-produkty/.test(r)) + ')'
      + '\n  chyby stranky:\n    ' + chyby.slice(0, 8).join('\n    '));
  }
  return { browser, page, stav, log, puts, posts, chyby, dialogy, cols };
}

// otevre skladovou kartu tak, jak to dela klik na radek seznamu (openStockCardModal(p) s radkem seznamu)
async function otevriKartu(page, id) {
  await page.evaluate(id => openStockCardModal(shopProductsCache.find(p => p.id === id)), id);
  await page.waitForSelector('#scfPrice', { timeout: 8000 });
  await page.waitForTimeout(250);
}

module.exports = { otevriAdmin, otevriKartu, vychoziProdukty, sloupceMovements };
