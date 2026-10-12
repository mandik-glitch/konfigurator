// Parametry rodiny DeWalt ToughSystem 2.0 (DS300 / DS400): shodný půdorys 554 × 371 mm, jediný parametr = výška H (308 / 408).
// Víko má u obou kufrů stejnou výšku (62 mm nad dělicí spárou), celý přírůstek výšky (100 mm) je ve spodním dílu.
// Všechny výšky jsou z' = výška nad spodní plochou (0..H); funkce v ts2_zaklad.mjs je převádějí na Z modelu (z' − H/2).
export const D = { Y: 277, X: 185.5, LID: +(process.env.TS2_LID || 62) };      // polovina délky, polovina hloubky, výška víka nad spárou (odhad z fitu kamery landmarky + obrys, viz poznámky)
export function par(H) {
  const zRim = H - D.LID;                            // dělicí spára korpus / víko (žlutá těsnicí linka)
  return {
    H, zRim,
    zPocket: H - 26,                                 // dno kapsy sklopného madla v horní ploše víka
    zIn: 14,                                         // spodní okraj čelního vybrání (loga)
    yLatch: 188,                                     // osa čelních západek (Y = ±188)
    pivotVicko: [-181, 0, zRim + 2],                 // osa pantu (zadní hrana, v z' = zRim + 2)
  };
}
// snímek půdorysu (jako v Hilti generátoru): z, xf (čelo), xr (zadek), y (poloviční délka), yF (konec rovné čelní hrany), cfx (hloubka zkosení rohu), rr (zadní rohy)
export const F = (z, xf, xr, y, yF, cfx = 22, rr = 10, wx = 4, wy = 4) => ({ z, xf, xr, y0: -y, y1: y, yF, cfx, rr, wx, wy, ns: 4 });
export const nl = fr => ({ fr });
