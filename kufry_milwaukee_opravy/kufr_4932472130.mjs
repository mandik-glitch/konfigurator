// Milwaukee PACKOUT Box se 3 zásuvkami, 4932472130 (opravený model v6 – vlastní parametrický generátor, společné moduly p4932472129_*.mjs).
// Souřadnice: X = hloubka 414 (čelo se zásuvkami do +X), Y = šířka 564, Z = výška 363; počátek = střed obálky.
import { sestav } from './p4932472129_sestav.mjs';
export const SKU = '4932472130';
export const OBALKA = { x: 414, y: 564, z: 363 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box se 3 zásuvkami (4932472130)';
export const ZASUVKY = 3;
// hrany mezer z fotek c01/c02 (poměr k hranám rámu čela, kalibrováno na čelní fotografii 3189 c01): střed mezer ≈ +50,7 a −46,8 mm
export const CELA = [{ z1: 144, z0: 52.7 }, { z1: 48.7, z0: -44.8 }, { z1: -48.8, z0: -138 }];
export function build() { return sestav(CELA, { jmeno: SKU, stredCerveny: true }); }
