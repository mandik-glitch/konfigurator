// Milwaukee PACKOUT Otevřená přepravka 4932471724 – tělo: spodní příruba s nožkami, stěny zapuštěné mezi žebry (≈12 mm od obálky), 6 vodorovných žeber + horní lem s ozubením, svislé sloupky, ruční otvor v -Y stěně.
// X = šířka 389 (dlouhé stěny ±X; čelo s logem a sedlem spojky do +X), Y = délka 475, z' = výška od země 0..251; počátek = střed obálky.
import { kit, rrPoly, Group } from './p4932471723_zaklad.mjs';
export const V = 251, k = kit(V);
export const HX = 194.5, HY = 237.5;
export const ZAP = 12;                       // zapuštění stěn od obálky (kontrola: 12–14 mm na stranu)
export const T = 6;                          // tloušťka stěny (odhad)
export const Z_PODL = 30, Z_LEM0 = 226, Z_TOP = 251;
export const CX = HX - ZAP, CY = HY - ZAP;   // vnější plocha jádra stěn

export function telo() {
  const g = new Group('telo');
  const cx = CX, cy = CY;
  // --- nožky (≈ 14 mm pod přírubou): 4 rohové + 2 středové ---
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) g.add(k.blok('cerna', 'nozka', { x0: sx * 150 - 30, x1: sx * 150 + 30, y0: sy * 195 - 24, y1: sy * 195 + 24, z0: 0, z1: 7, r: 8, cB: 2.5 }));
  for (const sx of [-1, 1]) g.add(k.blok('cerna', 'nozka-stred', { x0: sx * 150 - 30, x1: sx * 150 + 30, y0: -22, y1: 22, z0: 0, z1: 7, r: 8, cB: 2.5 }));
  // --- spodní příruba (široká, zaoblené rohy) z' 14–30 ---
  g.add(k.blok('cerna', 'priruba', { x0: -HX + 3.5, x1: HX - 3.5, y0: -HY + 3.5, y1: HY - 3.5, z0: 6, z1: Z_PODL, r: 26, cT: 4, cB: 3 }));
  // --- jádro: dno + 4 stěny, nahoře otevřené ---
  g.add(k.bx('cerna', 'dno', -cx + 1, cx - 1, -cy + 1, cy - 1, Z_PODL, Z_PODL + 8));
  for (const s of [-1, 1]) g.add(k.bx('cerna', 'stena-dlouha', s > 0 ? cx - T : -cx, s > 0 ? cx : -cx + T, -cy, cy, Z_PODL, Z_LEM0 + 4));
  g.add(k.bx('cerna', 'stena-konec-+Y', -cx, cx, cy - T, cy, Z_PODL, Z_LEM0 + 4));
  // -Y konec: plná zadní stěna BEZ otvoru je zde jen nad/pod ručním otvorem; ruční otvor je průchozí (levá stěna na fotce): X ±78, z' 186–216
  g.add(k.extXZh('cerna', 'stena-konec--Y', [[-cx, Z_PODL], [cx, Z_PODL], [cx, Z_LEM0 + 4], [-cx, Z_LEM0 + 4]], [[[-78, 186], [78, 186], [78, 216], [-78, 216]]], -cy, -cy + T));
  // --- vodorovná žebra (6 úrovní) jako úseky na stěnách: střed dlouhé stěny (Y ±88, z' 100–200) zůstává hladký (panel s logem a sedlem) ---
  const ZEBRA = [[38, 45], [62, 69], [98, 105], [132, 139], [166, 173], [196, 203]], R = 24, PX = HX - 1.5, PY = HY - 5.5;
  for (const [z0, z1] of ZEBRA) {
    const stred = z0 > 90 && z1 < 210;
    for (const sx of [-1, 1]) {
      const segs = stred ? [[-(HY - R), -88], [88, HY - R]] : [[-(HY - R), HY - R]];
      for (const [ya, yb] of segs) g.add(k.bx('cerna', 'zebro-bok', sx > 0 ? cx - 1.5 : -PX, sx > 0 ? PX : -cx + 1.5, ya, yb, z0, z1));
    }
    for (const sy of [-1, 1]) g.add(k.bx('cerna', 'zebro-konec', -(HX - R), HX - R, sy > 0 ? cy - 1.5 : -PY, sy > 0 ? PY : -cy + 1.5, z0, z1));
  }
  // --- svislé sloupky: rohové (zaoblené) + hrany středového panelu na dlouhých stěnách + dva na koncích ---
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) {
    g.add(k.rb('cerna', 'sloupek-roh', { x0: sx > 0 ? HX - 24 : -HX + 1, x1: sx > 0 ? HX - 1 : -HX + 24, y0: sy > 0 ? HY - 29 : -HY + 5.5, y1: sy > 0 ? HY - 5.5 : -HY + 29, z0: Z_PODL, z1: Z_LEM0 + 2, rc: 22, re: 1.5 }));
  }
  for (const sx of [-1, 1]) for (const y of [-205, 205]) g.add(k.bx('cerna', 'sloupek-bok', sx > 0 ? cx - 1 : -PX, sx > 0 ? PX : -cx + 1, y - 5, y + 5, Z_PODL + 6, Z_LEM0));
  for (const sy of [-1, 1]) for (const x of [-120, 120]) g.add(k.bx('cerna', 'sloupek-konec', x - 5, x + 5, sy > 0 ? cy - 1 : -PY, sy > 0 ? PY : -cy + 1, Z_PODL + 6, Z_LEM0));
  // --- horní lem (stupňovitý, ozubený): prstenec z' 226–244 na obálce + zuby do 251 ---
  g.add(k.slab('cerna', 'lem', rrPoly(-HX, HX, -HY, HY, 22, 3), [rrPoly(-cx + T, cx - T, -cy + T, cy - T, 10, 3)], Z_LEM0, 244));
  g.add(k.slab('cerna', 'lem-stupen', rrPoly(-HX + 5, HX - 5, -HY + 5, HY - 5, 20, 3), [rrPoly(-cx + T, cx - T, -cy + T, cy - T, 10, 3)], 244, 248));
  for (const sx of [-1, 1]) for (const y of [-205, -160, -105, -35, 35, 105, 160, 205]) g.add(k.bx('cerna', 'lem-zub', sx > 0 ? HX - 17 : -HX + 5, sx > 0 ? HX - 5 : -HX + 17, y - 9, y + 9, 248, Z_TOP));
  for (const sy of [-1, 1]) for (const x of [-120, -60, 0, 60, 120]) g.add(k.bx('cerna', 'lem-zub-konec', x - 9, x + 9, sy > 0 ? HY - 17 : -HY + 5, sy > 0 ? HY - 5 : -HY + 17, 248, Z_TOP));
  return g;
}
