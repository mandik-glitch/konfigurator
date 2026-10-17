// Zpětná projekce pixelu fotografie na rovinu modelu při zadané kameře.
// node unproj.mjs <kamery.json> <pohled> <varianta|-> <osa X|Y|Z> <hodnota> px,py [px,py ...]  [--zoff 265]
// X=h → vrací Y a z' ; Y=h → X a z' ; Z=h (z modelu) → X a Y.  z' = Z + zoff (výška nad podlahou, výchozí 265).
import fs from 'node:fs';
const args = process.argv.slice(2); const zoff = (i => i >= 0 ? +args.splice(i, 2)[1] : 265)(args.indexOf('--zoff'));
const [kf, pohled, varianta, osa, hod, ...pts] = args; const hv = +hod;
let c = JSON.parse(fs.readFileSync(kf, 'utf8'))[pohled]; if (varianta !== '-') c = c[varianta];
const W = c.w ?? 1200, H = c.h ?? 1200;
export function proj(X, c = c, W = 1200, H = 1200) {
  const a = c.azim * Math.PI / 180, e = c.elev * Math.PI / 180, d = c.dist;
  const pos = [d * Math.cos(e) * Math.cos(a), d * Math.cos(e) * Math.sin(a), d * Math.sin(e)];
  const f = pos.map(v => -v / d); const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const dd = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
  const xc = dot(dd, r), yc = dot(dd, u), zc = dot(dd, f), t = Math.tan(c.fov * Math.PI / 360);
  return [c.cx + (W / 2) * (xc / zc) / (t * W / H), c.cy - (H / 2) * (yc / zc) / t];
}
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
