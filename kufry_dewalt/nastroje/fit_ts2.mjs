// Odhad kamery z obrysu studiové fotografie (maska bílého pozadí); volné: azim, elev, dist, fov, shiftX, shiftY a (s --roll 1) i náklon; jinak roll = 0.
// Nelder–Mead z několika startů (azimut/elevace), IoU masky modelu (GLB) a fotografie v rozlišení masky (delší strana L px).
// Použití: node fit_ts2.mjs --glb ../modely/DWST83294.glb --foto foto.jpg --sku DWST83294 --pohled sikmo-c02 --start -40,16 [--pose vicko=0,drzadlo=90] [--L 480] [--fov 20 (pevné)] [--roll 1] [--lm landmarky.json --wl 0.002]   (landmarky = ručně odečtené body {w,h,body:[[X,Y,Z,px,py]]}; do ceny se přičte wl × průměrná chyba v px)
// Výstup: ../../kufriky_cloud/srovnani/<sku>/<pohled>.json (kamera + pose + IoU) – stejný formát jako render/srovnej.mjs (lze použít --reuse / iou_kamera.mjs).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), sku = opt('sku'), pohled = opt('pohled'), L = opt('L', '480');
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const maskFile = path.join(scratch, `${sku}_${pohled}_fit.bin`);
execFileSync('python3', ['-I', path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, L], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const R = await new Renderer().open(w, h); await R.load(glb, true); if (Object.keys(pose).length) await R.pose(pose);
const fovFix = opt('fov', null), rollFree = opt('roll', '0') !== '0';
const LM = opt('lm', null) ? JSON.parse(fs.readFileSync(opt('lm'))) : null, WL = +opt('wl', 0.002);
let lastIoU = 0, lastErr = 0;
const lmErr = async () => {   // projekce landmarků aktuální kamerou stránky (stejná projekce jako render), chyba v px fotografie (rozlišení landmarků)
  const k = w / LM.w;
  const pr = await R.page.evaluate(pts => pts.map(([X, Y, Z]) => { const v = new THREE.Vector3(X, Y, Z).project(camera); const cv = renderer.domElement; return [(v.x * 0.5 + 0.5) * cv.width, (1 - (v.y * 0.5 + 0.5)) * cv.height]; }), LM.body.map(b => b.slice(0, 3)));
  return LM.body.reduce((a, b, i) => a + Math.hypot(pr[i][0] - b[3] * k, pr[i][1] - b[4] * k) / k, 0) / LM.body.length;
};
const iou = async p => {
  const fov = fovFix !== null ? +fovFix : p[4];
  if (fov < 5 || fov > 40 || p[2] < 600 || p[1] < 0 || p[1] > 80 || Math.abs(p[6]) > 8) return 0;
  const m = await R.mask(kamera({ azim: p[0], elev: p[1], dist: p[2], fov, roll: p[6], shiftX: p[3], shiftY: p[5] }));
  let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
  lastIoU = U ? I / U : 0; if (LM) { lastErr = await lmErr(); return lastIoU - WL * lastErr; } return lastIoU;
};
async function nm(x0, steps, iters) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
  const F = async q => 1 - await iou(q); let vals = []; for (const q of pts) vals.push(await F(q));
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
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], iou: 1 - vals[b] };
}
const st = opt('start', '40,20').split(',').map(Number), init = opt('init', null);
let best = null;
if (init) {   // rychlé doladění z uložené kamery: --init azim,elev,dist,fov,shiftX,shiftY,roll
  const q = init.split(',').map(Number), x0 = [q[0], q[1], q[2], q[4], q[3], q[5], q[6] ?? 0];
  if (fovFix === null) x0[4] = q[3];
  const X = [q[0], q[1], q[2], q[4], q[3], q[5], q[6] ?? 0];
  best = await nm(X, [2, 2, 80, 0.008, 1, 0.008, rollFree ? 0.5 : 1e-9], 90);
}
for (const fov0 of init ? [] : fovFix !== null ? [+fovFix] : [10, 16, 24]) for (const da of [-4, 4]) for (const de of [1]) {
  const x0 = [st[0] + da, st[1] + de, 1900 * (20 / fov0), 0, fov0, 0, 0];
  let r = await nm(x0, [8, 6, 300, 0.03, 4, 0.03, rollFree ? 2 : 1e-9], 100); r = await nm(r.x, [2, 2, 80, 0.008, 1, 0.008, rollFree ? 0.6 : 1e-9], 100);
  if (!best || r.iou > best.iou) best = r;
}
const x = best.x, fov = fovFix !== null ? +fovFix : x[4];
const finalIoU = (await iou(best.x), lastIoU), finalErr = lastErr;
const cam = { azim: x[0], elev: x[1], roll: rollFree ? x[6] : 0, dist: x[2], fov, shiftX: x[3], shiftY: x[5], iou: finalIoU, ...(LM ? { chyba_landmarku_px_prumer: finalErr } : {}) };
await R.close();
const outDir = path.join(KC, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, pohled + '.json'), JSON.stringify({ sku, pohled, foto_repo_cesta: path.basename(path.dirname(foto)) + '/' + path.basename(foto) + ' (mimo repo, scratchpad)', pose, kamera: cam, iou: cam.iou, poznamka: 'kamera z obrysu fotografie (IoU masky; roll ' + (rollFree ? 'volný' : '= 0') + '); nastroje/fit_ts2.mjs' }, null, 1));
console.log(JSON.stringify(cam));
