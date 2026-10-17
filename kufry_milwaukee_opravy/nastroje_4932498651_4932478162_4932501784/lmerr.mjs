// node lmerr.mjs cam.json lm.json → chyby landmarků v px
import fs from 'node:fs'; import { camFromJson, proj } from './kamera_lib.mjs';
const c = camFromJson(JSON.parse(fs.readFileSync(process.argv[2]))), lm = JSON.parse(fs.readFileSync(process.argv[3]));
for (const [X, Y, Z, px, py] of lm.body) { const o = proj(c, [X, Y, Z]); console.log([X, Y, Z].join(','), 'foto', px, py, 'model', o.map(v => v.toFixed(0)).join(','), 'chyba', Math.hypot(o[0] - px, o[1] - py).toFixed(1)); }
