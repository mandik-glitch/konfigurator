// webapp/js/i18n.js: preklad textu stranek podle slovniku - bot16, 2026-10-08 (IT/EN verze webu, docs/web_jazyky/README.md).
// A) chovani na fixturach (cesky host = nic, bez slovniku = nic, cisla, vzory {0}, vety s inline znackami a zachovane obsluhy udalosti, atributy, dynamicky obsah, alert/confirm, dvojity preklad),
// B) SHODA s extraktorem: skutecne zakaznicke stranky (bez skriptu) se slovnikem z docs/web_jazyky/10_ui.json (preklad = "§" + cesky klic) - po prekladu nesmi na strance zbyt zadny
//    staticky cesky text, ktery extraktor (scripts/web_jazyk_ui_zdroj.py) vytahl; tim se hlida, ze norm() / jednotky v Pythonu a v JS davaji stejne klice.
// Spusteni: node scripts/2026-10-08_web_jazyky_testy/test_i18n_js.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const I18N_JS = fs.readFileSync(process.env.I18N_JS || path.join(ROOT, 'webapp/js/i18n.js'), 'utf8');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)).slice(0, 400) : ''}`); };

const stranka = (lang, telo, slovnik, extraHead) => `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><title>Košík</title><meta name="description" content="Hliníkové profily skladem">${extraHead || ''}` +
  `${slovnik ? `<script>window.__I18N=${JSON.stringify(slovnik)};</script>` : ''}</head><body>${telo}<script>${I18N_JS}</script></body></html>`;
const SL = {
  lang: 'en', locale: 'en-GB', currency: 'EUR',
  exact: {
    'Košík': 'Basket', 'Přidat do košíku': 'Add to basket', 'Celkem {n} ks': 'Total {n} pcs', 'Hledat produkty…': 'Search products…', 'Zavřít': 'Close',
    'Pro zobrazení objednávek se prosím <1>přihlaste</1>.': 'Please <1>log in</1> to see your orders.',
    '<1>Kategorie</1> <2>›</2> Kontakt': '<1>Categories</1> <2>›</2> Contact',
    'Cena: <1>{n}</1> bez DPH': 'Price: <1>{n}</1> excl. VAT', 'Opravdu smazat?': 'Really delete?', 'Hliníkové profily skladem': 'Aluminium profiles in stock',
    'Rozměr {n}×{n} mm': 'Size {n}×{n} mm', 'Jedna<1/>dva': 'One<1/>two', 'Nic neprekladej': 'Never used',
  },
  patterns: [['Přidáno: {0} do košíku', 'Added: {0} to basket'], ['{0} položek v košíku', '{0} items in basket'], ['Montáž (+{0} Kč)', 'Installation (+{0} EUR)']],
};

