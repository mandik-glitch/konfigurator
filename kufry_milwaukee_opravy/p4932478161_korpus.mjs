// 4932478161 – Pojízdná bedna na nářadí: spodní díl (vana), čelo, koncový blok u kol, spodní patky, konec s madlem.
// Souřadnice: X = šířka 609 (čelo se západkami +X, pant vzadu -X), Y = délka 965 (konec s madlem -Y, kola +Y), Z = výška 401; počátek = střed obálky.
// Výšky v kódu jsou z' = výška nad podlahou (0 = spodek kol, 401 = horní hrana víka); převod z = z' - 200.5.
import { napis, blesk, Part, Group, box, tube, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid, loftSolid, lathe } from './p4932464078_zaklad.mjs';
export const ZC = 200.5;
export const zc = z => z - ZC;
export const D = {
  xf: 296, xr: -296,           // čelní / zadní stěna vany
  yL: -462, yR: 424,           // konce vany (u madla / u kol)
  zDno: 38, zSeva: 305,        // spodek vany, švík víko/vana
  zTop: 401,                   // horní okraj víka
};
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));

// půdorys vany: obdélník se zaoblenými rohy; v oblasti kol (Y > yK) je spodní část užší (kola stojí po stranách)
function planVana(yL, yR, hx, r = 22, hxn = null, yN = 336) {
  if (hxn === null) return rrPoly(-hx, hx, yL, yR, [r, r, r, r], 4);
  const P = [[hx, yL], [hx, yN], [hxn, yN], [hxn, yR], [-hxn, yR], [-hxn, yN], [-hx, yN], [-hx, yL]];   // výřez pro kola (u konce +Y je spodní část užší)
  return roundPoly(P, [r, 4, 4, r, r, 4, 4, r], 3);
}

