// Overovaci skript (Robert 2026-09-13: "spocitej podle tebou navrzeneho
// idealniho postupu kolik tam tech cel, ktere jsou zaroven spojem").
// PRESNA kopie produkcni logiky touch-detekce z webapp/scene.html
// (autoRegisterTouchedProfileJoints + inferProfileJointConnectors,
// EPS_FACE=0.75/EPS_OVERLAP=0.5, plne pokryti mensi plochy - viz
// PRAVIDLA_SPOJU.md "Presna definice spoje", oprava 2026-08-31) -
// NE zastarala scripts/2026-08-18_scene_geometry_lib.js::isValidFlushTouch
// (ta jeste kontroluje jen "libovolny presah > 0", predchazi opravu).
//
// Bezi jen NAD sestavou 346 (Doblo K-075 C, bez horniho bloku) - jednorazove
// overeni PRED katalogovym prepoctem, na skutecne .glb geometrii.
const fs = require("fs");
const path = require("path");
const { worldConnectorsOf, computeConnectorsLocal, isProfilePart } = require("./2026-08-18_scene_geometry_lib.js");
const { parseGlbMesh } = require("./2026-08-19_glb_real_geometry.js");
const R = require("./2026-09-11_glb_resolver.js");
const THREE = require("three");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/c0c788fb-0783-4d56-adb5-543ba6b0dda8/scratchpad";
const katalog = JSON.parse(fs.readFileSync(path.join(SCRATCH, "katalog_346.json"), "utf8"));
const sestava = JSON.parse(fs.readFileSync(path.join(SCRATCH, "sestava_346.json"), "utf8"));
const katalogById = new Map(katalog.map(p => [p.id, p]));

function jeRazitko(role) {
  return String(role || "").startsWith("logo-ochrana") || role === null && false; // viz nize - resime primo part_id
}

const meshCache = new Map();
function meshFor(glbFile) {
  if (!meshCache.has(glbFile)) meshCache.set(glbFile, parseGlbMesh(glbFile));
  return meshCache.get(glbFile);
}

const EPS_FACE = 0.75, EPS_OVERLAP = 0.5;
const AXES = ["x", "y", "z"];

function profileLengthAxisWorld(entry) {
  const endIdxs = [];
  entry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return null;
  const w = worldConnectorsOf(entry);
  return w[endIdxs[1]].point.clone().sub(w[endIdxs[0]].point).normalize();
}

function profileAxialOverlapMm(entry, profEntry) {
  const endIdxs = [];
  profEntry.connectorsLocal.forEach((c, i) => { if (c.kind === "end") endIdxs.push(i); });
  if (endIdxs.length !== 2) return Infinity;
  const profWorld = worldConnectorsOf(profEntry);
  const A = profWorld[endIdxs[0]].point, B = profWorld[endIdxs[1]].point;
  const axis = B.clone().sub(A);
  const L = axis.length();
  if (L < 1e-6) return Infinity;
  axis.normalize();
  entry.object3d.updateMatrixWorld(true);
  const bbox = new THREE.Box3().setFromObject(entry.object3d);
  if (bbox.isEmpty()) return Infinity;
  let mn = Infinity, mx = -Infinity;
  for (let xi = 0; xi < 2; xi++) for (let yi = 0; yi < 2; yi++) for (let zi = 0; zi < 2; zi++) {
    const corner = new THREE.Vector3(xi ? bbox.max.x : bbox.min.x, yi ? bbox.max.y : bbox.min.y, zi ? bbox.max.z : bbox.min.z);
    const t = corner.sub(A).dot(axis);
    if (t < mn) mn = t;
    if (t > mx) mx = t;
  }
  return Math.min(mx, L) - Math.max(mn, 0);
}

