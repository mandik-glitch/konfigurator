// Stranka produktu (product.html): zastupce karty + volby "Montaz" / "Bez boxu" -> co odejde do kosiku (bot5, 2026-10-01).
// CHYBA: u zastupce (is_master) stranka volby nabizela a pricitala k cene, ale do kosiku (POST /api/cart/items) neposlala
// ani assembly_id, ani volby (pdUserSelectedAssemblyId = is_master ? null : id) -> zakaznik zaplatil cenu BEZ montaze.
// SKUTECNA stranka + skripty v Chromiu proti falesnemu serveru (harness_produkt.js, zadna sit, zadna DB).
// Spusteni: node test_produkt_zastupce_kosik.js   (konci kodem 0 jen kdyz VSE prosla)
// Kandidat pred nasazenim: PRODUCT_HTML=/cesta/k/product.html node test_produkt_zastupce_kosik.js
// Mutacni kontrola: PRODUCT_HTML=<puvodni verze> musi selhat na S2, S3, S9.
const { otevriProdukt, posunVerzi } = require('./harness_produkt');

const vysl = [];
const over = (nazev, podminka, detail) => {
  vysl.push(!!podminka);
  console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail)));
};
const norm = s => (s || '').replace(/[\u00a0\u202f]/g, ' ').trim();   // cs-CZ cisla maji pevnou / uzkou pevnou mezeru
const cena = page => page.evaluate(() => document.getElementById('pdPrice').textContent).then(norm);
const klik = (page, sel) => page.evaluate(s => { const e = document.querySelector(s); if (!e) throw new Error('nenalezeno: ' + s); e.click(); }, sel);
const montaz = async (page, misto) => { await klik(page, '#pdMontazOption'); if (misto) { await page.waitForTimeout(100); await klik(page, `input[name="pdMontazMisto"][value="${misto}"]`); } await page.waitForTimeout(100); };
const boxy = async page => { await klik(page, '#pdBezBoxuOption'); await page.waitForTimeout(100); };
async function doKosiku(page, posts) {
  const pred = posts.length;
  await klik(page, '#pdAddCartBtn');
  for (let i = 0; i < 30 && posts.length === pred; i++) await page.waitForTimeout(100);
  await page.waitForTimeout(150);
  return posts.length > pred ? posts[posts.length - 1].body : null;
}
const bezDrobnosti = chyby => chyby.filter(m => !/Failed to fetch|net::/.test(m));

