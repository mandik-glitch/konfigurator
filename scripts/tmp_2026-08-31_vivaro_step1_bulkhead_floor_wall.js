// Krok 1: kolizni krokovani (car_body_placement_methods.id=1, "kolizni-krokovani")
// pro PRVNI ("plain") nohu regalu na euroboxy ve Vivaro OP18, leva stena (L, id=642).
// Poradi os presne dle Roberta: podlaha -> prepazka B -> stena.
// Vivaro GLB je FYZICKY OTOCENA o 180 (viz place_vivaro.js) - stena L je na
// ZAPORNE strane X, prepazka B na VELKE ZAPORNE strane Z. Smery kroku jsou
// proto ZRCADLOVE (-1) oproti nenotocenym CI24/CI25/Movano skriptum.
const THREE = require("three");
const fs = require("fs");
const { collidesWithWalls, buildLegObject, boxL0, boxB0 } = require("/opt/konfigurator/scripts/tmp_2026-08-31_place_vivaro.js");
const { buildPlainAtDepth } = require("/opt/konfigurator/scripts/tmp_2026-08-30_build_depth_variants_both.js");

const D = 326, T = 30, H = 1180;

const localParts = buildPlainAtDepth(D);

function toWorld(parts, offsetX, offsetY, anchorZ) {
  return parts.map(p => ({
    part_id: "Object_7",
    position: [offsetX - p.position[0], p.position[1] + offsetY, anchorZ + p.position[2]],
    quaternion: p.quaternion,
    scale: p.scale,
    role: p.role,
  }));
}
function groupAt(offsetX, offsetY, anchorZ) { return buildLegObject(toWorld(localParts, offsetX, offsetY, anchorZ)); }

// Cargo Z zhruba od otevreneho konce (~+147) po lic prepazky B (~-2374.5).
// Stred ~ (147-2374.5)/2 ~ -1113.75. X: stred sirky (~0, symetricke steny).
let offsetX = 0 - D / 2;
let offsetY = (600 - H / 2);
let anchorZ = -1114 - T / 2;

console.log("Start pozice koliduje?", collidesWithWalls(groupAt(offsetX, offsetY, anchorZ)));

function stepUntilCollision1D(testFn, dir, maxSteps, label) {
  let steps = 0, collided = false, val = 0;
  while (steps < maxSteps) {
    val += dir;
    steps++;
    if (testFn(val)) { collided = true; break; }
  }
  if (!collided) throw new Error(`${label}: zadna kolize po ${maxSteps} krocich`);
  const backoffVal = val - dir * 2;
  const stillColliding = testFn(backoffVal);
  console.log(`[${label}] kolize po ${steps}mm (val=${val}), 2mm zpet (val=${backoffVal}) -> stale koliduje: ${stillColliding}`);
  if (stillColliding) throw new Error(`${label}: po 2mm zpet stale koliduje`);
  return backoffVal;
}

// krok 2: podlaha (Y dolu, dir=-1, stejne jako CI25 - podlaha je vzdy dole)
const dY = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX, offsetY + v, anchorZ)), -1, 2000, "podlaha (Y dolu)");
offsetY = offsetY + dY;
console.log("Po podlaze: offsetY =", offsetY);

// krok 3: prepazka B (Z smerem k prepazce = KLESAJICI Z, dir=-1, ZRCADLENO oproti CI25)
const dZ = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX, offsetY, anchorZ + v)), -1, 3000, "prepazka B (Z dolu/zaporne)");
anchorZ = anchorZ + dZ;
console.log("Po prepazce: anchorZ =", anchorZ, " (leg z-rozsah:", anchorZ, "..", anchorZ + T, ")");

// krok 4: stena L (X smerem ke stene = KLESAJICI X, dir=-1, ZRCADLENO oproti CI25)
const dX = stepUntilCollision1D((v) => collidesWithWalls(groupAt(offsetX + v, offsetY, anchorZ)), -1, 2000, "stena L (X zaporne)");
offsetX = offsetX + dX;
console.log("Po stene: offsetX =", offsetX);

console.log("\n=== VYSLEDEK ===");
console.log({ offsetX, offsetY, anchorZ });
const finalGroup = groupAt(offsetX, offsetY, anchorZ);
console.log("Finalni kolize?", collidesWithWalls(finalGroup));
const box = new THREE.Box3().setFromObject(finalGroup);
console.log("Box noha:", box.min, box.max);

fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-08-31_vivaro_step1_result.json", JSON.stringify({ offsetX, offsetY, anchorZ, D, T, H }, null, 1));