// presna kopie inferProfileJointConnectors (webapp/scene.html)
function inferProfileJointConnectors(entry, peer) {
  const entryAxis = profileLengthAxisWorld(entry);
  const peerAxis = profileLengthAxisWorld(peer);
  if (!entryAxis || !peerAxis) return null;
  const myWorld = worldConnectorsOf(entry);
  const peerWorld = worldConnectorsOf(peer);
  const axDot = Math.abs(entryAxis.dot(peerAxis));
  let myKinds, peerKinds, typ;
  if (axDot < 0.1) {
    entry.object3d.updateMatrixWorld(true);
    peer.object3d.updateMatrixWorld(true);
    const boxE = new THREE.Box3().setFromObject(entry.object3d);
    const boxP = new THREE.Box3().setFromObject(peer.object3d);
    let dEndE = Infinity, dEndP = Infinity;
    myWorld.forEach(cw => { if (cw.kind === "end") dEndE = Math.min(dEndE, boxP.distanceToPoint(cw.point)); });
    peerWorld.forEach(cw => { if (cw.kind === "end") dEndP = Math.min(dEndP, boxE.distanceToPoint(cw.point)); });
    if (dEndE <= dEndP) { myKinds = ["end"]; peerKinds = ["mid"]; typ = "T (moje celo na jeho bok)"; }
    else { myKinds = ["mid"]; peerKinds = ["end"]; typ = "T (jeho celo na muj bok)"; }
  } else if (axDot > 0.9) {
    if (profileAxialOverlapMm(entry, peer) > 5) { myKinds = ["face"]; peerKinds = ["face"]; typ = "bok-k-boku (wall)"; }
    else { myKinds = ["end"]; peerKinds = ["end"]; typ = "rovne prodlouzeni (celo-na-celo)"; }
  } else {
    return { typ: "sikmy dotyk (neklasifikovano)", myConnIdx: null, otherConnIdx: null };
  }
  let best = null, bestDist = Infinity;
  myWorld.forEach((mc, mi) => {
    if (!myKinds.includes(mc.kind)) return;
    peerWorld.forEach((pc, pi) => {
      if (!peerKinds.includes(pc.kind)) return;
      const d = mc.point.distanceTo(pc.point);
      if (d < bestDist) { bestDist = d; best = { myConnIdx: mi, otherConnIdx: pi }; }
    });
  });
  return { typ, myKind: myKinds[0], peerKind: peerKinds[0], ...best };
}

// presna kopie touch-testu z autoRegisterTouchedProfileJoints
function touchAxis(boxA, boxB) {
  for (let axisIdx = 0; axisIdx < 3; axisIdx++) {
    const a = AXES[axisIdx];
    const faceClose = Math.abs(boxA.max[a] - boxB.min[a]) < EPS_FACE || Math.abs(boxA.min[a] - boxB.max[a]) < EPS_FACE;
    if (!faceClose) continue;
    let overlaps = true;
    for (let j = 0; j < 3; j++) {
      if (j === axisIdx) continue;
      const oa = AXES[j];
      const lo = Math.max(boxA.min[oa], boxB.min[oa]);
      const hi = Math.min(boxA.max[oa], boxB.max[oa]);
      const sizeA = boxA.max[oa] - boxA.min[oa];
      const sizeB = boxB.max[oa] - boxB.min[oa];
      const minSize = Math.min(sizeA, sizeB);
      if ((hi - lo) < (minSize - EPS_OVERLAP)) { overlaps = false; break; }
    }
    if (overlaps) return axisIdx;
  }
  return -1;
}

// ---- Sestav entries pro VSECHNY profil-profil kandidaty ----
const STAMP_PART_IDS = new Set(["logo_logiman_cz", "vypln_drazky_30"]);
const parts = sestava.data.parts;
const profileEntries = [];
let skippedNonProfile = 0, skippedStamp = 0, skippedCarBody = 0, skippedNoGlb = 0;

parts.forEach((p, idx) => {
  const pid = p.part_id;
  if (R.jeKaroserie(pid)) { skippedCarBody++; return; }
  if (STAMP_PART_IDS.has(pid)) { skippedStamp++; return; }
  const kat = katalogById.get(pid);
  if (!kat || !isProfilePart(kat)) { skippedNonProfile++; return; }
  const glb = R.glbPath(pid);
  if (!glb) { skippedNoGlb++; console.log("CHYBA: neni GLB pro", pid); return; }
  const mesh = meshFor(glb);
  const obj = new THREE.Mesh(mesh.geometry);
  // KRITICKE (viz runAIPlan/loadGlbAsync v scene.html): computeConnectorsLocal
  // MUSI bezet na objektu v identite (position 0, quaternion identity) - pocita
  // Box3 pres matrixWorld, takze pozdejsi worldConnectorsOf() transformuje
  // "local" body podruhe. Nastavit position/quaternion az PO tomhle volani.
  obj.updateMatrixWorld(true);
  const connectorsLocal = computeConnectorsLocal(obj);
  obj.position.set(...p.position);
  obj.quaternion.set(...p.quaternion);
  if (p.scale) obj.scale.set(...p.scale); else obj.scale.set(1, 1, 1);
  obj.updateMatrixWorld(true);
  profileEntries.push({ idx, partId: pid, role: p.role, object3d: obj, connectorsLocal });
});

