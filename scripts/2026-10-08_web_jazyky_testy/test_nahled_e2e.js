// E2E "vse nebo nic" pro jazykove verze webu (EN / IT) nad NAHLEDOVYM serverem (nahled_server.py) - bot16, 2026-10-08.
// Pro kazdy jazyk a hlavni stranky: 200, <html lang>, stranka se po prekladu zobrazi, zadne chyby JS, ZADNY viditelny cesky text (krome vlastnich jmen), zadna cena v Kc, zadny dodavatel.
// Pojistky: i18n.js nebo slovnik se nenacte (404 / blokovano) -> stranka se presto zobrazi do ~3,5 s. Cesky nahled (?jazyk=cs) nema i18n.js a zustava cesky.
// Spusteni:  1) systemd-run --unit=bot16-nahled --collect --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=<koren> /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-08_web_jazyky_testy/nahled_server.py <koren> 8191
//            2) BASE=http://127.0.0.1:8191 node scripts/2026-10-08_web_jazyky_testy/test_nahled_e2e.js     (potom systemctl stop bot16-nahled)
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8191';
const STRANKY = [['uvod', '/'], ['kategorie', '/vestavby-do-dodavek-aut'], ['stoly', '/balici-stoly-a-pracoviste-na-miru'], ['karta-vandr', '/produkt/regal-na-euroboxy-citroen-jumpy-l1-od-2016'], ['karta-profil', '/produkt/uhelnikova-spojka-30x30'], ['kontakt', '/kontakt.html'], ['404', '/neexistujici-stranka-xyz']];
const VLASTNI = /Slavičín|Zlín|Praha|Škoda|ČSN|Husinecká|Citroën|Dobřichovice/g;
const CZ = /[ěščřžýůťďňĚŠČŘŽÝŮŤĎŇáíú]/;
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)).slice(0, 500) : ''}`); };

const viditelnyCesky = (p) => p.evaluate(({ src, vlastni }) => {
  const re = new RegExp(src), vl = new RegExp(vlastni, 'g'), out = [], skip = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1 };
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) {
    const par = n.parentElement; if (!par || skip[par.tagName] || par.closest('svg,script,style')) continue;
    const cs = getComputedStyle(par); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const v = n.nodeValue.replace(/\s+/g, ' ').trim().replace(vl, ''); if (v && re.test(v)) out.push(v.slice(0, 90));
  }
  document.querySelectorAll('[placeholder],[title],[alt],[aria-label]').forEach(e => { if (e.closest('svg')) return; ['placeholder', 'title', 'alt', 'aria-label'].forEach(a => { const v = (e.getAttribute(a) || '').replace(vl, ''); if (v && re.test(v)) out.push(a + ': ' + v.slice(0, 80)); }); });
  return out;
}, { src: CZ.source, vlastni: VLASTNI.source });

(async () => {
  const b = await chromium.launch();
  for (const lang of ['en', 'it']) {
    const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, locale: lang === 'it' ? 'it-IT' : 'en-GB' });
    const p = await ctx.newPage(); const chyby = []; p.on('pageerror', e => chyby.push(e.message));
    await p.route(/\/api\/track\/|\/track\.js/, r => r.abort());
    let prvni = true;
    for (const [nazev, cesta] of STRANKY) {
      const odp = await p.goto(BASE + cesta + (prvni ? '?jazyk=' + lang : ''), { waitUntil: 'networkidle', timeout: 60000 }).catch(e => ({ status: () => 0, chyba: e.message }));
      prvni = false; await p.waitForTimeout(1200);
      const stav = await p.evaluate(() => ({ lang: document.documentElement.lang, pending: document.documentElement.classList.contains('i18n-pending'), vis: getComputedStyle(document.body).visibility, text: document.body.innerText }));
      const cz = await viditelnyCesky(p);
      const jeStr404 = nazev === '404';
      ok(odp.status() === (jeStr404 ? 404 : 200) && stav.lang === lang && !stav.pending && stav.vis !== 'hidden', `${lang} ${nazev}: ${odp.status()}, lang=${stav.lang}, stránka zobrazena (bez i18n-pending)`, [odp.status(), stav]);
      if (!jeStr404) ok(cz.length === 0, `${lang} ${nazev}: žádný viditelný český text (${cz.length})`, cz.slice(0, 10));
      ok(!/\bKč\b|\bCZK\b/.test(stav.text), `${lang} ${nazev}: žádná cena v Kč`, (stav.text.match(/.{0,30}Kč.{0,10}/) || [''])[0]);
      ok(!/Dogus|Doğuş|Kalip/i.test(stav.text), `${lang} ${nazev}: žádný dodavatel (Dogus)`, (stav.text.match(/.{0,30}Dogus.{0,20}/i) || [''])[0]);
    }
    ok(chyby.length === 0, `${lang}: žádné chyby JS na všech stránkách`, chyby.slice(0, 3));
    await ctx.close();
  }
  // pojistky
  for (const [popis, vzor] of [['i18n.js se nenačte (404)', /\/js\/i18n\.js/], ['slovník se nenačte', /\/api\/i18n\/ui\.js/]]) {
    const ctx = await b.newContext({ viewport: { width: 1000, height: 700 } }); const p = await ctx.newPage();
    await p.route(/\/api\/track\/|\/track\.js/, r => r.abort()); await p.route(vzor, r => r.abort());
    const t0 = Date.now();
    await p.goto(BASE + '/kontakt.html?jazyk=en', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await p.waitForFunction(() => getComputedStyle(document.body).visibility !== 'hidden', null, { timeout: 6000 }).catch(() => {});
    const ms = Date.now() - t0;
    ok((await p.evaluate(() => getComputedStyle(document.body).visibility)) !== 'hidden' && ms < 5500, `pojistka: ${popis} → stránka se přesto zobrazí (${ms} ms)`, ms);
    await ctx.close();
  }
  { const ctx = await b.newContext({ viewport: { width: 1000, height: 700 } }); const p = await ctx.newPage(); await p.route(/\/api\/track\/|\/track\.js/, r => r.abort());
    await p.goto(BASE + '/?jazyk=cs', { waitUntil: 'networkidle', timeout: 60000 }); await p.waitForTimeout(500);
    const s = await p.evaluate(() => ({ lang: document.documentElement.lang, i18n: !!window.I18N && window.I18N.active, js: [...document.scripts].some(x => /i18n\.js/.test(x.src)), t: document.body.innerText.slice(0, 4000) }));
    ok(s.lang === 'cs' && !s.js && !s.i18n && /Košík|Přihlásit/.test(s.t), 'český náhled (?jazyk=cs): bez i18n.js, česky', s); await ctx.close(); }
  await b.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
