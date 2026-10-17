// Ladění svislých/bočních poloh předního hardwaru podle IoU červených prvků (rukojeť, západky, kroužek, jazýček, štítek) při FIXNÍ kameře (dofitované k obrysu).
// node ladeni_cervena.mjs <SKU> <pohled> '{"param":krok,...}' [kola=3]   → vypíše nejlepší hodnoty; do modelu se přepisují ručně (p4932464079_data.mjs)
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from './render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [sku, pohled, stepsJ, kolaN = '3'] = process.argv.slice(2);
const cfg = JSON.parse(fs.readFileSync(path.join(HERE, `cfg_${sku}.json`), 'utf8'))[pohled];
const dof = JSON.parse(fs.readFileSync(path.join(HERE, '../../kufriky_cloud/srovnani_opravy', sku, `kamery_dofit_${sku}.json`), 'utf8'))[pohled];
const scratch = process.env.KUF_SCRATCH || '/tmp/kuf_scratch'; fs.mkdirSync(scratch, { recursive: true });
const L = 640, mf = path.join(scratch, `cm_${sku}_${pohled}.bin`);
execFileSync('python3', [path.join(HERE, 'cervena_maska.py'), cfg.foto, mf, String(L)]);
const photo = Buffer.from(fs.readFileSync(mf).slice(8));
const REG = process.env.KUF_REG ? process.env.KUF_REG.split(',').map(Number) : null;   // oblast v px fotografie 1200 (x0,y0,x1,y1) – mimo ni se červená nepočítá (např. nářadí na fotografii)
const inReg = i => { if (!REG) return true; const x = (i % L + .5) * 1200 / L, y = (((i / L) | 0) + .5) * 1200 / L; return x >= REG[0] && x <= REG[2] && y >= REG[1] && y <= REG[3]; };
const c = dof.kamera, cam = kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: 0, shiftX: (c.cx - 600) / 1200, shiftY: (c.cy - 600) / 1200 });
const R = await new Renderer().open(L, L);
const glb = `/tmp/lad_${sku}.glb`;
async function ev(ovr) {
  try { execFileSync('node', [path.join(HERE, '../vytvor_4932464079_4932499703.mjs'), sku], { env: { ...process.env, KUF_OVR: JSON.stringify(ovr), KUF_OUT: glb }, stdio: 'ignore' }); } catch (e) { if (e.status !== 1) throw e; }   // exit 1 = obálka mimo toleranci (GLB se zapíše)
  await R.load(glb, false); await R.pose(dof.pose || {});
  const rgb = await R.rgb(cam); let I = 0, U = 0;
  for (let i = 0; i < L * L; i++) { if (!inReg(i)) continue; const r = rgb[3 * i], g = rgb[3 * i + 1], b = rgb[3 * i + 2]; const m = (r > 130 && g < 95 && b < 95 && r - g > 60) ? 1 : 0, p = photo[i]; if (m & p) I++; if (m | p) U++; }
  return I / U;
}
const steps = JSON.parse(stepsJ); const base = {}; // výchozí hodnoty z dat
const D = await import(path.join(HERE, '../p4932464079_data.mjs')); const V0 = { 4932464079: D.V79, 4932464080: D.V80, 4932499703: D.V499703, 4932499704: D.V499703 }[sku];
for (const k of Object.keys(steps)) base[k] = V0[k];
let best = await ev(base); console.log('start', best.toFixed(4), JSON.stringify(base));
for (let pass = 0; pass < +kolaN; pass++) {
  for (const k of Object.keys(steps)) for (const sg of [1, -1]) { const t = { ...base, [k]: base[k] + sg * steps[k] }; const v = await ev(t); if (v > best + 1e-4) { best = v; base[k] = t[k]; console.log('  ', k, '→', t[k], best.toFixed(4)); break; } }
  for (const k of Object.keys(steps)) steps[k] /= 2;
}
console.log('NEJLEPŠÍ', best.toFixed(4), JSON.stringify(base)); await R.close();
