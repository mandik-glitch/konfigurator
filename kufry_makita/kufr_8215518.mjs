// Makita MAKPAC Typ 3 (číslo Makita 821551-8), obálka 395 × 295 × 210 mm – vlastní parametrický generátor podle fotografií výrobce (makitauk.com / makitamedia.com).
// Souřadnice: X = hloubka 295 (čelo se západkami a madlem do +X), Y = délka 395, Z = výška 210; počátek = střed obálky.
// Všechny čtyři typy sdílejí korpus i víko (makpac*.mjs), liší se jen výškou; víko = skupina `vicko` (pivot na pantové hraně), madlo = vnořená skupina `madlo`.
import { sestav } from './makpac.mjs';

export const SKU = '8215518';
export const OBALKA = { x: 295, y: 395, z: 210 };
export const CELO = 'X';
export const NAZEV = 'Makita MAKPAC Typ 3 (821551-8)';
export const VYSKA = 210;

export function build() { return sestav(SKU, VYSKA); }
