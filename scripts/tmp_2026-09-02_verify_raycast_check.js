// Ground-truth check: is the detected "door gap" a REAL hole in the wall mesh
// or a false positive from sparse vertex tessellation (large flat quad with
// no interior vertices)? Cast rays from outside the vehicle straight at the
// wall (along +X or -X, whichever points INTO the wall from outside) across
// the full flagged Z span and Y=200..900 band, sampled densely. If a solid
// fraction of rays hit a wall triangle, the wall is CONTINUOUS there (false
// positive door-void flag). If none/almost none hit, it's a real hole.
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/car_bodies/";

const base = process.argv[2];
const zNear = parseFloat(process.argv[3]);
const zFar = parseFloat(process.argv[4]);

const wall = parseGlbMesh(KAT + base + "_R_D.glb");
wall.updateMatrixWorld(true);

// Determine which X side the wall is on (R_D = right side wall), find its
// approximate X plane from bounding box, then raycast from further-out X
// toward the vehicle interior (-X direction if wall is on +X side, else +X).
const bbox = new THREE.Box3().setFromObject(wall);
console.log("wall bbox:", JSON.stringify({min:bbox.min,max:bbox.max}));
const wallX = (bbox.min.x + bbox.max.x) / 2;
const outsideX = bbox.max.x + 500; // start well outside
const dir = new THREE.Vector3(-1, 0, 0); // ray travels toward -X (into vehicle)
// If bbox suggests wall is actually on -X side (min.x very negative, max.x small), flip.
let originX = outsideX;
let rdir = dir;
if (Math.abs(bbox.min.x) > Math.abs(bbox.max.x)) {
  originX = bbox.min.x - 500;
  rdir = new THREE.Vector3(1, 0, 0);
}

const raycaster = new THREE.Raycaster();
raycaster.params.Line.threshold = 0;
let total = 0, hits = 0;
const misses = [];
for (let z = zNear; z <= zFar; z += 10) {
  for (let y = 200; y <= 900; y += 25) {
    total++;
    raycaster.set(new THREE.Vector3(originX, y, z), rdir);
    const inter = raycaster.intersectObject(wall, true);
    if (inter.length > 0) hits++;
    else misses.push({ y, z });
  }
}
console.log(`base=${base} zRange=[${zNear},${zFar}] total=${total} hits=${hits} hitFraction=${(hits/total).toFixed(3)}`);
if (misses.length && misses.length < 40) console.log("misses sample:", JSON.stringify(misses.slice(0,20)));
