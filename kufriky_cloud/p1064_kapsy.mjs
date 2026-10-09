// Kapsy víka 4932471064: obrys (rim) a dno (floor) se stejnou topologií, šikmé stěny vpředu a po stranách, svislá zadní stěna,
// "uši" (průhledné rampy) v zadních rozích, šestiúhelníková mřížka na dně. Plán (xp, Y) → model přes X().
import { Part } from './p1064_zaklad.mjs';
import { area2 } from './pomocne_4932471064.mjs';
import { X } from './p1064_data.mjs';

// kapsa: rim a floor jako pole [xp, Y] (CCW v plánu)
// b0/b1 = zadní/přední hrana obrysu (xp), y0/y1 = Y rozsah obrysu
export function kapsaLoops({ xp0, xp1, y0, y1 }, o = {}) {
  const yc = (y0 + y1) / 2, hw = (y1 - y0) / 2;
  const cf = o.cf ?? 11, cr = o.cr ?? 4, ear = o.ear ?? 16.0, iS = o.iS ?? 10.0, sf = o.sf ?? 10.5, sr = o.sr ?? 2.0;
  const bs = xp0 + (o.step ?? 27.0), cf2 = o.cf2 ?? 7.5, cr2 = o.cr2 ?? 3;
  const b0 = xp0, b1 = xp1;
  const rim = [[-hw, b0 + cr], [-hw, bs], [-hw, bs], [-hw, b1 - cf], [-hw + cf, b1], [hw - cf, b1], [hw, b1 - cf], [hw, bs], [hw, bs], [hw, b0 + cr], [hw - cr, b0], [-hw + cr, b0]];
  const flr = [[-hw + ear, b0 + sr + cr2], [-hw + ear, bs], [-hw + iS, bs], [-hw + iS, b1 - sf - cf2], [-hw + iS + cf2, b1 - sf], [hw - iS - cf2, b1 - sf], [hw - iS, b1 - sf - cf2], [hw - iS, bs], [hw - ear, bs], [hw - ear, b0 + sr + cr2], [hw - ear - cr2, b0 + sr], [-hw + ear + cr2, b0 + sr]];
  const conv = L => L.map(([a, b]) => [b, yc + a]);
  let R = conv(rim), F = conv(flr);
  if (area2(R) < 0) { R = R.reverse(); F = F.reverse(); }
  return { rim: R, floor: F };
}
// pruh uprostřed: osmiúhelník s jednou svislou stěnou
export function pruhLoops({ y, xp0, xp1 }, ch = 10, d = 3) {
  const mk = (e) => [[xp0 + e + ch, -y + e], [xp1 - e - ch, -y + e], [xp1 - e, -y + e + ch], [xp1 - e, y - e - ch], [xp1 - e - ch, y - e], [xp0 + e + ch, y - e], [xp0 + e, y - e - ch], [xp0 + e, -y + e + ch]];
  let R = mk(0), F = mk(d);
  if (area2(R) < 0) { R = R.reverse(); F = F.reverse(); }
  return { rim: R, floor: F };
}

// šestiúhelníková mřížka jako tenké pásky; jen hrany plně uvnitř polygonu poly [xp,Y] (bod-v-polygonu); z' = výška
export function hexMrizka(mat, name, poly, z, { a = 6.7, w = 0.7, ox = 0, oy = 0, zc0 = 32 } = {}) {
  const p = new Part(name, mat); p.crease = 60;
  let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
  for (const [u, v] of poly) { x0 = Math.min(x0, u); x1 = Math.max(x1, u); y0 = Math.min(y0, v); y1 = Math.max(y1, v); }
  const inside = (u, v) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > v) !== (yj > v) && u < (xj - xi) * (v - yi) / (yj - yi) + xi) c = !c; } return c; };
  const h = Math.sqrt(3) * a, Z = z - zc0;
  const edge = (ax, ay, bx_, by) => {
    if (!(inside(ax, ay) && inside(bx_, by) && inside((ax + bx_) / 2, (ay + by) / 2))) return;
    const dx = bx_ - ax, dy = by - ay, l = Math.hypot(dx, dy), nx = -dy / l * w / 2, ny = dx / l * w / 2;
    const v = [p.addV(X(ax + nx), ay + ny, Z), p.addV(X(bx_ + nx), by + ny, Z), p.addV(X(bx_ - nx), by - ny, Z), p.addV(X(ax - nx), ay - ny, Z)];
    p.addQ(v[0], v[1], v[2], v[3]); p.addQ(v[0], v[3], v[2], v[1]);
  };
  const ncol = Math.ceil((y1 - y0) / (1.5 * a)) + 3, nrow = Math.ceil((x1 - x0) / h) + 3;
  for (let i = -1; i < ncol; i++) for (let j = -1; j < nrow; j++) {
    const cy = y0 + oy + i * 1.5 * a, cx = x0 + ox + j * h + (i & 1 ? h / 2 : 0);
    const V = k => { const t = Math.PI / 3 * k; return [cx + a * Math.sin(t), cy + a * Math.cos(t)]; };      // [xp, Y]
    for (const [k0, k1] of [[0, 1], [1, 2], [2, 3]]) { const A = V(k0), B = V(k1); edge(A[0], A[1], B[0], B[1]); }
  }
  return p;
}
