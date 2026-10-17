// Pojízdný box PACKOUT 4932498651 – společné rozměry (mm). Souřadnice modelu: X = hloubka 480 (čelo se zásuvkou +X), Y = šířka 610 (včetně kol),
// Z = výška 550 (od spodku kol po vrch víka); počátek = střed obálky. Katalogová obálka = ZAVŘENÁ poloha (zásuvka zasunutá, madlo zasunuté).
export const HX = 240, HY = 305, HZ = 275;
export const BY = 257;                       // polovina šířky těla (rohové patky)
export const LIDY = 252;                     // polovina šířky víka
export const Z_LID0 = 228, Z_LID1 = 262, Z_PLATE = 268, Z_TOP = 275;   // víko: spodek, začátek zkosení, deska, vrch
export const Z_BOT = -252;                   // spodní hrana těla (nad zemí), kola sahají do -275
export const ZASUVKA = { y: 218, x0: -184, x1: 231, z0: -198, z1: 207, zdvih: 330 };    // rozměry zásuvky (odhad podle fotek, viz poznámky)
export const KOLO = { r: 114, xc: -126, zc: -161, y0: 258, y1: 305 };            // kolo Ø 228, osa rovnoběžná s Y
export const MADLO = { y: 168, x: -187, a: 32, zdvihHorni: 618, zdvihStredni: 254 };
export const XR = +(process.env.RB_XR ?? -200);        // zadní rovina těla (odhad z fotek; viz poznámky)
