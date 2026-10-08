// Independent second-pass verification: for each of the 8 rows' FINAL merged
// parts (car_body + legs/rails/boxes/endcaps), fresh-parse the real car body
// GLB and confirm 0 collisions, using the SAME production collidesWithWalls
// (edge-crossing raycast vs three-mesh-bvh) as the build pipeline - but run
// here as a wholly separate script/process, not reusing any cached env.
const fs = require("fs");
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";

const BODYFILE = {
  124: "Volkswagen_Caddy_VW21_2021-", 125: "Volkswagen_Caddy_VW22_2021-",
  126: "Volkswagen_Caddy_VW31_2021-", 127: "Volkswagen_Caddy_VW32_2021-",
  143: "Volkswagen_Caddy_VW31_2021-", 144: "Volkswagen_Caddy_VW31_2021-",
  165: "Volkswagen_Caddy_VW31_2021-", 166: "Volkswagen_Caddy_VW31_2021-",
};
const CARBODY_OFFSET = { 124:[0,0,0],125:[0,0,0],126:[0,-1651.5,0],127:[0,0,0],143:[0,-1651.5,0],144:[0,-1651.5,0],165:[0,-1651.5,0],166:[0,-1651.5,0] };

function glbForPart(partId) {
  if (partId === "Object_7") return KAT + "Object_7.glb";
  if (partId === "product_3071") return KAT + "product_3071.glb";
  if (partId.startsWith("product_37")) return KAT + partId + ".glb";
  return null;
}

function verifyRow(rowId, dataParts) {
  const bodyPrefix = BODYFILE[rowId];
  const off = CARBODY_OFFSET[rowId];
  const wallL = parseGlbMesh(CARB + bodyPrefix + "_L.glb");
  const wallR = parseGlbMesh(CARB + bodyPrefix + "_R_D.glb");
  const wallB = parseGlbMesh(CARB + bodyPrefix + "_B.glb");
  [wallL, wallR, wallB].forEach(m => { m.position.set(off[0], off[1], off[2]); m.updateMatrixWorld(true); m.geometry.computeBoundsTree(); });
  const wallMeshes = [wallL, wallR, wallB];
  const raycaster = new THREE.Raycaster(); raycaster.firstHitOnly = true;
  const MAX_EDGES = 300;
  function edges(mesh) {
    const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
    const triCount = idx ? idx.count/3 : pos.count/3;
    const step = Math.max(1, Math.floor(triCount / (MAX_EDGES/3)));
    const out = []; const vA=new THREE.Vector3(),vB=new THREE.Vector3(),vC=new THREE.Vector3();
    for (let t=0;t<triCount;t+=step) {
      let ia,ib,ic;
      if (idx) { ia=idx.getX(t*3); ib=idx.getX(t*3+1); ic=idx.getX(t*3+2); } else { ia=t*3; ib=t*3+1; ic=t*3+2; }
      vA.fromBufferAttribute(pos,ia).applyMatrix4(mesh.matrixWorld);
      vB.fromBufferAttribute(pos,ib).applyMatrix4(mesh.matrixWorld);
      vC.fromBufferAttribute(pos,ic).applyMatrix4(mesh.matrixWorld);
      out.push([vA.clone(),vB.clone()],[vB.clone(),vC.clone()],[vC.clone(),vA.clone()]);
    }
    return out;
  }
  function collidesWithWalls(object3d) {
    object3d.updateMatrixWorld(true);
    let hit=false;
    object3d.traverse(n=>{ if(hit||!n.isMesh) return; for (const [p0,p1] of edges(n)) { const dir=p1.clone().sub(p0); const dist=dir.length(); if(dist<1e-6) continue; dir.normalize(); raycaster.set(p0,dir); raycaster.far=dist; if(raycaster.intersectObjects(wallMeshes,false).length){hit=true;break;} } });
    return hit;
  }
  const nonCarBody = dataParts.filter(p => !p.part_id.startsWith("car_body_"));
  let collisions = 0; const bad = [];
  const meshes = [];
  for (const p of nonCarBody) {
    const glb = glbForPart(p.part_id);
    if (!glb || !fs.existsSync(glb)) { bad.push({role:p.role, part_id:p.part_id, err:"missing-glb"}); continue; }
    const m = parseGlbMesh(glb);
    m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale); m.updateMatrixWorld(true);
    meshes.push({p,m});
    const grp = new THREE.Group(); grp.add(m.clone()); // clone since add() reparents
    // note: clone() on a Mesh with BufferGeometry shares geometry/material by ref, fine for our purposes (read-only)
    grp.updateMatrixWorld(true);
  }
  for (const {p,m} of meshes) {
    const grp = new THREE.Group();
    const m2 = m.clone(); m2.geometry = m.geometry; m2.matrix.copy(m.matrix); m2.matrixWorld.copy(m.matrixWorld); m2.matrixAutoUpdate = false;
    grp.add(m2); grp.matrixAutoUpdate = false; grp.updateMatrixWorld(true);
    if (collidesWithWalls(grp)) { collisions++; bad.push({role: p.role, part_id: p.part_id, position: p.position}); }
  }
  // self-collision: box-vs-box only unexpected overlap check
  const boxes = meshes.filter(x => x.p.part_id.startsWith("product_37"));
  let selfColl = 0; const selfBad = [];
  for (let i=0;i<boxes.length;i++) for (let j=i+1;j<boxes.length;j++) {
    const A = new THREE.Box3().setFromObject(boxes[i].m), B = new THREE.Box3().setFromObject(boxes[j].m);
    const ox=Math.min(A.max.x,B.max.x)-Math.max(A.min.x,B.min.x), oy=Math.min(A.max.y,B.max.y)-Math.max(A.min.y,B.min.y), oz=Math.min(A.max.z,B.max.z)-Math.max(A.min.z,B.min.z);
    if (ox>0.5&&oy>0.5&&oz>0.5) { selfColl++; selfBad.push([boxes[i].p.role, boxes[j].p.role]); }
  }
  return { rowId, totalParts: dataParts.length, nonCarBodyParts: nonCarBody.length, collisions, bad, selfColl, selfBad };
}

const rows = [124,125,126,127,143,144,165,166];
const results = {};
for (const id of rows) {
  const d = JSON.parse(fs.readFileSync(`/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/fresh_from_db_${id}.json`, "utf8"));
  results[id] = verifyRow(id, d.parts);
  console.log(id, JSON.stringify(results[id]));
}
fs.writeFileSync("/tmp/claude-0/-opt-domeny/40752a20-c083-499a-8fe3-7c39a4eef60b/scratchpad/verify_final_results.json", JSON.stringify(results, null, 1));
