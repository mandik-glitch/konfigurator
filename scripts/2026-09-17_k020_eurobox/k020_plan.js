// Planovani sloupcu K-020: pro kazdy sloupec zkousi N=3,2,1 (Robert: nejdriv 3boxovy),
// meri: typ a adaptaci zadni nohy, luzko (nosniky+spojnice) na 200mm, podlahu sloupce
// (max(200, Y_new) + fresh krokovani nosniku pres cely rozpon, +30 podbeh), fyzicky strop
// (siroka sonda D x rozpon), pocet pater (30mm mezera, nosnik stred <= TOP_Y-T/2).
const THREE = require("three");
const L = require("./k020_lib.js");
const { T, D, H, TOP_Y } = L;

function measureColumn(ctx, legFrom, N) {
  const nz = legFrom.anchorZ + ctx.dirAway * (T + L.CLEAR_SPACING[N]);
  const leg = L.legAt(ctx, nz);
  const r = { N, legToAnchorZ: +nz.toFixed(1), dzOdPrepazky: null, leg };
  if (!leg) { r.vysledek = "noha nejde postavit (za zadni hranici / kolize)"; return r; }
  const railsAt = floorY => L.railsFor(ctx, N, legFrom, leg, floorY + T / 2).parts;
  r.luzko200koliduje = ctx.collides(railsAt(200));
  const yNews = [legFrom, leg].filter(l => l.type === "vyrez").map(l => l.yNew);
  const base = Math.max(200, ...yNews);
  let floor = base;
  if (ctx.collides(railsAt(base))) {
    let y = base, clear = null;
    for (let s = 0; s < 700; s++) { y++; if (!ctx.collides(railsAt(y))) { clear = y; break; } }
    if (clear === null) { r.vysledek = "luzko nenalezlo bezkolizni vysku"; return r; }
    floor = clear + L.PODBEH_CLEARANCE;
    if (ctx.collides(railsAt(floor))) { r.vysledek = "luzko po +30 koliduje"; return r; }
  }
  r.floorBase = base; r.floorY = floor;
  // cele sestava noh + luzko v podlaze nesmi kolidovat
  r.legKoliduje = ctx.collides(ctx.toWorld(L.legParts(leg), leg.anchorZ));
  // fyzicky strop siroka sonda
  const rr = L.railsFor(ctx, N, legFrom, leg, 0);
  const slab = y => { const m = new THREE.Mesh(new THREE.BoxGeometry(D, 10, rr.len)); m.position.set(ctx.offsetX + ctx.sgn * (D / 2), y + ctx.offsetY, (rr.zFrom + rr.zTo) / 2); m.updateMatrixWorld(true); return m; };
  let y = floor + T, hit = null;
  for (let s = 0; s < 1200; s++) { y++; if (ctx.collidesWithWalls(slab(y))) { hit = y; break; } }
  r.physCeil = hit === null ? null : hit - 2;
  // maximalni pocet pater s nejmensim boxem (120) - kapacita
  const maxRailCenter = TOP_Y - T / 2;
  let railTop = floor + T, levels = 0;
  const topLimit = Math.min(H, r.physCeil == null ? H : r.physCeil);
  while (true) {
    const railCenter = railTop - T / 2;
    if (railCenter > maxRailCenter + 1e-6) break;
    const topIfTop = railTop + (120 - 12);
    if (topIfTop > topLimit) break;
    levels++;
    railTop = railTop + (120 - 12) + 30 + T;
  }
  r.maxPater120 = levels;
  r.vysledek = "OK";
  return r;
}

const t0 = Date.now();
const ctx = L.makeCtx();
const front = L.placeFrontLeg(ctx);
const leg0 = { type: "plain", anchorZ: front.anchorZ, yNew: null, sb: 0 };
const out = { front, offsetX: ctx.offsetX, offsetY: ctx.offsetY, sloupec0: [], zaNohou: {} };
for (const N of [3, 2, 1]) {
  const m = measureColumn(ctx, leg0, N);
  out.sloupec0.push(m);
  // druhy a treti sloupec za touto nohou (hladove nejsirsi-nejdriv), jen pro prehled kapacity
  if (m.vysledek === "OK") {
    const chain = [];
    let last = m.leg;
    for (let k = 0; k < 4; k++) {
      let placed = null; const tried = [];
      for (const N2 of [3, 2, 1]) { const m2 = measureColumn(ctx, last, N2); tried.push({ N: N2, vysledek: m2.vysledek, floorY: m2.floorY, physCeil: m2.physCeil, maxPater120: m2.maxPater120, leg: m2.leg }); if (m2.vysledek === "OK" && m2.maxPater120 > 0) { placed = m2; break; } }
      chain.push(tried);
      if (!placed) break;
      last = placed.leg;
    }
    out.zaNohou[N] = chain;
  }
}
out.sekund = (Date.now() - t0) / 1000;
require("fs").writeFileSync(__dirname + "/k020_plan_out.json", JSON.stringify(out, null, 1));
const fmtLeg = l => l ? `${l.type}@${l.anchorZ.toFixed(0)}${l.type === "vyrez" ? ` yNew=${l.yNew} sb=${l.sb}` : ""}` : "-";
console.log(`predni noha plain@${front.anchorZ.toFixed(1)} (prepazka kolize ${front.prepazkaHitZ.toFixed(1)}) offsetX=${ctx.offsetX} offsetY=${ctx.offsetY.toFixed(2)}`);
for (const m of out.sloupec0) {
  console.log(`\nSLOUPEC0 N=${m.N}: ${m.vysledek} noha1=${fmtLeg(m.leg)} luzko@200 koliduje=${m.luzko200koliduje} floorBase=${m.floorBase} floor=${m.floorY} physCeil=${m.physCeil} maxPater(120)=${m.maxPater120}`);
  (out.zaNohou[m.N] || []).forEach((tried, k) => console.log(`   dalsi sloupec ${k + 1}: ` + tried.map(t => `N=${t.N}:${t.vysledek}${t.floorY != null ? ` floor=${t.floorY} ceil=${t.physCeil} pater=${t.maxPater120} noha=${fmtLeg(t.leg)}` : ""}`).join(" | ")));
}
console.log("\nsekund", out.sekund);
