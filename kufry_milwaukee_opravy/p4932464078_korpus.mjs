// 4932464078 – spodní díl (vana), čelo, rohové lišty, boční madla, zadní stěna. Souřadnice: X = hloubka 472 (čelo +X), Y = šířka 561, Z = výška 530; počátek = střed obálky.
// Výšky v kódu jsou z' = výška nad podlahou (0 = spodek kol, 530 = horní hrana složeného madla); převod z = z' - 265.
import { Part, Group, box, tube, prism, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid, mirY, addSym, loftSolid, cylinder } from './p4932464078_zaklad.mjs';
export const ZC = 265;
export const zc = z => z - ZC;
export const D = {
  xf: 230, xr: -224,          // čelní stěna vany / zadní stěna vany (čelní výstupky a víko až na ±236)
  wU: 242, wL: 200,           // poloviční šířka vany: horní část / spodní zadní část (u kol)
  zDno: 34, zSeva: 335,       // spodek vany, švík víko/vana
  yRail: 276,                 // vnější strana rohových lišt
};
const bx = (mat, name, x0, x1, y0, y1, z0, z1) => box(mat, name, x0, x1, y0, y1, zc(z0), zc(z1));

function planVana(wRear, wFront, xNotch = -70) {
  const P = [[D.xf, -wFront], [D.xf, wFront], [xNotch, wFront], [xNotch, wRear], [D.xr, wRear], [D.xr, -wRear], [xNotch, -wRear], [xNotch, -wFront]];
  return roundPoly(P, [10, 10, 4, 4, 14, 14, 4, 4], 3);
}

