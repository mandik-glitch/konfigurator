// Milwaukee PACKOUT Box pro elektrikáře 4932499703 (165 × 410 × 560) – box s vložnými panely. Stejný model (jiné SKU v meta) má i 4932499704 (box pro instalatéry).
// Souřadnice: X = hloubka 410 (čelo +X), Y = délka 560, Z = výška 165; počátek = střed obálky.
import { Group, nastavVysku } from './p4932464079_zaklad.mjs';
import { V499703 } from './p4932464079_data.mjs';
import { sestavBox } from './p4932464079_sestav.mjs';
import { vlozkyTelo, vlozkaVicko } from './p4932499703_vnitrek.mjs';

export const SKU = '4932499703';
export const OBALKA = { x: 410, y: 560, z: 165 };
export const CELO = 'X';
export const NAZEV = 'Milwaukee PACKOUT Box pro elektrikáře (4932499703)';
export function build(opt = {}) {
  const V = { ...V499703, sku: opt.sku || SKU, nazev: opt.nazev || NAZEV, doplnky: [(V, root, vk) => { root.addGroup(vlozkyTelo(V)); vlozkaVicko(V, vk); }] };
  return sestavBox(V, opt);
}
