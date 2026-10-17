// 4932464078 – spodní díl (vana), čelo, rohové lišty, boční madla, zadní stěna. Souřadnice: X = hloubka 472 (čelo +X), Y = šířka 561, Z = výška 530; počátek = střed obálky.
// Výšky v kódu jsou z' = výška nad podlahou (0 = spodek kol, 530 = horní hrana složeného madla); převod z = z' - 265.
import { napis, blesk, Part, Group, box, tube, prism, rrPoly, roundPoly, ccw, ext, extYZ, extXZ, slab, skorepina, polyInset, ringSolid, mirY, addSym, loftSolid, cylinder } from './p4932464078_zaklad.mjs';
export const ZC = 265;
export const zc = z => z - ZC;
export const H_LID = +(process.env.KUF_HLID || 410);          // výška horní plochy víka nad podlahou (z')
export const D = {
  xf: 230, xr: -224,          // čelní stěna vany / zadní stěna vany (čelní výstupky a víko až na ±236)
  wU: 244, wL: 200,           // poloviční šířka vany: horní část / spodní zadní část (u kol)
  zDno: 38, zSeva: H_LID - 60,       // spodek vany, švík víko/vana
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
  add(planVana(250, wf), 214);                        // schod nad koly: zadní část se rozšíří na plnou šířku
  add(planVana(250, wf), D.zSeva - 2);
  add(planVana(250, wf), D.zSeva);                    // horní okraj
  const w = 5;
  const top = rings[rings.length - 1].poly;
  rings.push({ poly: polyInset(top, w), z: zc(D.zSeva) });
  rings.push({ poly: polyInset(top, w), z: zc(D.zDno + 12) });
  rings.push({ poly: polyInset(planVana(wr - 12, wf - 14), w), z: zc(D.zDno + 8) });
  g.add(skorepina('cerna', 'vana', rings, { otevreno: 'nahoru' }));

  // ---- logo na čele (červená plochá písmena, zjednodušený font; tvar písma Milwaukee není kopírován) ----
  for (const p of napis('MILWAUKEE', { x: D.xf + 0.2, y: -18, z: zc(284), h: 26, sirka: 0.55, mezera: 0.25 })) g.add(p);
  g.add(blesk('cervena', D.xf + 0.2, -88, 52, zc(262), 24));
  for (const p of napis('PACKOUT', { x: D.xf + 0.2, y: 40, z: zc(248), h: 11, sklon: 0.15 })) g.add(p);
  // ---- čelní panel (zvednutý schodovitý výstupek se žebrovanou spodní deskou) a ocelová smyčka ----
  const xp = D.xf;                                           // čelní plocha vany
  g.add(extYZ('cerna', 'celo_panel', roundPoly([[-124, 215], [124, 215], [124, 154], [100, 116], [100, 46], [-100, 46], [-100, 116], [-124, 154]].map(([y, z]) => [y, zc(z)]), [16, 16, 4, 8, 8, 8, 8, 4], 3), xp - 2, 232.4));
  for (let i = -6; i <= 6; i++) g.add(bx('cerna_mat', 'celo_zebro' + i, 232.3, 233.6, i * 12.4 - 2.4, i * 12.4 + 2.4, 52, 108));
  // smyčka (chromovaný drát Ø 5,2, šířka ≈ 175 mm), čepy zasazené do spodní desky
  const sm = [[231.4, -80, 48], [233.2, -86, 64], [233.4, -82, 100], [233.4, -64, 112], [233.4, 64, 112], [233.4, 82, 100], [233.2, 86, 64], [231.4, 80, 48]].map(([x, y, z]) => [x, y, zc(z)]);
  g.add(tube('ocel', 'celo_smycka', sm, 2.6, 10));
  // záklopky nad zámky (výlisky kolem západek) – tmavé tlumicí plošky
  for (const s of [-1, 1]) g.add(slab('cerna', 'zamek_vylis' + (s > 0 ? 'P' : 'L'), { x0: xp - 1, x1: 234, y0: s * 178 - 58, y1: s * 178 + 58, z0: zc(272), z1: zc(372), rs: 6, reT: 1.5, fs: 2 }));

  // ---- rohové lišty: vpravo plochá hliníková lišta 36 × 14 mm čelem k předku, vlevo odsazená tyč Ø 14 (madlo) s kolénkem; černé hlavice nahoře i dole ----
  const zT = D.zSeva - 6;                                    // horní hlavice končí těsně pod švíkem
  for (const s of [-1, 1]) {
    const nm = s > 0 ? 'P' : 'L';
    const yh0 = Math.min(s * 238, s * 277), yh1 = Math.max(s * 238, s * 277);
    g.add(slab('cerna', 'lista_hlavice_h_' + nm, { x0: 192, x1: 236, y0: yh0, y1: yh1, z0: zc(zT - 76), z1: zc(zT + 4), rs: 7, reT: 5, reB: 1, fs: 2 }));
    g.add(slab('cerna', 'lista_hlavice_d_' + nm, { x0: 188, x1: 236, y0: yh0, y1: yh1, z0: zc(32), z1: zc(92), rs: 7, reT: 1, reB: 6, fs: 2 }));
  }
  g.add(bx('pozink', 'lista_P', 214, 232, 241, 277, 92, zT - 76));
  for (const k of [0, 1, 2]) g.add(bx('seda', 'lista_zebro_P' + k, 232, 233, 247 + k * 12, 249 + k * 12, 86, zT - 78));
  g.add(tube('pozink', 'lista_tyc_L', [[222, -268, zc(zT - 74)], [222, -268, zc(112)], [222, -265, zc(100)], [222, -257, zc(90)], [222, -245, zc(86)]], 7.2, 12));
  // ---- boční madla (červený rám s gumovým úchopem, vybrání v koncové stěně) ----
  for (const s of [-1, 1]) {
    const yw = s * 244;                                      // koncová stěna
    const nm = s > 0 ? 'P' : 'L';
    // červený rám madla
    const o = [[-96, D.zSeva - 14], [150, D.zSeva - 14], [150, D.zSeva - 92], [-96, D.zSeva - 92]];
    const fr = extXZ('cervena', 'bocni_madlo_ram_' + nm, roundPoly(o.map(([x, z]) => [x, zc(z)]), [8, 8, 8, 8], 3), Math.min(yw, yw + s * 20), Math.max(yw, yw + s * 20));
    g.add(fr);
    // gumový úchop (tyč s žebry)
    g.add(tube('cerna_mat', 'bocni_madlo_uchop_' + nm, [[-70, yw + s * 12, zc(D.zSeva - 53)], [126, yw + s * 12, zc(D.zSeva - 53)]], 11, 14));
    for (let i = 0; i < 12; i++) g.add(tube('cerna_mat', 'bocni_madlo_zebro_' + nm + i, [[-64 + i * 16, yw + s * 12, zc(D.zSeva - 53) - 12.5], [-64 + i * 16, yw + s * 12, zc(D.zSeva - 53) + 12.5]], 1.3, 6));
  }

  // ---- zadní stěna: kanály madla (žebrované sloupce), svislá žebra, spodní stupňovitá deska (opěrka) ----
  for (const sg of [-1, 1]) {
    const nm = sg > 0 ? 'P' : 'L';
    g.add(bx('cerna', 'zad_kanal_' + nm, -233, D.xr + 2, sg * 165 - 29, sg * 165 + 29, 46, 336));
    for (let k = 0; k < 12; k++) g.add(bx('cerna_mat', 'zad_kanal_zebro_' + nm + k, -235.5, -232, sg * 165 - 27, sg * 165 + 27, 56 + k * 23, 60 + k * 23));
    g.add(tube('ocel', 'zad_kanal_sroub_' + nm, [[-235.5, sg * 165, zc(70)], [-236, sg * 165, zc(70)]], 4, 8));
  }
  for (let i = -9; i <= 9; i++) {
    if (Math.abs(i) < 2 || Math.abs(Math.abs(i * 24) - 165) < 40) continue;
    g.add(bx('cerna', 'zad_zebro' + i, -231, D.xr + 2, i * 24 - 3, i * 24 + 3, 220, 332));
  }
  g.add(extYZ('cerna', 'zad_opirka', roundPoly([[-110, zc(30)], [110, zc(30)], [86, zc(140)], [-86, zc(140)]], [4, 4, 4, 4], 2), -233, D.xr + 2));
  return g;
}
