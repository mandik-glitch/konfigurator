// Spodní díl (korpus) DeWalt TSTAK IP54: dutá vana + čelní panely, kapsa (výřez pro prsty/stohování) vpředu, boční kapsy pro stohovací háky, západky.
// Souřadnice: X = hloubka (čelo +X), Y = délka, z' = výška od spodní plochy. Výška korpusu = H − LID_H (spára víko/korpus zs).
// Všechny rozměry jsou odhady z čelní fotografie c02 (měřítko 440 mm = šířka víka, elevace ≈ 9,5°) – viz zdroje/*_poznamky.md.
import { Group, S, zs, zf, plne, vana, bx, rb, extXZ, extYZ, vyrez, mirY, Part } from './tstak_zaklad.mjs';

export const K = {
  yB: 212.5,            // polovina šířky korpusu (c02: 2340 px / 5,507 px/mm = 424,9 mm)
  xR: -158, xHull: 140, // zadní stěna korpusu; čelo „holé“ vany (dno kapsy)
  xCol: 157, xZona: 155, xPanel: 161,   // čelní plochy: vnější sloupky, zóny západek, střední panel
  yCol: 171, yPanel: 108,               // hranice sloupek | zóna západky (y=171), zóna | střední panel (y=108)
  yPk: 93, zPk: 85,                     // kapsa vpředu: polovina šířky, výška (z' 0..85)
  latY0: 113, latY1: 167,               // západka: y rozsah (absolutní hodnoty)
};

