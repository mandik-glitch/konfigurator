// 4932471723 – nosné držadlo = vztyčený rám přes délku víka (čepy nad sponou). Rám stojí v rovině YZ (X ±11,5), čepy na koncích víka.
// Výchozí (zavřená) poloha: rám je zasunut – příčka leží v žlábku víka (horní hrana z' 330 = katalog), nohy zapadají do víka. Poloha vztyčeno = posun o ZDVIH nahoru.
import { Group } from './p4932471723_zaklad.mjs';
import { k } from './p4932471723_telo.mjs';
export const ZDVIH = 135;
export function drzadlo(nahore = false) {
  const dz = nahore ? 0 : -ZDVIH;
  const g = new Group('drzadlo', { pivot: [0, 0, k.zc(316)], extras: { typ: 'posun', posun_osa: [0, 0, 1], posun_vztycene_mm: ZDVIH, poznamka: 'Kinematika sklopení z jedné fotky neověřena; výchozí poloha = zavřeno (obálka katalogu 330 mm), vztyčená poloha = posun nahoru o posun_vztycene_mm.' } });
  const yo = 202, yi = 170, zt = 462, zb = 428;   // vnější/vnitřní Y nohou, horní/spodní hrana příčky (v poloze vztyčeno)
  // obrys rámu v rovině (Y, z') – vnější a vnitřní oblouk
  const outer = [[-yo - 1, 300], [-yo - 3, 400], [-yo + 6, 442], [-yo + 22, zt], [yo - 22, zt], [yo - 6, 442], [yo + 1, 400], [yo - 1, 300]].reverse().map(([y, z]) => [y, z + dz]);
  const hole = [[-yi, 300], [-yi + 1, 410], [-yi + 10, zb], [yi - 10, zb], [yi - 1, 410], [yi, 300]].reverse().map(([y, z]) => [y, z + dz]);
  // kvůli otevřenému rámu (nohy dole nekončí) se obrys uzavírá na z' 300 (+dz): spodní hrany nohou jsou ve víku
  const poly = [[-yo - 1, 300], [-yo - 3, 400], [-yo + 6, 442], [-yo + 22, zt], [yo - 22, zt], [yo - 6, 442], [yo + 1, 400], [yo - 1, 300], [yi, 300], [yi - 1, 410], [yi - 10, zb], [-yi + 10, zb], [-yi + 1, 410], [-yi, 300]].map(([y, z]) => [y, z + dz]);
  g.add(k.extYZ('cerna', 'drzadlo-ram', poly, -11.5, 11.5));
  // vroubkování na příčce (rýhy proti sklouznutí)
  for (let i = 0; i < 9; i++) { const y = -80 + i * 22; g.add(k.bx('cerna_mat', 'drzadlo-drazka', -9, 9, y, y + 8, zt - 3 + dz, zt + 0.6 + dz)); }
  // čepy
  g.add(k.cylX('ocel', 'drzadlo-cep-predni', 4, -14, 14, 190, 316));
  return g;
}
