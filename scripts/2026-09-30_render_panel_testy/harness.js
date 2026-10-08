// Harness panelu "Rendering -> HDRi" (prirazeni materialu/HDRI/svetel): pousti SKUTECNY kod panelu
// (blok `if (maMaterialPanel)` z webapp/admin/js/render-panel.js, vytazeny pri kazdem spusteni) v Chromiu
// nad minimalnim DOM a falesnym fetch/serverem. Nic nesaha na zivy system (zadna sit, zadna DB).
// Spusteni: viz run_all.sh. Kdyz se zmeni zacatek/konec bloku v render-panel.js, uprav kotvy nize.
// (Panel zil do 2026-09-30 v crm-nabidky.js, pak byl presunut 1:1 do render-panel.js.)
// Jiny soubor panelu (kandidat pred nasazenim): RENDER_PANEL_JS=/cesta/render-panel.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const zdroj = fs.readFileSync(process.env.RENDER_PANEL_JS || path.join(__dirname, '../../webapp/admin/js/render-panel.js'), 'utf8');
const _a = zdroj.indexOf('  const matPoleId = {');
const _k = zdroj.indexOf('btnUlozit.addEventListener("click"', _a);
if (_a < 0 || _k < 0) throw new Error('harness: kotvy bloku panelu v render-panel.js nenalezeny (matPoleId / btnUlozit) - uprav harness.js');
const blok = zdroj.slice(_a, zdroj.indexOf('\n  }\n', _k) + '\n  }\n'.length);
// instrumentace: pred posledni uzaviraci zavorku bloku `if (maMaterialPanel) {`
const idx = blok.lastIndexOf('\n  }');
const blokInstr = blok.slice(0, idx)
  + '\n window.__dbg = () => ({ svetlaVyber, svetlaVyberSoubor, svetlaSeznam: svetlaSeznam.map(x=>x.jmeno), svetlaSeznamSoubor });'
  + '\n window.__ulozPrirazeni = () => ulozPrirazeni();'
  + '\n window.__obnovStav = () => obnovStavAutomatu();'
  + blok.slice(idx);

const HTML = `<!doctype html><meta charset=utf-8><body><div id="wrap">
<input type=checkbox id=matPrirazeniAutomat>
<div id=matPrirazeniAutomatStav></div>
<label><input type=checkbox id=matPrirazeniSvetlaAktivni></label>
<input type=text id=matPrirazeniSvetlaSoubor>
<input type=number id=matPrirazeniSvetlaSila>
<span id=matPrirazeniSvetlaInfo></span>
<div id=matPrirazeniSvetlaSeznam style="display:none"></div>
<input type=checkbox id=matPrirazeniKrycList>
<span id=matPrirazeniUlozStav></span>
<button id=matPrirazeniUlozit>ulozit</button>
</div></body>`;

const SOUBORY = {
  'X1_SCENA.blend': [
    { jmeno: 'Light', typ: 'POINT', vykon: 1000 },
    { jmeno: 'Spot', typ: 'AREA', vykon: 0.28 },
    { jmeno: 'Spot.001', typ: 'SPOT', vykon: 254 },
    { jmeno: 'Spot.002', typ: 'SPOT', vykon: 254 },
  ],
  'Y.blend': [
    { jmeno: 'Sun', typ: 'SUN', vykon: 5 },
    { jmeno: 'Lamp', typ: 'POINT', vykon: 50 },
    { jmeno: 'Fill', typ: 'POINT', vykon: 10 },
  ],
  'XSS.blend': [
    { jmeno: '<img src=x onerror="window.__xss=1">', typ: 'POINT', vykon: 100 },
    { jmeno: 'a"b\'c\\d + e', typ: 'SPOT', vykon: 90 },
    { jmeno: 'Svetlo \u010d\u0159\u017e', typ: 'SUN', vykon: 1 },
  ],
  // X1 po prejmenovani Spot.001 -> Spot.003
  'X1_PREJMENOVANO.blend': [
    { jmeno: 'Light', typ: 'POINT', vykon: 1000 },
    { jmeno: 'Spot', typ: 'AREA', vykon: 0.28 },
    { jmeno: 'Spot.003', typ: 'SPOT', vykon: 254 },
    { jmeno: 'Spot.002', typ: 'SPOT', vykon: 254 },
  ],
};

