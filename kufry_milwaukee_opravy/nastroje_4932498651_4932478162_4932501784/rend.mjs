// Render GLB z uložené kamery + IoU proti masce fotografie + dvojice foto | model | překryv (do scratchpadu).
// node rend.mjs --glb X.glb --foto f.jpg --cam cam.json --png out.png [--pair pair.png] [--iou-json o.json] [--pose a=10,b=20] [--pos madlo=600,zasuvka=300] [--hide a,b] [--W 1200] [--L 600] [--ycut px]
import fs from 'node:fs'; import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Renderer, kamera } from '../../kufriky_cloud/render/render.mjs';
const HERE = path.dirname(fileURLToPath(import.meta.url)), KC = path.join(HERE, '../../kufriky_cloud');
export const SCR = process.env.KUF_SCRATCH || '/tmp/claude-0/-home-user-konfigurator/4afe04ea-52af-557e-a8a4-75a8d542e4f9/scratchpad/m';
const opt = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
export function parseKV(s) { const o = {}; for (const kv of (s || '').split(',').filter(Boolean)) { const [k, v] = kv.split('='); o[k] = +v; } return o; }
// pózy: rotace (°) přes window.pose a posuvy (mm) podél extras.osa
export async function nastavPozu(R, rot, pos) {
  await R.pose(rot || {});
  if (pos && Object.keys(pos).length) await R.page.evaluate(p => {
    root.traverse(o => { const d = p[o.name]; if (d !== undefined && o.userData.posuv_osa) { const ax = new THREE.Vector3(...o.userData.posuv_osa).normalize(); if (!o.userData._p0) o.userData._p0 = o.position.clone(); o.position.copy(o.userData._p0).addScaledVector(ax, d); } });
  }, pos);
}
export function camObj(j, w, h) {
  const c = j.kamera || j;
  const sx = c.shiftX !== undefined ? c.shiftX : (c.cx - (c.w || 1200) / 2) / (c.w || 1200), sy = c.shiftY !== undefined ? c.shiftY : (c.cy - (c.h || 1200) / 2) / (c.h || 1200);
  return kamera({ azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll || 0, shiftX: sx, shiftY: sy });
}
export async function maska(foto, L = 600, nofill = false) {
  const mf = path.join(SCR, 'mask_' + path.basename(path.dirname(foto)) + '_' + path.basename(foto) + '_' + L + (nofill ? '_nf' : '') + '.bin');
  if (!fs.existsSync(mf)) execFileSync('python3', ['-I', nofill ? path.join(HERE, 'maska_nefill.py') : path.join(KC, 'nastroje/foto_maska.py'), foto, mf, String(L)], { stdio: 'ignore' });
  const mb = fs.readFileSync(mf); return { w: mb.readUInt32LE(0), h: mb.readUInt32LE(4), mask: mb.slice(8) };
}
export async function iouRender({ glb, foto, cam, rot, pos, hide = [], L = 600, ycut = 0, nofill = false }) {
  const { w, h, mask } = await maska(foto, L, nofill);
  const R = await new Renderer().open(w, h); await R.load(glb, true); if (hide.length) await R.hide(hide); await nastavPozu(R, rot, pos);
  const m = await R.mask(camObj(cam, w, h)); await R.close();
  let I = 0, U = 0, I2 = 0, U2 = 0; const yc = Math.round(ycut * h / 1200);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = y * w + x, a = m[i], b = mask[i]; if (a & b) I++; if (a | b) U++; if (y >= yc) { if (a & b) I2++; if (a | b) U2++; } }
  return { iou: +(I / U).toFixed(4), iou_pod_radkem: +(I2 / U2).toFixed(4), ycut_px: ycut };
}
export async function renderPng({ glb, cam, rot, pos, hide = [], W = 1200, out, bg = null }) {
  const R = await new Renderer().open(W, W); await R.load(glb, false); if (hide.length) await R.hide(hide); await nastavPozu(R, rot, pos); if (bg) await R.bg(bg);
  await R.png(camObj(cam, W, W), out); await R.close();
}
if (process.argv[1] && process.argv[1].endsWith('rend.mjs')) {
  const glb = opt('glb'), foto = opt('foto'), camf = opt('cam'), png = opt('png'), pair = opt('pair', null);
  const cam = JSON.parse(fs.readFileSync(camf)); const rot = parseKV(opt('pose', '')), pos = parseKV(opt('pos', '')), hide = (opt('hide', '') || '').split(',').filter(Boolean);
  const res = await iouRender({ glb, foto, cam, rot, pos, hide, L: +opt('L', 600), ycut: +opt('ycut', 0) });
  await renderPng({ glb, cam, rot, pos, hide, W: +opt('W', 1200), out: png });
  if (pair) execFileSync('python3', [path.join(KC, 'nastroje/porovnej.py'), foto, png, pair, '700'], { stdio: 'ignore' });
  if (opt('iou-json', null)) fs.writeFileSync(opt('iou-json'), JSON.stringify(res));
  console.log(JSON.stringify(res));
}
