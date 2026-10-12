// Hilti Kufr 2-tools (M) SF/SI+TE, číslo Hilti 2329206 (595 × 461 × 175 mm) – vlastní parametrický generátor podle fotografií výrobce (hilti.cz).
// Souřadnice: X = hloubka 461 (čelo s madlem do +X), Y = délka 595, Z = výška 175; počátek = střed obálky.
// Moduly: p2329206_korpus.mjs (spodní díl), p2329206_vicko.mjs (víko, samostatná skupina `vicko` s pivotem na pantu), p2329206_zaklad.mjs (loft půdorysu).
import { Group } from './p2329206_zaklad.mjs';
import { korpus } from './p2329206_korpus.mjs';
import { vicko } from './p2329206_vicko.mjs';

export const SKU = '2329206';
export const OBALKA = { x: 461, y: 595, z: 175 };
export const CELO = 'X';
export const NAZEV = 'Hilti Kufr 2-tools (M) SF/SI+TE (2329206)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  return root;
}
