// Zpětná projekce pixelu fotografie na rovinu modelu při zadané kameře.
// node unproj.mjs <kamery.json> <pohled> <varianta|-> <osa X|Y|Z> <hodnota> px,py [px,py ...]  [--zoff 265]
// X=h → vrací Y a z' ; Y=h → X a z' ; Z=h (z modelu) → X a Y.  z' = Z + zoff (výška nad podlahou, výchozí 265).
import fs from 'node:fs';
const args = process.argv.slice(2); const zoff = (i => i >= 0 ? +args.splice(i, 2)[1] : 265)(args.indexOf('--zoff'));
const [kf, pohled, varianta, osa, hod, ...pts] = args; const hv = +hod;
let c = JSON.parse(fs.readFileSync(kf, 'utf8'))[pohled]; if (varianta !== '-') c = c[varianta];
const W = c.w ?? 1200, H = c.h ?? 1200;
import { project as proj } from './proj.mjs';
if (process.argv[1].endsWith('unproj.mjs')) {
  const mk = osa === 'X' ? (p, q) => [hv, p, q - zoff] : osa === 'Y' ? (p, q) => [p, hv, q - zoff] : (p, q) => [p, q, hv];
  for (const s of pts) {
    const [px, py] = s.split(',').map(Number); let p = 0, q = 200;
    for (let it = 0; it < 80; it++) {
      const f0 = proj(mk(p, q), c, W, H), dp = proj(mk(p + 1, q), c, W, H), dq = proj(mk(p, q + 1), c, W, H);
      const J = [[dp[0] - f0[0], dq[0] - f0[0]], [dp[1] - f0[1], dq[1] - f0[1]]], r = [px - f0[0], py - f0[1]];
      const det = J[0][0] * J[1][1] - J[0][1] * J[1][0]; p += (r[0] * J[1][1] - r[1] * J[0][1]) / det; q += (J[0][0] * r[1] - J[1][0] * r[0]) / det;
    }
    console.log(s, '→', osa === 'X' ? `Y=${p.toFixed(1)} z'=${q.toFixed(1)}` : osa === 'Y' ? `X=${p.toFixed(1)} z'=${q.toFixed(1)}` : `X=${p.toFixed(1)} Y=${q.toFixed(1)}`);
  }
}
