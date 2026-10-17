// Sestaví GLB opravených modelů Milwaukee PACKOUT: node vytvor_4932471723_4932471724_4932480623.mjs [SKU ...]
// Každý modul kufr_<SKU>.mjs exportuje SKU, OBALKA {x,y,z} (mm), CELO, NAZEV, build(volby) → Group a volitelně VARIANTY [{pripona, volby}] (jen srovnávací varianty, např. vztyčené držadlo).
// Obálka (bounding box GLB) se kontroluje ±1 mm; kontroluje se i orientace sítí (kladný objem). Nenulový výstup při překročení.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB, readGLB } from '../kufriky_cloud/jadro/glb.js';
import { objem } from './p4932471723_zaklad.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const SKUS = ['4932471723', '4932471724', '4932480623'];
const want = process.argv.slice(2).filter(a => !a.startsWith('--'));
const files = SKUS.filter(s => !want.length || want.some(w => s.includes(w))).map(s => `kufr_${s}.mjs`).filter(f => fs.existsSync(path.join(HERE, f)));
fs.mkdirSync(path.join(HERE, 'modely'), { recursive: true });
let bad = 0;
for (const f of files) {
  const mod = await import('./' + f);
  for (const v of [{ pripona: '', volby: {} }, ...(process.argv.includes('--bez-variant') ? [] : (mod.VARIANTY || []))]) {
    const t0 = Date.now(); const root = mod.build(v.volby);
    const out = path.join(HERE, 'modely', mod.SKU + v.pripona + '.glb');
    // orientace sítí: záporný objem = otočené normály
    let neg = [];
    const walk = g => { for (const p of g.parts) { const vol = objem(p); if (vol < -1e-6) neg.push(p.name + ' ' + vol.toFixed(0)); } g.children.forEach(walk); };
    walk(root);
    const r = writeGLB(root, out, { sku: mod.SKU, nazev: mod.NAZEV, jednotky: 'mm', osy: 'X=sirka, Y=delka, Z=vyska; pocatek ve stredu obalky; celo +' + (mod.CELO || 'Y'), varianta: v.pripona || 'zavreno', zdroj: 'vlastni generator (kufriky_cloud/jadro), oprava podle kontroly kufriky_cloud/kontrola_john_v6; presnost viz zdroje/' + mod.SKU + '_poznamky.md' });
    const g = readGLB(out);
    const b = [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity];
    for (const p of g.parts) for (let i = 0; i < p.pos.length; i += 3) for (let k = 0; k < 3; k++) { b[k] = Math.min(b[k], p.pos[i + k]); b[k + 3] = Math.max(b[k + 3], p.pos[i + k]); }
    const sz = [b[3] - b[0], b[4] - b[1], b[5] - b[2]], ob = [mod.OBALKA.x, mod.OBALKA.y, mod.OBALKA.z];
    const dev = sz.map((x, i) => +(x - ob[i]).toFixed(2));
    const ok = dev.every(d => Math.abs(d) <= 1.0) || !!v.pripona;       // varianty (vztyčené držadlo) obálku nesplňují záměrně
    if (!ok || (neg.length && !v.pripona)) bad++;
    console.log(`${mod.SKU}${v.pripona}: ${r.parts} dílů, ${r.triangles} trojúhelníků, ${(r.bytes / 1e6).toFixed(2)} MB, obálka ${sz.map(x => x.toFixed(1)).join('×')} (cíl ${ob.join('×')}, odchylka ${dev.join('/')}) ${ok ? (v.pripona ? 'varianta' : 'OK') : 'MIMO OBÁLKU'}; střed ${[(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2].map(x => x.toFixed(1)).join(',')} ${Date.now() - t0} ms${neg.length ? ' | OTOČENÉ SÍTĚ: ' + neg.join(', ') : ''}`);
  }
}
process.exit(bad ? 1 : 0);
