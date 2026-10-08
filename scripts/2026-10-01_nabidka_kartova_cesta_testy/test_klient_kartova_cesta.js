// Klient (scena): buildRenderRecipe() + renderViewWithFallback() ve webapp/js/scene/path-traced-preview.js - nabidka a test renderu
// posilaji zapis dilu pro "vzhled jako u karet" a pri jakemkoli selhani se AUTOMATICKY zkusi stara cesta (GLB bez zapisu dilu);
// uzivatel, ktery render zastavil, se nevraci. SKUTECNE funkce se vytahnou ze souboru a pusti v Chromiu proti falesnemu serveru.
// Spusteni: node test_klient_kartova_cesta.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: SCENA_JS=/cesta/path-traced-preview.js node test_klient_kartova_cesta.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const SOUBOR = process.env.SCENA_JS || path.join(__dirname, '../../webapp/js/scene/path-traced-preview.js');
const zdroj = fs.readFileSync(SOUBOR, 'utf8');
const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push([nazev, !!podminka]);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};

const vyber = (re) => { const m = re.exec(zdroj); return m ? m[0] : null; };
const fnRecipe = vyber(/function buildRenderRecipe\(\) \{[\s\S]*?\n\}\n/);
const fnRender = vyber(/async function renderViewWithFallback\([\s\S]*?\n\}\n/);
if (!fnRecipe || !fnRender) { console.log('FAIL funkce buildRenderRecipe/renderViewWithFallback v souboru nenalezeny'); process.exit(1); }

