// Srovnání fotografie a modelu MAKPAC ze STEJNÉHO úhlu (IoU obrysu). Fotografie se jen čtou (scratchpad, mimo repo); do repa jde jen vlastní render + json.
//  1) maska produktu z fotografie (bílé pozadí; volitelně --cervena = maska podle tyrkysové/barevné, pro fotky s popisky),
//  2) odhad kamery: IoU obrysu + (volitelně) ručně změřené landmarky (--lm soubor.json: {"w":..,"h":..,"body":[[X,Y,Z,px,py,vaha],...]}, Z = Z modelu = z' − V/2),
//     volné parametry pózy (--free madlo,vicko) se doladí spolu s kamerou,
//  3) render modelu s touto kamerou do kufriky_cloud/srovnani/<kód>/<pohled>.png + .json (kamera, póza, IoU, landmarky), dvojice foto|model|překryv do scratchpadu.
// Použití: node srovnej.mjs --kod 8215500 --foto <foto.jpg> --pohled c01 [--pose madlo=85,vicko=0] [--free madlo] [--lm lm.json] [--start az,el] [--fov 18 | volné ohnisko] [--reuse] [--len 1100]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
import { fitKamera } from '../../kufriky_cloud/render/fit.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud'), MK = path.join(HERE, '..');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const flag = k => process.argv.includes('--' + k);
const kod = opt('kod'), foto = opt('foto'), pohled = opt('pohled');
if (!kod || !foto || !pohled) { console.error('chybí --kod --foto --pohled'); process.exit(1); }
const glb = path.join(MK, 'modely', kod + '.glb');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const outDir = path.join(KC, 'srovnani', kod); fs.mkdirSync(outDir, { recursive: true });
const jsonFile = path.join(outDir, pohled + '.json');
const parsePose = s => { const o = {}; for (const kv of (s || '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); o[k] = +v; } return o; };
const maskPy = flag('cervena') ? path.join(HERE, 'maska_barva.py') : path.join(KC, 'nastroje/foto_maska.py');
const MASKLEN = +opt('masklen', 320);
const makeMask = (len, f, mode = '') => { const mf = path.join(scratch, `${kod}_${pohled}_${len}${mode}.bin`); execFileSync('python3', mode ? [path.join(HERE, 'maska_barva.py'), foto, mf, String(len), 'tyrkys'] : [maskPy, foto, mf, String(len)], { stdio: ['ignore', 'ignore', 'inherit'] }); const mb = fs.readFileSync(mf); return { w: mb.readUInt32LE(0), h: mb.readUInt32LE(4), m: mb.slice(8) }; };
const M = makeMask(MASKLEN);
const lm = opt('lm', null) ? JSON.parse(fs.readFileSync(opt('lm'))) : null;
const WL = +opt('wl', 0.004);
let pose0 = parsePose(opt('pose', '')); const free = opt('free', '').split(',').filter(Boolean);
const fixFov = opt('fov', null) !== null; const fov0 = +opt('fov', opt('fov0', 18));
const iouOf = (m, mask) => { let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return U ? I / U : 0; };
// projekce landmarku (stejné konvence jako render.mjs)
function proj(c, X, w, h) {
  const a = c.azim * Math.PI / 180, e = c.elev * Math.PI / 180, dist = c.dist;
  const pos = [dist * Math.cos(e) * Math.cos(a), dist * Math.cos(e) * Math.sin(a), dist * Math.sin(e)];
  const f = pos.map(v => -v / dist); const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); let u = cr(r, f);
  if (c.roll) { const ro = c.roll * Math.PI / 180, co = Math.cos(ro), si = Math.sin(ro); const r2 = r.map((v, i) => v * co + u[i] * si), u2 = r.map((v, i) => -v * si + u[i] * co); r = r2; u = u2; }
  const d = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const xc = dot(d, r), yc = dot(d, u), zc = dot(d, f), t = Math.tan(c.fov * Math.PI / 360);
  return [w * (0.5 + (xc / zc) / (t * w / h) / 2) + c.shiftX * w, h * (0.5 - (yc / zc) / t / 2) + c.shiftY * h];
}
async function nm(F, x0, steps, iters) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const p = x0.slice(); p[i] += steps[i]; pts.push(p); }
  let vals = []; for (const p of pts) vals.push(await F(p));
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 1e-6) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) c[k] += pts[i][k] / n;
    const along = t => c.map((v, k) => v + t * (pts[n][k] - v));
    const xr = along(-1), fr = await F(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = await F(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await F(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, k) => pts[0][k] + 0.5 * (v - pts[0][k])); vals[i] = await F(pts[i]); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
}
let cam, pose = { ...pose0 };
const telo = flag('telo');           // kamera se nejdřív odhadne jen z tyrkysového těla (bez madla), pak se dolaďuje póza madla/víka
if (flag('reuse') && fs.existsSync(jsonFile)) { const j = JSON.parse(fs.readFileSync(jsonFile, 'utf8')); cam = j.kamera; pose = { ...pose0, ...j.pose }; }
else {
  const R = await new Renderer().open(M.w, M.h); await R.load(glb, true);
  await R.pose(pose);
  const cm = telo ? makeMask(MASKLEN, '', 'tyrkys').m : M.m;
  if (telo) await R.hide(['madlo']);
  const st = opt('start', null);
  let start;
  if (opt('kam', null)) { const k = JSON.parse(fs.readFileSync(opt('kam'))); start = k.kamera || k; }
  else start = await fitKamera(R, cm, M.w, M.h, { fov: fov0, fitFov: !fixFov, startAz: st ? +st.split(',')[0] : null, startEl: st ? +st.split(',')[1] : null, dist0: +opt('dist', 1500) });
  console.error('start IoU', start.iou?.toFixed(4));
  const k = lm ? M.w / lm.w : 1;
  const F = async p => {
    const [az, el, roll, dist, fv, sx, sy, ...fp] = p;
    const f = fixFov ? fov0 : fv;
    if (f < 4 || f > 45 || dist < 300 || Math.abs(roll) > 15 || el < -80 || el > 89.5) return 9;
    const pz = { ...pose }; if (!telo) free.forEach((n, i) => { pz[n] = fp[i]; });
    if (Object.keys(pz).length) await R.pose(pz);
    const c = { azim: az, elev: el, dist, fov: f, roll, shiftX: sx, shiftY: sy };
    const m = await R.mask(kamera(c));
    let cost = 1 - iouOf(m, cm);
    if (lm) { let le = 0, ws = 0; for (const [X, Y, Z, px, py, wt = 1] of lm.body) { const q = proj(c, [X, Y, Z], M.w, M.h); le += wt * Math.hypot(q[0] - px * k, q[1] - py * k); ws += wt; } cost += WL * (le / ws) / k; }
    return cost;
  };
  const nfree = telo ? 0 : free.length;
  let p = [start.azim, start.elev, start.roll || 0, start.dist, start.fov ?? fov0, start.shiftX || 0, start.shiftY || 0, ...free.slice(0, nfree).map(n => pose[n] ?? 0)];
  const steps = [4, 4, 1, p[3] * 0.15, 3, 0.02, 0.02, ...free.slice(0, nfree).map(() => 8)];
  let r = await nm(F, p, steps, 160); r = await nm(F, r.x, steps.map(s => s / 3), 160);
  const q = r.x; if (!telo) free.forEach((n, i) => { pose[n] = q[7 + i]; });
  const c0 = { azim: q[0], elev: q[1], dist: q[3], fov: fixFov ? fov0 : q[4], roll: q[2], shiftX: q[5], shiftY: q[6] };
  if (telo) {
    await R.hide([]);
    // pózy (madlo, víko) při pevné kameře proti plné masce
    const G = async pp => { const pz = { ...pose }; free.forEach((n, i) => { pz[n] = pp[i]; }); await R.pose(pz); return 1 - iouOf(await R.mask(kamera(c0)), M.m); };
    if (free.length) { const r2 = await nm(G, free.map(n => pose[n] ?? 0), free.map(() => 8), 80); free.forEach((n, i) => { pose[n] = r2.x[i]; }); }
  }
  if (Object.keys(pose).length) await R.pose(pose);
  const m = await R.mask(kamera(c0));
  cam = { ...c0, iou: iouOf(m, M.m) };
  await R.close();
}
// vyhodnocení a render v rozlišení fotografie (delší strana = len); IoU se při vykazování počítá na jemnější masce (--iou-len, výchozí 640)
const len = +opt('len', 1100);
const IL = +opt('iou-len', 640); const MF = makeMask(IL);
const R1 = await new Renderer().open(MF.w, MF.h); await R1.load(glb, true); if (Object.keys(pose).length) await R1.pose(pose);
const mm = await R1.mask(kamera(cam)); await R1.close();
const iouFine = iouOf(mm, MF.m);
const sc = len / Math.max(M.w, M.h), W = Math.round(M.w * sc), H = Math.round(M.h * sc);
const R2 = await new Renderer().open(W, H); await R2.load(glb, false); if (Object.keys(pose).length) await R2.pose(pose);
const png = path.join(outDir, pohled + '.png'); await R2.png(kamera(cam), png); await R2.close();
let errs = null;
if (lm) { const k = MF.w / lm.w; errs = lm.body.map(([X, Y, Z, px, py]) => { const o = proj(cam, [X, Y, Z], MF.w, MF.h); return +(Math.hypot(o[0] - px * k, o[1] - py * k) / k).toFixed(1); }); }
fs.writeFileSync(jsonFile, JSON.stringify({ kod, pohled, foto: `kufry2/${path.basename(path.dirname(foto))}/${path.basename(foto)} (scratchpad, mimo repo)`, pose, kamera: cam, iou: +iouFine.toFixed(4), iou_hrube: +cam.iou.toFixed(4), maska_px: [MF.w, MF.h], chyby_landmarku_px: errs, poznamka: 'Kamera odhadnuta z obrysu fotografie (IoU) a případně ručních landmarků; ohnisko a póza (madlo/víko) jsou odhad, ne měření.' }, null, 1));
const pair = path.join(scratch, `${kod}_${pohled}_dvojice.png`);
execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), foto, png, pair, '700'], { stdio: 'ignore' });
console.log(JSON.stringify({ pohled, iou: +iouFine.toFixed(4), azim: +cam.azim.toFixed(1), elev: +cam.elev.toFixed(1), dist: Math.round(cam.dist), fov: +cam.fov.toFixed(1), pose, dvojice: pair }));
