// DeWalt ToughSystem 2.0 DS300, DWST83294-1 – vlastní parametrický generátor podle fotografií výrobce (dewalt.cz). Sdílená skořepina: ts2_kufr.mjs (výška H = 308).
// Souřadnice: X = hloubka 371 (čelo s logem a západkami do +X), Y = délka 554, Z = výška 308; počátek = střed obálky.
import { postav } from './ts2_kufr.mjs';
export const SKU = 'DWST83294';
export const OBALKA = { x: 371, y: 554, z: 308 };
export const CELO = 'X';
export const NAZEV = 'DeWalt ToughSystem 2.0 DS300 (DWST83294-1)';
export function build() { return postav(308, SKU); }
