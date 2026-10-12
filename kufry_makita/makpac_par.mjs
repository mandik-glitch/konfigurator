// Parametry a půdorysné snímky MAKPAC Typ 1–4 (společné všem čtyřem typům; jediný parametr je výška V).
// Míry jsou z čelního pohledu 821552-6 c09 (téměř kolmý, 1000 px = 395 mm → 2,405 px/mm) a šikmých fotografií; viz zdroje/*_poznamky.md.
// Co nejde změřit (hloubky výřezů, zadní stěna), je v poznámkách označeno „odhad“/„neověřeno“.
import { XF, XR, YH } from './makpac_zaklad.mjs';

export const LID = 26;                 // výška víka (spára korpus/víko je 26 mm pod horní plochou) – c09 py 17..80 (2,405 px/mm)
export const R_ROH = 8;                // poloměr svislých rohů v půdorysu (odhad z šikmých fotografií)
export const Y_ZAP = [140, 181];       // západkový/nožkový výřez (Y od osy) – c09 px 65..163 / 837..933
export const Y_PANEL = 84.4;           // polovina šířky vtlačeného čelního panelu – c09 px 297..703
export const DZ_PANEL = 52;            // horní hrana panelu pod horní plochou – c09 py 145
export const Y_PRST = 52;              // polovina šířky prstové jamky v čele víka – c09 px 375..625

export function par(H) {
  const zS = H - LID;
  // snímek půdorysu: iF = odsazení čelní/zadní roviny, iE = odsazení konců (zaoblení hran)
  const F = (z, iF = 0, iE = iF) => ({ z, xf: XF - iF, xr: XR + iF, y0: -YH + iE, y1: YH - iE, rf: R_ROH - iE * 0.5, rr: R_ROH - iE * 0.5 });
  const frames = [
    F(0, 2.4, 3.2), F(1, 1.2, 1.7), F(2.5, 0.5, 0.65), F(4.5, 0, 0),
    F(zS - 0.6, 0, 0), F(zS, 0.6, 0.6), F(zS + 1e-4, 0.6, 0.6), F(zS + 0.6, 0, 0),
    F(H - 7, 0, 0), F(H - 5, 0.1, 0.3), F(H - 4, 0.15, 0.68), F(H - 3, 0.3, 1.26), F(H - 2, 0.6, 2.1), F(H - 1, 1.0, 3.4), F(H, 1.6, 6.2),
  ];
  // výřezy: [a0, a1] podél strany; d = hloubka od vnějšího povrchu
  const fr = (z, a0, a1, d) => ({ z, a0, a1, d });
  const notches = [], slit = H - 77.6 < 46.7;      // u nízkého Typu 1 se kapsa západky a nožky slévají
  for (const s of [-1, 1]) {
    const y0 = s < 0 ? -Y_ZAP[1] : Y_ZAP[0], y1 = s < 0 ? -Y_ZAP[0] : Y_ZAP[1];
    if (slit) notches.push({ side: 'F', name: 'zapadka', fr: [fr(0, y0, y1, 13), fr(H - 5.3, y0, y1, 13)] });   // Typ 1: kapsa západky plynule přechází do nožkové kapsy
    else {
      notches.push({ side: 'F', name: 'zapadka', fr: [fr(H - 77.6, y0, y1, 13), fr(H - 5.3, y0, y1, 13)] });     // kapsa západky
      notches.push({ side: 'F', name: 'nozka', fr: [fr(0, y0, y1, 12), fr(45.7, y0, y1, 12)] });                 // kapsa pro západku spodního kufru (stohování)
    }
  }
  // vtlačený čelní panel (horní rohy zaoblené R 17 mm), hloubka 2 mm
  {
    const f = [fr(2.5, -Y_PANEL, Y_PANEL, 2)], r = 17, yc = Y_PANEL - r, zc0 = H - DZ_PANEL - r;
    for (let k = 0; k <= 6; k++) { const th = (90 * k / 6) * Math.PI / 180, y = yc + r * Math.cos(th); f.push(fr(zc0 + r * Math.sin(th), -y, y, 2)); }
    notches.push({ side: 'F', name: 'panel', fr: f });
  }
  // prstová jamka v čele víka (nad panelem, uprostřed)
  notches.push({ side: 'F', name: 'prst', fr: [fr(H - 20, -40, 40, 4), fr(H - 16, -48, 48, 8), fr(H - 8, -Y_PRST, Y_PRST, 12), fr(H, -Y_PRST, Y_PRST, 14)] });
  // konce (±Y): vtlačený panel, kapsa zadní západky (pantu), zadní nožková kapsa, štěrbina u přední hrany
  notches.push({ side: 'E', name: 'panel_konec', fr: [fr(2.5, -46, 120, 2), fr(H - 54, -46, 120, 2)] });
  if (slit) notches.push({ side: 'E', name: 'zapadka_zadni', fr: [fr(0, -128, -84, 13), fr(H - 5.3, -128, -84, 13)] });
  else {
    notches.push({ side: 'E', name: 'zapadka_zadni', fr: [fr(H - 77.6, -128, -84, 13), fr(H - 5.3, -128, -84, 13)] });
    notches.push({ side: 'E', name: 'nozka_zadni', fr: [fr(0, -128, -84, 12), fr(45.7, -128, -84, 12)] });
  }
  notches.push({ side: 'E', name: 'stesbina', fr: [fr(10, 139, 145, 6), fr(H - 82, 139, 145, 6)] });
  return { H, zS, frames, notches };
}
