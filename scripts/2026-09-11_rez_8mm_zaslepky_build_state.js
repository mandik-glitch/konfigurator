const THREE = require("/opt/konfigurator/node_modules/three");
const fs = require("fs");

const parts = {
  "pricka-spodni-0": {part_id:"Object_7", position:[-511.99999237060547,981.5004,-1358.502541065216], quaternion:[0,0,-0.7071067811865475,0.7071067811865476], scale:[1,0.219,1]},
  "pricka-police-0": {part_id:"Object_7", position:[-511.99999237060547,1093.2502,-1358.502541065216], quaternion:[0,0,-0.7071067811865475,0.7071067811865476], scale:[1,0.219,1]},
  "vypln-bok-prepazka-a": {part_id:"product_3939", position:[-511.99999237060547,1026.3753,-1358.502541065216], quaternion:[0,0,0,1], scale:[0.233,0.09574979999999994,1]},
  "vypln-bok-prepazka-b": {part_id:"product_3939", position:[-511.99999237060547,1143.6251,-1358.502541065216], quaternion:[0,0,0,1], scale:[0.233,0.10674980000000005,1]},
};
const GLB = { "Object_7": "/opt/konfigurator/webapp/katalog/Object_7.glb", "product_3939": "/opt/konfigurator/webapp/katalog/deska_mdf_seda_8.glb" };

function matrixOf(p) {
  const pos = new THREE.Vector3(...p.position);
  const quat = new THREE.Quaternion(...p.quaternion);
  const scl = new THREE.Vector3(...p.scale);
  const m = new THREE.Matrix4().compose(pos, quat, scl);
  return m.toArray();
}
function axisWorld(p) {
  const quat = new THREE.Quaternion(...p.quaternion);
  const axis = new THREE.Vector3(0,1,0).applyQuaternion(quat);
  return axis.toArray();
}

function buildPair(profRole, accRole, outName) {
  const prof = parts[profRole], acc = parts[accRole];
  const state = {
    profMatrix: matrixOf(prof),
    accMatrix: matrixOf(acc),
    profAxisWorld: axisWorld(prof),
    wallNormalWorld: [0,0,1],
    accCenter: acc.position,
    profFile: GLB[prof.part_id],
    accFile: GLB[acc.part_id],
  };
  fs.writeFileSync(`/tmp/claude-0/-opt-konfigurator/a0c7cc49-b540-492a-9d17-c27a0dbab25e/scratchpad/rez_zaslepka_8mm/${outName}_state.json`, JSON.stringify(state, null, 1));
  console.log("written", outName);
}
buildPair("pricka-spodni-0", "vypln-bok-prepazka-a", "par1");
buildPair("pricka-police-0", "vypln-bok-prepazka-b", "par2");
