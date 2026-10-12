// Hilti ProKit "Box na nářadí ProKit XL" PKC 61, číslo Hilti 2437354 – vlastní parametrický generátor podle fotografií výrobce (hilti.cz).
// Souřadnice: X = hloubka 387 (čelo s logem do +X), Y = délka 561, Z = výška 422; počátek = střed obálky.
// Moduly: p2437354_korpus.mjs (spodní díl, boční madla), p2437354_vicko.mjs (víko, samostatná skupina `vicko` s pivotem na pantu).
import { Group } from './p2437354_zaklad.mjs';
import { korpus } from './p2437354_korpus.mjs';
import { vicko } from './p2437354_vicko.mjs';

export const SKU = '2437354';
export const OBALKA = { x: 387, y: 561, z: 422 };
export const CELO = 'X';
export const NAZEV = 'Hilti ProKit PKC 61 (2437354)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  return root;
}
