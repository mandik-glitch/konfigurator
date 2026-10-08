// Vypocet: clenita noha se spodnim zadnim profilem (sloupek-pred-podbehem) az k podlaze pro nohy K-020 A.
const L = require("./k020_lib.js");
const { T, D } = L;
const ctx = L.makeCtx();
const front = L.placeFrontLeg(ctx);
const legZ = [front.anchorZ + ctx.dirAway * (T + 832), front.anchorZ + ctx.dirAway * (T + 832 + T + 430)];
legZ.forEach((z, i) => {
  const leg = L.legAt(ctx, z);
  const r = L.sloupekKPodlazeWallNear(ctx, z, leg.yNew);
  let celaNohaKoliduje = null, spojniceDelka = null;
  if (r) {
    const parts = ctx.toWorld(L.buildVyrez(leg.yNew, 0, r.wallNear), z);
    celaNohaKoliduje = ctx.collides(parts);
    spojniceDelka = (D - r.wallNear - T) - T;
  }
  console.log(JSON.stringify({ noha: i + 1, anchorZ: +z.toFixed(1), typ: leg.type, yNew: leg.yNew, dosavadniPataSloupku: leg.sb, dosavadniOdSteny: L.SLOUPEK_WALL_NEAR, kPodlaze: r, spojniceDolniDelka: spojniceDelka, celaNohaKoliduje }));
});
