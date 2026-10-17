// Společný základ parametrického generátoru boxů se zásuvkami Milwaukee PACKOUT (SKU 4932472129 / 4932472130 / 4932493189 / 4932493190).
// Vlastní generátor (jádro kufriky_cloud/jadro), tvar podle fotografií výrobce; nic z Johnových modelů se nepoužívá.
// Jednotky mm. Souřadnice: X = hloubka (414, ČELO se zásuvkami do +X), Y = šířka (564), Z = výška (363); počátek = střed obálky.
// Obálka: x ±207, y ±282, z ±181,5. Díly se tvoří přímo v souřadnicích modelu.
import { Part, Group, loftRings, earClip, box, tube, cylinder, lathe, prism, roundedBox, rrRing } from '../kufriky_cloud/jadro/mesh.js';
export { Part, Group, box, tube, cylinder, lathe, prism, roundedBox, loftRings, earClip };

export const G = {
  HX: 207, HY: 282, HZ: 181.5,            // poloviny obálky
  FACE_X: 198,                            // rovina čel zásuvek (zavřených)
  ZASUVKY_Z1: 144, ZASUVKY_Z0: -138,      // horní/dolní mez oblasti čel (z fotek, čelní pohled)
  MEZERA: 4,                              // mezera mezi čely
  VYSUV_PLNY: 372, VYSUV_CAST: 240,       // odečteno z fotek c04/c05 (viz zdroje/*_poznamky.md)
};

// zaoblený kvádr – zkratka
export const rbx = (mat, name, x0, x1, y0, y1, z0, z1, rc = 2, re = 1, seg = 3, fs = 2) =>
  roundedBox(mat, name, { x0, x1, y0, y1, z0, z1, rc, re, seg, fs });

// anizotropní loft zaoblených obdélníků: profile = [[z, dx, dy, r?, dxZad?], ...] (dx = odsazení čela (+X), dxZad = odsazení zadní hrany (−X; výchozí = dx),
// dy = odsazení boků, r = poloměr rohu prstence, jinak odvozen z rc). Pravidlo orientace viz jadro/mesh.js (profil zdola po vnější straně nahoru).
export function loftRR(mat, name, { cx = 0, cy = 0, hx, hy, rc = 10, seg = 5, profile, capStart = null, capEnd = null, crease = 40 }) {
  const p = new Part(name, mat); p.crease = crease;
  const rings = profile.map(([z, dx, dy, r, dxz]) => {
    const dz = dxz ?? dx, x0 = cx - hx + dz, x1 = cx + hx - dx;
    return rrRing((x0 + x1) / 2, cy, Math.max((x1 - x0) / 2, 0.5), Math.max(hy - dy, 0.5), r ?? Math.max(rc - (dx + dy) / 2, 1.5), seg).map(q => [q[0], q[1], z]);
  });
  loftRings(p, rings, { capStart, capEnd });
  return p;
}

// extruze obrysu v rovině YZ podél X: poly = [[y,z]...]
export function extYZ(mat, name, poly, x0, x1, crease = 25) {
  const p = prism(mat, name, poly, x0, x1); p.crease = crease; p.mapV((u, v, w) => [w, u, v]); return p;
}
// extruze obrysu v rovině XZ podél Y: poly = [[x,z]...]; mapování (u,v,w)->(u,w,v) mění orientaci, proto flip
export function extXZ(mat, name, poly, y0, y1, crease = 25) {
  const p = prism(mat, name, poly, y0, y1); p.crease = crease; p.mapV((u, v, w) => [u, w, v]); p.flip(); return p;
}

// válec s osou podél X: x0..x1 na pozici (y,z)
export function cylX(mat, name, r, x0, x1, y, z, n = 18) { return cylinder(mat, name, r, x0, x1, n, [0, 0]).rot('y', 90).move(0, y, z); }

// zrcadlená kopie dílu podle Y=0 (přejmenovaná)
export const zrcY = (part, name) => part.clone(name).mirror('y', 0);

// doplní komplement obdélníků: z obdélníku R=[x0,x1,y0,y1] odečte disjunktní obdélníky H a vrátí obdélníky (rozklad po řádcích mřížky)
export function komplement(R, H) {
  const xs = [...new Set([R[0], R[1], ...H.flatMap(h => [h[0], h[1]])])].sort((a, b) => a - b);
  const ys = [...new Set([R[2], R[3], ...H.flatMap(h => [h[2], h[3]])])].sort((a, b) => a - b);
  const vnitr = (x, y) => H.some(h => x > h[0] && x < h[1] && y > h[2] && y < h[3]);
  const out = [];
  for (let j = 0; j < ys.length - 1; j++) {
    let start = null;
    for (let i = 0; i <= xs.length - 1; i++) {
      const full = i < xs.length - 1 && !vnitr((xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2);
      if (full && start === null) start = i;
      if (!full && start !== null) { out.push([xs[start], xs[i], ys[j], ys[j + 1]]); start = null; }
    }
  }
  return out;
}

// ---------- drát po cestě se zaoblenými rohy ----------
// pts = [[x,y,z],...] – lomená čára, r = poloměr rohu; vrací hustší cestu pro tube()
export function zaoblenaCesta(pts, r, kroku = 5) {
  const out = [pts[0]];
  const sub = (a, b) => a.map((v, i) => v - b[i]), add = (a, b) => a.map((v, i) => v + b[i]), mul = (a, k) => a.map(v => v * k);
  const len = a => Math.hypot(...a), nrm = a => mul(a, 1 / (len(a) || 1));
  for (let i = 1; i < pts.length - 1; i++) {
    const a = pts[i - 1], b = pts[i], c = pts[i + 1];
    const u = nrm(sub(a, b)), v = nrm(sub(c, b));
    const ang = Math.acos(Math.max(-1, Math.min(1, u[0] * v[0] + u[1] * v[1] + u[2] * v[2])));
    const rr = Array.isArray(r) ? r[i - 1] : r;
    let d = rr / Math.tan(ang / 2); d = Math.min(d, len(sub(a, b)) * 0.5, len(sub(c, b)) * 0.5);
    const p0 = add(b, mul(u, d)), p1 = add(b, mul(v, d));
    for (let k = 0; k <= kroku; k++) { const t = k / kroku; const q = add(add(mul(p0, (1 - t) * (1 - t)), mul(b, 2 * t * (1 - t))), mul(p1, t * t)); out.push(q); }
  }
  out.push(pts[pts.length - 1]);
  return out;
}

// čtyři rohy: [sx, sy] pro sx,sy ∈ {-1,+1}
export const ROHY = [[1, 1], [1, -1], [-1, 1], [-1, -1]];
