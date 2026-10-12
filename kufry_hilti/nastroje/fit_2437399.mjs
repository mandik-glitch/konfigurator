// Odhad kamery pro PKC 18-H (2437399) z obrysu fotografie: IoU siluety modelu, roll = 0, volné: azimut, elevace, vzdálenost, ohnisko, posun (oříznutí fotografie) a úhel víka.
// (Volný odhad z render/fit.mjs tady nestačí: s rollem a bez omezení padal do špatného minima – elevace ~55° a roll −5°; proto vlastní varianta s roll = 0 a startem z odhadu podle sklonu loga.)
// Použití: node fit_2437399.mjs --glb ../modely/2437399.glb --foto foto.jpg --pohled otevreny-c03 --start az,el,dist,fov,shiftX,shiftY,uhel [--cervena 1] [--r0 0.55 --hidelid 1 (jen spodní část, víko skryté)]
// Výstup: kufriky_cloud/srovnani/2437399/<pohled>.json (kamera + úhel víka + IoU); fotografie se jen čte (mimo repo).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const glb = opt('glb'), foto = opt('foto'), pohled = opt('pohled'), sku = '2437399';
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const maskFile = path.join(scratch, `${sku}_${pohled}_fit.bin`);
if (opt('cervena', null) !== null) execFileSync('python3', [path.join(HERE, 'maska_cervena.py'), foto, maskFile, '320'], { stdio: 'ignore' });
else execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), foto, maskFile, '320'], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const r0 = Math.round(+opt('r0', 0) * h), r1 = Math.round(+opt('r1', 1) * h);
const hideLid = opt('hidelid', '0') === '1';
const s0 = opt('start').split(',').map(Number);
const R = await new Renderer().open(w, h); await R.load(glb, true);
if (hideLid) await R.hide(['vicko']);
const iou = async p => {
  const [az, el, dist, fov, sx, sy, lid] = p;
  if (fov < 4 || fov > 60 || dist < 400 || el < 0 || el > 85 || lid < 20 || lid > 140) return 0;
  if (!hideLid) await R.pose({ vicko: lid });
  const m = await R.mask(kamera({ azim: az, elev: el, dist, fov, roll: 0, shiftX: sx, shiftY: sy }));
  let I = 0, U = 0; for (let y = r0; y < r1; y++) for (let x = 0; x < w; x++) { const i = y * w + x, a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return U ? I / U : 0;
};
async function nm(x0, steps, iters) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
  const F = async q => 1 - await iou(q); let vals = []; for (const q of pts) vals.push(await F(q));
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 1e-6) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) c[k] += pts[i][k] / n;
    const along = t => c.map((v, k) => v + t * (pts[n][k] - v)); const xr = along(-1), fr = await F(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = await F(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await F(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, k) => pts[0][k] + 0.5 * (v - pts[0][k])); vals[i] = await F(pts[i]); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], iou: 1 - vals[b] };
}
const r = await nm(s0, [8, 6, 250, 5, 0.03, 0.03, hideLid ? 0.0001 : 8], 260);
const r2 = await nm(r.x, [2, 2, 60, 1.5, 0.01, 0.01, hideLid ? 0.0001 : 2], 200);
const [az, el, dist, fov, sx, sy, lid] = r2.x;
await R.close();
const kam = { azim: az, elev: el, dist, fov, roll: 0, shiftX: sx, shiftY: sy, iou: r2.iou };
const outDir = path.join(KC, 'srovnani', sku); fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, pohled + '.json'), JSON.stringify({ sku, pohled, foto_repo_cesta: path.basename(path.dirname(foto)) + '/' + path.basename(foto) + ' (mimo repo, scratchpad)', pose: hideLid ? {} : { vicko: lid }, kamera: kam, iou: kam.iou, poznamka: 'kamera odhadnuta z obrysu fotografie (fit_2437399.mjs, roll = 0); ohnisko a úhel víka jsou odhad, ne měření' }, null, 1));
console.log(JSON.stringify({ pohled, iou: kam.iou, vicko: lid, azim: az, elev: el, dist, fov, shiftX: sx, shiftY: sy }));
