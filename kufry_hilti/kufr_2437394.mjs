// Hilti ProKit "Box na nářadí ProKit L" PKC 35, číslo Hilti 2437394 – vlastní parametrický generátor podle fotografií výrobce (hilti.cz).
// Souřadnice: X = hloubka 387 (čelo s logem do +X), Y = délka 554, Z = výška 267; počátek = střed obálky.
// Moduly: p2437394_korpus.mjs (spodní díl), p2437394_vicko.mjs (víko, samostatná skupina `vicko` s pivotem na pantu).
import { Group } from './p2437394_zaklad.mjs';
import { korpus } from './p2437394_korpus.mjs';
import { vicko } from './p2437394_vicko.mjs';

export const SKU = '2437394';
export const OBALKA = { x: 387, y: 554, z: 267 };
export const CELO = 'X';
export const NAZEV = 'Hilti ProKit PKC 35 (2437394)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  return root;
}
