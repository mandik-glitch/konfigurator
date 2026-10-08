// Online nabidka: SLEVA v cenovem souhrnu (bot16, 2026-10-07; Robert: "chci v cenovem souhrnu online nabidky nabidnout slevu, i v te 0133 zpetne") - stranka (frontend).
// Backend (offer_options.discount_pct, verejny payload offer.discount_pct, _offer_gross_total) ma vlastni testy: test_sleva_backend.py a test_sleva_endpointy.py v teto slozce.
// Overuje na SKUTECNE strance webapp/nabidka-online.html v Chromiu proti falesnemu serveru (harness bot8): radek "Sleva X %" v cenove tabulce (zaporna castka), rozpis v banneru
// ("zbozi bez DPH A - sleva X % B"), celkova cena po sleve, pocet kusu, montaz z ceny PO sleve (info pod tabulkou i zvolena v souctu), kusovnik bez cen (jen banner), nabidka BEZ slevy beze zmeny.
// Spusteni: node test_sleva_stranka.js     Kandidat: NABIDKA_HTML=/cesta/nabidka-online.html node test_sleva_stranka.js   (puvodni verze MUSI selhat)
const { otevriNabidku, vzorovaNabidka } = require('../2026-10-06_nabidka_montaz_polozky_testy/harness');
const vm = require('vm'), fs = require('fs'), path = require('path');
const { vytahniFunkci } = require('../2026-10-01_kotovani_testy/harness_koty');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const KLIC = page => page.evaluate(() => (document.querySelector('.slide.active') || { dataset: {} }).dataset.key);
async function naCeny(page) {
  for (let i = 0; i < 12 && (await KLIC(page)) !== 'pricing'; i++) { await page.keyboard.press('ArrowRight'); await page.waitForTimeout(450); }
  await page.waitForTimeout(500);
}
const cisla = t => (String(t).match(/\d[\d\s ]*(?:,\d+)?/g) || []).map(x => parseFloat(x.replace(/[\s ]/g, '').replace(',', '.')));
const stav = page => page.evaluate(() => {
  const t = id => { const e = document.getElementById(id); return e ? e.textContent.replace(/\s+/g, ' ').trim() : null; };
  const r = document.querySelector('tr.it-discount');
  return { hodnota: t('totalBannerValue'), detail: t('totalBannerDetail'), dph: t('totalBannerVat'), montaz: t('montazInfo'),
           radek: r ? { text: r.textContent.replace(/\s+/g, ' ').trim(), total: (r.querySelector('.it-total') || {}).textContent, viditelny: r.getBoundingClientRect().height > 0 } : null,
           radkyTabulky: document.querySelectorAll('table.items tbody tr').length };
});
const nab = (uprav, oo = {}, prefs = null) => vzorovaNabidka(d => { d.offer_options = Object.assign({}, d.offer_options, oo); if (prefs) d.order_prefs = prefs; return uprav(d) || d; });
const kc = n => Math.round(n).toLocaleString('cs-CZ').replace(/ /g, ' ');

