// Milwaukee PACKOUT Skříň s předními dvířky 4932480623 – tělo: nožky + jazýčky, spodní lišta, dutá skříň (dno 50 mm, boční kolejnice, práh), rám před dvířky.
// Souřadnice: X = hloubka 381 (čelo s dvířky do +X), Y = šířka 508, z' = výška od země 0..381; počátek = střed obálky.
import { kit, rrPoly, planPoly, octPoly, Group, textWidth } from './p4932471723_zaklad.mjs';
export const V = 381, k = kit(V);
export const LX = 190.5, LY = 254;           // lem víka (obálka)
export const BX = 182.5, BY = 249.5;         // korpus: čelní plocha rámu a půlšířka nahoře (dole 246: zužuje se dolů – změřeno na c02: 246,2 mm ve z' 45, 249,5 mm ve z' 310)
export const OPEN_Y = 218, Z_DNO = 50, Z_STROP = 338, Z_VICKO = 322;
export const XB = -168;                      // vnitřní plocha zadní stěny

// obrys korpusu (půdorys XY) otevřený do dutiny směrem dopředu: C-polygon (stěny + zadní stěna), vyříznutá dutina Y ±OPEN_Y, X od XB dopředu
export function cPoly(x0, x1, y0, y1, r, xb, oy) {
  const P = rrPoly(x0, x1, y0, y1, r, 3);   // 1. souřadnice = X
  // poslední bod = konec oblouku (+X,-Y) → přidáme výřez dutiny, první bod = začátek oblouku (+X,+Y)
  P.push([x1, -oy], [xb, -oy], [xb, oy], [x1, oy]);
  return P;
}

export function telo() {
  const g = new Group('telo');
  // --- nožky: Y ±(132–190), podél X −150…+120 (podle c02: nožky ve čtvrtinách šířky) ---
  for (const sy of [-1, 1]) g.add(k.blok('cerna', 'nozka', { x0: -140, x1: 128, y0: sy > 0 ? 106 : -158, y1: sy > 0 ? 158 : -106, z0: 0, z1: 9, r: 8, cB: 2.5 }));
  // --- jazýčky pod dvířky (3×, červené; střední větší) ---
  g.add(k.bx('cervena', 'jazycek-stred', 168, 187.5, -21.5, 22.5, 2, 22));
  g.add(k.bx('cervena', 'jazycek-bok-1', 138, 160, -139, -117, 3, 14));      // podle c01: dva menší jazýčky vlevo pod předním lemem, ze zepředu (c02) skryté
  g.add(k.bx('cervena', 'jazycek-bok-2', 128, 150, -72, -50, 3, 14));
  // přední sukně pod přírubou (zakrývá boční jazýčky zepředu; střed s výřezem pro střední jazýček)
  for (const [a, b] of [[-150, -26], [27, 150]]) g.add(k.bx('cerna', 'sukne', 172, 181.5, a, b, 3, 13));
  // --- spodní lišta (příruba) z' 12–30 ---
  g.add(k.blok('cerna', 'priruba', { x0: -BX + 3, x1: BX - 1, y0: -BY + 6, y1: BY - 6, z0: 8, z1: 31, r: 20, cT: 2, cB: 2 }));
  // --- dno dutiny (z' 30–50) ---
  g.add(k.blok('cerna', 'dno', { x0: -BX, x1: BX, y0: -BY + 3.4, y1: BY - 3.4, z0: 30, z1: Z_DNO, r: 16 }));
  // --- stěny + zadní stěna (C-polygon, otevřeno dopředu), z' 50–322; svislé stěny se k vrchu mírně zužují ---
  const wallLayers = [];
  for (const [z, d] of [[Z_DNO, 3.5], [200, 1.5], [Z_VICKO + 0.5, 0]]) wallLayers.push({ z, pts: cPoly(-BX + d * 0.4, BX - d * 0.3, -BY + d, BY - d, 16, XB, OPEN_Y) });
  g.add(k.sloupec('cerna', 'korpus-steny', wallLayers, { capB: true, capT: true }));
  // --- rám před dvířky (čelní plocha stěn: 5 mm sloupky kolem otvoru) ---
  g.add(k.extYZ('cerna', 'celni-ram', [[-BY + 3.2, 30], [BY - 3.2, 30], [BY - 0.5, Z_STROP], [OPEN_Y, Z_STROP], [OPEN_Y, Z_DNO - 2], [-OPEN_Y, Z_DNO - 2], [-OPEN_Y, Z_STROP], [-BY + 0.5, Z_STROP]], BX - 3, BX));
  // --- vnitřek: boční svislé kolejnice se zářezy, práh s dorazem, zadní stěna s prolisem, kruhový otvor v podlaze ---
  for (const sy of [-1, 1]) {
    g.add(k.bx('cerna', 'kolejnice', XB, BX - 8, sy > 0 ? OPEN_Y - 11 : -OPEN_Y, sy > 0 ? OPEN_Y : -OPEN_Y + 11, Z_DNO, Z_STROP - 6));
    for (let i = 0; i < 6; i++) g.add(k.bx('cerna_mat', 'kolejnice-zarez', XB + 20 + i * 48, XB + 36 + i * 48, sy > 0 ? OPEN_Y - 12 : -OPEN_Y - 0.1, sy > 0 ? OPEN_Y + 0.1 : -OPEN_Y + 12, 70, 296));
  }
  g.add(k.bx('cerna', 'prah', BX - 24, BX - 3, -OPEN_Y + 11, OPEN_Y - 11, Z_DNO, Z_DNO + 7));
  g.add(k.bx('cerna_mat', 'prah-doraz', BX - 20, BX - 5, -24, 24, Z_DNO + 7, Z_DNO + 15));
  g.add(k.bx('cerna', 'zadni-prolis', XB, XB + 5, -150, 150, 90, 300));
  g.add(k.bx('cerna', 'zadni-pas', XB, XB + 7, -OPEN_Y + 11, OPEN_Y - 11, 285, 318));
  g.add(k.cylZ('cerna_mat', 'podlaha-otvor', 6, Z_DNO, Z_DNO + 0.8, 120, -130, 16));
  return g;
}
