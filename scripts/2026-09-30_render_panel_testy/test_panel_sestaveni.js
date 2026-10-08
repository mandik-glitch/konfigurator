// Integracni test panelu "Rendering -> HDRi" (webapp/admin/js/render-panel.js): SKUTECNA sablona
// (renderPanelHtml) + SKUTECNA logika (renderPanelInit) v Chromiu proti falesnemu serveru (page.route).
// Overuje to, co unit-harness (test_panel_svetla.js) nevidi: ze sablona a logika patri k sobe (kazde id,
// na ktere JS sahne, v sablone je), ze se ulozeny stav promitne do poli, ze klik na "svetla ze souboru"
// (presne to, co dela Robert) posle spravny PUT, ze funguje volba stroje "renderovat na", test-render,
// fronta testu a 3D nahled. Nic nesaha na zivy system (zadna sit, zadna DB).
// Spusteni: node test_panel_sestaveni.js   (konci kodem 0 jen kdyz VSE prosla)
// Jiny soubor panelu (napr. kandidat pred nasazenim): RENDER_PANEL_JS=/cesta/render-panel.js node ...
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const PANEL_JS = process.env.RENDER_PANEL_JS || path.join(REPO, 'webapp/admin/js/render-panel.js');
const CRM_JS = process.env.CRM_NABIDKY_JS || path.join(REPO, 'webapp/admin/js/crm-nabidky.js');
const panelSrc = fs.readFileSync(PANEL_JS, 'utf8');
const crmSrc = fs.readFileSync(CRM_JS, 'utf8');
// skutecna escapeHtmlAdmin ze sklad-produkty.js (ne vlastni napodobenina)
const skladSrc = fs.readFileSync(path.join(REPO, 'webapp/admin/js/sklad-produkty.js'), 'utf8');
const mEsc = /function escapeHtmlAdmin\(s\) \{[\s\S]*?\n\}/.exec(skladSrc);
if (!mEsc) throw new Error('test: escapeHtmlAdmin ve sklad-produkty.js nenalezena');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push([nazev, !!podminka]);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};

const ULOZENO = {
  alu_material: 'Alumi2', alu_knihovna_soubor: 'Alumi2.blend',
  klt_material: 'Blue Ceramic', klt_knihovna_soubor: 'modrecelo.blend',
  svetla_soubor: 'X1_SCENA.blend', cub_seda_tmava_sila: 0.1, alu_ao_sila: 0.4,
  hdri_sila: 1.4, hdri_rotace_deg: 177, azimut_deg: 250, svetla_aktivni: false,
  svetla_vybrana: ['Light', 'Spot.001'], hdri_file_id: 4125,
  nahrady: [{ rodina: '', role: 'black', material: 'Black', knihovna_soubor: 'Black.blend', typ: '' }],
  aktivni_pro_automat: true, kryci_listy_skryt: true,
};
const SVETLA = [
  { jmeno: 'Light', typ: 'bodové', vykon: 1000, vychozi: true },
  { jmeno: 'Spot', typ: 'plošné', vykon: 0.28, vychozi: false },
  { jmeno: 'Spot.001', typ: 'reflektor', vykon: 254, vychozi: true },
  { jmeno: 'Spot.002', typ: 'reflektor', vykon: 254, vychozi: false },
];
const RODINY = {
  rodiny: [], specialni_karta: {}, celkem_rodin: 5, karty_rodiny: {}, karty_rodiny_typ: {}, nazvy_karet: { 4001: 'Sestava A', 4002: 'Sestava B' },
  typy_dilu: {}, karty_role: { multiboxarc: [4001, 4002], black: [4001] }, karty_role_typ: {},
  sestavy: [], sestavy_role: [{ karta: 4001, nazev: 'Sestava A', pocet_roli: 2 }, { karta: 4002, nazev: 'Sestava B', pocet_roli: 1 }],
  role: [
    { role: 'multiboxarc', nazev: 'Multibox', rodiny: ['multibox'], sestav: 3, dilu: 10,
      typy: [{ typ: 'kltbox', nazev: 'KLT box', sestav: 2 }, { typ: 'polica', nazev: 'Police', sestav: 1 }] },
    { role: 'black', nazev: 'Černé plasty', rodiny: [], sestav: 5, dilu: 20, typy: [] },
  ],
};
const CILE = [
  { jmeno: 'Logiman2', vychozi: true, gpu: 'OPTIX: NVIDIA GeForce RTX 3060 | Blender 5.2.1', online: true, duvod: null },
  { jmeno: 'Omen', vychozi: false, gpu: 'OPTIX: NVIDIA GeForce RTX 4080 Laptop GPU', online: false, duvod: 'nehlásí se 2 min' },
];
const TESTY = [
  { id: 46, status: 'done', frame_url: '/x/a270.jpg', azimut_deg: 270, hdri_filename: 'crossfit_gym_2k.exr', hdri_rotace_deg: 177, hdri_sila: 1.4, render_na: 'Omen', requested_at: '2026-09-29 12:00' },
  { id: 47, status: 'pending', azimut_deg: null, hdri_filename: 'tv_studio_4k.hdr', hdri_rotace_deg: null, hdri_sila: null, render_na: null, requested_at: '2026-09-29 12:05' },
];

