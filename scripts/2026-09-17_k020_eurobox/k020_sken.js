// Diagnosticky sken K-020: predni noha + profil podbehu/stropu podel steny po 25mm az k zadni hrane.
const L = require("./k020_lib.js");
const t0 = Date.now();
const ctx = L.makeCtx();
const front = L.placeFrontLeg(ctx);
console.log(JSON.stringify({ mirror: ctx.mirror, dirZtoBulkhead: ctx.dirZtoBulkhead, offsetX: ctx.offsetX, offsetY: ctx.offsetY, front, H: L.H, TOP_Y: L.TOP_Y, CAP_H: L.CAP_H, CAP_X: L.CAP_X, SLOUPEK_X: L.SLOUPEK_X }));
const hard = ctx.dirAway > 0 ? ctx.boxL0.max.z : ctx.boxL0.min.z;
const rows = [];
for (let dz = 0; ; dz += 25) {
  const aZ = front.anchorZ + ctx.dirAway * dz;
  if (ctx.dirAway > 0 ? aZ + L.T > hard : aZ < hard) break;
  const plainOk = !ctx.collides(ctx.toWorld(L.buildPlain(), aZ));
  const exist = L.existenceCollides(ctx, aZ);
  let yNew = null, sb = null, leg = null;
  if (!plainOk && !exist) { yNew = L.yNewWallAt(ctx, aZ); sb = L.sloupekBottomAt(ctx, aZ, yNew); leg = L.legAt(ctx, aZ); }
  rows.push({ dz, aZ: +aZ.toFixed(1), plainOk, existenceKolize: exist, yNew, sb, vyrezOk: leg ? leg.type : null });
}
rows.forEach(r => console.log(`dz=${String(r.dz).padStart(5)} aZ=${String(r.aZ).padStart(8)} plain=${r.plainOk ? "OK " : "kol"} strop/cap/predni=${r.existenceKolize ? "KOL" : "ok "} yNew=${r.yNew} sb=${r.sb} vyrez=${r.vyrezOk}`));
console.log("sekund", (Date.now() - t0) / 1000);
