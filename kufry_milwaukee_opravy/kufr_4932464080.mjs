// Milwaukee PACKOUT Box na nářadí 4932464080 (165 × 411 × 561) – stejný parametrický generátor jako 4932464079 (výška = parametr V.H).
import { V80 } from './p4932464079_data.mjs';
import { sestavBox } from './p4932464079_sestav.mjs';
export const SKU = V80.sku;
export const OBALKA = { x: 411, y: 561, z: V80.H };
export const CELO = 'X';
export const NAZEV = V80.nazev;
export function build(opt = {}) { return sestavBox(V80, opt); }
