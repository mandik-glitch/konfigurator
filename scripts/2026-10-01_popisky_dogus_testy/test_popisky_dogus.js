// Test popisku koeficientu Doguskalip v adminu (bot5, 2026-10-01; nalez bot16 pres bot3): koeficient kategorie
// (content_categories.dogus_price_coefficient) pocita E-SHOPOVOU cenu z Dogus USD, NE cenu ve 3D scene.
// SKUTECNY admin.html + skripty v Chromiu proti falesnemu serveru (harness skladove karty, zadna sit, zadna DB).
// Spusteni: node test_popisky_dogus.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: ADMIN_HTML=... SKLAD_PRODUKTY_JS=... node test_popisky_dogus.js
// Mutacni kontrola: stejny test nad ZACHOVANOU puvodni verzi (ADMIN_HTML=admin.html.base ...) musi selhat.
const { otevriAdmin, otevriKartu } = require('../2026-09-30_karta_produktu_testy/harness');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const ploch = s => (s || '').replace(/\s+/g, ' ').trim();

(async () => {
  const { browser, page, chyby } = await otevriAdmin();

  // --- editor kategorie: popisek + napoveda u pole #cemDogusCoef
  const editor = await page.evaluate(() => {
    const inp = document.getElementById('cemDogusCoef');
    const lab = document.querySelector('label[for="cemDogusCoef"]');
    const hint = inp && inp.nextElementSibling;
    return {
      existuje: !!inp, label: lab ? lab.textContent : null, placeholder: inp ? inp.getAttribute('placeholder') : null,
      hintTag: hint ? hint.tagName + '.' + hint.className : null, hint: hint ? hint.textContent : null,
      stejnyRodic: !!(lab && inp && lab.parentElement === inp.parentElement),
    };
  });
  const ed = ploch(editor.hint);
  over('E1 pole koeficientu v editoru kategorie existuje (id cemDogusCoef) a ma sve <label for>', editor.existuje && editor.label && editor.stejnyRodic, editor);
  over('E2 popisek rika, ze jde o E-SHOPOVOU cenu z Doguskalip a NEzminuje 3D scenu', /e-shopov/i.test(editor.label || '') && /Doguskalip/.test(editor.label || '') && !/3D/.test(editor.label || ''), editor.label);
  over('E3 napoveda je odstavec .hint hned za polem', editor.hintTag === 'P.hint', editor.hintTag);
  over('E4 napoveda: vzorec USD x kurz Fio x koeficient, tyce x 3, nahoru na cele Kc',
       /USD/.test(ed) && /kurz Fio/.test(ed) && /koeficient/.test(ed) && /× 3/.test(ed) && /nahoru/.test(ed), ed);
  over('E5 napoveda: scena cte e-shopovou cenu (÷ 3 = za metr) a koeficient sceny je JINY', /÷ 3/.test(ed) && /koeficient scény je jiný/.test(ed), ed);
  over('E6 napoveda: prazdne = kategorie se preskoci, ceny zustanou stare (a kde se to hlasi)', /Prázdné = kategorie se při přepočtu přeskočí/.test(ed) && /zůstanou staré/.test(ed) && /Návrhy na doplnění/.test(ed), ed);
  over('E7 napoveda uz NETVRDI, ze koeficient nasobi cenu profilu ve 3D scene, ani ze prazdne = zadny prepocet',
       !/Násobí cenu profilu ve 3D scéně/.test(ed) && !/žádný přepočet/i.test(ed) && !/bez přepočtu/i.test(editor.placeholder || ''), { ed, ph: editor.placeholder });

  // --- zalozka "Koeficienty cen": odstavec pod nadpisem "Koeficient Doguskalip (podle kategorie)"
  const zal = await page.evaluate(() => {
    const t = document.getElementById('tab-pricecoef');
    if (!t) return { existuje: false };
    const h3 = [...t.querySelectorAll('h3')].find(h => /Doguskalip/.test(h.textContent));
    const p = h3 && h3.nextElementSibling;
    const poradi = ['scenePriceCoefInput', 'btnSaveScenePriceCoef', 'btnPriceCoefCheckAll', 'priceCoefTable', 'priceCoefTbody', 'priceCoefMsg']
      .map(id => { const e = document.getElementById(id); return { id, v: !!e, vTabu: !!e && t.contains(e) }; });
    // poradi podle DOM (zalozka je skryta, takze rozlozeni stranky nic nerika)
    const tlacitko = document.getElementById('btnPriceCoefCheckAll'), tabulka = document.getElementById('priceCoefTable');
    const tlacitkoNadTabulkou = !!tlacitko && !!tabulka && !!(tlacitko.compareDocumentPosition(tabulka) & Node.DOCUMENT_POSITION_FOLLOWING);
    return {
      existuje: true, h3: h3 ? h3.textContent : null, pTag: p ? p.tagName + '.' + p.className : null, p: p ? p.textContent : null,
      poradi, tlacitkoNadTabulkou,
      nadpisy: [...t.querySelectorAll('h3')].map(h => h.textContent.trim()),
      pocetHint: t.querySelectorAll('p.hint').length,
    };
  });
  const zp = ploch(zal.p);
  over('Z1 zalozka Koeficienty cen ma nadpis "Koeficient Doguskalip (podle kategorie)" a hned za nim odstavec .hint', zal.existuje && /Koeficient Doguskalip \(podle kategorie\)/.test(zal.h3 || '') && zal.pTag === 'P.hint', zal);
  over('Z2 odstavec: e-shopova prodejni cena z nakupni USD ceny, kazdou noc, USD x kurz Fio x koeficient, tyce x 3, nahoru',
       /e-shopová prodejní cena/.test(zp) && /každou noc/.test(zp) && /USD/.test(zp) && /kurz Fio/.test(zp) && /× 3/.test(zp) && /nahoru/.test(zp), zp);
  over('Z3 odstavec: scena cte e-shopovou cenu (÷ 3) a navic nasobi koeficient konfiguratoru', /÷ 3/.test(zp) && /koeficient konfigurátoru/.test(zp), zp);
  over('Z4 odstavec: kategorie bez koeficientu se preskoci + kde se to hlasi', /bez koeficientu se při přepočtu přeskočí/.test(zp) && /Návrhy na doplnění/.test(zp), zp);
  over('Z5 odstavec uz NETVRDI "koeficient prepoctu ceny pro 3D scenu" ani neodkazuje na SQL soubor',
       !/přepočtu ceny pro 3D scénu/.test(zp) && !/\.sql/.test(zp), zp);
  over('Z6 zbytek puvodniho odstavce (Zastupce / Zjistit / dopocet rozdilem) zustal', /Sloupec "Zástupce" je 1 náhodně vybraný produkt/.test(zp) && /"Zjistit" stáhne aktuální cenu z logiman\.cz/.test(zp) && /dopočet koeficientu rozdílem/.test(zp), zp);
  over('Z7 struktura zalozky nenarusena: vsechny prvky (koeficient sceny, tlacitka, tabulka) existuji UVNITR #tab-pricecoef',
       zal.poradi.every(x => x.v && x.vTabu), zal.poradi);
  over('Z8 poradi: tlacitko "Zjistit ceny" je nad tabulkou', zal.tlacitkoNadTabulkou, zal.tlacitkoNadTabulkou);
  over('Z9 zalozka ma porad stejne nadpisy sekci', JSON.stringify(zal.nadpisy) === JSON.stringify(['Koeficient konfigurátoru', 'Koeficient Doguskalip (podle kategorie)']), zal.nadpisy);

  // --- skladova karta: "Zdroj ceny (Doguskalip)" - frekvence a vzorec
  await otevriKartu(page, 3671);
  const karta = await page.evaluate(() => {
    const l = [...document.querySelectorAll('.sc-stat-label')].find(e => /Zdroj ceny \(Doguskalip\)/.test(e.textContent));
    return l ? l.textContent : null;
  });
  const kt = ploch(karta);
  over('K1 karta: cena se obnovuje kazdou noc (ne "1x tydne / nedele")', /každou noc/.test(kt) && !/týdně|neděle/.test(kt), kt);
  over('K2 karta: vzorec USD x koeficient kategorie x kurz Fio, u tyci navic x 3, nahoru na cele koruny',
       /cena v USD × koeficient kategorie × aktuální kurz Fio/.test(kt) && /u tyčí navíc × 3/.test(kt) && /nahoru na celé koruny/.test(kt), kt);
  over('K3 karta: zdrojovy skript je porad uveden', /scripts\/2026-08-09_dogus_price_recompute\.py/.test(kt), kt);

  over('X0 stranka behem testu nevyhodila zadnou chybu skriptu', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\n${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
