// Společná knihovna kamer (vlastní, SKU 4932498651 / 4932478162 / 4932501784): projekce 3D → pixel a zpětná projekce pixelu na rovinu.
// Konvence jako kufriky_cloud/render/render.mjs: azim 0 = pohled z +X, 90 = z +Y; elev nad horizontem; kamera míří do středu (0,0,0);
// shiftX/shiftY = posun obrazu v podílu rozměru; roll ve stupních (rotateZ kamery).
export function camFromJson(j) {
  const c = j.kamera || j;
  const sx = c.shiftX !== undefined ? c.shiftX : (c.cx - c.w / 2) / c.w, sy = c.shiftY !== undefined ? c.shiftY : (c.cy - c.h / 2) / c.h;
  return { azim: c.azim, elev: c.elev, dist: c.dist, fov: c.fov, roll: c.roll || 0, sx, sy, w: c.w || 1200, h: c.h || 1200 };
}
const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export function basis(c) {
  const a = c.azim * Math.PI / 180, e = c.elev * Math.PI / 180;
  const pos = [c.dist * Math.cos(e) * Math.cos(a), c.dist * Math.cos(e) * Math.sin(a), c.dist * Math.sin(e)];
  const f = pos.map(v => -v / c.dist);
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const ro = (c.roll || 0) * Math.PI / 180;
  const r2 = r.map((v, i) => v * Math.cos(ro) + u[i] * Math.sin(ro)), u2 = r.map((v, i) => -v * Math.sin(ro) + u[i] * Math.cos(ro));
  return { pos, f, r: r2, u: u2 };
}
export function proj(c, X) {
  const B = basis(c), d = [X[0] - B.pos[0], X[1] - B.pos[1], X[2] - B.pos[2]];
  const xc = dot(d, B.r), yc = dot(d, B.u), zc = dot(d, B.f), t = Math.tan(c.fov * Math.PI / 360);
  return [c.w * (0.5 + (xc / zc) / (t * c.w / c.h) / 2) + c.sx * c.w, c.h * (0.5 - (yc / zc) / t / 2) + c.sy * c.h];
}
// paprsek pixelem → bod na rovině osa=hodnota ('X'|'Y'|'Z')
export function unproj(c, px, py, osa, hv) {
  const B = basis(c), t = Math.tan(c.fov * Math.PI / 360);
  const nx = ((px - c.sx * c.w) / c.w - 0.5) * 2 * (t * c.w / c.h), ny = -((py - c.sy * c.h) / c.h - 0.5) * 2 * t;
  const dir = [0, 1, 2].map(i => B.f[i] + nx * B.r[i] + ny * B.u[i]);
  const k = { X: 0, Y: 1, Z: 2 }[osa], s = (hv - B.pos[k]) / dir[k];
  return [0, 1, 2].map(i => B.pos[i] + s * dir[i]);
}
