// Dialog "Nastaveni nabidky" ve scene: pole "Montaz (% z ceny nabidky)" (bot5, 2026-10-01; Robert: "montaz v online nabidce chci pred
// vytvorenim nabidky zvolit jako % castku"). SKUTECNE casti ze zdroju se vytahnou a pusti v Chromiu:
//   - znaceni dialogu (<div id="offerOptionsModalOverlay"> ... ) a CSS ze scene.html,
//   - funkce a posluchace z webapp/js/scene/path-traced-preview.js (offerMontazPctValue, offerOptionsPayload, openOfferOptionsModal,
//     offerOptSyncMontazUI ... a samotny handler tlacitka "Vytvorit nabidku"); generateSceneOffer je atrapa, ktera zaznamena volby.
// Sceny samotne (three.js, prihlaseni, DB) se test nedotyka.
// Kandidat pred nasazenim: SCENE_HTML=... PATH_TRACED_JS=... node test_montaz_pct_dialog_scena.js
const { chromium } = require('/opt/konfigurator/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const REPO = path.join(__dirname, '../..');
const SCENE_HTML = process.env.SCENE_HTML || path.join(REPO, 'webapp/scene.html');
const PTP = process.env.PATH_TRACED_JS || path.join(REPO, 'webapp/js/scene/path-traced-preview.js');
const OUT = process.env.OUT_DIR || '/tmp/claude-0/montaz_dialog';
fs.mkdirSync(OUT, { recursive: true });
const scene = fs.readFileSync(SCENE_HTML, 'utf8');
const ptp = fs.readFileSync(PTP, 'utf8');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const norm = s => (s || '').replace(/[  ]/g, ' ').replace(/\s+/g, ' ').trim();

// ---- pomocne vytahovani ze zdroju (secte slozene zavorky, preskoci retezce a komentare)
function parovaZavorka(src, odIdx) {          // odIdx = index otviraci "{"; vraci index parove "}"
  let depth = 0, inStr = null, inLine = false, inBlock = false;
  for (let i = odIdx; i < src.length; i++) {
    const c = src[i], n = src[i + 1];
    if (inLine) { if (c === '\n') inLine = false; continue; }
    if (inBlock) { if (c === '*' && n === '/') { inBlock = false; i++; } continue; }
    if (inStr) { if (c === '\\') { i++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === '/' && n === '/') { inLine = true; continue; }
    if (c === '/' && n === '*') { inBlock = true; continue; }
    if (c === '"' || c === "'" || c === '`') { inStr = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) return i; }
  }
  throw new Error('nenalezena parova zavorka');
}
function vytahniFunkci(src, jmeno) {
  const start = src.indexOf('function ' + jmeno + '(');
  if (start < 0) throw new Error('funkce nenalezena: ' + jmeno);
  const o = src.indexOf('{', src.indexOf(')', start));
  return src.slice(start, parovaZavorka(src, o) + 1);
}
function vytahniRadek(src, re, popis) {
  const m = re.exec(src);
  if (!m) throw new Error('radek nenalezen: ' + popis);
  return m[0];
}
function vytahniHandler(src, marker) {
  const s = src.indexOf(marker);
  if (s < 0) throw new Error('handler nenalezen: ' + marker);
  const o = src.indexOf('{', s + marker.length - 3);
  const k = parovaZavorka(src, o);
  const konec = src.indexOf(');', k) + 2;
  return src.slice(s, konec);
}
function vytahniDiv(src, idMarker) {
  const s = src.indexOf(idMarker);
  if (s < 0) throw new Error('znaceni nenalezeno: ' + idMarker);
  let depth = 0, i = s;
  const re = /<div\b|<\/div>/g; re.lastIndex = s;
  let m;
  while ((m = re.exec(src))) { if (m[0] === '</div>') { depth--; if (depth === 0) return src.slice(s, m.index + 6); } else depth++; }
  throw new Error('nenalezen konec znaceni');
}

let zdroj;
try {
  zdroj = {
    modal: vytahniDiv(scene, '<div id="offerOptionsModalOverlay">'),
    styly: [...scene.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n'),
    fn: ['offerMontazPctValue', 'offerOptionsPayload', 'openOfferOptionsModal', 'closeOfferOptionsModal', 'offerOptSyncFixedDepositUI',
      'offerOptSyncHideBomPricesUI', 'offerOptMontazBaseCzk', 'offerOptSyncMontazUI'].map(j => {
      try { return vytahniFunkci(ptp, j); } catch (e) { return null; }
    }),
    fnJmena: ['offerMontazPctValue', 'offerOptionsPayload', 'openOfferOptionsModal', 'closeOfferOptionsModal', 'offerOptSyncFixedDepositUI',
      'offerOptSyncHideBomPricesUI', 'offerOptMontazBaseCzk', 'offerOptSyncMontazUI'],
    listeners: [
      /^document\.getElementById\("offerOptFixedDepositOn"\)\.onchange = offerOptSyncFixedDepositUI;$/m,
      /^document\.getElementById\("offerOptHideBomPrices"\)\.onchange = offerOptSyncHideBomPricesUI;$/m,
      /^document\.getElementById\("offerOptionsModalClose"\)\.addEventListener\("click", closeOfferOptionsModal\);$/m,
      /^document\.getElementById\("offerOptCancel"\)\.addEventListener\("click", closeOfferOptionsModal\);$/m,
    ].map(re => { try { return vytahniRadek(ptp, re, String(re)); } catch (e) { return null; } }),
    listenersMontaz: [
      /^document\.getElementById\("offerOptMontazPct"\)\.addEventListener\("input", offerOptSyncMontazUI\);$/m,
      /^document\.getElementById\("offerOptCustomTotal"\)\.addEventListener\("input", offerOptSyncMontazUI\);$/m,
      /^document\.getElementById\("offerOptHideBomPrices"\)\.addEventListener\("change", offerOptSyncMontazUI\);$/m,
    ].map(re => { try { return vytahniRadek(ptp, re, String(re)); } catch (e) { return null; } }),
    handler: vytahniHandler(ptp, 'document.getElementById("offerOptSubmit").addEventListener("click", async () => {'),
    generate: vytahniFunkci(ptp, 'generateSceneOffer'),
  };
} catch (e) {
  console.log('FAIL priprava zdroju: ' + e.message);
  console.log('\nVYSLEDEK dialog Nastaveni nabidky (montaz %): 0/1 OK');
  process.exit(1);
}

(async () => {
  // ---- 0) pritomnost casti v souborech
  over('0a v dialogu je pole offerOptMontazPct (cislo 0-100) a pole pro orientacni castku', /id="offerOptMontazPct"[^>]*min="0"[^>]*max="100"/.test(zdroj.modal) && /id="offerOptMontazInfo"/.test(zdroj.modal), null);
  over('0b vsechny funkce dialogu (offerMontazPctValue, offerOptionsPayload, openOfferOptionsModal, offerOptSyncMontazUI ...) jsou v path-traced-preview.js',
       zdroj.fn.every(f => f !== null), zdroj.fnJmena.filter((j, i) => zdroj.fn[i] === null));
  over('0c posluchace pole montaze (input, zmena individualni ceny, zmena checkboxu "kusovnik bez cen") jsou zapojeni', zdroj.listenersMontaz.every(r => r !== null), zdroj.listenersMontaz.map(r => r !== null));
  over('0d generateSceneOffer posila offer_options pres offerOptionsPayload(offerOptions) (zadny vlastni literal, ktery by montaz_pct zahodil)',
       /offer_options:\s*offerOptionsPayload\(offerOptions\)/.test(zdroj.generate) && !/hide_bom_prices:\s*!!offerOptions\.hideBomPrices/.test(zdroj.generate), null);
  if (zdroj.fn.some(f => f === null) || zdroj.listenersMontaz.some(r => r === null)) {
    console.log('\nVYSLEDEK dialog Nastaveni nabidky (montaz %): ' + vysl.filter(Boolean).length + '/' + vysl.length + ' OK  (chybi casti, dalsi testy preskoceny)');
    process.exit(1);
  }

  const html = `<!doctype html><html><head><meta charset="utf-8"><style>${zdroj.styly}</style></head><body>
    <div id="statTotalPrice">12345</div><div id="offerStatus"></div><button id="btnGenerateOffer"></button>
    ${zdroj.modal}
    <script>
      var placed = [{}];                                   // scena neni prazdna
      var PRICING_CONFIG = { montaz_pct: 20, packaging_pct: 3 };
      var offerWithRenders = false;                         // stav, ktery handler cte (v souboru je to let nad handlerem)
      window.__volani = [];
      async function generateSceneOffer(o) { window.__volani.push(JSON.parse(JSON.stringify(o))); }   // atrapa: zaznamena volby
      ${zdroj.fn.join('\n')}
      ${zdroj.listeners.filter(Boolean).join('\n')}
      ${zdroj.listenersMontaz.join('\n')}
      ${zdroj.handler}
    </script></body></html>`;
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const chyby = [], dialogy = [];
  page.on('pageerror', e => chyby.push(e.message));
  page.on('dialog', async d => { dialogy.push(d.message()); await d.accept(); });
  await page.setContent(html);

  const stav = () => page.evaluate(() => ({
    hodnota: document.getElementById('offerOptMontazPct').value, info: document.getElementById('offerOptMontazInfo').textContent,
    otevreno: document.getElementById('offerOptionsModalOverlay').classList.contains('open'), volani: window.__volani.length,
  }));
  const otevri = () => page.evaluate(() => openOfferOptionsModal());
  const nastav = async v => { await page.fill('#offerOptMontazPct', String(v)); };
  const odeslat = async () => { await page.click('#offerOptSubmit'); await page.waitForTimeout(80); return page.evaluate(() => window.__volani.slice(-1)[0] || null); };

  // ---- 1) otevreni dialogu: predvyplneno vychozi sazbou z nastaveni
  await otevri();
  let s = await stav();
  over('1a po otevreni je pole predvyplnene vychozi sazbou z nastaveni (20) a dialog je otevreny', s.hodnota === '20' && s.otevreno, s);
  over('1b vedle pole je orientacni castka bez DPH: 20 % z ceny sestavy 12 345 = 2 469 Kc', norm(s.info) === '≈ 2 469 Kč bez DPH', s.info);
  await page.screenshot({ path: path.join(OUT, 'dialog_vychozi.png') });

  // ---- 2) zmena sazby: castka se prepocita
  await nastav(15);
  s = await stav();
  over('2a sazba 15 % -> ≈ 1 852 Kc (12 345 x 0,15 = 1 851,75)', norm(s.info) === '≈ 1 852 Kč bez DPH', s.info);
  await nastav(0);
  s = await stav();
  over('2b sazba 0 (bez montaze) -> zadna castka', s.info === '', s);
  await nastav('');
  s = await stav();
  over('2c prazdne pole (vychozi sazba z nastaveni) -> zadna castka', s.info === '', s);

  // ---- 3) individualni cena (kusovnik bez cen) prebiji cenu sestavy
  await nastav(10);
  await page.check('#offerOptHideBomPrices');
  await page.fill('#offerOptCustomTotal', '50000');
  s = await stav();
  over('3a "kusovnik bez cen" + individualni cena 50 000 -> castka montaze se pocita z ni: 10 % = 5 000 Kc', norm(s.info) === '≈ 5 000 Kč bez DPH', s.info);
  await page.fill('#offerOptCustomTotal', '');
  s = await stav();
  over('3b individualni cena smazana -> zpet z ceny sestavy: 10 % z 12 345 = 1 235 Kc', norm(s.info) === '≈ 1 235 Kč bez DPH', s.info);
  await page.uncheck('#offerOptHideBomPrices');

  // ---- 4) odeslani: do generateSceneOffer jde zvolena sazba
  await nastav(15);
  let v = await odeslat();
  over('4a odeslani se sazbou 15 -> generateSceneOffer dostane montazPct 15 a dialog se zavre', v && v.montazPct === 15 && !(await stav()).otevreno, v);
  await otevri(); await nastav(12.5);
  v = await odeslat();
  over('4b desetinna sazba 12,5 se preda beze ztraty', v && v.montazPct === 12.5, v);
  await otevri(); await nastav(0);
  v = await odeslat();
  over('4c sazba 0 se preda jako 0 (NE null - 0 je platna volba "bez montaze")', v && v.montazPct === 0 && v.montazPct !== null, v);
  await otevri(); await nastav('');
  v = await odeslat();
  over('4d prazdne pole se preda jako null (= plati vychozi sazba z nastaveni)', v && v.montazPct === null, v);
  over('4e ostatni volby nabidky jdou beze zmeny (QR zapnuto, bez terminu, bez skryte platby/stavu, bez fixni zalohy, kusovnik s cenami)',
       v && v.showQr === true && v.deliveryTerm === '' && v.hiddenPaymentMethod === null && v.hiddenDeliveryState === null && v.fixedDepositPct === null && v.hideBomPrices === false && v.customTotal === null, v);

  // ---- 5) neplatna sazba: upozorneni, nic se neodesle, dialog zustane otevreny
  await otevri(); await nastav(150);
  const pred = (await stav()).volani;
  dialogy.length = 0;
  v = await odeslat();
  s = await stav();
  over('5a sazba 150 % -> upozorneni "Montaz musi byt cislo od 0 do 100 %", nic se neodeslalo a dialog zustal otevreny',
       dialogy.some(t => /Montáž musí být číslo od 0 do 100 %/.test(t)) && s.volani === pred && s.otevreno, { dialogy, s, pred });
  await nastav(-5);
  dialogy.length = 0;
  await odeslat();
  s = await stav();
  over('5b zaporna sazba -> totez', dialogy.some(t => /Montáž musí být/.test(t)) && s.volani === pred && s.otevreno, { dialogy, s });

  // ---- 6) po dalsim otevreni dialogu se zase predvyplni vychozi sazba (nezustane posledni hodnota)
  await page.evaluate(() => closeOfferOptionsModal());
  await page.evaluate(() => { PRICING_CONFIG = { montaz_pct: 18, packaging_pct: 3 }; });
  await otevri();
  s = await stav();
  over('6a po zmene vychozi sazby (18 %) a novem otevreni dialogu je v poli 18 a castka 2 222 Kc (12 345 x 0,18)', s.hodnota === '18' && norm(s.info) === '≈ 2 222 Kč bez DPH', s);
  await page.evaluate(() => { PRICING_CONFIG = { montaz_pct: 0 }; });
  await page.evaluate(() => closeOfferOptionsModal()); await otevri();
  s = await stav();
  over('6b vychozi sazba 0 (v nastaveni vypnuta montaz) -> pole 0, zadna castka', s.hodnota === '0' && s.info === '', s);
  await page.evaluate(() => { PRICING_CONFIG = undefined; });
  await page.evaluate(() => closeOfferOptionsModal()); await otevri();
  s = await stav();
  over('6c nastaveni se nenacetlo (PRICING_CONFIG chybi) -> pole 0, dialog nespadne', s.hodnota === '0' && s.otevreno, s);
  await page.evaluate(() => { PRICING_CONFIG = { montaz_pct: 20, packaging_pct: 3 }; });

  // ---- 7) funkce offerOptionsPayload / offerMontazPctValue primo
  const p = await page.evaluate(() => ({
    prazdne: offerOptionsPayload({}), nula: offerOptionsPayload({ montazPct: 0 }), plne: offerOptionsPayload({ showQr: false, deliveryTerm: '4 tydny', hiddenPaymentMethod: 'dobirka', hiddenDeliveryState: 'smontovano', fixedDepositPct: 70, hideBomPrices: true, montazPct: 15 }),
    bezArg: offerOptionsPayload(), hodnoty: [null, undefined, '', 0, '0', 15, '12,5', '12.5', 100, 100.01, -1, 'abc', NaN, 7.556].map(x => offerMontazPctValue(x)),
  }));
  over('7a offerOptionsPayload({}) = puvodni vychozi volby + montaz_pct null', JSON.stringify(p.prazdne) === JSON.stringify({ show_qr: true, delivery_term: null, hidden_payment_method: null, hidden_delivery_state: null, fixed_deposit_pct: null, hide_bom_prices: false, montaz_pct: null }), p.prazdne);
  over('7b montazPct 0 zustane 0 (zadne "|| null")', p.nula.montaz_pct === 0, p.nula);
  over('7c vsechny volby spolu: stejne klice a hodnoty jako puvodni literal + montaz_pct 15', JSON.stringify(p.plne) === JSON.stringify({ show_qr: false, delivery_term: '4 tydny', hidden_payment_method: 'dobirka', hidden_delivery_state: 'smontovano', fixed_deposit_pct: 70, hide_bom_prices: true, montaz_pct: 15 }), p.plne);
  over('7d volani bez argumentu nespadne', p.bezArg.montaz_pct === null, p.bezArg);
  over('7e offerMontazPctValue: null,undefined,"" -> null; 0,"0" -> 0; 15 -> 15; "12,5" a "12.5" -> 12.5; 100 -> 100; 100.01,-1,"abc",NaN -> null; 7.556 -> 7.56',
       JSON.stringify(p.hodnoty) === JSON.stringify([null, null, null, 0, 0, 15, 12.5, 12.5, 100, null, null, null, null, 7.56]), p.hodnoty);

  // ---- 8) vzhled: pole je videt a vejde se do dialogu (po rolovani), nepretece
  await otevri();
  const vz = await page.evaluate(() => {
    const box = document.getElementById('offerOptionsModalBox'), pole = document.getElementById('offerOptMontazPct'), info = document.getElementById('offerOptMontazInfo');
    pole.scrollIntoView({ block: 'center' });
    const b = box.getBoundingClientRect(), r = pole.getBoundingClientRect(), i = info.getBoundingClientRect();
    return { poleViditelne: r.width > 40 && r.height > 15 && r.top >= b.top && r.bottom <= b.bottom, infoVpravoOdPole: i.left >= r.right - 1, boxPretekaVodorovne: box.scrollWidth > box.clientWidth + 1,
             pismo: getComputedStyle(pole).fontSize, barvaPozadi: getComputedStyle(pole).backgroundColor };
  });
  over('8 pole montaze je v dialogu videt, castka je vpravo vedle nej, dialog nepretece do sirky', vz.poleViditelne && vz.infoVpravoOdPole && !vz.boxPretekaVodorovne, vz);
  await page.screenshot({ path: path.join(OUT, 'dialog_pole_montaze.png') });
  over('9 bez JS chyb', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK dialog Nastaveni nabidky (montaz %): ${ok}/${vysl.length} OK   (snimky: ${OUT})`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
