// Odhad kamery z fotografie: porovnání siluety modelu (z GLB) se siluetou produktu na bílém pozadí.
// Použití: node render/fit.mjs model.glb maska.bin [vystup.json] [--fov 20] [--pose vicko=100,...] [--start az,el]
// maska.bin: 4 B šířka (uint32 LE), 4 B výška, pak w*h bajtů 0/1 (řádky shora dolů). Vyrábí foto_maska.py (mimo repo).
import fs from 'node:fs';
import { Renderer, kamera } from './render.mjs';

export function nelderMead(f, x0, steps, { iters = 220, tol = 1e-5 } = {}) {
  const n = x0.length; let pts = [x0.slice()];
  for (let i = 0; i < n; i++) { const p = x0.slice(); p[i] += steps[i]; pts.push(p); }
  let vals = pts.map(p => f(p));
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < tol) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) c[k] += pts[i][k] / n;
    const along = (t) => c.map((v, k) => v + t * (pts[n][k] - v));
    const xr = along(-1), fr = f(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = f(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = f(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, k) => pts[0][k] + 0.5 * (v - pts[0][k])); vals[i] = f(pts[i]); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
}

export async function fitKamera(R, mask, w, h, { fov = 20, fitFov = true, startAz = null, startEl = null, dist0 = 1500, target = [0, 0, 0] } = {}) {
  const cache = new Map();
  const iou = async (p) => {
    const f = fitFov ? p[6] : fov;
    if (f < 4 || f > 45 || p[3] < 300 || Math.abs(p[2]) > 15) return 0;                       // mimo rozumný rozsah
    const cam = kamera({ azim: p[0], elev: p[1], dist: p[3], fov: f, target, roll: p[2], shiftX: p[4], shiftY: p[5] });
    const m = await R.mask(cam); let I = 0, U = 0;
    for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
    return U ? I / U : 0;
  };
  // synchronní obálka kolem asynchronního hodnocení: NM přes vlastní async smyčku
  async function nmAsync(x0, steps, iters = 160) {
    const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const p = x0.slice(); p[i] += steps[i]; pts.push(p); }
    const F = async (p) => 1 - await iou(p);
    let vals = []; for (const p of pts) vals.push(await F(p));
    for (let it = 0; it < iters; it++) {
      const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
      if (Math.abs(vals[n] - vals[0]) < 1e-5) break;
      const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) c[k] += pts[i][k] / n;
      const along = t => c.map((v, k) => v + t * (pts[n][k] - v));
      const xr = along(-1), fr = await F(xr);
      if (fr < vals[0]) { const xe = along(-2), fe = await F(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
      else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
      else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await F(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, k) => pts[0][k] + 0.5 * (v - pts[0][k])); vals[i] = await F(pts[i]); } } }
    }
    const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], iou: 1 - vals[b] };
  }
  // hrubá mřížka startů (azimut × elevace), pak zjemnění nejlepších
  const starts = [];
  const azs = startAz !== null ? [startAz] : [0, 45, 90, 135, 180, 225, 270, 315], els = startEl !== null ? [startEl] : [10, 30, 50, 75, 90];
  for (const a of azs) for (const e of els) starts.push([a, e, 0, dist0, 0, 0, fov]);
  const scored = [];
  for (const s of starts) scored.push({ s, iou: await iou(s) });
  scored.sort((a, b) => b.iou - a.iou);
  let best = null;
  for (const c of scored.slice(0, 4)) {
    const r = await nmAsync(c.s, [12, 8, 2, 250, 0.03, 0.03, 6], 160);
    const r2 = await nmAsync(r.x, [3, 3, 1, 80, 0.01, 0.01, 2], 140);
    if (!best || r2.iou > best.iou) best = r2;
  }
  return { azim: best.x[0], elev: best.x[1], roll: best.x[2], dist: best.x[3], shiftX: best.x[4], shiftY: best.x[5], fov: fitFov ? best.x[6] : fov, iou: best.iou };
}

if (process.argv[1] && process.argv[1].endsWith('fit.mjs')) {
  const [glb, maskFile, outFile] = process.argv.slice(2);
  const getOpt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
  const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4); const mask = mb.slice(8);
  const R = await new Renderer().open(w, h);
  await R.load(glb, true);
  const pose = getOpt('pose', ''); if (pose) { const o = {}; for (const kv of pose.split(',')) { const [k, v] = kv.split('='); o[k] = +v; } await R.pose(o); }
  const st = getOpt('start', null);
  const res = await fitKamera(R, mask, w, h, { fov: +getOpt('fov', 20), fitFov: getOpt('fov', null) === null, startAz: st ? +st.split(',')[0] : null, startEl: st ? +st.split(',')[1] : null, dist0: +getOpt('dist', 1500) });
  console.log(JSON.stringify(res));
  if (outFile) fs.writeFileSync(outFile, JSON.stringify(res, null, 1));
  await R.close();
}
