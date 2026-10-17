// Zásuvky: pohyblivé uzly „zasuvka-N“ (N = 1 nahoře …) s osou výsuvu +X (extras.osa) a teleskopické kolejnice (střední člen „kolejnice-N-L/P“
// se pohybuje poloviční rychlostí, extras.vazba/podil). Délka zásuvky a kolejnic je volená tak, aby se zásuvka při plném výsuvu neoddělila od těla
// (kontroluje se v ověřZasuvky()). Čela: červené držadlo ≈ 190 × 18 mm v prolisu, štítek na horní zásuvce.
import { Group, rbx, hollowBox, G, box } from './p4932472129_zaklad.mjs';
import { hollowBox as hb } from '../kufriky_cloud/jadro/mesh.js';

export const Z = {
  xCelo: G.FACE_X, tlCela: 10,                       // čelo: x 188 … 198
  xZad: -170,                                        // zadní hrana tácu v zavřené poloze → délka tácu 358 mm
  yTac: 224,                                         // polovina šířky tácu
  stena: 8, dno: 6,
  kol: { in: [-105, 195], mid: [-130, 190], fix: [-185, 190] },   // teleskop: vnitřní (na zásuvce), střední, pevný
  yHandle: 104, barHalf: 95,
};

export function zasuvka(i, f) {
  const nm = 'zasuvka-' + (i + 1);
  const zc = (f.z0 + f.z1) / 2;
  const g = new Group(nm, { pivot: [Z.xCelo, 0, zc], extras: { osa: [1, 0, 0], typ: 'posuv', rozsah_mm: [0, G.VYSUV_PLNY], vysun_castecny_mm: G.VYSUV_CAST, cast: 'zasuvka' } });
  const x0 = Z.xCelo - Z.tlCela, x1 = Z.xCelo;
  const h = f.z1 - f.z0;
  // čelo se zaobleným okrajem; prolis pro držadlo uprostřed
  const rz0 = f.z0 + 11, rz1 = f.z1 - 4, yh = Z.yHandle;
  g.add(rbx('cerna', 'zasuvka_celo_L', x0, x1, -236, -yh, f.z0, f.z1, 5, 2.2, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_P', x0, x1, yh, 236, f.z0, f.z1, 5, 2.2, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_horni', x0, x1, -yh - 1, yh + 1, rz1, f.z1, 2, 1.8, 3, 2));
  g.add(rbx('cerna', 'zasuvka_celo_dolni', x0, x1, -yh - 1, yh + 1, f.z0, rz0, 2, 1.8, 3, 2));
  g.add(rbx('cerna_mat', 'zasuvka_prolis', x0, x0 + 11, -yh, yh, rz0 - 0.5, rz1 + 0.5, 1, 0.5, 2, 1));
  // červené držadlo (rýhovaná lišta) u horní hrany prolisu
  g.add(rbx('cervena', 'zasuvka_drzadlo', x0 + 8, x1 + 1.5, -Z.barHalf, Z.barHalf, rz1 - 19, rz1 - 1, 3, 2.4, 4, 3));
  for (let k = 0; k < 24; k++) {
    const y = -Z.barHalf + 6 + k * ((2 * Z.barHalf - 12) / 23);
    g.add(rbx('cervena', 'zasuvka_drzadlo_rys', x1 - 0.5, x1 + 2, y - 1.3, y + 1.3, rz1 - 19, rz1 - 14, 0.5, 0.4, 2, 1));
  }
  // tác (tlustá stěna 8 mm, otevřený nahoře)
  g.add(hb('cerna', 'zasuvka_tac', { x0: Z.xZad, x1: x0 + 0.5, y0: -Z.yTac, y1: Z.yTac, z0: f.z0 + 4.5, z1: f.z1 - 6, rc: 6, re: 1.5, wall: Z.stena, floor: Z.dno, seg: 3, fs: 2 }));
  // vnitřní člen kolejnice (na zásuvce)
  for (const sy of [1, -1]) g.add(rbx('cerna_mat', 'kolejnice_vnitrni', Z.kol.in[0], Z.kol.in[1], sy > 0 ? 224 : -228, sy > 0 ? 228 : -224, zc - 7, zc + 7, 0.6, 0.4, 2, 1));
  g.zc = zc;
  return g;
}

// střední člen teleskopické kolejnice (jeden na stranu a zásuvku)
export function kolejnice(i, f) {
  const out = [], zc = (f.z0 + f.z1) / 2;
  for (const sy of [1, -1]) {
    const g = new Group(`kolejnice-${i + 1}-${sy > 0 ? 'P' : 'L'}`, { pivot: [0, sy * 230, zc], extras: { osa: [1, 0, 0], typ: 'posuv', vazba: 'zasuvka-' + (i + 1), podil: 0.5 } });
    g.add(rbx('seda', 'kolejnice_stredni', Z.kol.mid[0], Z.kol.mid[1], sy > 0 ? 228 : -232, sy > 0 ? 232 : -228, zc - 8, zc + 8, 0.6, 0.4, 2, 1));
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