async function otevri(opts = {}) {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const chyby = [];
  page.on('pageerror', e => chyby.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !(opts.cile === null && /404/.test(m.text()))) chyby.push('console: ' + m.text()); });
  const server = { state: JSON.parse(JSON.stringify(ULOZENO)), puts: [], hdriPuts: [], rotPuts: [], posts: [] };
  await page.route('http://panel.test/**', async route => {
    const req = route.request();
    const u = new URL(req.url());
    const p = u.pathname;
    const json = (status, body) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (p === '/') return route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><meta charset=utf-8><body><div id="driveFolderContents"></div></body>' });
    if (p === '/api/kontrola-scena') return route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>kontrola</title>' });
    if (p === '/api/admin/render-prirazeni' && req.method() === 'GET') return json(200, server.state);
    if (p === '/api/admin/render-prirazeni' && req.method() === 'PUT') {
      const telo = JSON.parse(req.postData());
      server.puts.push(telo);
      server.state = Object.assign({}, telo);            // server stavi stav od nuly z tela
      return json(200, Object.assign({ status: 'ok' }, telo));
    }
    if (p === '/api/admin/render-prirazeni/rodiny') return json(200, RODINY);
    if (p === '/api/admin/render-prirazeni/materialy') {
      const k = u.searchParams.get('knihovna') || 'vd_materialy.blend';   // prazdna = vychozi knihovna (jako skutecny endpoint)
      const mat = { 'Alumi2.blend': ['Alumi1', 'Alumi2'], 'modrecelo.blend': ['Blue Ceramic'], 'Black.blend': ['Black'],
        'vd_materialy.blend': ['VD_hlinik', 'VD_plast'] }[k];
      return mat ? json(200, { knihovna: k, materialy: mat }) : json(404, { error: 'soubor ' + k + ' není' });
    }
    if (p === '/api/admin/render-prirazeni/svetla') {
      return u.searchParams.get('soubor') === 'X1_SCENA.blend' ? json(200, { soubor: 'X1_SCENA.blend', svetla: SVETLA, preskoceno: 1 })
        : json(404, { error: 'soubor není' });
    }
    if (p === '/api/admin/render-hdri-rotace') return json(200, { rotace_deg: 177 });
    if (p === '/api/admin/render-hdri' && req.method() === 'PUT') { server.hdriPuts.push(JSON.parse(req.postData())); return json(200, { status: 'ok' }); }
    if (p === '/api/admin/render-hdri-rotace' && req.method() === 'PUT') { server.rotPuts.push(JSON.parse(req.postData())); return json(200, { status: 'ok' }); }
    if (p === '/api/admin/render-hdri/test-render' && req.method() === 'GET') return json(200, { testy: TESTY });
    if (/^\/api\/admin\/render-hdri\/\d+\/test-render$/.test(p) && req.method() === 'POST') {
      const telo = JSON.parse(req.postData());
      server.posts.push({ url: p, telo });
      return json(200, { request_id: 99, render_na: telo.render_na || null });
    }
    if (p === '/api/admin/render-worker/cile') return opts.cile === null ? json(404, { error: 'mock: starsi server' }) : json(200, { cile: opts.cile || CILE });
    return json(404, { error: 'mock: ' + req.method() + ' ' + p });
  });
  await page.goto('http://panel.test/');
  // globalni stav z crm-nabidky.js (plni ho loadDriveTree) + skutecna escapeHtmlAdmin
  await page.addScriptTag({ content: mEsc[0] + '\nlet driveActiveHdriId = 4125;\n'
    + 'let driveHdriFiles = [{id: 4125, filename: "crossfit_gym_2k.exr"}, {id: 4044, filename: "tv_studio_4k.hdr"}];\n' });
  await page.addScriptTag({ content: panelSrc });
  await page.evaluate(() => {
    const wrap = document.getElementById('driveFolderContents');
    wrap.innerHTML = renderPanelHtml(driveHdriFiles);
    renderPanelInit(wrap);
  });
  return { browser, page, server, chyby };
}

