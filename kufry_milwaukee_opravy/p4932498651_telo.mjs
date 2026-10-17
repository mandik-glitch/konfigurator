// Pojízdný box 4932498651 – tělo (skříň s otevřeným čelem pro zásuvku), víko s 10 kapsami, rohové patky a hliníkové tyče, boční rukojeti v pouzdrech.
import { Part, Group, rrPoly, loftBox, loftVessel, rbox, bx, extYZ, extXZ, cylX, cylY, extrude, roundPoly } from './p4932478162_zaklad.mjs';
import { HX, BY, LIDY, Z_LID0, Z_LID1, Z_PLATE, Z_TOP, Z_BOT, XR } from './p4932498651_data.mjs';

const T = 7;   // tloušťka stěn skříně (odhad)
export function skrin() {
  const g = new Group('telo');
  const zt = Z_LID0 + 2;
  // zadní stěna, dno a strop skříně (strop = spodní deska víka)
  g.add(rbox('cerna', 'zadni_stena', XR, XR + T + 3, -250, 250, Z_BOT, zt, 8, 2));
  g.add(rbox('cerna', 'dno', XR, 236, -250, 250, Z_BOT, Z_BOT + T, 10, 2));
  g.add(rbox('cerna', 'strop', XR, 240, -250, 250, zt - T, zt, 10, 2));
  // boční stěny s pouzdrem rukojeti (otevřené nahoře pod víkem)
  const POC = { x0: XR + 68, x1: 150, z0: 62 };
  for (const s of [1, -1]) {
    const ya = s > 0 ? 238 : -251, yb = s > 0 ? 251 : -238, m = s > 0 ? '' : '_m';
    g.add(rbox('cerna', 'bok_spodni' + m, XR, 236, ya, yb, Z_BOT, POC.z0, 8, 2.5));
    g.add(rbox('cerna', 'bok_predni_sloupek' + m, POC.x1, 238, ya, yb, POC.z0 - 2, zt, 8, 2));
    g.add(rbox('cerna', 'bok_zadni_sloupek' + m, XR, POC.x0, ya, yb, POC.z0 - 2, zt, 8, 2));
    g.add(bx('cerna_mat', 'pouzdro_dno' + m, POC.x0, POC.x1, s > 0 ? 231 : -238, s > 0 ? 238 : -231, POC.z0, zt));
    g.add(bx('cerna_mat', 'pouzdro_zlab' + m, POC.x0, POC.x1, s > 0 ? 231 : -243, s > 0 ? 243 : -231, POC.z0, POC.z0 + 4));
    for (const x of [-100, -20, 60, 120]) g.add(bx('cerna_mat', 'pouzdro_zebro' + m + x, x - 2, x + 2, s > 0 ? 238 : -246, s > 0 ? 246 : -238, POC.z0 + 5, zt - 8));
  }
  // čelní rám otvoru zásuvky: horní a spodní příčka + svislé sloupky
  g.add(rbox('cerna', 'celo_horni_pricka', 222, 240, -250, 250, 206, zt, 5, 2));
  g.add(rbox('cerna', 'celo_spodni_pricka', 222, 240, -250, 250, Z_BOT, -206, 5, 2));
  // žebrování (zuby) spodní příčky pro spojování boxů
  for (let k = 0; k < 12; k++) { const y = -220 + k * 40; g.add(bx('cerna_mat', 'celo_spodni_zub', 236, 240, y, y + 22, Z_BOT + 4, Z_BOT + 26)); }
  g.add(rbox('cerna', 'celo_sloupek_p', 222, 240, 224, 250, -206, 206, 4, 1.5));
  g.add(rbox('cerna', 'celo_sloupek_l', 222, 240, -250, -224, -206, 206, 4, 1.5));
  return { g, POC };
}

// 10 kapes na víku (rozložení jako u XL: zadní řada 4 malé, střední 2 dlouhé, přední 4 malé)
export const KAPSY_RADY = [
  { x0: -210, x1: -128, bloky: [[-222, -134], [-118, -30], [30, 118], [134, 222]] },
  { x0: -112, x1: -20, bloky: [[-222, -24], [24, 222]] },
  { x0: -4, x1: 80, bloky: [[-222, -134], [-118, -30], [30, 118], [134, 222]] },
];
const poly = (x0, x1, y0, y1, r, rn = 2) => roundPoly([[x1, y1], [x0, y1], [x0, y0], [x1, y0]], [r, r, r, r], rn);
export function viko() {
  const g = new Group('viko');
  const L = (z, d, r = 16) => ({ z, x0: XR + d, x1: 240 - d, y0: -LIDY + d, y1: LIDY - d, r });
  // plné těleso víka (vrstvy) + deska s kapsami
  g.add(loftBox('cerna_lesk', 'viko_telo', [L(Z_LID0, 0), L(Z_LID1 - 4, 0), L(Z_PLATE - 2, 12, 22), L(Z_PLATE, 15, 25)], { seg: 4, crease: 38 }));
  const out = rrPoly(XR + 15, 240 - 15, -LIDY + 15, LIDY - 15, 25, 4);
  const holes = [];
  for (const r of KAPSY_RADY) for (const [y0, y1] of r.bloky) holes.push(poly(r.x0, r.x1, y0, y1, 9, 3));
  g.add(extrude('cerna_lesk', 'viko_deska', out, holes, Z_PLATE - 0.5, Z_TOP, { crease: 30 }));
  for (const h of holes) g.add(extrude('cerna', 'kapsa_dno', h, [], Z_PLATE - 6, Z_PLATE, { crease: 30 }));
  // červený štítek na ploše víka (vpravo) a lišty
  g.add(rbox('cervena', 'viko_stitek', -70, -10, 40, 130, Z_TOP - 1.2, Z_TOP + 0.01, 3, 0.4));
  // větrací blok na čele víka
  g.add(rbox('cerna', 'viko_vetrani', 230, 240, -60, 60, 234, 262, 3, 1.5));
  for (let k = 0; k < 7; k++) { const y = -48 + k * 16; g.add(bx('cerna_mat', 'viko_vetrani_zebro', 238.5, 240, y - 3, y + 3, 238, 258)); }
  // lišta pod víkem po obvodu a zámek (červená lišta nahoře uprostřed zásuvky – součást čela zásuvky)
  return g;
}

