// DeWalt TSTAK IP54 hluboký (DWST83346-1) – vlastní parametrický generátor podle fotografií výrobce (dewalt.cz); sdílená skořepina = tstak_*.mjs.
// Souřadnice: X = hloubka 333 (čelo se západkami do +X), Y = délka 440, Z = výška 302; počátek = střed obálky. Víko = skupina `vicko` (pivot odhadnut na zadní hraně spáry).
import { sestav } from './tstak_kufr.mjs';
export const SKU = 'DWST83346';
export const OBALKA = { x: 333, y: 440, z: 302 };
export const CELO = 'X';
export const NAZEV = 'DeWalt TSTAK IP54 hluboký (DWST83346-1)';
export const build = () => sestav(SKU, OBALKA.z, { celoMadlo: false });
