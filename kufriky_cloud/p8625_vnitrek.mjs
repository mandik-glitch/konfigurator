// Vnitřek vany 4932478625: pevná příčná stěna (střed), vodicí drážky a šest vyjímatelných červených děličů (3 dlouhé + 3 krátké).
// Děliče jsou samostatné uzly (vyjímatelné), stojí na podlaze vany. Obrysy děličů: c16 (viz p8625_data.mjs), poloha a rozměry: c02/c03.
import { Group, slab, bx, zc, ZC } from './p8625_zaklad.mjs';
import { prismXZ } from './pomocne_8625.mjs';
import { K } from './p8625_korpus.mjs';
import { DELIC_DLOUHY, DELIC_KRATKY } from './p8625_data.mjs';

export const I = {
  xw: -62, tw: 3.2,                 // poloha a tloušťka pevné příčné stěny (střed)
  zFloor: K.cav.floor,              // horní plocha dna vany
  zTopW: 152,                       // horní hrana pevné stěny
  ysDel: [-114, 0, 114],            // polohy děličů ve směru Y (osa děliče)
  kDel: 0.386, kDelZ: 0.337,                      // mm na pixel c16 (měřítko děličů; určeno z rozměrů vany, viz poznámky)
  tDel: 2.4,                        // tloušťka děliče
};

// polygon děliče v c16 [px] -> [x(mm podél X), z'(výška)]: střed šířky = x0c, spodek = zBottom
function polyDelice(c, xc, zBottom, flipX) {
  const b = c.bbox, k = I.kDel, cx = (b[0] + b[2]) / 2;
  return c.vnejsi.map(([px, py]) => [(flipX ? -1 : 1) * (px - cx) * k + xc, zBottom + (py - b[1]) * I.kDelZ]);
}

export function vnitrek() {
  const g = new Group('vnitrek');
  const C = K.cav;
  // pevná příčná stěna (černá) s mírně zesílenou hlavou
  g.add(slab('cerna_mat', 'pevny_stred', { x0: I.xw - I.tw / 2, x1: I.xw + I.tw / 2, y0: -C.y + 2, y1: C.y - 2, z0: I.zFloor - 1, z1: I.zTopW, rs: 0.5, seg: 1, reT: 0.8, reB: 0.3, fs: 1 }));
  g.add(slab('cerna_mat', 'pevny_stred_hlava', { x0: I.xw - 2.8, x1: I.xw + 2.8, y0: -C.y + 2, y1: C.y - 2, z0: I.zTopW - 3.5, z1: I.zTopW, rs: 0.5, seg: 1, reT: 1.2, reB: 0.3, fs: 1 }));
  // vodicí drážky děličů: dvojice žeber po stranách každé drážky na čelní, zadní a obou stranách pevné stěny
  const zT = I.zTopW - 6;
  for (const y of I.ysDel) for (const [xa, xb] of [[C.x1 - 1.8, C.x1], [C.x0, C.x0 + 1.8], [I.xw + I.tw / 2, I.xw + I.tw / 2 + 1.8], [I.xw - I.tw / 2 - 1.8, I.xw - I.tw / 2]]) for (const sy of [-1, 1]) {
    const yy = y + sy * (I.tDel / 2 + 1.4);
    g.add(bx('cerna_mat', 'vodici_zebro', xa, xb, yy - 0.7, yy + 0.7, I.zFloor, zT));
  }
  // podlaha čelních oddílů: dvě mělké podložky (3 mm) oddělené žebrem uprostřed (c03; rozměry NEOVĚŘENY, jen přibližné)
  for (const sy of [-1, 1]) g.add(slab('cerna_mat', 'podlozka_dna', { x0: -48, x1: 138, y0: sy > 0 ? 9 : -215, y1: sy > 0 ? 215 : -9, z0: I.zFloor - 0.5, z1: I.zFloor + 3, rs: 4, seg: 3, reT: 1, reB: 0.2, fs: 2 }));
  return g;
}

// děliče: vlastní skupina; každý dělič je samostatný uzel (vyjímatelný), deska v rovině (x, z') vytažená podél Y
export function delice() {
  const g = new Group('delice');
  const C = K.cav, zB = I.zFloor;
  const xaL = I.xw + I.tw / 2 + 0.8, xbL = C.x1 - 0.8;           // dlouhé: od pevné stěny k čelní stěně
  const xaS = C.x0 + 0.8, xbS = I.xw - I.tw / 2 - 0.8;           // krátké: od zadní stěny k pevné stěně
  const mk = (name, c, xa, xb, y, flip) => {
    const xc = (xa + xb) / 2, k = I.kDel;
    const poly = polyDelice(c, xc, zB + 0.2, flip);
    const d = new Group(name, { pivot: [xc, y, zc(zB)], extras: { vyjimatelny: true } });
    d.add(prismXZ('cervena', name + '_deska', poly.map(([x, z]) => [x, z - ZC]), y - I.tDel / 2, y + I.tDel / 2));
    // průzory (vodicí otvory) v uších děliče – tmavé záplaty na obou stranách
    for (const h of c.otvory) {
      const hb = [Math.min(...h.map(p => p[0])), Math.min(...h.map(p => p[1])), Math.max(...h.map(p => p[0])), Math.max(...h.map(p => p[1]))];
      const cx = (c.bbox[0] + c.bbox[2]) / 2;
      const x0 = (flip ? -1 : 1) * (hb[0] - cx) * k + xc, x1 = (flip ? -1 : 1) * (hb[2] - cx) * k + xc;
      const z0 = zB + 0.2 + (hb[1] - c.bbox[1]) * I.kDelZ, z1 = zB + 0.2 + (hb[3] - c.bbox[1]) * I.kDelZ;
      d.add(bx('cerna_mat', name + '_otvor', Math.min(x0, x1), Math.max(x0, x1), y - I.tDel / 2 - 0.12, y + I.tDel / 2 + 0.12, z0, z1));
    }
    return d;
  };
  I.ysDel.forEach((y, i) => {
    g.addGroup(mk('delic_dlouhy_' + (i + 1), DELIC_DLOUHY[i], xaL, xbL, y, false));
    g.addGroup(mk('delic_kratky_' + (i + 1), DELIC_KRATKY[i], xaS, xbS, y, false));
  });
  return g;
}
