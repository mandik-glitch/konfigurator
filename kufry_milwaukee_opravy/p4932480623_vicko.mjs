// 4932480623 – víko: plášť ≈ 58 mm (z' 322–381) přesahující tělo o 5–13 mm, zkosené rohy (30 mm), horní deska se 10 kapsami (4+2+4, reliéf dovnitř), středový pruh se západkou a kulatým otvorem, ozubený úchyt na čele, boční "uši".
import { rrPoly, octPoly, planPoly, Group } from './p4932471723_zaklad.mjs';
import { k, LX, LY, Z_VICKO, Z_STROP, OPEN_Y, XB } from './p4932480623_telo.mjs';

export const Z_HORNI = 381, Z_DNO_KAPS = 366;
const C = 30;                       // zkosení rohů půdorysu
export function vicko() {
  const g = new Group('vicko');
  // plášť (skirt) – spodní stupeň z' 322–353 (Y ±252, X ±190,5): v pásu 322–338 otevřený dopředu nad dutinou (dvířka zde zajíždějí pod víko)
  const oct = (x0, x1, y0, y1, c) => octPoly(x0, x1, y0, y1, c);
  const SY = 252;                                   // půlšířka pláště v Y (c02: 251–253 mm); "uši" jdou až na 254
  const P = oct(-LX, LX, -SY, SY, C);
  const front = [[LX, -OPEN_Y - 4], [LX - 14, -OPEN_Y - 4], [XB, -OPEN_Y - 4], [XB, OPEN_Y + 4], [LX - 14, OPEN_Y + 4], [LX, OPEN_Y + 4]];
  const pasA = [P[0], P[1], P[2], front[0], front[1], front[2], front[3], front[4], front[5], P[3], P[4], P[5], P[6], P[7]];
  g.add(k.sloupec('cerna', 'vicko-pas', [{ z: Z_VICKO, pts: pasA }, { z: Z_STROP, pts: pasA }]));
  g.add(k.sloupec('cerna', 'vicko-plast', [{ z: Z_STROP, pts: P }, { z: 351, pts: P }, { z: 353.5, pts: oct(-LX + 3, LX - 3, -SY + 3, SY - 3, C - 2) }]));
  // horní stupeň z' 353,5–381: inset 8 mm (c02: šířka klesá z 252 na ≈ 244 mm), horní hrana zkosená
  const up = d => oct(-LX + d, LX - d, -SY + d, SY - d, Math.max(C - d * 0.5, 6));
  g.add(k.sloupec('cerna', 'vicko-horni', [{ z: 353.5, pts: up(7.5) }, { z: 372, pts: up(8.5) }, { z: Z_DNO_KAPS, pts: up(11) }]));
  // horní deska s otvory (kapsy), z' 366–381
  const outer = up(11), RR = 6, pk = (x0, x1, y0, y1) => rrPoly(x0, x1, y0, y1, RR, 2);
  const holes = [];
  const rows = { zadni: [-166, -90], stredni: [-79, -2], predni: [10, 116] };
  const cols = [[38, 134], [142, 228]];     // sloupce v Y (vnitřní, vnější) pro polovinu Y>0
  for (const s of [-1, 1]) {
    for (const [a, b] of cols) { for (const key of ['zadni', 'predni']) { const [x0, x1] = rows[key]; holes.push(s > 0 ? pk(x0, x1, a, b) : pk(x0, x1, -b, -a)); } }
    const [x0, x1] = rows.stredni; holes.push(s > 0 ? pk(x0, x1, 38, 228) : pk(x0, x1, -228, -38));
  }
  // středový pruh (|Y| < 32) podél X
  holes.push([[-170, -30], [170, -30], [170, 30], [-170, 30]]);
  g.add(k.slab('cerna', 'vicko-deska', outer, holes, Z_DNO_KAPS, Z_HORNI));
  // červený štítek (logo) v pravé střední kapse + červená západka a kulatý otvor v pruhu
  g.add(k.bx('cervena', 'vicko-stitek', -62, -22, 120, 190, Z_DNO_KAPS, Z_DNO_KAPS + 1.2));
  g.add(k.rb('cervena', 'zapadka', { x0: -10, x1: 46, y0: -21, y1: 21, z0: Z_DNO_KAPS, z1: Z_DNO_KAPS + 9, rc: 3, re: 1.5 }));
  g.add(k.cylZ('cervena', 'kulaty-otvor', 17, Z_DNO_KAPS, Z_DNO_KAPS + 7, 84, 0, 24));
  g.add(k.cylZ('cerna_mat', 'kulaty-otvor-dira', 10, Z_DNO_KAPS + 6.9, Z_DNO_KAPS + 7.3, 84, 0, 20));
  g.add(k.cylZ('cerna_mat', 'znacka-zadni', 11, Z_DNO_KAPS, Z_DNO_KAPS + 1.5, -166, 0, 20));
  // ozubený úchyt na čele víka (ribbing)
  for (let i = 0; i < 14; i++) g.add(k.bx('cerna_mat', 'vicko-vroubek', LX - 2.2, LX - 0.2, -50 + i * 7.5, -50 + i * 7.5 + 3.5, 345, 358));
  // boční "uši" na koncích víka (Y = ±254), z' 322–336
  for (const s of [-1, 1]) g.add(k.bx('cerna', 'vicko-usi', LX - 34, LX - 4, s > 0 ? SY - 2 : -LY, s > 0 ? LY : -SY + 2, Z_VICKO - 6, Z_VICKO + 10));
  return g;
}
