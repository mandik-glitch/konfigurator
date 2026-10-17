// unproj2.mjs <kamery.json> <pohled> <varianta> <osa X|Y|Z> <hodnota> px,py [px,py ...]  -> průsečík paprsku s rovinou (souřadnice modelu, Z = výška od středu)
import fs from 'node:fs';
import { camFromJson, unproj, proj } from './kamera_lib.mjs';
const [kf, pohled, varianta, osa, hod, ...pts] = process.argv.slice(2);
let c = JSON.parse(fs.readFileSync(kf, 'utf8'))[pohled]; if (varianta !== '-') c = c[varianta];
const cam = camFromJson(c);
for (const s of pts) { const [px, py] = s.split(',').map(Number); const p = unproj(cam, px, py, osa, +hod); console.log(s, '->', p.map(v => v.toFixed(1)).join(', ')); }
