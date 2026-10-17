// Dofitování kamery podle siluety (IoU) – POZOR: IoU z dofitované kamery NENÍ důkaz správnosti tvaru.
// node fit_cam.mjs --glb X.glb --foto f.jpg --cam start.json --out out.json [--pose a=1] [--pos a=1] [--L 400] [--fixfov 19.5] [--iters 200] [--hide a,b] [--lm lm.json --wl 0.004]
// lm.json: {"body":[[X,Y,Z,px,py,vaha],...]} (px,py v pixelech fotky 1200×1200)
import fs from 'node:fs';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
import { maska, nastavPozu, parseKV } from './rend.mjs';
import { proj } from './kamera_lib.mjs';
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), L = +opt('L', 400), iters = +opt('iters', 160);
const st = JSON.parse(fs.readFileSync(opt('cam'))); const c0 = st.kamera || st;
const rot = parseKV(opt('pose', '')), pos = parseKV(opt('pos', '')), hide = (opt('hide', '') || '').split(',').filter(Boolean);
const lm = opt('lm', null) ? JSON.parse(fs.readFileSync(opt('lm'))) : null, WL = +opt('wl', 0.004);
const ycut = +opt('ycutfit', 0), fixel = opt('fixel', null), fixfov = opt('fixfov', null), freepos = opt('freepos', null);
const { w, h, mask } = await maska(foto, L, process.argv.includes('--nofill'));
const R = await new Renderer().open(w, h); await R.load(glb, true); if (hide.length) await R.hide(hide); await nastavPozu(R, rot, pos);
const sx0 = c0.shiftX !== undefined ? c0.shiftX : (c0.cx - 600) / 1200, sy0 = c0.shiftY !== undefined ? c0.shiftY : (c0.cy - 600) / 1200;
let p = [c0.azim, fixel ? +fixel : c0.elev, c0.dist, fixfov ? +fixfov : c0.fov, sx0, sy0]; if (freepos) p.push(pos[freepos] ?? 0);
const cost = async q => {
  let [az, el, dist, fov, sx, sy, pp] = q; if (fixel) el = +fixel; if (freepos) { pos[freepos] = pp; await nastavPozu(R, rot, pos); }
  if (fov < 8 || fov > 40 || el < 0 || el > 60 || dist < 800) return 9;
  const m = await R.mask(kamera({ azim: az, elev: el, dist, fov, roll: c0.roll || 0, shiftX: sx, shiftY: sy }));
  let I = 0, U = 0; const y0r = Math.round(ycut * h / 1200) * w; for (let i = y0r; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
  let le = 0;
  if (lm) { let ws = 0; for (const [X, Y, Z, px, py, wt = 1] of lm.body) { const o = proj({ azim: az, elev: el, dist, fov, roll: c0.roll || 0, sx, sy, w: 1200, h: 1200 }, [X, Y, Z]); le += wt * Math.hypot(o[0] - px, o[1] - py); ws += wt; } le /= ws; }
  return (1 - I / U) + WL * le;
};
async function nm(x0, steps, it) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
  let vals = []; for (const q of pts) vals.push(await cost(q));
  for (let k = 0; k < it; k++) {
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
const steps = [3, fixel ? 1e-6 : 4, p[2] * 0.15, fixfov ? 1e-6 : 2, 0.02, 0.02]; if (freepos) steps.push(40);
let r = await nm(p, steps, iters); r = await nm(r.x, steps.map(s => s / 3), iters);
const q = r.x;
await R.close();
const cam = { posun_zasuvky: freepos ? q[6] : undefined, azim: q[0], elev: q[1], dist: q[2], fov: q[3], roll: c0.roll || 0, shiftX: q[4], shiftY: q[5], w: 1200, h: 1200 };
fs.writeFileSync(opt('out'), JSON.stringify({ kamera: cam, poznamka: 'kamera DOFITOVANÁ podle siluety nového modelu (IoU) – není důkaz' }, null, 1));
console.log(JSON.stringify({ cena: r.f, ...cam }));
