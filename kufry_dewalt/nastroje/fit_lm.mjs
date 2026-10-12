// Kopie fit_lm.mjs (Hilti PKC 19) pro DeWalt TSTAK: dolní mez ohniska 1,2° (studiové fotografie jsou pořízeny dlouhým objektivem), navíc --pose k=v,... (pevná poloha skupin, např. drzadlo=80) a --len (rozlišení masky). Původní popis:
// Doladění kamery: překryv obrysu (IoU ve pevném rámu fotografie) + vzdálenosti ručně změřených bodů (landmarků) po promítnutí.
// Použití: node fit_lm.mjs --glb ../modely/2437394.glb --foto foto.jpg --lm landmarky.json --kam start.json --sku 2437394 --pohled c02-lm [--wl 0.004] [--pose-fix] [--cervena 1 (maska podle červené barvy – pro fotografie s kótami)]
// landmarky.json: {"w":614,"h":800,"body":[[X,Y,Z,px,py,vaha],...]}  (X,Y,Z = souřadnice modelu, Z = z'-133,5; px,py = pixel na fotografii)
// start.json: výstup kalibruj.py (azim, elev, dist, fov, cx, cy, roll[, vicko]). Výstup: srovnani/<sku>/<pohled>.json s kamerou (kamera.shiftX/Y = (cx-w/2)/w ...).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const lm = JSON.parse(fs.readFileSync(opt('lm'))), st = JSON.parse(fs.readFileSync(opt('kam')));
const WL = +opt('wl', 0.004), hide = opt('hide', '').split(',').filter(Boolean), LEN = opt('len', '480');
const fixPose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [a, b] = kv.split('='); fixPose[a] = +b; }
const maskFile = path.join(scratch, `${sku}_${pohled}_lm.bin`);
if (opt('cervena', null) !== null) execFileSync('python3', [path.join(HERE, 'maska_cervena.py'), foto, maskFile, '320'], { stdio: 'ignore' });
else execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, LEN], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const k = w / lm.w;                                   // měřítko landmarků do rozlišení masky
const R = await new Renderer().open(w, h); await R.load(glb, true); if (hide.length) await R.hide(hide);
const fitName = opt('fit-pose', null);   // volitelně se fituje úhel jedné skupiny (např. drzadlo), ostatní z --pose
const fixLid = !fitName;
// projekce (stejné konvence jako render.mjs / kalibruj.py)
function proj(p, X) {
  const [az, el, , dist, fov, sx, sy] = p; const a = az * Math.PI / 180, e = el * Math.PI / 180;
  const pos = [dist * Math.cos(e) * Math.cos(a), dist * Math.cos(e) * Math.sin(a), dist * Math.sin(e)];
  const f = pos.map(v => -v / dist); const up = [0, 0, 1];
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, up); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const d = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const xc = dot(d, r), yc = dot(d, u), zc = dot(d, f), t = Math.tan(fov * Math.PI / 360);
  return [w * (0.5 + (xc / zc) / (t * w / h) / 2) + sx * w, h * (0.5 - (yc / zc) / t / 2) + sy * h];
}
const cost = async p => {
  const [az, el, roll, dist, fov, sx, sy, lid] = p;
  if (fov < 1.2 || fov > 60 || dist < 400 || el < 0 || el > 89) return 9;
  if (fitName) { if (lid < 0 || lid > 110) return 9; await R.pose({ ...fixPose, [fitName]: lid }); }
  
  const m = await R.mask(kamera({ azim: az, elev: el, dist, fov, roll, shiftX: sx, shiftY: sy }));
  let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
  let le = 0, ws = 0; for (const [X, Y, Z, px, py, wt = 1] of lm.body) { const q = proj(p, [X, Y, Z]); le += wt * Math.hypot(q[0] - px * k, q[1] - py * k); ws += wt; }
  return (1 - I / U) + WL * (le / ws) / k * 1.0;
};
if (!fitName) await R.pose(fixPose);
let p = [st.azim, st.elev, st.roll || 0, st.dist, st.fov, (st.cx - lm.w / 2) / lm.w, (st.cy - lm.h / 2) / lm.h, fitName ? (fixPose[fitName] ?? 80) : 0];
const steps = [4, 4, 0.0001, p[3] * 0.3, 3, 0.03, 0.03, fixLid ? 0.0001 : 8];
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
let r = await nm(p, steps, 150); r = await nm(r.x, steps.map(s => s / 3), 150);
const q = r.x;
// vyhodnocení
if (fitName) await R.pose({ ...fixPose, [fitName]: q[7] });

const m = await R.mask(kamera({ azim: q[0], elev: q[1], dist: q[3], fov: q[4], roll: q[2], shiftX: q[5], shiftY: q[6] }));
let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
const errs = lm.body.map(([X, Y, Z, px, py]) => { const o = proj(q, [X, Y, Z]); return +(Math.hypot(o[0] - px * k, o[1] - py * k) / k).toFixed(1); });
await R.close();
const cam = { azim: q[0], elev: q[1], roll: q[2], dist: q[3], fov: q[4], shiftX: q[5], shiftY: q[6], iou: I / U };
const outDir = path.join(KC, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, pohled + '.json'), JSON.stringify({ sku, pohled, foto_repo_cesta: path.basename(path.dirname(foto)) + '/' + path.basename(foto) + ' (mimo repo, scratchpad)', pose: fitName ? { ...fixPose, [fitName]: q[7] } : fixPose, kamera: cam, iou: cam.iou, chyby_landmarku_px: errs, poznamka: 'kamera z ručně změřených bodů (kalibruj.py) a doladění překryvem obrysu (fit_lm.mjs)' }, null, 1));
console.log(JSON.stringify({ iou: cam.iou, pose: fitName ? { ...fixPose, [fitName]: q[7] } : fixPose, az: q[0], el: q[1], dist: q[3], fov: q[4], chyby_px: errs }));
