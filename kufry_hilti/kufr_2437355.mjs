// Hilti ProKit "Box na nářadí ProKit" PKC 19, číslo Hilti 2437355 – vlastní parametrický generátor podle fotografií výrobce (hilti.cz); šablona = PKC 35 (2437394).
// Souřadnice: X = hloubka 387 (čelo s madlem do +X), Y = délka 554, Z = výška 168; počátek = střed obálky.
// Moduly: p2437355_korpus.mjs (spodní díl), p2437355_vicko.mjs (víko, samostatná skupina `vicko` s pivotem na pantu).
import { Group } from './p2437355_zaklad.mjs';
import { korpus } from './p2437355_korpus.mjs';
import { vicko } from './p2437355_vicko.mjs';

export const SKU = '2437355';
export const OBALKA = { x: 387, y: 554, z: 168 };
export const CELO = 'X';
export const NAZEV = 'Hilti ProKit PKC 19 (2437355)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  return root;
}
