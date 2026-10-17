// Dofitování kamery podle obrysu modelu (IoU) – JEN pro orientační srovnání; IoU z dofitované kamery NENÍ důkaz tvaru.
// node dofituj_kameru.mjs --sku 4932480623 --c 01 --glb cesta.glb [--pose a=90] [--hide x] [--out soubor.json] [--iters 120]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
import { nelderMead } from '../../kufriky_cloud/render/fit.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const sku = opt('sku'), c = opt('c', '01'), glb = opt('glb', path.join(HERE, '../modely', sku + '.glb'));
const SCR = process.env.KUF_SCRATCH || '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad';
const pose = {}; for (const kv of opt('pose', '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); pose[k] = +v; }
const hide = opt('hide', '').split(',').filter(Boolean);
const cam0 = JSON.parse(fs.readFileSync(opt('kam', path.join(KC, 'kontrola_john_v6', sku, `kamera_c${c}.json`)))).kamera;
const maskFile = path.join(SCR, 'out', `${sku}_c${c}_foto.bin`);
execFileSync('python3', [path.join(KC, 'nastroje/foto_maska.py'), path.join(SCR, 'kufry3', sku, `c${c}.jpg`), maskFile, '400'], { stdio: 'ignore' });
const mb = fs.readFileSync(maskFile); const w = mb.readUInt32LE(0), h = mb.readUInt32LE(4), mask = mb.slice(8);
const R = await new Renderer().open(w, h); await R.load(glb, true); if (Object.keys(pose).length) await R.pose(pose); if (hide.length) await R.hide(hide);
const iouOf = async p => { const [az, el, dist, fov, sx, sy] = p; if (fov < 4 || fov > 40 || dist < 500 || el < 0 || el > 80) return 0; const m = await R.mask(kamera({ azim: az, elev: el, dist, fov, roll: 0, shiftX: sx, shiftY: sy })); let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return I / U; };
// asynchronní Nelder–Mead (vlastní, protože nelderMead z fit.mjs je synchronní)
async function nm(f, x0, steps, iters) {
  const n = x0.length; let pts = [x0.slice()]; for (let i = 0; i < n; i++) { const q = x0.slice(); q[i] += steps[i]; pts.push(q); }
  let vals = []; for (const q of pts) vals.push(await f(q));
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 1e-6) break;
    const cc = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) cc[j] += pts[i][j] / n;
    const along = t => cc.map((v, j) => v + t * (pts[n][j] - v));
    const xr = along(-1), fr = await f(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = await f(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = await f(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, j) => pts[0][j] + 0.5 * (v - pts[0][j])); vals[i] = await f(pts[i]); } } }
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
}
const p0 = [cam0.azim, cam0.elev, cam0.dist, cam0.fov, cam0.shiftX, cam0.shiftY];
const i0 = await iouOf(p0);
const cost = async p => 1 - await iouOf(p);
const iters = +opt('iters', 120);
let r = await nm(cost, p0, [3, 3, p0[2] * 0.15, 2, 0.02, 0.02], iters); r = await nm(cost, r.x, [1, 1, p0[2] * 0.05, 0.7, 0.007, 0.007], iters);
await R.close();
const q = r.x, out = { sku, c: 'c' + c, kamera: { azim: q[0], elev: q[1], dist: q[2], fov: q[3], roll: 0, shiftX: q[4], shiftY: q[5] }, iou_pocatek: +i0.toFixed(4), iou_dofitovano: +(1 - r.f).toFixed(4), poznamka: 'Kamera dofitovaná podle obrysu TOHOTO modelu – IoU není důkaz tvaru, jen horní mez při volné kameře.' };
console.log(JSON.stringify(out)); if (opt('out', null)) fs.writeFileSync(opt('out'), JSON.stringify(out, null, 1));
