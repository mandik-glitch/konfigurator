// Srovnání modelu s fotografií: IoU obrysu + (volitelně) dofitování kamery + render + dvojice foto | model | překryv.
// node srov.mjs --cfg cfg.json --pohled c01 [--fit] [--len 1200] [--pose vicko=-95,...] [--glb cesta] [--out prefix]
// cfg.json: { "<pohled>": { "foto": "...jpg", "start": {azim,elev,dist,fov,cx,cy,roll,w,h}, "pose": {...}, "vyloucit": [[[x,y],...],...] (polygony v px fotografie 1200),
//             "lm": [[X,Y,Z,px,py,vaha],...], "hide": ["prefix",...], "nazev": "..." } }
// IoU se počítá v rozlišení masky (ML px delší strana) po vyplnění děr v masce modelu (stejný postup jako maska fotografie: dutiny uvnitř obrysu se plní) a mimo vyloučené polygony.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const flag = k => process.argv.includes('--' + k);
const cfg = JSON.parse(fs.readFileSync(opt('cfg'), 'utf8'))[opt('pohled')]; const pohled = opt('pohled');
const glb = opt('glb'); if (!glb) throw new Error('--glb');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const ML = +opt('maska', 320), tag = opt('tag', pohled);
const maskFile = path.join(scratch, `mask_${tag}_${ML}${process.argv.includes('--raw') ? 'r' : ''}.bin`);
const RAW = flag('raw');
execFileSync('python3', [RAW ? path.join(HERE, 'foto_maska_raw.py') : path.join(KC, 'nastroje/foto_maska.py'), cfg.foto, maskFile, String(ML)], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const pose = Object.assign({}, cfg.pose || {}); for (const s of (opt('pose', '') || '').split(',').filter(Boolean)) { const [k, v] = s.split('='); pose[k] = +v; }
const W0 = 1200, H0 = 1200;
// vyloučená oblast
const excl = new Uint8Array(w * h);
function inPoly(x, y, P) { let c = false; for (let i = 0, j = P.length - 1; i < P.length; j = i++) { if (((P[i][1] > y) !== (P[j][1] > y)) && (x < (P[j][0] - P[i][0]) * (y - P[i][1]) / (P[j][1] - P[i][1]) + P[i][0])) c = !c; } return c; }
for (const P of cfg.vyloucit || []) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (inPoly((x + .5) * W0 / w, (y + .5) * H0 / h, P)) excl[y * w + x] = 1;
function vyplnDiry(m) { // zaplavení pozadí od okraje; vše ostatní = objekt
  const out = new Uint8Array(w * h), st = []; const seen = new Uint8Array(w * h);
  const push = (x, y) => { if (x < 0 || y < 0 || x >= w || y >= h) return; const i = y * w + x; if (seen[i] || m[i]) return; seen[i] = 1; st.push(i); };
  for (let x = 0; x < w; x++) { push(x, 0); push(x, h - 1); } for (let y = 0; y < h; y++) { push(0, y); push(w - 1, y); }
  while (st.length) { const i = st.pop(), x = i % w, y = (i / w) | 0; push(x + 1, y); push(x - 1, y); push(x, y + 1); push(x, y - 1); }
  for (let i = 0; i < w * h; i++) out[i] = seen[i] ? 0 : 1; return out;
}
if (opt('oblast')) { const boxes = opt('oblast').split(';').map(s => s.split(',').map(Number)); for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const X = (x + .5) * W0 / w, Y = (y + .5) * H0 / h; if (!boxes.some(([a, b, c, d]) => X >= a && X <= c && Y >= b && Y <= d)) excl[y * w + x] = 1; } }
const R = await new Renderer().open(w, h); await R.load(glb, true); if (cfg.hide) await R.hide(cfg.hide); if (Object.keys(pose).length) await R.pose(pose);
const kmr = c => kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll || 0, shiftX: (c.cx - W0 / 2) / W0, shiftY: (c.cy - H0 / 2) / H0 });
async function iouOf(c, fill = true) {
  const m0 = await R.mask(kmr(c)); const m = (fill && !RAW) ? vyplnDiry(m0) : m0;
  let I = 0, U = 0; for (let i = 0; i < w * h; i++) { if (excl[i]) continue; const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return I / U;
}
// projekce pro landmarky (pixely 1200)
function proj(c, X) {
  const a = c.azim * Math.PI / 180, e = c.elev * Math.PI / 180, d = c.dist;
  const pos = [d * Math.cos(e) * Math.cos(a), d * Math.cos(e) * Math.sin(a), d * Math.sin(e)]; const f = pos.map(v => -v / d);
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const dd = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
  const xc = dot(dd, r), yc = dot(dd, u), zc = dot(dd, f), t = Math.tan(c.fov * Math.PI / 360);
  return [c.cx + (W0 / 2) * (xc / zc) / (t * W0 / H0) , c.cy - (H0 / 2) * (yc / zc) / t];
}
let cam = JSON.parse(JSON.stringify(cfg.start)); cam.w = W0; cam.h = H0;
if (opt('st')) { const a = opt('st').split(',').map(Number); ['azim', 'elev', 'dist', 'fov', 'cx', 'cy'].forEach((k, i) => { if (!isNaN(a[i])) cam[k] = a[i]; }); }
const lmErr = c => (cfg.lm || []).map(([X, Y, Z, px, py]) => { const q = proj(c, [X, Y, Z]); return Math.hypot(q[0] - px, q[1] - py); });
if (flag('fit')) {
  const free = (opt('free', 'azim,elev,dist,fov,cx,cy')).split(',');
  const WL = +opt('wl', 0.0025), start = JSON.parse(JSON.stringify(cam));
  const toP = c => free.map(k => k in c ? c[k] : (pose[k] ?? 0)), fromP = p => { const c = Object.assign({}, cam); free.forEach((k, i) => { if (k in cam || !(k in pose)) { if (k in cam) c[k] = p[i]; } }); return c; };
  const poseKeys = free.filter(k => !(k in cam));
  const scale = { azim: 3, elev: 3, dist: cam.dist * 0.08, fov: 2, cx: 15, cy: 15, roll: 0.5 }; for (const k of poseKeys) scale[k] = 6;
  const cost = async p => { const c = fromP(p); if (c.fov < 4 || c.fov > 60 || c.elev < 0 || c.elev > 89 || c.dist < 500) return 9;
    if (poseKeys.length) { const pp = Object.assign({}, pose); free.forEach((k, i) => { if (poseKeys.includes(k)) pp[k] = p[i]; }); await R.pose(pp); }
    const le = lmErr(c); const lmc = le.length ? le.reduce((a, b) => a + b, 0) / le.length : 0; return (1 - await iouOf(c)) + WL * lmc; };
  async function nm(x0, steps, iters) {
    const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
    let vals = []; for (const q of pts) vals.push(await cost(q));
    for (let it = 0; it < iters; it++) {
      const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
      if (Math.abs(vals[n] - vals[0]) < 1e-7) break;
      const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += pts[i][j] / n;
      const along = t => c.map((v, j) => v + t * (pts[n][j] - v)); const xr = along(-1), fr = await cost(xr);
      if (fr < vals[0]) { const xe = along(-2), fe = await cost(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
      else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
      else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await cost(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, j) => pts[0][j] + 0.5 * (v - pts[0][j])); vals[i] = await cost(pts[i]); } } }
    }
    const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
  }
  let r = await nm(toP(cam), free.map(k => scale[k]), +opt('iter', 160)); r = await nm(r.x, free.map(k => scale[k] / 3), +opt('iter', 160));
  cam = fromP(r.x); free.forEach((k, i) => { if (poseKeys.includes(k)) pose[k] = +r.x[i].toFixed(2); }); if (poseKeys.length) await R.pose(pose);
}
const iou = await iouOf(cam), iouRaw = await iouOf(cam, false), le = lmErr(cam);
const out = { pohled, iou: +iou.toFixed(4), iou_bez_plneni_der: +iouRaw.toFixed(4), kamera: Object.fromEntries(Object.entries(cam).map(([k, v]) => [k, typeof v === 'number' ? +v.toFixed(3) : v])), chyby_lm_px: le.map(v => +v.toFixed(1)), pose };
if (flag('fit') && opt('save')) { fs.writeFileSync(opt('save'), JSON.stringify(out.kamera)); }
if (!flag('bez-rendru')) {
  const len = +opt('len', 1200), rend = path.join(scratch, `rend_${tag}.png`);
  await R.resize(len, len); await R.load(glb, false); if (cfg.hide) await R.hide(cfg.hide); if (Object.keys(pose).length) await R.pose(pose);
  await R.png(kmr(cam), rend); out.render = rend;
  const pair = path.join(scratch, `dvojice_${tag}.png`);
  execFileSync('python3', [path.join(HERE, 'dvojice.py'), cfg.foto, rend, pair, '640', maskFile], { stdio: 'ignore' }); out.dvojice = pair;
}
await R.close();
console.log(JSON.stringify(out));