console.log(`Dilu celkem: ${parts.length}`);
console.log(`  karoserie (preskoceno): ${skippedCarBody}`);
console.log(`  razitka (preskoceno): ${skippedStamp}`);
console.log(`  neni profil / bez katalog. zaznamu (preskoceno): ${skippedNonProfile}`);
console.log(`  chybi GLB: ${skippedNoGlb}`);
console.log(`  PROFIL-PROFIL kandidatu do parovani: ${profileEntries.length}`);
console.log("");

// ---- Vsechny dvojice - presny touch test ----
const joints = [];
for (let i = 0; i < profileEntries.length; i++) {
  for (let j = i + 1; j < profileEntries.length; j++) {
    const a = profileEntries[i], b = profileEntries[j];
    const boxA = new THREE.Box3().setFromObject(a.object3d);
    const boxB = new THREE.Box3().setFromObject(b.object3d);
    if (boxA.isEmpty() || boxB.isEmpty()) continue;
    const axisIdx = touchAxis(boxA, boxB);
    if (axisIdx < 0) continue;
    const info = inferProfileJointConnectors(a, b);
    joints.push({ a, b, axis: AXES[axisIdx], info });
  }
}

console.log(`=== NALEZENO SPOJU (profil-profil, plna definice PRAVIDLA_SPOJU.md): ${joints.length} ===`);
console.log("");

// ---- Kolik z nich ma skutecne "celo" (end-kind konektor) na ktere strane ----
// OPRAVA (nalezeno pri tomhle overeni): puvodni verze merila vzdalenost
// konce OD DISKRETNICH KONEKTORU souseda (end/end/mid/face - jen ~4-7
// pevnych bodu na dilu) - u "mid" konektoru pruchozi nohy to je bod v
// JEJIM STREDU, ne tam, kde po jeji delce prislusenstvi realne dosedaji.
// U dlouhe nohy s prickou daleko od stredu tak vychazela vzdalenost
// stovky mm i pro SKUTECNE dotykajici se celo - presne stejna trida chyby
// jako "mid konektor merime jako bod, ne jako celou stenu". Spravne (a
// presne to, co uz pouziva inferProfileJointConnectors pro KLASIFIKACI
// T/roh vyse - boxP.distanceToPoint): vzdalenost konce OD SKUTECNE
// PLOCHY (Box3) souseda, ne od jeho pevnych bodu.
const JOINT_FACE_NEAR_MM = 2;
function nearestOwnEnd(entry, other) {
  const myConns = worldConnectorsOf(entry);
  other.object3d.updateMatrixWorld(true);
  const otherBox = new THREE.Box3().setFromObject(other.object3d);
  let bestIdx = null, bestDist = Infinity;
  entry.connectorsLocal.forEach((c, idx) => {
    if (c.kind !== "end") return;
    const d = otherBox.distanceToPoint(myConns[idx].point);
    if (d < bestDist) { bestDist = d; bestIdx = idx; }
  });
  return bestIdx == null ? null : { idx: bestIdx, dist: bestDist };
}

let facesTotal = 0;
const perTypeCount = {};
joints.forEach((j, n) => {
  const typ = j.info.typ;
  perTypeCount[typ] = (perTypeCount[typ] || 0) + 1;
  const nearA = nearestOwnEnd(j.a, j.b);
  const nearB = nearestOwnEnd(j.b, j.a);
  const faceA = nearA && nearA.dist <= JOINT_FACE_NEAR_MM;
  const faceB = nearB && nearB.dist <= JOINT_FACE_NEAR_MM;
  const facesHere = (faceA ? 1 : 0) + (faceB ? 1 : 0);
  facesTotal += facesHere;
  console.log(
    `${n + 1}. #${j.a.idx}(${j.a.role || "?"}) <-> #${j.b.idx}(${j.b.role || "?"}) ` +
    `| osa dotyku=${j.axis} | typ=${typ} | celo A=${faceA ? "ANO d=" + nearA.dist.toFixed(2) + "mm" : "ne"} ` +
    `celo B=${faceB ? "ANO d=" + nearB.dist.toFixed(2) + "mm" : "ne"} | cel na tomhle spoji=${facesHere}`
  );
});

console.log("");
console.log("=== SOUHRN ===");
console.log(`Pocet SPOJU (= "Cena spoju" zaklad, kazdy fyzicky dotyk 1x): ${joints.length}`);
Object.entries(perTypeCount).forEach(([t, c]) => console.log(`  z toho ${t}: ${c}`));
console.log(`Pocet CEL (kolikrat se na nektere strane spoje najde skutecny koncovy konektor blizko doteku, presne to co znaci tlacitko "Cela = spoj"): ${facesTotal}`);

