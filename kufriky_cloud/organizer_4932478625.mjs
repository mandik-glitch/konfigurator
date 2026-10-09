// Milwaukee PACKOUT Deep Organiser 4932478625 (hluboký organizér, 8 oddílů, 6 červených vyjímatelných děličů).
// VLASTNÍ parametrický generátor podle fotografií výrobce; konstrukce převzata z modelu 4932464082 (p4082_*.mjs), rozměry a výšky
// podle fotografií tohoto SKU. Moduly p8625_*.mjs; poznámky k měření: zdroje/4932478625_poznamky.md.
// Souřadnice (mm): X = šířka (čelo +X), Y = délka, Z = výška; počátek = střed obálky 386 × 507 × 178.
import { Group } from './jadro/mesh.js';
import { korpus } from './p8625_korpus.mjs';
import { celo } from './p8625_celo.mjs';
import { vicko } from './p8625_vicko.mjs';
import { vnitrek, delice } from './p8625_vnitrek.mjs';

export const SKU = '4932478625';
export const OBALKA = { x: 386, y: 507, z: 178 };
export const CELO = 'X';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(vnitrek()); root.addGroup(delice()); root.addGroup(celo()); root.addGroup(vicko());
  return root;
}
