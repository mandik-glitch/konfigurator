// Milwaukee PACKOUT Box se 4 zásuvkami, 4932493189 (opravený model v6 – vlastní parametrický generátor, společné moduly p4932472129_*.mjs).
// Souřadnice: X = hloubka 414 (čelo se zásuvkami do +X), Y = šířka 564, Z = výška 363; počátek = střed obálky.
// Čela změřena z čelní fotografie c01 (hrany mezer ve z +75, +2,6, −70, ±3 mm; viz zdroje/4932493189_poznamky.md).
import { sestav } from './p4932472129_sestav.mjs';
export const SKU = '4932493189';
export const OBALKA = { x: 414, y: 564, z: 363 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box se 4 zásuvkami (4932493189)';
export const ZASUVKY = 4;
export const CELA = [{ z1: 144, z0: 77 }, { z1: 73.2, z0: 4.3 }, { z1: 1, z0: -68 }, { z1: -72.5, z0: -138 }];
export function build() { return sestav(CELA, { jmeno: SKU }); }
