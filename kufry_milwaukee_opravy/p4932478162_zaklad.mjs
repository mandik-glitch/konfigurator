// Společný základ modelů Milwaukee PACKOUT XL (4932478162 a nová revize 4932501784) a pojízdného boxu 4932498651 – vlastní generátor.
// Jednotky mm. Souřadnice modelu: X = hloubka (čelo s logem do +X), Y = šířka (délka dle katalogu), Z = výška; počátek = střed obálky.
// Nic z Johnových tvarů; jen import jádra (kufriky_cloud/jadro) a vlastních pomocných funkcí (kufriky_cloud/pomocne.mjs).
import { Part, Group, loftRings, box, tube, cylinder, lathe, prism, earClip, roundedBox } from '../kufriky_cloud/jadro/mesh.js';
import { MATERIALY } from '../kufriky_cloud/jadro/glb.js';
import { extrude, roundPoly, offsetPoly, ccw, cw, rectPoly, circlePoly, rotPoly, movePoly, area2 } from '../kufriky_cloud/pomocne.mjs';
export { Part, Group, loftRings, box, tube, cylinder, lathe, prism, earClip, roundedBox, extrude, roundPoly, offsetPoly, ccw, cw, rectPoly, circlePoly, rotPoly, movePoly, area2 };

// doplňkové materiály (jen za běhu skriptu; jádro se neupravuje)
MATERIALY.hlinik = { color: [0.60, 0.62, 0.65], metallic: 0.95, roughness: 0.34 };       // leštěný / kartáčovaný hliník
MATERIALY.guma = { color: [0.012, 0.012, 0.014], metallic: 0.0, roughness: 0.9 };         // černá guma (úchopy, pneumatiky)
MATERIALY.cerna_lesk = { color: [0.012, 0.012, 0.014], metallic: 0.0, roughness: 0.32 };  // lesklé víko
MATERIALY.cervena_mat = { color: [0.50, 0.010, 0.025], metallic: 0.0, roughness: 0.6 };

