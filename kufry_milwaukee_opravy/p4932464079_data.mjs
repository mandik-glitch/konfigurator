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
export const V79 = { ...SPOLECNE, yFront: 0, ringY: 24.5, logoY: 8, sku: '4932464079', nazev: 'Milwaukee PACKOUT Velký box na nářadí (4932464079)', H: 282, horniDrzadlo: true, capT: 50, capB: 31, capUp: 30, capZ0: 11,  // krytky zasahují do rohových výřezů víka o capUp
  // svislé polohy předního hardwaru (z' = výška nad spodní plochou)
  latchTop: 182, latchH: 72, handlePivot: 135, handleH: 81, ringZ: 117, logoZ: 167, tabZ: 0, yLatch: 172 };
export const V80 = { ...SPOLECNE, yFront: 0, ringY: 24.5, logoY: 8, sku: '4932464080', nazev: 'Milwaukee PACKOUT Box na nářadí (4932464080)', H: 165, horniDrzadlo: false, capT: 33, capB: 11, capUp: 25, capZ0: 11,
  latchTop: 83, latchH: 72, handlePivot: 78, handleH: 76, ringZ: 68, logoZ: null, tabZ: 0, yLatch: 172 };
// Box s vložnými panely (elektrikář 4932499703 / instalatér 4932499704): obálka 410 × 560 × 165; bez hliníkových tyčí a rohových krytek (z fotografií sady – viz poznámky).
export const V499703 = { sku: '4932499703', nazev: 'Milwaukee PACKOUT Box pro elektrikáře (4932499703)', H: 165, X: 205, Y: 280,
  xF: 189.2, xR: -197, yB: 274, rohy: false, rTub: 36, rLid: 38, lidH: 62, capUp: 0, horniDrzadlo: false, vnitrekVika: 'panel', lidTyp: 'elektrikar',
  pantX: -198.2, pantZ_off: 3, gripMat: 'cervena', yLatch: 164, yHandle: 112, bar: 0, barX: 0, capT: 0, capB: 0,
  latchTop: 88, latchH: 66, handlePivot: 68, handleH: 60, ringZ: 48, logoZ: null, tabZ: 0,
  // vložné panely (z c01; ladí se podle červených lemů): pravý/levý panel v těle a panel ve víku
  pRx0: -150, pRx1: 146, pRy0: -109, pRy1: 238, pLx0: -143, pLx1: 146, pLy0: -240, pLy1: 70, pVx0: -150, pVx1: 150, pVy: 246 };