export function korpus({ celoMadlo = false } = {}) {
  const g = new Group('korpus');
  const Z = zs(), t = { ...K, xR: S.rearBody + S.trim };
  // --- vana (hrubý tvar; čelo je odsazené na xHull, panely se přidávají zvlášť) ---
  const FR = [
    { z: 0, xr: t.xR + 8, xf: t.xHull - 4, y: t.yB - 7, rc: 7 },
    { z: 8, xr: t.xR, xf: t.xHull, y: t.yB, rc: 9 },
    { z: Z, xr: t.xR, xf: t.xHull, y: t.yB, rc: 9 },
  ];
  g.add(vana('cerna', 'korpus_vana', FR, { wall: 4, floorZ: 4 }));
  // --- čelní panely: sloupky (vnější), zóny západek (zapuštěné), střední panel s kapsou ---
  for (const s of [1, -1]) {
    const m = (a, b) => s > 0 ? [a, b] : [-b, -a];
    const [c0, c1] = m(t.yCol, t.yB - 0.4), [z0, z1] = m(t.yPanel, t.yCol);
    g.add(rb('cerna', 'celo_sloupek' + (s > 0 ? '_p' : '_l'), { x0: t.xHull - 8, x1: t.xCol, y0: c0, y1: c1, z0: 6, z1: Z, rc: 2, re: 1.2, seg: 1, fs: 1 }));
    g.add(rb('cerna', 'celo_zona' + (s > 0 ? '_p' : '_l'), { x0: t.xHull - 8, x1: t.xZona, y0: z0, y1: z1, z0: 3, z1: Z, rc: 1, re: 0.8, seg: 1, fs: 1 }));
  }
  // střední panel: nad kapsou a po stranách kapsy
  g.add(rb('cerna', 'celo_panel_horni', { x0: t.xHull - 8, x1: t.xPanel, y0: -t.yPanel, y1: t.yPanel, z0: t.zPk, z1: Z, rc: 1, re: 1, seg: 1, fs: 1 }));
  g.add(rb('cerna', 'celo_panel_levy', { x0: t.xHull - 8, x1: t.xPanel, y0: -t.yPanel, y1: -t.yPk, z0: 3, z1: t.zPk + 1, rc: 1, re: 0.8, seg: 1, fs: 1 }));
  g.add(rb('cerna', 'celo_panel_pravy', { x0: t.xHull - 8, x1: t.xPanel, y0: t.yPk, y1: t.yPanel, z0: 3, z1: t.zPk + 1, rc: 1, re: 0.8, seg: 1, fs: 1 }));
  // spodní lišta pod kapsou (patka panelu) – vyplní dno kapsy, aby kapsa neměla průhled
  g.add(bx('cerna', 'kapsa_dno', t.xHull - 2, t.xHull + 6, -t.yPk, t.yPk, 0, 4));
  // jazyk (zesílení) uprostřed horní hrany kapsy: čelní fotografie ukazuje lichoběžník y ±44 sestupující o ~10 mm
  g.add(extYZ('cerna', 'kapsa_jazyk', [[-48, t.zPk + 1], [48, t.zPk + 1], [38, t.zPk - 9], [-38, t.zPk - 9]], t.xHull - 2, t.xPanel - 0.4));
  // svislé drážky ve středním panelu (c01: dvě svislé hrany ~ y ±40, hloubka neověřena)
  for (const y of [-42, 42]) g.add(bx('cerna_mat', 'celo_drazka', t.xPanel - 0.1, t.xPanel + 0.35, y - 1, y + 1, t.zPk + 12, Z - 8));
  // --- boční kapsy pro stohovací háky (c01 pravý konec): rámeček + tmavá vložka; kapsa je jen naznačena (nevyříznuta), vpředu u dna otevřená ---
  {
    const xa = -54, xb = 92, zb = 68, y0 = t.yB - 0.3;
    const parts = [[xa, xb, zb - 3.5, zb, 'h'], [xa, xa + 3.5, 0, zb, 'r'], [xb - 3.5, xb, 0, zb, 'f']].map(([a, b, c, e, n]) => bx('cerna', 'bok_ramecek_' + n + '_p', a, b, y0, y0 + 1.9, c, e));
    parts.push(bx('cerna_mat', 'bok_kapsa_p', xa + 3.5, xb - 3.5, y0, y0 + 0.9, 0, zb - 3.5));
    for (const x of [138, -117]) parts.push(bx('cerna_mat', 'bok_drazka_' + x + '_p', x - 1.5, x + 1.5, y0, y0 + 0.5, 6, Z - 6));
    for (const p of parts) { g.add(p); g.add(mirY(p, p.name.replace(/_p$/, '_l'))); }
  }
  // --- mělký kufr: v kapse sklopné čelní madlo (c01/c02 DWST83345: dva držáky + válcová hmatnice), jen pevný díl ---
  if (celoMadlo) {
    for (const s of [-1, 1]) g.add(rb('cerna', 'madlo_drzak' + (s < 0 ? '_l' : '_p'), { x0: t.xHull + 0.5, x1: t.xHull + 13, y0: s < 0 ? -t.yPk + 0.5 : 70, y1: s < 0 ? -70 : t.yPk - 0.5, z0: 6, z1: t.zPk - 6, rc: 1.5, re: 1, seg: 1, fs: 1 }));
    g.add(rb('cerna_mat', 'madlo_hmatnice', { x0: t.xHull + 0.5, x1: t.xHull + 16, y0: -72, y1: 72, z0: 7, z1: 30, rc: 6, re: 4, seg: 2, fs: 2 }));
  }
  // --- západky (pozinkovaný plech): profil v rovině XZ, 3 vylisovaná žebra ---
  const Zf = zf(), zl0 = Zf - 49, zl1 = Zf + 20;
  const prof = [[156.6, zl0], [158.8, zl0], [158.8, Zf - 8], [165.7, Zf + 4], [165.7, zl1], [163.5, zl1], [163.5, Zf + 6], [156.6, Zf - 6]];
  for (const s of [-1, 1]) {
    const y0 = s > 0 ? K.latY0 : -K.latY1, y1 = s > 0 ? K.latY1 : -K.latY0, nm = s > 0 ? '_p' : '_l';
    g.add(extXZ('pozink', 'zamek' + nm, prof, y0, y1, { crease: 20 }));
    const yc = (y0 + y1) / 2;
    [Zf + 1, Zf - 11, Zf - 23].forEach((zr, i) => g.add(rb('pozink', 'zamek_zebro' + i + nm, { x0: 165.3, x1: 166.5, y0: yc - 13, y1: yc + 13, z0: zr - 2.6, z1: zr + 2.6, rc: 2.4, re: 0.5, seg: 2, fs: 1 })));
  }
  return g;
}
