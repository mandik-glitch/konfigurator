// Nacte GLB pres three r128 GLTFLoader.parse a znovu ulozi pres GLTFExporter (binary) - bez site, bez DOM.
// Pouziti: node _three_roundtrip.js vstup.glb vystup.glb [--scale k] [--rot-x-deg d] [--translate x,y,z]
//   --scale/--rot-x-deg/--translate: transformace kořene sceny pred exportem (uzel, vrcholy se nemeni)
'use strict';
const fs = require('fs');
const path = require('path');
const NM = process.env.V3D_NODE_MODULES || '/opt/konfigurator/node_modules';
global.window = global;
global.THREE = require(path.join(NM, 'three'));
require(path.join(NM, 'three/examples/js/loaders/GLTFLoader.js'));
require(path.join(NM, 'three/examples/js/exporters/GLTFExporter.js'));
// minimalni FileReader (exporter pri binary=true sklada GLB pres Blob)
global.FileReader = class {
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(ab => { this.result = ab; this.onloadend && this.onloadend(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then(ab => { this.result = 'data:application/octet-stream;base64,' + Buffer.from(ab).toString('base64'); this.onloadend && this.onloadend(); }); }
};
const args = process.argv.slice(2);
const [inp, outp] = args;
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const buf = fs.readFileSync(inp);
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
new THREE.GLTFLoader().parse(ab, '', (gltf) => {
  const scene = gltf.scene;
  const k = parseFloat(opt('--scale', '1'));
  if (k !== 1) scene.scale.set(k, k, k);
  const rx = parseFloat(opt('--rot-x-deg', '0'));
  if (rx) scene.rotation.x = rx * Math.PI / 180;
  const tr = opt('--translate', null);
  if (tr) scene.position.set(...tr.split(',').map(Number));
  scene.updateMatrixWorld(true);
  new THREE.GLTFExporter().parse(scene, (res) => {
    fs.writeFileSync(outp, Buffer.from(res));
    process.stdout.write(JSON.stringify({ ok: true, revision: THREE.REVISION, bytes: res.byteLength }));
  }, { binary: true, onlyVisible: false });
}, (err) => { process.stdout.write(JSON.stringify({ ok: false, error: String(err && err.message || err) })); process.exitCode = 1; });
