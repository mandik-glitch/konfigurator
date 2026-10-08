// Test PLUGINU PRICEK v Multiboxech A OCELOVYCH SUPLICICH (v5) - HOTOVE MIXY PRO POLICI / SUPLIK + vyber po boxech (webapp/js/v3d/pricky-multibox.js; bot8, 2026-10-07; Robert: pricky do multiboxu v online nabidce, hotove varianty mix
// pro celou policii / suplik, ve 3D viditelne ruzne pocty pricek v boxech).
// SKUTECNY viewer3d.js (three r128 z node_modules) + SKUTECNA zakaznicka GLB s mbx z build_karty.py + payload vyrobeny pri startu z jejich spec (api/nabidka_pricky.payload s testovacimi cenami) v headless
// Chromiu (swiftshader), bez site a bez DB, zadny binarni ani JSON fixture v repu. Dve testovaci stranky: /viewer.html (plny viewer + plugin) a /direct.html (plugin nad holou scenou: syntetika, dispose, vadne vstupy).
// SPUSTENI (z teto slozky):
//   python3 /opt/konfigurator/scripts/2026-10-02_v3d_testy/build_karty.py 4917 4918 4921 4594       (jednou: zakaznicka GLB do <V3D_TEST_OUT>/out2; Blender na CPU, ~15 s na kartu)
//   node test_plugin.js                                                                              (~5-10 min podle zatizeni stroje; SHOTS=<slozka> uklada snimky; sekce S a R: supliky, ~1 a ~3 min)
// Prostredi (vse nepovinne): PRICKY_REPO (koren repa, vychozi ../..), PLUGIN_JS (plugin, vychozi <repo>/webapp/js/v3d/pricky-multibox.js; kandidat pred nasazenim), PRICKY_API (slozka s nabidka_pricky.py
//   a v3d_glb.py, vychozi <repo>/api; kandidat), V3D_TEST_OUT (vystupy build_karty.py, vychozi <tmp>/v3d_testy), PRICKY_FIX (primo slozka s <karta>.offer.glb, vychozi <V3D_TEST_OUT>/out2), WEB_DIR (vychozi <repo>/webapp),
//   VIEWER_JS / V3D_CSS (kandidat vieweru), THREE_DIR (vychozi <repo>/node_modules/three, jinak /opt/konfigurator/node_modules/three), PY (python pro make_glbs.py, vychozi python3), STOP_ON_FAIL=1 (konec po prvni chybe sekce),
//   SEKCE=A,K (jen vybrane sekce: P data payloadu, A mixy a souhrn, M mixy v 3D, K pocty po boxech, B pohyb, C dratovy vzhled, D obrys skupiny, E setModel, F pixely, G vykon, H syntetika, N motionIds, S supliky, R skutecne karty se supliky; bez SEKCE vsechny).
// v5: PRICKY_SUPLIKY=rucne|skutecny|auto (payload supliku v sekci S: rucne podle kontraktu / z API / z API kdyz umi supliky, vychozi auto). Karty se supliky (mbx sk = 4) vidi karetni sekce jako 'jen multiboxy'
//   (make_glbs.py je odfiltruje a prectisluje, takze puvodni kontroly bezi beze zmeny na starych I novych GLB); sekce R testuje tytez karty VCETNE podnosu (skutecne AABB, pivoty a pohyby).
// Povinne jsou GLB karet 4921 a 4917 (jinak konci s kodem 2 a napovedou); ostatni karty jsou volitelne (test E6 pouzije prvni vhodnou z 4918 / 4917 / 4453). Vystup: [OK] / [CHYBA] po kontrolach a "N/N OK" na konci,
// exit 0 jen kdyz vse prosel. Mutacni kontrola tohoto testu: python3 mutace_plugin.py (zamerne chyby v kopii pluginu, vsechny musi test chytit).
const { chromium } = require("/opt/konfigurator/node_modules/playwright");
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), cp = require("child_process");
const HERE = __dirname;
const REPO = process.env.PRICKY_REPO || path.resolve(HERE, "..", "..");
const API = process.env.PRICKY_API || path.join(REPO, "api");
const OUT = process.env.V3D_TEST_OUT || path.join(os.tmpdir(), "v3d_testy");
const FIX = process.env.PRICKY_FIX || path.join(OUT, "out2");                       // <karta>.offer.glb z scripts/2026-10-02_v3d_testy/build_karty.py
const WEB = process.env.WEB_DIR || path.join(REPO, "webapp");
const THREE_DIR = process.env.THREE_DIR || (fs.existsSync(path.join(REPO, "node_modules", "three")) ? path.join(REPO, "node_modules", "three") : "/opt/konfigurator/node_modules/three");
const PLUGIN = process.env.PLUGIN_JS || path.join(WEB, "js/v3d/pricky-multibox.js");
const VIEWER = process.env.VIEWER_JS || path.join(WEB, "js/v3d/viewer3d.js");
const CSS = process.env.V3D_CSS || path.join(WEB, "css/v3d.css");
const SHOTS = process.env.SHOTS || "";
const STOP = process.env.STOP_ON_FAIL === "1";
const SEK = (process.env.SEKCE || "").split(",").map((x) => x.trim()).filter(Boolean);        // SEKCE=A,M = jen tyto sekce (mutacni kontrola je pousti cilene); bez SEKCE vsechny
const run = (k) => !SEK.length || SEK.indexOf(k) >= 0;
const GEN = fs.mkdtempSync(path.join(os.tmpdir(), "pricky_gen_"));                  // docasne vstupy testu (payloady, syntetika); po testu se smaze
const cleanup = () => { try { fs.rmSync(GEN, { recursive: true, force: true }); } catch (e) { /* docasna slozka */ } };
let KARTY = {};
try {
  const r = cp.execFileSync(process.env.PY || "python3", ["-B", path.join(HERE, "make_glbs.py"), GEN], { stdio: ["ignore", "pipe", "pipe"], env: Object.assign({}, process.env, { PRICKY_REPO: REPO, PRICKY_API: API, V3D_TEST_OUT: OUT, PRICKY_FIX: FIX }) }).toString();
  const m = /^KARTY (.+)$/m.exec(r);
  KARTY = m ? JSON.parse(m[1]) : {};
} catch (e) {
  console.error("TEST SPADL: " + ((e.stderr && e.stderr.toString().trim().split("\n").pop()) || e.message));
  cleanup();
  process.exit(2);
}
console.log("vstupy: karty s payloadem " + JSON.stringify(KARTY.payload) + (Object.keys(KARTY.preskoceno || {}).length ? ", preskoceno " + JSON.stringify(KARTY.preskoceno) : "") + " (GLB z " + FIX + "), plugin " + PLUGIN);
if (SHOTS) fs.mkdirSync(SHOTS, { recursive: true });

const SCRIPTS_THREE = ["build/three.min.js", "examples/js/controls/OrbitControls.js", "examples/js/loaders/GLTFLoader.js", "examples/js/environments/RoomEnvironment.js",
  "examples/js/renderers/CSS2DRenderer.js", "examples/js/shaders/HorizontalBlurShader.js", "examples/js/shaders/VerticalBlurShader.js"];
