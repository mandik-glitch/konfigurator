// Společná data a parametry generátoru Milwaukee PACKOUT "Velký box" 4932464079 (V = 282) a "Box" 4932464080 (V = 165).
// Souřadnice: X = hloubka (čelo +X, pant -X), Y = délka (561), Z = výška; počátek = střed obálky 411 × 561 × V.
// Výšky v modulech jsou z' = výška nad nejnižším bodem (0..V); převod na Z modelu: z' - V/2 (viz zaklad).
// Rozměry v mm. Co je změřeno / odhad / neověřeno: zdroje/<SKU>_poznamky.md.
export const SPOLECNE = {
  X: 205.5, Y: 280.5,             // polovina obálky (katalog 411 × 561)
  xF: 190, xR: -197, yB: 275.5,     // vana: čelní a zadní rovina stěny; polovina délky (koncové stěny)
  xN: 149.5, yN: 222.5,           // výřez rohu vany (okno kolem rohové tyče): koncová stěna končí v |X| = xN, čelní/zadní v |Y| = yN
  bar: 29, barX: 8,               // průřez hliníkové tyče: 29 (Y) × 8 (X) – plochá extruze (z šířky viditelných ploch na c01)
  lidH: 75,                       // výška víka nad švíkem (vnější spodní hrana víka)
  pantX: -198.2, pantZ_off: 3,      // osa pantu (X, výška nad švíkem)
  yLatch: 170,                    // střed západky (±Y)
  yHandle: 115,                   // polovina šířky červené rukojeti
};
export const V79 = { ...SPOLECNE, sku: '4932464079', nazev: 'Milwaukee PACKOUT Velký box na nářadí (4932464079)', H: 282, horniDrzadlo: true, capT: 50, capB: 31, capUp: 30, capZ0: 11,  // krytky zasahují do rohových výřezů víka o capUp
  // svislé polohy předního hardwaru (z' = výška nad spodní plochou)
  latchTop: 168, latchH: 68, handlePivot: 125, handleH: 85, ringZ: 115, logoZ: 167, tabZ: 0 };
export const V80 = { ...SPOLECNE, sku: '4932464080', nazev: 'Milwaukee PACKOUT Box na nářadí (4932464080)', H: 165, horniDrzadlo: false, capT: 33, capB: 11, capUp: 25, capZ0: 11,
  latchTop: 83, latchH: 69, handlePivot: 84, handleH: 80, ringZ: 70, logoZ: null, tabZ: 0 };
// Box s vložnými panely (elektrikář 4932499703 / instalatér 4932499704): obálka 410 × 560 × 165; bez hliníkových tyčí a rohových krytek (z fotografií sady – viz poznámky).
export const V499703 = { sku: '4932499703', nazev: 'Milwaukee PACKOUT Box pro elektrikáře (4932499703)', H: 165, X: 205, Y: 280,
  xF: 190, xR: -197, yB: 274, rohy: false, rTub: 36, rLid: 38, lidH: 62, capUp: 0, horniDrzadlo: false, vnitrekVika: 'panel', lidTyp: 'elektrikar',
  pantX: -198.2, pantZ_off: 3, gripMat: 'cervena', yLatch: 155, yHandle: 112, bar: 0, barX: 0, capT: 0, capB: 0,
  latchTop: 92, latchH: 62, handlePivot: 74, handleH: 58, ringZ: 56, logoZ: null, tabZ: 0 };
