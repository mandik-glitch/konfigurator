// Projekce bodu modelu do pixelů fotografie podle kamery {azim, elev, dist, fov, cx, cy, roll} (stejné konvence jako render.mjs).
export function project(X, c, W = 1200, H = 1200) {
  const a = c.azim * Math.PI / 180, e = c.elev * Math.PI / 180, d = c.dist;
  const pos = [d * Math.cos(e) * Math.cos(a), d * Math.cos(e) * Math.sin(a), d * Math.sin(e)];
  const f = pos.map(v => -v / d); const cr = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  let r = cr(f, [0, 0, 1]); const rl = Math.hypot(...r); r = r.map(v => v / rl); const u = cr(r, f);
  const ro = (c.roll || 0) * Math.PI / 180, cs = Math.cos(ro), sn = Math.sin(ro);
  const r2 = r.map((v, i) => v * cs + u[i] * sn), u2 = r.map((v, i) => -v * sn + u[i] * cs);
  const dd = [X[0] - pos[0], X[1] - pos[1], X[2] - pos[2]]; const dot = (p, q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];
  const xc = dot(dd, r2), yc = dot(dd, u2), zc = dot(dd, f), t = Math.tan(c.fov * Math.PI / 360);
  return [c.cx + (W / 2) * (xc / zc) / (t * W / H), c.cy - (H / 2) * (yc / zc) / t];
}
