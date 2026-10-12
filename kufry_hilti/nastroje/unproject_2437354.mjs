// Zpětná projekce pixelu fotografie na rovinu modelu (osa=Y|X|Z, hodnota) při uložené kameře (srovnani/<sku>/<pohled>.json).
// Použití: node unproject.mjs <pohled> <W> <H> <osa> <hodnota> px,py [px,py ...]   (W,H = rozměr fotografie v px)
// Pro rovinu Y=h vrací X a z' (z' = Z + 133,5), pro X=h vrací Y a z', pro Z=h vrací X a Y.
import fs from 'node:fs'; import path from 'node:path'; import { fileURLToPath } from 'node:url';
const KC = path.join(path.dirname(fileURLToPath(import.meta.url)), '../../kufriky_cloud');
const [pohled, W, H, osa, hod, ...pts] = process.argv.slice(2); const w = +W, h = +H, hv = +hod;
const j = JSON.parse(fs.readFileSync(path.join(KC, 'srovnani/2437354', pohled + '.json'))).kamera;
function proj(X) {
  const a = j.azim * Math.PI / 180, e = j.elev * Math.PI / 180, dist = j.dist;
  const pos = [dist * Math.cos(e) * Math.cos(a), dist * Math.cos(e) * Math.sin(a), dist * Math.sin(e)];
  const f = pos.map(v => -v / dist); const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const d = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const xc = dot(d, r), yc = dot(d, u), zc = dot(d, f), t = Math.tan(j.fov * Math.PI / 360);
  return [w * (0.5 + (xc / zc) / (t * w / h) / 2) + j.shiftX * w, h * (0.5 - (yc / zc) / t / 2) + j.shiftY * h];
}
const mk = (osa === 'Y') ? (p, q) => [p, hv, q - 211] : (osa === 'X') ? (p, q) => [hv, p, q - 211] : (p, q) => [p, q, hv - 211];
for (const s of pts) {
  const [px, py] = s.split(',').map(Number); let p = 0, q = 100;
  for (let it = 0; it < 60; it++) {
    const f0 = proj(mk(p, q)), dp = proj(mk(p + 1, q)), dq = proj(mk(p, q + 1));
    const J = [[dp[0] - f0[0], dq[0] - f0[0]], [dp[1] - f0[1], dq[1] - f0[1]]], r = [px - f0[0], py - f0[1]];
    const det = J[0][0] * J[1][1] - J[0][1] * J[1][0]; p += (r[0] * J[1][1] - r[1] * J[0][1]) / det; q += (J[0][0] * r[1] - J[1][0] * r[0]) / det;
  }
  console.log(s, '→', osa === 'Y' ? `X=${p.toFixed(1)} z'=${q.toFixed(1)}` : osa === 'X' ? `Y=${p.toFixed(1)} z'=${q.toFixed(1)}` : `X=${p.toFixed(1)} Y=${q.toFixed(1)}`);
}
