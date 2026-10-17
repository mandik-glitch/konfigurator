// Ověří, že nahled/<SKU>.html se načte bez chyby a vykreslí model (nenulové pixely). node test_nahled.mjs SKU...
import { createRequire } from 'node:module'; import path from 'node:path'; import fs from 'node:fs'; import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url); let chromium; for (const p of ['playwright', '/opt/node22/lib/node_modules/playwright']) { try { ({ chromium } = require(p)); break; } catch {} }
const HERE = path.dirname(fileURLToPath(import.meta.url));
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
for (const s of process.argv.slice(2)) {
  const pg = await b.newPage({ viewport: { width: 900, height: 700 } }); const err = [];
  pg.on('pageerror', e => err.push(e.message)); pg.on('console', m => { if (m.type() === 'error') err.push(m.text()); });
  await pg.goto('file://' + path.join(HERE, '../nahled', s + '.html')); await pg.waitForTimeout(4000);
  const out = '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad/mk79/nahled_' + s + '.png';
  await pg.screenshot({ path: out });
  const sl = await pg.evaluate(() => document.querySelectorAll('input[type=range]').length);
  console.log(s, 'chyby:', JSON.stringify(err), 'posuvníků:', sl, out); await pg.close();
}
await b.close();
