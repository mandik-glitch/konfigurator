// Nacte GLB pres three r128 GLTFLoader.parse (stejny loader jako nabidka-online.html)
// a vypise svetove AABB kazdeho Mesh objektu (Box3.setFromObject), jmena a userData.
// Bez site, bez DOM (testovaci GLB nemaji textury).
// Pouziti: node three_check.js soubor.glb  -> JSON na stdout
'use strict';
const fs = require('fs');
const path = require('path');
const NM = process.env.V3D_NODE_MODULES || '/opt/konfigurator/node_modules';
global.THREE = require(path.join(NM, 'three'));
require(path.join(NM, 'three/examples/js/loaders/GLTFLoader.js'));

const file = process.argv[2];
const buf = fs.readFileSync(file);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const loader = new THREE.GLTFLoader();
loader.parse(ab, '', (gltf) => {
  const scene = gltf.scene;
  scene.updateMatrixWorld(true);
  const prims = [];
  const names = [];
  const userData = [];
  scene.traverse((o) => {
    if (o !== scene) {
      names.push(o.name);
      if (Object.keys(o.userData || {}).length) userData.push(o.userData);
    }
    if (o.isMesh) {
      const b = new THREE.Box3().setFromObject(o);
      prims.push([b.min.x, b.min.y, b.min.z, b.max.x, b.max.y, b.max.z]);
    }
  });
  process.stdout.write(JSON.stringify({
    ok: true,
    revision: THREE.REVISION,
    prims,
    names,
    userData,
    sceneUserData: scene.userData,
    gltfScenes: gltf.scenes.length,
  }));
}, (err) => {
  process.stdout.write(JSON.stringify({ ok: false, error: String(err && err.message || err) }));
  process.exitCode = 1;
});
