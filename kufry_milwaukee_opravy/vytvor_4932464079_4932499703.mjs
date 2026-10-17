// Sestaví GLB modelů 4932464079, 4932464080 (společný generátor) a 4932499703, 4932499704 (box s vložnými panely):
//   node vytvor_4932464079_4932499703.mjs [SKU ...]    (bez argumentu všechny čtyři)
// Každý modul kufr_<SKU>.mjs exportuje SKU, OBALKA {x,y,z}, CELO, NAZEV a build() → Group; obálka (bbox GLB) se kontroluje ±1 mm, jinak nenulový kód.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from '../kufriky_cloud/jadro/glb.js';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOJE = ['4932464079', '4932464080', '4932499703', '4932499704'];
const want = process.argv.slice(2).filter(a => !a.startsWith('--'));
const sk = MOJE.filter(s => !want.length || want.includes(s));
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
let bad = 0;
for (const sku of sk) {
  let mod; try { mod = await import('./kufr_' + sku + '.mjs'); } catch (e) { if (e.code === 'ERR_MODULE_NOT_FOUND' && String(e.message).includes('kufr_' + sku)) { console.log(sku + ': modul zatím neexistuje'); continue; } throw e; }
  const varianty = mod.VARIANTY || [{ soubor: mod.SKU, opt: {} }];
  for (const v of varianty) {
    const t0 = Date.now(); const root = mod.build(v.opt || {});
    const out = path.join(HERE, 'modely', v.soubor + '.glb');
    const r = writeGLB(root, out, { sku: mod.SKU, nazev: mod.NAZEV, jednotky: 'mm', osy: 'X=hloubka, Y=delka, Z=vyska; pocatek ve stredu obalky; celo +' + (mod.CELO || 'X'), zdroj: 'vlastni generator kufriky_cloud (oprava v6), tvar podle fotografii vyrobce; presnost viz kufry_milwaukee_opravy/zdroje/' + mod.SKU + '_poznamky.md', varianta: v.soubor });
    const g = readGLB(out);
    const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    const bboxOf = (parts) => { for (const p of parts) for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); } };
    bboxOf(g.parts);
    const sz = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], ob = [mod.OBALKA.x, mod.OBALKA.y, mod.OBALKA.z];
    const dev = sz.map((x, i) => +(x - ob[i]).toFixed(2));
    const ok = v.mimoObalku ? true : dev.every(d => Math.abs(d) <= 1.0);
    if (!ok) bad++;
    console.log(`${v.soubor}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB, obálka ${sz.map(x => x.toFixed(1)).join('×')} (cíl ${ob.join('×')}, odchylka ${dev.join('/')}) ${ok ? 'OK' : 'MIMO OBÁLKU'}${v.mimoObalku ? ' (varianta mimo obálku – viz poznámky)' : ''}; střed ${[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2].map(x => x.toFixed(1)).join(',')} ${(Date.now() - t0)} ms`);
  }
}
process.exit(bad ? 1 : 0);
