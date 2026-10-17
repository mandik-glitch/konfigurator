// 4932471723 – nosné držadlo = vztyčený rám přes délku víka (čepy nad sponou). Rám stojí v rovině YZ (X ±11,5), čepy na koncích víka.
// Výchozí (zavřená) poloha: rám je zasunut – příčka leží v žlábku víka (horní hrana z' 330 = katalog), nohy zapadají do víka. Poloha vztyčeno = posun o ZDVIH nahoru.
import { Group } from './p4932471723_zaklad.mjs';
import { k } from './p4932471723_telo.mjs';
export const ZDVIH = 103;
export function drzadlo(nahore = false) {
  const dz = nahore ? 0 : -ZDVIH;
  const g = new Group('drzadlo', { pivot: [0, 0, k.zc(306)], extras: { typ: 'posun', posun_osa: [0, 0, 1], posun_vztycene_mm: ZDVIH, poznamka: 'Kinematika sklopení z jedné fotky neověřena; výchozí poloha = zavřeno (obálka katalogu 330 mm), vztyčená poloha = posun nahoru o posun_vztycene_mm.' } });
  const yo = 192, yi = 163, zt = 433, zb = 401;   // vnější/vnitřní Y nohou, horní/spodní hrana příčky (v poloze vztyčeno)
  // kvůli otevřenému rámu (nohy dole nekončí) se obrys uzavírá na z' 300 (+dz): spodní hrany nohou jsou ve víku
  const poly = [[-yo - 1, 290], [-yo - 3, 380], [-yo + 6, 420], [-yo + 22, zt], [yo - 22, zt], [yo - 6, 420], [yo + 1, 380], [yo - 1, 290], [yi, 290], [yi - 1, 392], [yi - 10, zb], [-yi + 10, zb], [-yi + 1, 392], [-yi, 290]].map(([y, z]) => [y, z + dz]);
  g.add(k.extYZ('cerna', 'drzadlo-ram', poly, -10, 10));
  // vroubkování na příčce (rýhy proti sklouznutí)
  for (let i = 0; i < 9; i++) { const y = -80 + i * 22; g.add(k.bx('cerna_mat', 'drzadlo-drazka', -8, 8, y, y + 8, zt - 3 + dz, zt - 0.4 + dz)); }
  // čepy
  g.add(k.cylX('ocel', 'drzadlo-cep-predni', 4, -14, 14, 190, 306));
  return g;
}
