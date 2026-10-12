// DeWalt TSTAK II IP54 mělký (DWST83345-1) – stejná skořepina jako DWST83346 (tstak_*.mjs), výška 162 mm; v kapse čelní madlo.
// Souřadnice: X = hloubka 333 (čelo se západkami do +X), Y = délka 440, Z = výška 162; počátek = střed obálky.
import { sestav } from './tstak_kufr.mjs';
export const SKU = 'DWST83345';
export const OBALKA = { x: 333, y: 440, z: 162 };
export const CELO = 'X';
export const NAZEV = 'DeWalt TSTAK II IP54 mělký (DWST83345-1)';
export const build = () => sestav(SKU, OBALKA.z, { celoMadlo: true });
