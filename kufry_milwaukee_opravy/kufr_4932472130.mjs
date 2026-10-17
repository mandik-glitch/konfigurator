// Milwaukee PACKOUT Box se 3 zásuvkami, 4932472130 (opravený model v6 – vlastní parametrický generátor, společné moduly p4932472129_*.mjs).
// Souřadnice: X = hloubka 414 (čelo se zásuvkami do +X), Y = šířka 564, Z = výška 363; počátek = střed obálky.
import { sestav, stejnaCela } from './p4932472129_sestav.mjs';
export const SKU = '4932472130';
export const OBALKA = { x: 414, y: 564, z: 363 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box se 3 zásuvkami (4932472130)';
export const ZASUVKY = 3;
export function build() { return sestav(stejnaCela(3), { jmeno: SKU }); }