// ---- --apply: zapis lic_peers/joint_count/hidden_end_conn/used_conn zpet
// do data.parts sestavy 346 (indexy = puvodni p.idx, presne format, ktery
// insertCustomShape() cte pri nacteni - viz webapp/scene.html "Krizove
// odkazy MEZI dily (lic_peers...) se resi az kdyz jsou nactene VSECHNY
// entries"). "Čela = spoj" cte JEN lic_peers (highlightJointCountedFaces),
// joint_count/hidden_end_conn/used_conn jsou navic pro "Cena spoju" a pro
// obecnou konzistenci se zbytkem ucetnictvi.
if (process.argv.includes("--apply")) {
  const perPart = new Map(); // idx -> {licPeers:Set, jointCount, hiddenEndConn:Set, usedConn:Set}
  const get = idx => {
    if (!perPart.has(idx)) perPart.set(idx, { licPeers: new Set(), jointCount: 0, hiddenEndConn: new Set(), usedConn: new Set() });
    return perPart.get(idx);
  };
  // OPRAVA (Robert 2026-09-13, "346 ma 73 spoju spravne, nevim co je
  // mysleno tim 74"): Robertova PRESNA definice (PRAVIDLA_SPOJU.md, 2d +
  // "Presna definice spoje", 2026-08-31) - "existuje pouze pokud se cela
  // plocha CELA jednoho profilu dotyka bud cele plochy cela druheho, NEBO
  // kterekoli steny" - vyzaduje, aby ALESPON JEDNA strana byla skutecne
  // "celo" (zavit). "bok-k-boku" (wall) typ - obe strany rovnobezne s
  // prekryvem, ZADNA strana neni "celo" - tuhle podminku nesplnuje, i
  // kdyz box test rekl "dotykaji se". U 346 presne 1 takova dvojice
  // (#30 pricka-uzavreni-vyrezu <-> #61 spojnice-col0-p0) - proto 74 (vsechny
  // box-test dotyky) != 73 (skutecne spoje podle definice). lic_peers
  // (obecna "dotyka se" evidence, sirsi nez jen spoje) zustava VCETNE
  // tehle dvojice - jointCount/hiddenEndConn/usedConn uz ne.
  joints.forEach(j => {
    const pa = get(j.a.idx), pb = get(j.b.idx);
    pa.licPeers.add(j.b.idx); pb.licPeers.add(j.a.idx);
    const aIsEnd = j.info.myKind === "end";
    const bIsEnd = j.info.peerKind === "end";
    if (!aIsEnd && !bIsEnd) return; // "wall" (bok-k-boku) - nesplnuje definici spoje, nepocitat
    const h = aIsEnd ? pa : pb; // pri obou "end" (celo-na-celo) kredit jen jednou, na A
    h.jointCount += 1;
    if (aIsEnd && j.info.myConnIdx != null) pa.hiddenEndConn.add(j.info.myConnIdx);
    if (bIsEnd && j.info.otherConnIdx != null) pb.hiddenEndConn.add(j.info.otherConnIdx);
    if (j.info.myConnIdx != null) pa.usedConn.add(j.info.myConnIdx);
    if (j.info.otherConnIdx != null) pb.usedConn.add(j.info.otherConnIdx);
  });

  const sumJc = [...perPart.values()].reduce((s, p) => s + p.jointCount, 0);
  console.log("");
  console.log(`--apply: pripraveno k zapisu, ${perPart.size} dilu ma alespon 1 spoj, soucet jointCount=${sumJc} (ocekavano ${joints.length})`);

  const pymysql_write = () => {
    const { execSync } = require("child_process");
    const payload = {};
    perPart.forEach((v, idx) => {
      payload[idx] = {
        lic_peers: [...v.licPeers].sort((a, b) => a - b),
        joint_count: v.jointCount,
        hidden_end_conn: [...v.hiddenEndConn].sort(),
        used_conn: [...v.usedConn].sort(),
      };
    });
    fs.writeFileSync(path.join(SCRATCH, "joint_write_346.json"), JSON.stringify(payload));
    console.log("Zapsano do", path.join(SCRATCH, "joint_write_346.json"), "- pouzij scripts/tmp_2026-09-13_bot8_joint_write_346.py pro zapis do DB.");
  };
  pymysql_write();
}
