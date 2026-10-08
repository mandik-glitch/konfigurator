// Harness verejne stranky produktu (webapp/product.html): SKUTECNA stranka + skripty z webapp/js v Chromiu proti falesnemu
// serveru (page.route, zadna sit, zadna DB). Stav "DB" drzi tenhle soubor v Node. Zakaznik je prihlaseny, karta ma
// 3 provedeni (zastupce A + B + C) jako skutecne karty sestav (3943), kazda s cenou montaze a boxu z verejneho JSON.
//
// Kandidat pred nasazenim (nic se nezapise do zivych souboru): PRODUCT_HTML=/cesta/k/product.html node test_produkt_zastupce_kosik.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const PRODUCT_HTML = process.env.PRODUCT_HTML || path.join(REPO, 'webapp/product.html');
const WEBAPP = path.join(REPO, 'webapp');

function vychoziProdukt() {
  return {
    id: 3943, sku: 'K-075-RL-EB-30', name: 'Regál na eurobox Fiat Doblo L1H1 do 2022', slug: 'regal-na-euroboxy-fiat-doblo-l1h1-do-2022',
    active: 1, is_archived: 0, category_id: null, price_czk_placeholder: 23081, effective_price_czk: null, price_basis: 'base',
    unit: 'ks', stock_qty: 0, supplier_name: null, description: null, images: [], is_profile_material: 0, is_board_material: 0,
    cfg_dily_id: null, weight_g: null, meta_title: null, meta_description: null, dogus_url: null, dogus_list_price_usd: null,
    has_variants: 0, variant_count: 0, price_visible_default: 1, hover_show_price: 1, hover_show_availability: 0,
  };
}

// verejny JSON /api/shop/products/<id>/assemblies - ceny, montaz a boxy JAK JE VRACI SKUTECNY ENDPOINT po oprave z 2026-09-15
function vychoziVarianty() {
  const zaklad = { horni_blok_kod: 'B1', horni_blok_nazev: 'Základní', typologie_nazev: 'Regál na eurobox', has_turntable: true,
                   popis_varianty: null, kotveni_varianty: null, montaz_varianty: null, weight_kg: 19.0 };
  return [
    { ...zaklad, id: 344, name: 'Regál na eurobox Doblo L1H1 – provedení A', verze: 'A', is_master: true, kod_sestavy: 'K-075-E30A72',
      price_czk: 23081, montaz_cena_czk: 4616, boxy_cena_czk: 1520 },
    { ...zaklad, id: 345, name: 'Regál na eurobox Doblo L1H1 – provedení B', verze: 'B', is_master: false, kod_sestavy: 'K-075-E30B72',
      price_czk: 20262, montaz_cena_czk: 4052, boxy_cena_czk: 1520 },
    { ...zaklad, id: 346, name: 'Regál na eurobox Doblo L1H1 – provedení C', verze: 'C', is_master: false, kod_sestavy: 'K-075-E30C72',
      price_czk: 25000, montaz_cena_czk: 5000, boxy_cena_czk: 2000 },
  ];
}

const ROUTES_STATIC = { '/track.js': 'track.js' };

async function otevriProdukt(opts = {}) {
  const produkt = opts.produkt || vychoziProdukt();
  const varianty = opts.varianty || vychoziVarianty();
  const posts = [];          // { path, body }  - POST /api/cart/items atd.
  const chyby = [];
  const log = [];

  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1100 } });
  page.on('pageerror', e => chyby.push(process.env.PRINT_STACK ? (e.stack || e.message) : e.message));
  page.on('dialog', d => d.accept());

  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname !== 'shop.test') return route.abort();          // zadna skutecna sit (fonty, CDN)
    const p = u.pathname, m = req.method();
    log.push(m + ' ' + p + u.search);
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/product.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(PRODUCT_HTML, 'utf8') });
    if (/^\/js\/[A-Za-z0-9_.-]+\.js$/.test(p) || p === '/track.js') {
      const f = path.join(WEBAPP, p);
      return fs.existsSync(f) ? route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(f, 'utf8') })
                              : route.fulfill({ status: 404, body: '' });
    }
    if (p === '/js/product-variant-groups.json') return json(200, { groups: [] });
    if (p === '/api/auth/me') return json(200, { user: { id: 793, role: 'user', name: 'Zákazník', email: 'zakaznik@test', theme_shop: 'dark', permissions: {} } });
    if (p === '/api/categories') return json(200, { tree: [], cart_enabled: true, discount_codes_enabled: true });
    if (p === '/api/theme-colors') return json(200, { dark: {}, light: {} });
    if (p === '/api/montaz-mista') return json(200, { mista: [{ klic: 'praha', nazev: 'Praha' }, { klic: 'slavicin', nazev: 'Slavičín' }] });
    if (p === `/api/shop/products/${produkt.id}` && m === 'GET') return json(200, { product: produkt, gallery: [], related_products: [], compatible_accessories: [], usage_images: [] });
    if (p === `/api/shop/products/${produkt.id}/assemblies`) return json(200, { assemblies: varianty });
    if (p === `/api/shop/products/${produkt.id}/turntable`) return json(200, { available: false });
    if (p === '/api/cart' && m === 'GET') return json(200, { items: [], subtotal_czk: 0, item_count: 0, total_qty: 0 });
    if (p === '/api/cart/items' && m === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      posts.push({ path: p, body });
      return json(opts.kosikOdpoved ? opts.kosikOdpoved.status : 201, opts.kosikOdpoved ? opts.kosikOdpoved.body : { items: [], subtotal_czk: 0, item_count: 1, total_qty: 1 });
    }
    if (p.startsWith('/api/')) return json(200, m === 'GET' ? {} : { status: 'ok' });   // zbytek stranky: prazdne odpovedi
    return route.fulfill({ status: 404, body: '' });
  });

  await page.goto(`http://shop.test/product.html?id=${produkt.id}`);
  try {
    await page.waitForSelector('.pd-av-track', { timeout: 15000 });
    await page.waitForTimeout(400);
  } catch (e) {
    throw new Error('harness: stranka produktu nenacetla posuvnik provedeni. ' + e.message.split('\n')[0]
      + '\n  chyby stranky:\n    ' + chyby.slice(0, 8).join('\n    ') + '\n  volani: ' + log.filter(r => /api/.test(r)).slice(0, 12).join(' | '));
  }
  return { browser, page, posts, chyby, log };
}

// zakaznik hne posuvnikem "Skladba boxu" (klavesnice = skutecny zasah, userInitiated:true); smer: 'ArrowRight' | 'ArrowLeft'
async function posunVerzi(page, klavesa) {
  const track = page.locator('.pd-av-track').first();    // prvni osa = Skladba boxu (verze)
  await track.focus();
  await page.keyboard.press(klavesa);
  await page.waitForTimeout(250);
}

module.exports = { otevriProdukt, posunVerzi, vychoziProdukt, vychoziVarianty };