(async () => {
  // A) bez slevy: nic se nezmeni (pole chybi = starsi API; pole 0 = bez slevy)
  for (const [nazev, uprav] of [['pole discount_pct chybi (starsi API)', d => d], ['discount_pct 0', d => { d.discount_pct = 0; return d; }]]) {
    const { browser, page, chyby } = await otevriNabidku({ nabidka: nab(uprav) });
    await naCeny(page);
    const s = await stav(page);
    over(`A ${nazev}: zadny radek Sleva, banner 27 353 Kc bez rozpisu slevy`, s.radek === null && /27\s353/.test(s.hodnota) && !/sleva/i.test(s.detail || ''), s);
    over(`A ${nazev}: bez chyb JS`, chyby.length === 0, chyby);
    await browser.close();
  }
  // B) sleva 10 %
  {
    const { browser, page, chyby } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = 10; return d; }) });
    await naCeny(page);
    const s = await stav(page);
    over('B sleva 10 %: v cenove tabulce je radek "Sleva 10 %" se zapornou castkou -2 735 Kc', s.radek && s.radek.viditelny && /Sleva 10 %/.test(s.radek.text) && /[−-]\s?2\s735/.test(s.radek.total), s.radek);
    over('B banner: celkova cena po sleve 24 618 Kc (27 353 - 2 735,30)', /24\s618/.test(s.hodnota), s.hodnota);
    over('B rozpis banneru: "zbozi bez DPH 27 353 Kc - sleva 10 % 2 735 Kc"', /zboží bez DPH 27\s353\s*Kč\s*[−-]\s*sleva 10 %\s*2\s735\s*Kč/.test(s.detail || ''), s.detail);
    const gross = cisla((s.dph || '').split('k úhradě')[1] || '')[0];
    over('B k uhrade vc. DPH = po sleve x 1,21 = 29 787 Kc (+-1)', Math.abs(gross - 29787) <= 1, s.dph);
    over('B montaz (21 % DPH info) pod tabulkou se pocita z ceny PO sleve: 20 % z 24 617,70 = 4 923,54', /po slevě/.test(s.montaz || '') && /4\s924/.test(s.montaz || ''), s.montaz);
    over('B bez chyb JS', chyby.length === 0, chyby);
    await browser.close();
  }
  // C) zlomkova sleva (carka)
  {
    const { browser, page } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = 12.5; return d; }) });
    await naCeny(page);
    const s = await stav(page);
    over('C sleva 12,5 %: radek "Sleva 12,5 %", banner 23 934 Kc (27 353 - 3 419,13)', s.radek && /Sleva 12,5 %/.test(s.radek.text) && /23\s934/.test(s.hodnota), s);
    await browser.close();
  }
  // D) pocet kusu 3
  {
    const { browser, page } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = 10; return d; }, {}, { qty: 3, deposit_pct: 70, payment_method: 'zaloha', delivery_state: 'demontovano', shipping_method: 'vlastni' }) });
    await naCeny(page);
    const s = await stav(page);
    over('D 3 ks se slevou 10 %: banner (82 059 - 8 205,90) = 73 853 Kc a rozpis "3 ks x 27 353 Kc bez DPH 82 059 Kc - sleva 10 % 8 206 Kc"', /73\s853/.test(s.hodnota) && /3 ks × 27\s353\s*Kč bez DPH 82\s059\s*Kč\s*[−-]\s*sleva 10 %\s*8\s206\s*Kč/.test(s.detail || ''), s);
    await browser.close();
  }
  // E) sestava do auta se zvolenou montazi: montaz z ceny po sleve je v souctu
  {
    const { browser, page } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = 10; return d; }, { is_vehicle_assembly: true }, { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha', deposit_pct: 70, payment_method: 'zaloha' }) });
    await naCeny(page);
    const s = await stav(page);
    over('E auto + zvolena montaz + sleva 10 %: celkem 24 617,70 + 4 923,54 = 29 541 Kc, v rozpisu sleva i montaz 4 924 Kc', /29\s541/.test(s.hodnota) && /sleva 10 %/.test(s.detail || '') && /montáž bez DPH 4\s924\s*Kč/.test(s.detail || ''), s);
    await browser.close();
  }
  // F) kusovnik bez cen (individualni cena): radek Sleva se v tabulce neukazuje (tabulka nema ceny), sleva je v banneru
  {
    const { browser, page } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = 10; return d; }, { hide_bom_prices: true }) });
    await naCeny(page);
    const s = await stav(page);
    over('F kusovnik bez cen: zadny radek Sleva v tabulce, rozpis banneru slevu ukazuje', s.radek === null && /sleva 10 %/.test(s.detail || ''), s);
    await browser.close();
  }
  // G) sleva 100 % a hranice: neplatne hodnoty z API se ignoruji
  for (const [nazev, v, cekano] of [['150 (nad 100)', 150, false], ['zaporna', -5, false], ['text', 'abc', false], ['100 %', 100, true]]) {
    const { browser, page } = await otevriNabidku({ nabidka: nab(d => { d.discount_pct = v; return d; }) });
    await naCeny(page);
    const s = await stav(page);
    over(`G discount_pct ${nazev}: ${cekano ? 'radek Sleva je, cena 0 Kc' : 'ignoruje se (zadny radek, cena 27 353 Kc)'}`, cekano ? (s.radek !== null && /^0\s?Kč/.test(s.hodnota || '')) : (s.radek === null && /27\s353/.test(s.hodnota)), s);
    await browser.close();
  }
  // H) pricky do multiboxu (bot8) + sleva - stejny vzorec jako backend (_offer_gross_total): sleva jen ze zbozi, montaz z ceny po sleve PLUS pricky (funkce z kodu stranky v izolovanem kontextu, PRICKY = maketa 500 Kc/ks)
  {
    const HTML = fs.readFileSync(process.env.NABIDKA_HTML || path.join(__dirname, '../../webapp/nabidka-online.html'), 'utf8');
    const ctx = vm.createContext({ PRICKY: { perKus: () => 500 } });
    vm.runInContext(['effectiveQty', 'montazJeVolba', 'montazNetFor', 'discountPctOf', 'goodsNetAfterDiscount', 'effectiveNetTotal'].map(n => vytahniFunkci(HTML, n)).join('\n'), ctx);
    const nab = { total_price: 10000, montaz_pct: 20, discount_pct: 10, offer_options: { is_vehicle_assembly: true } };
    const r = ctx.effectiveNetTotal(nab, { qty: 2, montaz_zvolena: true });
    over('H pricky + sleva: zbozi 20 000 - 10 % = 18 000, pricky 2 x 500 = 1 000 (neslevnuji se), montaz 20 % z 19 000 = 3 800, celkem 22 800 (backend: 27 588 s DPH)', r.goodsNet === 18000 && r.prickyNet === 1000 && r.itemsNet === 19000 && r.montazNet === 3800 && r.total === 22800, r);
    const r0 = ctx.effectiveNetTotal({ total_price: 10000, montaz_pct: 20, offer_options: { is_vehicle_assembly: true } }, { qty: 1, montaz_zvolena: true });
    over('H bez slevy s prickami: zbozi 10 000 + pricky 500, montaz 20 % z 10 500 = 2 100, celkem 12 600 (puvodni chovani bot8)', r0.discountNet === 0 && r0.itemsNet === 10500 && r0.montazNet === 2100 && r0.total === 12600, r0);
  }
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK sleva v online nabidce - stranka: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('CHYBA TESTU', e); process.exit(2); });
