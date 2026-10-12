// Hilti ProKit "Přepravka na nářadí ProKit L" PKC 37-O, číslo Hilti 2441669 - vlastní parametrický generátor podle fotografií výrobce (hilti.cz).
// Je to OTEVŘENÁ přepravka BEZ víka (název "-O", fotografie c01-c03 žádné víko neukazují) - model je tedy jedna skupina `telo`, žádný pohyblivý uzel.
// Souřadnice: X = hloubka 378 (čelo s logem do +X), Y = délka 545, Z = výška 279; počátek = střed obálky.
// Moduly: p2441669_zaklad.mjs (loft, výřezy), p2441669_telo.mjs (vana, doplňky).
import { Group } from './p2441669_zaklad.mjs';
import { telo } from './p2441669_telo.mjs';

export const SKU = '2441669';
export const OBALKA = { x: 378, y: 545, z: 279 };
export const CELO = 'X';
export const NAZEV = 'Hilti ProKit PKC 37-O (2441669)';

export function build() {
  const root = new Group(SKU);
  root.addGroup(telo());
  return root;
}
