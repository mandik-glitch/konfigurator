// Hilti Kufr SF 6(H)-22 prázdný, č. 2284143, 444 × 395 × 122 mm (hilti.cz) – vlastní parametrický generátor podle jediné (generické) čelní fotografie L137214.
// Souřadnice: X = hloubka 122 (čelo s logem do +X), Y = délka 444, Z = výška 395 (držadlo nahoře); počátek = střed obálky. Víko = skupina `vicko` (pivot na spodní pantové hraně, osa Y).
// Moduly: p2284143_zaklad.mjs (společný základ řady), p2284143_korpus.mjs, p2284143_vicko.mjs.
import { mk, Group } from './p2284143_zaklad.mjs';
import { korpus } from './p2284143_korpus.mjs';
import { vicko } from './p2284143_vicko.mjs';

export const SKU = '2284143';
export const OBALKA = { x: 122, y: 444, z: 395 };
export const CELO = 'X';
export const NAZEV = 'Hilti Kufr SF 6(H)-22 (2284143)';

export function build() {
  const K = mk({ sku: SKU, L: OBALKA.y, H: OBALKA.z, D: OBALKA.x });
  const root = new Group(SKU);
  root.addGroup(korpus(K));
  root.addGroup(vicko(K));
  return root;
}
