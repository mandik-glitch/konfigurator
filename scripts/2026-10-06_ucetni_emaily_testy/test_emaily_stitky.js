// Emaily odchozi: citelne stitky NOVYCH typu e-mailu od haku bota5 (api/ucetni_hak.py): "ucetni_doklad" (vydane doklady pro ucetni) a "prijaty_doklad:<id>" (prijate) - bot16, 2026-10-06.
// Backend EMAIL_KIND_LABELS tyhle klice nezna, takze v prehledu zustal surovy klic. SKUTECNY admin.html + admin/js proti falesnemu serveru (harness.js, zadna DB).
// Kandidat pred nasazenim:  ADMIN_HTML=<kandidat>/admin.html JS_DIR=<kandidat>/js node scripts/2026-10-06_ucetni_emaily_testy/test_emaily_stitky.js
const { otevriAdmin } = require('./harness');
let bad = 0, total = 0;
const ok = (c, t, d) => { total++; if (!c) bad++; console.log(`[${c ? 'OK   ' : 'CHYBA'}] ${t}${!c && d !== undefined ? ' | ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const ceka = ms => new Promise(r => setTimeout(r, ms));
const iso = new Date().toISOString();
const r = (id, key, label, extra) => Object.assign({ id, order_id: null, document_id: null, purchase_order_id: null, template_key: key, template_label: label, recipient_email: 'ucetni@x.cz', cc_email: null, subject: 'Predmet ' + id, body_text: 'x', status: 'pending', trigger_type: 'auto', created_at: iso, order_number: null, document_number: null }, extra || {});
const EMAILS = { emails: [
  r(1, 'ucetni_doklad', 'ucetni_doklad'), r(2, 'prijaty_doklad:12', 'prijaty_doklad:12'), r(3, 'invoice', 'Faktura'), r(4, 'custom', 'Vlastní e-mail'),
  r(5, 'neznamy_klic', 'neznamy_klic'), r(6, '<img src=x onerror=window.__xss=1>', '<img src=x onerror=window.__xss=1>'), r(7, 'order_confirmation', 'Potvrzení objednávky'),
], counts: { all: 7 }, status_counts: { pending: 7 }, total: 7, page: 1, page_size: 50 };

(async () => {
  const h = await otevriAdmin({ emails: EMAILS });
  const p = h.page;
  await p.evaluate(() => document.querySelector('.tab-btn[data-tab="emails"]').click());
  await p.waitForFunction(() => document.querySelectorAll('#emailsTbody tr, #tab-emails tbody tr').length >= 7, null, { timeout: 8000 }).catch(() => {});
  const stitky = await p.$$eval('#tab-emails tbody tr.order-row[data-email-id]', trs => trs.map(t => (t.children[4] || {}).textContent));      // u pending e-mailu je pod radkem jeste radek s nahledem
  ok(stitky.length === 7, 'A0 v přehledu je všech 7 testovacích e-mailů', stitky);
  ok(stitky[0] === 'Doklad pro účetní', 'A1 ucetni_doklad → „Doklad pro účetní“', stitky[0]);
  ok(stitky[1] === 'Přijatý doklad pro účetní', 'A2 prijaty_doklad:12 → „Přijatý doklad pro účetní“ (id v klíči stítek nerozbije)', stitky[1]);
  ok(stitky[2] === 'Faktura' && stitky[3] === 'Vlastní e-mail' && stitky[6] === 'Potvrzení objednávky', 'A3 dosavadní typy beze změny (štítek z backendu)', stitky);
  ok(stitky[4] === 'neznamy_klic', 'A4 úplně neznámý klíč se zobrazí tak, jak je (nezmizí)', stitky[4]);
  ok(stitky[5] === '<img src=x onerror=window.__xss=1>' && (await p.evaluate(() => window.__xss)) === undefined && (await p.locator('#tab-emails tbody img').count()) === 0, 'A5 klíč s HTML je jen text (žádný <img>, nic se nespustilo)', stitky[5]);
  const opt = await p.locator('#emailFilterTemplate option[value="ucetni_doklad"]').textContent().catch(() => null);
  ok(opt === 'Doklad pro účetní (vydaný)', 'B1 ve filtru šablony je volba „Doklad pro účetní (vydaný)“', opt);
  await p.selectOption('#emailFilterTemplate', 'ucetni_doklad');
  await p.click('#emailSearchApply');
  await ceka(500);
  ok(h.stav.emailsDotazy.some(q => /template_key=ucetni_doklad/.test(q)), 'B2 po výběru filtru jde na server template_key=ucetni_doklad', h.stav.emailsDotazy);
  ok(h.chyby.length === 0, 'C1 žádné chyby JS', h.chyby.slice(0, 3));
  await h.zavri();
  console.log(`\n==> ${total - bad}/${total} kontrol OK`);
  process.exit(bad ? 1 : 0);
})();
