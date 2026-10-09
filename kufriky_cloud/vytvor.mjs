// Sestaví GLB organizérů: node vytvor.mjs [SKU ...]   (bez argumentu všechny, pro které existuje organizer_<SKU>.mjs)
// Každý modul organizer_<SKU>.mjs exportuje: SKU, OBALKA {x,y,z} (mm, z kufriky.csv) a build() → Group (počátek = střed obálky).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from './jadro/glb.js';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const want = process.argv.slice(2);
const files = fs.readdirSync(HERE).filter(f => /^organizer_\d+\.mjs$/.test(f)).filter(f => !want.length || want.some(w => f.includes(w)));
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
let bad = 0;
for (const f of files) {
  const mod = await import('./' + f);
  const t0 = Date.now(); const root = mod.build();
  const out = path.join(HERE, 'modely', mod.SKU + '.glb');
  const r = writeGLB(root, out, { sku: mod.SKU, jednotky: 'mm', osy: 'X=sirka, Y=delka, Z=vyska; pocatek ve stredu obalky; celo +' + (mod.CELO || 'X'), zdroj: 'vlastni generator kufriky_cloud, tvar podle fotografii vyrobce; presnost viz zdroje/' + mod.SKU + '_poznamky.md' });
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