// ---------- 2D ----------
// obdélník se zaoblenými rohy (CCW); r = číslo nebo [r(+x+y), r(-x+y), r(-x-y), r(+x-y)]; seg = úseků na roh (stejný počet bodů pro všechny vrstvy)
export function rrPoly(x0, x1, y0, y1, rs = 0, seg = 4) {
  const R = Array.isArray(rs) ? rs : [rs, rs, rs, rs];
  const hx = (x1 - x0) / 2, hy = (y1 - y0) / 2;
  const cs = [[x1, y1, 0], [x0, y1, 90], [x0, y0, 180], [x1, y0, 270]], pts = [];
  for (let c = 0; c < 4; c++) {
    const r = Math.max(Math.min(R[c], hx - 1e-4, hy - 1e-4), 1e-3);
    const sx = c === 0 || c === 3 ? -1 : 1, sy = c === 0 || c === 1 ? -1 : 1;
    const cx = cs[c][0] + sx * r, cy = cs[c][1] + sy * r;
    for (let k = 0; k <= seg; k++) { const a = (cs[c][2] + 90 * k / seg) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
  }
  return pts;
}
// z vrstev [{x0,x1,y0,y1,r,z}] poly
export const layerPoly = (L, seg = 4) => rrPoly(L.x0, L.x1, L.y0, L.y1, L.r, seg);
export const lift3 = (P, z) => P.map(p => [p[0], p[1], z]);

// ---------- tělesa ----------
// plné těleso z vrstev [{x0,x1,y0,y1,r,z}] (stejný počet bodů), víčka dole/nahoře
export function loftBox(mat, name, layers, { seg = 4, crease = 35, capStart = 'down', capEnd = 'up' } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  loftRings(p, layers.map(L => lift3(layerPoly(L, seg), L.z)), { capStart, capEnd });
  return p;
}
// dutá nádoba otevřená nahoře: vnější vrstvy zdola nahoru + vnitřní vrstvy shora dolů (poslední = dno)
export function loftVessel(mat, name, outer, inner, { seg = 4, crease = 35 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const rings = [...outer, ...inner].map(L => lift3(layerPoly(L, seg), L.z));
  loftRings(p, rings, { capStart: 'down', capEnd: 'up' });
  return p;
}
// dutý plášť otevřený dolů (víko): vnější vrstvy zdola nahoru, vnitřní shora dolů, uzavřeno okrajem dole
export function loftHood(mat, name, outer, inner, { seg = 4, crease = 35 } = {}) {
  const p = new Part(name, mat); p.crease = crease;
  const rings = [...outer, ...inner].map(L => lift3(layerPoly(L, seg), L.z));
  loftRings(p, rings, { closed: true });
  return p;
}
// zaoblený kvádr v souřadnicích modelu (zkratka)
export const rbox = (mat, name, x0, x1, y0, y1, z0, z1, rc = 2, re = 1, seg = 3) => roundedBox(mat, name, { x0, x1, y0, y1, z0, z1, rc, re, seg, fs: 2 });
export const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, z0, z1);
// extruze obrysu (u,v) v rovině YZ podél X (x0..x1): poly = [[y,z]...]
export function extYZ(mat, name, poly, x0, x1, crease = 25, holes = []) {
  const p = extrude(mat, name, poly, holes, x0, x1, { crease });
  p.mapV((u, v, w) => [w, u, v]);
  // (u,v,w)=(y,z,x) → (x,y,z) je cyklická permutace: orientace se zachová
  return p;
}
// extruze obrysu v rovině XZ podél Y (y0..y1): poly = [[x,z]...]
export function extXZ(mat, name, poly, y0, y1, crease = 25, holes = []) {
  const p = extrude(mat, name, poly, holes, y0, y1, { crease });
  p.mapV((u, v, w) => [u, w, v]); p.flip();
  return p;
}
// válec s osou X: střed (y,z), poloměr r, x0..x1
export function cylX(mat, name, r, x0, x1, y, z, n = 18) {
  return cylinder(mat, name, r, x0, x1, n, [0, 0]).mapV((u, v, w) => [w, u + y, v + z]);
}
// válec s osou Y: střed (x,z), poloměr, y0..y1
export function cylY(mat, name, r, y0, y1, x, z, n = 18) {
  return cylinder(mat, name, r, y0, y1, n, [0, 0]).mapV((u, v, w) => [u + x, w, v + z]).flip();
}
// zrcadlení parts podle roviny Y=0 (kopie s příponou)
export function mirY(p, suffix = '_m') { const q = p.clone(p.name + suffix); q.mirror('y', 0); return q; }
// přidá do skupiny díl a jeho zrcadlo podle Y
export function addSymY(g, p) { g.add(p); g.add(mirY(p)); return p; }
// zrcadlení podle X (přední ↔ zadní)
export function mirX(p, suffix = '_z') { const q = p.clone(p.name + suffix); q.mirror('x', 0); return q; }

// ---------- jednoduchý tahový font (logo): polyline glyfy na mřížce 0..1 × 0..1 (šířka × výška) ----------
// Každý glyf = seznam tahů; tah = pole bodů [u,v]; vykreslí se plochými pásky šířky w tloušťky t v rovině YZ (kolmo k X).
const GLYF = {
  P: [[[0, 0], [0, 1], [0.8, 1], [1, 0.85], [1, 0.62], [0.8, 0.5], [0, 0.5]]],
  A: [[[0, 0], [0.5, 1], [1, 0]], [[0.2, 0.38], [0.8, 0.38]]],
  C: [[[1, 0.85], [0.8, 1], [0.2, 1], [0, 0.8], [0, 0.2], [0.2, 0], [0.8, 0], [1, 0.15]]],
  K: [[[0, 0], [0, 1]], [[1, 1], [0, 0.42]], [[0.25, 0.58], [1, 0]]],
  O: [[[0.2, 0], [0, 0.2], [0, 0.8], [0.2, 1], [0.8, 1], [1, 0.8], [1, 0.2], [0.8, 0], [0.2, 0]]],
  U: [[[0, 1], [0, 0.18], [0.2, 0], [0.8, 0], [1, 0.18], [1, 1]]],
  T: [[[0, 1], [1, 1]], [[0.5, 1], [0.5, 0]]],
  M: [[[0, 0], [0.04, 1], [0.5, 0.35], [0.96, 1], [1, 0]]],
  i: [[[0.5, 0], [0.5, 0.62]], [[0.5, 0.82], [0.5, 0.95]]],
  l: [[[0.5, 0], [0.5, 1]]],
  w: [[[0, 0.62], [0.25, 0], [0.5, 0.45], [0.75, 0], [1, 0.62]]],
  a: [[[0.9, 0.62], [0.9, 0]], [[0.9, 0.5], [0.7, 0.62], [0.25, 0.62], [0.05, 0.45], [0.05, 0.17], [0.25, 0], [0.7, 0], [0.9, 0.14]]],
  u: [[[0.05, 0.62], [0.05, 0.15], [0.25, 0], [0.7, 0], [0.9, 0.12]], [[0.9, 0.62], [0.9, 0]]],
  k: [[[0.05, 0], [0.05, 1]], [[0.85, 0.62], [0.05, 0.25]], [[0.3, 0.38], [0.9, 0]]],
  e: [[[0.05, 0.3], [0.95, 0.3], [0.95, 0.45], [0.75, 0.62], [0.25, 0.62], [0.05, 0.45], [0.05, 0.17], [0.25, 0], [0.75, 0], [0.95, 0.12]]],
};
// text → díl (cervena) v rovině X = x0 .. x0+t; počátek (yc = střed textu, zb = spodek), výška h, šířka znaku cw, mezera gap, šířka tahu w; skos = zešikmení (italic) v mm na výšku
export function textYZ(mat, name, str, { x0, t = 1.2, yc, zb, h, cw, gap = 0.2, w = 2.2, skew = 0, mirror = false }) {
  const p = new Part(name, mat); p.crease = 20;
  const adv = cw * (1 + gap), total = adv * str.length - cw * gap;
  let u0 = -total / 2;
  for (const ch of str) {
    const g = GLYF[ch];
    if (g) for (const stroke of g) {
      const pts = stroke.map(([u, v]) => { const yy = u0 + u * cw + skew * v * h; return [mirror ? yc - yy : yc + yy, zb + v * h]; });
      for (let i = 0; i < pts.length - 1; i++) {
        const a = pts[i], b = pts[i + 1], dy = b[0] - a[0], dz = b[1] - a[1], L = Math.hypot(dy, dz) || 1, ny = -dz / L * w / 2, nz = dy / L * w / 2;
        const q = [[a[0] + ny, a[1] + nz], [b[0] + ny, b[1] + nz], [b[0] - ny, b[1] - nz], [a[0] - ny, a[1] - nz]];
        const e = extYZ(mat, 'seg', mirror ? q.slice().reverse() : q, x0, x0 + t, 20); p.append(e);
      }
      // zaoblení styků (kolečka) – jen pro návaznost tahů
      for (let i = 1; i < pts.length - 1; i++) { const c = cylX(mat, 'k', w / 2, x0, x0 + t, pts[i][0], pts[i][1], 8); p.append(c); }
    }
    u0 += adv;
  }
  return p;
}
