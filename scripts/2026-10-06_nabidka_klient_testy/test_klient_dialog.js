// Jmeno klienta v online nabidce se da doplnit dodatecne - dialog "Upravit nabidku" v adminu (bot5, 2026-10-06, Robert): SKUTECNY admin.html + admin/js/crm-nabidky.js v Chromiu proti falesnemu
// serveru (harness scripts/2026-09-30_karta_produktu_testy, zadna sit, zadna DB, nic se nezapisuje). Hlida: pole Klient je v dialogu, predvyplni se z edit-data, PUT nese customer_name
// (i prazdne = smazat), po ulozeni se nacte seznam znovu, bez chyb ve strance.
// Spusteni: node test_klient_dialog.js     Kandidat: ADMIN_HTML=... CRM_NABIDKY_JS=... node test_klient_dialog.js
const { otevriAdmin } = require('../2026-09-30_karta_produktu_testy/harness');
const vysl = [];
const over = (nazev, podminka, detail) => { vysl.push(!!podminka); console.log((podminka ? 'OK   ' : 'FAIL ') + nazev + (podminka ? '' : '  -> ' + JSON.stringify(detail))); };

(async () => {
  const { browser, page, chyby, log } = await otevriAdmin();
  const putBody = [];
  let editData = { offer_number: 'Logiman0129', customer_name: null, items: [{ name: 'Regál', qty: 1, unit_price: 1000, total: 1000 }], total_price: 1000,
                   editable_text: { popis: 'p', patka: 'f' }, offer_options: { show_qr: true }, revision_number: 1, last_edited_at: null, rucni_polozky: { max: 10, obrazky_max: 2 } };
  await page.route('**/api/admin/scene-offers/77/**', async route => {
    const req = route.request();
    if (req.method() === 'GET' && /edit-data$/.test(req.url())) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(editData) });
    return route.fallback();
  });
  await page.route('**/api/admin/scene-offers/77', async route => {
    const req = route.request();
    if (req.method() === 'PUT') { putBody.push(JSON.parse(req.postData() || '{}')); return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', revision_number: 2 }) }); }
    return route.fallback();
  });
  const otevri = async () => {
    await page.evaluate(() => { currentOnlineOfferId = 77; });
    await page.evaluate(() => openOfferEditModal());
    await page.waitForSelector('#offerEditModal.open', { timeout: 5000 });
  };
  await otevri();
  const pole = await page.evaluate(() => { const e = document.getElementById('offerEditCustomerName'); return e ? { value: e.value, max: e.maxLength, visible: !!(e.offsetWidth || e.offsetHeight), label: (document.querySelector('label[for="offerEditCustomerName"]') || {}).textContent } : null; });
  over('D1 dialog Upravit nabidku ma viditelne pole Klient (maxlength 255) s popiskem', pole && pole.visible && pole.max === 255 && /Klient/.test(pole.label || ''), pole);
  over('D2 u nabidky bez klienta je pole prazdne', pole && pole.value === '', pole);

  await page.fill('#offerEditCustomerName', 'Novák s.r.o.');
  await page.click('#btnOfferEditSave');
  await page.waitForTimeout(1200);
  over('D3 ulozeni posle PUT s customer_name "Novák s.r.o."', putBody.length === 1 && putBody[0].customer_name === 'Novák s.r.o.', putBody);
  over('D4 po ulozeni se dialog zavre a seznam nabidek se nacte znovu (GET /api/admin/scene-offers)', !(await page.evaluate(() => document.getElementById('offerEditModal').classList.contains('open'))) && log.filter(r => /^GET \/api\/admin\/scene-offers(\?|$)/.test(r)).length >= 1, log.filter(r => /scene-offers/.test(r)).slice(-6));

  editData = { ...editData, customer_name: 'Starý klient a.s.', revision_number: 2 };
  await otevri();
  const stare = await page.evaluate(() => document.getElementById('offerEditCustomerName').value);
  over('D5 u nabidky se jmenem se pole predvyplni z edit-data', stare === 'Starý klient a.s.', stare);
  await page.fill('#offerEditCustomerName', '');
  await page.click('#btnOfferEditSave');
  await page.waitForTimeout(1200);
  over('D6 vymazane pole = PUT s customer_name "" (smazat jmeno)', putBody.length === 2 && putBody[1].customer_name === '', putBody[1]);
  over('D7 zbytek formulare se posila beze zmeny (items, total_price, editable_text, offer_options)', putBody[1] && Array.isArray(putBody[1].items) && putBody[1].total_price === 1000 && putBody[1].editable_text && putBody[1].offer_options && putBody[1].offer_options.show_qr === true, putBody[1]);

  // starsi backend (edit-data bez customer_name): pole se skryje a PUT jmeno neposila (statika je zivy driv nez API)
  const bezKlienta = { ...editData }; delete bezKlienta.customer_name; editData = bezKlienta;
  await otevri();
  const skryto = await page.evaluate(() => ({ pole: getComputedStyle(document.getElementById('offerEditCustomerName')).display, label: getComputedStyle(document.getElementById('offerEditCustomerNameLabel')).display }));
  over('D7b starsi backend (edit-data bez customer_name): pole Klient i popisek skryte', skryto.pole === 'none' && skryto.label === 'none', skryto);
  await page.click('#btnOfferEditSave');
  await page.waitForTimeout(1200);
  over('D7c starsi backend: PUT klic customer_name vubec neposila (jmeno se nema potichu zahodit)', putBody.length === 3 && !('customer_name' in putBody[2]), putBody[2]);
  editData = { ...editData, customer_name: null };
  await otevri();
  over('D7d backend s customer_name: pole zase viditelne', await page.evaluate(() => getComputedStyle(document.getElementById('offerEditCustomerName')).display !== 'none'), null);
  over('D8 popisek sestavy do auta rika, ze zvolena montaz vylucuje dopravu', await page.evaluate(() => /vylučuje dopravu/.test(document.querySelector('label:has(#offerEditIsVehicleAssembly)')?.textContent || document.getElementById('offerEditIsVehicleAssembly').parentElement.textContent)), null);
  over('D9 bez chyb ve strance', chyby.length === 0, chyby.slice(0, 3));
  await browser.close();
  const ok = vysl.filter(Boolean).length;
  console.log(`\nVYSLEDEK jmeno klienta - dialog v adminu: ${ok}/${vysl.length} OK`);
  process.exit(ok === vysl.length ? 0 : 1);
})().catch(e => { console.error('TEST SPADL:', e); process.exit(2); });
