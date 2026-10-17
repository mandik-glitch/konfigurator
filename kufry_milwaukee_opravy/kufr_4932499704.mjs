// Milwaukee PACKOUT Box pro instalatéry 4932499704 (165 × 410 × 560): STEJNÝ model jako 4932499703 (box pro elektrikáře), jen jiné SKU v meta.
// Důvod: výrobce používá pro obě SKU totožnou fotografii (Hero_1, md5 shodné), Hero_2–5 neexistují (404) a doplňkové fotografie sad (4932499466 elektrikář / 4932499467 instalatér)
// ukazují stejný box se stejnými panely; rozdíl je jen v nářadí (viz zdroje/4932499704_poznamky.md). Model proto sdílí generátor (kufr_4932499703.mjs).
import { build as build703, OBALKA, CELO } from './kufr_4932499703.mjs';
export const SKU = '4932499704';
export { OBALKA, CELO };
export const NAZEV = 'Milwaukee PACKOUT Box pro instalatéry (4932499704) – shodný model s 4932499703';
export function build(opt = {}) { return build703({ ...opt, sku: SKU, nazev: NAZEV }); }
