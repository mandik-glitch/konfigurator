// Milwaukee PACKOUT Box se 2 zásuvkami, 4932472129 (opravený model v6 – vlastní parametrický generátor, společné moduly p4932472129_*.mjs).
// Souřadnice: X = hloubka 414 (čelo se zásuvkami do +X), Y = šířka 564, Z = výška 363; počátek = střed obálky.
import { sestav } from './p4932472129_sestav.mjs';
export const SKU = '4932472129';
export const OBALKA = { x: 414, y: 564, z: 363 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box se 2 zásuvkami (4932472129)';
export const ZASUVKY = 2;
// hrany mezer z fotek c01/c02 (poměr k hranám rámu čela, kalibrováno na čelní fotografii 3189 c01): střed mezer ≈ +2,1 mm
export const CELA = [{ z1: 144, z0: 4.1 }, { z1: 0.1, z0: -138 }];
export function build() { return sestav(CELA, { jmeno: SKU, stredCerveny: true }); }
