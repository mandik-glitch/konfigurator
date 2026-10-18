// Boční černý rám (3 úhelníky: horní, šikmá čelní, zadní = sloupek) + děrovaný nerezový panel s drážkami (skutečné otvory),
// spodní rám (lišty, deska, osa kol), nýty, neutrální štítek. Obě strany zrcadlově.
import { Part, Group, plate, extrudeRound, slotRing, box, cylX, cylinder, K, Y } from './c_zaklad.mjs';
import { SLOTY } from './c_data.mjs';

const yo = z => K.yft - K.slope * (K.zft - z);          // vnější čelní hrana rámu (y při výšce z)
const yi = z => yo(z) + K.wBar;                          // vnitřní hrana
export const RAM = { yRear: K.yRear, zTop: K.zft, zIn: K.zft - K.wBar, zBot: K.zfb };

function stranaE() {
  const out = [];
  const x0 = K.hw, { yRear, zTop, zIn, zBot } = RAM;
  // děrovaný panel (obrys uvnitř rámu), tloušťka 1,8 mm, skutečné otvory
  const panel = [[yi(zBot), zBot], [yRear, zBot], [yRear, zIn], [yi(zIn), zIn]];
  const sloty = SLOTY.map(([y, z, l, a]) => slotRing(Y(y + 4.5), z, l, 7, a, 3));
  out.push(plate('nerez_svetly', 'panel_deroveny', panel, sloty, x0 + 0.7, x0 + 2.5));
  out.push(plate('cerna_mat', 'panel_podklad', panel, [], x0 + 0.1, x0 + 0.7));       // tmavý podklad – vidět skrz drážky
  // rám: obrys CCW (y, z')
  const ram = [[yo(zTop), zTop], [yo(RAM.zBot), RAM.zBot], [yi(RAM.zBot), RAM.zBot], [yi(zIn), zIn], [yRear, zIn], [yRear, zTop]];
  // (první bod = vnější horní přední roh; jde dolů po vnější hraně)
  out.push(extrudeRound('cerna', 'ram_bok', ram, x0, x0 + K.ramH, { re: 3, seg: 2, mapF: (u, v, w) => [w, u, v] }));
  // nýty (hlavy 4 mm) na horním a čelním úhelníku
  const nyty = [[Y(-70), zTop - 15], [Y(60), zTop - 15], [Y(165), zTop - 15], [yo(470) + 15, 470], [yo(250) + 15, 250]];
  for (const [y, z] of nyty) out.push(cylX('ocel', 'nyt', 4.2, x0 + K.ramH, x0 + K.ramH + 2.5, y, z, 10));
  // štítek (neutrální bílá ploška 80 × 55) u zadního spodního rohu panelu
  out.push(box('plocha_bila', 'stitek', x0 + 2.5, x0 + 3.1, Y(120), Y(200), 210, 268));
  return out;
}

export function ramBoky() {
  const g = new Group('ram_boky');
  const E = stranaE();
  for (const p of E) { g.add(p); g.add(p.clone(p.name, p.mat).mirror('x', 0)); }
  return g;
}

// spodní rám: lišty po stranách, deska, osa kol, příčky
export function spodniRam() {
  const g = new Group('spodni_ram');
  const { hw, Yf, yb } = K;
  for (const sg of [-1, 1]) {
    const a = sg > 0 ? hw - 4 : -hw - 16, b = sg > 0 ? hw + 16 : -hw + 4;
    g.add(box('nerez_svetly', 'lista_spodni', a, b, Yf + 12, K.yRear + 8, 130, 142));       // vodorovná příruba úhelníku
    g.add(box('nerez_svetly', 'lista_spodni_svisla', sg > 0 ? hw + 12 : -hw - 16, sg > 0 ? hw + 16 : -hw - 12, Yf + 12, K.yRear + 8, 142, 188));
  }
  g.add(box('cerna', 'podlaha', -hw + 10, hw - 10, Yf + 16, K.yRear + 6, 118, 126));
  g.add(cylX('cerna', 'osa_kol', 12, -K.xw + 30, K.xw - 30, K.yw, K.R, 14));
  g.add(box('cerna', 'pricka_predni', -hw + 4, hw - 4, Yf + 14, Yf + 40, 126, 160));
  return g;
}
