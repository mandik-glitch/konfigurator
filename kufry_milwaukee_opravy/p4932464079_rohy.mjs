// Rohové sestavy PACKOUT: dolní a horní černá krytka + hliníková tyč (stojí v rohovém výřezu vany, mezi tyčí a stěnou je "chytací okno").
import { Group, bx, slab, loftSolid, roundPoly, ccw, polyInset, cylX, cylY, zc } from './p4932464079_zaklad.mjs';

// obrys krytky v půdoryse (CCW), roh (+X,+Y); vnější (zkosený) roh má větší sražení
function capPoly(V, ins = 0) {
  const x0 = V.xN, x1 = V.X - 0.5, y0 = V.yN, y1 = V.Y - 0.5;
  const P = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  // rozšířená krytka: zkosení vnějšího rohu 12, ostatní 5
  return polyInset(roundPoly(P, [5, 9, 12, 5], 2), ins);
}
function rohJeden(V) {
  const L = [];
  const zs = V.H - V.lidH + V.capUp;                         // horní hrana krytky (zasahuje do rohového výřezu víka)
  const zT0 = zs - V.capT, zB1 = V.capB;
  // horní krytka: těleso od zT0 po zs; hrany zaoblené (zúžení dole)
  const mk = (ins, z) => ({ poly: ccw(capPoly(V, ins)), z });
  L.push(loftSolid('cerna', 'krytka_horni', [mk(4, zT0), mk(1.2, zT0 + 4), mk(0, zT0 + 10), mk(0, zs - 6), mk(0.8, zs)], { crease: 38 }));
  // dolní krytka: od 0 po capB
  L.push(loftSolid('cerna', 'krytka_dolni', [mk(5, 0), mk(1.5, 4), mk(0, 10), mk(0, zB1 - 5), mk(2.5, zB1)], { crease: 38 }));
  // tyč: čtvercový profil 29 s ostrými hranami zkosenými; okraj leží u vnějšího rohu
  const b = V.bar, x1 = V.X - 0.5, y1 = V.Y - 0.5;
  L.push(slab('ocel', 'tyc_hlinik', { x0: x1 - V.barX, x1, y0: y1 - b, y1, z0: zB1 - 2, z1: zT0 + 2, rs: 3, seg: 2, reT: 0.2, reB: 0.2, fs: 1 }));
  // tmavé drážky (3 podélná žebra) na čelní a boční ploše tyče: tenké pásky
  for (const k of [0.33, 0.66]) {
    L.push(slab('seda', 'tyc_zebro_x', { x0: x1 - 0.3, x1: x1 + 0.2, y0: y1 - b + b * k - 0.6, y1: y1 - b + b * k + 0.6, z0: zB1, z1: zT0, rs: 0.1, seg: 1 }));
    L.push(slab('seda', 'tyc_zebro_y', { x0: x1 - V.barX + V.barX * k - 0.6, x1: x1 - V.barX + V.barX * k + 0.6, y0: y1 - 0.3, y1: y1 + 0.2, z0: zB1, z1: zT0, rs: 0.1, seg: 1 }));
  }
  // šrouby: boční plocha dolní krytky (+Y) a horní krytky (+Y), čelní plocha (+X) dolní krytky
  L.push(cylY('ocel', 'sroub_dolni_y', 4.6, y1 - 1.2, y1 + 0.1, x1 - 20, zB1 * 0.55, 18));
  L.push(cylY('ocel', 'sroub_horni_y', 4.0, y1 - 1.0, y1 + 0.1, x1 - 22, zT0 + V.capT * 0.5, 18));
  L.push(cylX('ocel', 'sroub_dolni_x', 4.2, x1 - 1.2, x1 + 0.1, y1 - 24, zB1 * 0.55, 18));
  L.push(cylX('cerna_mat', 'sroub_horni_x', 5.5, x1 - 1.0, x1 + 0.1, y1 - 24, zT0 + V.capT * 0.5, 18));
  return L;
}
export function rohy(V) {
  const g = new Group('rohy');
  const base = rohJeden(V);
  for (const sx of [1, -1]) for (const sy of [1, -1]) {
    for (const p of base) {
      const q = p.clone(p.name + (sx > 0 ? '_p' : '_z') + (sy > 0 ? 'P' : 'L'));
      if (sx < 0) q.mirror('x', 0);
      if (sy < 0) q.mirror('y', 0);
      g.add(q);
    }
  }
  return g;
}
