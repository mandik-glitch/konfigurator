// Korpus (černý PP) – zadní deska, boční stěny, čtyři rohové nárazníky, spodní pás, nožičky – model 4932498323.
// Souřadnice: X = šířka (čelo s madlem +X), Y = délka, Z = výška (plocha s boxy +Z). Rozměry viz zdroje/4932498323_poznamky.md.
import { Group, slab, loftSolid, roundPoly, ccw, extYZ, ext, bx, mirrorInto, voxelSolid } from './p8323_zaklad.mjs';

export const K = {
  XT: 193, XBODY: -177.3, XB: -193,           // horní (madlo) hrana, spodní hrana korpusu, konec nožiček
  ZF: 85, ZPLATE: -69, ZBP: -58,              // čelní rovina rámu, spodek zadní desky, horní líc zadní desky
  YO: 249.9, YOB: 248.4, YW: 238.5, YIN: 202, // vnější šířka nárazníků (nahoře / dole), střední stěna, okno s boxy
  XOT: 161.5, XOB: -162.8,                    // horní a dolní hrana okna s boxy
  XNT: 135, XNB: -121.2,                      // hranice mezi horním/dolním nárazníkem a střední stěnou
  CHX: 22, YPL: 232, WREC: 6.5,               // zkosení zadní hrany nárazníku ve směru X (odhad); polovina šířky zadní desky; zapuštění spodního pásu stěny
};

// Vrstvy nárazníku: obrys z vrcholů {p:[x,y], n:[nx,ny] (vnější normála, null = pevný), r:poloměr}; posun podél -n podle výšky z.
//   sy(z) = zúžení ve směru Y (zkosení zadní hrany Z -68…-53, zapuštěný střed Z -39…58 o 2,5 mm, c04);  e(z) = zaoblení čelní hrany (Z 81…85).
const Zs = [-68, -63, -58, -53, -39, -36.5, 55.5, 58, 81, 83.2, 84.5, 85];
const chm = (z, c) => z < -53 ? c * (-53 - z) / 15 : 0;
const sy = z => z < -53 ? 22 * (-53 - z) / 15 : (z < -39 ? 0 : z < -36.5 ? 2.5 * (z + 39) / 2.5 : z < 55.5 ? 2.5 : z < 58 ? 2.5 * (58 - z) / 2.5 : 0);
const ee = z => z <= 81 ? 0 : z <= 83.2 ? 0.5 * (z - 81) / 2.2 : z <= 84.5 ? 0.5 + 1.0 * (z - 83.2) / 1.3 : 1.5 + 2.0 * (z - 84.5) / 0.5;
function bumperLayers(verts, n = 4) {
  return Zs.map(z => {
    const pts = verts.map(v => {
      if (!v.n) return v.p;
      const k = (v.n[1] > 0.3 ? sy(z) : 0) + (Math.abs(v.n[0]) > 0.3 ? chm(z, K.CHX) : 0) + ee(z);
      return [v.p[0] - v.n[0] * k, v.p[1] - v.n[1] * k];
    });
    return { poly: ccw(roundPoly(pts, verts.map(v => v.r), n)), z };
  });
}
const S2 = Math.SQRT1_2;

export function narazniky(g) {
  const { XT, YO, YOB, YW, YIN, XNT, XNB, XBODY } = K;
  // horní (u madla): čelo stupňovité – panel X=185 do |y|=218 (stěna u madla), sloupek X=193 od |y|=218 (c04)
  const top = [
    { p: [XNT, YIN], r: 0 }, { p: [185, YIN], r: 0 }, { p: [185, 218], r: 0.6 }, { p: [XT, 218], n: [1, 0], r: 0.6 },
    { p: [XT, YO], n: [S2, S2], r: 23 }, { p: [147, YO], n: [0, 1], r: 2 }, { p: [XNT, YW], n: null, r: 2 }];
  // dolní: náběh zkosením z |y| 238,5 na 248,4, zkosený roh u spodní hrany
  const bot = [
    { p: [XBODY, YIN], r: 0 }, { p: [XNB, YIN], r: 0 }, { p: [XNB, YW], n: null, r: 2 }, { p: [-133.5, YOB], n: [0, 1], r: 3 },
    { p: [-161.5, YOB], n: [0, 1], r: 3 }, { p: [XBODY, 231.5], n: [-S2, S2], r: 2 }];
  const items = [
    loftSolid('o8323_mat', 'naraznik_horni', bumperLayers(top), { crease: 40 }),
    loftSolid('o8323_mat', 'naraznik_dolni', bumperLayers(bot), { crease: 40 }),
  ];
  mirrorInto(g, items);
}

export function steny(g) {
  const { YIN, YW, XNT, XNB, XBODY, XOB, ZF, ZBP, ZPLATE } = K;
  // zadní deska s zkosenou spodní hranou (c04: zúžení u Z -62…-69)
  g.add(slab('o8323_cerna', 'deska_zadni', { x0: XBODY, x1: 185, y0: -K.YPL, y1: K.YPL, z0: ZPLATE, z1: ZBP, rs: 8, seg: 4, reB: 5, reT: 0, fs: 3 }));
  // boční (koncové) stěny: horní hrana zkosená (pás s červeným proužkem), dole zapuštěný pás (Z -58…-28), c05/c15
  const prof = [[YIN, ZBP], [K.YPL, ZBP], [K.YPL, -28], [YW, -28], [YW, 68], [226, ZF], [YIN, ZF]];
  if (K.WREC <= 0) { prof.splice(1, 3, [YW, ZBP]); }
  mirrorInto(g, [extYZ('o8323_mat', 'bok_stena', prof, XNB, XNT)]);
  // spodní pás (u nožiček): plná výška, čelní hrana Z=85
  g.add(slab('o8323_mat', 'pas_dolni', { x0: XBODY, x1: XOB, y0: -YIN, y1: YIN, z0: ZBP, z1: ZF, rs: 0.8, seg: 2, reT: 0.8, reB: 0, fs: 2 }));
}

// nožičky pod spodním pásem (u čelní strany; zadní strana neověřena)
export function nozicky(g) {
  const poly = [[K.XBODY + 0.3, 177], [K.XBODY + 0.3, 213.8], [-193, 203.5], [-193, 180.2]];
  mirrorInto(g, [ext('o8323_mat', 'nozicka', ccw(poly.map(([x, y]) => [x, y])), 38, 80)]);
}

export function korpus() {
  const g = new Group('korpus');
  steny(g); narazniky(g); nozicky(g);
  return g;
}
