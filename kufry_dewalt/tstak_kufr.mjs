// Sestavení parametrické skořepiny DeWalt TSTAK IP54: build(H, { celoMadlo }) → kořenová Group (počátek = střed obálky 333 × 440 × H).
import { Group, S } from './tstak_zaklad.mjs';
import { korpus } from './tstak_korpus.mjs';
import { vicko } from './tstak_vicko.mjs';
export const OBALKA_XY = { x: 333, y: 440 };
export function sestav(sku, H, opt = {}) {
  S.H = H;
  const root = new Group(sku);
  root.addGroup(korpus(opt));
  root.addGroup(vicko());
  return root;
}
