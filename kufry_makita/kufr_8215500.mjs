// Makita MAKPAC Typ 2 (číslo Makita 821550-0), obálka 395 × 295 × 157 mm – vlastní parametrický generátor podle fotografií výrobce (makitauk.com / makitamedia.com).
// Souřadnice: X = hloubka 295 (čelo se západkami a madlem do +X), Y = délka 395, Z = výška 157; počátek = střed obálky.
// Všechny čtyři typy sdílejí korpus i víko (makpac*.mjs), liší se jen výškou; víko = skupina `vicko` (pivot na pantové hraně), madlo = vnořená skupina `madlo`.
import { sestav } from './makpac.mjs';

export const SKU = '8215500';
export const OBALKA = { x: 295, y: 395, z: 157 };
export const CELO = 'X';
export const NAZEV = 'Makita MAKPAC Typ 2 (821550-0)';
export const VYSKA = 157;

export function build() { return sestav(SKU, VYSKA); }
