// Makita MAKPAC Typ 1 (číslo Makita 821549-5), obálka 395 × 295 × 105 mm – vlastní parametrický generátor podle fotografií výrobce (makitauk.com / makitamedia.com).
// Souřadnice: X = hloubka 295 (čelo se západkami a madlem do +X), Y = délka 395, Z = výška 105; počátek = střed obálky.
// Všechny čtyři typy sdílejí korpus i víko (makpac*.mjs), liší se jen výškou; víko = skupina `vicko` (pivot na pantové hraně), madlo = vnořená skupina `madlo`.
import { sestav } from './makpac.mjs';

export const SKU = '8215495';
export const OBALKA = { x: 295, y: 395, z: 105 };
export const CELO = 'X';
export const NAZEV = 'Makita MAKPAC Typ 1 (821549-5)';
export const VYSKA = 105;

export function build() { return sestav(SKU, VYSKA); }
