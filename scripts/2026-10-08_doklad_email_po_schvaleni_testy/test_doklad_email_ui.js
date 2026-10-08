// Admin: odkaz "Poslat e-mail" u dokladu, ktery neni schvaleny - bot16, 2026-10-08.
// Robert PRIMO: "nemuze se nabidnout odeslat e-mail o potvrzeni zaslani dokladu ktery neni schvaleny!" (doklad 26VDD00001 se schvaloval az 8. 10., e-mail s nim odesel uz 29. 9.).
// Server (bot5) hlida zarazeni i odeslani a vraci v dokladech approval_status; UI nesmi nabizet odkaz, ktery by skoncil chybou:
//   prehled Doklady, seznam dokladu v detailu objednavky, vyber prilohy "Napsat vlastni e-mail". Starsi API bez approval_status = odkaz jako drive.
// SKUTECNY admin.html + admin/js proti falesnemu serveru (harness z 2026-10-06_ucetni_emaily_testy, zadna DB / sit).
// Kandidat pred nasazenim:  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node scripts/2026-10-08_doklad_email_po_schvaleni_testy/test_doklad_email_ui.js   (puvodni kod MUSI selhat)
const { otevriAdmin } = require('../2026-10-06_ucetni_emaily_testy/harness');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const ceka = ms => new Promise(r => setTimeout(r, ms));

const dok = (id, cislo, extra) => Object.assign({ id, order_id: 187, document_type: 'payment_tax_document', document_type_label: 'Daňový doklad k přijaté platbě', document_number: cislo, order_number: 'OBJ-2026-00001',
  customer_name: 'Zákazník', issue_date: '2026-09-16T00:42:08', amount_due_czk: 0, total_with_vat_czk: 12135.09, part_number: 1 }, extra || {});
const SCHVALENY = dok(90, '26VDD00001', { approval_status: 'schvaleno', approved_at: '2026-10-08T15:48:09' });
const CEKA = dok(91, '26FAK00002', { document_type: 'invoice', document_type_label: 'Faktura', approval_status: 'ceka_schvaleni', approved_at: null });
const STARY = dok(92, '26DOD00003', { document_type: 'delivery_note', document_type_label: 'Dodací list' });      // starsi API: bez approval_status
const ZLY = dok(93, '<img src=x onerror=window.__xss=1>', { approval_status: 'ceka_schvaleni' });

