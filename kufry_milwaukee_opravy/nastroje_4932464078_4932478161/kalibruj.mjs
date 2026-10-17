// Kamera z ručně změřených korespondencí 3D bod modelu <-> pixel fotografie (náhodné starty + Nelder–Mead/LM bez renderu).
// node kalibruj.mjs landmarky.json [--free roll,cx,cy] [--fov 22] [--n 4000] → vypíše kameru (azim, elev, roll, dist, fov, cx, cy) a chyby v px
// landmarky.json: {"w":1200,"h":1200,"body":[[X,Y,Z,px,py,vaha,"popis"],...]} (Z = z modelu, tj. z' - ZC)
import fs from 'node:fs';
const args = process.argv.slice(2); const lm = JSON.parse(fs.readFileSync(args[0], 'utf8'));
const opt = (k, d) => { const i = args.indexOf('--' + k); return i > 0 ? args[i + 1] : d; };
const W = lm.w ?? 1200, H = lm.h ?? 1200, B = lm.body;
const fixed = (opt('fix', '') || '').split(',').filter(Boolean);
const names = ['azim', 'elev', 'roll', 'dist', 'fov', 'cx', 'cy'];
const lo = [-720, -10, -180, 800, 4, 0, 0], hi = [720, 89.9, 180, 20000, 60, W, H];
import { project } from './proj.mjs';
const E = p => { const c = { azim: p[0], elev: p[1], roll: p[2], dist: p[3], fov: p[4], cx: p[5], cy: p[6] }; let s = 0; for (const [X, Y, Z, px, py, wt = 1] of B) { const q = project([X, Y, Z], c, W, H); s += wt * ((q[0] - px) ** 2 + (q[1] - py) ** 2); } return Math.sqrt(s / B.length); };
function nm(f, x0, steps, iters = 600) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const p = x0.slice(); p[i] += steps[i] || 0.0001; pts.push(p); }
  let vals = pts.map(f);
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 1e-9) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) c[k] += pts[i][k] / n;
    const along = t => c.map((v, k) => v + t * (pts[n][k] - v));
    const xr = along(-1), fr = f(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = f(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = f(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, k) => pts[0][k] + 0.5 * (v - pts[0][k])); vals[i] = f(pts[i]); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
}
const ranges = { azim: JSON.parse(opt('razim', '[-180,180]')), elev: JSON.parse(opt('rel', '[0,89]')), roll: JSON.parse(opt('rroll', '[-180,180]')), dist: JSON.parse(opt('rdist', '[1500,9000]')), fov: JSON.parse(opt('rfov', '[8,40]')) };
const fixv = { fov: opt('fov', null) !== null ? +opt('fov') : null, roll: opt('roll', null) !== null ? +opt('roll') : null, cx: W / 2, cy: H / 2 };
const free = [0, 1, 2, 3, 4].filter(i => !(i === 4 && fixv.fov !== null) && !(i === 2 && fixv.roll !== null)).concat(fixed.includes('cx') ? [] : (opt('pp', null) ? [5, 6] : []));
let best = null; const N = +opt('n', 3000);
const rg = ([a, b]) => a + Math.random() * (b - a);
const cands = [];
for (let i = 0; i < N; i++) { const p = [rg(ranges.azim), rg(ranges.elev), fixv.roll ?? rg(ranges.roll), rg(ranges.dist), fixv.fov ?? rg(ranges.fov), W / 2, H / 2]; cands.push({ p, e: E(p) }); }
cands.sort((a, b) => a.e - b.e);
for (const c of cands.slice(0, 12)) {
  const mk = v => { const q = c.p.slice(); free.forEach((i, k) => q[i] = v[k]); if (q[1] < -10 || q[1] > 89.9 || q[4] < 4 || q[3] < 800) return null; return q; };
  const f = v => { const q = mk(v); return q ? E(q) : 1e9; };
  let r = nm(f, free.map(i => c.p[i]), free.map(i => [10, 6, 10, c.p[3] * 0.1, 3, 20, 20][i]));
  r = nm(f, r.x, free.map(i => [2, 2, 2, c.p[3] * 0.02, 0.5, 5, 5][i]));
  if (!best || r.f < best.f) best = { f: r.f, p: mk(r.x) };
}
const p = best.p; const cam = { azim: +p[0].toFixed(3), elev: +p[1].toFixed(3), roll: +p[2].toFixed(3), dist: +p[3].toFixed(1), fov: +p[4].toFixed(3), cx: +p[5].toFixed(2), cy: +p[6].toFixed(2), w: W, h: H };
const errs = B.map(([X, Y, Z, px, py, wt, nmz]) => { const q = project([X, Y, Z], cam, W, H); return `${nmz ?? ''}:${Math.hypot(q[0] - px, q[1] - py).toFixed(1)}`; });
console.log(JSON.stringify({ ...cam, rms_px: +best.f.toFixed(2), chyby_px: errs }));
