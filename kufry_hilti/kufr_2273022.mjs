// Hilti Kufr SF 4(H)-22 prázdný, č. 2273022, 395 × 362 × 119 mm (hilti.cz) – vlastní parametrický generátor podle jediné (generické) čelní fotografie L137214.
// Souřadnice: X = hloubka 119 (čelo s logem do +X), Y = délka 395, Z = výška 362 (držadlo nahoře); počátek = střed obálky. Víko = skupina `vicko` (pivot na spodní pantové hraně, osa Y).
// Moduly: sdílené p2284143_zaklad/korpus/vicko.mjs (stejný generátor řady SF; jiné rozměry a poměr fotografie), parametry jsou v tomto souboru.
import { mk, Group } from './p2284143_zaklad.mjs';
import { korpus } from './p2284143_korpus.mjs';
import { vicko } from './p2284143_vicko.mjs';

export const SKU = '2273022';
export const OBALKA = { x: 119, y: 395, z: 362 };
export const CELO = 'X';
export const NAZEV = 'Hilti Kufr SF 4(H)-22 (2273022)';

export function build() {
  const K = mk({ sku: SKU, L: OBALKA.y, H: OBALKA.z, D: OBALKA.x });
  const root = new Group(SKU);
  root.addGroup(korpus(K));
  root.addGroup(vicko(K));
  return root;
}
