// bot25, 2026-09-02 - ROBUST konfirmace kandidatnich dvernich mezer.
// detectDoorGap() (puvodni, 2026-09-02, FO31/VW25) je JEN vertex-density
// heuristika - hleda mezery mezi Z-serazenymi vertexy v pasmu Y=[200,900].
// Nalezena "mezera" ale muze byt FALESNA (proste sparse/velky plochy panel
// s malo vertexy, ktery presto MA material a kolizni raycasting ho najde -
// trojuhelnik "premosti" mezeru mezi vzdalenymi vertexy). Tenhle skript
// KAZDOU kandidatni mezeru nezavisle overi SKUTECNYM koliznim probe testem
// (1mm stepping od stredu vozidla smerem ke stene, na 3 vyskach Y) - pokud
// se najde kolize v ocekavane hloubce (srovnatelna s referencni "solid" Z
// pozici), jde o FALESNY nalez (mesh je jen sparse, ne diravy). Genuine
// dverni otvor = ZADNA kolize nalezena PRI SOUCASNEM potvrzeni, ze wall
// existuje na sousednich Z pozicich (jinak jde jen o okraj modelovane
// geometrie, ne o dveře uprostred jinak souvisle steny).
const THREE = require("three");
const { createEngine } = require("/opt/konfigurator/scripts/tmp_2026-08-31_batch_engine.js");
const { detectDoorGap } = require("/opt/konfigurator/scripts/tmp_2026-09-02_doorvoid_pipeline.js");

function wallDepthAt(engine, z, y, maxSteps) {
  const { collidesWithWalls, mirror } = engine;
  const geo = new THREE.BoxGeometry(2, 2, 2);
  function probeAtX(x) {
    const m = new THREE.Mesh(geo);
    m.position.set(x, y, z);
    m.updateMatrixWorld(true);
    return collidesWithWalls(m);
  }
  let x = 0, steps = 0;
  const dir = mirror ? -1 : 1;
  while (steps < maxSteps) {
    x += dir; steps++;
    if (probeAtX(x)) return x;
  }
  return null;
}

function confirmDoorGaps(engine, refZ) {
  const gaps = detectDoorGap(engine.wallR);
  const YS = [250, 500, 750];
  const refDepths = YS.map(y => wallDepthAt(engine, refZ, y, 2000));
  const confirmed = [];
  const rejected = [];
  for (const g of gaps) {
    const zMid = (g.near + g.far) / 2;
    const midDepths = YS.map(y => wallDepthAt(engine, zMid, y, 2000));
    // solid-nearby check: probe just outside each edge (+/-50mm) to confirm wall exists there
    const nearOutside = Math.min(g.near, g.far) - 50;
    const farOutside = Math.max(g.near, g.far) + 50;
    const nearDepths = YS.map(y => wallDepthAt(engine, nearOutside, y, 2000));
    const farDepths = YS.map(y => wallDepthAt(engine, farOutside, y, 2000));
    const midIsVoid = midDepths.every(d => d === null);
    const nearIsSolid = nearDepths.every(d => d !== null && Math.abs(d - (refDepths.find(r=>r!==null)||d)) < 100);
    const farIsSolid = farDepths.every(d => d !== null && Math.abs(d - (refDepths.find(r=>r!==null)||d)) < 100);
    const real = midIsVoid && nearIsSolid && farIsSolid;
    const rec = { ...g, zMid, midDepths, nearOutside, nearDepths, farOutside, farDepths, real };
    if (real) confirmed.push(rec); else rejected.push(rec);
  }
  return { gapsRaw: gaps, refDepths, confirmed, rejected };
}

module.exports = { confirmDoorGaps, wallDepthAt };

if (require.main === module) {
  const base = process.argv[2];
  const engine = createEngine(base);
  const boxL0 = engine.boxL0;
  const refZ = (boxL0.min.z + boxL0.max.z) / 2;
  const result = confirmDoorGaps(engine, refZ);
  console.log(base, "raw gaps:", result.gapsRaw.length, "CONFIRMED real:", result.confirmed.length, "rejected(false positive):", result.rejected.length);
  result.confirmed.forEach(g => console.log("  CONFIRMED:", JSON.stringify({near:+g.near.toFixed(1),far:+g.far.toFixed(1),gap:+g.gap.toFixed(1)})));
  result.rejected.forEach(g => console.log("  false-positive:", JSON.stringify({near:+g.near.toFixed(1),far:+g.far.toFixed(1),gap:+g.gap.toFixed(1), midDepths:g.midDepths})));
}
