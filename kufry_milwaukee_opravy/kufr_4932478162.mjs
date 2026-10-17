// Milwaukee PACKOUT XL Box 4932478162 (katalog 394 × 554 × 422): vlastní generátor podle fotografií výrobce.
// Souřadnice: X = hloubka 394 (čelo s logem a sponami do +X), Y = šířka 554, Z = výška 422; počátek = střed obálky.
// Moduly p4932478162_*.mjs jsou společný základ i pro revizi 4932501784 (ta přidává zdvižitelné U-madlo).
import { Group } from './p4932478162_zaklad.mjs';
import { zakladXL } from './p4932478162_sestav.mjs';

export const SKU = '4932478162';
export const OBALKA = { x: 394, y: 554, z: 422 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT XL Box (4932478162)';

export function build() {
  const root = new Group(SKU);
  return zakladXL(root);
}
