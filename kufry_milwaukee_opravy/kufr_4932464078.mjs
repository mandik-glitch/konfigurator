// Milwaukee PACKOUT Pojízdný box s výsuvným držadlem, 4932464078 – OPRAVENÁ verze (vlastní generátor podle fotografií výrobce).
// Souřadnice: X = hloubka 472 (čelo +X), Y = šířka 561, Z = výška 530 (složené madlo nahoře); počátek = střed obálky.
import { Group } from './p4932464078_zaklad.mjs';
import { korpus } from './p4932464078_korpus.mjs';

export const SKU = '4932464078';
export const OBALKA = { x: 472, y: 561, z: 530 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT pojízdný box (4932464078), oprava v6';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus());
  return root;
}
