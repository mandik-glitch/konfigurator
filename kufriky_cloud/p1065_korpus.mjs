// Korpus (černá vana s lemem na švíku víka), rukojeť (deska s oknem), rohové nárazníky, pantové čepy, patky a žebra – model 4932471065.
// Souřadnice: X = šířka (249), Y = délka (čelo +Y), výšky z' od nejnižšího bodu (0 .. 64). Měření viz zdroje/4932471065_poznamky.md.
import { Group, Part, rrPoly, roundPoly, ccw, loftSolid, ext, slab, rrShell, ringSolid, bx, zc, cylinder } from './p1065_zaklad.mjs';
import { extrude, offsetPoly, rectPoly, rrect, cylX } from './pomocne.mjs';

export const K = {
  zFoot: 0, zPlate: 3, zWallBot: 7, zFloor: 8,           // patky 0..3, deska dna 3..8, spodní hrana vnější stěny 7
  zStep: 23.5, zSeam: 28,                                // schod na horním okraji, švík s víkem
  hHandleBot: 9.5, hHandleTop: 28.6,                     // rukojeť (deska): c07 rektifikace čelní plochy Y = 205,5
  hw: 115.5, rimHw: 113, y0: -196, y1: 150,              // vana: poloviční šířka, zadní a čelní hrana těla
  cav: { hw: 103, y0: -177, y1: 128 },                   // otvor pro nádoby (vnitřní prostor 203 × 305)
  diag: { a: [115.5, 139.5], b: [81.5, 177.3] },         // úhlopříčná čelní hrana (rukojeť + roh se sponou), c06/c03
  yH: 205.5, xH: 56.0,                                   // čelní hrana rukojeti, poloviční šířka čelní plochy
  hingeY: -196.5, hingeZ: 30.5, hingeR: 7.2,
  zBump: 56,
};

export const bodyOutline = () => roundPoly([[-K.hw, K.y0], [K.hw, K.y0], [K.hw, 139.5], [106.1, K.y1], [-106.1, K.y1], [-K.hw, 139.5]], [22, 22, 0, 0, 0, 0], 8);
const rimOutline = () => roundPoly([[-K.rimHw, K.y0 + 1.5], [K.rimHw, K.y0 + 1.5], [K.rimHw, 139], [104.6, K.y1], [-104.6, K.y1], [-K.rimHw, 139]], [21, 21, 0, 0, 0, 0], 8);
export const cavityPoly = () => rrPoly(-K.cav.hw, K.cav.hw, K.cav.y0, K.cav.y1, 9, 6);
export const handleOutline = () => roundPoly([[108.8, 147], [K.diag.b[0], K.diag.b[1]], [K.xH, K.yH], [-K.xH, K.yH], [-K.diag.b[0], K.diag.b[1]], [-108.8, 147]], [0, 0, 1.5, 1.5, 0, 0], 3);
export const windowPoly = () => roundPoly([[-54.5, 184.5], [-54.5, 171], [-33, 151], [33, 151], [54.5, 171], [54.5, 184.5]], [6.5, 3, 3, 3, 3, 6.5], 5);

const ex = (mat, name, outer, holes, z0, z1, o) => extrude(mat, name, outer, holes, zc(z0), zc(z1), o);

// ---------- vana ----------
function vana(g) {
  const out = bodyOutline(), cav = cavityPoly();
  // deska dna (patky pod ní) – užší než vnější stěna: spodní hrana stěny je vyšší než spodek desky (c13: deska ustupuje do vany)
  g.add(ex('cerna_mat', 'vana_dno', offsetPoly(out, 6.5), [], K.zPlate, K.zFloor));
  // vnitřní podlaha pod nádobami (jednoduchý obdélník; překrývá případné vlasové praskliny triangulace velké desky)
  g.add(ex('cerna_mat', 'vana_podlaha', rrPoly(-104.5, 104.5, -178.5, 129.5, 10, 6), [], K.zPlate + 0.8, K.zFloor - 0.05));
  // stěna (od 7 do schodu) a lem na švíku (užší, zadní strana kryje pant)
  g.add(ex('cerna_mat', 'vana_stena', out, [cav], K.zWallBot, K.zStep));
  g.add(ex('cerna_mat', 'vana_lem', rimOutline(), [cav], K.zStep, K.zSeam));
  // rukojeť: deska s oknem (c06/c03 půdorys, c07 výška)
  g.add(ex('cerna_mat', 'rukojet', handleOutline(), [windowPoly()], K.hHandleBot, K.hHandleTop));
  // žebra úchopu na horní ploše příčky (rozteč 7,8; c03)
  const zb = new Part('rukojet_zebra', 'cerna_mat');
  for (let i = -5; i <= 5; i++) zb.append(ex('cerna_mat', 'z', rrect(i * 7.8, 194, 3.8, 12, 1.4, 0, 2), [], K.hHandleTop - 0.3, K.hHandleTop + 0.9));
  g.add(zb);
  // zámek víka – černý jazýček na čelní stěně dutiny (c12: 47 × 12,5 mm, zaoblený)
  g.add(ex('cerna_mat', 'zamek_jazyk', rrect(0, 135.8, 47, 12.5, 3.5), [], K.zSeam - 0.2, K.zSeam + 3));
  g.add(ex('cerna_mat', 'zamek_jazyk_hore', rrect(0, 135.8, 44, 9.5, 2.6), [], K.zSeam + 2.9, K.zSeam + 4.2));
}

