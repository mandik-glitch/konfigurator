// Zásuvky: pohyblivé uzly „zasuvka-N“ (N = 1 nahoře …) s osou výsuvu +X (extras.osa) a teleskopické kolejnice (střední člen „kolejnice-N-L/P“
// se pohybuje poloviční rychlostí, extras.vazba/podil). Délka zásuvky a kolejnic je volená tak, aby se zásuvka při plném výsuvu neoddělila od těla
// (kontroluje se v overZasuvky() a ve vytvor_zasuvky.mjs). Čela: červené držadlo ≈ 190 × 18 mm v prolisu, štítek na horní zásuvce.
import { Group, rbx, G } from './p4932472129_zaklad.mjs';
import { hollowBox as hb } from '../kufriky_cloud/jadro/mesh.js';

export const Z = {
  xCelo: G.FACE_X, tlCela: 10,                       // čelo: x 188 … 198
  xZad: -170,                                        // zadní hrana tácu v zavřené poloze → délka tácu 358 mm
  yTac: 224,                                         // polovina šířky tácu
  stena: 8, dno: 6,
  kol: { in: [-105, 195], mid: [-130, 190], fix: [-185, 190] },   // teleskop: vnitřní (na zásuvce), střední, pevný
  yHandle: 99, barHalf: 95,
};

