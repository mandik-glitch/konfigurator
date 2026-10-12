// DeWalt ToughSystem 2.0 DS400, DWST83342-1 – vlastní parametrický generátor podle fotografií výrobce (dewalt.cz). Sdílená skořepina: ts2_kufr.mjs (výška H = 408).
// Souřadnice: X = hloubka 371 (čelo s logem a západkami do +X), Y = délka 554, Z = výška 408; počátek = střed obálky.
import { postav } from './ts2_kufr.mjs';
export const SKU = 'DWST83342';
export const OBALKA = { x: 371, y: 554, z: 408 };
export const CELO = 'X';
export const NAZEV = 'DeWalt ToughSystem 2.0 DS400 (DWST83342-1)';
export function build() { return postav(408, SKU); }