// ---------- červené tlačítko (palcová část pod víkem + tělo při dně), rektifikace čela c07: 44 mm široké, z' 14..32 ----------
function tlacitko(g) {
  g.add(ex('cervena', 'tlacitko_dno', rrect(0, 136, 45.6, 28, 4), [], 2.6, K.zWallBot + 1));
  // palec: vystupuje z čelní stěny okna o ~3 mm (c12), horní plocha pod okrajem desky rukojeti
  g.add(loftSolid('cervena', 'tlacitko_palec', [
    { poly: ccw(rrect(0, 150.2, 44, 8.6, 3, 0, 2)), z: 14 }, { poly: ccw(rrect(0, 150.2, 44, 8.6, 3, 0, 2)), z: 26.5 },
    { poly: ccw(rrect(0, 150.2, 41, 7, 2.6, 0, 2)), z: 28.0 }]));
}

// ---------- zadní rohové nárazníky (černé, kolem rohu víka, bez zásahu do dutiny) ----------
function bumper(s) {
  const arc = (cx, cy, r, a0, a1, n) => Array.from({ length: n + 1 }, (_, i) => { const a = (a0 + (a1 - a0) * i / n) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; });
  let poly = [[84.5, -205.3], [95, -205.3], ...arc(95, -176, 29.0, -90, 0, 10).slice(1), [124.3, -163], [119.4, -157.5], ...arc(93, -165, 25.8, 0, -90, 10), [84.5, -190.8]];
  if (s < 0) poly = poly.map(p => [-p[0], p[1]]).reverse();
  const p = ex('cerna_mat', s > 0 ? 'naraznik_P' : 'naraznik_L', poly, [], 5, K.zBump, { crease: 30 });
  // zkosení vrchu (vnější zadní roh nižší)
  p.mapV((x, y, z) => { if (z < zc(K.zBump) - 1e-6) return [x, y, z]; const d = Math.hypot(Math.abs(x) - 95, y + 165); return [x, y, z - Math.min(9, Math.max(0, (d - 14) * 0.45))]; });
  return p;
}

// ---------- pant: černé články základny + ocelový čep (c06 zadní okraj; středy X = 0, ±48, šířka 22,2) ----------
function pant(g) {
  const zcen = zc(K.hingeZ), y = K.hingeY, r = K.hingeR;
  for (const xc of [-48, 0, 48]) {
    const x0 = xc - 11.1, x1 = xc + 11.1;
    g.add(cylX('cerna_mat', 'pant_clanek_' + xc, y, zcen, r, x0, x1, 18));
    g.add(bx('cerna_mat', 'pant_noha_' + xc, x0, x1, y, K.y0 + 3, K.hingeZ - r + 0.4, K.hingeZ + r - 1.2));
    g.add(bx('cerna_mat', 'pant_podstava_' + xc, x0, x1, y - 0.6, K.y0 + 3, K.zStep - 6, K.hingeZ - r + 0.7));
  }
  g.add(cylX('ocel', 'pant_cep', y, zcen, 1.6, -108, 108, 10));
}

// ---------- patky spodku (3 × 2, c13: 8 štěrbin 17,5 × 4,2, rozteč 7,9, patka 70 × 36, středy X = ±53, Y = 55 / −46,5 / −147,5) ----------
function patky(g) {
  const ys = [55, -46.5, -147.5], xs = [-53, 53];
  for (const y of ys) for (const x of xs) {
    const slots = [];
    for (let i = 0; i < 8; i++) slots.push(rrect(x + (i - 3.5) * 7.9, y, 4.2, 17.5, 1.6, 0, 2));
    g.add(ex('cerna_mat', 'patka', rrect(x, y, 70, 36, 4, 0, 3), slots, K.zFoot, K.zPlate + 0.2));
  }
}

// ---------- rysky na spodní stěně vany (c07 rektifikace boku: rozteč 12,2; 1,2 × 5 mm) ----------
function rysky(g) {
  const pr = new Part('vana_rysky', 'cerna_mat');
  for (const sx of [1, -1]) for (let y = -150; y <= 135; y += 12.2) {
    const x0 = sx > 0 ? K.hw - 0.2 : -K.hw - 0.5, x1 = sx > 0 ? K.hw + 0.5 : -K.hw + 0.2;
    pr.append(bx('cerna_mat', 'r', x0, x1, y - 0.6, y + 0.6, 11.5, 17));
  }
  g.add(pr);
}

export function korpus() {
  const g = new Group('korpus');
  vana(g); tlacitko(g);
  for (const s of [1, -1]) g.add(bumper(s));
  pant(g); patky(g); rysky(g);
  return g;
}
