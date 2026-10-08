// Finalni oprava dvirek 40x20 (id=384):
// 1) vyskovy rozvrh POCITA s piny (Object_2/4/5/7, "cepy prilnute k
//    hornimu 20x20 profilu shora") - horni pricel se posune NIZ, aby
//    piny nad ni sahaly presne ke stropu (1189.5), ne pricel sama.
// 2) odstranit dily horniho bloku, ktere dvirkum zavazi (Robert: "je
//    potreba odstranit", uz ne "neresit zatim"): podelnik-celni-police-1,
//    vypln-police-1, vypln-celo-1-b.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const d = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/a384_v7.json", "utf8"));

const Z_LO = -881.5, Z_HI = -51.5, X_MID = -387.5;
const Y_LO = 996.5;      // spodni pasmo top (nezmeneno)
const Y_CEIL = 1189.5;   // strop (horni ram bottom - 0.5mm, nezmeneno)
const PIN_EXTRA = 164.62152 - 143.61803; // = 21.00349mm, zmereno z FBX (Object_2 top - top-pricel top)

const railTopTop = Y_CEIL - PIN_EXTRA;           // 1168.497 - kam sahat horni hrana horniho pricle
const railTopCenter = railTopTop - 10;           // profil_20x20, polovina 20mm
const railBottomCenter = Y_LO + 20;              // profil_20x40, nezmeneno
const panelYLo = Y_LO + 40;                      // 1036.5, horni hrana spodni pricle
const panelYHi = railTopTop - 20;                // spodni hrana horni pricle
const panelH = panelYHi - panelYLo;

console.log("railTopTop=", railTopTop.toFixed(3), " panelH=", panelH.toFixed(3));

function basisQuat(xAxis, yAxis, zAxis) {
  const m = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
  if (Math.abs(m.determinant() - 1) > 0.01) throw new Error("det " + m.determinant());
  return new THREE.Quaternion().setFromRotationMatrix(m);
}
const qRail = basisQuat(new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0));
let qPanel;
try { qPanel = basisQuat(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)); }
catch (e) { qPanel = basisQuat(new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)); }
function endCapQuat(dir) { return basisQuat(new THREE.Vector3(dir, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, dir)); }
const qCapNeg = endCapQuat(1), qCapPos = endCapQuat(-1);

const railBottom = { role: "dvirka-40-20-pricel-spodni", part_id: "profil_20x40", position: [X_MID, railBottomCenter, (Z_LO + Z_HI) / 2], quaternion: [qRail.x, qRail.y, qRail.z, qRail.w], scale: [1, (Z_HI - Z_LO) / 1000, 1] };
const railTop = { role: "dvirka-40-20-pricel-horni", part_id: "profil_20x20", position: [X_MID, railTopCenter, (Z_LO + Z_HI) / 2], quaternion: [qRail.x, qRail.y, qRail.z, qRail.w], scale: [1, (Z_HI - Z_LO) / 1000, 1] };
const panel = { role: "dvirka-40-20-vyplen", part_id: "product_3939", position: [X_MID, (panelYLo + panelYHi) / 2, (Z_LO + Z_HI) / 2], quaternion: [qPanel.x, qPanel.y, qPanel.z, qPanel.w], scale: [(Z_HI - Z_LO) / 1000, panelH / 1000, 1] };
const capTop1 = { role: "dvirka-40-20-zaslepka-horni-a", part_id: "product_3070", position: [X_MID, railTopCenter, Z_LO], quaternion: [qCapNeg.x, qCapNeg.y, qCapNeg.z, qCapNeg.w], scale: [1, 1, 1] };
const capTop2 = { role: "dvirka-40-20-zaslepka-horni-b", part_id: "product_3070", position: [X_MID, railTopCenter, Z_HI], quaternion: [qCapPos.x, qCapPos.y, qCapPos.z, qCapPos.w], scale: [1, 1, 1] };
const capBot1 = { role: "dvirka-40-20-zaslepka-spodni-a", part_id: "product_3150", position: [X_MID, railBottomCenter, Z_LO], quaternion: [qCapNeg.x, qCapNeg.y, qCapNeg.z, qCapNeg.w], scale: [1, 1, 1] };
const capBot2 = { role: "dvirka-40-20-zaslepka-spodni-b", part_id: "product_3150", position: [X_MID, railBottomCenter, Z_HI], quaternion: [qCapPos.x, qCapPos.y, qCapPos.z, qCapPos.w], scale: [1, 1, 1] };
const postA = { role: "dvirka-40-20-sloupek-a", part_id: "profil_20x20", position: [X_MID, (panelYLo + panelYHi) / 2, Z_LO + 10], quaternion: [0, 0, 0, 1], scale: [1, panelH / 1000, 1] };
const postB = { role: "dvirka-40-20-sloupek-b", part_id: "profil_20x20", position: [X_MID, (panelYLo + panelYHi) / 2, Z_HI - 10], quaternion: [0, 0, 0, 1], scale: [1, panelH / 1000, 1] };
// "neznamy hardware" (piny+cerne zakladny+modre klipy) - cely blok posunut tak, aby jeho VRSEK (byl na 164.62 v puvodni referenci, pri centrovani na stred cele 17-mesh sestavy) sedel presne na Y_CEIL
const scaleX = (Z_HI - Z_LO) / 990.25;
const hw = { role: "dvirka-40-20-hardware-neznamy", part_id: "dvirka_40_20_test", position: [X_MID, railTopTop + PIN_EXTRA / 2, (Z_LO + Z_HI) / 2], quaternion: [0.5, 0.5, 0.5, -0.5], scale: [scaleX, 1, 1] };

const NEW_PARTS = [railBottom, railTop, panel, capTop1, capTop2, capBot1, capBot2, postA, postB, hw];

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
for (const p of NEW_PARTS) { const b = worldBox(p); console.log(p.role.padEnd(30), "Y=[" + b.min.y.toFixed(1) + "," + b.max.y.toFixed(1) + "]"); }

function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
function scan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map(); let n = 0;
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.set(m[i].p.role + "|" + m[j].p.role, [ox, oy, oz]); }
  }
  return { n, pairs };
}

const REMOVE_ROLES = new Set(["podelnik-celni-police-1", "vypln-police-1", "vypln-celo-1-b"]);
const removed = d.parts.filter(p => REMOVE_ROLES.has(p.role));
console.log("\nodstranuji", removed.length, "dilu horniho bloku:", removed.map(p => p.role).join(", "));
const kept = d.parts.filter(p => !REMOVE_ROLES.has(p.role) && !(p.role || "").startsWith("dvirka-"));
const after = kept.concat(NEW_PARTS);

const before = scan(kept);
const afterScan = scan(after);
const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
console.log("dilu:", d.parts.length, "->", after.length, " kolize bez dvirek=" + before.n + " s dvirky=" + afterScan.n + " nove_pary=" + newPairs.length);
for (const k of newPairs) console.log("  ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));

fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/a384_v7_final.json", JSON.stringify(after));
console.log("ulozeno");
