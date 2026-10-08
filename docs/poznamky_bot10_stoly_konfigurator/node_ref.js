// REFERENCNI vypocet pro prototyp_compose_glb.py (bot10, 2026-10-02, jen cteni, nic nezapisuje mimo K).
//
// Ctene vstupy: JSON z Pythonu {parts:[{part_id,position,quaternion,scale,lic_peers?}], glb_map:{part_id:glb_file},
//   is_profile:{part_id:bool}, length_mm:{part_id:..}, cross:{part_id:[a,b]}}
// Co dela (vsechno na SKUTECNE geometrii, THREE r128 z /opt/konfigurator/node_modules):
//   1) Box3 kazdeho dilu + sjednoceni (parseGlbMesh z scripts/2026-08-19_glb_real_geometry.js, TRS jako loadCustomShapePartEntry)
//   2) pocet spoju PRESNE KODEM ZE scene.html: funkce profileLengthAxisWorld / profileAxialOverlapMm /
//      inferProfileJointConnectors / classifyJointPair / autoRegisterTouchedProfileJoints / registerLicJoint se
//      vyrezou jako TEXT ze scene.html a spusti ve vm (zadna vlastni reimplementace) + scene-geometry-shared.js.
//      Varianty:  scena_po_nacteni  = lic_peers z ulozeni + autoRegister (jako insertCustomShape)
//                 jen_geometrie     = autoRegister bez lic_peers (jedine, co jde spocitat pro zmenene rozmery)
// Spusteni: node node_ref.js vstup.json vystup.json
const fs = require("fs"), vm = require("vm"), path = require("path");
const REPO = "/opt/konfigurator";
const THREE = require(REPO + "/node_modules/three");
const { parseGlbMesh } = require(REPO + "/scripts/2026-08-19_glb_real_geometry.js");
const shared = require(REPO + "/webapp/js/scene-geometry-shared.js");

const inp = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const KAT = REPO + "/webapp/katalog/";
const sceneSrc = fs.readFileSync(REPO + "/webapp/scene.html", "utf8");

