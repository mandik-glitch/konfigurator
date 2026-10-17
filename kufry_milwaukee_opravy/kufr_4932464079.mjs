// Milwaukee PACKOUT Velký box na nářadí 4932464079 (282 × 411 × 561) – společný parametrický generátor s 4932464080 (výška = parametr).
// Souřadnice: X = hloubka 411 (čelo +X), Y = délka 561, Z = výška 282; počátek = střed obálky.
import { Group, nastavVysku } from './p4932464079_zaklad.mjs';
import { V79 } from './p4932464079_data.mjs';
import { sestavBox } from './p4932464079_sestav.mjs';

export const SKU = V79.sku;
export const OBALKA = { x: 411, y: 561, z: V79.H };
export const CELO = 'X';
export const NAZEV = V79.nazev;
export const VARIANTY = [{ soubor: '4932464079', opt: {} }, { soubor: '4932464079_drzadlo_nahore', opt: { drzadloNahore: true }, mimoObalku: true }];
export function build(opt = {}) { return sestavBox(V79, opt); }
