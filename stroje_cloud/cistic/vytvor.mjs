// Sestaví GLB stroje: node vytvor.mjs   → modely/cistic.glb; kontroluje obálku (±1 mm) a vypíše střed.
// node vytvor.mjs fotky → pomocná varianta modely/cistic_dle_fotek.glb BEZ roztažení v Y (SY = 1: rozměry v Y přesně podle odhadu z fotografií, obálka v Y ≈ 585 mm); obálka se u ní nekontroluje.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from '../../kufriky_cloud/jadro/glb.js';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const VARIANTA = process.argv.includes('fotky');
if (VARIANTA) process.env.CISTIC_SY = '1';
const mod = await import('./stroj_cistic.mjs');
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
const t0 = Date.now(), root = mod.build();
const out = path.join(HERE, 'modely', mod.SKU + (VARIANTA ? '_dle_fotek' : '') + '.glb');
const r = writeGLB(root, out, { sku: mod.SKU, nazev: mod.NAZEV, jednotky: 'mm', osy: 'X=sirka, Y=delka, Z=vyska; pocatek ve stredu obalky; celo +Y (rukojet); predni konec s velkymi koly = -Y', zdroj: 'vlastni generator stroje_cloud/cistic, tvar podle 4 fotografii; presnost viz zdroje/cistic_poznamky.md' });
const g = readGLB(out);
const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
const hlavni = {};                         // krajní díly pro ladění obálky
for (const p of g.parts) for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) {
  const v = p.pos[i + k];
  if (v < b[k]) { b[k] = v; hlavni['min' + 'XYZ'[k]] = p.name; }
  if (v > b[k + 3]) { b[k + 3] = v; hlavni['max' + 'XYZ'[k]] = p.name; }
}
const sz = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], ob = [mod.OBALKA.x, mod.OBALKA.y, mod.OBALKA.z];
const dev = sz.map((v, i) => +(v - ob[i]).toFixed(2));
const ok = dev.every(d => Math.abs(d) <= 1.0);
console.log(`${mod.SKU}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB, obálka ${sz.map(v => v.toFixed(1)).join('×')} (cíl ${ob.join('×')}, odchylka ${dev.join('/')}) ${ok ? 'OK' : 'MIMO OBÁLKU'}; střed ${[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2].map(v => v.toFixed(1)).join(',')}; ${Date.now() - t0} ms`);
console.log('krajní díly:', JSON.stringify(hlavni), 'bbox', b.map(v => +v.toFixed(1)).join(' '));
process.exit(ok || VARIANTA ? 0 : 1);
