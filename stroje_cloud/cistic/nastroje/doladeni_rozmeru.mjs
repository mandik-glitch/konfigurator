// Doladění rozměrů těla (slovník DA v c_zaklad.mjs) Nelderovým–Meadovým simplexem: cena = průměr (1 − IoU) při pevných kamerách (srovnani/c<N>_<tag>.json)
// + váha × průměrná chyba landmarků + apriorní trest (rozměr se nesmí příliš vzdálit od odhadu ze svazkového vyrovnání).
// node nastroje/doladeni_rozmeru.mjs <tag> [iterace=120] [vystup.json]   → po doběhu zapíše zdroje/rozmery_doladene_<tag>.json
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { DA } from '../c_zaklad.mjs';
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
const server = await chromium.launchServer({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--allow-file-access-from-files'] });
const WS = server.wsEndpoint();
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..');
const tag = process.argv[2], ITER = +(process.argv[3] || 120), outFile = process.argv[4] || path.join(ROOT, `zdroje/rozmery_doladene_${tag}.json`);
const WL = 0.004;
// [klíč, rozsah ±(hranice a σ priorů)]
const P = [['hw', 8], ['Yf', 14], ['ys', 16], ['yb', 16], ['Hb', 14], ['zb', 10], ['zft', 10], ['yft', 12], ['yRear', 12], ['xp', 8], ['yp', 12], ['Yh', 14], ['zh', 16], ['hwBox', 8], ['zBoxT', 10], ['xc', 10], ['yc', 12], ['holeX', 30], ['holeY', 25], ['R', 5], ['tw', 14], ['Rc', 4]];
const x0 = P.map(([k]) => DA[k]);
let evals = 0;
function cost(x) {
  for (let i = 0; i < P.length; i++) if (Math.abs(x[i] - x0[i]) > P[i][1]) return 9;
  const f = `/tmp/dims_${process.pid}.json`, d = {}; P.forEach(([k], i) => { d[k] = x[i]; }); fs.writeFileSync(f, JSON.stringify(d));
  let r; try { r = JSON.parse(execFileSync('node', [path.join(HERE, 'eval_rozmery.mjs'), tag, '300'], { env: { ...process.env, CISTIC_DIMS: f, CISTIC_WS: WS }, encoding: 'utf8' })); } catch (e) { return 9; }
  evals++;
  const iou = Object.values(r.iou).reduce((a, b) => a + b, 0) / 4, lm = Object.values(r.lm).reduce((a, b) => a + b, 0) / 4;
  let pr = 0; P.forEach(([k, s], i) => { pr += ((x[i] - x0[i]) / s) ** 2; });
  return (1 - iou) + WL * lm + 0.0008 * pr;
}
async function nm(x, steps, iters) {
  const n = x.length; let pts = [x.slice()]; for (let i = 0; i < n; i++) { const q = x.slice(); q[i] += steps[i]; pts.push(q); }
  let vals = pts.map(cost);
  for (let it = 0; it < iters; it++) {
    const idx = vals.map((v, i) => i).sort((a, b) => vals[a] - vals[b]); pts = idx.map(i => pts[i]); vals = idx.map(i => vals[i]);
    if (Math.abs(vals[n] - vals[0]) < 2e-5) break;
    const c = new Array(n).fill(0); for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) c[j] += pts[i][j] / n;
    const along = t => c.map((v, j) => v + t * (pts[n][j] - v));
    const xr = along(-1), fr = cost(xr);
    if (fr < vals[0]) { const xe = along(-2), fe = cost(xe); if (fe < fr) { pts[n] = xe; vals[n] = fe; } else { pts[n] = xr; vals[n] = fr; } }
    else if (fr < vals[n - 1]) { pts[n] = xr; vals[n] = fr; }
    else { const xc = fr < vals[n] ? along(-0.5) : along(0.5), fc = cost(xc); if (fc < Math.min(fr, vals[n])) { pts[n] = xc; vals[n] = fc; } else { for (let i = 1; i <= n; i++) { pts[i] = pts[i].map((v, j) => pts[0][j] + 0.5 * (v - pts[0][j])); vals[i] = cost(pts[i]); } } }
    if (it % 10 === 0) console.error('it', it, 'cena', vals[0].toFixed(5), 'evals', evals);
  }
  const b = vals.indexOf(Math.min(...vals)); return { x: pts[b], f: vals[b] };
}
const base = cost(x0); console.error('start cena', base.toFixed(5));
const r = await nm(x0, P.map(([, s]) => s * 0.25), ITER);
const d = {}; P.forEach(([k], i) => { d[k] = +r.x[i].toFixed(2); });
fs.writeFileSync(outFile, JSON.stringify({ tag, cena_start: base, cena: r.f, evals, dims: d, poznamka: 'rozměry v „A“ prostoru (před roztažením v Y); doladěno proti ručně obkresleným obrysům + landmarkům při pevných kamerách; priory = ±rozsah' }, null, 1));
console.log(JSON.stringify({ start: base, konec: r.f, evals, dims: d }));
await server.close();