// rohové patky a hliníkové tyče
function patka(name, sx, sy, z0, z1, hi) {
  const x0 = sx > 0 ? 198 : XR - 4, x1 = sx > 0 ? 240 : XR + 38;
  const y0 = sy > 0 ? 228 : -BY, y1 = sy > 0 ? BY : -228;
  const d = (z, k) => ({ z, x0: x0 + (sx > 0 ? 0 : k), x1: x1 - (sx > 0 ? k : 0), y0: y0 + (sy > 0 ? 0 : k), y1: y1 - (sy > 0 ? k : 0), r: 9 });
  return loftBox('cerna', name, hi ? [d(z0, 0), d(z1 - 14, 0), d(z1 - 2, 5), d(z1, 7)] : [d(z0, 7), d(z0 + 2, 5), d(z0 + 14, 0), d(z1, 0)], { seg: 3, crease: 38 });
}
export function rohy() {
  const g = new Group('rohy');
  for (const sx of [1, -1]) for (const sy of [1, -1]) {
    const id = (sx > 0 ? 'p' : 'z') + (sy > 0 ? '1' : '2');
    g.add(patka('patka_horni_' + id, sx, sy, 205, Z_LID1, true));
    g.add(patka('patka_dolni_' + id, sx, sy, -257, -205, false));
    const xc = sx > 0 ? 222 : XR + 16, yc = sy * 246;
    g.add(rbox('hlinik', 'tyc_' + id, xc - 12, xc + 12, yc - 12, yc + 12, -207, 207, 3.5, 1.2, 3));
    for (const dy of [-5, 0, 5]) g.add(bx('cerna_mat', 'tyc_drazka_' + id, sx > 0 ? xc + 11.4 : xc - 12.2, sx > 0 ? xc + 12.2 : xc - 11.4, yc + dy - 0.7, yc + dy + 0.7, -200, 200));
    g.add(cylX('ocel', 'srouby_' + id, 4, sx > 0 ? 238.6 : XR - 4, sx > 0 ? 240 : XR - 2.6, sy * 243, 238, 14));
  }
  return g;
}

// boční rukojeť (zapuštěná v pouzdře, uzel s pivotem nahoře, osa X): dvě červené vidlice (ucha) s čepem nahoře, spodní červená příčka a černý gumový úchop
export function rukojetBok(s, POC) {
  const id = s > 0 ? 'P' : 'L', y0 = 232.5, y1 = 243;
  const g = new Group('rukojet_bok_' + id, { pivot: [-10, s * 234, 206], extras: { osa: [s > 0 ? 1 : -1, 0, 0], max_uhel: 60, popis: 'boční rukojeť (zapuštěná v pouzdře), čep nahoře' } });
  const yA = s > 0 ? y0 : -y1, yB = s > 0 ? y1 : -y0;
  // vidlice (XZ profil s drážkami nahoře – „hřebeny“)
  const ucho = (xa, xb, nm) => {
    const poly = roundPoly([[xa, 104], [xb, 104], [xb, 206], [xb - 8, 206], [xb - 8, 190], [xa + 8, 190], [xa + 8, 206], [xa, 206]], [4, 4, 1, 1, 1, 1, 1, 1], 2);
    g.add(extXZ('cervena', nm + id, poly, yA, yB, 30));
  };
  ucho(-136, -108, 'rukojet_bok_ucho_'); ucho(116, 144, 'rukojet_bok_ucho2_');
  g.add(rbox('cervena', 'rukojet_bok_pricka_' + id, -136, 144, s > 0 ? y0 : -(y1 + 2), s > 0 ? y1 + 2 : -y0, 104, 120, 4, 2));
  g.add(rbox('guma', 'rukojet_bok_uchop_' + id, -104, 112, s > 0 ? y0 + 1 : -(y1 + 7), s > 0 ? y1 + 7 : -(y0 + 1), 118, 138, 4, 3));
  g.add(cylY('ocel', 'rukojet_bok_cep_' + id, 4.5, s > 0 ? y1 + 0.5 : -(y1 + 3.5), s > 0 ? y1 + 3.5 : -(y1 + 0.5), -122, 196, 12));
  g.add(cylY('ocel', 'rukojet_bok_cep2_' + id, 4.5, s > 0 ? y1 + 0.5 : -(y1 + 3.5), s > 0 ? y1 + 3.5 : -(y1 + 0.5), 130, 196, 12));
  return g;
}