async function otevri(stored, opts = {}) {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('  [pageerror]', e.message));
  await page.setContent(HTML);
  await page.evaluate(({ stored, SOUBORY, opts }) => {
    window.__server = { state: stored, puts: [], gets: [] };
    window.__delay = opts.delay || {};      // soubor -> ms zpozdeni GET /svetla
    window.__bezVychozi = !!opts.bezVychozi; // simulace stareho API bez pole "vychozi"
    window.__putDelay = opts.putDelaySrc ? new Function('telo', 'return (' + opts.putDelaySrc + ')') : (() => 0);
    const json = (status, body) => ({ ok: status < 400, status, json: async () => body });
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    window.fetch = async (url, o) => {
      url = String(url);
      if (url.startsWith('/api/admin/render-prirazeni/svetla')) {
        const soubor = decodeURIComponent(url.split('soubor=')[1]);
        window.__server.gets.push(soubor);
        await sleep(window.__delay[soubor] || 0);
        const sv = SOUBORY[soubor];
        if (!sv) return json(404, { error: "soubor '" + soubor + "' na Sdíleném disku není" });
        const poradi = sv.map((_, i) => i).sort((a, b) => (sv[b].vykon - sv[a].vykon) || (a - b));
        const vych = new Set(poradi.slice(0, 2));
        return json(200, { soubor, svetla: sv.map((x, i) => window.__bezVychozi ? { ...x } : { ...x, vychozi: vych.has(i) }), preskoceno: 1 });
      }
      if (url === '/api/admin/render-prirazeni/rodiny') return json(200, { rodiny: [] });
      if (url === '/api/admin/render-hdri-rotace') return json(200, {});
      if (url === '/api/admin/render-prirazeni' && (!o || !o.method || o.method === 'GET')) return json(200, JSON.parse(JSON.stringify(window.__server.state)));
      if (url === '/api/admin/render-prirazeni' && o.method === 'PUT') {
        const telo = JSON.parse(o.body);
        window.__server.puts.push(telo);
        await sleep(window.__putDelay(telo));
        // simulace serveru: n od nuly
        const n = {};
        ['svetla_soubor'].forEach(k => { if (telo[k]) n[k] = String(telo[k]).trim(); });
        if ('svetla_aktivni' in telo) n.svetla_aktivni = !!telo.svetla_aktivni;
        if (telo.svetla_vybrana != null) {
          const v = telo.svetla_vybrana;
          if (!Array.isArray(v) || !v.length) return json(400, { error: 'svetla_vybrana musí být neprázdný seznam jmen světel.' });
          n.svetla_vybrana = v;
        }
        // svetla_args validace (jen zapnuta svetla)
        if (n.svetla_soubor && n.svetla_aktivni !== false) {
          const sv = SOUBORY[n.svetla_soubor];
          if (!sv) return json(400, { error: "Tabulka se neuložila - světla: soubor se svetly '" + n.svetla_soubor + "' nenalezen" });
          if (n.svetla_vybrana) {
            const ex = sv.map(x => x.jmeno);
            const chybi = n.svetla_vybrana.filter(j => !ex.includes(j));
            if (chybi.length) return json(400, { error: "Tabulka se neuložila - světla: vybrané světlo '" + chybi.join("', '") + "' v souboru není" });
          }
        }
        n.aktivni_pro_automat = !!telo.aktivni_pro_automat;
        n.kryci_listy_skryt = !!telo.kryci_listy_skryt;
        window.__server.state = n;
        return json(200, { status: 'ok', ...n });
      }
      return json(404, { error: 'mock: ' + url });
    };
  }, { stored, SOUBORY, opts: { delay: opts.delay, bezVychozi: opts.bezVychozi, putDelaySrc: opts.putDelaySrc } });
  await page.evaluate(({ blokInstr }) => {
    const src = 'const maMaterialPanel = true; const wrap = document.getElementById("wrap");'
      + 'const escapeHtmlAdmin = s => s; let driveActiveHdriId = null; let matPrirazeni3dStav = null;'
      + blokInstr;
    (new Function(src))();
  }, { blokInstr });
  return { browser, page };
}

const dbg = page => page.evaluate(() => window.__dbg());
const info = page => page.evaluate(() => ({
  info: document.getElementById('matPrirazeniSvetlaInfo').textContent,
  stav: document.getElementById('matPrirazeniAutomatStav').textContent,
  ulozStav: document.getElementById('matPrirazeniUlozStav').textContent,
  seznamDisplay: document.getElementById('matPrirazeniSvetlaSeznam').style.display,
  seznam: [...document.querySelectorAll('#matPrirazeniSvetlaSeznam input[data-svetlo]')].map(c => (c.checked ? '[x] ' : '[ ] ') + c.dataset.svetlo),
  pozn: [...document.querySelectorAll('#matPrirazeniSvetlaSeznam span')].map(s => s.textContent).filter(t => /uložený|vypnuté/.test(t)),
}));
const server = page => page.evaluate(() => ({ state: window.__server.state, puts: window.__server.puts.length }));
const lastPut = page => page.evaluate(() => window.__server.puts[window.__server.puts.length - 1]);
const wait = (page, ms) => page.waitForTimeout(ms);
// zmena souboru: nastav hodnotu a vystrel 'change' (bubliny) jako prohlizec po opusteni pole
const zmenSoubor = (page, v) => page.evaluate(v => {
  const el = document.getElementById('matPrirazeniSvetlaSoubor');
  el.value = v; el.dispatchEvent(new Event('change', { bubbles: true }));
}, v);
const klikSvetlo = (page, jmeno) => page.evaluate(jmeno => {
  const c = [...document.querySelectorAll('#matPrirazeniSvetlaSeznam input[data-svetlo]')].find(x => x.dataset.svetlo === jmeno);
  c.checked = !c.checked; c.dispatchEvent(new Event('change', { bubbles: true }));
}, jmeno);
const klikAktivni = (page) => page.evaluate(() => {
  const c = document.getElementById('matPrirazeniSvetlaAktivni');
  c.checked = !c.checked; c.dispatchEvent(new Event('change', { bubbles: true }));
});

module.exports = { otevri, dbg, info, server, lastPut, wait, zmenSoubor, klikSvetlo, klikAktivni };