(async () => {
  // S1: nic nezmeneno (zastupce = vychozi stav karty) -> obycejny produkt, bez assembly_id (cena karty vcetne slev/kuponu)
  {
    const { browser, page, posts, chyby } = await otevriProdukt();
    const b = await doKosiku(page, posts);
    over('S1 vychozi stav (zastupce, nikdo nic nemenil): do kosiku obycejny produkt BEZ assembly_id a voleb',
         b && b.product_id === 3943 && b.qty === 1 && b.assembly_id === undefined && b.montaz_zvolena === undefined && b.bez_boxu === undefined, b);
    over('S1b stranka behem testu nevyhodila chybu skriptu', bezDrobnosti(chyby).length === 0, chyby.slice(0, 3));
    await browser.close();
  }

  // S2: HLAVNI CHYBA - zakaznik prejede na jine provedeni a vrati se na zastupce, zaskrtne montaz + misto
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');                                 // zpet na zastupce (provedeni A)
    over('S2a po navratu na zastupce stranka nabizi montaz s cenou zastupce (+4 616 Kc)',
         /\+4 616 Kč/.test(norm(await page.evaluate(() => document.getElementById('pdMontazOptionLabel').textContent))), await page.evaluate(() => document.getElementById('pdMontazOptionLabel').textContent));
    await montaz(page, 'praha');
    over('S2b cena na strance po zaskrtnuti montaze = 23 081 + 4 616 = 27 697 Kc', (await cena(page)) === '27 697 Kč', await cena(page));
    const b = await doKosiku(page, posts);
    over('S2 do kosiku jde zastupce SE svym assembly_id (344), montaz_zvolena a mistem - cena v kosiku bude sedet s cenou na strance',
         b && b.assembly_id === 344 && b.montaz_zvolena === true && b.montaz_misto === 'praha' && b.bez_boxu === false, b);
    await browser.close();
  }

  // S3: zastupce + jen "Bez boxu"
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    await boxy(page);
    over('S3a cena po zaskrtnuti "Bez boxu" = 23 081 - 1 520 = 21 561 Kc', (await cena(page)) === '21 561 Kč', await cena(page));
    const b = await doKosiku(page, posts);
    over('S3 do kosiku jde zastupce s assembly_id (344) a bez_boxu, montaz vypnuta a bez mista',
         b && b.assembly_id === 344 && b.bez_boxu === true && b.montaz_zvolena === false && b.montaz_misto === undefined, b);
    await browser.close();
  }

  // S4: zastupce vybran posuvnikem, ale NIC nezaskrtnuto -> beze zmeny obycejny produkt (sleva/kupon karty zustavaji)
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    const b = await doKosiku(page, posts);
    over('S4 zastupce vybrany posuvnikem, zadna volba: BEZ assembly_id (jako driv, cena = cena karty)',
         b && b.assembly_id === undefined && b.montaz_zvolena === undefined && b.bez_boxu === undefined, b);
    await browser.close();
  }

  // S5: jine provedeni (B) + montaz - beze zmeny
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await montaz(page, 'slavicin');
    const b = await doKosiku(page, posts);
    over('S5 jine provedeni (B) + montaz: assembly_id 345, montaz a misto (beze zmeny)',
         b && b.assembly_id === 345 && b.montaz_zvolena === true && b.montaz_misto === 'slavicin' && b.bez_boxu === false, b);
    await browser.close();
  }

  // S6: montaz zaskrtnuta na zastupci, pak posuvnik na B - volba se NESMI prenest na B (checkboxy se resetuji)
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    await montaz(page, 'praha');
    await posunVerzi(page, 'ArrowRight');                                // na B
    const b = await doKosiku(page, posts);
    over('S6 po prejezdu ze zastupce na B se volba montaze neprenese: assembly_id 345, montaz vypnuta',
         b && b.assembly_id === 345 && b.montaz_zvolena === false && b.bez_boxu === false && b.montaz_misto === undefined, b);
    await browser.close();
  }

  // S7: montaz na zastupci, pak B a zpet na zastupce (checkboxy odskrtnuty) -> zadna zastarala volba, zastupce bez assembly_id
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    await montaz(page, 'praha');
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');                                 // znovu zastupce, volby resetovane
    over('S7a po navratu jsou volby odskrtnute, cena zase 23 081 Kc', (await cena(page)) === '23 081 Kč', await cena(page));
    const b = await doKosiku(page, posts);
    over('S7 zadna zastarala volba: zastupce bez voleb jde BEZ assembly_id',
         b && b.assembly_id === undefined && b.montaz_zvolena === undefined, b);
    await browser.close();
  }

  // S8: montaz zaskrtnuta, misto NEvybrano -> klientska kontrola (nic neodejde)
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    await montaz(page, null);
    const b = await doKosiku(page, posts);
    over('S8 montaz bez mista: nic se do kosiku neposle (stranka zada vybrat misto)', b === null && posts.length === 0, b);
    await browser.close();
  }

  // S9: zastupce + montaz + "bez boxu" zaroven
  {
    const { browser, page, posts } = await otevriProdukt();
    await posunVerzi(page, 'ArrowRight');
    await posunVerzi(page, 'ArrowLeft');
    await montaz(page, 'slavicin');
    await boxy(page);
    over('S9a cena = 23 081 + 4 616 - 1 520 = 26 177 Kc', (await cena(page)) === '26 177 Kč', await cena(page));
    const b = await doKosiku(page, posts);
    over('S9 zastupce + montaz i "bez boxu": assembly_id 344, obe volby, misto Slavicin',
         b && b.assembly_id === 344 && b.montaz_zvolena === true && b.bez_boxu === true && b.montaz_misto === 'slavicin', b);
    await browser.close();
  }

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK stranka produktu - zastupce + montaz: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e.message); process.exit(2); });