export function zasuvka(i, f) {
  const nm = 'zasuvka-' + (i + 1);
  const zc = (f.z0 + f.z1) / 2;
  const g = new Group(nm, { pivot: [Z.xCelo, 0, zc], extras: { osa: [1, 0, 0], typ: 'posuv', rozsah_mm: [0, G.VYSUV_PLNY], vysun_castecny_mm: G.VYSUV_CAST, cast: 'zasuvka' } });
  const x0 = Z.xCelo - Z.tlCela, x1 = Z.xCelo;
  const h = f.z1 - f.z0;
  // čelo se zaobleným okrajem; prolis pro držadlo uprostřed
  // držadlo: u nízkých čel (4 zásuvky, 2 + 1 nahoře) lišta 18 mm ≈ 6,5 mm pod horní hranou, u vysokých čel (2, 3 zásuvky, spodní velká u 2 + 1) lišta ≈ 22 mm,
  // jejím středem ≈ 30 mm pod horní hranou (změřeno z fotek c02/c01 přes červenou masku; viz zdroje/*_poznamky.md); prolis sahá od lišty dolů
  const velke = h > 85, barH = velke ? 22 : 18, barTop = f.z1 - (velke ? 19 : 5.5);
  const rz1 = barTop + 3.5, rz0 = f.z0 + 11 + 0.14 * Math.max(h - 68, 0), yh = Z.yHandle;
  g.add(rbx('cerna', 'zasuvka_celo_L', x0, x1, -236, -yh, f.z0, f.z1, 5, 2.2, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_P', x0, x1, yh, 236, f.z0, f.z1, 5, 2.2, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_horni', x0, x1, -yh - 1, yh + 1, rz1, f.z1, 2, 1.8, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_dolni', x0, x1, -yh - 1, yh + 1, f.z0, rz0, 2, 1.8, 3, 2));
  g.add(rbx('cerna_mat', 'zasuvka_prolis', x0, x0 + 11, -yh, yh, rz0 - 0.5, rz1 + 0.5, 1, 0.5, 2, 1));
  // červené držadlo (rýhovaná lišta) u horní hrany prolisu
  g.add(rbx('cervena', 'zasuvka_drzadlo', x0 + 8, x1 + 1.5, -Z.barHalf, Z.barHalf, barTop - barH, barTop, 3, 2.4, 4, 3));
  for (let k = 0; k < 24; k++) {
    const y = -Z.barHalf + 6 + k * ((2 * Z.barHalf - 12) / 23);
    g.add(rbx('cervena', 'zasuvka_drzadlo_rys', x1 - 0.5, x1 + 2, y - 1.3, y + 1.3, barTop - barH, barTop - barH + 5, 0.5, 0.4, 2, 1));
  }
  // červený štítek Milwaukee PACKOUT na horní zásuvce vpravo od držadla (z fotek, červená maska: vysoká čela 98 × 44 mm, nízká 76 × 34 mm; pravý okraj y ≈ 212 / 201)
  if (i === 0) {
    const bw = velke ? 98 : 76, bh = velke ? 44 : 34, yr = velke ? 212 : 201, zt = f.z1 - (velke ? 19 : 20);
    g.add(rbx('cervena', 'zasuvka_stitek', x1 - 1.6, x1 + 1.3, yr - bw, yr, zt - bh, zt, 5, 1.2, 4, 2));
    g.add(rbx('bila', 'zasuvka_stitek_napis1', x1 + 1.1, x1 + 1.6, yr - bw * 0.88, yr - bw * 0.14, zt - bh * 0.58, zt - bh * 0.42, 1, 0.2, 2, 1));
    g.add(rbx('bila', 'zasuvka_stitek_napis2', x1 + 1.1, x1 + 1.6, yr - bw * 0.78, yr - bw * 0.30, zt - bh * 0.24, zt - bh * 0.12, 1, 0.2, 2, 1));
  }
  // tác (tlustá stěna 8 mm, otevřený nahoře)
  g.add(hb('cerna', 'zasuvka_tac', { x0: Z.xZad, x1: x0 + 0.5, y0: -Z.yTac, y1: Z.yTac, z0: f.z0 + 4.5, z1: f.z1 - 6, rc: 6, re: 1.5, wall: Z.stena, floor: Z.dno, seg: 3, fs: 2 }));
  // vnitřní člen kolejnice (na zásuvce)
  for (const sy of [1, -1]) g.add(rbx('cerna_mat', 'kolejnice_vnitrni', Z.kol.in[0], Z.kol.in[1], sy > 0 ? 224 : -228, sy > 0 ? 228 : -224, zc - 7, zc + 7, 0.6, 0.4, 2, 1));
  // vyjímatelné červené přepážky (příslušenství; na fotkách c04–c06 vidět v některých zásuvkách): samostatný podřízený uzel
  g.addGroup(prepazky(i, f, nm, zc));
  g.zc = zc;
  return g;
}

// přepážky: mřížka tenkých červených desek (2,2 mm); počet buněk podle velikosti zásuvky (nízká 4 × 3, vysoká 3 × 3)
export function prepazky(i, f, nm, zc) {
  const g = new Group('prepazky-' + (i + 1), { pivot: [Z.xCelo, 0, zc], extras: { typ: 'prislusenstvi', volitelne: true, patri_k: nm } });
  const zf = f.z0 + 4.5 + Z.dno, vyska = Math.min(38, (f.z1 - 6) - zf - 8);
  const nx = (f.z1 - f.z0) > 100 ? 3 : 4, ny = 3, xa = Z.xZad + Z.stena + 2, xb = Z.xCelo - Z.tlCela - Z.stena + 2, ya = -(Z.yTac - Z.stena) + 1, yb = (Z.yTac - Z.stena) - 1;
  g.add(rbx('cervena', 'prepazky_dno', xa, xb, ya, yb, zf - 0.5, zf + 1.6, 1, 0.3, 2, 1));
  for (let k = 1; k < nx; k++) { const x = xa + k * (xb - xa) / nx; g.add(rbx('cervena', 'prepazka_pricna', x - 1.1, x + 1.1, ya, yb, zf - 0.5, zf + vyska, 0.5, 0.4, 2, 1)); }
  for (let k = 1; k < ny; k++) { const y = ya + k * (yb - ya) / ny; g.add(rbx('cervena', 'prepazka_podelna', xa, xb, y - 1.1, y + 1.1, zf - 0.5, zf + vyska, 0.5, 0.4, 2, 1)); }
  return g;
}

// střední člen teleskopické kolejnice (jeden na stranu a zásuvku)
export function kolejnice(i, f) {
  const out = [], zc = (f.z0 + f.z1) / 2;
  for (const sy of [1, -1]) {
    const g = new Group(`kolejnice-${i + 1}-${sy > 0 ? 'P' : 'L'}`, { pivot: [0, sy * 230, zc], extras: { osa: [1, 0, 0], typ: 'posuv', vazba: 'zasuvka-' + (i + 1), podil: 0.5 } });
    g.add(rbx('cerna_mat', 'kolejnice_stredni', Z.kol.mid[0], Z.kol.mid[1], sy > 0 ? 228 : -232, sy > 0 ? 232 : -228, zc - 8, zc + 8, 0.6, 0.4, 2, 1));
    out.push(g);
  }
  return out;
}

// kontrola, že se zásuvka při plném výsuvu neoddělí od těla: překryv členů kolejnice
export function overZasuvky() {
  const e = G.VYSUV_PLNY, d = [];
  const ov = (a, b) => Math.min(a[1], b[1]) - Math.max(a[0], b[0]);
  const mid = [Z.kol.mid[0] + e / 2, Z.kol.mid[1] + e / 2], inn = [Z.kol.in[0] + e, Z.kol.in[1] + e];
  d.push({ dvojice: 'pevný/střední', preryv_mm: ov(Z.kol.fix, mid) }, { dvojice: 'střední/vnitřní', preryv_mm: ov(mid, inn) });
  return d;
}
