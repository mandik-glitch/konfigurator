// Sestaví GLB kufrů Hilti: node vytvor.mjs [číslo ...]   (bez argumentu všechny, pro které existuje kufr_<číslo>.mjs v tomto adresáři)
// Každý modul kufr_<číslo>.mjs exportuje: SKU, OBALKA {x,y,z} (mm), volitelně CELO, NAZEV a build() → Group (počátek = střed obálky).
// Obálka (bounding box celého GLB) se kontroluje s tolerancí ±1 mm; skript vrací nenulový kód při překročení.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from '../kufriky_cloud/jadro/glb.js';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const want = process.argv.slice(2);
const files = fs.readdirSync(HERE).filter(f => /^kufr_\d+\.mjs$/.test(f)).filter(f => !want.length || want.some(w => f.includes(w)));
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
let bad = 0;
for (const f of files) {
  const mod = await import('./' + f);
  const t0 = Date.now(); const root = mod.build();
  const out = path.join(HERE, 'modely', mod.SKU + '.glb');
  const r = writeGLB(root, out, { sku: mod.SKU, nazev: mod.NAZEV || ('Hilti ProKit ' + mod.SKU), jednotky: 'mm', osy: 'X=hloubka, Y=delka, Z=vyska; pocatek ve stredu obalky; celo +' + (mod.CELO || 'X'), zdroj: 'vlastni generator kufriky_cloud, tvar podle fotografii vyrobce (hilti.cz); presnost viz zdroje/' + mod.SKU + '_poznamky.md' });
  const g = readGLB(out);
  const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
  for (const p of g.parts) for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); }
  const sz = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], ob = [mod.OBALKA.x, mod.OBALKA.y, mod.OBALKA.z];
  const dev = sz.map((v, i) => +(v - ob[i]).toFixed(2));
  const ok = dev.every(d => Math.abs(d) <= 1.0);
  if (!ok) bad++;
  console.log(`${mod.SKU}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB, obálka ${sz.map(v => v.toFixed(1)).join('×')} (cíl ${ob.join('×')}, odchylka ${dev.join('/')}) ${ok ? 'OK' : 'MIMO OBÁLKU'}; střed ${[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2].map(v => v.toFixed(1)).join(',')} ${(Date.now() - t0)} ms`);
}
process.exit(bad ? 1 : 0);
