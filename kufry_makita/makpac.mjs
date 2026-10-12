// Sestavení kufru Makita MAKPAC: build(V) → kořenová Group (korpus + víko s madlem). Počátek = střed obálky 295 × 395 × V.
import { Group, nastavVysku, D, S } from './makpac_zaklad.mjs';
import { korpus } from './makpac_korpus.mjs';
import { vicko } from './makpac_vicko.mjs';

export { D, S };
export function sestav(sku, V) {
  nastavVysku(V);
  const root = new Group(sku);
  root.addGroup(korpus(V));
  root.addGroup(vicko(V));
  return root;
}
