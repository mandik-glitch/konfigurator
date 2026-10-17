// Milwaukee PACKOUT Box se zásuvkami 2 + 1, 4932493190 (opravený model v6 – vlastní parametrický generátor, společné moduly p4932472129_*.mjs).
// Souřadnice: X = hloubka 414 (čelo se zásuvkami do +X), Y = šířka 564, Z = výška 363; počátek = střed obálky.
// 2 nízké zásuvky nahoře (stejné jako horní dvě u 4932493189) + 1 vysoká dole (výška ≈ 2 nízké + mezera; poměr 1 : 1 : ≈1,9–2,0 z čelní fotografie c01).
import { sestav } from './p4932472129_sestav.mjs';
export const SKU = '4932493190';
export const OBALKA = { x: 414, y: 564, z: 363 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box se zásuvkami 2 + 1 (4932493190)';
export const ZASUVKY = 3;
export const CELA = [{ z1: 144, z0: 77 }, { z1: 73.2, z0: 4.3 }, { z1: 1, z0: -138 }];
export function build() { return sestav(CELA, { jmeno: SKU }); }
