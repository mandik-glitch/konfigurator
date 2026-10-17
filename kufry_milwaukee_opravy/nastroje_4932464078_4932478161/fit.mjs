// Dofitování kamery na obrys fotografie (IoU) při dané póze modelu; volitelně s landmarky (px) a váhou.
// node fit.mjs --glb model.glb --foto foto.jpg --kam kamery.json --pohled c01 --start z_bodu --nazev z_obrysu_novy [--pose a=1,b=2] [--ymin N] [--xmin N] [--fix fov,roll] [--lm landmarky.json --wl 0.004] [--iter 150]
// Výsledek (kamera + IoU) se zapíše do kamery.json pod <pohled>.<nazev>. IoU z dofitované kamery NENÍ důkaz správnosti tvaru (horní mez).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), pohled = opt('pohled'), kamFile = opt('kam'), start = opt('start'), nazev = opt('nazev');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const kams = JSON.parse(fs.readFileSync(kamFile, 'utf8')); const st = kams[pohled][start];
const pose = {}; for (const s of (opt('pose', '') || '').split(',').filter(Boolean)) { const [k, v] = s.split('='); pose[k] = +v; }
const fix = (opt('fix', '') || '').split(',').filter(Boolean);
const maskFile = path.join(scratch, `fit_${pohled}.bin`);
execFileSync('python3', [path.join(HERE, 'maska.py'), foto, maskFile, '320', '236', ...(process.argv.includes('--vyplnit') ? ['--vyplnit'] : [])], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const W0 = st.w ?? 1200, H0 = st.h ?? 1200;
const ymin = +opt('ymin', 0) * h / H0, xmin = +opt('xmin', 0) * w / W0, ymax = +opt('ymax', 1e9) * h / H0, xmax = +opt('xmax', 1e9) * w / W0;
const lm = opt('lm', null) ? JSON.parse(fs.readFileSync(opt('lm'))) : null; const WL = +opt('wl', 0.004);
function proj(p, X) {
  const [az, el, , dist, fov, sx, sy] = p; const a = az * Math.PI / 180, e = el * Math.PI / 180;
  const pos = [dist * Math.cos(e) * Math.cos(a), dist * Math.cos(e) * Math.sin(a), dist * Math.sin(e)];
  const f = pos.map(v => -v / dist); const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const d = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const xc = dot(d, r), yc = dot(d, u), zc = dot(d, f), t = Math.tan(fov * Math.PI / 360);
  return [W0 * (0.5 + (xc / zc) / (t * W0 / H0) / 2) + sx * W0, H0 * (0.5 - (yc / zc) / t / 2) + sy * H0];
}
const R = await new Renderer().open(w, h); await R.load(glb, true); if (Object.keys(pose).length) await R.pose(pose);
const names = ['azim', 'elev', 'roll', 'dist', 'fov', 'sx', 'sy'];
const cost = async p => {
  const [az, el, roll, dist, fov, sx, sy] = p;
  if (fov < 3 || fov > 60 || dist < 300 || el < -5 || el > 89 || Math.abs(roll) > (opt('maxroll', null) ? +opt('maxroll') : 8)) return 9;
  const m = await R.mask(kamera({ azim: az, elev: el, dist, fov, roll, shiftX: sx, shiftY: sy }));
  let I = 0, U = 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { if (y < ymin || x < xmin || y > ymax || x > xmax) continue; const i = y * w + x; const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
  let c = 1 - I / U;
  if (lm) { let le = 0, ws = 0; for (const [X, Y, Z, px, py, wt = 1] of lm.body) { const q = proj(p, [X, Y, Z]); le += wt * Math.hypot(q[0] - px, q[1] - py); ws += wt; } c += WL * le / ws / (W0 / 1200); }
  return c;
};
const p0 = [st.azim, st.elev, st.roll || 0, st.dist, st.fov, (st.cx - W0 / 2) / W0, (st.cy - H0 / 2) / H0];
const steps = [4, 3, opt('maxroll', null) ? 4 : 0.5, p0[3] * 0.12, p0[4] * 0.12, 0.02, 0.02].map((s, i) => fix.includes(names[i]) ? 0 : s);
const free = steps.map((s, i) => s !== 0 ? i : -1).filter(i => i >= 0);
async function nm(x0, stp, iters) {
  const n = free.length; const mk = v => { const q = x0.slice(); free.forEach((i, k) => q[i] = v[k]); return q; };
  let pts = [free.map(i => x0[i])]; for (let k = 0; k < n; k++) { const q = pts[0].slice(); q[k] += stp[free[k]]; pts.push(q); }
  let vals = []; for (const q of pts) vals.push(await cost(mk(q)));
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 1e-6) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += pts[i][j] / n;
    const along = t => c.map((v, j) => v + t * (pts[n][j] - v));
    const xr = along(-1), fr = await cost(mk(xr));
    if (fr < vals[0]) { const xe = along(-2), fe = await cost(mk(xe)); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await cost(mk(xc)); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, j) => pts[0][j] + 0.5 * (v - pts[0][j])); vals[i] = await cost(mk(pts[i])); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: mk(pts[b]), f: vals[b] };
}
const it = +opt('iter', 150);
let startP = p0;
if (opt('multistart', null)) {                                  // hrubá mřížka azimut × elevace × roll, pak zjemnění nejlepšího
  const azs = (opt('azs', '-60,-30,0,30,60,90,120') || '').split(',').map(Number), els = (opt('els', '25,40,55,70') || '').split(',').map(Number), rolls = (opt('rolls', '0') || '').split(',').map(Number);
  let best = null;
  for (const az of azs) for (const el of els) for (const ro of rolls) { const q = p0.slice(); q[0] = az; q[1] = el; q[2] = ro; const c = await cost(q); if (!best || c < best.c) best = { c, q }; }
  startP = best.q; console.error('multistart nejlepší', startP.slice(0, 3), 'IoU', (1 - best.c).toFixed(3));
}
if (opt('random', null)) {                                      // náhodné startovní kamery v zadaných mezích, pak zjemnění 3 nejlepších
  const rg = (lo, hi) => lo + Math.random() * (hi - lo);
  const lim = (k, d) => (opt(k, d) || d).split(',').map(Number);
  const [a0, a1] = lim('razim', '0,360'), [e0, e1] = lim('rel', '20,85'), [r0, r1] = lim('rroll', '-40,40'), [d0, d1] = lim('rdist', '2000,5000'), [f0, f1] = lim('rfov', '16,26');
  const cand = [];
  for (let i = 0; i < +opt('random'); i++) { const q = p0.slice(); q[0] = rg(a0, a1); q[1] = rg(e0, e1); q[2] = rg(r0, r1); q[3] = rg(d0, d1); q[4] = rg(f0, f1); cand.push({ q, c: await cost(q) }); }
  cand.sort((a, b) => a.c - b.c);
  let bestR = null;
  for (const cd of cand.slice(0, 3)) { let rr = await nm(cd.q, steps, it); rr = await nm(rr.x, steps.map(s => s / 3), it); if (!bestR || rr.f < bestR.f) bestR = rr; console.error('kandidát', cd.q.slice(0, 3).map(v => v.toFixed(0)), (1 - cd.c).toFixed(3), '→', (1 - rr.f).toFixed(4)); }
  startP = bestR.x;
}
let r = await nm(startP, steps, it); r = await nm(r.x, steps.map(s => s / 3), it);
const q = r.x;
const m = await R.mask(kamera({ azim: q[0], elev: q[1], dist: q[3], fov: q[4], roll: q[2], shiftX: q[5], shiftY: q[6] }));
let I = 0, U = 0; for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { if (y < ymin || x < xmin || y > ymax || x > xmax) continue; const i = y * w + x; const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
await R.close();
const cam = { azim: +q[0].toFixed(3), elev: +q[1].toFixed(3), dist: +q[3].toFixed(2), fov: +q[4].toFixed(3), cx: +(W0 / 2 + q[5] * W0).toFixed(2), cy: +(H0 / 2 + q[6] * H0).toFixed(2), roll: +q[2].toFixed(3), w: W0, h: H0, iou: +(I / U).toFixed(4), pose, ymin: opt('ymin', null), xmin: opt('xmin', null) };
{ const cur = JSON.parse(fs.readFileSync(kamFile, 'utf8')); cur[pohled][nazev] = cam; fs.writeFileSync(kamFile, JSON.stringify(cur, null, 1)); }
console.log(JSON.stringify(cam));