(async () => {
  const browser = await chromium.launch();
  const nova = async (html) => { const ctx = await browser.newContext(); const p = await ctx.newPage(); const chyby = []; p.on('pageerror', e => chyby.push(e.message)); await p.setContent(html); await p.waitForTimeout(80); return { p, chyby, ctx }; };

  // ---------- A: fixtury ----------
  let x = await nova(stranka('cs', '<h1>Košík</h1><button>Přidat do košíku</button>', SL));
  ok((await x.p.textContent('h1')) === 'Košík' && (await x.p.evaluate(() => window.I18N.active)) === false, 'A1 český host: nic se nemění, I18N neaktivní', await x.p.textContent('h1'));
  await x.ctx.close();
  x = await nova(stranka('en', '<h1>Košík</h1>', null));
  ok((await x.p.textContent('h1')) === 'Košík' && (await x.p.evaluate(() => window.I18N.active)) === false && x.chyby.length === 0, 'A2 jazyk bez slovníku: nic se nemění, žádná chyba', x.chyby);
  await x.ctx.close();

  const TELO = `<h1>Košík</h1><button id="b">Přidat do košíku</button><p id="c">Celkem 12 ks</p><p id="c2">Celkem 1 234 ks</p><input id="i" placeholder="Hledat produkty…" title="Zavřít"><input id="s" type="submit" value="Zavřít">
    <p id="m">Pro zobrazení objednávek se prosím <a id="l" href="/login" data-x="1">přihlaste</a>.</p><p id="k"><a id="ka" href="/">Kategorie</a> <span id="kb">›</span> Kontakt</p>
    <p id="pr">Cena: <b id="pb">99</b> bez DPH</p><p id="rz">Rozměr 30×40 mm</p><p id="br">Jedna<br>dva</p><p id="vz">Přidáno: Úhelník 30x30 do košíku</p><p id="vz2">7 položek v košíku</p>
    <p id="ne">Nic neprekladej tady</p><img id="im" alt="Zavřít" src="data:image/gif;base64,R0lGODlhAQABAAAAACw="><script id="sk">var Košík = 1; /* Přidat do košíku */</script><style>.x::after{content:"Košík"}</style><textarea id="ta">Košík</textarea>`;
  x = await nova(stranka('en', TELO, SL));
  const T = async sel => (await x.p.textContent(sel)).replace(/\s+/g, ' ').trim();
  ok((await T('h1')) === 'Basket' && (await T('#b')) === 'Add to basket', 'A3 nadpis a tlačítko přeloženo', [await T('h1'), await T('#b')]);
  ok((await T('#c')) === 'Total 12 pcs' && (await T('#c2')) === 'Total 1 234 pcs', 'A4 číslo se vrátí do překladu (i s mezerou tisíců)', [await T('#c'), await T('#c2')]);
  ok((await x.p.getAttribute('#i', 'placeholder')) === 'Search products…' && (await x.p.getAttribute('#i', 'title')) === 'Close' && (await x.p.getAttribute('#s', 'value')) === 'Close' && (await x.p.getAttribute('#im', 'alt')) === 'Close', 'A5 placeholder, title, alt a value tlačítka', 0);
  ok((await T('#m')) === 'Please log in to see your orders.' && (await x.p.getAttribute('#l', 'href')) === '/login' && (await x.p.getAttribute('#l', 'data-x')) === '1' && (await x.p.evaluate(() => document.getElementById('l').textContent)) === 'log in', 'A6 věta s odkazem: odkaz zůstal (href, atributy), text uvnitř přeložen', await T('#m'));
  ok((await T('#k')) === 'Categories › Contact' && (await x.p.evaluate(() => [...document.querySelectorAll('#k > *')].map(e => e.id).join())) === 'ka,kb', 'A7 drobečková navigace se dvěma značkami, prvky zachovány v pořadí', await T('#k'));
  ok((await T('#pr')) === 'Price: 99 excl. VAT' && (await x.p.evaluate(() => document.getElementById('pb').tagName)) === 'B', 'A8 věta se značkou a číslem uvnitř', await T('#pr'));
  ok((await T('#rz')) === 'Size 30×40 mm' && (await T('#br')) === 'Onetwo' && (await x.p.evaluate(() => !!document.querySelector('#br br'))) === true, 'A9 více čísel a <br> uvnitř věty', [await T('#rz'), await T('#br')]);
  ok((await T('#vz')) === 'Added: Úhelník 30x30 to basket' && (await T('#vz2')) === '7 items in basket', 'A10 vzory s proměnnou částí {0}', [await T('#vz'), await T('#vz2')]);
  ok((await T('#ne')) === 'Nic neprekladej tady', 'A11 věta bez překladu zůstane česky', await T('#ne'));
  ok((await x.p.evaluate(() => document.getElementById('sk').textContent)) === 'var Košík = 1; /* Přidat do košíku */' && (await x.p.evaluate(() => document.getElementById('ta').value)) === 'Košík', 'A12 script / style / textarea se nepřekládají', 0);
  ok((await x.p.title()) === 'Basket' && (await x.p.getAttribute('meta[name=description]', 'content')) === 'Aluminium profiles in stock', 'A13 <title> a meta description', [await x.p.title()]);
  ok((await x.p.evaluate(() => document.documentElement.classList.contains('i18n-pending'))) === false, 'A14 třída i18n-pending se po prvním průchodu odstraní');

  // obsluha udalosti na odkazu ve vete prezije preklad; dynamicky pridany obsah se prelozi hned; zadny dvojity preklad
  await x.p.evaluate(() => { window.__klik = 0; document.getElementById('l').addEventListener('click', e => { e.preventDefault(); window.__klik++; }); });
  await x.p.evaluate(() => { const d = document.createElement('div'); d.id = 'dyn'; d.innerHTML = '<p>Celkem 5 ks</p><button>Zavřít</button><p>Pro zobrazení objednávek se prosím <a id="l2" href="#">přihlaste</a>.</p>'; document.body.appendChild(d); });
  await x.p.waitForTimeout(60);
  ok((await T('#dyn')) === 'Total 5 pcsClosePlease log in to see your orders.', 'A15 dynamicky vložený obsah je přeložen před vykreslením', await T('#dyn'));
  await x.p.evaluate(() => { document.getElementById('c').textContent = 'Celkem 8 ks'; });
  await x.p.waitForTimeout(60);
  ok((await T('#c')) === 'Total 8 pcs', 'A16 změna textu uzlu (characterData) se přeloží', await T('#c'));
  await x.p.evaluate(() => { document.getElementById('i').setAttribute('placeholder', 'Zavřít'); });
  await x.p.waitForTimeout(60);
  ok((await x.p.getAttribute('#i', 'placeholder')) === 'Close', 'A17 změna atributu se přeloží', await x.p.getAttribute('#i', 'placeholder'));
  await x.p.click('#l'); await x.p.click('#l');
  ok((await x.p.evaluate(() => window.__klik)) === 2, 'A18 obsluha události na odkazu uvnitř přeložené věty zůstala (prvek je znovupoužit, ne klonován)', await x.p.evaluate(() => window.__klik));
  const pred = await T('#m'); await x.p.evaluate(() => window.I18N.apply());
  ok((await T('#m')) === pred && (await T('h1')) === 'Basket', 'A19 opakovaný průchod nic nezmění (přeložený text se nepřekládá znovu)', await T('#m'));
  // alert / confirm / prompt
  const dialogy = []; x.p.on('dialog', d => { dialogy.push(d.message()); d.accept('ok'); });
  await x.p.evaluate(() => { alert('Opravdu smazat?'); confirm('Zavřít'); prompt('Přidáno: Něco do košíku', 'Zavřít'); });
  ok(dialogy.join('|') === 'Really delete?|Close|Added: Něco to basket', 'A20 alert / confirm / prompt jdou přes překlad', dialogy);
  ok((await x.p.evaluate(() => window.I18N.t('Celkem 3 ks')) === 'Total 3 pcs') && (await x.p.evaluate(() => window.I18N.t('  Zavřít  '))) === '  Close  ' && (await x.p.evaluate(() => window.I18N.t(5))) === 5, 'A21 I18N.t() zachová okraje a necizí typy', 0);
  ok((await x.p.evaluate(() => window.I18N.money(1234.5, 'EUR'))).replace(/\s/g, ' ').includes('1,234.50') && (await x.p.evaluate(() => window.I18N.money(1200, 'EUR'))) === '€1,200' && x.chyby.length === 0, 'A22 I18N.money: celé částky bez haléřů, jinak 2 desetinná místa, podle jazyka hostu; žádné chyby JS', [await x.p.evaluate(() => window.I18N.money(1234.5, 'EUR')), x.chyby]);
  await x.ctx.close();

  // castky: cesky zapis -> mena a format hostu (server vraci EUR)
  x = await nova(stranka('en', '<p id="m1">12 345,50 Kč</p><p id="m2">1 200 Kč</p><p id="m3">Montáž (+1 234 Kč)</p><p id="m4">Měrná cena: <b id="m4b">3,50 Kč</b> / 1 m</p><p id="m5">Cena 10 EUR bez slev</p><p id="m6">Kód K-120 a 5 ks</p>', SL));
  ok((await T('#m1')) === '€12,345.50' && (await T('#m2')) === '€1,200', 'A24 EN: „12 345,50 Kč“ → €12,345.50, „1 200 Kč“ → €1,200', [await T('#m1'), await T('#m2')]);
  ok((await T('#m3')) === 'Installation (+€1,234)', 'A25 překladová věta s částkou: „Montáž (+1 234 Kč)“ → Installation (+€1,234)', await T('#m3'));
  ok((await T('#m4b')) === '€3.50' && (await T('#m5')) === 'Cena 10 EUR bez slev'.replace('10 EUR', '€10') && (await T('#m6')) === 'Kód K-120 a 5 ks', 'A26 částka v samostatném prvku, „EUR“ za číslem, ostatní čísla se nemění', [await T('#m4b'), await T('#m5'), await T('#m6')]);
  await x.ctx.close();
  x = await nova(stranka('it', '<p id="m1">12 345,50 Kč</p>', Object.assign({}, SL, { lang: 'it', locale: 'it-IT' })));
  ok((await T('#m1')).replace(/\s/g, ' ') === '12.345,50 €', 'A27 IT: „12 345,50 Kč“ → 12.345,50 €', await T('#m1'));
  await x.ctx.close();

  // vykon: tisic uzlu
  const velke = Array.from({ length: 1500 }, (_, i) => `<li>Celkem ${i} ks <b>Zavřít</b></li><li>Řádek ${i} neznámý</li>`).join('');
  x = await nova(stranka('en', `<ul>${velke}</ul>`, SL));
  const ms = await x.p.evaluate(() => { const t = performance.now(); window.I18N.apply(); return performance.now() - t; });
  ok(ms < 1500, `A23 3 000 prvků: opakovaný průchod ${Math.round(ms)} ms (< 1500)`, ms);
  await x.ctx.close();

  // ---------- B: shoda s extraktorem na skutecnych strankach ----------
  const sheet = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs/web_jazyky/10_ui.json'), 'utf8'));
  const exact = {}, patterns = [];
  sheet.forEach(it => { const tr = '§' + it.cs.replace(/(<\/?\d+\/?>)/g, '$1§'); if (/\{\d+\}/.test(it.cs)) patterns.push([it.cs, tr]); else exact[it.cs] = tr; });
  const SLB = { lang: 'en', locale: 'en-GB', currency: 'EUR', exact, patterns };
  const STR = ['index', 'category', 'product', 'moje-objednavky', 'login', 'register', 'forgot-password', 'reset-password', 'verify-email', 'kontakt', 'realizace', 'poptavka-stul', '404', 'blok'];
  const DIA = /[ěščřžýáíéúůďťňĚŠČŘŽÝÁÍÉÚŮĎŤŇ]/;
  for (const s of STR) {
    let html = fs.readFileSync(path.join(ROOT, 'webapp', s + '.html'), 'utf8');
    html = html.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/<html([^>]*?)lang="cs"/i, '<html$1lang="en"');
    html = html.replace('</head>', `<script>window.__I18N=${JSON.stringify(SLB)};</script></head>`).replace('</body>', `<script>${I18N_JS}</script></body>`);
    const ctx = await browser.newContext(); const p = await ctx.newPage(); const chyby = []; p.on('pageerror', e => chyby.push(e.message));
    await p.route('**/*', r => r.abort());                                  // zadna sit (obrazky, fonty)
    await p.setContent(html); await p.waitForTimeout(150);
    const zbytek = await p.evaluate((DIAs) => {
      const re = new RegExp(DIAs), out = [], skip = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEXTAREA: 1, svg: 1, SVG: 1 };
      const w = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
      for (let n; (n = w.nextNode());) { const par = n.parentNode; if (skip[par.tagName] || (par.closest && par.closest('svg'))) continue; const v = n.nodeValue.replace(/\s+/g, ' ').trim(); if (v && re.test(v) && v.indexOf('§') < 0) out.push('T: ' + v.slice(0, 70)); }
      document.querySelectorAll('[placeholder],[title],[alt],[aria-label]').forEach(e => ['placeholder', 'title', 'alt', 'aria-label'].forEach(a => { const v = e.getAttribute(a); if (v && re.test(v) && v.indexOf('§') < 0) out.push(a + ': ' + v.slice(0, 70)); }));
      return out;
    }, DIA.source);
    // vyjimky: vnitrni (zamestnanecke) vety vyrazene extraktorem (Dogus, Vandr, Fio, Interni ...) - na strance nejsou, pripadne se nesmi pocitat
    const INTERNI = /Dogus|🔒|[Ii]nterní|Fio\b|[Vv]andr|[Uu]nity|Shoptet/;
    const skutecne = zbytek.filter(v => !INTERNI.test(v));
    ok(skutecne.length === 0 && chyby.length === 0, `B ${s}.html: po překladu nezbývá žádný statický český text (${zbytek.length - skutecne.length} vnitřních výjimek)`, skutecne.slice(0, 12).concat(chyby));
    await ctx.close();
  }
  await browser.close();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
