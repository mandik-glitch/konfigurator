// Milwaukee PACKOUT Organiser 4932464082 (standard, 10 nádob). Vlastní parametrický generátor podle fotografií výrobce.
// Souřadnice: X = šířka (čelo +X), Y = délka, Z = výška; počátek = střed obálky 386 × 500 × 117 mm.
// Stavba je rozdělena do modulů p4082_*.mjs (korpus, čelo, víko, nádoby); poznámky k měření: zdroje/4932464082_poznamky.md
import { Group } from './jadro/mesh.js';
import { korpus } from './p4082_korpus.mjs';
import { celo } from './p4082_celo.mjs';
import { vicko } from './p4082_vicko.mjs';
import { nadoby } from './p4082_nadoby.mjs';

export const SKU = '4932464082';
export const OBALKA = { x: 386, y: 500, z: 117 };
export const CELO = 'X';

export function build() {
  const root = new Group(SKU);
  root.addGroup(korpus()); root.addGroup(nadoby()); root.addGroup(celo()); root.addGroup(vicko());
  return root;
}