over('S1 soubor jde zparsovat (node --check)', (() => { try { execFileSync('node', ['--check', SOUBOR]); return true; } catch (e) { return false; } })());
over('S2 prime POST na /api/admin/blender-render zustaly 2 (pomocna funkce + zivy nahled)', (zdroj.match(/fetch\("\/api\/admin\/blender-render", \{ method: "POST"/g) || []).length === 2, (zdroj.match(/fetch\("\/api\/admin\/blender-render", \{ method: "POST"/g) || []).length);
over('S3 obe cesty (nabidka, test) volaji renderViewWithFallback', (zdroj.match(/await renderViewWithFallback\(/g) || []).length === 2, (zdroj.match(/await renderViewWithFallback\(/g) || []).length);
over('S4 nabidka i test dal posilaji ucel "nabidka"', /settings\.ucel = "nabidka";/.test(zdroj) && /ucel: "nabidka",/.test(zdroj));
over('S5 zivy nahled (progressive) NEposila zapis dilu (recipe jen v pomocne funkci)', (zdroj.match(/append\("recipe"/g) || []).length === 1, (zdroj.match(/append\("recipe"/g) || []).length);

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  const chyby = [];
  page.on('pageerror', e => chyby.push(e.message));
  await page.setContent('<!doctype html><body></body>');
  const vystup = await page.evaluate(async ({ fnRecipe, fnRender }) => {
    const puvodniST = window.setTimeout;
    window.setTimeout = (f, ms) => puvodniST(f, 0);                 // cekani 3 s mezi dotazy -> okamzite
    const out = {};

    // ---- buildRenderRecipe
    const recipeFn = (placed, serial) => { window.placed = placed; window.serializeEntryForSave = serial; return (new Function('return (' + fnRecipe.replace(/^function buildRenderRecipe/, 'function') + ')'))()(); };
    const dil = (id) => ({ part_id: id, position: [1, 2, 3], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] });
    out.r_prazdna = recipeFn([], (e) => e);
    out.r_bez_funkce = (() => { window.placed = [{}]; delete window.serializeEntryForSave; return (new Function('return (' + fnRecipe.replace(/^function buildRenderRecipe/, 'function') + ')'))()(); })();
    out.r_vyjimka = recipeFn([{}], () => { throw new Error('bum'); });
    out.r_ok = recipeFn([dil('a'), dil('b')], (e) => e);
    out.r_velke = recipeFn([{ x: 'x'.repeat(2000000) }], (e) => e);
    // nahled rozpracovaneho importu (tmpimport_*) se do zapisu nedostane; isImportPreviewEntry je globalni funkce sceny
    window.isImportPreviewEntry = (e) => !!(e && e.part && String(e.part.id).startsWith('tmpimport_'));
    const entry = (id) => ({ part: { id } });
    const serial = (e) => ({ part_id: e.part.id, position: [0, 0, 0], quaternion: [0, 0, 0, 1], scale: [1, 1, 1] });
    out.r_import = recipeFn([entry('a'), entry('tmpimport_1'), entry('b')], serial);
    out.r_jen_import = recipeFn([entry('tmpimport_1'), entry('tmpimport_2')], serial);
    delete window.isImportPreviewEntry;
    out.r_bez_filtru = recipeFn([entry('a'), entry('tmpimport_1')], serial);       // starsi scena bez funkce: nic nepadne, nefiltruje se

    // ---- renderViewWithFallback proti falesnemu serveru
    const vyrobRender = () => (new Function('return (' + fnRender.replace(/^async function renderViewWithFallback/, 'async function') + ')'))()
    async function scenar(skript, recipe, opt) {
      const posty = [];
      let radek = 0;
      window.FormData = window.FormData;                              // skutecny FormData
      window.fetch = async (url, init) => {
        if (init && init.method === 'POST' && url === '/api/admin/blender-render') {
          posty.push({ recipe: init.body.has('recipe'), settings: init.body.get('settings') });
          const odp = skript.post.shift();
          return { ok: odp.ok !== false, status: odp.status || 202, json: async () => odp.telo };
        }
        const odp = skript.get.shift();
        if (!odp) throw new Error('falesny server: nic dalsiho nepripraveno (' + url + ')');
        return { ok: odp.ok !== false, status: odp.status || 200, json: async () => odp.telo };
      };
      const udalosti = [];
      const optFull = Object.assign({ timeoutMs: 60000, onFallback: (d) => udalosti.push('fallback:' + d), onWait: (sd, el, k) => udalosti.push('wait:' + sd.state + ':' + k), onJob: (id, k) => udalosti.push('job:' + id + ':' + k) }, opt || {});
      let vysledek = null, chyba = null;
      try { vysledek = await vyrobRender()(new ArrayBuffer(8), { a: 1 }, recipe, optFull); } catch (e) { chyba = { zprava: e.message, zruseno: !!e.zruseno }; }
      return { posty: posty.map(p => p.recipe), vysledek: vysledek && { image: vysledek.image, jakKarta: vysledek.jakKarta, jobId: vysledek.jobId }, chyba, udalosti };
    }
    const hotovo = (j) => ({ telo: { state: 'done', image: 'data:image/png;base64,' + j, render_seconds: 5, worker_name: 'Omen' } });
    out.A = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }], get: [{ telo: { state: 'waiting_worker' } }, { telo: { state: 'running' } }, hotovo('A')] }, '[1]');
    out.B = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }, { telo: { job_id: 'j2' } }], get: [{ telo: { state: 'running' } }, { telo: { state: 'error', error: 'Blender spadl' } }, hotovo('B')] }, '[1]');
    out.C = await scenar({ post: [{ ok: false, status: 500, telo: { error: 'server' } }, { telo: { job_id: 'j2' } }], get: [hotovo('C')] }, '[1]');
    out.D = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }, { telo: { job_id: 'j2' } }], get: [{ telo: { state: 'cancelled', error: 'zruseno uzivatelem' } }, hotovo('D')] }, '[1]');
    out.E = await scenar({ post: [{ telo: { job_id: 'j1' } }], get: [hotovo('E')] }, null);
    out.F = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }, { telo: { job_id: 'j2' } }], get: [{ telo: { state: 'error', error: 'karta' } }, { telo: { state: 'error', error: 'stara taky' } }] }, '[1]');
    out.G = await scenar({ post: [{ telo: { job_id: 'j1' } }], get: [hotovo('G')] }, '[1]');       // server sam spadl na starou cestu: bez cesty:'karta'
    out.H = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }, { telo: { job_id: 'j2' } }], get: [] }, '[1]', { timeoutMs: -1 });
    out.I = await scenar({ post: [{ ok: false, status: 400, telo: { error: 'Chybi GLB' } }], get: [] }, null);
    out.J = await scenar({ post: [{ telo: { job_id: 'j1', cesta: 'karta' } }], get: [{ telo: { state: 'running', preview: 'data:image/png;base64,P', preview_mtime: 5 } }, hotovo('J')] }, '[1]', { progressive: true, onPreview: () => {} });
    return out;
  }, { fnRecipe, fnRender });

  over('R1 prazdna scena -> bez zapisu dilu (null)', vystup.r_prazdna === null, vystup.r_prazdna);
  over('R2 chybi serializeEntryForSave -> null (jen stara cesta)', vystup.r_bez_funkce === null, vystup.r_bez_funkce);
  over('R3 serializace vyhodi vyjimku -> null, nic nespadne', vystup.r_vyjimka === null, vystup.r_vyjimka);
  over('R4 bezna scena -> JSON seznam dilu', Array.isArray(JSON.parse(vystup.r_ok || 'null')) && JSON.parse(vystup.r_ok).length === 2, vystup.r_ok);
  over('R5 prilis velky zapis -> null (server by ho stejne odmitl)', vystup.r_velke === null, typeof vystup.r_velke);
  over('R6 nahled importu (tmpimport_*) v zapisu NENI, ostatni dily ano', JSON.stringify(JSON.parse(vystup.r_import).map(d => d.part_id)) === '["a","b"]', vystup.r_import);
  over('R7 ve scene jen nahled importu -> null (zadna kartova cesta)', vystup.r_jen_import === null, vystup.r_jen_import);
  over('R8 bez funkce isImportPreviewEntry nic nespadne (nefiltruje se)', JSON.parse(vystup.r_bez_filtru).length === 2, vystup.r_bez_filtru);

  over('A karta ok: 1 POST se zapisem dilu, vysledek z karty', JSON.stringify(vystup.A.posty) === '[true]' && vystup.A.vysledek && vystup.A.vysledek.jakKarta === true && vystup.A.vysledek.image.endsWith('A') && !vystup.A.chyba, vystup.A);
  over('A2 udalosti: job (karta), cekani s priznakem karta', vystup.A.udalosti.includes('job:j1:true') && vystup.A.udalosti.includes('wait:waiting_worker:true'), vystup.A.udalosti);
  over('B karta spadne -> automaticky 2. POST BEZ zapisu dilu, vysledek ze stare cesty', JSON.stringify(vystup.B.posty) === '[true,false]' && vystup.B.vysledek && vystup.B.vysledek.jakKarta === false && vystup.B.vysledek.image.endsWith('B'), vystup.B);
  over('B2 uzivatel se o navratu dozvi (onFallback s duvodem)', vystup.B.udalosti.some(u => u.startsWith('fallback:') && u.includes('Blender spadl')), vystup.B.udalosti);
  over('C HTTP 500 pri zarazeni karty -> stara cesta', JSON.stringify(vystup.C.posty) === '[true,false]' && vystup.C.vysledek && vystup.C.vysledek.image.endsWith('C'), vystup.C);
  over('D uzivatel render zastavil (cancelled) -> ZADNY navrat, 1 POST, chyba oznacena zruseno', JSON.stringify(vystup.D.posty) === '[true]' && vystup.D.chyba && vystup.D.chyba.zruseno === true && !vystup.D.vysledek, vystup.D);
  over('E bez zapisu dilu -> jedna stara cesta, bez recipe', JSON.stringify(vystup.E.posty) === '[false]' && vystup.E.vysledek && vystup.E.vysledek.image.endsWith('E'), vystup.E);
  over('F selzou obe cesty -> chyba ze STARE cesty (posledni), 2 POSTy', JSON.stringify(vystup.F.posty) === '[true,false]' && vystup.F.chyba && vystup.F.chyba.zprava === 'stara taky' && !vystup.F.chyba.zruseno, vystup.F);
  over('G server sam spadl na starou cestu (bez cesta:karta) -> bez dalsiho POSTu, jakKarta=false', JSON.stringify(vystup.G.posty) === '[true]' && vystup.G.vysledek && vystup.G.vysledek.jakKarta === false, vystup.G);
  over('H casovy limit karty -> stara cesta (a ta taky vyprsi -> chyba)', JSON.stringify(vystup.H.posty) === '[true,false]' && vystup.H.chyba && /render trvá přes/.test(vystup.H.chyba.zprava), vystup.H);
  over('I chyba serveru bez zapisu dilu (stara cesta) -> hned chyba, zadny dalsi pokus', JSON.stringify(vystup.I.posty) === '[false]' && vystup.I.chyba && vystup.I.chyba.zprava === 'Chybi GLB', vystup.I);
  over('J progresivni nahled (test renderu) proleze celou funkci', vystup.J.vysledek && vystup.J.vysledek.jakKarta === true, vystup.J);
  over('Z zadne chyby stranky', chyby.length === 0, chyby);

  await browser.close();
  const selhalo = vysl.filter(v => !v[1]).length;
  console.log('\nVYSLEDEK klient kartova cesta: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})();
