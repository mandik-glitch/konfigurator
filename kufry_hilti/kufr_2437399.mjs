// Hilti ProKit PKC 18-H "ProKit box s poloviční šířkou", číslo Hilti 2437399 – vlastní parametrický generátor podle fotografií výrobce (hilti.cz).
// Souřadnice: X = hloubka 389 (čelo s logem do +X), Y = šířka čela 275, Z = výška 295; počátek = střed obálky.
// Moduly: p2437399_korpus.mjs (spodní díl), p2437399_vicko.mjs (víko, samostatná skupina `vicko` s pivotem na pantu).
import { Group } from './p2437399_zaklad.mjs';
import { korpus } from './p2437399_korpus.mjs';
import { vicko } from './p2437399_vicko.mjs';

export const SKU = '2437399';
export const OBALKA = { x: 389, y: 275, z: 295 };
export const CELO = 'X';
export const NAZEV = 'Hilti ProKit PKC 18-H (2437399)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  root.addGroup(vicko());
  return root;
}
