// Dofitování kamery překryvem obrysu (Nelder–Mead na IoU, 400 × 400 px, parametry azim, elev, dist, fov, shiftX, shiftY v omezených mezích kolem startu
// z ručních landmarků). POZOR: IoU z takto dofitované kamery NENÍ důkaz věrnosti (kamera se přizpůsobí modelu); slouží jen jako horní odhad
// a ke kontrole, zda zbylé rozdíly jsou chyba kamery, nebo tvaru. Nezávislá míra = IoU z kamery z landmarků (srovnej.mjs).
// node fit_kamera.mjs --sku 4932493189 --pohled c02 --scratch <scratchpad> [--iter 120]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), REPO = path.join(HERE, '../..');
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const sku = opt('sku'), pohledy = opt('pohled').split(','), scratch = opt('scratch'), ITER = +opt('iter', 120);
const FOTO = path.join(scratch, 'kufry3', sku);
const SKLOP = new Set(['4932472129:c02', '4932472130:c02', '4932493189:c03', '4932493189:c04', '4932493189:c05', '4932493190:c03', '4932493190:c04', '4932493190:c05', '4932493190:c06']);
const R = await new Renderer().open(400, 400);
const glb = path.join(HERE, '../modely', sku + '.glb');
async function pose2(p) {
  await R.page.evaluate(p => {
    root.traverse(o => { if (o.userData && o.userData.osa) { if (!o.userData._p0) o.userData._p0 = o.position.clone(); o.position.copy(o.userData._p0); o.quaternion.identity(); } });
    root.traverse(o => { const u = o.userData; if (!u || !u.osa) return; const ax = new THREE.Vector3(...u.osa).normalize();
      if (u.typ === 'posuv') { let v = p[o.name]; if (v === undefined && u.vazba && p[u.vazba] !== undefined) v = p[u.vazba] * (u.podil ?? 1); if (v !== undefined) o.position.addScaledVector(ax, v); }
      else if (u.typ === 'rotace') { const a = p[o.name]; if (a !== undefined) o.quaternion.setFromAxisAngle(ax, a * Math.PI / 180); } });
  }, p);
}
await R.load(glb, true);
const out = {};
for (const pohled of pohledy) {
  const mf = path.join(scratch, 'mszas', `${sku}_${pohled}_fit.bin`);
  execFileSync('python3', [path.join(HERE, 'maska_foto.py'), path.join(FOTO, pohled + '.jpg'), mf, '400']);
  const mb = fs.readFileSync(mf), w = mb.readUInt32LE(0), mask = mb.slice(8);
  const kont = JSON.parse(fs.readFileSync(path.join(REPO, 'kufriky_cloud/kontrola_john_v6', sku, pohled + '_kamera.json')));
  const st = JSON.parse(fs.readFileSync(path.join(REPO, 'kufriky_cloud/srovnani_opravy', sku, pohled + '.json'))).kamera;
  const pose = {}; for (const [k, v] of Object.entries(kont.ext || {})) pose['zasuvka-' + (+k.split('-')[1] + 1)] = v; if (SKLOP.has(sku + ':' + pohled)) pose.trmen = -90;
  await pose2(pose);
  const x0 = [st.azim, st.elev, st.dist, st.fov, st.shiftX, st.shiftY];
  const lo = [x0[0] - 6, Math.max(x0[1] - 5, 0), x0[2] * 0.85, x0[3] * 0.75, x0[4] - 0.04, x0[5] - 0.04], hi = [x0[0] + 6, x0[1] + 5, x0[2] * 1.15, x0[3] * 1.25, x0[4] + 0.04, x0[5] + 0.04];
  const iou = async p => {
    const m = await R.mask(kamera({ azim: p[0], elev: p[1], dist: p[2], fov: p[3], roll: 0, shiftX: p[4], shiftY: p[5] }));
    let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; } return I / U;
  };
  const cost = async p => { for (let i = 0; i < 6; i++) if (p[i] < lo[i] || p[i] > hi[i]) return 9; return 1 - await iou(p); };
  const steps = [2, 1.5, x0[2] * 0.04, x0[3] * 0.06, 0.012, 0.012];
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
  const i0 = await iou(x0);
  let r = await nm(x0, steps, ITER); r = await nm(r.x, steps.map(s => s / 3), ITER);
  const q = r.x;
  out[pohled] = { iou400_start: +i0.toFixed(4), iou400_dofit: +(1 - r.f).toFixed(4), kamera: { azim: q[0], elev: q[1], dist: q[2], fov: q[3], roll: 0, shiftX: q[4], shiftY: q[5], w: 1200, h: 1200 }, start: { azim: x0[0], elev: x0[1], dist: x0[2], fov: x0[3], shiftX: x0[4], shiftY: x0[5] } };
  console.log(sku, pohled, 'IoU(400px) start', i0.toFixed(4), '→ dofit', (1 - r.f).toFixed(4), 'Δ azim/elev/fov/dist', (q[0] - x0[0]).toFixed(1), (q[1] - x0[1]).toFixed(1), (q[3] - x0[3]).toFixed(1), (q[2] - x0[2]).toFixed(0));
}
fs.writeFileSync(path.join(scratch, 'mszas', `${sku}_dofit.json`), JSON.stringify(out, null, 1));
await R.close();