export function korpus() {
  const g = new Group('korpus');
  // ---- vana: vnější plášť + vnitřní dutina (hladká, zjednodušená) ----
  const rings = [], add = (poly, z) => rings.push({ poly, z: zc(z) });
  const HN = 206;                                            // poloviční šířka spodní části u kol (kola ±216…304,5 stojí vně)
  add(planVana(D.yL + 14, D.yR - 12, D.xf - 14, 16, HN - 14), D.zDno);
  add(planVana(D.yL + 6, D.yR - 5, D.xf - 5, 20, HN - 5), D.zDno + 8);
  add(planVana(D.yL, D.yR, D.xf, 24, HN), D.zDno + 20);
  add(planVana(D.yL - 2, D.yR + 1, D.xf, 24, HN), 238);
  add(planVana(D.yL - 3, D.yR + 2, D.xf, 24, D.xf - 0.6), 240);    // schod nad koly: nahoře plná šířka
  add(planVana(D.yL - 4, D.yR + 3, D.xf, 24, D.xf - 0.6), D.zSeva - 3);
  add(planVana(D.yL - 4, D.yR + 3, D.xf, 24, D.xf - 0.6), D.zSeva);
  const top = rings[rings.length - 1].poly, w = 5;
  rings.push({ poly: polyInset(top, w), z: zc(D.zSeva) });
  rings.push({ poly: polyInset(top, w), z: zc(D.zDno + 14) });
  rings.push({ poly: polyInset(planVana(D.yL + 6, D.yR - 5, D.xf - 5, 20, HN - 5), w), z: zc(D.zDno + 8) });
  g.add(skorepina('cerna', 'vana', rings, { otevreno: 'nahoru' }));

  // ---- čelní stěna: pás pod víkem, výlisky kolem západek, zvýšený štít s logem, stupňovitý spodek ----
  const xs = D.xf;                                           // čelní plocha vany
  g.add(bx('cerna_mat', 'celo_pas', xs - 1, xs + 2, D.yL + 70, D.yR - 60, 262, 270));
  for (const [nm, yc] of [['L', -280], ['P', 215]]) {
    g.add(slab('cerna', 'celo_zamek_vylis_' + nm, { x0: xs - 2, x1: xs + 3.5, y0: yc - 52, y1: yc + 52, z0: zc(150), z1: zc(268), rs: 8, reT: 1.5, fs: 2 }));
  }
  g.add(slab('cerna', 'celo_stit', { x0: xs - 2, x1: xs + 3, y0: -140, y1: 78, z0: zc(52), z1: zc(150), rs: 20, reT: 1.5, fs: 2 }));
  // logo (červená plochá písmena, zjednodušený font)
  for (const p of napis('MILWAUKEE', { x: xs + 0.2, y: -58, z: zc(222), h: 30, sirka: 0.55, mezera: 0.25 })) g.add(p);
  g.add(blesk('cervena', xs + 0.2, -125, 20, zc(198), 26));
  for (const p of napis('PACKOUT', { x: xs + 0.2, y: -8, z: zc(178), h: 13, sklon: 0.15 })) g.add(p);
  // spodní patky (široké, ne nožičky)
  for (const sx of [-1, 1]) for (const [y0, y1] of [[-405, -232], [100, 262]]) {
    g.add(slab('cerna', `patka_${sx > 0 ? 'P' : 'L'}_${y0}`, { x0: sx > 0 ? 190 : -286, x1: sx > 0 ? 286 : -190, y0, y1, z0: zc(16), z1: zc(D.zDno + 2), rs: 8, reB: 3, fs: 2 }));
  }
  // ---- konec u kol: koncový blok (nástavec s úchytem), spodní žebrovaná patka mezi koly ----
  g.add(slab('cerna', 'konec_blok', { x0: -168, x1: 168, y0: D.yR - 14, y1: 482.5, z0: zc(246), z1: zc(350), rs: 14, reT: 14, reB: 3, fs: 3, kT: 0.6 }));
  g.add(extYZ('cerna', 'konec_sikma', [[400, zc(350)], [460, zc(350)], [482.5, zc(326)], [482.5, zc(280)], [400, zc(280)]], -150, 150));
  for (let i = 0; i < 9; i++) g.add(bx('cerna_mat', 'konec_zebro' + i, -150 + i * 37.5 - 4, -150 + i * 37.5 + 4, 480.5, 482.5, 270, 325));
  g.add(slab('cerna', 'konec_patka', { x0: -170, x1: 170, y0: D.yR - 8, y1: 462, z0: zc(26), z1: zc(80), rs: 10, reB: 4, fs: 2 }));
  for (let i = 0; i < 12; i++) g.add(bx('cerna_mat', 'konec_patka_zebro' + i, -156 + i * 28.4 - 3, -156 + i * 28.4 + 3, 458, 462.5, 32, 74));
  return g;
}

// ---- vyjímatelná vložka (tác) u konce s madlem – c02–c04; ve zavřeném stavu skrytá ve vaně; posun nahoru po Z ----
export function vlozka() {
  const g = new Group('vlozka', { pivot: [0, -300, zc(280)], extras: { posun_osa: [0, 0, 1], zdvih_max: 160, popis: 'vyjímatelná vložka (tác se dvěma přihrádkami); posun nahoru' } });
  const P = (hx, y0, y1, r) => rrPoly(-hx, hx, y0, y1, r, 3);
  const rings = [], add = (poly, z) => rings.push({ poly, z: zc(z) });
  add(P(270, -447, -166, 12), 250);
  add(P(280, -452, -160, 16), 256);
  add(P(280, -452, -160, 16), 296);
  add(P(284, -455, -157, 18), 302);
  add(P(274, -447, -163, 14), 302);
  add(P(274, -447, -163, 14), 262);
  add(P(266, -441, -171, 10), 258);
  g.add(skorepina('cerna', 'vlozka_tac', rings, { otevreno: 'nahoru' }));
  g.add(bx('cerna', 'vlozka_prepazka', -9, 9, -440, -172, 258, 292));
  g.add(bx('cerna', 'vlozka_zebro', -266, 266, -312, -306, 258, 280));
  return g;
}
