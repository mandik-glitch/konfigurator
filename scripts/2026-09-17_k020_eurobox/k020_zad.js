// Diagnostika zadni hranice pro 2. dvouboxovy sloupec: ktery kus nohy koliduje a jak vysoko smi noha byt.
const L = require("./k020_lib.js");
const { T, D, H, TOP_Y, CAP_X } = L;
const ctx = L.makeCtx();
const front = L.placeFrontLeg(ctx);
const leg0 = { type: "plain", anchorZ: front.anchorZ };
const leg1Z = front.anchorZ + ctx.dirAway * (T + 832);
const leg2Z = leg1Z + ctx.dirAway * (T + 832);
console.log(`front=${front.anchorZ.toFixed(1)} leg1Z=${leg1Z.toFixed(1)} (dz ${(leg1Z - front.anchorZ).toFixed(0)}) leg2Z=${leg2Z.toFixed(1)} (dz ${(leg2Z - front.anchorZ).toFixed(0)})`);
// po 5mm od dz 1600 do 1800: jednotlive kusy
function maxTopFree(localX, y0, aZ, yMax) {
  // nejvyssi horni konec [y0,top], ktery nekoliduje (krokovani nahoru po 1mm)
  if (ctx.collides(ctx.piece(localX, y0, y0 + 1, aZ))) return null;
  let top = y0 + 1;
  while (top < yMax && !ctx.collides(ctx.piece(localX, y0, top + 1, aZ))) top++;
  return top;
}
for (let dz = 1600; dz <= 1800; dz += 10) {
  const aZ = front.anchorZ + ctx.dirAway * dz;
  const wallBand = ctx.collides(ctx.piece(D - T / 2, TOP_Y - 40, TOP_Y, aZ));
  const cap = ctx.collides(ctx.piece(CAP_X, TOP_Y, H, aZ));
  const predni = ctx.collides(ctx.piece(T / 2, 0, H, aZ));
  const wallTop = maxTopFree(D - T / 2, 700, aZ, 1300);
  const capTop = maxTopFree(CAP_X, 700, aZ, 1300);
  const predniTop = maxTopFree(T / 2, 700, aZ, 1300);
  const yNew = L.yNewWallAt(ctx, aZ);
  console.log(`dz=${dz} aZ=${aZ.toFixed(0)} pasStena(800-840)=${wallBand ? "KOL" : "ok"} cap(840-${H})=${cap ? "KOL" : "ok"} predni(0-${H})=${predni ? "KOL" : "ok"} | max volny vrch: stena=${wallTop} cap=${capTop} predni=${predniTop} | yNew=${yNew}`);
}
