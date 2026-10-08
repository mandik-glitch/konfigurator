// Snimek seznamu E-maily s SKUTECNOU odpovedi API (ostre_sent_at.py <json>): skutecny admin.html + admin/js (ADMIN_HTML / JS_DIR jako u testu) proti falesnemu serveru, ktery vraci ulozenou
// skutecnou odpoved. Zvyrazneny radek 201. Pouziti: node snimek_ostra_data.js <odpoved.json> <vystup.png> [sirka]
const fs = require('fs');
const { otevriAdmin } = require('../2026-10-06_ucetni_emaily_testy/harness');
(async () => {
  const [, , vstup, vystup, sirka] = process.argv;
  const data = JSON.parse(fs.readFileSync(vstup, 'utf8'));
  const h = await otevriAdmin({ emails: data.emails, viewport: { width: Number(sirka) || 1900, height: 900 } });
  const p = h.page;
  await p.route('**/api/admin/system-emails**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data.system) }));
  await p.evaluate(() => document.querySelector('.tab-btn[data-tab="emails"]').click());
  await p.evaluate(() => loadSystemEmails());
  await p.waitForSelector('#emailsTbody tr.order-row[data-email-id="201"]', { timeout: 8000 });
  await new Promise(r => setTimeout(r, 400));
  await p.addStyleTag({ content: '#emailsTbody tr[data-email-id="201"] td { outline: 2px solid #f5a623; outline-offset: -2px; }' });
  const tabulka = await p.locator('#emailsTbl').boundingBox();
  const zalozky = await p.locator('#emailStatusTabs').boundingBox();
  await p.screenshot({ path: vystup, clip: { x: Math.max(0, zalozky.x - 8), y: Math.max(0, zalozky.y - 8), width: Math.min(Number(sirka) || 1900, tabulka.x + tabulka.width + 16 - Math.max(0, zalozky.x - 8)), height: tabulka.y + tabulka.height + 16 - Math.max(0, zalozky.y - 8) } });
  console.log('chyby JS:', JSON.stringify(h.chyby));
  await h.zavri();
})();
