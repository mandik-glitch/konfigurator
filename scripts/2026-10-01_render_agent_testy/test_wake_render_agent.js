// wakeRenderAgent() ve scene (webapp/js/scene/path-traced-preview.js): tlacitka "+ rendery" a "Test" budi renderovaciho
// agenta pres protokol logimanrender://start JEN kdyz GPU stanice (vychozi worker) nehlasi tep. Jinak (Robert 2026-09-30)
// otevrela zbytecne okno stareho spoustece "Agent skoncil, restartuji za 3s..." ve smycce. SKUTECNA funkce se vytahne ze
// souboru a pusti v Chromiu proti falesnemu /api/admin/render-worker/status. Bez site a DB.
// Spusteni: node test_wake_render_agent.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: SCENA_JS=/cesta/path-traced-preview.js node test_wake_render_agent.js
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

const m = /(?:async )?function wakeRenderAgent\(\) \{[\s\S]*?\n\}\n/.exec(zdroj);
if (!m) { console.log('FAIL funkce wakeRenderAgent v souboru nenalezena'); process.exit(1); }
const fn = m[0];

over('S1 soubor jde zparsovat (node --check)', (() => { try { execFileSync('node', ['--check', SOUBOR]); return true; } catch (e) { return false; } })());
over('S2 wakeRenderAgent je async (kontroluje stav)', /^async function wakeRenderAgent/.test(fn), fn.slice(0, 60));
const volani = zdroj.match(/^\s*wakeRenderAgent\(\);/gm) || [];
over('S3 tlacitka volaji wakeRenderAgent() bez await (nezdrzuji klik), 2 mista', volani.length === 2 && !/await wakeRenderAgent/.test(zdroj), volani.length);

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  async function scenar(odpoved) {
    const page = await browser.newPage();
    const chyby = [];
    page.on('pageerror', e => chyby.push(e.message));
    await page.setContent('<!doctype html><body></body>');
    const vysledek = await page.evaluate(async ({ fn, odpoved }) => {
      window.fetch = async () => {
        if (odpoved.hod) throw new Error('sit nejede');
        return { ok: odpoved.ok, status: odpoved.status || 200, json: async () => { if (odpoved.rozbity) throw new Error('rozbite JSON'); return odpoved.telo; } };
      };
      // funkce se vyrobi z textu souboru
      const wake = (new Function(fn + '; return wakeRenderAgent;'))();
      let vyjimka = null;
      try { await wake(); } catch (e) { vyjimka = String(e); }
      const iframes = [...document.querySelectorAll('iframe')].map(f => f.getAttribute('src'));
      return { iframes, vyjimka };
    }, { fn, odpoved });
    return { page, vysledek, chyby };
  }

  let s = await scenar({ ok: true, telo: { state: 'offline', online: false } });
  over('T1 GPU stanice offline -> agent se probudi (1 iframe logimanrender://start)', JSON.stringify(s.vysledek.iframes) === JSON.stringify(['logimanrender://start']) && !s.vysledek.vyjimka, s.vysledek);
  await s.page.waitForTimeout(4300);
  over('T1b iframe se po 4 s sam odstrani', (await s.page.evaluate(() => document.querySelectorAll('iframe').length)) === 0);
  await s.page.close();

  s = await scenar({ ok: true, telo: { state: 'online', online: true } });
  over('T2 GPU stanice online (sluzba) -> NEbudit, zadne okno', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  s = await scenar({ ok: true, telo: { state: 'stuck', online: false, stuck: true } });
  over('T3 agent tepe, ale nebere praci (stuck) -> NEbudit (start dalsi kopie nepomuze)', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  s = await scenar({ ok: false, status: 403, telo: { error: 'Nemate opravneni' } });
  over('T4 403 (bez prava GPU monitoru) -> NEbudit, bez vyjimky', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  s = await scenar({ hod: true });
  over('T5 chyba site -> NEbudit, bez vyjimky', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  s = await scenar({ ok: true, rozbity: true });
  over('T6 rozbita odpoved -> NEbudit, bez vyjimky', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  s = await scenar({ ok: true, telo: null });
  over('T7 prazdna odpoved (null) -> NEbudit', s.vysledek.iframes.length === 0 && !s.vysledek.vyjimka, s.vysledek);
  await s.page.close();

  await browser.close();
  const selhalo = vysl.filter(v => !v[1]).length;
  console.log('\nVYSLEDEK wakeRenderAgent: ' + (vysl.length - selhalo) + '/' + vysl.length + ' OK');
  process.exit(selhalo ? 1 : 0);
})().catch(e => { console.log('FAIL vyjimka testu: ' + (e && e.stack || e)); process.exit(1); });
