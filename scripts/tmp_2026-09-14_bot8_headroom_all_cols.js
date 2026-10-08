// Zmeri VOLNOU vysku nad nejvyssim boxem v KAZDEM sloupci (col0 i col1)
// pro varianty 01-04 (A i B) - Robertovo pravidlo: mezera > 80mm = prostor
// na vymenu jednoho luzka za vyssi box, se zachovanim patternu "nejvyssi
// box dole, nejnizsi nahore" (=> po vymene se cely sloupec preskladat).
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const D = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/headroom_v2.json", "utf8"));

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

const HEIGHT_BY_SKU = { product_3788: 120, product_3793: 170, product_3794: 220, product_3795: 270, product_3796: 320 };

for (const id of Object.keys(D).map(Number)) {
  const { name, data } = D[id];
  const parts = data.parts;
  console.log(`\n=== id=${id} (${name}) ===`);
  for (const col of ["col0", "col1"]) {
    const boxes = parts.filter(p => (p.role || "").startsWith("eurobox-" + col)).map(p => ({ p, box: worldBox(p) }));
    if (!boxes.length) { console.log(`  ${col}: zadne boxy`); continue; }
    // sezad podle realneho stredu (odshora dolu), abychom videli CELY sloupec luzek
    const byY = [...new Map(boxes.map(x => [x.p.position[2].toFixed(1) + "_" + x.box.min.y.toFixed(0), x])).values()];
    // sjednoceni: pro KAZDOU Z-pozici (bay) vezmi jen jednu reprezentativni radu poloh (pozice se opakuji 2x kvuli 2 bayim)
    const uniqYs = [...new Set(boxes.map(x => Math.round(x.box.min.y)))].sort((a, b) => a - b);
    const topEntry = boxes.reduce((best, x) => (x.box.max.y > (best ? best.box.max.y : -Infinity) ? x : best), null);
    // strop = nejnizsi bod cehokoli NAD timhle boxem se stejnym Z/X prekryvem (podelnik-spodni, jak uz zname)
    const zLo = topEntry.box.min.z - 0.5, zHi = topEntry.box.max.z + 0.5, xLo = topEntry.box.min.x - 0.5, xHi = topEntry.box.max.x + 0.5;
    let ceiling = Infinity, ceilPart = null;
    for (const p of parts) {
      if (!/spodni|vypln-dno/.test(p.role || "")) continue;
      const b = worldBox(p); if (!b) continue;
      if (b.min.y < topEntry.box.max.y - 0.5) continue;
      const zOv = Math.min(b.max.z, zHi) - Math.max(b.min.z, zLo);
      const xOv = Math.min(b.max.x, xHi) - Math.max(b.min.x, xLo);
      if (zOv <= 0 || xOv <= 0) continue;
      if (b.min.y < ceiling) { ceiling = b.min.y; ceilPart = p.role; }
    }
    const volno = ceiling - topEntry.box.max.y;
    const topHeight = Math.round(topEntry.box.max.y - topEntry.box.min.y);
    console.log(`  ${col}: uroven=${uniqYs.length} nejvyssi_box_sku=${topEntry.p.part_id}(${topHeight}mm) top=${topEntry.box.max.y.toFixed(1)} strop=${ceiling.toFixed(1)}(${ceilPart}) VOLNO=${volno.toFixed(1)}mm ${volno > 80 ? "  <<< >80mm!" : ""}`);
  }
}