// ---- vyrez funkce ze scene.html podle zacatku radku + vyvazeni slozenych zavorek (s ohledem na retezce/komentare/regex)
function extractFn(src, header) {
  const i = src.indexOf(header);
  if (i < 0) throw new Error("nenalezeno: " + header);
  let j = src.indexOf("{", i), depth = 0, k = j;
  let inStr = null, inLine = false, inBlock = false, prev = "";
  for (; k < src.length; k++) {
    const c = src[k], n = src[k + 1];
    if (inLine) { if (c === "\n") inLine = false; continue; }
    if (inBlock) { if (c === "*" && n === "/") { inBlock = false; k++; } continue; }
    if (inStr) { if (c === "\\") { k++; continue; } if (c === inStr) inStr = null; continue; }
    if (c === "/" && n === "/") { inLine = true; continue; }
    if (c === "/" && n === "*") { inBlock = true; continue; }
    if (c === '"' || c === "'" || c === "`") { inStr = c; continue; }
    if (c === "{") depth++;
    else if (c === "}") { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}
const FN = {};
["function profileLengthAxisWorld(", "function profileAxialOverlapMm(", "function inferProfileJointConnectors(",
 "function classifyJointPair(", "function autoRegisterTouchedProfileJoints(", "  function registerLicJoint("]
  .forEach(h => { FN[h.trim()] = extractFn(sceneSrc, h); });

function makeCtx(entries) {
  const ctx = {
    THREE, console, Set, Map, Math, Infinity, Array, Object,
    placed: entries,
    isProfilePart: shared.isProfilePart, isStampPart: shared.isStampPart, isKontrolniPart: shared.isKontrolniPart,
    worldConnectorsOf: shared.worldConnectorsOf, linkJointPeers: shared.linkJointPeers,
    showJoinToast: undefined,
  };
  vm.createContext(ctx);
  vm.runInContext(Object.values(FN).join("\n") + "\nthis.__fn = {profileLengthAxisWorld, profileAxialOverlapMm, inferProfileJointConnectors, classifyJointPair, autoRegisterTouchedProfileJoints, registerLicJoint};", ctx);
  return ctx;
}

const geoCache = new Map();
function getMesh(file) {
  if (!geoCache.has(file)) geoCache.set(file, parseGlbMesh(KAT + file));
  return geoCache.get(file).clone(true);
}

function buildEntries(parts) {
  return parts.map((p, i) => {
    const file = inp.glb_map[p.part_id];
    if (!file) return null;
    const obj = getMesh(file);
    obj.position.set(0, 0, 0); obj.quaternion.set(0, 0, 0, 1); obj.scale.set(1, 1, 1); obj.updateMatrixWorld(true);
    const isProf = !!inp.is_profile[p.part_id];
    const part = { id: p.part_id, length_mm: isProf ? inp.length_mm[p.part_id] : null,
                   cross_section_mm: isProf ? inp.cross[p.part_id] : [null, null], name: p.part_id };
    const connectorsLocal = shared.computeConnectorsLocal(obj);   // na identite, PRED umistenim (jako loadCustomShapePartEntry)
    obj.position.set(...p.position); obj.quaternion.set(...p.quaternion); obj.scale.set(...p.scale);
    obj.updateMatrixWorld(true);
    obj.userData.basePos = obj.position.clone();
    const e = { part, object3d: obj, connectorsLocal, _i: i };
    if (p.role) e.role = p.role;
    return e;
  });
}

function boxes(entries) {
  const out = [], u = new THREE.Box3();
  entries.forEach((e, i) => {
    if (!e) { out.push(null); return; }
    e.object3d.updateMatrixWorld(true);
    const b = new THREE.Box3().setFromObject(e.object3d);
    out.push({ min: b.min.toArray(), max: b.max.toArray() });
    u.union(b);
  });
  return { per_part: out, union: { min: u.min.toArray(), max: u.max.toArray() } };
}

function countScene(parts, withLic) {
  const entries = buildEntries(parts);
  const ctx = makeCtx(entries.filter(Boolean));
  const f = ctx.__fn;
  // registerLicJoint je v ostre scene uvnitr IIFE, vidi tyz globalni kontext -> pridej do kontextu pro autoRegister
  ctx.registerLicJoint = f.registerLicJoint; ctx.classifyJointPair = f.classifyJointPair;
  ctx.inferProfileJointConnectors = f.inferProfileJointConnectors; ctx.profileLengthAxisWorld = f.profileLengthAxisWorld;
  ctx.profileAxialOverlapMm = f.profileAxialOverlapMm;
  const prof = entries.filter(e => e && e.part && shared.isProfilePart(e.part));
  if (withLic) {
    // jako insertCustomShape: lic_peers (indexy v poli parts) -> licPeers; pak prestavba uctu pres classifyJointPair
    parts.forEach((p, i) => {
      if (!entries[i] || !Array.isArray(p.lic_peers)) return;
      p.lic_peers.forEach(j => { if (entries[j] && entries[j] !== entries[i]) shared.linkJointPeers(entries[i], entries[j]); });
    });
    entries.forEach(e => { if (e && shared.isProfilePart(e.part)) e.jointCount = 0; });
    entries.forEach((e, myIdx) => {
      if (!e || !shared.isProfilePart(e.part) || !e.licPeers) return;
      e.licPeers.forEach(peer => {
        if (!peer || !shared.isProfilePart(peer.part)) return;
        const peerIdx = entries.indexOf(peer);
        if (peerIdx < 0) return;
        const cls = (myIdx < peerIdx) ? f.classifyJointPair(e, peer) : null;
        if (cls) e.jointCount = (e.jointCount || 0) + 1;     // drzitel nehraje roli pro SOUCET
      });
    });
  } else {
    entries.forEach(e => { if (e) e.jointCount = 0; });
  }
  const cache = new Map();
  entries.forEach(e => { if (e && shared.isProfilePart(e.part)) f.autoRegisterTouchedProfileJoints(e, cache); });
  const total = entries.reduce((s, e) => s + ((e && e.jointCount) || 0), 0);
  // pary profil-profil, ktere jsou zapocitane (pro porovneni s Pythonem po dvojicich)
  const pairs = [];
  prof.forEach(a => {
    (a.licPeers || new Set()).forEach(b => {
      const ia = entries.indexOf(a), ib = entries.indexOf(b);
      if (ia < ib && f.classifyJointPair(a, b)) pairs.push([ia, ib]);
    });
  });
  pairs.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
  return { total, pairs };
}

if (inp.batch) {
  // davka: [{id, parts}] -> {id: pocet spoju jen geometrie (kod scene.html)}; jen pro hromadne porovnani
  const res = {};
  inp.batch.forEach(b => { try { res[b.id] = countScene(b.parts, false).total; } catch (e) { res[b.id] = "ERR " + e.message; } });
  fs.writeFileSync(process.argv[3], JSON.stringify(res));
  console.log("node_ref davka OK:", Object.keys(res).length);
} else {
  const out = { boxes: boxes(buildEntries(inp.parts)) };
  out.joints_scena_po_nacteni = countScene(inp.parts, true);
  out.joints_jen_geometrie = countScene(inp.parts, false);
  out.stored_joint_count_sum = inp.parts.reduce((s, p) => s + (p.joint_count || 0), 0);
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
  console.log("node_ref OK: dily", inp.parts.length, "| scena_po_nacteni", out.joints_scena_po_nacteni.total,
    "| jen_geometrie", out.joints_jen_geometrie.total, "| ulozeny soucet joint_count", out.stored_joint_count_sum);
}
