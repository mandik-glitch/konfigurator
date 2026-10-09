// Nádoby (10 ks, červené, vlastní dno) 4932471064 + děliče. Stojí na podlaze vany; horní okraj (lem) nad švíkem víka.
// Obrys nádoby = obrys kapsy víka zvětšený o 5,5 mm (kapsa zapadá do otvoru nádoby), viz zdroje/4932471064_poznamky.md.
import { Group, Part, trayT, rrFrame, bx, ccw, ext, zc, polyInset, rrPoly, slab } from './p1064_zaklad.mjs';
import { H, X, seznam } from './p1064_data.mjs';
import { kapsaLoops } from './p1064_kapsy.mjs';

export const NB = { out: 5.5, wall: 1.8, floor: 2.0, taper: 2.2, lem: 2.4, lemW: 4.5, rc: 7 };

export function seznamNadob() {
  return seznam().map(n => {
    const k = kapsaLoops(n); let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
    for (const [a, b] of k.rim) { x0 = Math.min(x0, a); x1 = Math.max(x1, a); y0 = Math.min(y0, b); y1 = Math.max(y1, b); }
    return { ...n, x0: X(x0 - NB.out), x1: X(x1 + NB.out), y0: y0 - NB.out, y1: y1 + NB.out };
  });
}

export function nadoby() {
  const g = new Group('nadoby');
  for (const n of seznamNadob()) {
    g.add(trayT('cervena', 'nadoba', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: H.zFloor, z1: H.zBin, rs: NB.rc, seg: 3, wall: NB.wall, floor: NB.floor, re: 1.8, fs: 2, taper: NB.taper }));
    g.add(rrFrame('cervena', 'nadoba_lem', { x0: n.x0, x1: n.x1, y0: n.y0, y1: n.y1, z0: H.zBin - NB.lem, z1: H.zBin, w: NB.lemW, rs: NB.rc, seg: 3 }));
  }
  return g;
}