export function korpus() {
  const g = new Group('korpus');
  // ---- vana: vnější plášť + vnitřní dutina (zjednodušená, hladká) ----
  const rings = [];
  const add = (poly, z) => rings.push({ poly, z: zc(z) });
  const wr = D.wL, wf = D.wU;
  add(planVana(wr - 12, wf - 14), D.zDno);                 // spodek – zkosená spodní hrana
  add(planVana(wr - 4, wf - 5), D.zDno + 8);
  add(planVana(wr, wf), D.zDno + 18);
  add(planVana(wr, wf), 212);
  add(planVana(D.wU - 8, wf), 214);                        // schod nad koly: zadní část se rozšíří na plnou šířku
  add(planVana(D.wU - 8, wf), D.zSeva - 2);
  add(planVana(D.wU - 8, wf), D.zSeva);                    // horní okraj
  const w = 5;
  const top = rings[rings.length - 1].poly;
  rings.push({ poly: polyInset(top, w), z: zc(D.zSeva) });
  rings.push({ poly: polyInset(top, w), z: zc(D.zDno + 12) });
  rings.push({ poly: polyInset(planVana(wr - 12, wf - 14), w), z: zc(D.zDno + 8) });
  g.add(skorepina('cerna', 'vana', rings, { otevreno: 'nahoru' }));

  // ---- čelní panel (zvednutý schodovitý výstupek se žebrovanou spodní deskou) ----
  const xp = D.xf;                                           // čelní plocha vany
  g.add(extYZ('cerna', 'celo_panel', roundPoly([[-132, 178], [132, 178], [132, 110], [92, 110], [92, 38], [-92, 38], [-92, 110], [-132, 110]].map(([y, z]) => [y, zc(z)]), [14, 14, 6, 6, 6, 6, 6, 6], 3), xp - 2, 236));
  // žebrovaná spodní deska (rýhy)
  for (let i = -6; i <= 6; i++) g.add(bx('cerna_mat', 'celo_zebro' + i, 232, 236.4, i * 11.5 - 2.2, i * 11.5 + 2.2, 44, 104));
  // záklopky nad zámky (výlisky kolem západek) – tmavé tlumicí plošky
  for (const s of [-1, 1]) g.add(slab('cerna', 'zamek_vylis' + (s > 0 ? 'P' : 'L'), { x0: xp - 1, x1: 234, y0: s * 150 - 62, y1: s * 150 + 62, z0: zc(262), z1: zc(338), rs: 6, reT: 1.5, fs: 2 }));

  // ---- rohové lišty (hliník) s černými hlavicemi, stojí před koncovou stěnou ----
  for (const s of [-1, 1]) {
    const y0 = s > 0 ? D.yRail - 14 : -D.yRail, y1 = s > 0 ? D.yRail : -D.yRail + 14;
    const lis = bx('pozink', 'lista_' + (s > 0 ? 'P' : 'L'), 196, 232, y0, y1, 76, 330);
    g.add(lis);
    // žebra lišty
    for (const k of [-1, 0, 1]) g.add(bx('seda', 'lista_zebro' + (s > 0 ? 'P' : 'L') + k, 206 + (k + 1) * 10, 208 + (k + 1) * 10, y0 + (s > 0 ? 0.5 : -0.5) * 0 + 1, y1 - 1, 77, 329));
    // hlavice (horní, dolní)
    const yh0 = Math.min(s * 244, s * D.yRail), yh1 = Math.max(s * 244, s * D.yRail);
    g.add(slab('cerna', 'lista_hlavice_h_' + (s > 0 ? 'P' : 'L'), { x0: 194, x1: 236, y0: yh0, y1: yh1, z0: zc(330), z1: zc(404), rs: 8, reT: 5, reB: 1, fs: 2 }));
    g.add(slab('cerna', 'lista_hlavice_d_' + (s > 0 ? 'P' : 'L'), { x0: 190, x1: 236, y0: yh0 - 4 * (s > 0 ? 0 : 1) + (s > 0 ? 0 : 0), y1: yh1 + 0, z0: zc(8), z1: zc(76), rs: 8, reT: 1, reB: 6, fs: 2 }));
    // spoje lišty se stěnou (nahoře a dole) – přemostění mezery
    g.add(bx('cerna', 'lista_most_h_' + (s > 0 ? 'P' : 'L'), 196, 232, Math.min(s * 240, s * 262), Math.max(s * 240, s * 262), 318, 336));
    g.add(bx('cerna', 'lista_most_d_' + (s > 0 ? 'P' : 'L'), 196, 232, Math.min(s * 240, s * 262), Math.max(s * 240, s * 262), 70, 90));
  }

  // ---- boční madla (červený rám s gumovým úchopem, vybrání v koncové stěně) ----
  for (const s of [-1, 1]) {
    const yw = s * 242;                                      // koncová stěna
    const nm = s > 0 ? 'P' : 'L';
    // červený rám madla
    const o = [[-96, 318], [150, 318], [150, 236], [-96, 236]];
    const fr = extXZ('cervena', 'bocni_madlo_ram_' + nm, roundPoly(o.map(([x, z]) => [x, zc(z)]), [8, 8, 8, 8], 3), Math.min(yw, yw + s * 20), Math.max(yw, yw + s * 20));
    g.add(fr);
    // gumový úchop (tyč s žebry)
    g.add(tube('cerna_mat', 'bocni_madlo_uchop_' + nm, [[-70, yw + s * 12, zc(268)], [126, yw + s * 12, zc(268)]], 11, 14));
    for (let i = 0; i < 12; i++) g.add(tube('cerna_mat', 'bocni_madlo_zebro_' + nm + i, [[-64 + i * 16, yw + s * 12, zc(268) - 12.5], [-64 + i * 16, yw + s * 12, zc(268) + 12.5]], 1.3, 6));
  }

  // ---- zadní stěna: svislá žebra, spodní stupňovitá deska (opěrka) ----
  for (let i = -9; i <= 9; i++) {
    if (Math.abs(i) < 2) continue;
    g.add(bx('cerna', 'zad_zebro' + i, -233, D.xr + 2, i * 24 - 3, i * 24 + 3, 220, 332));
  }
  g.add(extYZ('cerna', 'zad_opirka', roundPoly([[-110, zc(30)], [110, zc(30)], [86, zc(140)], [-86, zc(140)]], [4, 4, 4, 4], 2), -233, D.xr + 2));
  return g;
}