(async () => {
  const h = await otevriAdmin({});
  const p = h.page;
  const ODPOVEDI = { 90: [200, { status: 'ok', id: 7 }], 92: [409, { error: 'Doklad č. 26DOD00003 ještě není schválený – e-mail s ním nejde odeslat. Nejdřív ho schval na Dashboardu.' }] };
  const posty = [];
  await p.route('**/api/admin/documents/*/email', async route => {
    const id = Number(/documents\/(\d+)\/email/.exec(route.request().url())[1]);
    posty.push(id);
    const [st, body] = ODPOVEDI[id] || [200, { status: 'ok' }];
    return route.fulfill({ status: st, contentType: 'application/json', body: JSON.stringify(body) });
  });

  // ---------- A: prehled Doklady ----------
  await p.evaluate(() => document.querySelector('.tab-btn[data-tab="documents"]').click()); await ceka(600);      // zalozka musi byt viditelna (klikani)
  await p.evaluate(docs => renderDocumentsTable(docs), [SCHVALENY, CEKA, STARY, ZLY]);
  const radek = async (selTbody, id) => p.$eval(`${selTbody} tr:nth-child(${id})`, tr => ({
    odkaz: !!tr.querySelector('a[class*="send-email"]'), stitek: (tr.querySelector('.doc-email-ceka') || {}).textContent || null, title: (tr.querySelector('.doc-email-ceka') || {}).title || null, text: tr.textContent.replace(/\s+/g, ' ') }));
  const a1 = await radek('#documentsTbody', 1), a2 = await radek('#documentsTbody', 2), a3 = await radek('#documentsTbody', 3), a4 = await radek('#documentsTbody', 4);
  ok(a1.odkaz && !a1.stitek, 'A1 přehled: schválený doklad má odkaz „Poslat e-mail“', a1);
  ok(!a2.odkaz && a2.stitek === 'e-mail až po schválení' && /není schválený/.test(a2.title || ''), 'A2 přehled: neschválený doklad odkaz NEMÁ, ukáže „e-mail až po schválení“ s vysvětlením', a2);
  ok(a3.odkaz && !a3.stitek, 'A3 přehled: starší API bez approval_status → odkaz jako dřív', a3);
  ok(!a4.odkaz && a4.stitek === 'e-mail až po schválení' && (await p.evaluate(() => window.__xss)) === undefined && (await p.locator('#documentsTbody img').count()) === 0, 'A4 číslo dokladu s HTML je jen text, nic se nespustí', a4.text.slice(0, 120));
  ok(/Stáhnout PDF/.test(a2.text) && /Foto/.test(a2.text), 'A5 přehled: u neschváleného dokladu zůstává Stáhnout PDF a Foto', a2.text.slice(0, 160));
  // klik na odkaz schvaleneho -> POST; chyba serveru (409 "doklad neni schvaleny") se ukaze uzivateli
  await p.click('#documentsTbody tr:nth-child(1) a.doc-tab-send-email'); await ceka(400);
  ok(posty.join() === '90' && h.stav.dialogy.some(d => /E-mail odeslán/.test(d.text)), 'A6 klik u schváleného dokladu odešle POST /documents/90/email a ohlásí odeslání', [posty, h.stav.dialogy]);
  await p.click('#documentsTbody tr:nth-child(3) a.doc-tab-send-email'); await ceka(400);
  ok(posty.join() === '90,92' && h.stav.dialogy.some(d => /ještě není schválený/.test(d.text)), 'A7 když server odmítne (409), uživatel uvidí jeho text místo mlčení', [posty, h.stav.dialogy.map(d => d.text.slice(0, 60))]);
  await p.locator('#documentsTbody tr:nth-child(2) .doc-email-ceka').click(); await ceka(200);
  ok(posty.length === 2, 'A8 klik na „e-mail až po schválení“ nic neodešle', posty);

  // ---------- B: detail objednavky (seznam dokladu + priloha vlastniho e-mailu) ----------
  await p.route('**/api/admin/orders/187/documents', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ documents: [SCHVALENY, CEKA, STARY], payment_summary: null, actions: {} }) }));
  await p.evaluate(() => loadOrderDocuments(187)); await ceka(500);
  const b1 = await radek('#orderModalDocuments', 1), b2 = await radek('#orderModalDocuments', 2), b3 = await radek('#orderModalDocuments', 3);
  ok(b1.odkaz && !b1.stitek, 'B1 detail objednávky: schválený doklad má odkaz', b1);
  ok(!b2.odkaz && b2.stitek === 'e-mail až po schválení', 'B2 detail objednávky: neschválený doklad odkaz nemá', b2);
  ok(b3.odkaz, 'B3 detail objednávky: starší API bez approval_status → odkaz jako dřív', b3);
  const opts = await p.$$eval('#emailAttach option', os => os.map(o => ({ v: o.value, t: o.textContent.trim(), dis: o.disabled, title: o.title })));
  ok(opts.length === 4 && opts[0].v === '' && !opts[0].dis, 'B4 příloha vlastního e-mailu: „bez přílohy“ + 3 doklady', opts);
  ok(opts[1].dis === false && opts[2].dis === true && /čeká na schválení/.test(opts[2].t) && /není schválený/.test(opts[2].title) && opts[3].dis === false, 'B5 příloha: neschválený doklad je vypnutý s popiskem „(čeká na schválení)“, ostatní volné', opts.map(o => [o.v, o.dis]));
  ok(h.chyby.length === 0, 'B6 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