const threeTags = SCRIPTS_THREE.map((s) => `<script src="/three/${s}"></script>`).join("\n");
const PAGE_COMMON = `
window.__errs = [];
window.addEventListener('error', function (e) { __errs.push('error: ' + e.message); });
window.addEventListener('unhandledrejection', function (e) { __errs.push('rejection: ' + ((e.reason && e.reason.message) || e.reason)); });
var __ce = console.error; console.error = function () { __errs.push('console: ' + [].slice.call(arguments).join(' ')); __ce.apply(console, arguments); };
window.__disposed = new Set();
(function () {
  var gd = THREE.BufferGeometry.prototype.dispose, md = THREE.Material.prototype.dispose;
  THREE.BufferGeometry.prototype.dispose = function () { if (this.userData && this.userData.__pricky) __disposed.add(this); return gd.apply(this, arguments); };
  THREE.Material.prototype.dispose = function () { if (this.userData && this.userData.__pricky) __disposed.add(this); return md.apply(this, arguments); };
})();
window.platesOf = function (root, id) {              // pro kazdou pricku (24 vrcholu) svetovy AABB; + pocet trojuhelniku a usecek
  var out = { plates: [], tris: 0, lineVerts: 0, groups: 0, meshes: 0, color: null, edgeColor: null, colorWrite: null };
  root.updateMatrixWorld(true);
  root.traverse(function (n) {
    if (!n.userData || n.userData.__pricky !== id) return;
    if (n.isGroup) out.groups++;
    if (n.isMesh) {
      out.meshes++; out.tris += n.geometry.index.count / 3; out.colorWrite = n.material.colorWrite;
      var c = n.material.color.clone(); if (window.__srgb) c.convertLinearToSRGB(); out.color = c.getHexString();
      var pa = n.geometry.attributes.position, m = n.matrixWorld, v = new THREE.Vector3();
      for (var i = 0; i < pa.count; i += 24) {
        var mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
        for (var j = i; j < i + 24; j++) { v.fromBufferAttribute(pa, j).applyMatrix4(m); var a = [v.x, v.y, v.z]; for (var k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], a[k]); mx[k] = Math.max(mx[k], a[k]); } }
        out.plates.push({ min: mn, max: mx });
      }
    }
    if (n.isLineSegments) { out.lineVerts += n.geometry.attributes.position.count; out.edgeColor = n.material.color.clone().getHexString(); }
  });
  return out;
};
window.hlList = function (root) {                    // oranzove obrysy: [{box, gid, min, max}] (jeden na box skupiny)
  var res = [];
  root.updateMatrixWorld(true);
  root.traverse(function (n) { if (n.isGroup && n.userData && n.userData.__prickyHl) { var b = new THREE.Box3().expandByObject(n); res.push({ box: n.userData.__prickyBox, gid: n.userData.__prickyHl, min: b.min.toArray(), max: b.max.toArray() }); } });
  return res;
};
window.countGroups = function (root) { var n = 0; root.traverse(function (o) { if (o.isGroup && o.userData && o.userData.__pricky) n++; }); return n; };
window.countHl = function (root) { var n = 0; root.traverse(function (o) { if (o.userData && o.userData.__prickyHl) n++; }); return n; };
`;
const VIEWER_HTML = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/css/v3d.css">
<style>html,body{margin:0;background:#fff} #c{position:relative;width:1100px;height:700px}</style></head><body><div id="c"></div>
${threeTags}
<script src="/js/v3d/viewer3d.js"></script><script src="/plugin.js"></script>
<script>${PAGE_COMMON}
window.mount = function (glb, payload, extra, preset) {
  window.__changes = [];
  var pr = window.pr = V3DPricky.create({ payload: payload, onChange: function (v, s) { __changes.push({ v: v, s: s }); } });
  if (preset) pr.api.setMany(preset);       // vyber PRED mountem (napr. obnova z localStorage)
  var v = window.v = V3D.mount(document.getElementById('c'), Object.assign({ modelUrl: glb, mode: 'real', allowReal: true, hudKoty: false, plugins: [pr.plugin, function (c) { window.__ctx = c; }] }, extra || {}));
  return v.ready.then(function () { window.__srgb = window.__ctx.renderer.outputEncoding === THREE.sRGBEncoding; return true; });
};
window.model = function () { return v.debug.model(); };
window.cam = function (center, dist, dir) {                // kamera zblizka na bod (mm) z rohu nahore
  var c = window.__ctx, t = new THREE.Vector3().fromArray(center);
  c.controls.minDistance = 10; c.controls.target.copy(t);
  c.camera.position.copy(t).add(new THREE.Vector3().fromArray(dir || [0.55, 0.85, 1.0]).normalize().multiplyScalar(dist));
  c.camera.near = 5; c.camera.far = 20000; c.camera.updateProjectionMatrix(); c.controls.update(); c.requestRender();
};
window.settle = function () { return new Promise(function (res) { var t0 = performance.now(); (function w() { if (v.debug.idle() || performance.now() - t0 > 30000) res(performance.now() - t0); else setTimeout(w, 50); })(); }); };
window.pix = function (slot) { v.debug.renderNow(); var cv = document.querySelector('.v3d-canvas'), c2 = document.createElement('canvas'); c2.width = cv.width; c2.height = cv.height; var g = c2.getContext('2d'); g.drawImage(cv, 0, 0); (window.__pix = window.__pix || {})[slot] = g.getImageData(0, 0, cv.width, cv.height).data; return true; };
window.pixDiff = function (a, b) { var A = __pix[a], B = __pix[b], n = 0; for (var i = 0; i < A.length; i += 4) { if (Math.abs(A[i] - B[i]) + Math.abs(A[i + 1] - B[i + 1]) + Math.abs(A[i + 2] - B[i + 2]) > 36) n++; } return n; };
</script></body></html>`;
const DIRECT_HTML = `<!doctype html><html><head><meta charset="utf-8"></head><body>
${threeTags}
<script src="/plugin.js"></script>
<script>${PAGE_COMMON}
window.direct = function (glb, payload, o) {
  o = o || {};
  return new Promise(function (res, rej) { new THREE.GLTFLoader().load(glb, res, undefined, rej); }).then(function (gltf) {
    var scene = new THREE.Scene(); scene.add(gltf.scene);
    var root = document.createElement('div'); document.body.appendChild(root);
    var frames = [], renders = 0, changes = [];
    var ctx = { THREE: THREE, gltf: gltf, model: gltf.scene, scene: scene, root: root, requestRender: function () { renders++; },
      state: function () { return { mode: root.classList.contains('v3d-mode-wire') ? 'wire' : 'real' }; },
      onFrame: function (fn) { frames.push(fn); return function () { var i = frames.indexOf(fn); if (i >= 0) frames.splice(i, 1); }; } };
    if (o.bezOnFrame) delete ctx.onFrame;
    var pr = V3DPricky.create({ payload: payload, onChange: function (v, s) { changes.push({ v: v, s: s }); } });
    var off = pr.plugin(ctx);
    window.D = { pr: pr, ctx: ctx, off: off, scene: scene, frames: frames, changes: changes, renders: function () { return renders; }, tick: function () { frames.slice().forEach(function (f) { f(0); }); } };
    return typeof off;
  });
};
</script></body></html>`;

const MIME = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".glb": "model/gltf-binary", ".json": "application/json", ".hdr": "application/octet-stream" };
const server = http.createServer((req, res) => {
  const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const send = (f, type) => fs.readFile(f, (e, d) => { if (e) { res.writeHead(404); return res.end("nf"); } res.writeHead(200, { "Content-Type": type || MIME[path.extname(f)] || "application/octet-stream", "Cache-Control": "no-store" }); res.end(d); });
  if (p === "/viewer.html") { res.writeHead(200, { "Content-Type": MIME[".html"] }); return res.end(VIEWER_HTML); }
  if (p === "/direct.html") { res.writeHead(200, { "Content-Type": MIME[".html"] }); return res.end(DIRECT_HTML); }
  if (p === "/plugin.js") return send(PLUGIN);
  if (p === "/js/v3d/viewer3d.js") return send(VIEWER);
  if (p === "/css/v3d.css") return send(CSS);
  let m = /^\/three\/(.+)$/.exec(p);
  if (m && !m[1].includes("..")) return send(path.join(THREE_DIR, m[1]));
  m = /^\/fx\/([\w.]+)$/.exec(p);
  if (m) return send(fs.existsSync(path.join(GEN, m[1])) ? path.join(GEN, m[1]) : path.join(FIX, m[1]));
  if (/^\/js\/v3d\/env\//.test(p)) return send(path.join(WEB, p));
  res.writeHead(404); res.end("nf");
});

let bad = 0, total = 0;
const t = (name, cond, detail) => { total++; if (!cond) bad++; console.log(`[${cond ? "OK   " : "CHYBA"}] ${name}${!cond && detail !== undefined ? " | " + (typeof detail === "string" ? detail : JSON.stringify(detail)).slice(0, 700) : ""}`); };
const gate = () => { if (STOP && bad) throw new Error("STOP_ON_FAIL"); };
const near = (a, b, eps) => Math.abs(a - b) <= (eps === undefined ? 0.02 : eps);
const nearV = (a, b, eps) => a.length === b.length && a.every((x, i) => near(x, b[i], eps));

function readSpec(file) {                              // v3d spec z JSON chunku GLB
  const buf = fs.readFileSync(file), len = buf.readUInt32LE(12);
  return JSON.parse(buf.slice(20, 20 + len).toString("utf8")).scenes[0].extras.v3d;
}
const payloadOf = (k) => JSON.parse(fs.readFileSync(path.join(GEN, `payload_${k}.json`), "utf8"));
const cardGlb = (c) => (fs.existsSync(path.join(GEN, c + ".offer.glb")) ? path.join(GEN, c + ".offer.glb") : path.join(FIX, c + ".offer.glb"));      // v5: karta se supliky = pohled 'jen multiboxy' z make_glbs (GEN, prednostne; stejne ho servíruje server), jinak GLB z build_karty

const NOM = { "288": [288, 4], "395": [395.5, 6], "500": [500, 8] };      // trida delky -> [nominalni delka, sloty] (Robert: 300 > 4, 400 > 6, 500 > 8)
// sloty: kazda pricka v nastavenem setu lezi PRESNE v nekterem z S rovnomernych slotu studny (X0 = 28,4 ... L-2), zadne dve ve stejnem
function slotErrors(typKey, desky) {
  const [L, S] = NOM[typKey.split("x")[0]], x0 = 28.4, pitch = (L - 2 - x0) / (S + 1), seen = new Set(), errs = [];
  desky.forEach((d) => {
    const j = (d.s[0] - x0) / pitch, jr = Math.round(j);
    if (Math.abs(j - jr) * pitch > 0.06 || jr < 1 || jr > S) errs.push("mimo slot: x " + d.s[0] + " slot " + j.toFixed(3));
    if (seen.has(jr)) errs.push("dve pricky ve slotu " + jr);
    seen.add(jr);
  });
  return errs;
}
// kontrola jedne pricky ve SVETE vuci boxu z mbx: uvnitr studny, na dne, pod okrajem, konec s vykrojem volny
function checkPlate(pl, mb, geom) {
  const a = (mb.max[0] - mb.min[0]) >= (mb.max[2] - mb.min[2]) ? 0 : 2, b = 2 - a, eps = 0.02, studna = geom.studna_od, dno = 2;
  const errs = [];
  for (let i = 0; i < 3; i++) if (pl.min[i] < mb.min[i] - eps || pl.max[i] > mb.max[i] + eps) errs.push("mimo AABB osa " + i);
  if (!near(pl.min[1], mb.min[1] + dno, eps)) errs.push("nestoji na dne: " + (pl.min[1] - mb.min[1]));
  if (!near(pl.max[1] - pl.min[1], 75, eps)) errs.push("vyska " + (pl.max[1] - pl.min[1]));
  if (!near(pl.max[a] - pl.min[a], 2, eps)) errs.push("tloustka " + (pl.max[a] - pl.min[a]));
  if (mb.e > 0 && pl.min[a] < mb.min[a] + studna - eps) errs.push("zasahuje do vykroje (e=+1): " + (pl.min[a] - mb.min[a]));
  if (mb.e < 0 && pl.max[a] > mb.max[a] - studna + eps) errs.push("zasahuje do vykroje (e=-1): " + (mb.max[a] - pl.max[a]));
  if (pl.min[b] < mb.min[b] + 2 - eps || pl.max[b] > mb.max[b] - 2 + eps) errs.push("zasahuje do steny po sirce");
  if (!near((pl.min[b] + pl.max[b]) / 2, (mb.min[b] + mb.max[b]) / 2, 0.6)) errs.push("neni na stred sirky");       // 0,6: boxy siroke 92 mm (typ 91) maji stred o 0,5 mm vedle nominalniho 91
  return errs;
}
const center = (pl) => pl.min.map((x, i) => (x + pl.max[i]) / 2);
// presne mapovani mistni -> svet: pricka j ma stred v mistnich (x, y, z) presne podle desky j payloadu
function mapErrors(pl, mb, d) {
  const a = (mb.max[0] - mb.min[0]) >= (mb.max[2] - mb.min[2]) ? 0 : 2, bb = 2 - a, c = center(pl), sz = pl.max.map((x, k) => x - pl.min[k]), errs = [];
  const xloc = mb.e > 0 ? c[a] - mb.min[a] : mb.max[a] - c[a];
  if (!near(xloc, d.s[0], 0.06) || !near(c[bb] - mb.min[bb], d.s[2], 0.06) || !near(c[1] - mb.min[1], d.s[1], 0.06)) errs.push("stred " + c.map((x) => x.toFixed(1)));
  if (!near(sz[a], d.r[0], 0.06) || !near(sz[1], d.r[1], 0.06) || !near(sz[bb], d.r[2], 0.06)) errs.push("rozmer " + sz.map((x) => x.toFixed(1)));
  return errs;
}

// ---------------------------------------------------------------------- pomocne funkce testu v4 (cisty vypocet z payloadu, nezavisly na pluginu)
const boxOf = (P, id) => P.boxy.find((b) => b.id === id);
const grpOf = (P, gid) => P.skupiny.find((g) => g.id === gid);
const canon = (o) => (Array.isArray(o) ? o.map(canon) : (o && typeof o === "object" ? Object.keys(o).sort().reduce((a, k) => { a[k] = canon(o[k]); return a; }, {}) : o));
const eq = (a, b) => JSON.stringify(canon(a)) === JSON.stringify(canon(b));
const keysOrdered = (o) => Object.keys(o).join();
const idNum = (id) => parseInt(id.slice(1), 10);
// vyber po boxech {boxId: n} z hotoveho setu skupiny (payload.skupiny[].sety[set].po_boxech); 'bez' = nic
function fromSet(P, gid, sid) {
  const g = grpOf(P, gid), out = {};
  if (sid === "bez") return out;
  g.boxy.forEach((id, i) => { const n = g.sety[sid].po_boxech[i]; if (n) out[id] = n; });
  return out;
}
const fromSets = (P, map) => Object.assign({}, ...Object.keys(map).map((gid) => fromSet(P, gid, map[gid])));
const sortedSel = (m) => Object.keys(m).sort((a, b) => idNum(a) - idNum(b)).reduce((a, k) => { a[k] = m[k]; return a; }, {});
// rozpoznani setu (pravidlo serveru): 'bez' | nabizeny set s presne stejnymi po_boxech | 'vlastni'
function recognizeNode(P, g, selMap) {
  const po = g.boxy.map((id) => selMap[id] || 0);
  if (!po.some((x) => x)) return "bez";
  for (const sid of Object.keys(g.sety)) if (sid !== "bez" && JSON.stringify(po) === JSON.stringify(g.sety[sid].po_boxech)) return sid;
  return "vlastni";
}
const r2 = (x) => Math.round(x * 100) / 100;
// ocekavany souhrn z vyberu {boxId: n}: Sum n x cena dilu (typy[k].dil -> dily[klic].cena)
function expectSummary(P, selMap) {
  const qty = {};
  let boxu = 0, kusy = 0;
  P.boxy.forEach((b) => { const n = selMap[b.id] || 0; if (!n) return; const d = P.typy[b.k].dil; qty[d] = (qty[d] || 0) + n; boxu++; kusy += n; });
  const radky = P.dily.filter((d) => qty[d.klic]).map((d) => ({ klic: d.klic, qty: qty[d.klic], unit_price: d.cena, total: r2(d.cena * qty[d.klic]) }));
  const skupiny = [];
  P.skupiny.forEach((g) => {
    const q2 = {}; let ks = 0, bs = 0;
    g.boxy.forEach((id) => { const n = selMap[id] || 0; if (!n) return; const d = P.typy[boxOf(P, id).k].dil; q2[d] = (q2[d] || 0) + n; ks += n; bs++; });
    if (!ks) return;
    skupiny.push({ id: g.id, set: recognizeNode(P, g, selMap), cena: r2(P.dily.reduce((a, d) => a + (q2[d.klic] ? d.cena * q2[d.klic] : 0), 0)), priccek: ks, boxu_s_pricky: bs });
  });
  return { boxu, kusy, cena_net: r2(radky.reduce((a, r) => a + r.total, 0)), radky, skupiny };
}
const sumOk = (a, e) => a.boxu === e.boxu && a.kusy === e.kusy && near(a.cena_net, e.cena_net, 0.005) && a.radky.length === e.radky.length
  && e.radky.every((r, i) => a.radky[i].klic === r.klic && a.radky[i].qty === r.qty && near(a.radky[i].unit_price, r.unit_price, 1e-9) && near(a.radky[i].total, r.total, 0.005))
  && a.skupiny.length === e.skupiny.length && e.skupiny.every((g, i) => a.skupiny[i].id === g.id && a.skupiny[i].set === g.set && a.skupiny[i].priccek === g.priccek && a.skupiny[i].boxu_s_pricky === g.boxu_s_pricky && near(a.skupiny[i].cena, g.cena, 0.005));

// ---------------------------------------------------------------------- v5: supliky - cisla z kontraktu (c5/KONTRAKT_SUPLIKY_v5.md), NEZAVISLY zdroj pravdy testu (nebere se z payloadu ani z pluginu)
const SUP = { bok: { 443: 12.5, 695: 11.4, 950: 11.7 }, celo: { 332: 0.4, 384: 0.5 }, lem: { 332: 17.8, 384: 20.6 }, podlaha: { 101: 1.0, 137: 1.4, 210: 2.1 }, slot: 100 };
const SUP_TYPY = ["S443x332x137", "S695x332x137", "S950x332x137", "S443x332x210", "S695x332x210", "S443x384x137", "S695x384x137", "S950x384x137", "S443x384x210", "S695x384x210", "S950x384x210", "S950x384x101"];
function supOracle(k) {
  const m = /^S(\d+)x(\d+)x(\d+)$/.exec(k), L = +m[1], W = +m[2], H = +m[3], vnitrni = W - SUP.celo[W] - SUP.lem[W], v = H - 8;
  return { L, W, H, max: Math.floor((L - 2 * SUP.bok[L]) / SUP.slot), bok: SUP.bok[L], celo: SUP.celo[W], lem: SUP.lem[W], podlaha: SUP.podlaha[H], vnitrni, delka: Math.floor(vnitrni), v, y: SUP.podlaha[H] + v / 2, z: SUP.celo[W] + vnitrni / 2, dil: "ps" + W + "v" + H };
}
const longAxis = (mb) => ((mb.max[0] - mb.min[0]) >= (mb.max[2] - mb.min[2]) ? 0 : 2);
// jedna pricka podnosu ve SVETE proti dutine podnosu podle kontraktu: rozmery, poloha vuci celu (e = +1: celo na MIN strane osy b, e = -1: na MAX), uprostred dutiny, ve slotu po 100 mm, na podlaze
function checkPlateSup(pl, mb, key) {
  const o = supOracle(key), a = longAxis(mb), b = 2 - a, eps = 0.12, errs = [], sz = pl.max.map((x, k) => x - pl.min[k]);
  if (!near(sz[a], 2, eps)) errs.push("tloustka " + sz[a]);
  if (!near(sz[b], o.delka, eps)) errs.push("delka zepredu dozadu " + sz[b] + " != " + o.delka);
  if (!near(sz[1], o.v, eps)) errs.push("vyska " + sz[1] + " != " + o.v);
  const celo = mb.e > 0 ? mb.min[b] : mb.max[b];
  const z0 = mb.e > 0 ? pl.min[b] - celo : celo - pl.max[b], z1 = mb.e > 0 ? pl.max[b] - celo : celo - pl.min[b];
  if (z0 < o.celo - eps) errs.push("zasahuje pred dutinu u cela: " + z0);
  if (z1 > o.W - o.lem + eps) errs.push("zasahuje do zadniho lemu: " + z1);
  if (!near((z0 + z1) / 2, o.z, eps)) errs.push("neni uprostred dutiny: " + ((z0 + z1) / 2) + " != " + o.z);
  const x0 = pl.min[a] - mb.min[a], x1 = pl.max[a] - mb.min[a];
  if (x0 < o.bok - eps || x1 > o.L - o.bok + eps) errs.push("mimo dutinu podel sirky: " + x0 + ".." + x1);
  const xc = (x0 + x1) / 2, j = (xc - o.L / 2) / SUP.slot + (o.max + 1) / 2;
  if (Math.abs(j - Math.round(j)) * SUP.slot > eps || Math.round(j) < 1 || Math.round(j) > o.max) errs.push("neni ve slotu: x " + xc + " slot " + j.toFixed(3));
  if (!near(pl.min[1] - mb.min[1], o.podlaha, eps)) errs.push("nestoji na podlaze: " + (pl.min[1] - mb.min[1]) + " != " + o.podlaha);
  if (pl.max[1] - mb.min[1] > o.H + eps) errs.push("presahuje vysku podnosu");
  for (let i = 0; i < 3; i++) if (pl.min[i] < mb.min[i] - eps || pl.max[i] > mb.max[i] + eps) errs.push("mimo AABB osa " + i);
  return errs;
}
// presne mapovani mistni -> svet u supliku (os 'b'): x od min[a] BEZ prevraceni, z od cela (e urcuje stranu cela na ose b), y od min[1]
function mapErrorsSup(pl, mb, d) {
  const a = longAxis(mb), b = 2 - a, c = center(pl), sz = pl.max.map((x, k) => x - pl.min[k]), errs = [];
  const zloc = mb.e > 0 ? c[b] - mb.min[b] : mb.max[b] - c[b];
  if (!near(c[a] - mb.min[a], d.s[0], 0.06) || !near(zloc, d.s[2], 0.06) || !near(c[1] - mb.min[1], d.s[1], 0.06)) errs.push("stred " + c.map((x) => x.toFixed(1)) + " vs desky " + d.s);
  if (!near(sz[a], d.r[0], 0.06) || !near(sz[1], d.r[1], 0.06) || !near(sz[b], d.r[2], 0.06)) errs.push("rozmer " + sz.map((x) => x.toFixed(1)) + " vs desky " + d.r);
  return errs;
}
// vsechny kontroly jednoho PODNOSU (r = platesOf): pocet, mesh + hrany, poloha vuci dutine, mapovani na desky payloadu, sloty (ruzne, rovnomerne rozlozene, plny pocet = vsechny sloty)
function trayErrors(r, bx, mb, desky, n) {
  const errs = [], o = supOracle(bx.k);
  if (n === 0) { if (r.groups !== 0 || r.plates.length !== 0) errs.push("ma mit 0 pricek, ma " + r.plates.length); return errs; }
  if (desky.length !== n || r.plates.length !== n || r.tris !== 12 * n || r.lineVerts !== 24 * n || r.meshes !== 1 || r.groups !== 1) { errs.push("pocet/geometrie " + JSON.stringify([n, desky.length, r.plates.length, r.tris, r.lineVerts, r.meshes, r.groups])); return errs; }
  const a = longAxis(mb), js = [];
  r.plates.forEach((pl, i) => {
    checkPlateSup(pl, mb, bx.k).concat(mapErrorsSup(pl, mb, desky[i])).forEach((e) => errs.push("#" + i + ": " + e));
    js.push(Math.round(((pl.min[a] + pl.max[a]) / 2 - mb.min[a] - o.L / 2) / SUP.slot + (o.max + 1) / 2));
  });
  js.sort((x, y) => x - y);
  if (new Set(js).size !== js.length) errs.push("dve pricky ve stejnem slotu " + js);
  const gaps = [js[0]];
  for (let i = 1; i < js.length; i++) gaps.push(js[i] - js[i - 1]);
  gaps.push(o.max + 1 - js[js.length - 1]);
  if (Math.max.apply(null, gaps) - Math.min.apply(null, gaps) > 1) errs.push("sloty nejsou rovnomerne (mezery " + gaps + ")");
  if (n === o.max && JSON.stringify(js) !== JSON.stringify(Array.from({ length: o.max }, (_, i) => i + 1))) errs.push("plny pocet neobsazuje vsechny sloty: " + js);
  return errs;
}
// id pohybu vieweru, ktere otevrou boxy skupin - NEZAVISLY vypocet ze spec (box -> pohyby, jejichz steps[].p je jeho pivot; prednost k 'box', jinak prvni; unikatne v poradi boxu)
const expectIds = (spec, P, gids) => {
  const out = [];
  gids.forEach((gid) => grpOf(P, gid).boxy.forEach((id) => {
    const mb = (spec.mbx || []).find((m) => m.id === id);
    if (!mb || !mb.p) return;
    const ms = (spec.motions || []).filter((mo) => mo && Array.isArray(mo.steps) && mo.steps.some((st) => st && st.p === mb.p));
    const pick = ms.find((mo) => mo.k === "box") || ms[0];
    if (pick && out.indexOf(pick.id) < 0) out.push(pick.id);
  }));
  return out;
};

(async () => {
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const pages = [];
  async function viewerPage(glb, payload, extra, preset) {
    const ctx = await browser.newContext({ viewport: { width: 1200, height: 760 }, locale: "cs-CZ" });
    const page = await ctx.newPage(); pages.push(ctx);
    await page.goto(base + "/viewer.html", { waitUntil: "load" });
    await page.evaluate(([g, p, x, pre]) => window.mount(g, p, x, pre), [glb, payload, extra || null, preset || null]);
    await page.waitForFunction(() => window.v.state().ready, null, { timeout: 120000 });
    await page.waitForTimeout(500);
    return page;
  }
  async function directPage(glb, payload, o) {
    const ctx = await browser.newContext({ viewport: { width: 400, height: 300 } });
    const page = await ctx.newPage(); pages.push(ctx);
    await page.goto(base + "/direct.html", { waitUntil: "load" });
    const r = await page.evaluate(([g, p, x]) => window.direct(g, p, x), [glb, payload, o || null]);
    return { page, r };
  }
  const errsOf = (page) => page.evaluate(() => window.__errs.slice());
  const shot = async (page, name) => { if (!SHOTS) return; try { await page.screenshot({ path: path.join(SHOTS, name), timeout: 90000 }); } catch (e) { console.log("[PRESKOCENO] snimek " + name + ": " + e.message.split("\n")[0]); } };
  // geometrie pricek ve SVETE pro vyber selMap {boxId: n} u boxu ids (ktere jsou v modelu): pocet n, 1 spojeny mesh + hrany, ve slotech, uvnitr studny, presne mapovani na typy[k].pocty[n].desky
  async function checkBoxes(pg, P, mbxList, selMap, ids, root) {
    const errs = [], counts = { boxes: 0, plates: 0 };
    for (const id of ids) {
      const bx = boxOf(P, id), mb = mbxList.find((m) => m.id === id);
      if (!bx || !mb) continue;
      const n = selMap[id] || 0, desky = P.typy[bx.k].pocty[n].desky;
      const r = await pg.evaluate(([root, id]) => platesOf(root === "D" ? D.scene : model(), id), [root || "V", id]);
      counts.boxes++; counts.plates += r.plates.length;
      if (n === 0) { if (r.groups !== 0 || r.plates.length !== 0) errs.push(id + " ma mit 0 pricek, ma " + r.plates.length); continue; }
      if (r.plates.length !== desky.length || r.tris !== 12 * desky.length || r.lineVerts !== 24 * desky.length || r.meshes !== 1 || r.groups !== 1) { errs.push(id + " pocet/geometrie " + JSON.stringify([r.plates.length, r.tris, r.lineVerts, r.meshes, r.groups])); continue; }
      slotErrors(bx.k, desky).forEach((e) => errs.push(id + " " + e));
      r.plates.forEach((pl, i) => { checkPlate(pl, mb, P.geom).concat(mapErrors(pl, mb, desky[i])).forEach((e) => errs.push(id + "#" + i + ": " + e)); });
    }
    return { errs, counts };
  }

  // geometrie VSECH uvedenych boxu (multibox i podnos supliku) pro vyber selMap {id: n}: jedno vyhodnoceni ve strance, kontrola podle typu boxu
  async function checkAny(pg, P, mbxList, selMap, ids, root) {
    const errs = [], counts = { boxes: 0, plates: 0 };
    const infos = await pg.evaluate(([ids, root]) => ids.map((id) => platesOf(root === "D" ? D.scene : model(), id)), [ids, root || "V"]);
    ids.forEach((id, i) => {
      const bx = boxOf(P, id), mb = mbxList.find((m) => m.id === id);
      if (!bx || !mb) return;
      const r = infos[i], n = selMap[id] || 0, desky = P.typy[bx.k].pocty[n].desky;
      counts.boxes++;
      counts.plates += r.plates.length;
      if (/^S\d/.test(bx.k)) { trayErrors(r, bx, mb, desky, n).forEach((e) => errs.push(id + " " + e)); return; }
      if (n === 0) { if (r.groups !== 0 || r.plates.length !== 0) errs.push(id + " ma mit 0 pricek, ma " + r.plates.length); return; }
      if (r.plates.length !== desky.length || r.tris !== 12 * desky.length || r.lineVerts !== 24 * desky.length || r.meshes !== 1 || r.groups !== 1) { errs.push(id + " pocet/geometrie " + JSON.stringify([r.plates.length, r.tris, r.lineVerts, r.meshes, r.groups])); return; }
      slotErrors(bx.k, desky).forEach((e) => errs.push(id + " " + e));
      r.plates.forEach((pl, j) => { checkPlate(pl, mb, P.geom).concat(mapErrors(pl, mb, desky[j])).forEach((e) => errs.push(id + "#" + j + ": " + e)); });
    });
    return { errs, counts };
  }

  try {
    // ====================================================================== P) data: karta 4921 odpovida zadani (mixy, deduplikace, bez typy[k].sety)
    console.log("\n## P) data payloadu 4921 (v4: sety jen ve skupinach s po_boxech, geometrie z typy[k].pocty)");
    const P21 = payloadOf("4921"), spec21 = readSpec(cardGlb("4921")), mbx21 = spec21.mbx, geom = P21.geom;
    const grp = (id) => P21.skupiny.find((g) => g.id === id);
    const allIds = P21.boxy.map((b) => b.id);
    const s1b = grp("s1").boxy, s2b = grp("s2").boxy;
    const bA = s1b.find((id) => boxOf(P21, id).k === "395x186"), bB = s1b.find((id) => boxOf(P21, id).k === "395x91");
    const SET_ORDER = "bez,mix1,mix2,mix3,mix4,pln";
    t("P1 payload: 3 skupiny (police 8, vysuv 7, vysuv 7), kazda nabizi sety bez, mix1, mix2, mix3, mix4, pln s po_boxech delky = pocet boxu; typy[k] nemaji sety (jen max, dil, pocty 0..max)",
      P21.skupiny.length === 3 && P21.skupiny.map((g) => g.boxy.length).join() === "8,7,7" && P21.skupiny.every((g) => keysOrdered(g.sety) === SET_ORDER && Object.keys(g.sety).every((sid) => g.sety[sid].po_boxech.length === g.boxy.length))
      && Object.keys(P21.typy).every((k) => !("sety" in P21.typy[k]) && P21.typy[k].pocty.length === P21.typy[k].max + 1 && P21.typy[k].pocty.every((x, n) => x.n === n && x.desky.length === n)) && P21.sety.map((x) => x.id).join() === SET_ORDER,
      [P21.skupiny.map((g) => [g.id, g.boxy.length, keysOrdered(g.sety)]), Object.keys(P21.typy)]);
    t("P2 police s1 (8 boxu): mix1 [6,1,6,1,6,1,6,1], mix2 [6,3,6,3,...], mix3 [6,6,1,6,6,1,6,6], mix4 [1,1,3,3,3,3,6,6] (postupne od raddeho k hustemu), pln [6 x 8] - presne dle zadani",
      JSON.stringify(grp("s1").sety.mix1.po_boxech) === "[6,1,6,1,6,1,6,1]" && JSON.stringify(grp("s1").sety.mix2.po_boxech) === "[6,3,6,3,6,3,6,3]" && JSON.stringify(grp("s1").sety.mix3.po_boxech) === "[6,6,1,6,6,1,6,6]"
      && JSON.stringify(grp("s1").sety.mix4.po_boxech) === "[1,1,3,3,3,3,6,6]" && JSON.stringify(grp("s1").sety.pln.po_boxech) === "[6,6,6,6,6,6,6,6]" && JSON.stringify(grp("s1").sety.bez.po_boxech) === "[0,0,0,0,0,0,0,0]", grp("s1").sety);
    t("P3 u kazdeho setu platí: priccek = soucet po_boxech, cena skupiny = soucet po_boxech x cena dilu typu boxu (cena setu z payloadu sedi s vlastnim vypoctem)",
      P21.skupiny.every((g) => Object.keys(g.sety).every((sid) => { const m = {}; g.boxy.forEach((id, i) => { if (g.sety[sid].po_boxech[i]) m[id] = g.sety[sid].po_boxech[i]; }); const e = expectSummary(P21, m); return g.sety[sid].priccek === e.kusy && near(g.sety[sid].cena, e.cena_net, 0.005); })));
    gate();

    // ====================================================================== A) viewer, karta 4921 (police 8 + 2 suplíky po 7 boxech, vse v pivotech, e = +1): sety jako hotove mixy
    if (run("A")) console.log("\n## A) viewer + plugin, karta 4921: hotove mixy pro celou policii / suplik (setGroup, setAll), souhrn, neplatne vstupy");
    const needPg = ["A", "M", "K", "B", "C", "D", "E", "F", "N"].some(run);
    const pg = needPg ? await viewerPage("/fx/4921.offer.glb", P21) : null;
    const chk = (selMap, ids) => checkBoxes(pg, P21, mbx21, selMap, ids || allIds);
    const motionIds = pg ? await pg.evaluate(() => v.state().motions.map((m) => m.id)) : [];
    if (run("A")) {
      const sk0 = await pg.evaluate(() => ({ s: pr.api.skupiny(), b: pr.api.boxes(), ready: pr.api.ready() }));
      t("A1 plugin bezi; skupiny(): 3 skupiny (id, druh, popis, pocet boxu z payloadu), vsechny ready, set 'bez', 0 pricek, nabizene sety = sety skupiny z payloadu; boxes(): 22 boxu ready, n 0, max / dil z typu, poradi z payloadu",
        sk0.ready && sk0.s.length === 3 && sk0.s.every((g, i) => g.id === P21.skupiny[i].id && g.ready && g.pocet_ready === g.boxu && g.boxu === P21.skupiny[i].boxy.length && g.set === "bez" && g.priccek === 0 && g.cena === 0 && g.boxu_s_pricky === 0
          && g.popis === P21.skupiny[i].popis && g.k === P21.skupiny[i].k && g.sety.join() === keysOrdered(P21.skupiny[i].sety))
        && sk0.b.length === 22 && sk0.b.every((b, i) => b.ready && b.id === P21.boxy[i].id && b.k === P21.boxy[i].k && b.s === P21.boxy[i].s && b.n === 0 && b.poradi === P21.boxy[i].n && b.max === P21.typy[b.k].max && b.dil === P21.typy[b.k].dil && b.cena === 0), sk0);
      const s0 = await pg.evaluate(() => ({ s: pr.api.souhrn(), g: pr.api.get(), groups: countGroups(model()), gi: pr.api.groupInfo("s1"), unk: pr.api.groupInfo("s9") }));
      t("A2 na zacatku bez vyberu: get() prazdne, souhrn nulovy, v modelu zadna skupina pricek; groupInfo('s1') = bez, 8 boxu, po_boxech samé nuly; neznama skupina = null",
        Object.keys(s0.g).length === 0 && s0.s.kusy === 0 && s0.s.cena_net === 0 && s0.s.boxu === 0 && s0.s.radky.length === 0 && s0.s.skupiny.length === 0 && s0.groups === 0
        && eq(s0.gi, { set: "bez", priccek: 0, cena: 0, boxu_s_pricky: 0, boxu: 8, po_boxech: [0, 0, 0, 0, 0, 0, 0, 0] }) && s0.unk === null, s0);
      const e1 = fromSet(P21, "s1", "mix4");
      const r1 = await pg.evaluate(() => ({ r: pr.api.setGroup("s1", "mix4"), get: pr.api.get(), groups: countGroups(model()), ch: __changes.length, last: __changes[__changes.length - 1], gi: pr.api.groupInfo("s1") }));
      t("A3 setGroup('s1','mix4') = true: pocty po boxech z po_boxech setu [1,1,3,3,3,3,6,6] (get() po boxech, razene), groupInfo = mix4 s cenou setu z payloadu, 8 skupin pricek ve 3D, onChange prave 1x se stavem po boxech",
        r1.r === true && eq(r1.get, e1) && keysOrdered(r1.get) === s1b.join() && r1.groups === 8 && r1.ch === 1 && eq(r1.last.v, e1) && r1.last.s.kusy === 26 && r1.last.s.skupiny.length === 1
        && eq(r1.gi, { set: "mix4", priccek: 26, cena: grp("s1").sety.mix4.cena, boxu_s_pricky: 8, boxu: 8, po_boxech: [1, 1, 3, 3, 3, 3, 6, 6] }), r1);
      const cg = await chk(e1);
      const cntBox = await pg.evaluate((ids) => ids.map((id) => platesOf(model(), id).plates.length), s1b);
      t("A4 Mix 4: v jedne polici maji boxy VIDITELNE ruzne pocty pricek ve 3D (1,1,3,3,3,3,6,6 = 3 ruzne hodnoty); kazda pricka kazdeho boxu: ve slotu, uvnitr studny, na dne, vyska 75, tloustka 2, konec s vykrojem volny, presne mapovani na desky payloadu",
        cg.errs.length === 0 && cg.counts.boxes === 22 && cg.counts.plates === 26 && cntBox.join() === "1,1,3,3,3,3,6,6" && new Set(cntBox).size === 3, [cg.errs.slice(0, 5), cntBox]);
      const e2 = Object.assign({}, e1, fromSet(P21, "s2", "pln"));
      const r2s = await pg.evaluate(() => ({ r: pr.api.setGroup("s2", "pln"), sou: pr.api.souhrn(), sk: pr.api.skupiny().map((g) => [g.id, g.set]) }));
      const cg2 = await chk(e2);
      t("A5 setGroup('s2','pln'): 7 boxu x 6 pricek, policni mix 4 se nezmenil; souhrn = vypocet z payloadu, cena = cena Mixu 4 policie + cena Plneho setu suplíku, rozpis po dilech = soucet dily setu; skupina s3 bez pricek",
        r2s.r === true && cg2.errs.length === 0 && cg2.counts.plates === 26 + 42 && sumOk(r2s.sou, expectSummary(P21, e2)) && near(r2s.sou.cena_net, grp("s1").sety.mix4.cena + grp("s2").sety.pln.cena, 0.005)
        && eq(r2s.sou.radky.map((x) => [x.klic, x.qty]), P21.dily.map((d) => [d.klic, (grp("s1").sety.mix4.dily[d.klic] || 0) + (grp("s2").sety.pln.dily[d.klic] || 0)]).filter((x) => x[1] > 0))
        && eq(r2s.sk, [["s1", "mix4"], ["s2", "pln"], ["s3", "bez"]]), [r2s.sou, r2s.sk]);
      const sou = r2s.sou;
      t("A6 souhrn je vnitrne konzistentni: cena_net = soucet radky.total = soucet skupiny.cena, kusy = soucet radky.qty = soucet skupiny.priccek, unit_price z payloadu, total = qty x unit_price",
        near(sou.cena_net, sou.radky.reduce((a, r) => a + r.total, 0), 0.005) && near(sou.cena_net, sou.skupiny.reduce((a, r) => a + r.cena, 0), 0.005) && sou.kusy === sou.radky.reduce((a, r) => a + r.qty, 0)
        && sou.kusy === sou.skupiny.reduce((a, r) => a + r.priccek, 0) && sou.radky.every((r) => near(r.unit_price, P21.dily.find((d) => d.klic === r.klic).cena, 1e-9) && near(r.total, r.qty * r.unit_price, 0.005)), sou);
      const e3 = fromSets(P21, { s1: "mix2", s2: "mix2", s3: "mix2" });
      const n3 = await pg.evaluate(() => pr.api.setAll("mix2"));
      const g3 = await pg.evaluate(() => ({ get: pr.api.get(), groups: countGroups(model()), s: pr.api.souhrn(), sk: pr.api.skupiny().map((g) => g.set).join() }));
      const cg3 = await chk(e3);
      t("A7 setAll('mix2') = 3 (vsechny skupiny set nabizeji): kazdy box ma pocet z po_boxech SVE skupiny (6,3,6,3,...), 22 boxu s pricky, souhrn = soucet cen setu Mix 2, vsechny skupiny rozpoznany jako mix2",
        n3 === 3 && eq(g3.get, e3) && g3.groups === 22 && cg3.errs.length === 0 && g3.sk === "mix2,mix2,mix2" && sumOk(g3.s, expectSummary(P21, e3)) && near(g3.s.cena_net, P21.skupiny.reduce((a, g) => a + g.sety.mix2.cena, 0), 0.005), [n3, g3.sk, cg3.errs.slice(0, 3)]);
      await pg.evaluate(() => pr.api.setGroup("s1", "bez"));
      const e4 = Object.assign({}, e3); s1b.forEach((id) => { delete e4[id]; });
      const r8 = await pg.evaluate(() => ({ g: pr.api.get(), n: countGroups(model()), s: pr.api.souhrn(), o: pr.api.setOf("s1"), gi: pr.api.groupInfo("s1") }));
      const cg4 = await chk(e4);
      t("A8 setGroup('s1','bez') pricky policie odstrani (zbyva 14 boxu), s1 zmizela z get() i ze souhrnu, setOf / groupInfo = 'bez'", eq(r8.g, e4) && r8.n === 14 && cg4.errs.length === 0 && r8.s.skupiny.length === 2 && r8.o === "bez" && r8.gi.set === "bez" && r8.gi.priccek === 0, r8);
      await pg.evaluate(() => pr.api.setGroup("s1", "mix1"));
      const ch0 = await pg.evaluate(() => __changes.length);
      await pg.evaluate(() => pr.api.setGroup("s1", "pln"));
      const ch1 = await pg.evaluate(() => __changes.length);
      const again = await pg.evaluate(() => [pr.api.setGroup("s1", "pln"), __changes.length]);
      t("A9 zmena setu = 1x onChange; stejny set znovu = zadna zmena (onChange se nevola), setGroup ale vrati true", ch1 === ch0 + 1 && again[0] === true && again[1] === ch1, [ch0, ch1, again]);
      const ch2 = await pg.evaluate(() => __changes.length), selB = await pg.evaluate(() => JSON.stringify(pr.api.get()));
      const bads = await pg.evaluate(() => [pr.api.setGroup("s9", "pln"), pr.api.setGroup("s1", "zzz"), pr.api.setGroup("s1", "zak"), pr.api.setGroup("s1", "str"), pr.api.setGroup("__proto__", "pln"), pr.api.setGroup("s1", 5), pr.api.setGroup(7, "pln"), pr.api.setGroup(null, null),
        pr.api.setAll("zzz"), pr.api.setAll("zak"), pr.api.setAll(null), pr.api.setAll(5), pr.api.setMany(null), pr.api.setMany("x"), pr.api.setMany(5),
        pr.api.setBox("b99", 1), pr.api.setBox("__proto__", 1), pr.api.setBox(7, 1), pr.api.setBox(null, null),
        pr.api.highlightGroup("s9"), pr.api.highlightGroup(5), pr.api.highlightGroup("__proto__"), pr.api.highlightBox("b99"), pr.api.highlightBox(5), pr.api.highlightBox("__proto__"),
        ({}).polluted === undefined, pr.api.setOf("s9"), pr.api.setOf("__proto__"), pr.api.setOf(null), pr.api.groupInfo("s9"), pr.api.groupInfo("__proto__"), pr.api.groupInfo(5)]);
      t("A10 neplatne vstupy (neznama skupina, zrusene sety 'zak' / 'str', neznamy set, spatne typy, __proto__) = false / 0 / null a NIC se nezmeni (bez onChange, stejny vyber, bez znecisteni prototypu)",
        JSON.stringify(bads) === JSON.stringify([false, false, false, false, false, false, false, false, 0, 0, 0, 0, 0, 0, 0, false, false, false, false, false, false, false, false, false, false, true, null, null, null, null, null, null])
        && await pg.evaluate(() => __changes.length) === ch2 && await pg.evaluate(() => JSON.stringify(pr.api.get())) === selB, bads);
      const sm = await pg.evaluate(() => ({ n: pr.api.setMany({ b01: 2, b02: 6, b99: 1, b03: 7, b04: -1, b05: 1.5, b06: "3", b07: 0, b08: null }), g: pr.api.get(), groups: countGroups(model()) }));
      t("A11 setMany nahradi CELY vyber (puvodni pricky zmizely), preskoci neplatne polozky (neznamy box, n mimo 0..max, zaporne, desetinne, retezec, null); n = 0 je platne, ale nepocita se; vraci pocet pouzitych (2)",
        sm.n === 2 && eq(sm.g, { b01: 2, b02: 6 }) && sm.groups === 2, sm);
      const cl = await pg.evaluate(() => ({ n: pr.api.clear(), g: pr.api.get(), groups: countGroups(model()), s: pr.api.souhrn() }));
      t("A12 clear(): vraci pocet boxu, kterym se zmenil stav (2), zadne skupiny pricek, get() prazdne, souhrn nulovy", cl.n === 2 && cl.groups === 0 && Object.keys(cl.g).length === 0 && cl.s.cena_net === 0 && cl.s.skupiny.length === 0, cl);
      const mat = await pg.evaluate((a) => { pr.api.setBox(a, 1); return platesOf(model(), a); }, bA);
      const hexOk = (h, w) => typeof h === "string" && h.length === 6 && [0, 2, 4].every((i) => Math.abs(parseInt(h.substr(i, 2), 16) - parseInt(w.substr(i, 2), 16)) <= 1);
      t("A13 vzhled: plocha svetle modra #dbe6ff (po prevodu barevneho prostoru viewer +-1), hrany tmave (barva hran nastavena)", hexOk(mat.color, "dbe6ff") && typeof mat.edgeColor === "string" && mat.edgeColor.length === 6 && parseInt(mat.edgeColor.substr(0, 2), 16) < 0x30, mat);
      const iso = await pg.evaluate((a) => { const g = pr.api.get(); g[a] = 99; g.b99 = 1; return JSON.stringify(pr.api.get()); }, bA);
      t("A14 get() vraci KOPII: zmena vraceneho objektu nema vliv na vyber", iso === JSON.stringify({ [bA]: 1 }), iso);
      t("A15 po vsech akcich bez chyb v konzoli a ve strance", (await errsOf(pg)).length === 0, await errsOf(pg));
    }
    gate();

    // ====================================================================== M) mixy: viditelne ruzne pocty v jedne polici, rozpoznani, ceny, pixelovy dukaz
    if (run("M")) console.log("\n## M) mixy v jedne polici: 5 hotovych setu, rozpoznani, ceny, ruzne pocty viditelne ve 3D");
    if (run("M")) {
      await pg.evaluate(() => pr.api.clear());
      let bad = [], seen = {};
      for (const sid of ["mix1", "mix2", "mix3", "mix4", "pln", "bez"]) {
        const e = fromSet(P21, "s1", sid), exp = grp("s1").sety[sid];
        const r = await pg.evaluate(([sid]) => ({ ok: pr.api.setGroup("s1", sid), gi: pr.api.groupInfo("s1"), get: pr.api.get(), sk: pr.api.skupiny()[0], sou: pr.api.souhrn() }), [sid]);
        const cg = await chk(e);
        const ex = expectSummary(P21, e);
        if (r.ok !== true || r.gi.set !== sid || r.gi.priccek !== exp.priccek || !near(r.gi.cena, exp.cena, 0.005) || JSON.stringify(r.gi.po_boxech) !== JSON.stringify(exp.po_boxech) || r.sk.set !== sid || !eq(r.get, e) || cg.errs.length || !sumOk(r.sou, ex)) bad.push(sid + " " + JSON.stringify([r.ok, r.gi, cg.errs.slice(0, 2)]));
        seen[sid] = await pg.evaluate((ids) => ids.map((id) => platesOf(model(), id).plates.length).join(), s1b);
      }
      t("M1 kazdy z 5 mixu (+ bez) na policii s1: pocty po boxech z payloadu, rozpoznani = id setu, priccek a cena sedi s payloadem, souhrn = vypocet, geometrie vsech 8 boxu ve 3D v poradku", bad.length === 0, bad.slice(0, 3));
      t("M2 pocty pricek v 8 boxech policie ve 3D: mix1 6,1,6,1,6,1,6,1 | mix2 6,3,6,3,6,3,6,3 | mix3 6,6,1,6,6,1,6,6 | mix4 1,1,3,3,3,3,6,6 | pln 6 x 8 | bez 0",
        seen.mix1 === "6,1,6,1,6,1,6,1" && seen.mix2 === "6,3,6,3,6,3,6,3" && seen.mix3 === "6,6,1,6,6,1,6,6" && seen.mix4 === "1,1,3,3,3,3,6,6" && seen.pln === "6,6,6,6,6,6,6,6" && seen.bez === "0,0,0,0,0,0,0,0", seen);
      // pixelovy dukaz: obraz cele policie (vysuny otevrene = boxy zvednute a videt) se pri kazdem mixu lisi od vsech ostatnich ve dvou pohledech (shora, z predu zvysoka)
      const gbox = s1b.map((id) => mbx21.find((m) => m.id === id)), c1 = [0, 1, 2].map((i) => (Math.min(...gbox.map((m) => m.min[i])) + Math.max(...gbox.map((m) => m.max[i]))) / 2);
      const sidsPix = ["bez", "mix1", "mix2", "mix3", "mix4", "pln"], views = [["A", [0.05, 1, 0.1], 1500], ["B", [0.6, 0.8, 1.0], 1400]];
      await pg.evaluate((ids) => { pr.api.clear(); const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); }, motionIds);
      for (const [vn, dir, dist] of views) {
        await pg.evaluate(([c, d, di]) => { cam(c, di, d); }, [c1, dir, dist]);
        for (const sid of sidsPix) await pg.evaluate(([sid, vn]) => { pr.api.setGroup("s1", sid); pix(sid + vn); }, [sid, vn]);
      }
      const diffs = {};
      let minDiff = 1e9;
      for (let i = 0; i < sidsPix.length; i++) for (let j = i + 1; j < sidsPix.length; j++) {
        const dA = await pg.evaluate(([a, b]) => pixDiff(a + "A", b + "A"), [sidsPix[i], sidsPix[j]]), dB = await pg.evaluate(([a, b]) => pixDiff(a + "B", b + "B"), [sidsPix[i], sidsPix[j]]);
        diffs[sidsPix[i] + "/" + sidsPix[j]] = [dA, dB]; minDiff = Math.min(minDiff, Math.max(dA, dB));
      }
      t("M3 vsech 6 stavu policie (bez, mix1..mix4, pln) se na platne lisi navzajem (kazda dvojice aspon 60 pixelu rozdilu aspon v jednom ze dvou pohledu, vysuny otevrene): ruzne mixy jsou ve 3D rozlisitelne", minDiff >= 60, { minDiff, diffs });
      await pg.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); });
      if (SHOTS) {
        for (const sid of ["mix1", "mix4"]) { await pg.evaluate(([sid]) => { pr.api.setGroup("s1", sid); v.debug.renderNow(); }, [sid]); await pg.waitForTimeout(300); await shot(pg, "police_" + sid + ".png"); }
      }
      // rozpoznani setu podle poctu po boxech (setBox po jednom odpovida setu z payloadu)
      const recRes = await pg.evaluate(([ids, mix2, mix4, pln]) => {
        pr.api.clear();
        const out = {};
        ids.forEach((id, i) => pr.api.setBox(id, mix2[i]));
        out.m2 = [pr.api.groupInfo("s1").set, pr.api.skupiny()[0].set, pr.api.souhrn().skupiny.map((x) => x.set).join(), pr.api.setOf("s1")];
        pr.api.setBox(ids[3], mix2[3] === 6 ? 5 : mix2[3] + 1);
        out.vl = pr.api.groupInfo("s1").set;
        pr.api.setBox(ids[3], mix2[3]);
        out.back = pr.api.groupInfo("s1").set;
        ids.forEach((id, i) => pr.api.setBox(id, mix4[i]));
        out.m4 = pr.api.groupInfo("s1").set;
        ids.forEach((id, i) => pr.api.setBox(id, pln[i]));
        out.pln = pr.api.groupInfo("s1").set;
        ids.forEach((id) => pr.api.setBox(id, 0));
        out.bez = [pr.api.groupInfo("s1").set, pr.api.souhrn().skupiny.length];
        return out;
      }, [s1b, grp("s1").sety.mix2.po_boxech, grp("s1").sety.mix4.po_boxech, grp("s1").sety.pln.po_boxech]);
      t("M4 rozpoznani podle poctu po boxech: pocty presne podle Mixu 2 = 'mix2' (groupInfo, skupiny(), souhrn, setOf), zmena jednoho boxu = 'vlastni', vraceni = 'mix2', pocty Mixu 4 = 'mix4', pln = 'pln', samé nuly = 'bez' (a skupina neni v souhrnu)",
        eq(recRes.m2, ["mix2", "mix2", "mix2", "mix2"]) && recRes.vl === "vlastni" && recRes.back === "mix2" && recRes.m4 === "mix4" && recRes.pln === "pln" && eq(recRes.bez, ["bez", 0]), recRes);
      // prepnuti z vlastni kombinace na set prepise VSECHNY boxy skupiny
      const ov = {};
      await pg.evaluate(([ids]) => { pr.api.clear(); pr.api.setBox(ids[0], 6); pr.api.setBox(ids[1], 2); pr.api.setBox(ids[2], 4); }, [s1b]);
      ov.custom = await pg.evaluate(() => pr.api.groupInfo("s1"));
      await pg.evaluate(() => pr.api.setGroup("s1", "mix3"));
      ov.mix3 = await pg.evaluate(() => [pr.api.groupInfo("s1"), pr.api.get()]);
      const cgOv1 = await chk(fromSet(P21, "s1", "mix3"));
      await pg.evaluate(([ids]) => { pr.api.setBox(ids[0], 1); pr.api.setBox(ids[7], 3); pr.api.setBox(ids[4], 0); }, [s1b]);
      ov.custom2 = await pg.evaluate(() => pr.api.groupInfo("s1").set);
      await pg.evaluate(() => pr.api.setGroup("s1", "pln"));
      ov.pln = await pg.evaluate(() => [pr.api.groupInfo("s1"), pr.api.get()]);
      const cgOv2 = await chk(fromSet(P21, "s1", "pln"));
      await pg.evaluate(([ids]) => { pr.api.setBox(ids[2], 2); }, [s1b]);
      await pg.evaluate(() => pr.api.setGroup("s1", "bez"));
      ov.bez = await pg.evaluate(() => [pr.api.groupInfo("s1"), pr.api.get(), countGroups(model())]);
      t("M5 prepnuti z VLASTNI kombinace na set prepise VSECHNY boxy skupiny: vlastni (6,2,4,0..) -> Mix 3 [6,6,1,6,6,1,6,6] -> (znovu vlastni) -> Plny [6 x 8] -> (vlastni) -> bez: zadne zbytky puvodnich poctu, geometrie sedi",
        ov.custom.set === "vlastni" && ov.custom.priccek === 12 && ov.mix3[0].set === "mix3" && eq(ov.mix3[1], fromSet(P21, "s1", "mix3")) && cgOv1.errs.length === 0 && ov.custom2 === "vlastni" && ov.pln[0].set === "pln" && eq(ov.pln[1], fromSet(P21, "s1", "pln")) && cgOv2.errs.length === 0
        && ov.bez[0].set === "bez" && Object.keys(ov.bez[1]).length === 0 && ov.bez[2] === 0, ov);
    }
    gate();

    // ====================================================================== K) vyber po boxech (API zustava pro budouci pouziti): setBox, rozsahy, ceny, obrysy
    if (run("K")) console.log("\n## K) pocty po boxech: setBox (rozsah, ceny, onChange), obrys boxu (highlightBox)");
    if (run("K")) {
      await pg.evaluate(() => { pr.api.clear(); pr.api.highlightGroup(null); });
      const chB0 = await pg.evaluate(() => __changes.length);
      const k1 = await pg.evaluate(([x, y]) => ({ r: [pr.api.setBox(y, 2), pr.api.setBox(x, 6)], get: pr.api.get(), ch: __changes.length, last: __changes[__changes.length - 1], gi: pr.api.groupInfo("s1"), sk: pr.api.skupiny()[0] }), [s1b[0], s1b[1]]);
      const selK1 = { [s1b[0]]: 6, [s1b[1]]: 2 }, exK1 = expectSummary(P21, selK1);
      const cgK1 = await chk(selK1);
      t("K1 setBox po boxech v jedne polici (pocty 6 a 2, zadano v opacnem poradi): get() razene podle cisla boxu, onChange 2x s vyberem po boxech, skupina = 'vlastni' (8 priccek, cena podle dilu typu boxu), geometrie: 6 a 2 pricky, ostatni boxy bez",
        eq(k1.r, [true, true]) && eq(k1.get, selK1) && keysOrdered(k1.get) === s1b[0] + "," + s1b[1] && k1.ch === chB0 + 2 && eq(k1.last.v, selK1) && k1.gi.set === "vlastni" && k1.gi.priccek === 8 && near(k1.gi.cena, exK1.skupiny[0].cena, 0.005) && k1.gi.boxu_s_pricky === 2
        && k1.sk.set === "vlastni" && cgK1.errs.length === 0 && cgK1.counts.plates === 8, [k1, cgK1.errs.slice(0, 3)]);
      const k2 = await pg.evaluate(([a, b]) => { pr.api.clear(); pr.api.setBox(a, 3); pr.api.setBox(b, 5); return { s: pr.api.souhrn(), bx: pr.api.boxes().filter((x) => x.n > 0) }; }, [bA, bB]);
      const u186 = P21.dily.find((d) => d.klic === "p186").cena, u91 = P21.dily.find((d) => d.klic === "p91").cena;
      t("K2 ruzne typy boxu v jedne polici (395x186 + 395x91): souhrn ma dva radky (p186 3 ks, p91 5 ks) s cenou podle dilu typu, boxes()[].cena = n x cena dilu, soucet cen boxu = cena_net",
        k2.s.radky.length === 2 && k2.s.radky[0].klic === "p186" && k2.s.radky[0].qty === 3 && near(k2.s.radky[0].total, 3 * u186, 0.005) && k2.s.radky[1].klic === "p91" && k2.s.radky[1].qty === 5 && near(k2.s.radky[1].total, 5 * u91, 0.005)
        && near(k2.s.cena_net, 3 * u186 + 5 * u91, 0.005) && k2.bx.length === 2 && near(k2.bx.find((x) => x.id === bA).cena, 3 * u186, 0.005) && near(k2.bx.find((x) => x.id === bB).cena, 5 * u91, 0.005)
        && near(k2.bx.reduce((a, x) => a + x.cena, 0), k2.s.cena_net, 0.005) && sumOk(k2.s, expectSummary(P21, { [bA]: 3, [bB]: 5 })), k2);
      const k3 = await pg.evaluate(([a]) => {
        const g0 = JSON.stringify(pr.api.get()), c0 = __changes.length, mx = pr.api.boxes().find((x) => x.id === a).max;
        const res = [mx + 1, -1, 1.5, "3", NaN, null, undefined, Infinity, true, {}, [2]].map((n) => pr.api.setBox(a, n));
        return { res: res, same: JSON.stringify(pr.api.get()) === g0, noch: __changes.length === c0, mx: mx, p: platesOf(model(), a).plates.length };
      }, [bA]);
      t("K3 setBox mimo rozsah / neplatne n (max + 1, -1, 1.5, '3', NaN, null, undefined, Infinity, true, {}, [2]) = false, vyber, onChange i geometrie beze zmeny", k3.mx === 6 && k3.res.every((x) => x === false) && k3.same && k3.noch && k3.p === 3, k3);
      const k3b = await pg.evaluate(([a]) => { const c0 = __changes.length; const r1 = pr.api.setBox(a, 6), c1 = __changes.length; const r2 = pr.api.setBox(a, 6), c2 = __changes.length; return { r1, r2, d1: c1 - c0, d2: c2 - c1, p: platesOf(model(), a).plates.length }; }, [bA]);
      t("K4 horni mez (n = max = 6) je platna; stejny pocet znovu = true bez onChange", k3b.r1 === true && k3b.r2 === true && k3b.d1 === 1 && k3b.d2 === 0 && k3b.p === 6, k3b);
      const k4 = await pg.evaluate(([a, b]) => { const c0 = __changes.length; const r = pr.api.setBox(a, 0); const r2 = pr.api.setBox(a, 0); return { r, r2, ch: __changes.length - c0, p: platesOf(model(), a), g: pr.api.get(), hasB: !!pr.api.get()[b] }; }, [bA, bB]);
      t("K5 setBox(box, 0) odstrani pricky (zadna skupina ve scene), box zmizi z get(), druhy box zustane; opakovani = true bez onChange", k4.r === true && k4.r2 === true && k4.ch === 1 && k4.p.groups === 0 && k4.p.plates.length === 0 && !(bA in k4.g) && k4.hasB, k4);
      // obrys jednoho boxu a skupiny
      const mbA = mbx21.find((m) => m.id === bA), mbB = mbx21.find((m) => m.id === bB);
      const h1 = await pg.evaluate(([a]) => ({ r: pr.api.highlightBox(a), hl: hlList(model()), n: countHl(model()) }), [bA]);
      t("K6 highlightBox(box) = true: PRAVE 1 obrys (3 objekty: skupina, plocha, hrany) obklopujici AABB boxu o ~2 mm", h1.r === true && h1.hl.length === 1 && h1.hl[0].box === bA && h1.hl[0].gid === bA && h1.n === 3
        && mbA.min.every((v, i) => near(h1.hl[0].min[i], v - 2, 0.05) && near(h1.hl[0].max[i], mbA.max[i] + 2, 0.05)), h1);
      const h2 = await pg.evaluate(() => ({ r: pr.api.highlightGroup("s2"), hl: hlList(model()).map((x) => x.box), n: countHl(model()) }));
      const h3 = await pg.evaluate(([b]) => ({ r: pr.api.highlightBox(b), hl: hlList(model()).map((x) => x.box), n: countHl(model()) }), [bB]);
      const h4 = await pg.evaluate(() => ({ r: pr.api.highlightBox(null), n: countHl(model()) }));
      const h5 = await pg.evaluate(([a]) => { pr.api.highlightBox(a); return { r: [pr.api.highlightBox("b99"), pr.api.highlightBox(5), pr.api.highlightBox("__proto__")], hl: hlList(model()).map((x) => x.box) }; }, [bA]);
      t("K7 novy obrys nahradi predchozi (box -> skupina s2 = 7 obrysu bez boxu bA -> box bB = 1 obrys); highlightBox(null) vse uklidi; neplatny box = false a stavajici obrys zustane",
        h2.r === true && eq(h2.hl.slice().sort(), s2b.slice().sort()) && h2.n === 21 && h3.r === true && eq(h3.hl, [bB]) && h3.n === 3 && h4.r === true && h4.n === 0 && eq(h5.r, [false, false, false]) && eq(h5.hl, [bA]), [h2, h3, h4, h5]);
      const loopRes = await pg.evaluate((ids) => ids.map((id) => { pr.api.highlightBox(id); const l = hlList(model()); return l.length === 1 && l[0].box === id; }), s1b.slice(0, 6));
      const nAfter = await pg.evaluate(() => countHl(model()));
      t("K8 prejizdeni mysi po boxech (6x highlightBox za sebou) = vzdy 1 obrys prave daneho boxu, nic se nehromadi (3 objekty na konci)", loopRes.every(Boolean) && nAfter === 3, [loopRes, nAfter]);
      await pg.evaluate(([a]) => { pr.api.highlightBox(a); v.debug.renderNow(); }, [bA]);
      const hb0 = await pg.evaluate(() => hlList(model())[0]), pv0 = await pg.evaluate((p) => v.debug.pivot(p).world, mbA.p);
      await pg.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, motionIds);
      const hb1 = await pg.evaluate(() => hlList(model())[0]), pv1 = await pg.evaluate((p) => v.debug.pivot(p).world, mbA.p);
      const dv = pv1.map((x, k) => x - pv0[k]);
      await pg.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); pr.api.highlightBox(null); });
      t("K9 obrys jednoho boxu nasleduje pohyb svého boxu (posun o stejny vektor jako pivot)", Math.hypot(dv[0], dv[1], dv[2]) > 5 && nearV(hb1.min.map((x, k) => x - hb0.min[k]), dv, 0.05) && nearV(hb1.max.map((x, k) => x - hb0.max[k]), dv, 0.05), [dv, hb0, hb1]);
      // setModel: vyber po boxech i obrys boxu prezijou
      await pg.evaluate(([a, b]) => { pr.api.clear(); pr.api.setMany({ [a]: 5, [b]: 1 }); pr.api.highlightBox(b); v.debug.renderNow(); }, [bA, bB]);
      const selK10 = await pg.evaluate(() => pr.api.get());
      for (let i = 0; i < 2; i++) await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));
      await pg.waitForTimeout(300);
      const k10 = await pg.evaluate(([a, b]) => ({ get: pr.api.get(), pa: platesOf(model(), a).plates.length, pb: platesOf(model(), b).plates.length, hl: hlList(model()).map((x) => x.box), n: countGroups(model()) }), [bA, bB]);
      t("K10 po 2x setModel zustane vyber po boxech (5 a 1 pricka) i obrys boxu bB", eq(k10.get, selK10) && k10.pa === 5 && k10.pb === 1 && eq(k10.hl, [bB]) && k10.n === 2, [k10, selK10]);
      await pg.evaluate(() => pr.api.highlightBox(null));
      // cela sestava: ruzne pocty ve vsech 22 boxech najednou (setMany)
      const mix = {};
      P21.boxy.forEach((b, i) => { const n = (i * 5 + 3) % (P21.typy[b.k].max + 1); if (n) mix[b.id] = n; });
      const k11 = await pg.evaluate((m) => { const t0 = performance.now(); const n = pr.api.setMany(m); const t1 = performance.now(); v.debug.renderNow(); return { n, ms: t1 - t0, get: pr.api.get(), souhrn: pr.api.souhrn(), sk: pr.api.skupiny().map((g) => [g.id, g.set, g.priccek, g.cena, g.boxu_s_pricky]), bx: pr.api.boxes().map((b) => [b.id, b.n]) }; }, mix);
      const exK11 = expectSummary(P21, mix), cgK11 = await chk(mix);
      t("K11 ruzne pocty (0..6) v kazdem z 22 boxu najednou (setMany): trva pod 1 s, get() / souhrn / skupiny() / boxes() sedi s nezavislym vypoctem z payloadu, geometrie vsech boxu v poradku",
        k11.n === Object.keys(mix).length && k11.ms < 1000 && eq(k11.get, mix) && sumOk(k11.souhrn, exK11) && k11.bx.every((b) => b[1] === (mix[b[0]] || 0))
        && P21.skupiny.every((g, i) => { const e = exK11.skupiny.find((x) => x.id === g.id); return e ? (k11.sk[i][1] === e.set && k11.sk[i][2] === e.priccek && near(k11.sk[i][3], e.cena, 0.005) && k11.sk[i][4] === e.boxu_s_pricky) : (k11.sk[i][1] === "bez" && k11.sk[i][2] === 0); })
        && cgK11.errs.length === 0, [k11.n, k11.ms, cgK11.errs.slice(0, 3)]);
      t("K12 bez chyb v konzoli a ve strance (vyber po boxech)", (await errsOf(pg)).length === 0, await errsOf(pg));
    }
    gate();

    // ====================================================================== B) pohyb: pricky jedou s boxem
    if (run("B")) console.log("\n## B) pohyb vysuvu a boxu: pricky jedou s pivotem boxu");
    let before, after;
    if (run("B")) {
      await pg.evaluate(() => { pr.api.clear(); pr.api.setAll("mix4"); v.debug.renderNow(); });
      const eB = fromSets(P21, { s1: "mix4", s2: "mix4", s3: "mix4" });
      before = await pg.evaluate((mbx) => mbx.map((m) => ({ id: m.id, plates: platesOf(model(), m.id).plates.map((p) => p.min.concat(p.max)), pv: v.debug.pivot(m.p).world })), mbx21);
      await pg.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, motionIds);
      after = await pg.evaluate((mbx) => mbx.map((m) => ({ id: m.id, plates: platesOf(model(), m.id).plates.map((p) => p.min.concat(p.max)), pv: v.debug.pivot(m.p).world })), mbx21);
      let moved = 0, mism = [], nplates = 0;
      before.forEach((b, i) => {
        const a = after[i], d = a.pv.map((x, k) => x - b.pv[k]), len = Math.hypot(d[0], d[1], d[2]);
        if (len > 5) moved++;
        b.plates.forEach((pb, j) => { nplates++; const pa = a.plates[j], sh = pa.map((x, k) => x - pb[k]); for (let k = 0; k < 6; k++) if (!near(sh[k], d[k % 3], 0.05)) { mism.push(b.id + "#" + j + " plate " + sh.map((x) => x.toFixed(1)) + " pivot " + d.map((x) => x.toFixed(1))); break; } });
      });
      t("B1 po otevreni VSECH pohybu se pohnula vetsina boxu (pivoty boxu) - test ma smysl (Mix 4 ve vsech skupinach = " + Object.values(eB).reduce((a, x) => a + x, 0) + " pricek ve 22 boxech)", moved >= 10 && nplates === Object.values(eB).reduce((a, x) => a + x, 0), [moved, nplates]);
      t("B2 pricky se posunuly PRESNE o stejny vektor jako pivot boxu (vsechny pricky vsech boxu, vc. zvednutych boxu a boxu na vysuvu)", mism.length === 0, mism.slice(0, 4));
      if (SHOTS) {
        const idx = before.findIndex((b, i) => { const d = after[i].pv.map((x, k) => x - b.pv[k]); return Math.hypot(d[0], d[1], d[2]) > 100; }), mb = mbx21[idx];
        await pg.evaluate(([c, gid]) => { cam(c, 1100); pr.api.highlightGroup(gid); v.debug.renderNow(); }, [mb.min.map((x, i) => (x + mb.max[i]) / 2), "s2"]);
        await pg.waitForTimeout(400);
        await shot(pg, "otevreny_vysuv_mix4.png");
        await pg.evaluate(() => pr.api.highlightGroup(null));
      }
      await pg.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); });
      const back = await pg.evaluate((mbx) => mbx.map((m) => platesOf(model(), m.id).plates.map((p) => p.min.concat(p.max))), mbx21);
      t("B3 po zavreni vsech pohybu jsou pricky zpet na puvodnich mistech", back.every((pl, i) => pl.every((p, j) => nearV(p, before[i].plates[j], 0.05))));
    }
    gate();

    // ====================================================================== C) dratovy vzhled
    if (run("C")) console.log("\n## C) dratovy vzhled viewer");
    if (run("C")) {
      await pg.evaluate(() => { pr.api.clear(); pr.api.setAll("mix4"); });
      await pg.evaluate(() => { v.setMode("wire"); });
      await pg.waitForFunction(() => v.state().mode === "wire", null, { timeout: 60000 });
      await pg.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const nB3 = grp("s1").sety.mix4.po_boxech[2];
      const w1 = await pg.evaluate(() => { const r = platesOf(model(), "b03"); return { cw: r.colorWrite, lines: r.lineVerts }; });
      t("C1 v dratovem vzhledu se plocha pricek nekresli (colorWrite = false, jen zakryva), hrany zustaly (box b03 s " + nB3 + " pricky)", w1.cw === false && w1.lines === 24 * nB3, w1);
      await pg.evaluate(() => { v.setMode("real"); });
      await pg.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const w2 = await pg.evaluate(() => platesOf(model(), "b03").colorWrite);
      t("C2 po navratu do Skutecneho vzhledu se plocha kresli znovu (colorWrite = true)", w2 === true, w2);
    }
    gate();

    // ====================================================================== D) zvyrazneni skupiny
    if (run("D")) console.log("\n## D) oranzovy obrys VSECH boxu skupiny (highlightGroup)");
    if (run("D")) {
      const idsS2 = grp("s2").boxy;
      const h1 = await pg.evaluate(() => ({ r: pr.api.highlightGroup("s2"), hl: hlList(model()) }));
      t("D1 highlightGroup('s2') = true; vykresleno 7 obrysu, po jednom na box skupiny, kazdy obklopuje AABB boxu (o ~2 mm vetsi)",
        h1.r === true && h1.hl.length === idsS2.length && idsS2.every((id) => { const o = h1.hl.find((x) => x.box === id), m = mbx21.find((x) => x.id === id); return o && o.gid === "s2" && m.min.every((v, i) => near(o.min[i], v - 2, 0.05) && near(o.max[i], m.max[i] + 2, 0.05)); }), h1.hl.map((x) => x.box));
      const h2 = await pg.evaluate(() => ({ r: pr.api.highlightGroup("s3"), hl: hlList(model()), n: countHl(model()) }));
      t("D2 zvyrazneni jine skupiny stary obrys zrusi (jen obrysy s3, 7 boxu; 3 objekty na obrys: skupina, plocha, hrany)", h2.r === true && h2.hl.length === 7 && h2.hl.every((x) => x.gid === "s3") && h2.n === 7 * 3, h2);
      const hb = h2.hl, pv0 = await pg.evaluate((ps) => ps.map((p) => v.debug.pivot(p).world), hb.map((o) => mbx21.find((m) => m.id === o.box).p));
      await pg.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, motionIds);
      const hb2 = await pg.evaluate(() => hlList(model())), pv1 = await pg.evaluate((ps) => ps.map((p) => v.debug.pivot(p).world), hb.map((o) => mbx21.find((m) => m.id === o.box).p));
      let fol = 0, folBad = [];
      hb.forEach((o, i) => { const d = pv1[i].map((x, k) => x - pv0[i][k]), o2 = hb2.find((x) => x.box === o.box); if (Math.hypot(d[0], d[1], d[2]) > 5) fol++; if (!nearV(o2.min.map((x, k) => x - o.min[k]), d, 0.05) || !nearV(o2.max.map((x, k) => x - o.max[k]), d, 0.05)) folBad.push(o.box); });
      t("D3 obrysy nasleduji pohyb svych boxu (posun o stejny vektor jako pivot kazdeho boxu)", fol >= 3 && folBad.length === 0, [fol, folBad]);
      await pg.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); });
      const h3 = await pg.evaluate(() => ({ r: pr.api.highlightGroup(null), n: countHl(model()), l: hlList(model()).length }));
      t("D4 highlightGroup(null) vsechny obrysy uklidi (zadny objekt)", h3.r === true && h3.n === 0 && h3.l === 0, h3);
      const h4 = await pg.evaluate(() => { pr.api.highlightGroup("s1"); const r = pr.api.highlightGroup("s9"); return { r: r, hl: hlList(model()).map((x) => x.gid) }; });
      t("D5 highlightGroup neznamy skupiny = false a stavajici obrys (s1, 8 boxu) zustane", h4.r === false && h4.hl.length === 8 && h4.hl.every((g) => g === "s1"), h4);
      await pg.evaluate(() => pr.api.highlightGroup(null));
    }
    gate();

    // ====================================================================== E) vymena modelu (setModel), unik objektu
    if (run("E")) console.log("\n## E) setModel: vyber prezije, zadny unik objektu");
    if (run("E")) {
      await pg.evaluate(([x]) => { pr.api.clear(); pr.api.setGroup("s1", "mix2"); pr.api.setGroup("s3", "mix4"); pr.api.setBox(x, 2); pr.api.highlightGroup("s2"); v.debug.renderNow(); }, [s1b[1]]);
      const selBefore = await pg.evaluate(() => pr.api.get());
      await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));         // zahrivaci vymena: zahodi i veci, ktere vznikly drive (dratovy vzhled = hrany modelu)
      await pg.evaluate(() => { pr.api.highlightGroup("s2"); v.debug.renderNow(); });
      const res0 = await pg.evaluate(() => { const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()), hl: countHl(model()) }; });
      for (let i = 0; i < 3; i++) await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));
      await pg.waitForTimeout(300);
      const res1 = await pg.evaluate(() => { v.debug.renderNow(); const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()), hl: countHl(model()), get: pr.api.get(), p1: platesOf(model(), "b01").plates.length, hlN: hlList(model()).length, disposed: window.__disposed.size, sk: pr.api.skupiny().map((g) => g.set).join() }; });
      t("E1 po 3x setModel(stejny model): vyber po boxech se obnovil (get() stejne vc. vlastni upravy jednoho boxu), policni box b01 ma znovu 6 pricek (Mix 2), obrys skupiny s2 (7 boxu) je take zpet, rozpoznani setu zustalo (vlastni, ., mix4)",
        eq(res1.get, selBefore) && res1.p1 === 6 && res1.hlN === 7 && res1.sk === "vlastni,bez,mix4", [res1, selBefore]);
      t("E2 zadny unik: pocet skupin, obrysu, geometrii, materialu a deti sceny je po 3 vymenach stejny jako pred nimi", res1.groups === res0.groups && res1.hl === res0.hl && res1.geos === res0.geos && res1.mats === res0.mats && res1.ch === res0.ch, [res0, res1]);
      t("E3 stare geometrie/materialy pricek byly uvolnene (dispose zavolano)", res1.disposed > 0, res1.disposed);
      await pg.evaluate(() => v.setModel("/fx/nombx.glb"));
      await pg.waitForTimeout(300);
      const nb = await pg.evaluate(([a]) => ({ boxes: pr.api.boxes().filter((b) => b.ready).length, sk: pr.api.skupiny().filter((g) => g.ready).length, groups: countGroups(model()), hl: countHl(model()), get: pr.api.get(), s: pr.api.souhrn(), hr: pr.api.highlightGroup("s1"), hb: pr.api.highlightBox(a) }), [bA]);
      t("E4 model BEZ mbx: zadny box ani skupina neni ready, zadne pricky ani obrys, vyber a souhrn v API zustaly; highlightGroup i highlightBox = false", nb.boxes === 0 && nb.sk === 0 && nb.groups === 0 && nb.hl === 0 && eq(nb.get, selBefore) && nb.s.skupiny.length === 2 && nb.hr === false && nb.hb === false, nb);
      await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));
      await pg.waitForTimeout(300);
      const nb2 = await pg.evaluate(() => ({ boxes: pr.api.boxes().filter((b) => b.ready).length, groups: countGroups(model()), p1: platesOf(model(), "b01").plates.length, hl: hlList(model()).length }));
      t("E5 navrat na model s mbx: pricky se samy vrati podle zachovaneho vyberu (15 boxu, b01 = 6 pricek) a obrys s2", nb2.boxes === 22 && nb2.groups === 15 && nb2.p1 === 6 && nb2.hl === 7, nb2);
      const typeOk = (m, b) => { const lw = b.k.split("x").map(Number), dx = m.max[0] - m.min[0], dz = m.max[2] - m.min[2]; return Math.abs(Math.max(dx, dz) - lw[0]) <= 12 && Math.abs(Math.min(dx, dz) - lw[1]) <= 5 && Math.abs(m.max[1] - m.min[1] - 81) <= 3; };
      let other = null;
      for (const c of ["4918", "4917", "4453"].filter((c) => KARTY.payload.indexOf(c) >= 0)) {         // vhodna = u stejnych id boxu je aspon jedna shoda typu a aspon jedna neshoda
        const mb = readSpec(cardGlb(c)).mbx || [], common = mb.filter((m) => P21.boxy.some((x) => x.id === m.id));
        const exp = common.filter((m) => typeOk(m, P21.boxy.find((x) => x.id === m.id)));
        if (exp.length > 0 && exp.length < common.length) { other = { card: c, mbx: mb, exp: exp.map((m) => m.id).sort() }; break; }
      }
      if (!other) console.log("[PRESKOCENO] E8 (payload 4921 nad modelem jine karty): v " + FIX + " neni zadna z karet 4918 / 4917 / 4453 se shodnymi i neshodnymi typy boxu");
      else {
        await pg.evaluate((c) => v.setModel("/fx/" + c + ".offer.glb"), other.card);
        await pg.waitForTimeout(300);
        const rdy = (await pg.evaluate(() => pr.api.boxes().filter((b) => b.ready).map((b) => b.id))).sort();
        let badX = [];
        for (const id of rdy) { if (!(await pg.evaluate((id) => pr.api.get()[id], id))) continue; const r = await pg.evaluate((id) => platesOf(model(), id), id); r.plates.forEach((pl) => checkPlate(pl, other.mbx.find((m) => m.id === id), geom).forEach((e) => badX.push(id + ": " + e))); }
        t("E6 payload karty 4921 nad modelem karty " + other.card + " (stejna id boxu, jine polohy a typy): ready jen boxy, jejichz rozmer odpovida typu z payloadu; jejich pricky lezi uvnitr SVYCH boxu v novem modelu; nic nepadne",
          JSON.stringify(rdy) === JSON.stringify(other.exp) && rdy.length > 0 && badX.length === 0 && (await errsOf(pg)).length === 0, [rdy, other.exp, badX.slice(0, 3)]);
      }
      await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));
      await pg.waitForTimeout(300);
      const idleMs = await pg.evaluate(() => settle());
      t("E7 plugin nedrzi vykreslovaci smycku (viewer po akcich zase ustoji; limit 25 s kvuli zatizenemu stroji - smycka, ktera nikdy neustoji, narazi na 30 s)", idleMs < 25000 && await pg.evaluate(() => v.debug.idle()), idleMs);
      t("E8 bez chyb v konzoli a ve strance", (await errsOf(pg)).length === 0, await errsOf(pg));
    }
    gate();

    // ====================================================================== F) vizualni dukaz, ze se pricky kresli
    if (run("F")) console.log("\n## F) pricky jsou na platne videt");
    if (run("F")) {
      await pg.evaluate(() => { pr.api.clear(); pr.api.highlightGroup(null); v.debug.setAll({}); v.debug.renderNow(); });
      const mbF = mbx21[0];
      await pg.evaluate((c) => { cam(c, 800); }, mbF.min.map((x, i) => (x + mbF.max[i]) / 2));
      await pg.evaluate(() => { pix("bez"); pr.api.setGroup("s1", "pln"); pix("pln"); });
      const dF = await pg.evaluate(() => pixDiff("bez", "pln"));
      t("F1 po nastaveni Plneho setu na policii se obraz zmeni (zasahnuto aspon 300 pixelu)", dF >= 300, dF);
      if (SHOTS) { await pg.waitForTimeout(300); await shot(pg, "police_plny_set_zblizka.png"); }
      await pg.evaluate(() => { pr.api.clear(); pix("zpet"); });
      const dB = await pg.evaluate(() => pixDiff("bez", "zpet"));
      t("F2 po clear() je obraz zase stejny jako na zacatku (pricky opravdu zmizely z platna)", dB < 30, dB);
      await pg.evaluate(([a]) => { pr.api.setBox(a, 1); pix("n1"); pr.api.setBox(a, 6); pix("n6"); }, [s1b[0]]);
      const dN = await pg.evaluate(() => pixDiff("n1", "n6"));
      t("F3 jeden box: 1 pricka vs 6 pricek se na platne lisi (aspon 100 pixelu) - pocet v boxu je ve 3D videt", dN >= 100, dN);
    }
    gate();

    // ====================================================================== G) vykon: karta 4917 (2 police + 2 vysuvy, 28 boxu vc. e = -1)
    if (run("G")) console.log("\n## G) vykon a e = -1: karta 4917 (28 boxu)");
    if (run("G")) {
      const P17 = payloadOf("4917"), mbx17 = readSpec(cardGlb("4917")).mbx, ids17 = P17.boxy.map((b) => b.id);
      const pg17 = await viewerPage("/fx/4917.offer.glb", P17);
      const tm = await pg17.evaluate(() => { const t0 = performance.now(); const n = pr.api.setAll("pln"); const t1 = performance.now(); v.debug.renderNow(); return { n: n, set: t1 - t0, render: performance.now() - t1 }; });
      t("G1 setAll('pln') u vsech 4 skupin (28 boxu x 6 pricek) trva pod 1 s (vc. prvniho vykresleni pod 3 s)", tm.n === 4 && tm.set < 1000 && tm.render < 3000, tm);
      const neg = mbx17.filter((m) => m.e < 0).length, ePln = fromSets(P17, { s1: "pln", s2: "pln", s3: "pln", s4: "pln" });
      const cgP = await checkBoxes(pg17, P17, mbx17, ePln, ids17);
      t("G2 karta 4917, Plny set: boxy s e = -1 (" + neg + ") i e = +1 maji pricky ve slotech uvnitr studny, konec s vykrojem volny (" + cgP.counts.plates + " pricek celkem = 28 x 6)", neg > 0 && cgP.counts.plates === 28 * 6 && cgP.errs.length === 0, cgP.errs.slice(0, 5));
      const s17 = await pg17.evaluate(() => pr.api.souhrn());
      t("G3 souhrn karty 4917 (Plny set): 4 skupiny, 168 pricek, cena = soucet cen setu 'pln' ze skupin payloadu", s17.skupiny.length === 4 && s17.kusy === 168 && near(s17.cena_net, P17.skupiny.reduce((a, g) => a + g.sety.pln.cena, 0), 0.01) && sumOk(s17, expectSummary(P17, ePln)), s17);
      const tm2 = await pg17.evaluate(() => { const t0 = performance.now(); const n = pr.api.setAll("mix4"); const t1 = performance.now(); v.debug.renderNow(); return { n: n, set: t1 - t0, render: performance.now() - t1 }; });
      const eM4 = fromSets(P17, { s1: "mix4", s2: "mix4", s3: "mix4", s4: "mix4" }), cgM = await checkBoxes(pg17, P17, mbx17, eM4, ids17);
      const s17b = await pg17.evaluate(() => pr.api.souhrn());
      t("G4 prepnuti vsech 4 skupin na Mix 4 (ruzne pocty 1..6 v kazdem boxu, geometrie 28 boxu se prestavi) trva pod 1 s; geometrie vsech boxu a souhrn sedi", tm2.n === 4 && tm2.set < 1000 && cgM.errs.length === 0 && sumOk(s17b, expectSummary(P17, eM4)), [tm2, cgM.errs.slice(0, 3)]);
      if (SHOTS) {
        const m0 = mbx17.find((m) => m.e < 0), c0 = m0.min.map((x, i) => (x + m0.max[i]) / 2), gid0 = P17.boxy.find((b) => b.id === m0.id).s;
        await pg17.evaluate(([c, g]) => { cam(c, 1000); pr.api.highlightGroup(g); v.debug.renderNow(); }, [c0, gid0]);
        await pg17.waitForTimeout(400);
        await shot(pg17, "karta_4917_e_minus_mix4.png");
      }
      t("G5 bez chyb v konzoli a ve strance", (await errsOf(pg17)).length === 0, await errsOf(pg17));
      const dsp17 = await pg17.evaluate(() => { const before = pr.api.ready(), k0 = pr.api.souhrn().kusy; v.dispose(); return { before: before, k0: k0, ready: pr.api.ready(), kusy: pr.api.souhrn().kusy, set: pr.api.setGroup("s1", "pln"), hl: pr.api.highlightGroup("s1") }; });
      t("G6 dispose vieweru: plugin se uklidi (ready() = false), API dal nehazi a vybrany souhrn zustava; bez chyb v konzoli", dsp17.before === true && dsp17.ready === false && dsp17.k0 > 0 && dsp17.set === true && dsp17.hl === false && (await errsOf(pg17)).length === 0, [dsp17, await errsOf(pg17)]);
      const preset = { [s1b[0]]: 4, [s1b[1]]: 2, [s1b[4]]: 6 };
      const pg53 = await viewerPage("/fx/4921.offer.glb", P21, null, preset);
      const pre = await pg53.evaluate((ids) => ({ get: pr.api.get(), groups: countGroups(model()), ch: __changes.length, p: ids.map((id) => platesOf(model(), id).plates.length), sou: pr.api.souhrn().kusy, set: pr.api.groupInfo("s1").set }), [s1b[0], s1b[1], s1b[4]]);
      t("G7 vyber nastaveny PRED mountem (setMany, napr. obnova z localStorage) se po postaveni modelu hned zobrazi: 3 boxy s 4 / 2 / 6 pricky, onChange jen pri nastaveni, ne pri stavbe, skupina 'vlastni'",
        eq(pre.get, preset) && pre.groups === 3 && pre.p.join() === "4,2,6" && pre.ch === 1 && pre.sou === 12 && pre.set === "vlastni", pre);
      t("G8 bez chyb v konzoli a ve strance (predvolba)", (await errsOf(pg53)).length === 0, await errsOf(pg53));
    }
    gate();

    // ====================================================================== H) syntetika a robustnost (plugin nad holou scenou)
    if (run("H")) console.log("\n## H) syntetika (osa Z, e = +-1, delky 288 / 395 / 500, ruzne delky v jedne skupine), deduplikace setu, vadne vstupy, dispose");
    const SM = JSON.parse(fs.readFileSync(path.join(GEN, "synt.mbx.json"), "utf8")), SP = JSON.parse(fs.readFileSync(path.join(GEN, "synt.payload.json"), "utf8"));
    const sg = (id) => grpOf(SP, id);
    if (run("H")) {
      const { page: dp, r: dr } = await directPage("/fx/synt.glb", SP);
      t("H0 plugin nad holou scenou se spustil a vratil dispose funkci", dr === "function", dr);
      t("H1 payload syntetiky: skupiny s1 / s2 (2 boxy) nenabizeji Mix 3 (= Plny set), s3 / s5 / s6 (1 box) jen bez + pln, s4 (3 boxy ruznych delek 288 + 288 + 395) nabizi vsech 6 setu; po_boxech podle delky boxu (288 > 4, 395 > 6, 500 > 8)",
        keysOrdered(sg("s1").sety) === "bez,mix1,mix2,mix4,pln" && keysOrdered(sg("s2").sety) === "bez,mix1,mix2,mix4,pln" && ["s3", "s5", "s6"].every((g) => keysOrdered(sg(g).sety) === "bez,pln") && keysOrdered(sg("s4").sety) === SET_ORDER
        && JSON.stringify(sg("s1").sety.mix1.po_boxech) === "[6,1]" && JSON.stringify(sg("s1").sety.mix4.po_boxech) === "[1,6]" && JSON.stringify(sg("s4").sety.pln.po_boxech) === "[4,4,6]" && JSON.stringify(sg("s6").sety.pln.po_boxech) === "[8]" && JSON.stringify(sg("s3").sety.pln.po_boxech) === "[6]",
        SP.skupiny.map((g) => [g.id, keysOrdered(g.sety)]));
      const rd = await dp.evaluate(() => ({ sk: D.pr.api.skupiny().map((g) => [g.id, g.pocet_ready, g.boxu, g.ready, g.sety.join("/")]), bx: D.pr.api.boxes().filter((b) => !b.ready).map((b) => b.id) }));
      t("H2 skupiny(): s1 2/2, s2 2/2, s3 1/1, s4 3/3, s5 0/1 (pivot p99 v modelu neni = box se preskoci, skupina neni ready), s6 1/1, s nabizenymi sety z payloadu; boxes(): jen b08 neni ready",
        JSON.stringify(rd.sk.map((x) => x.slice(0, 4))) === JSON.stringify([["s1", 2, 2, true], ["s2", 2, 2, true], ["s3", 1, 1, true], ["s4", 3, 3, true], ["s5", 0, 1, false], ["s6", 1, 1, true]]) && rd.sk.every((x, i) => x[4] === keysOrdered(SP.skupiny[i].sety).replace(/,/g, "/")) && JSON.stringify(rd.bx) === '["b08"]', rd);
      // vsechny pocty 0..max v KAZDEM boxu: presne mapovani mistni -> svet (osa X i Z, e = +1 / -1, 288 / 395 / 500, siroke i uzke, staticke i v pivotu)
      let mapErr = [], combos = 0;
      const readyIds = SP.boxy.map((b) => b.id).filter((id) => SM.some((m) => m.id === id) && id !== "b08");
      for (const id of readyIds) {
        const mx = SP.typy[boxOf(SP, id).k].max;
        for (let n = 0; n <= mx; n++) {
          await dp.evaluate(([id, n]) => D.pr.api.setBox(id, n), [id, n]);
          const c = await checkBoxes(dp, SP, SM, { [id]: n }, [id], "D");
          combos++;
          c.errs.forEach((e) => mapErr.push(id + "/" + n + ": " + e));
        }
        await dp.evaluate((id) => D.pr.api.setBox(id, 0), id);
      }
      t("H3 PRESNE mapovani mistni -> svet (vzorec ze smlouvy) pro KAZDY pocet 0..max v kazdem z " + readyIds.length + " boxu (" + combos + " kombinaci; osa X i Z, e = +1 i -1, 288 / 395 / 500, siroke i uzke): ve slotech, uvnitr studny, konec s vykrojem volny, rozmery", readyIds.length === 9 && combos === readyIds.reduce((a, id) => a + SP.typy[boxOf(SP, id).k].max + 1, 0) && combos === 61 && mapErr.length === 0, mapErr.slice(0, 6));
      // sety v syntetice: pocty z po_boxech SVE skupiny (u skupiny s ruznymi delkami boxu ruzne), geometrie
      let setErr = [], setCombos = 0;
      for (const g of SP.skupiny) {
        if (g.id === "s5") continue;
        for (const sid of Object.keys(g.sety)) {
          const ok = await dp.evaluate(([gid, sid]) => D.pr.api.setGroup(gid, sid), [g.id, sid]);
          const e = fromSet(SP, g.id, sid);
          const got = await dp.evaluate(() => D.pr.api.get());
          const c = await checkBoxes(dp, SP, SM, e, g.boxy, "D");
          setCombos++;
          if (ok !== true || !eq(got, e) || c.errs.length) setErr.push(g.id + "/" + sid + " " + JSON.stringify([ok, got, e, c.errs.slice(0, 2)]));
        }
        await dp.evaluate((gid) => D.pr.api.setGroup(gid, "bez"), g.id);
      }
      t("H4 vsechny nabizene sety vsech skupin syntetiky (" + setCombos + " kombinaci): pocty z po_boxech skupiny, u skupiny s ruznymi delkami boxu ruzne (Plny set s4 = 4, 4, 6), geometrie ve 3D, get() presne", setErr.length === 0 && setCombos === 5 + 5 + 2 + 6 + 2, setErr.slice(0, 3));
      // deduplikace: set, ktery skupina nenabizi, nejde nastavit
      const dd = await dp.evaluate(() => {
        D.pr.api.clear();
        const c0 = D.changes.length, out = {};
        out.s1mix3 = D.pr.api.setGroup("s1", "mix3");           // 2 boxy: Mix 3 = Plny set -> nenabizi se
        out.s3mix1 = D.pr.api.setGroup("s3", "mix1");           // 1 box: jen bez + pln
        out.s3str = D.pr.api.setGroup("s3", "zak");
        out.nochange = D.changes.length === c0 && Object.keys(D.pr.api.get()).length === 0;
        out.s3pln = [D.pr.api.setGroup("s3", "pln"), D.pr.api.get()];
        out.all = [D.pr.api.setAll("mix3"), D.pr.api.skupiny().map((g) => g.set).join()];       // Mix 3 nabizi jen s4 (3 boxy)
        out.get = D.pr.api.get();
        return out;
      });
      const nMix3 = SP.skupiny.filter((g) => g.sety.mix3).length;
      t("H5 deduplikace setu: setGroup na nenabizeny set (s1 Mix 3, s3 Mix 1, zrusene 'zak') = false a beze zmeny; Plny set 1 boxu ok; setAll('mix3') pouzije set jen u skupin, ktere ho nabizeji (" + nMix3 + " = s4) a vrati jejich pocet",
        dd.s1mix3 === false && dd.s3mix1 === false && dd.s3str === false && dd.nochange === true && dd.s3pln[0] === true && eq(dd.s3pln[1], { b05: 6 }) && nMix3 === 1 && dd.all[0] === 1 && dd.all[1] === "bez,bez,pln,mix3,bez,bez" && eq(dd.get, Object.assign({ b05: 6 }, fromSet(SP, "s4", "mix3"))), dd);
      // rozpoznani pri deduplikaci: [6,6] u 2 boxu je Plny set (Mix 3 se nenabizi), [6,1] Mix 1, [1,6] Mix 4, [6,3] Mix 2, [2,2] vlastni
      const rc = await dp.evaluate(() => { const out = []; D.pr.api.clear(); [[6, 6], [6, 1], [1, 6], [6, 3], [2, 2], [0, 0]].forEach((p) => { D.pr.api.setBox("b01", p[0]); D.pr.api.setBox("b02", p[1]); out.push(D.pr.api.groupInfo("s1").set); }); return out; });
      t("H6 rozpoznani u 2-boxove skupiny: [6,6] = pln, [6,1] = mix1, [1,6] = mix4, [6,3] = mix2, [2,2] = vlastni, [0,0] = bez", eq(rc, ["pln", "mix1", "mix4", "mix2", "vlastni", "bez"]), rc);
      await dp.evaluate(() => D.pr.api.clear());
      const par = await dp.evaluate(() => { D.pr.api.setAll("pln"); const o = {}; D.scene.traverse((n) => { if (n.isGroup && n.userData && n.userData.__pricky) o[n.userData.__pricky] = (n.parent.userData && n.parent.userData.name) || (n.parent === D.ctx.model ? "model" : n.parent.name); }); return o; });
      t("H7 staticke boxy maji pricky pod modelem, box b05 (pivot p22) pod pivotem p22; box b08 (pivot p99 chybi) zadne", par.b01 === "model" && par.b02 === "model" && par.b03 === "model" && par.b04 === "model" && par.b05 === "p22" && par.b06 === "model" && par.b09 === "model" && par.b10 === "model" && !("b08" in par), par);
      const nr = await dp.evaluate(() => ({ s: D.pr.api.setGroup("s5", "pln"), p: platesOf(D.scene, "b08").plates.length, sou: D.pr.api.souhrn(), h: D.pr.api.highlightGroup("s5"), hb: D.pr.api.highlightBox("b08"), ready: D.pr.api.skupiny().find((g) => g.id === "s5").ready, bx: D.pr.api.setBox("b08", 3), gi: D.pr.api.groupInfo("s5") }));
      t("H8 skupina bez boxu v modelu (s5): jde vybrat (cena je v souhrnu), ale nema pricky ve scene, neni ready; highlightGroup i highlightBox = false; setBox na box mimo model je platny", nr.s === true && nr.p === 0 && nr.sou.skupiny.some((x) => x.id === "s5") && nr.h === false && nr.hb === false && nr.ready === false && nr.bx === true && nr.gi.priccek === 3 && nr.gi.set === "vlastni", nr);
      await dp.evaluate(() => D.pr.api.clear());
      const wm = await dp.evaluate(() => { D.pr.api.setGroup("s1", "mix1"); const a0 = platesOf(D.scene, "b01").colorWrite; D.ctx.root.classList.add("v3d-mode-wire"); D.tick(); const a1 = platesOf(D.scene, "b01").colorWrite; D.ctx.root.classList.remove("v3d-mode-wire"); D.tick(); return [a0, a1, platesOf(D.scene, "b01").colorWrite]; });
      t("H9 frame hook prepina plochu podle tridy v3d-mode-wire na koreni viewer (real true -> wire false -> real true)", JSON.stringify(wm) === "[true,false,true]", wm);
      const rr = await dp.evaluate(() => { const n0 = D.renders(); D.pr.api.setGroup("s2", "pln"); D.pr.api.highlightGroup("s2"); D.pr.api.setBox("b06", 2); D.pr.api.highlightBox("b06"); return D.renders() - n0; });
      t("H10 zmena vyberu (set i box) i obrysu (skupina i box) vola requestRender() (viewer prekresli)", rr >= 4, rr);
      const dup = await dp.evaluate(() => { D.pr.api.setAll("pln"); const n0 = countGroups(D.scene), h0 = countHl(D.scene); D.off = D.pr.plugin(D.ctx); return [n0, countGroups(D.scene), h0, countHl(D.scene), D.frames.length]; });
      t("H11 druhe volani plugin(ctx) bez dispose (pojistka) stary beh uklidi: zadne zdvojene skupiny, obrysy ani frame hooky", dup[0] === dup[1] && dup[0] > 0 && dup[2] === dup[3] && dup[4] === 1, dup);
      await dp.evaluate(() => D.pr.api.setAll("pln"));
      const dsp = await dp.evaluate(() => {
        D.pr.api.highlightGroup("s1");
        const geos = [], mats = [];
        D.scene.traverse((o) => { if (o.userData && (o.userData.__pricky !== undefined || o.userData.__prickyHl !== undefined)) { if (o.geometry) geos.push(o.geometry); if (o.material) mats.push(o.material); } });
        const nf = D.frames.length, g0 = countGroups(D.scene), h0 = countHl(D.scene);
        window.__disposed.clear();
        D.off();
        const gone = geos.every((g) => __disposed.has(g)), mgone = mats.every((m) => __disposed.has(m));
        return { geos: geos.length, mats: mats.length, gone: gone, mgone: mgone, groups: countGroups(D.scene), hl: countHl(D.scene), nf0: nf, nf1: D.frames.length, g0: g0, h0: h0, ready: D.pr.api.ready(), matsDisposed: [...__disposed].filter((o) => o.isMaterial).length, set: D.pr.api.setGroup("s1", "pln"), groups2: countGroups(D.scene), hr: D.pr.api.highlightGroup("s1"), hbx: D.pr.api.highlightBox("b01") };
      });
      t("H12 dispose: z sceny zmizely vsechny skupiny i obrysy, vsechny geometrie a materialy pricek jsou uvolnene, frame hook odhlasen, ready() = false", dsp.g0 > 0 && dsp.h0 > 0 && dsp.groups === 0 && dsp.hl === 0 && dsp.gone && dsp.mgone && dsp.geos > 0 && dsp.matsDisposed >= 4 && dsp.nf0 === 1 && dsp.nf1 === 0 && dsp.ready === false, dsp);
      t("H13 po dispose API dal nehazi (setGroup vrati true, highlightGroup i highlightBox false) a do sceny uz nic nekresli", dsp.set === true && dsp.groups2 === 0 && dsp.hr === false && dsp.hbx === false, dsp);

      // --- vadne vstupy (bez GLB, falesny ctx s vlastnim mbx)
      const N = 13, ids13 = Array.from({ length: N }, (_, i) => "b" + String(i + 1).padStart(2, "0"));
      const desk = (n) => Array.from({ length: n }, (_, i) => ({ s: [60 + 40 * i, 39.5, 93], r: [2, 75, 181], d: "p186" }));
      const GOOD = { enabled: true, sety: [{ id: "bez", popis: "Bez", pozn: "" }, { id: "mix1", popis: "Mix 1", pozn: "" }, { id: "pln", popis: "Plny", pozn: "" }],
        skupiny: [{ id: "s1", k: "police", n: 1, g: null, popis: "Police 1", boxu: N, boxy: ids13, sety: { bez: { priccek: 0, cena: 0, dily: {}, po_boxech: ids13.map(() => 0) }, mix1: { priccek: 19, cena: 741, dily: { p186: 19 }, po_boxech: ids13.map((x, i) => (i % 2 ? 1 : 2)) }, pln: { priccek: 26, cena: 1014, dily: { p186: 26 }, po_boxech: ids13.map(() => 2) },
          vadny: { po_boxech: [1, 1] }, mix9: { po_boxech: ids13.map((x, i) => (i === 2 ? 9 : 1)) }, mix8: { po_boxech: "x" }, mix7: null } }],
        boxy: ids13.map((id, i) => ({ id: id, k: "395x186", n: i + 1, g: null, s: "s1", sk: "police" })),
        typy: { "395x186": { popis: "x", max: 2, dil: "p186", sety: { zak: { n: 1, desky: [] } }, pocty: [{ n: 0, desky: [] }, { n: 1, desky: desk(1) }, { n: 2, desky: desk(2) }] } },
        dily: [{ klic: "p186", nazev: "P", cena: 39, product_id: 1 }], geom: { vyska_boxu: 81, studna_od: 28.4 } };
      const bp = await dp.evaluate((GOOD) => {
        const out = {};
        const variants = { "bez argumentu": undefined, "null": { payload: null }, "cislo": { payload: 5 }, "retezec": { payload: "x" }, "skupiny neni pole": { payload: { skupiny: "x", boxy: [], typy: {} } }, "prazdne": { payload: { skupiny: [], boxy: [], typy: {} } },
          "typ bez pocty": { payload: Object.assign({}, GOOD, { typy: { "395x186": { popis: "x", max: 2, dil: "p186" } } }) }, "typ bez dil": { payload: Object.assign({}, GOOD, { typy: { "395x186": { max: 2, pocty: [{ n: 0, desky: [] }, { n: 1, desky: [] }] } } }) },
          "dily chybi": { payload: Object.assign({}, GOOD, { dily: [] }) }, "pocty posunute": { payload: Object.assign({}, GOOD, { typy: { "395x186": { max: 2, dil: "p186", pocty: [{ n: 1, desky: [] }, { n: 2, desky: [] }] } } }) },
          "vadne desky": { payload: Object.assign({}, GOOD, { typy: { "395x186": { max: 2, dil: "p186", pocty: [{ n: 0, desky: [null, { s: [1, 2], r: [1, 1, 1] }, "x"] }, { n: 1, desky: [{ s: [1, 2, 3], r: [0, 1, 1] }] }, { n: 2, desky: [] }] } } }) },
          "vadna id skupin": { payload: Object.assign({}, GOOD, { skupiny: [{ id: "__proto__", sety: {} }, { id: "S1", sety: {} }, { id: "s1" }, null, 5] }) },
          "vadne boxy": { payload: Object.assign({}, GOOD, { boxy: [{ id: "__proto__", k: "395x186", s: "s1" }, { id: "B01", k: "395x186", s: "s1" }, { id: "b01", k: "neznamy", s: "s1" }, { id: "b02", k: "395x186" }, { id: "b03", k: "395x186", s: "x" }] }) } };
        Object.keys(variants).forEach((k) => {
          try {
            const o = variants[k] === undefined ? V3DPricky.create() : V3DPricky.create(variants[k]), a = o.api;
            const off = o.plugin({ THREE: THREE, model: new THREE.Group(), gltf: { scenes: [{ userData: {} }] }, scene: new THREE.Scene(), requestRender: function () {} });
            out[k] = [a.skupiny().length, a.boxes().length, JSON.stringify(a.get()), a.souhrn().kusy, a.setAll("mix1"), a.setGroup("s1", "mix1"), a.setBox("b01", 1), a.highlightGroup("s1"), a.highlightBox("b01"), typeof off, a.clear() >= 0, a.setMany({ b01: 1 }) >= 0, a.groupInfo("s1") === null || typeof a.groupInfo("s1") === "object"].join("|");
            off();
          } catch (e) { out[k] = "VYJIMKA " + e.message; }
        });
        let thrown = 0;
        const o2 = V3DPricky.create({ payload: GOOD, onChange: function () { throw new Error("stranka"); } }); thrown = (o2.api.setGroup("s1", "mix1") === true && o2.api.setBox("b01", 2) === true && o2.api.setAll("bez") === 1) ? 0 : 1;
        out.onChangeThrows = thrown;
        return out;
      }, GOOD);
      const exc = Object.keys(bp).filter((k) => /VYJIMKA/.test(String(bp[k])));
      t("H14 vadne payloady (undefined, null, cislo, retezec, skupiny/typy/dily chybi, posunute nebo vadne pocty a desky, vadna id skupin a boxu, __proto__) nic nevyhodi, API vraci neutralni hodnoty", exc.length === 0 && bp["bez argumentu"] === "0|0|{}|0|0|false|false|false|false|function|true|true|true", bp);
      t("H15 vyjimka v onChange stranky se nepropaguje do pluginu", bp.onChangeThrows === 0, bp.onChangeThrows);
      const nz = await dp.evaluate((GOOD) => {
        const a = V3DPricky.create({ payload: GOOD }).api, out = {};
        out.sety = a.skupiny()[0].sety;                                    // vadne sety (jina delka po_boxech, pocet nad max, ne pole, null) se nenabizeji; 'bez' je vzdy dostupny
        out.bad = [a.setGroup("s1", "vadny"), a.setGroup("s1", "mix9"), a.setGroup("s1", "mix8"), a.setGroup("s1", "mix7"), a.setGroup("s1", "zak")];
        out.mix1 = [a.setGroup("s1", "mix1"), a.get(), a.groupInfo("s1").set];
        out.max = a.boxes()[0].max;
        return out;
      }, GOOD);
      t("H16 normalizace payloadu: vadne sety skupiny (spatna delka po_boxech, pocet nad max typu, neni pole, null) se nenabizeji a setGroup na ne = false; typy[k].sety z drivejsiho payloadu se ignoruje; platny Mix 1 [2,1,2,...] funguje",
        eq(nz.sety, ["bez", "mix1", "pln"]) && eq(nz.bad, [false, false, false, false, false]) && nz.mix1[0] === true && nz.mix1[1].b01 === 2 && nz.mix1[1].b02 === 1 && nz.mix1[2] === "mix1" && nz.max === 2, nz);
      const gap = await dp.evaluate((GOOD) => {
        const P2 = JSON.parse(JSON.stringify(GOOD));
        P2.typy["395x186"].max = 6;                                          // pocty jen 0..2 -> skutecny strop je 2
        const a = V3DPricky.create({ payload: P2 }).api;
        return { max: a.boxes()[0].max, r: [a.setBox("b01", 3), a.setBox("b01", 2)], get: a.get() };
      }, GOOD);
      t("H17 typ s deklarovanym max 6, ale podklady geometrie (pocty) jen pro 0..2: skutecny strop je 2 (setBox(.., 3) = false)", gap.max === 2 && eq(gap.r, [false, true]) && eq(gap.get, { b01: 2 }), gap);
      const fm = await dp.evaluate((GOOD) => {
        const ok = { id: "b01", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: "p01" };
        const mbx = [null, 5, {}, { id: "b02" }, { id: "b03", min: [0, 0, 0], max: [1, 2] }, { id: "b04", min: [0, 0, 0], max: [NaN, 81, 186], e: 1, p: null }, { id: "b05", min: [0, 0, 0], max: [395.5, 81, 186], e: 0, p: null },
          { id: "b06", min: [0, 0, 0], max: [395.5, 81, 186], e: "1", p: null }, { id: "b07", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: 5 }, { id: "b08", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: "p77" },
          { id: "b09", min: [400, 0, 0], max: [0, 81, 186], e: 1, p: null }, { id: "b10", min: [0, 0, 0], max: [300, 81, 120], e: 1, p: null }, { id: "b11", min: [0, 0, 0], max: [395.5, 40, 186], e: 1, p: null },
          { id: "b12", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: null }, { id: "b12", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: null }, { id: "b13", min: [0, 0, 0], max: [395.5, 81, 186], e: 1, p: null, g: 5, n: "x", s: "x" }, ok];
        const model = new THREE.Group(); const piv = new THREE.Object3D(); piv.name = "p01"; model.add(piv);
        const o = V3DPricky.create({ payload: GOOD });
        o.plugin({ THREE: THREE, model: model, gltf: { scenes: [{ userData: { v3d: { mbx: mbx } } }] }, scene: new THREE.Scene(), requestRender: function () {} });
        o.api.setGroup("s1", "pln");
        let n = 0; model.traverse((x) => { if (x.isGroup && x.userData && x.userData.__pricky) n++; });
        return { ready: o.api.boxes().filter((b) => b.ready).map((b) => b.id).join(","), sk: o.api.skupiny()[0].pocet_ready, plates: n };
      }, GOOD);
      t("H18 vadne mbx (null, cislo, chybejici pole, NaN, e = 0 / '1', p cislo / neexistujici, min > max, spatny rozmer / vyska, duplicita): preskoceno; jen platne (b01 s pivotem p01, b12, b13) jsou ready a maji pricky", fm.ready === "b01,b12,b13" && fm.sk === 3 && fm.plates === 3, fm);
      const cm = await dp.evaluate(() => { const o = V3DPricky.create({ payload: { skupiny: [], boxy: [], typy: {} } }); const r = []; [null, undefined, {}, { THREE: THREE }, { THREE: THREE, model: null }, { THREE: THREE, model: new THREE.Group(), gltf: null }].forEach((c) => { try { r.push(typeof o.plugin(c)); } catch (e) { r.push("VYJIMKA"); } }); return r.join(","); });
      t("H19 plugin(ctx) s chybejicim / neuplnym ctx (null, {}, bez modelu, bez gltf) nikdy nevyhodi a vrati funkci", cm === "function,function,function,function,function,function", cm);
      const nof = await directPage("/fx/synt.glb", SP, { bezOnFrame: true });
      const nf = await nof.page.evaluate(() => { D.pr.api.setGroup("s1", "pln"); return [platesOf(D.scene, "b01").plates.length, typeof D.off]; });
      t("H20 ctx bez onFrame (starsi viewer) plugin funguje (pricky se kresli, jen se neprepina dratovy vzhled)", nf[0] === 6 && nf[1] === "function", nf);
      t("H21 bez chyb v konzoli a ve strance (syntetika, vadne vstupy, dispose)", (await errsOf(dp)).length === 0 && (await errsOf(nof.page)).length === 0, [await errsOf(dp), await errsOf(nof.page)]);
    }
    gate();

    // ====================================================================== S) ocelove supliky (v5): podnosy jako boxy
    if (run("S")) console.log("\n## S) ocelove supliky: podnos = box typu S<sirka>x<hloubka>x<vyska>, os 'b' (z od cela, e = strana cela), sloty po 100 mm zepredu dozadu");
    if (run("S")) {
      const SPL = JSON.parse(fs.readFileSync(path.join(GEN, "suplik.payload.json"), "utf8")), SMBX = JSON.parse(fs.readFileSync(path.join(GEN, "suplik.mbx.json"), "utf8"));
      const typesSup = Object.keys(SPL.typy).filter((k) => SPL.typy[k].druh === "suplik"), idsSup = SPL.boxy.map((b) => b.id);
      // S1: payload typu podle kontraktu (platí pro rucni i skutecny payload)
      const pErr = [];
      typesSup.forEach((k) => {
        const ty = SPL.typy[k];
        if (SUP_TYPY.indexOf(k) < 0) { pErr.push(k + " neni v tabulce kontraktu"); return; }
        const o = supOracle(k);
        if (ty.druh !== "suplik" || ty.os !== "b") pErr.push(k + " druh/os " + ty.druh + "/" + ty.os);
        if (ty.L !== o.L || ty.W !== o.W || ty.H !== o.H || ty.lem !== 0) pErr.push(k + " L/W/H/lem " + [ty.L, ty.W, ty.H, ty.lem]);
        if (ty.max !== o.max || ty.dil !== o.dil) pErr.push(k + " max/dil " + [ty.max, ty.dil] + " vs " + [o.max, o.dil]);
        if (!Array.isArray(ty.pocty) || ty.pocty.length !== o.max + 1 || !ty.pocty.every((x, n) => x.n === n && x.desky.length === n && x.desky.every((d) => d.d === o.dil && near(d.r[0], 2, 0.01) && near(d.r[1], o.v, 0.01) && near(d.r[2], o.delka, 0.01)))) pErr.push(k + " pocty / desky");
      });
      t("S1 payload typu supliku podle kontraktu (druh 'suplik', os 'b', L/W/H z klice, lem 0, max = floor((sirka - 2 x bok) / 100) = 4 / 6 / 9, dil ps<hloubka>v<vyska>, pocty 0..max s deskami 2 x (vyska - 8) x vnitrni hloubka): "
        + typesSup.length + " typu z tabulky kontraktu (12)", typesSup.length >= 10 && pErr.length === 0, pErr.slice(0, 5));
      const { page: sp, r: sr } = await directPage("/fx/suplik.glb", SPL);
      const rdy = await sp.evaluate(() => ({ sk: D.pr.api.skupiny().map((g) => [g.id, g.pocet_ready, g.boxu, g.ready, g.k, g.sety.indexOf("pln") >= 0]), bx: D.pr.api.boxes().filter((b) => !b.ready).map((b) => b.id), n: D.pr.api.boxes().length }));
      t("S2 plugin nad holou scenou: " + idsSup.length + " podnosu ve " + SPL.skupiny.length + " skupinach (po jednom typu, 4 orientace), vsechny jsou v modelu (rozmer AABB odpovida typu vcetne vysky), skupiny nabizeji Plny set",
        sr === "function" && rdy.n === idsSup.length && rdy.bx.length === 0 && rdy.sk.every((x) => x[3] && x[1] === x[2] && x[4] === "suplik" && x[5]) && SPL.skupiny.every((g) => g.k === "suplik" && g.boxu === 4), rdy);
      const combos = new Set(SMBX.map((m) => (longAxis(m) === 0 ? "X" : "Z") + m.e));
      // S3: vsechny typy x vsechny pocty 0..max x 4 orientace (osa delky X / Z, e = +1 / -1): poloha, rozmery, sloty, mapovani - vsude najednou
      let geoErr = [], states = 0, plates = 0;
      const maxN = Math.max.apply(null, typesSup.map((k) => SPL.typy[k].max));
      for (let n = 0; n <= maxN; n++) {
        const sel = {};
        SPL.boxy.forEach((b) => { const m = Math.min(n, SPL.typy[b.k].max); if (m) sel[b.id] = m; });
        await sp.evaluate((sel) => { D.pr.api.setMany(sel); }, sel);
        const c = await checkAny(sp, SPL, SMBX, sel, idsSup, "D");
        states += c.counts.boxes;
        plates += c.counts.plates;
        c.errs.forEach((e) => geoErr.push("n=" + n + " " + e));
      }
      t("S3 PRESNA geometrie pricek ve SVETE (kontrakt v5: dutina podnosu od cela / zadniho lemu / boku / podlahy, tloustka 2, vyska = vyska podnosu - 8, delka = celá vnitrni hloubka, stred dutiny, sloty po 100 mm soumerne a rovnomerne) pro vsechny typy x pocty 0..max x 4 orientace ("
        + [...combos].sort().join(" ") + "): " + states + " stavu boxu, " + plates + " pricek; plny pocet obsazuje vsechny sloty", combos.size === 4 && geoErr.length === 0 && plates > 1000, geoErr.slice(0, 6));
      // S4: sety na skupinach supliku (po_boxech z payloadu): pocty, geometrie, Plny set = max v kazdem podnosu
      await sp.evaluate(() => { D.pr.api.clear(); });                    // S3 nechal vyber na plnych poctech
      let setErr = [], setCombos = 0;
      for (const g of SPL.skupiny) {
        for (const sid of Object.keys(g.sety)) {
          const ok = await sp.evaluate(([gid, sid]) => D.pr.api.setGroup(gid, sid), [g.id, sid]);
          const e = fromSet(SPL, g.id, sid), got = await sp.evaluate(() => D.pr.api.get());
          const c = await checkAny(sp, SPL, SMBX, e, g.boxy, "D");
          setCombos++;
          if (ok !== true || !eq(got, e) || c.errs.length) setErr.push(g.id + "/" + sid + " " + JSON.stringify([ok, got, e, c.errs.slice(0, 2)]));
          if (sid === "pln" && !g.boxy.every((id, i) => g.sety.pln.po_boxech[i] === SPL.typy[boxOf(SPL, id).k].max)) setErr.push(g.id + " Plny set neni max v kazdem podnosu");
        }
        await sp.evaluate((gid) => D.pr.api.setGroup(gid, "bez"), g.id);
      }
      t("S4 sety (bez / mixy / plny) na VSECH skupinach supliku (" + setCombos + " kombinaci): pocty z po_boxech v kazdem podnosu, geometrie, get() presne; Plny set = max slotu v kazdem podnosu", setErr.length === 0 && setCombos >= SPL.skupiny.length * 2, setErr.slice(0, 3));
      const mezi = await sp.evaluate((ids) => { D.pr.api.clear(); return ids.map((id) => { const mx = D.pr.api.boxes().find((b) => b.id === id).max; return [D.pr.api.setBox(id, mx + 1), D.pr.api.setBox(id, -1), D.pr.api.setBox(id, mx), D.pr.api.get()[id] === mx]; }); }, idsSup);
      t("S5 mez poctu pricek je max typu podnosu (4 / 6 / 9): setBox(max + 1) a setBox(-1) = false, setBox(max) = true (u vsech podnosu)", mezi.every((x) => x[0] === false && x[1] === false && x[2] === true && x[3] === true), mezi.filter((x) => !x.every((y, i) => y === [false, false, true, true][i])).length);
      await sp.evaluate(() => { D.pr.api.clear(); D.pr.api.setAll("mix4"); });
      const selM4 = {};
      SPL.skupiny.forEach((g) => Object.assign(selM4, fromSet(SPL, g.id, g.sety.mix4 ? "mix4" : "pln")));
      const sumS = await sp.evaluate(() => D.pr.api.souhrn());
      const expS = expectSummary(SPL, selM4);
      t("S6 souhrn pres vsechny skupiny supliku (Mix 4 / Plny set): dily ps<hloubka>v<vyska> v poradi payload.dily, kusy a cena podle jednotkovych cen karet = nezavisly vypocet; cena skupiny = soucet po boxech",
        sumOk(sumS, expS) && sumS.radky.length >= 2 && sumS.radky.every((x) => /^ps\d+v\d+$/.test(x.klic)), [sumS.kusy, expS.kusy, sumS.cena_net, expS.cena_net]);

      // ---- smisena scena (multibox + suplik, staticke i pod pivotem vysuvu) ve viewer: pohyb s pivotem, obrys, drat, setModel
      const PS = JSON.parse(fs.readFileSync(path.join(GEN, "smisena.payload.json"), "utf8")), SMB = JSON.parse(fs.readFileSync(path.join(GEN, "smisena.mbx.json"), "utf8")), PIV = JSON.parse(fs.readFileSync(path.join(GEN, "smisena.piv.json"), "utf8"));
      const mp = await viewerPage("/fx/smisena.glb", PS), idsPS = PS.boxy.map((b) => b.id);
      const sk0 = await mp.evaluate(() => ({ s: pr.api.skupiny().map((g) => [g.id, g.k, g.pocet_ready, g.boxu, g.ready]), b: pr.api.boxes().filter((b) => b.ready).length }));
      t("S7 smisena scena: skupiny police / vysuv / 2 x suplik (3 + 2 podnosy ruznych typu v jedne skupine), vsech 9 boxu (multiboxy i podnosy, staticke i pod pivotem vysuvu) je v modelu",
        eq(sk0.s.map((x) => x.slice(0, 2)), [["s1", "police"], ["s2", "vysuv"], ["s3", "suplik"], ["s4", "suplik"]]) && sk0.s.every((x) => x[4] && x[2] === x[3]) && sk0.b === 9 && eq(PS.skupiny.map((g) => g.boxy.length), [2, 2, 3, 2]), sk0);
      let cur = {}, mixErr = [];
      for (const sid of ["pln", "mix4", "mix1", "bez"]) {
        await mp.evaluate((sid) => pr.api.setAll(sid), sid);
        PS.skupiny.forEach((g) => { if (g.sety[sid]) { g.boxy.forEach((id, i) => { const n = sid === "bez" ? 0 : g.sety[sid].po_boxech[i]; if (n) cur[id] = n; else delete cur[id]; }); } });
        const c = await checkAny(mp, PS, SMB, cur, idsPS, "V");
        const sou = await mp.evaluate(() => pr.api.souhrn());
        if (c.errs.length || !sumOk(sou, expectSummary(PS, cur))) mixErr.push(sid + " " + JSON.stringify([c.errs.slice(0, 2), sou.kusy]));
      }
      t("S8 sety pres vsechny druhy najednou (setAll Plny / Mix 4 / Mix 1 / bez; skupiny, ktere set nenabizeji, zustanou): geometrie multiboxu i podnosu ve 3D a souhrn (dily p186 / p91 / ps...) = nezavisly vypocet", mixErr.length === 0, mixErr.slice(0, 3));
      // pohyb s pivotem
      await mp.evaluate(() => pr.api.setAll("pln"));
      const mids = await mp.evaluate(() => ({ s2: pr.api.motionIds("s2"), s3: pr.api.motionIds("s3"), s4: pr.api.motionIds("s4"), all: pr.api.motionIds() }));
      const specSM = readSpec(path.join(GEN, "smisena.glb"));
      t("S9 motionIds pro podnosy a boxy pod pivotem vysuvu: s2 (multiboxy pod pivotem " + PIV[0] + ") a s3 (3 podnosy pod pivotem " + PIV[1] + ") = pohyb vysuvu s timto pivotem ve steps; staticke podnosy (s4) nemaji pohyb = []; shodne s nezavislym vypoctem",
        eq(mids.s2, expectIds(specSM, PS, ["s2"])) && eq(mids.s3, expectIds(specSM, PS, ["s3"])) && mids.s2.length === 1 && mids.s3.length === 1 && eq(mids.s4, []) && eq(mids.all, expectIds(specSM, PS, ["s1", "s2", "s3", "s4"])), mids);
      const snap = () => mp.evaluate(([ids, pivs]) => ({ pl: ids.map((id) => platesOf(model(), id).plates.map((p) => p.min.concat(p.max))), pv: pivs.map((p) => v.debug.pivot(p).world) }), [idsPS, PIV]);
      const b0 = await snap();
      await mp.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, mids.all);
      const b1 = await snap();
      const dPiv = PIV.map((p, i) => b1.pv[i].map((x, k) => x - b0.pv[i][k])), mvErr = [];
      let movedBoxes = 0;
      SMB.forEach((m, i) => {
        const d = m.p ? dPiv[PIV.indexOf(m.p)] : [0, 0, 0];
        if (Math.hypot(d[0], d[1], d[2]) > 5) movedBoxes++;
        b0.pl[i].forEach((pa, j) => { const pb = b1.pl[i][j]; for (let k = 0; k < 6; k++) if (!near(pb[k] - pa[k], d[k % 3], 0.05)) { mvErr.push(m.id + "#" + j + " posun " + (pb[k] - pa[k]).toFixed(2) + " != " + d[k % 3].toFixed(2)); break; } });
      });
      t("S10 pohyb s pivotem: po otevreni vysuvu z motionIds() se pricky multiboxu pod p" + PIV[0].slice(1) + " i vsech podnosu pod " + PIV[1] + " posunuly PRESNE o stejny vektor jako pivot, pricky statickych boxu a podnosu zustaly (" + movedBoxes + " boxu se pohnulo)",
        movedBoxes === 5 && mvErr.length === 0 && b0.pl.every((p) => p.length > 0), [movedBoxes, mvErr.slice(0, 3)]);
      await mp.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); });
      // obrys podnosu a skupiny supliku + nasledovani pohybu
      const hl = await mp.evaluate(() => ({ b: pr.api.highlightBox("b05"), l1: hlList(model()), g: pr.api.highlightGroup("s3"), l2: hlList(model()), g4: pr.api.highlightGroup("s4"), l3: hlList(model()) }));
      const mbOf = (id) => SMB.find((m) => m.id === id);
      const aabbOk = (o, m) => m.min.every((v, i) => near(o.min[i], v - 2, 0.05) && near(o.max[i], m.max[i] + 2, 0.05));
      t("S11 obrys supliku: highlightBox(podnos) = 1 obrys kolem AABB podnosu (+2 mm), highlightGroup('s3') = 3 obrysy (podnosy pod pivotem), highlightGroup('s4') = 2 obrysy a predchozi se vzdy nahradi",
        hl.b === true && hl.l1.length === 1 && aabbOk(hl.l1[0], mbOf("b05")) && hl.g === true && hl.l2.length === 3 && ["b05", "b06", "b07"].every((id) => { const o = hl.l2.find((x) => x.box === id); return o && aabbOk(o, mbOf(id)); })
        && hl.g4 === true && hl.l3.length === 2 && hl.l3.every((x) => x.gid === "s4"), hl);
      await mp.evaluate(() => { pr.api.highlightGroup("s3"); v.debug.renderNow(); });
      const h0 = await mp.evaluate(() => hlList(model()));
      await mp.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, mids.all);
      const h1 = await mp.evaluate(() => hlList(model())), d2 = dPiv[PIV.indexOf(mbOf("b05").p)];
      t("S12 obrys skupiny podnosu nasleduje pohyb vysuvu (posun o vektor pivotu), obrys statickych podnosu stoji",
        Math.hypot(d2[0], d2[1], d2[2]) > 5 && h0.every((o) => { const o1 = h1.find((x) => x.box === o.box); return o1 && nearV(o1.min.map((x, k) => x - o.min[k]), d2, 0.05) && nearV(o1.max.map((x, k) => x - o.max[k]), d2, 0.05); }), [d2, h0.length, h1.length]);
      await mp.evaluate(() => { v.debug.setAll({}); pr.api.highlightGroup(null); v.debug.renderNow(); });
      // drat + setModel (vyber pres oba druhy prezije, zadny unik) + bez chyb
      await mp.evaluate(() => { pr.api.clear(); pr.api.setGroup("s1", "pln"); pr.api.setGroup("s3", "mix4"); pr.api.setBox("b09", 2); });
      const selSM = await mp.evaluate(() => pr.api.get());
      await mp.evaluate(() => { v.setMode("wire"); });
      await mp.waitForFunction(() => v.state().mode === "wire", null, { timeout: 5000 });
      await mp.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const w1 = await mp.evaluate(() => { const r = platesOf(model(), "b05"); return { cw: r.colorWrite, lines: r.lineVerts, p: r.plates.length }; });
      await mp.evaluate(() => { v.setMode("real"); });
      await mp.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      const w2 = await mp.evaluate(() => platesOf(model(), "b05").colorWrite);
      t("S13 dratovy vzhled u podnosu: plocha pricek se nekresli (colorWrite false), hrany zustaly; po navratu do Skutecneho se kresli", w1.cw === false && w1.lines === 24 * w1.p && w1.p > 0 && w2 === true, [w1, w2]);
      await mp.evaluate(() => v.setModel("/fx/smisena.glb"));
      await mp.waitForTimeout(300);
      const res0 = await mp.evaluate(() => { v.debug.renderNow(); const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()) }; });
      for (let i = 0; i < 2; i++) await mp.evaluate(() => v.setModel("/fx/smisena.glb"));
      await mp.waitForTimeout(300);
      const res1 = await mp.evaluate(() => { v.debug.renderNow(); const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()), get: pr.api.get(), ready: pr.api.boxes().filter((b) => b.ready).length }; });
      t("S14 setModel: vyber pres multiboxy i podnosy (s1 Plny, s3 Mix 4, jeden podnos s2 pricky) prezije, pricky se vrati do vsech 9 boxu a nic neuniká (skupiny, geometrie, materialy, deti sceny stejne)",
        eq(res1.get, selSM) && res1.ready === 9 && res1.groups === res0.groups && res1.geos === res0.geos && res1.mats === res0.mats && res1.ch === res0.ch && res0.groups === Object.keys(selSM).length, [res0, res1, selSM]);
      t("S15 bez chyb v konzoli a ve strance (smisena scena, supliky)", (await errsOf(mp)).length === 0 && (await errsOf(sp)).length === 0, [await errsOf(mp), await errsOf(sp)]);
      // dispose (holy ctx): zadne skupiny / obrysy, vsechny geometrie a materialy uvolnene
      const dsp = await sp.evaluate(() => {
        D.pr.api.setAll("pln"); D.pr.api.highlightGroup("s1");
        const geos = [], mats = [];
        D.scene.traverse((o) => { if (o.userData && (o.userData.__pricky !== undefined || o.userData.__prickyHl !== undefined)) { if (o.geometry) geos.push(o.geometry); if (o.material) mats.push(o.material); } });
        const g0 = countGroups(D.scene), h0 = countHl(D.scene);
        window.__disposed.clear();
        D.off();
        return { g0: g0, h0: h0, groups: countGroups(D.scene), hl: countHl(D.scene), gone: geos.every((g) => __disposed.has(g)), mgone: mats.every((m) => __disposed.has(m)), geos: geos.length, ready: D.pr.api.ready(), set: D.pr.api.setBox("b01", 1), groups2: countGroups(D.scene) };
      });
      t("S16 dispose pluginu se supliky: zadne skupiny pricek ani obrysy ve scene, vsechny geometrie a materialy uvolnene, ready() = false, API dal nehazi", dsp.g0 > 0 && dsp.h0 > 0 && dsp.groups === 0 && dsp.hl === 0 && dsp.gone && dsp.mgone && dsp.geos > 0 && dsp.ready === false && dsp.set === true && dsp.groups2 === 0, dsp);

      // ---- varianty payloadu: klic typu, rozmery z payloadu, os, vyska
      const clone = (o) => JSON.parse(JSON.stringify(o));
      const kS = "S950x384x101", trayIds = SPL.boxy.filter((b) => b.k === kS).map((b) => b.id);          // 4 podnosy typu S950x384x101 (obe osy, oba smery)
      const selRef = {}; trayIds.forEach((id) => { selRef[id] = 3; });
      const dirPlates = async (payload, sel, ids) => {
        const { page: pgx } = await directPage("/fx/suplik.glb", payload);
        const out = await pgx.evaluate(([sel, ids]) => { D.pr.api.setMany(sel); return { ready: D.pr.api.boxes().filter((b) => ids.indexOf(b.id) >= 0 && b.ready).map((b) => b.id), pl: ids.map((id) => platesOf(D.scene, id).plates.map((p) => p.min.concat(p.max))) }; }, [sel, ids]);
        out.errs = await errsOf(pgx);
        return out;
      };
      const ref = await dirPlates(SPL, selRef, trayIds);
      const bare = clone(SPL);
      ["druh", "os", "L", "W", "H", "lem"].forEach((f) => { delete bare.typy[kS][f]; });
      const rBare = await dirPlates(bare, selRef, trayIds);
      t("S17 typ supliku bez poli druh / os / L / W / H / lem (jen klic S950x384x101): plugin vezme rozmery z klice a os 'b' a dava presne stejne pricky ve svete jako uplny payload",
        ref.ready.length === 4 && rBare.ready.length === 4 && ref.pl.every((p, i) => p.length === 3 && p.every((a, j) => nearV(a, rBare.pl[i][j], 0.01))) && ref.errs.length === 0 && rBare.errs.length === 0, [ref.ready, rBare.ready]);
      const osA = clone(SPL);
      osA.typy[kS].os = "a";
      const rOsA = await dirPlates(osA, selRef, trayIds);
      const minusE = SMBX.filter((m) => trayIds.indexOf(m.id) >= 0 && m.e < 0).map((m) => m.id);
      const flip = trayIds.map((id, i) => ({ id: id, same: ref.pl[i].every((a, j) => nearV(a, rOsA.pl[i][j], 0.01)), e: SMBX.find((m) => m.id === id).e }));
      t("S18 os z payloadu se dodrzi: s os 'a' (jako multibox: z od min kratsi osy, x s prevracenim) se pricky podnosu s e = -1 ocitnou na JINEM miste nez s os 'b' (pro e = +1 ve smeru z stejne, ale x se u e = +1 neprevraci), takze geometrie neni shodna s referenci",
        minusE.length === 2 && flip.filter((f) => f.e < 0).every((f) => !f.same), flip);
      const badH = clone(SPL);
      badH.typy[kS].H = 210;
      const rBadH = await dirPlates(badH, selRef, trayIds);
      const keyH = clone(SPL);
      const k210 = "S950x384x210";
      keyH.typy[k210] = clone(keyH.typy[kS]);
      ["L", "W", "H", "druh", "os", "lem"].forEach((f) => { delete keyH.typy[k210][f]; });
      keyH.boxy.forEach((b) => { if (b.k === kS) b.k = k210; });
      const rKeyH = await dirPlates(keyH, selRef, trayIds);
      t("S19 kontrola rozmeru boxu v modelu proti typu vcetne VYSKY: typ s H = 210 (v modelu 101) -> zadny podnos neni ready; typ s klicem ...x210 bez pole H -> zadny podnos neni ready (vyska z klice)", rBadH.ready.length === 0 && rKeyH.ready.length === 0 && ref.ready.length === 4, [rBadH.ready, rKeyH.ready]);
      const badL = clone(SPL);
      badL.typy[kS].L = 600;
      const rBadL = await dirPlates(badL, selRef, trayIds);
      const badW = clone(SPL);
      badW.typy[kS].W = 332;
      const rBadW = await dirPlates(badW, selRef, trayIds);
      t("S20 rozmery typu z payloadu (L, W) maji prednost pred klicem: L = 600 nebo W = 332 (v modelu 950 x 384) -> zadny podnos neni ready", rBadL.ready.length === 0 && rBadW.ready.length === 0, [rBadL.ready, rBadW.ready]);
      // klice: vadne tvary se zahodi (typ i jeho boxy), multibox s vlastni vyskou
      const kkErr = [];
      for (const bad of ["S950x384", "s950x384x101", "S950x384x101x5", "S9x384x101", "S950x384xx101", "950x384x101", "S950X384X101"]) {
        const pb = clone(SPL);
        pb.typy[bad] = clone(pb.typy[kS]);
        delete pb.typy[kS];
        pb.boxy.forEach((b) => { if (b.k === kS) b.k = bad; });
        const rb = await dirPlates(pb, selRef, trayIds);
        if (rb.ready.length !== 0 || rb.errs.length) kkErr.push(bad + " " + JSON.stringify([rb.ready, rb.errs]));
      }
      t("S21 vadne klice typu (S950x384, s950..., S950x384x101x5, S9x384x101, S950x384xx101, 950x384x101 (bez S, jako multibox s jinym tvarem), S950X...): typ se zahodi, jeho boxy nejsou ready, nic nespadne", kkErr.length === 0, kkErr.slice(0, 3));
      const PM = JSON.parse(fs.readFileSync(path.join(GEN, "synt.payload.json"), "utf8"));
      const mbxIds = ["b01", "b02"], selMb = { b01: 3, b02: 3 };
      const dirM = async (payload) => { const { page: pgx } = await directPage("/fx/synt.glb", payload); return pgx.evaluate(([sel, ids]) => { D.pr.api.setMany(sel); return { ready: D.pr.api.boxes().filter((b) => ids.indexOf(b.id) >= 0 && b.ready).map((b) => b.id), pl: ids.map((id) => platesOf(D.scene, id).plates.map((p) => p.min.concat(p.max))) }; }, [selMb, mbxIds]); };
      const strip = (pl) => { const c = clone(pl); Object.keys(c.typy).forEach((k) => { ["druh", "os", "L", "W", "H", "lem"].forEach((f) => { delete c.typy[k][f]; }); }); return c; };
      const m0 = await dirM(PM), mV4 = await dirM(strip(PM));
      const mA = clone(PM);
      Object.keys(mA.typy).forEach((k) => { mA.typy[k].os = "a"; mA.typy[k].druh = "box"; mA.typy[k].H = 81; mA.typy[k].L = 395.5; mA.typy[k].W = 186; mA.typy[k].lem = 28.4; });
      const mAr = await dirM(mA);
      const mH = clone(PM);
      mH.typy["395x186"].H = 100;
      const mHr = await dirM(mH);
      const mG = strip(PM);
      mG.geom.vyska_boxu = 90;
      const mGr = await dirM(mG), mG81 = strip(PM);
      mG81.geom.vyska_boxu = 81;
      const mG81r = await dirM(mG81);
      const same = (x, y) => x.pl.every((p, i) => p.length === 3 && p.every((a, j) => nearV(a, y.pl[i][j], 0.01)));
      t("S22 multiboxy v payloadu v4 (bez poli druh / os / L / W / H / lem) i v5 (os 'a', druh 'box', L / W / H / lem): stejna geometrie; vyska z geom.vyska_boxu (81 sedi, 90 ne) i z typu (H = 100 ne) se porovnava s vyskou boxu v modelu (81)",
        m0.ready.length === 2 && mV4.ready.length === 2 && mAr.ready.length === 2 && mG81r.ready.length === 2 && same(m0, mV4) && same(m0, mAr) && same(m0, mG81r) && mHr.ready.length === 0 && mGr.ready.length === 0, [m0.ready, mV4.ready, mAr.ready, mG81r.ready, mHr.ready, mGr.ready]);
    }
    gate();

    // ====================================================================== R) skutecne zakaznicke karty se supliky (v5)
    if (run("R")) console.log("\n## R) skutecne zakaznicke karty s podnosy supliku (<karta>.vse.glb: multiboxy i podnosy, skutecne AABB, pivoty a pohyby z modelu; karty bez podnosu se preskoci)");
    if (run("R")) {
      const cardsR = KARTY.vse || [];
      if (!cardsR.length) console.log("[PRESKOCENO] R (skutecne karty se supliky): v " + FIX + " neni zadna karta s podnosy (mbx sk = 4) - zakaznicka GLB z build_karty.py bez podnosu (stary build)");
      else {
        const E = { r1: [], r2: [], r3: [], r4: [], r5: [], r6: [] };
        const nfo = { cards: [], boxes: 0, trays: 0, sets: 0, plates: 0, moved: 0, movedTrays: 0 };
        for (const c of cardsR) {
          const PC = payloadOf(c + ".vse"), mbxC = readSpec(path.join(GEN, c + ".vse.glb")).mbx, idsC = PC.boxy.map((b) => b.id);
          const trayIdsC = PC.boxy.filter((b) => /^S\d/.test(b.k)).map((b) => b.id);
          nfo.cards.push(c + ":" + idsC.length + "/" + trayIdsC.length);
          nfo.boxes += idsC.length;
          nfo.trays += trayIdsC.length;
          const pgc = await viewerPage("/fx/" + c + ".vse.glb", PC);
          // R1: plugin nad skutecnou kartou: vsechny boxy a skupiny ready, druhy skupin a typy z payloadu
          const r1 = await pgc.evaluate(() => ({ sk: pr.api.skupiny().map((g) => [g.id, g.k, g.pocet_ready, g.boxu, g.ready, g.sety]), bx: pr.api.boxes().map((b) => [b.id, b.k, b.ready, b.max]) }));
          if (r1.sk.length !== PC.skupiny.length || !r1.sk.every((g, i) => g[0] === PC.skupiny[i].id && g[1] === PC.skupiny[i].k && g[4] === true && g[2] === g[3] && g[3] === PC.skupiny[i].boxy.length && eq(g[5], Object.keys(PC.skupiny[i].sety).sort((a, b) => PC.sety.findIndex((x) => x.id === a) - PC.sety.findIndex((x) => x.id === b)))))
            E.r1.push(c + " skupiny " + JSON.stringify(r1.sk).slice(0, 300));
          if (r1.bx.length !== idsC.length || !r1.bx.every((b) => b[2] === true && b[3] === PC.typy[b[1]].max)) E.r1.push(c + " boxy " + JSON.stringify(r1.bx.filter((b) => !b[2])).slice(0, 200));
          if (!trayIdsC.length || PC.skupiny.filter((g) => g.k === "suplik").length === 0) E.r1.push(c + " karta nema supliky v payloadu");
          // R2: geometrie kazdeho setu kazde skupiny (multiboxy i podnosy) na skutecnych AABB
          for (const g of PC.skupiny) {
            for (const sid of Object.keys(g.sety)) {
              const ok = await pgc.evaluate(([gid, sid]) => pr.api.setGroup(gid, sid), [g.id, sid]);
              const sel = fromSet(PC, g.id, sid), got = await pgc.evaluate(() => pr.api.get()), cr = await checkAny(pgc, PC, mbxC, sel, g.boxy, "V");
              nfo.sets++;
              nfo.plates += cr.counts.plates;
              if (ok !== true || !eq(got, sel) || cr.errs.length) E.r2.push(c + " " + g.id + "/" + sid + " " + JSON.stringify([ok, cr.errs.slice(0, 2)]).slice(0, 300));
            }
            await pgc.evaluate((gid) => pr.api.setGroup(gid, "bez"), g.id);
          }
          // R3: celek najednou (Plny set, potom Mix 4 kde je): geometrie vsech boxu + souhrn = nezavisly vypocet
          for (const sid of ["pln", "mix4"]) {
            await pgc.evaluate((sid) => { pr.api.clear(); pr.api.setAll(sid); }, sid);
            const sel = {};
            PC.skupiny.forEach((g) => { if (g.sety[sid]) Object.assign(sel, fromSet(PC, g.id, sid)); });
            const got = await pgc.evaluate(() => pr.api.get()), sou = await pgc.evaluate(() => pr.api.souhrn()), cr = await checkAny(pgc, PC, mbxC, sel, idsC, "V");
            if (!eq(got, sel) || cr.errs.length || !sumOk(sou, expectSummary(PC, sel))) E.r3.push(c + " " + sid + " " + JSON.stringify([cr.errs.slice(0, 2), sou.kusy, expectSummary(PC, sel).kusy]).slice(0, 300));
          }
          // R4: pohyb s pivoty: po otevreni vsech pohybu z motionIds() se pricky VSECH boxu (multiboxy i podnosy) posunou presne o vektor pivotu jejich boxu, boxy bez pivotu stoji
          await pgc.evaluate(() => { pr.api.clear(); pr.api.setAll("pln"); });
          const mid = await pgc.evaluate(() => pr.api.motionIds()), pivs = [...new Set(mbxC.map((m) => m.p).filter((x) => typeof x === "string"))];
          const snapR = () => pgc.evaluate(([ids, pivs]) => ({ pl: ids.map((id) => platesOf(model(), id).plates.map((p) => p.min.concat(p.max))), pv: pivs.map((p) => v.debug.pivot(p).world) }), [idsC, pivs]);
          const q0 = await snapR();
          await pgc.evaluate((ids) => { const T = {}; ids.forEach((i) => { T[i] = 1; }); v.debug.setAll(T); v.debug.renderNow(); }, mid);
          const q1 = await snapR(), dP = pivs.map((_, i) => q1.pv[i].map((x, k) => x - q0.pv[i][k]));
          let movedC = 0, movedT = 0;
          idsC.forEach((id, i) => {
            const mb = mbxC.find((m) => m.id === id), d = typeof mb.p === "string" ? dP[pivs.indexOf(mb.p)] : [0, 0, 0], mv = Math.hypot(d[0], d[1], d[2]) > 5;
            if (mv) { movedC++; if (trayIdsC.indexOf(id) >= 0) movedT++; }
            q0.pl[i].forEach((pa, j) => { const pb = q1.pl[i][j]; for (let k = 0; k < 6; k++) if (!near(pb[k] - pa[k], d[k % 3], 0.06)) { E.r4.push(c + " " + id + "#" + j + " posun " + (pb[k] - pa[k]).toFixed(2) + " != " + d[k % 3].toFixed(2)); break; } });
          });
          nfo.moved += movedC;
          nfo.movedTrays += movedT;
          const trayPiv = trayIdsC.filter((id) => typeof mbxC.find((m) => m.id === id).p === "string").length;
          if (trayPiv > 0 && movedT === 0) E.r4.push(c + " podnosy maji pivot (" + trayPiv + "), ale zadny se pri otevreni pohybu nepohnul");
          if (mid.length === 0 && pivs.length > 0) E.r4.push(c + " motionIds() je prazdne, ale boxy maji pivoty");
          await pgc.evaluate(() => { v.debug.setAll({}); v.debug.renderNow(); });
          // R5: obrys kazde skupiny = 1 obrys na box kolem skutecne AABB (+2 mm), i u podnosu
          const hlErr = [];
          for (const g of PC.skupiny) {
            const okh = await pgc.evaluate((gid) => pr.api.highlightGroup(gid), g.id), list = await pgc.evaluate(() => hlList(model()));
            const exp = g.boxy.map((id) => mbxC.find((m) => m.id === id));
            if (okh !== true || list.length !== exp.length || !exp.every((m) => { const o = list.find((x) => x.box === m.id); return o && m.min.every((vv, i) => near(o.min[i], vv - 2, 0.06) && near(o.max[i], m.max[i] + 2, 0.06)); })) hlErr.push(g.id + " " + JSON.stringify([okh, list.length, exp.length]));
          }
          await pgc.evaluate(() => pr.api.highlightGroup(null));
          hlErr.forEach((e) => E.r5.push(c + " " + e));
          // R6: setModel (stejny model, 2x): vyber prezije, pricky se vrati do vsech boxu, nic neuniká; bez chyb ve strance
          await pgc.evaluate(() => { pr.api.clear(); pr.api.setAll("pln"); });
          const selR = await pgc.evaluate(() => pr.api.get());
          await pgc.evaluate((u) => v.setModel(u), "/fx/" + c + ".vse.glb");
          await pgc.waitForTimeout(300);
          const x0 = await pgc.evaluate(() => { v.debug.renderNow(); const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()), ready: pr.api.boxes().filter((b) => b.ready).length, get: pr.api.get() }; });
          for (let i = 0; i < 2; i++) await pgc.evaluate((u) => v.setModel(u), "/fx/" + c + ".vse.glb");
          await pgc.waitForTimeout(300);
          const x1 = await pgc.evaluate(() => { v.debug.renderNow(); const r = v.debug.resources(); return { geos: r.geos, mats: r.mats, ch: r.sceneChildren, groups: countGroups(model()), ready: pr.api.boxes().filter((b) => b.ready).length, get: pr.api.get() }; });
          const er = await errsOf(pgc);
          if (!eq(x0.get, selR) || !eq(x1.get, selR) || x0.ready !== idsC.length || x1.ready !== idsC.length || x1.groups !== x0.groups || x0.groups !== Object.keys(selR).length || x1.geos !== x0.geos || x1.mats !== x0.mats || x1.ch !== x0.ch || er.length)
            E.r6.push(c + " " + JSON.stringify([x0, x1, er]).slice(0, 300));
        }
        const desc = nfo.cards.join(" ");
        t("R1 skutecne karty se supliky (" + desc + " = karta:boxu/z toho podnosu): plugin v5 prijme payload i model, VSECHNY boxy (multiboxy i podnosy) a skupiny jsou ready, druh a poradi skupin a nabizene sety sedi s payloadem, max z typu", E.r1.length === 0 && nfo.trays >= 1, E.r1.slice(0, 3));
        t("R2 PRESNA geometrie pricek na skutecnych AABB: kazdy set kazde skupiny (" + nfo.sets + " kombinaci, " + nfo.plates + " pricek v podnosech i multiboxech): podnosy podle kontraktu (dutina, sloty po 100 mm, e = strana cela), multiboxy jako dosud, get() presne", E.r2.length === 0 && nfo.sets >= cardsR.length * 4, E.r2.slice(0, 3));
        t("R3 cele karty najednou (Plny set a Mix 4): geometrie vsech boxu a souhrn (kusy, ceny, dily p186 / p91 / ps...) = nezavisly vypocet z payloadu", E.r3.length === 0, E.r3.slice(0, 3));
        t("R4 pohyb s pivoty na skutecnych kartach: po otevreni pohybu z motionIds() se pricky multiboxu i podnosu posunuly PRESNE o vektor pivotu sveho boxu, boxy bez pivotu stoji (" + nfo.moved + " boxu se pohnulo, z toho " + nfo.movedTrays + " podnosu)", E.r4.length === 0 && nfo.moved > 0, E.r4.slice(0, 3));
        t("R5 obrys skupiny (highlightGroup) u kazde skupiny skutecne karty: 1 obrys na box kolem jeho AABB (+2 mm), i u podnosu", E.r5.length === 0, E.r5.slice(0, 3));
        t("R6 setModel (2 x stejny model): vyber s Plnymi sety prezije, pricky se vrati do vsech boxu a nic neuniká (skupiny, geometrie, materialy, deti sceny); bez chyb ve strance", E.r6.length === 0, E.r6.slice(0, 3));
      }
    }
    gate();

    // ====================================================================== N) motionIds (v4.1): id pohybu vieweru, ktere otevrou boxy skupiny
    if (run("N")) console.log("\n## N) motionIds(gid): id pohybu vieweru, ktere otevrou (zvednou) boxy skupiny - pro automaticke vysunuti po vyberu setu");
    if (run("N")) {
      const allG = P21.skupiny.map((g) => g.id);
      const got = await pg.evaluate(() => ({ s1: pr.api.motionIds("s1"), s2: pr.api.motionIds("s2"), s3: pr.api.motionIds("s3"), all: pr.api.motionIds(), allNull: pr.api.motionIds(null) }));
      const idsViewer = await pg.evaluate(() => v.state().motions.map((m) => m.id));
      const kindOf = (id) => ((spec21.motions || []).find((m) => m.id === id) || {}).k;
      t("N1 karta 4921 (skutecny model, 41 pohybu): motionIds('s1' / 's2' / 's3') = unikatni id pohybu k 'box' boxu skupiny v poradi boxu skupiny (8, 7, 7 pohybu), shodne s nezavislym vypoctem ze spec",
        eq(got.s1, expectIds(spec21, P21, ["s1"])) && eq(got.s2, expectIds(spec21, P21, ["s2"])) && eq(got.s3, expectIds(spec21, P21, ["s3"])) && got.s1.length === 8 && got.s2.length === 7 && got.s3.length === 7, got);
      t("N2 motionIds() bez gid (i s null) = pohyby vsech skupin za sebou (22 unikatnich), kazde id je platny pohyb vieweru (v.state().motions) typu 'box'",
        eq(got.all, expectIds(spec21, P21, allG)) && eq(got.allNull, got.all) && got.all.length === 22 && new Set(got.all).size === 22 && got.all.every((id) => idsViewer.indexOf(id) >= 0 && kindOf(id) === "box")
        && eq(got.all, [].concat(got.s1, got.s2, got.s3)), [got.all.length, got.all.filter((id) => idsViewer.indexOf(id) < 0)]);
      // semantika: pustit id skupiny s2 = pohnou se pivoty boxu s2 a ZADNE jine
      const pivOf = (gid) => grpOf(P21, gid).boxy.map((id) => mbx21.find((m) => m.id === id).p);
      const sem = await pg.evaluate(([ids, pivs]) => {
        v.debug.setAll({});
        const w0 = pivs.map((p) => v.debug.pivot(p).world), T = {};
        ids.forEach((i) => { T[i] = 1; });
        v.debug.setAll(T);
        const w1 = pivs.map((p) => v.debug.pivot(p).world);
        v.debug.setAll({});
        return { w0: w0, w1: w1 };
      }, [got.s2, pivOf("s1").concat(pivOf("s2"), pivOf("s3"))]);
      const dist = sem.w0.map((w, i) => Math.hypot(w[0] - sem.w1[i][0], w[1] - sem.w1[i][1], w[2] - sem.w1[i][2]));
      const nS1 = pivOf("s1").length, nS2 = pivOf("s2").length;
      t("N3 semantika na viewer: po pusteni pohybu z motionIds('s2') se pohnou pivoty VSECH boxu skupiny s2 (> 5 mm) a pivoty boxu s1 a s3 zustanou na miste",
        dist.slice(nS1, nS1 + nS2).every((d) => d > 5) && dist.slice(0, nS1).every((d) => d < 0.01) && dist.slice(nS1 + nS2).every((d) => d < 0.01), dist.map((d) => Math.round(d)));
      const fresh = await pg.evaluate(() => { const a = pr.api.motionIds("s1"); a.push("x"); a.length = 0; return pr.api.motionIds("s1").length; });
      t("N4 kazde volani vraci NOVE pole (zmena vraceneho pole neovlivni dalsi vysledky)", fresh === 8, fresh);

      // ---- syntetika (pohyby.glb: motions box / slide / drawer + vadne polozky, boxy bez pivotu / bez pohybu / mimo model / se sdilenym pivotem)
      const PP = JSON.parse(fs.readFileSync(path.join(GEN, "pohyby.payload.json"), "utf8"));
      const { page: np } = await directPage("/fx/pohyby.glb", PP);
      const r = await np.evaluate(() => ({ s1: D.pr.api.motionIds("s1"), s2: D.pr.api.motionIds("s2"), s3: D.pr.api.motionIds("s3"), s4: D.pr.api.motionIds("s4"), s5: D.pr.api.motionIds("s5"),
        all: D.pr.api.motionIds(), none: D.pr.api.motionIds(null), und: D.pr.api.motionIds(undefined), ready: D.pr.api.boxes().filter((b) => b.ready).map((b) => b.id).join(",") }));
      t("N5 box -> pohyb podle steps[].p: s1 = ['m3', 'm4'] (b01 a b02 sdili pivot = m3 jen jednou, b03 bez pivotu se preskoci, vadne polozky motions se ignoruji)", eq(r.s1, ["m3", "m4"]), r);
      t("N6 prednost pohybu k 'box': pivot p06 ma pohyb slide (m6, v seznamu driv) i box (m7) -> m7; pivot p05 ma JEN slide -> m5; pivot p12 ma jen slide m11 a drawer m12 -> PRVNI (m11); box s pivotem bez pohybu (p11) se preskoci: s2 = ['m5', 'm7', 'm11']", eq(r.s2, ["m5", "m7", "m11"]), r.s2);
      t("N7 pivot boxu az ve 2. kroku pohybu (m8) se najde; poradi je podle BOXU skupiny, ne podle id pohybu: s3 (b08, b09, b10) = ['m8', 'm10', 'm9']; pivot p10 ma dva pohyby k box (m10, pozdeji m13) -> prvni (m10)", eq(r.s3, ["m8", "m10", "m9"]), r.s3);
      t("N8 box mimo model (pivot p99 v modelu neni) se preskoci a sdileny pivot z jine skupiny dava totez id: s4 = ['m3']; skupina jen se statickym boxem: s5 = []; boxy mimo model nejsou ready (b11)",
        eq(r.s4, ["m3"]) && eq(r.s5, []) && r.ready.split(",").indexOf("b11") < 0 && r.ready.split(",").indexOf("b12") >= 0, [r.s4, r.s5, r.ready]);
      t("N9 vsechny skupiny najednou: unikatne a po skupinach = ['m3', 'm4', 'm5', 'm7', 'm11', 'm8', 'm10', 'm9'] (m3 se sdilenym pivotem jen jednou); gid null / undefined = totez", eq(r.all, ["m3", "m4", "m5", "m7", "m11", "m8", "m10", "m9"]) && eq(r.none, r.all) && eq(r.und, r.all), r);
      const inv = await np.evaluate(() => ["s9", "", "S1", "b01", "__proto__", "constructor", "toString", 5, 0, true, false, {}, [], ["s1"], function () {}, NaN].map((g) => JSON.stringify(D.pr.api.motionIds(g))));
      t("N10 neplatne / neznamé gid (neznama skupina, prazdny retezec, id boxu, __proto__, ne-retezce vc. 0, false, pole, objekt, funkce) = [] a nic nevyhodi", inv.every((x) => x === "[]"), inv);
      const dsp = await np.evaluate((PP) => ({ before: D.pr.api.motionIds().length, off: D.off() === undefined, po: D.pr.api.motionIds(), poS: D.pr.api.motionIds("s1"),
        bezModelu: [V3DPricky.create({ payload: PP }).api.motionIds("s1"), V3DPricky.create({ payload: PP }).api.motionIds()], neplatny: V3DPricky.create({ payload: null }).api.motionIds("s1") }), PP);
      t("N11 po dispose pluginu, u pluginu bez modelu (plugin(ctx) nebyl zavolan) a u neplatneho payloadu = [] (pred dispose 8 id)", dsp.before === 8 && dsp.off && eq(dsp.po, []) && eq(dsp.poS, []) && eq(dsp.bezModelu, [[], []]) && eq(dsp.neplatny, []), dsp);
      // setModel na model bez mbx: boxy nejsou v modelu -> []; zpet na model s mbx -> id se vrati
      await pg.evaluate(() => v.setModel("/fx/nombx.glb"));
      await pg.waitForTimeout(300);
      const nb = await pg.evaluate(() => ({ s1: pr.api.motionIds("s1"), all: pr.api.motionIds() }));
      await pg.evaluate(() => v.setModel("/fx/4921.offer.glb"));
      await pg.waitForTimeout(300);
      const nb2 = await pg.evaluate(() => ({ s1: pr.api.motionIds("s1"), all: pr.api.motionIds().length }));
      t("N12 setModel na model bez mbx = [] (boxy nejsou v modelu), zpet na 4921 se id skupin vrati (plugin se spusti znovu a znovu cte spec.motions)", eq(nb.s1, []) && eq(nb.all, []) && eq(nb2.s1, got.s1) && nb2.all === 22, [nb, nb2]);
      t("N13 bez chyb v konzoli a ve strance (motionIds)", (await errsOf(pg)).length === 0 && (await errsOf(np)).length === 0, [await errsOf(pg), await errsOf(np)]);
    }
    gate();
  } catch (e) {
    if (e && e.message !== "STOP_ON_FAIL") { t("VYJIMKA TESTU: " + (e.stack || e.message).split("\n").slice(0, 3).join(" / "), false); }
  }
  for (const c of pages) await c.close().catch(() => {});
  await browser.close();
  server.close();
  cleanup();
  console.log(`\n${total - bad}/${total} OK`);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.error("TEST SPADL:", e.message); cleanup(); process.exit(2); });
