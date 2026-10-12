// Hilti kufr "TE 6-22 prázdný", č. 2294834, 495 × 395 × 149 mm – vlastní parametrický model podle fotografie výrobce (hilti.cz, c01 = L137214, jen pohled shora na zavřený kufr).
// Otevřený pohled, vnitřek a svislé míry jsou ODVOZENY z 2329229 (stejné rozměry z hilti.cz) – viz zdroje/2294834_poznamky.md. Skořepina (loft, hinge, výšky) je společná:
// p2329229_zaklad.mjs, p2329229_skorepina.mjs; vnější reliéf (madlo, západky, nopy, logo) podle fotografie L137214 je v p2294834_data.mjs.
// Souřadnice: X = hloubka 395 (čelo s madlem do +X), Y = délka 495, Z = výška 149 (víko nahoře); počátek = střed obálky.
import { Group } from './p2329229_zaklad.mjs';
import { skorepina } from './p2329229_skorepina.mjs';
import { D } from './p2294834_data.mjs';

export const SKU = '2294834';
export const OBALKA = { x: 395, y: 495, z: 149 };
export const CELO = 'X';
export const NAZEV = 'Hilti kufr TE 6-22 (2294834)';

export function build() {
  const root = new Group(SKU), { korpus, vicko } = skorepina(D);
  root.addGroup(korpus); root.addGroup(vicko);
  return root;
}
