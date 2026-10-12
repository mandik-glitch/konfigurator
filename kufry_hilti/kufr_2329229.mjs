// Hilti kufr "2-tools (S) SF/SI prázdný", č. 2329229, 495 × 395 × 149 mm – vlastní parametrický model podle fotografií výrobce (hilti.cz, c01..c04).
// Souřadnice: X = hloubka 395 (čelo s madlem a západkami do +X), Y = délka 495, Z = výška 149 (víko nahoře); počátek = střed obálky.
// Zavřená verze, vnější pohled; vnitřek zjednodušen. Moduly: p2329229_zaklad.mjs (loft), p2329229_skorepina.mjs (skořepina z dat), p2329229_data.mjs (data z c01).
import { Group } from './p2329229_zaklad.mjs';
import { skorepina } from './p2329229_skorepina.mjs';
import { D } from './p2329229_data.mjs';

export const SKU = '2329229';
export const OBALKA = { x: 395, y: 495, z: 149 };
export const CELO = 'X';
export const NAZEV = 'Hilti kufr 2-tools (S) SF/SI (2329229)';

export function build() {
  const root = new Group(SKU), { korpus, vicko } = skorepina(D);
  root.addGroup(korpus); root.addGroup(vicko);
  return root;
}
