// Doladění kamery jedné fotografie: překryv obrysu (IoU proti ručně obkreslenému polygonu masky) + vzdálenosti ručně změřených landmarků.
// Kamera = (cx,cy,cz,yaw,pitch,roll,fov) se středním hlavním bodem (fotografie jsou neořezané 4:3). Výstup: srovnani/c<foto>.json (+ render srovnani/c<foto>.png).
// node nastroje/fit_kamery.mjs --glb modely/cistic.glb --foto 13 --start zdroje/svazek_v1.json [--kolo 3] [--wl 0.004] [--res 440] [--nofit] [--tag r3]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Renderer } from '../../../kufriky_cloud/render/render.mjs';
import { kameraZ } from './kamera_z.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = path.resolve(opt('glb', path.join(ROOT, 'modely/cistic.glb'))), id = opt('foto'), WL = +opt('wl', 0.004), RES = +opt('res', 440), tag = opt('tag', '');
const startJ = JSON.parse(fs.readFileSync(path.join(ROOT, opt('start', 'zdroje/svazek_v1.json')))); const st = startJ.kamera_cx_cy_cz_yaw_pitch_roll_fov || (startJ.cams || startJ)[id];
const lm = JSON.parse(fs.readFileSync(path.join(ROOT, `zdroje/landmarky/l${id}.json`))), xyz = JSON.parse(fs.readFileSync(path.join(ROOT, 'zdroje/landmarky/xyz_model.json')));
const mj = JSON.parse(fs.readFileSync(path.join(ROOT, `zdroje/masky/m${id}.json`)));
const W = RES, H = Math.round(RES * 3 / 4), k = W / lm.w;
// maska z polygonu (even-odd, střed pixelu)
const poly = mj.polygon.map(([x, y]) => [x * k, y * k]), mask = new Uint8Array(W * H);
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let c = false; const px = x + 0.5, py = y + 0.5; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) c = !c; } mask[y * W + x] = c ? 1 : 0; }
function proj(c, X) {
  const [cx, cy, cz, yaw, pitch, roll, fov] = c, ya = yaw * Math.PI / 180, pi = pitch * Math.PI / 180, ro = roll * Math.PI / 180;
  const f = [Math.cos(pi) * Math.cos(ya), Math.cos(pi) * Math.sin(ya), Math.sin(pi)];
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const r2 = r.map((v, i) => v * Math.cos(ro) + u[i] * Math.sin(ro)), u2 = r.map((v, i) => -v * Math.sin(ro) + u[i] * Math.cos(ro));
  const d = [X[0] - cx, X[1] - cy, X[2] - cz], dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const fp = (lm.h / 2) / Math.tan(fov * Math.PI / 360);
  return [lm.w / 2 + fp * dot(d, r2) / dot(d, f), lm.h / 2 - fp * dot(d, u2) / dot(d, f)];
}
const R = await new Renderer().open(W, H); await R.load(glb, true);
const iouOf = async c => { const m = await R.mask(kameraZ(c)); let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return I / U; };
const lmErr = c => { const e = {}; let s = 0, n = 0; for (const [nm, [px, py]] of Object.entries(lm.pts)) { if (!xyz[nm]) continue; const q = proj(c, xyz[nm]); const d = Math.hypot(q[0] - px, q[1] - py) / (lm.w / 1500); e[nm] = +d.toFixed(1); s += d; n++; } return { e, mean: s / n }; };
const cost = async c => { if (c[6] < 38 || c[6] > 70 || Math.abs(c[5]) > 4) return 9; const iou = await iouOf(c); return (1 - iou) + WL * lmErr(c).mean; };
let p = st.slice();
if (!process.argv.includes('--nofit')) {
  const steps = [40, 40, 25, 1.2, 1.2, 0.4, 2];
  async function nm(x0, steps, iters) {
    const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
    let vals = []; for (const q of pts) vals.push(await cost(q));
    for (let it = 0; it < iters; it++) {
      const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
      if (Math.abs(vals[n] - vals[0]) < 1e-6) break;
      const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += pts[i][j] / n;
      const along = t => c.map((v, j) => v + t * (pts[n][j] - v));
      const xr = along(-1), fr = await cost(xr);
      if (fr < vals[0]) { const xe = along(-2), fe = await cost(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
      else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
      else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await cost(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, j) => pts[0][j] + 0.5 * (v - pts[0][j])); vals[i] = await cost(pts[i]); } } }
    }
    const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
  }
  let r = await nm(p, steps, 160); r = await nm(r.x, steps.map(s => s / 3), 160); p = r.x;
}
const iou = await iouOf(p), le = lmErr(p);
if (opt('maskout', null)) { const m = await R.mask(kameraZ(p)); fs.writeFileSync(opt('maskout'), Buffer.concat([Buffer.from(new Uint32Array([W, H]).buffer), m])); }
await R.close();
const outDir = path.join(ROOT, 'srovnani'); fs.mkdirSync(outDir, { recursive: true });
const R2 = await new Renderer().open(1000, 750); await R2.load(glb, false); await R2.png(kameraZ(p), path.join(outDir, `c${id}${tag ? '_' + tag : ''}.png`)); await R2.close();
fs.writeFileSync(path.join(outDir, `c${id}${tag ? '_' + tag : ''}.json`), JSON.stringify({ foto: id, tag, kamera_cx_cy_cz_yaw_pitch_roll_fov: p.map(v => +v.toFixed(3)), iou: +iou.toFixed(4), chyby_landmarku_px_na_1500: le.e, prumer_chyby_px: +le.mean.toFixed(1), poznamka: 'kamera = ODHAD z ručně změřených bodů a doladění překryvem obrysu (IoU proti ručně obkreslenému polygonu); z\' nad zemí; fotografie ani překryv v repu nejsou' }, null, 1));
console.log(JSON.stringify({ foto: id, iou: +iou.toFixed(4), lm_mean: +le.mean.toFixed(1), kamera: p.map(v => +v.toFixed(2)) }));
