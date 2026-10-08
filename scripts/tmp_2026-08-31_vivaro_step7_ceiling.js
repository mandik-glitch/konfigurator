// Krok 7 (dle CI25 nalezu): box spanujici CELOU hloubku D muze narazit na
// SKUTECNOU karoserii (zaklonění strechy/boku) NEZAVISLE na joint-containment
// limitu nosniku (920/905). Fresh 1mm kolizni krokovani sirokeho sondovaciho
// objektu (cela hloubka D, ne jen tenky 30mm nohovy profil) pro KAZDY sloupec.
const fs = require("fs");
const THREE = require("three");
const { collidesWithWalls } = require("/opt/konfigurator/scripts/tmp_2026-08-31_place_vivaro.js");

const step1 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step1_result.json", "utf8"));
const step3 = JSON.parse(fs.readFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step3_result.json", "utf8"));
const { offsetX, offsetY, D, T } = step1;

function fullDepthSlab(y, zFrom, zTo) {
  const geo = new THREE.BoxGeometry(D, 10, zTo - zFrom);
  const mesh = new THREE.Mesh(geo);
  mesh.position.set(offsetX - D / 2, y, (zFrom + zTo) / 2);
  mesh.updateMatrixWorld(true);
  return mesh;
}

const results = {};
step3.columns.forEach((col, colIdx) => {
  const legFrom = step3.legs[col.legFromIdx], legTo = step3.legs[col.legToIdx];
  const zFrom = legFrom.anchorZ + T, zTo = legTo.anchorZ;
  console.log(`\n=== sloupec ${colIdx} (Z ${zFrom}..${zTo}) ===`);
  let y = 900;
  console.log(" Y=900 koliduje?", collidesWithWalls(fullDepthSlab(y, zFrom, zTo)));
  let steps = 0, collisionY = null;
  while (steps < 400) {
    y += 1; steps++;
    if (collidesWithWalls(fullDepthSlab(y, zFrom, zTo))) { collisionY = y; break; }
  }
  if (collisionY === null) throw new Error(`sloupec ${colIdx}: zadna kolize nalezena do Y=${y}`);
  const safeY = collisionY - 2;
  const stillColl = collidesWithWalls(fullDepthSlab(safeY, zFrom, zTo));
  console.log(` kolize nalezena pri Y=${collisionY}, 2mm zpet (Y=${safeY}) stale koliduje: ${stillColl}`);
  if (stillColl) throw new Error("po 2mm zpet stale koliduje");
  results[colIdx] = { collisionY, maxSafeBoxTop: safeY };
  console.log(" VYSLEDEK sloupec", colIdx, results[colIdx]);
});

fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step7_result.json", JSON.stringify(results, null, 1));
