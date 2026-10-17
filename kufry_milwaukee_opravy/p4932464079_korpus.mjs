// Spodní díl (vana) s rohovými výřezy, prolisy a stěnami. Vana je dutá (stěna 5 mm, dno 6 mm), nahoře otevřená pod víkem.
import { Group, Part, rrPoly, loftRings, loftSolid, roundPoly, ccw, polyInset, dutyLoft, bx, slab, extYZ, extXZ, cylX, cylY, zc } from './p4932464079_zaklad.mjs';

export function tubPoly(V) {
  const { xF, xR, yB, xN, yN } = V;
  if (V.rohy === false) return ccw(rrPoly(xR, xF, -yB, yB, V.rTub ?? 34, 5));
  const pts = [[xF, -yN], [xF, yN], [xN, yN], [xN, yB], [-xN, yB], [-xN, yN], [xR, yN], [xR, -yN], [-xN, -yN], [-xN, -yB], [xN, -yB], [xN, -yN]];
  return ccw(roundPoly(pts, [8, 8, 10, 8, 8, 10, 8, 8, 10, 8, 8, 10], 3));
}
export function vana(V) {
  const g = new Group('korpus');
  const zs = V.H - V.lidH, P = tubPoly(V);
  const L = (d, z) => ({ poly: polyInset(P, d), z });
  g.add(dutyLoft('cerna', 'vana', [L(9, 0), L(4.5, 3), L(1.8, 7), L(0.6, 16), L(0, zs - 6), L(0, zs)], { wall: 5, floorZ: 7, ri: 3 }));
  // okraj vany (lem pod víkem): vnitřní římsa 11 mm široká, 8 mm vysoká
  { const Pi = polyInset(P, 11), rim = new Part('vana_lem', 'cerna'); rim.crease = 38;
    const R = (poly, z) => poly.map(q => [q[0], q[1], zc(z)]);
    loftRings(rim, [R(polyInset(P, 4.2), zs - 9), R(polyInset(P, 4.2), zs - 0.2), R(Pi, zs - 0.2), R(Pi, zs - 9)], { closed: true }); g.add(rim); }
  if (V.rohy !== false) {
    // koncové stěny: řada svislých žeber pod uchem víka a svislé výlisky
    for (const s of [-1, 1]) {
      for (let i = 0; i < 12; i++) g.add(bx('cerna_mat', 'zebro_konec', -8 + i * 9.5, -8 + i * 9.5 + 4, s > 0 ? V.yB - 0.5 : -V.yB - 3.2, s > 0 ? V.yB + 3.2 : -V.yB + 0.5, zs - 24, zs - 3));
      g.add(bx('cerna', 'konec_vylis', -148, 148, s > 0 ? V.yB - 0.5 : -V.yB - 2.4, s > 0 ? V.yB + 2.4 : -V.yB + 0.5, 22, zs - 28));
    }
  }
  // pant: oka na vaně (střídají se s oky víka) a ocelový čep
  const zp = zs + V.pantZ_off;
  for (const yc of [-142, -47, 47, 142]) g.add(cylY('cerna', 'pant_oko_vana', 7.2, yc - 17, yc + 17, V.pantX, zp, 20));
  for (const yc of [-142, -47, 47, 142]) g.add(bx('cerna', 'pant_podpera', V.pantX - 7, V.xR + 3, yc - 17, yc + 17, zs - 12, zp));
  g.add(cylY('ocel', 'pant_cep', 2.8, -206, 206, V.pantX, zp, 12));
  return g;
}
