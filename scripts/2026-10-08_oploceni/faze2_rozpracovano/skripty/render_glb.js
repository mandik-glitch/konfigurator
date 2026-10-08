// Vykresleni GLB generatoru oploceni v three.js (Chromium, swiftshader) do PNG - jen pro OBRAZKY k nahledu (bot8, 2026-10-08).
// Pouziti: node render_glb.js <jobs.json>   jobs = [{glb: "cesta.glb", out: "cesta.png", az: 35, el: 18, w: 1200, h: 900, titulek: "..."}]
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const fs = require("fs");
const HTML = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#e9edf2}#c{display:block}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}</script></head>
<body><canvas id="c"></canvas><script type="module">
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
window.__ready = false;
window.render = async function (b64, az, el, w, h, titulek, cil, vzdal) {
  const canvas = document.getElementById("c");
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(w, h);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xe6eaef);
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0)).buffer;
  const gltf = await new Promise((ok, err) => new GLTFLoader().parse(bin, "", ok, err));
  scene.add(gltf.scene);
  gltf.scene.traverse(o => { if (o.isMesh) { o.castShadow = true; if (o.material && o.material.transparent) { o.material.depthWrite = false; o.renderOrder = 2; } } });
  const box = new THREE.Box3().setFromObject(gltf.scene), c = box.getCenter(new THREE.Vector3()), sz = box.getSize(new THREE.Vector3());
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(20000, 20000), new THREE.MeshStandardMaterial({ color: 0xb9bec6, roughness: 0.95, metalness: 0 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -0.5; floor.receiveShadow = true; scene.add(floor);
  const dl = new THREE.DirectionalLight(0xffffff, 1.6); dl.position.set(c.x + sz.x, sz.y * 2.2, c.z + sz.z * 1.5); dl.castShadow = true;
  dl.shadow.mapSize.set(2048, 2048); const sc = Math.max(sz.x, sz.z) * 1.6; Object.assign(dl.shadow.camera, { left: -sc, right: sc, top: sc, bottom: -sc, near: 1, far: sz.y * 8 }); dl.target.position.copy(c);
  scene.add(dl, dl.target);
  const cam = new THREE.PerspectiveCamera(32, w / h, 10, 100000);
  const vf = 32 * Math.PI / 180, hf = 2 * Math.atan(Math.tan(vf / 2) * (w / h)), fm = Math.min(vf, hf);
  const R = vzdal || (sz.length() / 2 / Math.sin(fm / 2) * 0.9), a = az * Math.PI / 180, e = el * Math.PI / 180;
  const tgt = cil ? new THREE.Vector3(cil[0], cil[1], cil[2]) : new THREE.Vector3(c.x, sz.y * 0.48, c.z);
  cam.position.set(tgt.x + R * Math.sin(a) * Math.cos(e), tgt.y + R * Math.sin(e), tgt.z + R * Math.cos(a) * Math.cos(e));
  cam.lookAt(tgt);
  renderer.render(scene, cam); renderer.render(scene, cam);
  if (titulek) { const ctx = document.createElement("canvas"); }
  window.__ready = true; return true;
};
</script></body></html>`;
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const errs = [];
  for (const j of jobs) {
    const page = await (await browser.newContext({ viewport: { width: j.w || 1200, height: j.h || 900 } })).newPage();
    page.on("pageerror", e => errs.push(j.out + ": " + e.message.slice(0, 160)));
    page.on("console", m => { if (m.type() === "error") errs.push(j.out + " console: " + m.text().slice(0, 160)); });
    await page.setContent(HTML, { waitUntil: "load" });
    await page.waitForFunction("typeof window.render === 'function'", null, { timeout: 60000 });
    const b64 = fs.readFileSync(j.glb).toString("base64");
    await page.evaluate(([b, az, el, w, h, cil, vz]) => window.render(b, az, el, w, h, "", cil, vz), [b64, j.az ?? 35, j.el ?? 18, j.w || 1200, j.h || 900, j.cil || null, j.vzdal || 0]);
    await page.waitForTimeout(800);
    await page.locator("#c").screenshot({ path: j.out });
    console.log("OK", j.out);
    await page.close();
  }
  console.log("chyby:", JSON.stringify(errs.slice(0, 5)));
  await browser.close();
})();
