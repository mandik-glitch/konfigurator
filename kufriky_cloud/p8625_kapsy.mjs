// Šestiúhelníková mřížka na dně kapes víka (tenké bílé pásky) – model 4932478625 (převzato z p4082_kapsy.mjs, výška ZC = 89).
import { Part, zc } from './p8625_zaklad.mjs';

// šestiúhelníková mřížka (strana a) jako tenké pásky na dně kapsy; jen hrany plně uvnitř obdélníku [x0,x1]×[y0,y1]
// orientace: plochá horní a spodní hrana rovnoběžná s osou Y (pohled shora s čelem nahoře, c04)
export function hexMrizka(mat, name, { x0, x1, y0, y1, z, a = 6.6, w = 0.7, ox = 0, oy = 0, gx = 0, gy = 0, ok = null }) {
  const p = new Part(name, mat); p.crease = 60;
  const h = Math.sqrt(3) * a, edge = (ax, ay, bx_, by) => {
    const m = 0.2;
    if (ok && !(ok(ax, ay) && ok(bx_, by))) return;
    if (ax < x0 + m || ax > x1 - m || bx_ < x0 + m || bx_ > x1 - m || ay < y0 + m || ay > y1 - m || by < y0 + m || by > y1 - m) return;
    const dx = bx_ - ax, dy = by - ay, l = Math.hypot(dx, dy), nx = -dy / l * w / 2, ny = dx / l * w / 2, Z = zc(z);
    const v = [p.addV(ax + nx, ay + ny, Z), p.addV(bx_ + nx, by + ny, Z), p.addV(bx_ - nx, by - ny, Z), p.addV(ax - nx, ay - ny, Z)];
    p.addQ(v[0], v[1], v[2], v[3]); p.addQ(v[0], v[3], v[2], v[1]);        // dvoustranně
  };
  const X0 = gx || x0, Y0 = gy || y0;                                        // společná kotva mřížky (aby na sebe navazovaly)
  const ncol = Math.ceil((y1 - Y0) / (1.5 * a)) + 3, nrow = Math.ceil((x1 - X0) / h) + 3;
  for (let i = -ncol; i < ncol; i++) for (let j = -nrow; j < nrow; j++) {
    const cy = Y0 + oy + i * 1.5 * a, cx = X0 + ox + j * h + (i & 1 ? h / 2 : 0);
    if (cy < y0 - 2 * a || cy > y1 + 2 * a || cx < x0 - 2 * h || cx > x1 + 2 * h) continue;
    const V = k => { const t = Math.PI / 3 * k; return [cx + a * Math.sin(t), cy + a * Math.cos(t)]; };
    for (const [k0, k1] of [[0, 1], [1, 2], [2, 3]]) { const A = V(k0), B = V(k1); edge(A[0], A[1], B[0], B[1]); }
  }
  return p;
}