const pole = (page, id) => page.evaluate(id => { const e = document.getElementById(id); return e ? (e.type === 'checkbox' ? e.checked : e.value) : undefined; }, id);
const text = (page, id) => page.evaluate(id => (document.getElementById(id) || {}).textContent, id);

(async () => {
  // ---- staticke kontroly vazby crm-nabidky.js <-> render-panel.js ----
  over('S1 crm-nabidky.js vola renderPanelHtml + renderPanelInit', /renderPanelHtml\(driveHdriFiles\)/.test(crmSrc) && /renderPanelInit\(wrap\)/.test(crmSrc));
  const crmBezKomentaru = crmSrc.split('\n').filter(l => !/^\s*\/\//.test(l)).join('\n');
  over('S2 v crm-nabidky.js nezustal kod panelu (komentare se nepocitaji)', !/matPoleId|matPrirazeniPanel|matPrirazeni3dStav|ulozPrirazeni/.test(crmBezKomentaru),
    (crmBezKomentaru.match(/matPoleId|matPrirazeniPanel|matPrirazeni3dStav|ulozPrirazeni/g) || []).slice(0, 5));
  over('S3 render-panel.js definuje obe funkce', /^function renderPanelHtml\(/m.test(panelSrc) && /^function renderPanelInit\(/m.test(panelSrc));

  const { browser, page, server, chyby } = await otevri();
  await page.waitForTimeout(800);   // nacteni stavu, rodin, materialu, svetel, fronty, cilu

  // ---- T1 sablona <-> logika ----
  const idVJs = new Set((panelSrc.match(/matPrirazeni[A-Za-z0-9]+/g) || []));
  ['matPrirazeni3dStav', 'matPrirazeni3dPosluchac', 'matPrirazeni3dInit'].forEach(x => idVJs.delete(x));
  const chybiId = await page.evaluate(ids => ids.filter(id => !document.getElementById(id)), [...idVJs]);
  over('T1 kazde id, na ktere JS sahne, je v sablone', chybiId.length === 0, chybiId);

  // ---- T2 ulozeny stav -> pole ----
  over('T2a knihovna hliniku', (await pole(page, 'matPrirazeniAluKnihovna')) === 'Alumi2.blend');
  over('T2b material hliniku (roleta z knihovny)', (await pole(page, 'matPrirazeniAluMaterial')) === 'Alumi2', await pole(page, 'matPrirazeniAluMaterial'));
  over('T2c material cela', (await pole(page, 'matPrirazeniKltMaterial')) === 'Blue Ceramic', await pole(page, 'matPrirazeniKltMaterial'));
  over('T2d HDRi roleta = ulozene 4125', (await pole(page, 'matPrirazeniHdriId')) === '4125', await pole(page, 'matPrirazeniHdriId'));
  over('T2e sila/rotace/azimut', (await pole(page, 'matPrirazeniHdriSila')) === '1.4' && (await pole(page, 'matPrirazeniHdriRotace')) === '177' && (await pole(page, 'matPrirazeniAzimut')) === '250');
  over('T2f svetla ze souboru ulozena VYPNUTA', (await pole(page, 'matPrirazeniSvetlaAktivni')) === false);
  over('T2g automat a kryci listy zatrzene', (await pole(page, 'matPrirazeniAutomat')) === true && (await pole(page, 'matPrirazeniKrycList')) === true);
  over('T2h informace o svetlech: VYPNUTO', /VYPNUTO/.test(await text(page, 'matPrirazeniSvetlaInfo')), await text(page, 'matPrirazeniSvetlaInfo'));
  over('T2i stav automatu: vestavena svetla', /světla: vestavěná/.test(await text(page, 'matPrirazeniAutomatStav')), await text(page, 'matPrirazeniAutomatStav'));
  over('T2j samotne nacteni panelu nic neulozilo', server.puts.length === 0, server.puts.length);

  // ---- T3 radky dilu podle role ----
  const radky = await page.evaluate(() => [...document.querySelectorAll('#matPrirazeniRodiny > .mp-lab')].map(e => e.dataset.rodina3d));
  over('T3a radky rol (2 hlavni + 2 podradky)', JSON.stringify(radky) === JSON.stringify(['role:multiboxarc', 'role:multiboxarc@kltbox', 'role:multiboxarc@polica', 'role:black']), radky);
  over('T3b tlacitko rozdelit podle dilu', (await page.evaluate(() => !!document.querySelector('#matPrirazeniRodiny .mp-rozdelit'))) === true);
  over('T3c ulozeny radek Black (knihovna + material)',
    await page.evaluate(() => { const sel = [...document.querySelectorAll('#matPrirazeniRodiny select')].pop(); return sel.value === 'Black'; }));

  // ---- T4 klik na "svetla ze souboru" (to, co udela Robert) ----
  await page.evaluate(() => document.getElementById('matPrirazeniSvetlaAktivni').click());
  await page.waitForTimeout(700);
  const put = server.puts[server.puts.length - 1] || {};
  over('T4a klik ulozil (1 PUT)', server.puts.length === 1, server.puts.length);
  over('T4b PUT: svetla_aktivni=true + soubor + 2 vychozi svetla', put.svetla_aktivni === true && put.svetla_soubor === 'X1_SCENA.blend'
    && JSON.stringify(put.svetla_vybrana) === JSON.stringify(['Light', 'Spot.001']), put);
  over('T4c PUT zachoval automat, kryci listy, HDRi a materialy', put.aktivni_pro_automat === true && put.kryci_listy_skryt === true
    && String(put.hdri_file_id) === '4125' && put.alu_material === 'Alumi2' && put.klt_material === 'Blue Ceramic' && (put.nahrady || []).length === 1, put);
  over('T4d hlaska "uloženo"', /uloženo/.test(await text(page, 'matPrirazeniUlozStav')), await text(page, 'matPrirazeniUlozStav'));
  over('T4e stav automatu ukazuje svetla ze souboru', /světla: ze souboru X1_SCENA\.blend \(Light \+ Spot\.001, síla 1,0\)/.test(await text(page, 'matPrirazeniAutomatStav')), await text(page, 'matPrirazeniAutomatStav'));
  over('T4f seznam svetel (4) se zatrzenymi 2', JSON.stringify(await page.evaluate(() => [...document.querySelectorAll('#matPrirazeniSvetlaSeznam input[data-svetlo]')].map(c => (c.checked ? 'x ' : '_ ') + c.dataset.svetlo)))
    === JSON.stringify(['x Light', '_ Spot', 'x Spot.001', '_ Spot.002']));

  // ---- T5 volba stroje "renderovat na" ----
  over('T5a volba stroje je videt', (await page.evaluate(() => document.getElementById('matPrirazeniKdeWrap').style.display)) === 'flex');
  const moznosti = await page.evaluate(() => [...document.querySelectorAll('#matPrirazeniKde option')].map(o => o.value + '|' + o.textContent));
  over('T5b dva stroje, Omen oznacen offline', moznosti.length === 2 && /^\|Logiman2 \(výchozí\)/.test(moznosti[0]) && /^Omen\|Omen .*offline/.test(moznosti[1]), moznosti);

  const stavAut = await text(page, 'matPrirazeniAutomatStav');
  over('T5c stav automatu rika, na kterych strojich renderuje',
    /Stroje automatu: Logiman2 \(výchozí, online\) · Omen \(pomáhá, když je Logiman2 vytížený nebo vypnutý a stroj je online a volný; teď offline\)\./.test(stavAut), stavAut);
  over('T5d veta o strojich je PO vete o panelu (nerusi ji)', stavAut.indexOf('Automat teď') >= 0 && stavAut.indexOf('Automat teď') < stavAut.indexOf('Stroje automatu'), stavAut);

  // ---- T6 tlacitko testovaciho renderu ----
  await page.evaluate(() => { const k = document.getElementById('matPrirazeniKde'); k.value = 'Omen'; k.dispatchEvent(new Event('change', { bubbles: true })); });
  const putyPredTestem = server.puts.length;
  await page.evaluate(() => document.getElementById('matPrirazeniSpustit').click());
  await page.waitForTimeout(700);
  over('T6a test nejdriv ulozil panel', server.puts.length === putyPredTestem + 1, server.puts.length);
  const post = server.posts[0];
  over('T6b POST test-render na HDRi 4125 s render_na=Omen', post && post.url === '/api/admin/render-hdri/4125/test-render' && post.telo.render_na === 'Omen', post);
  over('T6c POST nese hdri_sila/svetla_soubor', post && post.telo.hdri_sila === '1.4' && post.telo.svetla_soubor === 'X1_SCENA.blend', post && post.telo);
  over('T6d stav "zarazeno do fronty ... na Omen"', /zařazeno do fronty ✓ \(#99, na Omen\)/.test(await text(page, 'matPrirazeniStav')), await text(page, 'matPrirazeniStav'));

  // ---- T7 fronta testu ----
  const fronta = await text(page, 'matPrirazeniFronta');
  over('T7 fronta: hotovy #46 (na Omen) + cekajici #47', /#46/.test(fronta) && /na: Omen/.test(fronta) && /zobrazit render/.test(fronta) && /#47/.test(fronta) && /čeká ve frontě \(1\.\)/.test(fronta), fronta);

  // ---- T8 3D nahled ----
  const tri = await page.evaluate(() => ({
    moznosti: [...document.querySelectorAll('#matPrirazeni3dKarta option')].map(o => o.value),
    src: document.getElementById('matPrirazeni3d').getAttribute('src'),
  }));
  over('T8a 3D: sestavy a iframe na kontrolni scenu', tri.moznosti.includes('4001') && /items=vd:4001&rezim=materialy/.test(tri.src || ''), tri);
  await page.evaluate(() => {
    const f = document.getElementById('matPrirazeni3d');
    window.dispatchEvent(new MessageEvent('message', { origin: location.origin, source: f.contentWindow,
      data: { typ: 'kontrola-rodiny', rodiny: [], celo: false, kombinace: [], role: ['multiboxarc'], kombinaceRole: [] } }));
  });
  await page.waitForTimeout(100);
  const oka = await page.evaluate(() => [...document.querySelectorAll('.mp-oko')].map(b => b.dataset.rodina3d + ':' + b.style.opacity));
  over('T8b zprava z iframe obarvi oka (role v sestave = 1, ostatni 0.45)',
    oka.includes('role:multiboxarc:1') && oka.includes('role:black:0.45'), oka);

  over('T9 zadne chyby stranky/konzole', chyby.length === 0, chyby);
  await browser.close();

  // ---- T10 jen vychozi stroj / starsi server bez endpointu ----
  let o = await otevri({ cile: [CILE[0]] });
  await o.page.waitForTimeout(600);
  const st1 = await text(o.page, 'matPrirazeniAutomatStav');
  over('T10a jen Logiman2 -> "notebook se objevi po prvnim prihlaseni"', /Stroje automatu: Logiman2 \(výchozí, online\) · notebook se objeví po prvním přihlášení/.test(st1), st1);
  over('T10b bez chyb', o.chyby.length === 0, o.chyby);
  await o.browser.close();
  o = await otevri({ cile: [CILE[0], Object.assign({}, CILE[1], { nabidky: true })] });
  await o.page.waitForTimeout(600);
  const st3 = await text(o.page, 'matPrirazeniAutomatStav');
  over('T10e stroj pro nabidky: panel rika, ze je vyhrazeny a automat ho nepouziva', /Stroje automatu: Logiman2 \(výchozí, online\) · Omen \(vyhrazený pro nabídky a testy ze scény, automat ho nepoužívá; teď offline\)\./.test(st3) && !/pomáhá/.test(st3), st3);
  over('T10f bez chyb', o.chyby.length === 0, o.chyby);
  await o.browser.close();
  o = await otevri({ cile: null });
  await o.page.waitForTimeout(600);
  const st2 = await text(o.page, 'matPrirazeniAutomatStav');
  over('T10c starsi server bez /cile -> zadna veta o strojich, panel jede dal', st2.length > 0 && !/Stroje automatu/.test(st2), st2);
  over('T10d bez chyb stranky', o.chyby.length === 0, o.chyby);
  await o.browser.close();

  const selhalo = vysl.filter(v => !v[1]).length;
  console.log('\nVYSLEDEK sestaveni panelu: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})().catch(e => { console.log('FAIL vyjimka testu: ' + (e && e.stack || e)); process.exit(1); });
