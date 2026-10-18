// Vyhodnocení jedné sady rozměrů (CISTIC_DIMS): sestaví model v paměti, vyrenderuje obrysy při ZADANÝCH kamerách (srovnani/c<N>_<tag>.json) a spočítá IoU + chyby landmarků.
// CISTIC_DIMS=dims.json node nastroje/eval_rozmery.mjs <tag> [res]   → JSON na stdout
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { writeGLB } from '../../../kufriky_cloud/jadro/glb.js';
import { Renderer } from '../../../kufriky_cloud/render/render.mjs';
import { kameraZ } from './kamera_z.mjs';
import { build } from '../stroj_cistic.mjs';
import { K } from '../c_zaklad.mjs';
import { OTVOR } from '../c_kryt.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), ROOT = path.join(HERE, '..');
const tag = process.argv[2], RES = +(process.argv[3] || 330);
const tmp = `/tmp/ev_${process.pid}.glb`; writeGLB(build(), tmp, {});
const xyz = (() => { const S = { E: 1, W: -1 }, o = {}; for (const [n, s] of Object.entries(S)) { o['FT_' + n] = [s * K.hw, K.Yf, K.Ht]; o['SH_' + n] = [s * K.hw, K.ys, K.Ht]; o['SB_' + n] = [s * K.hw, K.yb, K.Hb]; o['FB_' + n] = [s * K.hw, K.Yf, K.zb]; o['FRtf_' + n] = [s * K.hw, K.yft, K.zft]; o['HUB_' + n] = [s * K.xw, K.yw, K.R]; o['TT_' + n] = [s * K.xw, K.yw, 2 * K.R]; o['TB_' + n] = [s * K.xw, K.yw, 0]; o['PBOT_' + n] = [s * K.xp, K.yp, 118]; o['CST_' + n] = [s * K.xc, K.yc, 0]; } o.HOLE = [OTVOR.cx, OTVOR.cy, K.Ht]; o.HNDM = [0, K.Yh, K.zh]; return o; })();
function proj(c, X, w, h) {
  const [cx, cy, cz, yaw, pitch, roll, fov] = c, ya = yaw * Math.PI / 180, pi = pitch * Math.PI / 180, ro = roll * Math.PI / 180;
  const f = [Math.cos(pi) * Math.cos(ya), Math.cos(pi) * Math.sin(ya), Math.sin(pi)];
  const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const r2 = r.map((v, i) => v * Math.cos(ro) + u[i] * Math.sin(ro)), u2 = r.map((v, i) => -v * Math.sin(ro) + u[i] * Math.cos(ro));
  const d = [X[0] - cx, X[1] - cy, X[2] - cz], dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2], fp = (h / 2) / Math.tan(fov * Math.PI / 360);
  return [w / 2 + fp * dot(d, r2) / dot(d, f), h / 2 - fp * dot(d, u2) / dot(d, f)];
}
const out = { iou: {}, lm: {} };
const W0 = RES, H0 = Math.round(RES * 3 / 4);
const R = new Renderer();
if (process.env.CISTIC_WS) {           // sdílený prohlížeč z doladeni_rozmeru.mjs (ušetří start chromia)
  const { chromium } = (await import('node:module')).createRequire(import.meta.url)('/opt/node22/lib/node_modules/playwright');
  R.w = W0; R.h = H0; R.browser = await chromium.connect(process.env.CISTIC_WS); R.page = await R.browser.newPage({ viewport: { width: W0, height: H0 } });
  await R.page.goto('file://' + path.join(ROOT, '../../kufriky_cloud/render/stranka.html')); await R.page.evaluate(([w, h]) => window.init(w, h), [W0, H0]);
} else await R.open(W0, H0);
await R.load(tmp, true);
for (const id of ['11', '12', '13', '14']) {
  const cam = JSON.parse(fs.readFileSync(path.join(ROOT, `srovnani/c${id}_${tag}.json`))).kamera_cx_cy_cz_yaw_pitch_roll_fov;
  const lm = JSON.parse(fs.readFileSync(path.join(ROOT, `zdroje/landmarky/l${id}.json`))), mj = JSON.parse(fs.readFileSync(path.join(ROOT, `zdroje/masky/m${id}.json`)));
  const W = RES, H = Math.round(RES * 3 / 4), k = W / lm.w, poly = mj.polygon.map(([x, y]) => [x * k, y * k]), mask = new Uint8Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) { let c = false; const px = x + 0.5, py = y + 0.5; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) c = !c; } mask[y * W + x] = c ? 1 : 0; }
  const m = await R.mask(kameraZ(cam));
  let I = 0, U = 0; for (let i = 0; i < m.length; i++) { const a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; }
  out.iou[id] = I / U;
  let s = 0, n = 0; for (const [nm, [px, py]] of Object.entries(lm.pts)) { if (!xyz[nm]) continue; const q = proj(cam, xyz[nm], lm.w, lm.h); s += Math.hypot(q[0] - px, q[1] - py) / (lm.w / 1500); n++; } out.lm[id] = s / n;
}
if (process.env.CISTIC_WS) await R.page.close(); else await R.close();
fs.unlinkSync(tmp);
console.log(JSON.stringify(out));
