// Celostrankovy test: SKUTECNY webapp/admin.html + vsechny skripty z webapp/admin/js/ v Chromiu proti
// falesnemu serveru (page.route, zadna sit, zadna DB). Overuje PRESUN panelu "Rendering -> HDRi" z
// crm-nabidky.js do render-panel.js tam, kde to unit-testy nevidi: ze admin.html novy skript nacte ve
// spravnem poradi, ze skutecna renderDriveFolderContents() panel vlozi a oziví, a ze stranka pri tom
// nehodi zadnou chybu, ktera se tyka panelu.
// Spusteni: node test_admin_nacteni.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: ADMIN_HTML=... RENDER_PANEL_JS=... CRM_NABIDKY_JS=... node test_admin_nacteni.js
// Vypis chyb stranky (pro porovnani "pred" vs "po"): PRINT_ERRORS=1
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const ADMIN_HTML = process.env.ADMIN_HTML || path.join(REPO, 'webapp/admin.html');
const JS_DIR = path.join(REPO, 'webapp/admin/js');
const PREPIS = {
  'crm-nabidky.js': process.env.CRM_NABIDKY_JS,
  'render-panel.js': process.env.RENDER_PANEL_JS,
};

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push([nazev, !!podminka]);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};

const STROM = {
  root_files: [],
  folders: [{
    id: 1, name: 'Rendering', locked: false, allowed_roles: [], files: [], children: [{
      id: 2, name: 'HDRi', locked: false, allowed_roles: [], children: [],
      files: [{ id: 4125, filename: 'crossfit_gym_2k.exr', size_bytes: 1000, content_type: 'image/x-exr', created_at: '2026-09-01T10:00:00' }],
    }],
  }],
};
const ULOZENO = { alu_material: 'Alumi2', alu_knihovna_soubor: 'Alumi2.blend', svetla_soubor: 'X1_SCENA.blend', svetla_aktivni: false,
  hdri_file_id: 4125, hdri_sila: 1.4, aktivni_pro_automat: true, kryci_listy_skryt: true, nahrady: [] };

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const chyby = [];
  page.on('pageerror', e => chyby.push(e.message));
  const pozadavky = [];
  await page.route('**/*', async route => {
    const req = route.request();
    const u = new URL(req.url());
    if (u.hostname !== 'admin.test') return route.abort();          // zadna skutecna sit
    const p = u.pathname;
    pozadavky.push(req.method() + ' ' + p);
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/admin.html') return route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: fs.readFileSync(ADMIN_HTML, 'utf8') });
    const mJs = /^\/admin\/js\/([A-Za-z0-9_.-]+\.js)$/.exec(p);
    if (mJs) {
      const nazev = mJs[1];
      const cesta = PREPIS[nazev] || path.join(JS_DIR, nazev);
      if (!fs.existsSync(cesta)) return route.fulfill({ status: 404, body: 'nenalezeno' });
      return route.fulfill({ status: 200, contentType: 'application/javascript; charset=utf-8', body: fs.readFileSync(cesta, 'utf8') });
    }
    if (p === '/api/auth/me') return json(200, { user: { id: 1, role: 'admin', name: 'Test Admin', email: 'test@lokalni', theme_admin: 'dark', permissions: {} } });
    if (p === '/api/admin/drive') return json(200, STROM);
    if (p === '/api/admin/render-hdri' && req.method() === 'GET') return json(200, { active_id: 4125, files: [{ id: 4125, filename: 'crossfit_gym_2k.exr' }, { id: 4044, filename: 'tv_studio_4k.hdr' }] });
    if (p === '/api/admin/render-hdri-rotace') return json(200, { rotace_deg: 177 });
    if (p === '/api/admin/render-prirazeni' && req.method() === 'GET') return json(200, ULOZENO);
    if (p === '/api/admin/render-prirazeni/rodiny') return json(200, { rodiny: [], role: [], sestavy_role: [], sestavy: [] });
    if (p === '/api/admin/render-prirazeni/materialy') return json(200, { knihovna: 'x', materialy: ['Alumi2'] });
    if (p === '/api/admin/render-prirazeni/svetla') return json(200, { soubor: 'X1_SCENA.blend', svetla: [{ jmeno: 'Light', typ: 'bodové', vykon: 1000, vychozi: true }], preskoceno: 0 });
    if (p === '/api/admin/render-hdri/test-render') return json(200, { testy: [] });
    if (p === '/api/admin/render-worker/cile') return json(200, { cile: [{ jmeno: 'Logiman2', vychozi: true, gpu: 'OPTIX: NVIDIA GeForce RTX 3060', online: true, duvod: null }] });
    if (p.startsWith('/api/kontrola-scena')) return route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>kontrola</title>' });
    if (p.startsWith('/api/')) return json(200, req.method() === 'GET' ? {} : { status: 'ok' });   // ostatni cast adminu: prazdne odpovedi
    return route.fulfill({ status: 404, body: '' });
  });

  await page.goto('http://admin.test/admin.html');
  await page.waitForFunction(() => typeof ADMIN_USER !== 'undefined' && !!ADMIN_USER, null, { timeout: 15000 });
  over('A1 admin.html se nacetl a prihlasil atrapou', true);
  const nacteno = await page.evaluate(() => ({
    html: typeof renderPanelHtml, init: typeof renderPanelInit, drive: typeof renderDriveFolderContents,
  }));
  over('A2 funkce panelu jsou globalne dostupne (render-panel.js nacten)', nacteno.html === 'function' && nacteno.init === 'function' && nacteno.drive === 'function', nacteno);
  over('A3 render-panel.js se nacetl az ZA crm-nabidky.js',
    pozadavky.findIndex(r => /crm-nabidky\.js/.test(r)) >= 0
    && pozadavky.findIndex(r => /render-panel\.js/.test(r)) > pozadavky.findIndex(r => /crm-nabidky\.js/.test(r)), pozadavky.filter(r => /crm-nabidky|render-panel/.test(r)));

  // otevrit slozku s HDRi souborem pres SKUTECNY loadDriveTree -> renderDriveFolderContents
  await page.evaluate(async () => { driveSelectedFolderId = 2; await loadDriveTree(); });
  await page.waitForTimeout(800);
  const panel = await page.evaluate(() => {
    const w = document.getElementById('driveFolderContents');
    const val = id => { const e = document.getElementById(id); return e ? (e.type === 'checkbox' ? e.checked : e.value) : undefined; };
    return {
      maPanel: !!w.querySelector('#matPrirazeniPanel'),
      hdriRoleta: [...document.querySelectorAll('#matPrirazeniHdriId option')].map(o => o.value + '|' + o.textContent),
      alu: val('matPrirazeniAluKnihovna'), hdriId: val('matPrirazeniHdriId'), svetlaAktivni: val('matPrirazeniSvetlaAktivni'),
      automat: val('matPrirazeniAutomat'), stav: (document.getElementById('matPrirazeniAutomatStav') || {}).textContent,
      ulozit: !!document.getElementById('matPrirazeniUlozit'), spustit: !!document.getElementById('matPrirazeniSpustit'),
      souboru: w.querySelectorAll('.crm-note-row').length,
    };
  });
  over('B1 ve slozce s HDRi se panel vykreslil', panel.maPanel, panel);
  over('B2 roleta HDRi dostala soubory z disku', panel.hdriRoleta.length === 3 && panel.hdriRoleta.some(x => /crossfit_gym_2k\.exr/.test(x)), panel.hdriRoleta);
  over('B3 ulozeny stav se promitl do poli', panel.alu === 'Alumi2.blend' && panel.hdriId === '4125' && panel.svetlaAktivni === false && panel.automat === true, panel);
  over('B4 stavovy radek automatu je vyplneny', /Automat teď renderuje podle TOHOTO panelu/.test(panel.stav || ''), panel.stav);
  over('B5 tlacitka Ulozit a Spustit jsou', panel.ulozit && panel.spustit, panel);
  over('B6 seznam souboru slozky se vykreslil i s panelem', panel.souboru === 1, panel.souboru);

  // slozka BEZ HDRI souboru nema panel a nic nehodi
  await page.evaluate(async () => { driveSelectedFolderId = 1; renderDriveFolderContents(); });
  await page.waitForTimeout(200);
  over('C1 slozka bez HDRI souboru panel nema', (await page.evaluate(() => !document.getElementById('matPrirazeniPanel'))) === true);

  // zpet do slozky s HDRI: panel se vykresli znovu (prekreslovani), posluchace se nenasobi do chyb
  await page.evaluate(async () => { driveSelectedFolderId = 2; renderDriveFolderContents(); });
  await page.waitForTimeout(500);
  over('C2 opetovne prekresleni panelu funguje', (await page.evaluate(() => !!document.getElementById('matPrirazeniPanel'))) === true);

  // jen chyby, ktere se tykaji panelu; nesouvisejici hluk atrapy (Quill z blokovaneho CDN, poradi inicializace
  // jinych zalozek) se porovnava rucne pres PRINT_ERRORS=1 proti stavu pred zmenou
  const tykaSePanelu = chyby.filter(e => /renderPanel|matPrirazeni|ulozPrirazeni|render-panel|matPoleId|hlavniHdri|svetlaVyber|obnovStavAutomatu|renderDriveFolderContents/.test(e));
  over('D1 zadna chyba stranky se netyka panelu', tykaSePanelu.length === 0, tykaSePanelu);
  if (process.env.PRINT_ERRORS) console.log('CHYBY STRANKY (' + chyby.length + '):\n' + chyby.map(e => '  - ' + e).join('\n'));
  await browser.close();

  const selhalo = vysl.filter(v => !v[1]).length;
  console.log('\nVYSLEDEK celostrankovy test: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})().catch(e => { console.log('FAIL vyjimka testu: ' + (e && e.stack || e)); process.exit(1); });
