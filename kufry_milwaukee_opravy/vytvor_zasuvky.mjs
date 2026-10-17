// Sestaví GLB boxů se zásuvkami (4932472129, 4932472130, 4932493189, 4932493190): node vytvor_zasuvky.mjs [SKU ...]   (bez argumentu všechny čtyři)
// Každý modul kufr_<SKU>.mjs exportuje SKU, OBALKA {x,y,z} (mm), CELO, NAZEV a build() → Group (počátek = střed obálky).
// Obálka (bounding box celého GLB) se kontroluje s tolerancí ±1 mm podle katalogu (kufriky_john/kufriky.csv: 564 × 414 × 363); nenulový kód při překročení.
// Kromě obálky se kontroluje, že se zásuvky při plném výsuvu neoddělí od těla (překryv členů kolejnic ≥ 50 mm).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from '../kufriky_cloud/jadro/glb.js';
import { overZasuvky } from './p4932472129_sestav.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const MOJE = ['4932472129', '4932472130', '4932493189', '4932493190'];
const want = process.argv.slice(2);
const files = MOJE.filter(s => !want.length || want.some(w => s.includes(w))).map(s => `kufr_${s}.mjs`);
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
let bad = 0;
for (const f of files) {
  const mod = await import('./' + f);
  const t0 = Date.now(); const root = mod.build();
  const out = path.join(HERE, 'modely', mod.SKU + '.glb');
  const r = writeGLB(root, out, { sku: mod.SKU, nazev: mod.NAZEV, jednotky: 'mm', osy: 'X=hloubka, Y=sirka, Z=vyska; pocatek ve stredu obalky; celo (zasuvky) +' + (mod.CELO || 'X'), zdroj: 'vlastni generator kufriky_cloud, tvar podle fotografii vyrobce (milwaukeetool.eu); presnost viz zdroje/' + mod.SKU + '_poznamky.md', pohyblive_uzly: 'zasuvka-N (posuv po +X, extras.osa/rozsah_mm), kolejnice-N-L|P (vazba+podil), trmen (rotace kolem Y, extras.osa)' });
  const g = readGLB(out);
  const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
  for (const p of g.parts) for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); }
  const sz = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], ob = [mod.OBALKA.x, mod.OBALKA.y, mod.OBALKA.z];
  const dev = sz.map((v, i) => +(v - ob[i]).toFixed(2));
  const ok = dev.every(d => Math.abs(d) <= 1.0);
  const ov = overZasuvky(), okOv = ov.every(o => o.preryv_mm >= 50);
  if (!ok || !okOv) bad++;
  console.log(`${mod.SKU}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB, obálka ${sz.map(v => v.toFixed(1)).join('×')} (cíl ${ob.join('×')}, odchylka ${dev.join('/')}) ${ok ? 'OK' : 'MIMO OBÁLKU'}; střed ${[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2].map(v => v.toFixed(1)).join(',')}; výsuv: ${ov.map(o => o.dvojice + ' ' + o.preryv_mm.toFixed(0) + ' mm').join(', ')} ${okOv ? 'OK' : 'ZÁSUVKA SE ODDĚLUJE'} ${(Date.now() - t0)} ms`);
}
process.exit(bad ? 1 : 0);
