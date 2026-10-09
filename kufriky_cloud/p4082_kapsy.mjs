// Kapsy víka (tenkostěnné misky s šikmou stěnou, uši v zadních rozích, šestiúhelníková mřížka na dně) – model 4932464082.
import { Part, rrPoly, ccw, ext, slab, rrShell, bx, zc } from './p4082_zaklad.mjs';

// šestiúhelníková mřížka (strana a) jako tenké pásky na dně kapsy; jen hrany plně uvnitř obdélníku [x0,x1]×[y0,y1]
// orientace: plochá horní a spodní hrana rovnoběžná s osou Y (jako na fotografiích, pohled shora s čelem nahoře)
export function hexMrizka(mat, name, { x0, x1, y0, y1, z, a = 7.0, w = 0.7, ox = 0, oy = 0 }) {
  const p = new Part(name, mat); p.crease = 60;
  const h = Math.sqrt(3) * a, edge = (ax, ay, bx_, by) => {
    const m = 0.2;
    if (ax < x0 + m || ax > x1 - m || bx_ < x0 + m || bx_ > x1 - m || ay < y0 + m || ay > y1 - m || by < y0 + m || by > y1 - m) return;
    const dx = bx_ - ax, dy = by - ay, l = Math.hypot(dx, dy), nx = -dy / l * w / 2, ny = dx / l * w / 2, Z = zc(z);
    const v = [p.addV(ax + nx, ay + ny, Z), p.addV(bx_ + nx, by + ny, Z), p.addV(bx_ - nx, by - ny, Z), p.addV(ax - nx, ay - ny, Z)];
    p.addQ(v[0], v[1], v[2], v[3]); p.addQ(v[0], v[3], v[2], v[1]);        // dvoustranně
  };
  const ncol = Math.ceil((y1 - y0) / (1.5 * a)) + 3, nrow = Math.ceil((x1 - x0) / h) + 3;
  for (let i = -1; i < ncol; i++) for (let j = -1; j < nrow; j++) {
    const cy = y0 + oy + i * 1.5 * a, cx = x0 + ox + j * h + (i & 1 ? h / 2 : 0);
    // vrcholy v rovině (y,x): θ = 0,60,...  (u = y, v = x)
    const V = k => { const t = Math.PI / 3 * k; return [cx + a * Math.sin(t), cy + a * Math.cos(t)]; };      // [x, y]
    // tři „horní“ hrany šestiúhelníku: 0→1 (pravá horní), 1→2 (horní), 2→3 (levá horní) v souř. (u=y,v=x)
    for (const [k0, k1] of [[0, 1], [1, 2], [2, 3]]) { const A = V(k0), B = V(k1); edge(A[0], A[1], B[0], B[1]); }
  }
  return p;
}

// kapsa víka: obrys rim = [x0,x1]×[y0,y1] (přední rohy zkosené, zadní zaoblené), hloubka d, šikmá stěna o vodorovném průmětu s
export function kapsa(g, { x0, x1, y0, y1, zTop, d, s, hex = true, ucho = true, name = 'vicko_kapsa', matStena = 'cira', matLines = 'bila' }) {
  const rs = [9, 6, 6, 9], seg = [1, 3, 3, 1];
  const zF = zTop - d;
  g.add(rrShell(matStena, name, { x0, x1, y0, y1, rs, seg, profile: [[zTop, 0], [zF, s], [zF - 1.2, s], [zTop - 1.2, 1.4]], closed: true, crease: 50 }));
  g.add(ext(matStena, name + '_dno', ccw(rrPoly(x0 + s, x1 - s, y0 + s, y1 - s, 0.5, 1)), zF - 1.2, zF));
  if (ucho) {
    // uši: průhledné vzpěry v zadních rozích (šířka 9, délka 26 v x), od dna po okraj
    for (const sy of [-1, 1]) {
      const ya = sy > 0 ? y1 - s - 9 : y0 + s, yb = sy > 0 ? y1 - s : y0 + s + 9;
      g.add(bx(matStena, name + '_ucho', x0 + s, x0 + s + 26, ya, yb, zF, zF + d * 0.8));
    }
  }
  if (hex) g.add(hexMrizka(matLines, name + '_hex', { x0: x0 + s + 1.2, x1: x1 - s - 1.2, y0: y0 + s + 1.2, y1: y1 - s - 1.2, z: zF + 0.15, ox: 0, oy: 0 }));
}
