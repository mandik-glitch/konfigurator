// Montaz (Praha / Slavicin) v online nabidce (bot8 2026-10-06, UPRAVENO bot5 2026-10-06 podle Roberta: JEN sestavy do aut, vylucuje dopravu; stul a ostatni: jen informace). SKUTECNA stranka v Chromiu proti falesnemu
// serveru (harness.js), nic se nezapisuje. Hlida: bezna nabidka (ne sestava do auta) se sazbou montaze > 0 ma pod "Dodanim ve stavu" volbu Montaz / Bez montaze a Misto montaze
// (Praha, Slavicin z /api/montaz-mista), volba meni hlavni cenu (sazba % z zbozi, nasobi se poctem kusu), uklada se (order-prefs montaz_zvolena + montaz_misto), sazba 0 = nic se nenabizi
// (nabidky z konfigurace mimo CR), sestava do auta zustava beze zmeny (montaz NAHRAZUJE Dodani ve stavu), konfiguracni nabidka se chova jako ostatni.
// Spusteni: node test_montaz.js     Kandidat: NABIDKA_HTML=/cesta/k/nabidka-online.html node test_montaz.js
const { otevriNabidku, naCenovouStranku, vzorovaNabidka, cislo } = require('./harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };
const stav = () => {
  const q = s => document.querySelector(s), t = e => e ? e.textContent.replace(/\s+/g, ' ').trim() : null;
  const radky = [...document.querySelectorAll('#orderOpts .opt-row')].map(r => t(r.querySelector('.opt-label')));
  const misto = q('#montazMistoRow');
  return {
    radky, banner: t(q('#totalBannerValue')), detail: t(q('#totalBannerDetail')), vat: t(q('#totalBannerVat')), info: t(q('#montazInfo')),
    btnMontaz: t(q('#montazOnBtn')), montazAktivni: !!q('#montazOnBtn') && q('#montazOnBtn').classList.contains('active'),
    mistoViditelne: !!misto && getComputedStyle(misto).display !== 'none', mista: misto ? [...misto.querySelectorAll('.opt-btn')].map(b => ({ nazev: t(b), aktivni: b.classList.contains('active'), val: b.dataset.val })) : [],
    mistoHint: misto ? t(misto.querySelector('.opt-hint')) : null,
  };
};
const upravit = (u) => vzorovaNabidka(d => { d.order_prefs = null; d.montaz_volba = true; return u(d) || d; });          // payload NOVEHO backendu nese montaz_volba: true

(async () => {
  // ---- 1) sestava do auta (montaz NAHRAZUJE Dodani ve stavu), sazba 20 %
  let { browser, page, chyby, posty } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 20; d.total_price = 10000; }) });
  await naCenovouStranku(page);
  let s = await page.evaluate(stav);
  over('M1 sestava do auta: Volby objednavky maji "Montaz" a "Misto montaze" a ZADNE "Dodani ve stavu"', !s.radky.includes('Dodání ve stavu') && s.radky.includes('Montáž') && s.radky.includes('Místo montáže'), s.radky);
  over('M2 vychozi stav: montaz NEzvolena, misto montaze (Praha / Slavicin) je VIDET hned (zadne neni aktivni), hlavni cena = 10 000 Kc bez DPH', !s.montazAktivni && s.mistoViditelne && s.mista.length === 2 && s.mista.every(m => !m.aktivni) && cislo(s.banner) === 10000, [s.montazAktivni, s.mistoViditelne, s.mista, s.banner]);
  over('M3 stitek tlacitka ukazuje cenu montaze (20 % z 10 000 = 2 000 Kc bez DPH / 2 420 Kc vc. DPH)', /Montáž \(\+2[  ]?000 Kč bez DPH \/ 2[  ]?420 Kč vč\. DPH\)/.test(s.btnMontaz), s.btnMontaz);
  over('M4 pod tabulkou info o montazi rika "volba nize" (uz neni jen "neni v cene")', /Montáž 20 % z ceny \(volitelná služba, volba níže\)/.test(s.info || ''), s.info);
  over('M5 mista montaze z katalogu: Praha a Slavicin', s.mista.length === 2 && s.mista[0].nazev === 'Praha' && s.mista[1].nazev === 'Slavičín', s.mista);

  await page.click('#montazOnBtn');
  await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  over('M6 po zvoleni montaze: hlavni cena 12 000 Kc bez DPH (+20 %), v rozpisu "montaz bez DPH 2 000 Kc"', cislo(s.banner) === 12000 && /montáž bez DPH 2[  ]?000 Kč/.test(s.detail || ''), [s.banner, s.detail]);
  over('M7 k uhrade vc. DPH 14 520 Kc', /14[  ]?520/.test(s.vat || ''), s.vat);
  over('M8 misto montaze je videt a rovnou je zvoleno PRVNI misto (Praha)', s.mistoViditelne && s.mista[0].aktivni && !s.mista[1].aktivni, s.mista);
  over('M9 info o montazi pod tabulkou po zvoleni zmizi (je v souctu)', !s.info, s.info);
  over('M10 volba se ulozi na server: POST order-prefs s montaz_zvolena true a montaz_misto "praha"', posty.length >= 1 && posty[posty.length - 1].montaz_zvolena === true && posty[posty.length - 1].montaz_misto === 'praha', posty[posty.length - 1]);

  await page.click('#montazMistoRow .opt-btn[data-val="slavicin"]');
  await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  over('M11 zmena mista na Slavicin: aktivni Slavicin, cena beze zmeny, na server jde montaz_misto "slavicin"', s.mista[1].aktivni && !s.mista[0].aktivni && cislo(s.banner) === 12000 && posty[posty.length - 1].montaz_misto === 'slavicin', [s.mista, s.banner, posty[posty.length - 1]]);

  await page.click('#qtyPlus');
  await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  over('M12 2 ks: zbozi 20 000 + montaz 20 % = 4 000 -> hlavni cena 24 000 Kc bez DPH', cislo(s.banner) === 24000, [s.banner, s.detail]);

  await page.click('#orderOpts .opt-btn[data-field="montaz_zvolena"][data-val="0"]');
  await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  over('M13 "Bez montaze": cena zpet 20 000 (2 ks), misto zustava videt ale bez aktivniho,  na server jde montaz_zvolena false a montaz_misto null',
       cislo(s.banner) === 20000 && s.mistoViditelne && s.mista.every(m => !m.aktivni) && posty[posty.length - 1].montaz_zvolena === false && posty[posty.length - 1].montaz_misto == null, [s.banner, s.mistoViditelne, posty[posty.length - 1]]);
  over('M14 bez chyb ve strance', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  // ---- 2) predvolba z ulozenych voleb: zakaznik uz drive zvolil montaz v Slavicine
  ({ browser, page, chyby, posty } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 20; d.total_price = 10000; d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'slavicin', shipping_method: null, payment_method: null }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M15 ulozena volba (montaz + Slavicin) se po otevreni nabidky predvyplni a promitne do ceny 12 000', s.montazAktivni && s.mistoViditelne && s.mista[1].aktivni && cislo(s.banner) === 12000, [s.montazAktivni, s.mista, s.banner]);
  await browser.close();

  // ---- 3) sazba 0 = montaz se nenabizi (nabidky z konfigurace mimo CR)
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.montaz_pct = 0; d.total_price = 10000; d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha' }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M16 sazba 0: v Volbach objednavky neni Montaz ani Misto montaze, zadne info pod tabulkou', !s.radky.includes('Montáž') && !s.radky.includes('Místo montáže') && !s.info && s.radky.includes('Dodání ve stavu'), [s.radky, s.info]);
  over('M17 sazba 0: ani drive ulozena zvolena montaz se do ceny nepricita (10 000)', cislo(s.banner) === 10000, s.banner);
  await browser.close();

  // ---- 4) sestava do auta: montaz NAHRAZUJE "Dodani ve stavu" (beze zmeny)
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 20; d.total_price = 10000; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M18 sestava do auta: Montaz + Misto montaze a ZADNE "Dodani ve stavu" (beze zmeny)', s.radky.includes('Montáž') && s.radky.includes('Místo montáže') && !s.radky.includes('Dodání ve stavu'), s.radky);
  await page.click('#montazOnBtn'); await page.waitForTimeout(500);
  s = await page.evaluate(stav);
  over('M19 sestava do auta: zvolena montaz -> 12 000', cislo(s.banner) === 12000, s.banner);
  await browser.close();

  // ---- 4b) STARSI backend (payload bez montaz_volba): u nabidky, ktera neni sestava do auta, zustava puvodni chovani (jen informace, zadna volba) - statika je zive driv nez API
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { delete d.montaz_volba; d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: false }); d.montaz_pct = 20; d.total_price = 10000;
                                                                              d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha' }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M22 starsi backend (bez montaz_volba): zadna volba montaze, info "neni v cene", drive ulozena volba se do ceny NEpricita (10 000)',
       !s.radky.includes('Montáž') && /Montáž 20 % z ceny \(volitelná služba, není v ceně\)/.test(s.info || '') && cislo(s.banner) === 10000, [s.radky, s.info, s.banner]);
  await browser.close();

  // ---- 4c) NOVY backend posila montaz_volba: true i u stolu / bezne nabidky - stranka ho uz nepouziva (Robert 2026-10-06: Praha / Slavicin jen u sestav do aut)
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: false }); d.montaz_pct = 20; d.total_price = 10000;
                                                                              d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha' }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M23 bezna nabidka / stul (montaz_volba true z backendu): zadna volba Praha / Slavicin, jen info "neni v ceně", ulozena volba se do ceny NEpricita (10 000), "Dodani ve stavu" zustava',
       !s.radky.includes('Montáž') && !s.radky.includes('Místo montáže') && s.radky.includes('Dodání ve stavu') && /Montáž 20 % z ceny \(volitelná služba, není v ceně\)/.test(s.info || '') && cislo(s.banner) === 10000, [s.radky, s.info, s.banner]);
  await browser.close();

  // ---- 5) nabidka z konfigurace stolu (source configurator) v CR: montaz je JEN informace (sazba z generatoru), zadna volba mista
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.source = 'configurator'; d.configuration = { kod: 'STL-ABCDEF', qty: 1, delivery_country: 'CZ', souhrn: [], bom: [] }; d.montaz_pct = 15; d.total_price = 20000; }) }));
  await page.waitForTimeout(800);
  for (let i = 0; i < 12; i++) { if (await page.evaluate(() => !!document.querySelector('.slide.active table.items'))) break; await page.click('#btnNext').catch(() => {}); await page.waitForTimeout(450); }
  s = await page.evaluate(stav);
  over('M20 nabidka z konfigurace stolu (CR, sazba 15 %): zadna volba Montaz / Misto montaze, montaz jako informace pod tabulkou (3 000 Kč bez DPH), cena 20 000', !s.radky.includes('Montáž') && !s.radky.includes('Místo montáže') && /Montáž 15 % z ceny \(volitelná služba, není v ceně\)/.test(s.info || '') && cislo(s.banner) === 20000, [s.radky, s.info, s.banner]);
  over('M21 stul: radek Doprava zustava (nic ho nevylucuje)', s.radky.includes('Doprava'), s.radky);
  await browser.close();

  // ---- 6) sestava do auta: zvolena montaz VYLUCUJE dopravu (radek Doprava se skryje, Toptrans se nepricita, na server jde shipping_method null)
  ({ browser, page, chyby, posty } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 20; d.total_price = 10000;
                                                                              d.order_prefs = { qty: 1, montaz_zvolena: 0, shipping_method: 'toptrans', delivery_zip: '11000', toptrans_price_czk: 1000 }; }) }));
  await naCenovouStranku(page);
  const dop = () => page.evaluate(() => { const r = document.getElementById('shippingRow'); return { existuje: !!r, viditelny: !!r && getComputedStyle(r).display !== 'none' }; });
  s = await page.evaluate(stav);
  over('M24 sestava do auta, bez montaze, Toptrans 1 000 zvolen: radek Doprava je videt a cena zahrnuje dopravu (11 000)', (await dop()).viditelny && cislo(s.banner) === 11000, [await dop(), s.banner]);
  await page.click('#montazOnBtn'); await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  const pr = posty[posty.length - 1];
  over('M25 po zvoleni montaze: radek Doprava zmizi a cena = zbozi + montaz 12 000 (Toptrans se NEpricita)', !(await dop()).viditelny && cislo(s.banner) === 12000, [await dop(), s.banner]);
  over('M26 na server jde montaz_zvolena true a doprava vynulovana (shipping_method null, bez PSC a ceny dopravy)', pr && pr.montaz_zvolena === true && pr.shipping_method == null && pr.delivery_zip == null && pr.toptrans_price_czk == null, pr);
  await page.click('#orderOpts .opt-btn[data-field="montaz_zvolena"][data-val="0"]'); await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  over('M27 "Bez montaze": radek Doprava je zase videt, doprava nevybrana (cena 10 000 do dalsi volby)', (await dop()).viditelny && cislo(s.banner) === 10000, [await dop(), s.banner]);
  await browser.close();

  // ---- 6b) sestava do auta, uz drive ulozena montaz: radek Doprava je skryty hned po otevreni
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 20; d.total_price = 10000;
                                                                              d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha', shipping_method: null }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M28 ulozena montaz (sestava do auta): radek Doprava skryty hned po otevreni, cena 12 000, bez chyb', !(await dop()).viditelny && cislo(s.banner) === 12000 && chyby.length === 0, [await dop(), s.banner, chyby.slice(0, 2)]);
  await browser.close();

  // ---- 6c) sestava do auta se sazbou montaze 0 (montaz se nenabizi): Doprava zustava, zadna montaz
  ({ browser, page, chyby } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true }); d.montaz_pct = 0; d.total_price = 10000;
                                                                              d.order_prefs = { qty: 1, montaz_zvolena: 1, montaz_misto: 'praha' }; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M29 sestava do auta se sazbou 0: radek Doprava zustava videt, zadna montaz v cene (10 000)', (await dop()).viditelny && cislo(s.banner) === 10000, [await dop(), s.banner]);
  await browser.close();

  // ---- 7) Robert 2026-10-07 ("Vandr je do auta a co je do auta ma montaz volitelnou v Praze / Slavicine", "zase tam chybi montaz KDE Praha/Slavicin"): misto montaze je videt VZDY, klik na misto montaz zaroven zapne
  ({ browser, page, chyby, posty } = await otevriNabidku({ nabidka: upravit(d => { d.offer_options = Object.assign({}, d.offer_options, { is_vehicle_assembly: true, vandr_single_drawing: true }); d.montaz_pct = 20; d.total_price = 10000; }) }));
  await naCenovouStranku(page);
  s = await page.evaluate(stav);
  over('M30 Vandr (sestava do auta): hned po otevreni je videt radek Montaz i radek Misto montaze s Praha a Slavicin', s.radky.includes('Montáž') && s.radky.includes('Místo montáže') && s.mistoViditelne && s.mista.map(m => m.nazev).join() === 'Praha,Slavičín', [s.radky, s.mistoViditelne, s.mista]);
  await page.click('#montazMistoRow .opt-btn[data-val="slavicin"]'); await page.waitForTimeout(800);
  s = await page.evaluate(stav);
  const dop7 = () => page.evaluate(() => { const r = document.getElementById('shippingRow'); return !!r && getComputedStyle(r).display !== 'none'; });
  over('M31 klik na Slavicin BEZ drivejsiho "Montaz": montaz se zapne (tlacitko aktivni), aktivni je Slavicin, cena 12 000, radek Doprava zmizi', s.montazAktivni && s.mista[1].aktivni && !s.mista[0].aktivni && cislo(s.banner) === 12000 && !(await dop7()), [s.montazAktivni, s.mista, s.banner]);
  over('M32 na server jde montaz_zvolena true + montaz_misto "slavicin" (jedno ulozeni) a doprava vynulovana', posty.length >= 1 && posty[posty.length - 1].montaz_zvolena === true && posty[posty.length - 1].montaz_misto === 'slavicin' && posty[posty.length - 1].shipping_method == null, posty[posty.length - 1]);
  await page.click('#montazMistoRow .opt-btn[data-val="praha"]'); await page.waitForTimeout(600);
  s = await page.evaluate(stav);
  over('M33 zmena mista na Prahu: montaz zustava zapnuta, aktivni Praha, cena 12 000', s.montazAktivni && s.mista[0].aktivni && !s.mista[1].aktivni && cislo(s.banner) === 12000, [s.montazAktivni, s.mista, s.banner]);
  await page.click('#montazOnBtn'); await page.waitForTimeout(600);
  s = await page.evaluate(stav);
  over('M34 klik na "Montaz" pri uz zvolenem miste misto NEPREPISE (zustava Praha)', s.montazAktivni && s.mista[0].aktivni && !s.mista[1].aktivni, s.mista);
  await page.click('#orderOpts .opt-btn[data-field="montaz_zvolena"][data-val="0"]'); await page.waitForTimeout(600);
  s = await page.evaluate(stav);
  over('M35 "Bez montaze": montaz vypnuta, misto montaze zustava videt ale zadne neni aktivni, Doprava zase videt, cena 10 000', !s.montazAktivni && s.mistoViditelne && s.mista.every(m => !m.aktivni) && await dop7() && cislo(s.banner) === 10000, [s.montazAktivni, s.mista, s.banner]);
  over('M36 bez chyb ve strance', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();

  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK montaz u kazde online nabidky: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
