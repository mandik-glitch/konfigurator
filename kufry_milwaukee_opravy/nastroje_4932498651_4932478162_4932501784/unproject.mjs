// node unproject.mjs <kamera.json> <osa X|Y|Z> <hodnota> px,py [px,py ...]  → souřadnice modelu na rovině
import fs from 'node:fs';
import { camFromJson, unproj } from './kamera_lib.mjs';
const [kf, osa, hv, ...pts] = process.argv.slice(2);
const c = camFromJson(JSON.parse(fs.readFileSync(kf)));
for (const s of pts) { const [px, py] = s.split(',').map(Number); const p = unproj(c, px, py, osa, +hv); console.log(s, '→', p.map(v => v.toFixed(1)).join(', ')); }
