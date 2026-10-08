// Dvirka 40x20 - PRAVE stavba z NASICH katalogovych dilu (Robertovo
// zadani: "nacist jako sadu z nasich profilu a desku sily 6mm, vse
// separatne, a pak zpatky skladat" - misto jednoho vypaleneho blob GLB).
// Sada: profil_20x40 (spodni pricel), profil_20x20 (horni pricel),
// product_3939/deska_mdf_seda_8 (vyplnova deska mezi nimi, roztahuje se
// dle prostoru), + zaslepky na obou koncich obou profilu (product_3150
// pro 20x40, product_3070 pro 20x20 - "zaslepky ve scene mame").
// Drobny hardware (chrom cepy, modre klipy z FBX) VYNECHAN - "nechat ve
// scene jako nezname", reseno zvlast (samostatny "unknown" mesh), NE tady.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const KAT = "/opt/konfigurator/webapp/katalog/";

function basisQuat(xAxis, yAxis, zAxis) {
  const m = new THREE.Matrix4().makeBasis(xAxis, yAxis, zAxis);
  const det = m.determinant();
  if (Math.abs(det - 1) > 0.01) throw new Error("spatny determinant " + det);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}
function realBox(partId, pos, quat, scale) {
  const mesh = parseGlbMesh(KAT + partId + ".glb");
  mesh.position.set(...pos); mesh.quaternion.set(quat.x, quat.y, quat.z, quat.w); mesh.scale.set(...scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}

// === cilovy prostor (dohodnuto: 1.+2. pasmo dohromady) ===
const Z_LO = -881.5, Z_HI = -51.5, LEN = Z_HI - Z_LO; // 830mm
const Y_LO = 996.5, Y_HI = 1189.5; // spodni pasmo top -> horni ram bottom (0.5mm rezerva u horniho ramu jiz zapocitana v 1189.5)
const X_MID = -387.5; // osa zavesu

// --- rotace profilu: lokalni Y(delka)->svet Z, lokalni X(20mm)->svet X, lokalni Z(druhy rozmer)->svet Y ---
const qRail = basisQuat(new THREE.Vector3(-1, 0, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0));

// spodni pricel: profil_20x40 (40mm svisle), horni hrana = Y_LO+40
const railBottom = {
  part_id: "profil_20x40", role: "dvirka-40-20-pricel-spodni",
  position: [X_MID, Y_LO + 20, (Z_LO + Z_HI) / 2],
  quaternion: [qRail.x, qRail.y, qRail.z, qRail.w],
  scale: [1, LEN / 1000, 1],
};
// horni pricel: profil_20x20 (20mm svisle), spodni hrana = Y_HI-20
const railTop = {
  part_id: "profil_20x20", role: "dvirka-40-20-pricel-horni",
  position: [X_MID, Y_HI - 10, (Z_LO + Z_HI) / 2],
  quaternion: [qRail.x, qRail.y, qRail.z, qRail.w],
  scale: [1, LEN / 1000, 1],
};
console.log("railBottom bbox:", realBox(railBottom.part_id, railBottom.position, qRail, railBottom.scale));

// --- panel (deska_mdf_seda_8): lokalni X(1000)->svet Z (delka), lokalni Y(1000)->svet Y (vyska), lokalni Z(8mm)->svet X (tloustka) ---
let qPanel;
try { qPanel = basisQuat(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)); }
catch (e) { qPanel = basisQuat(new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)); }

const railBottomBox = realBox(railBottom.part_id, railBottom.position, qRail, railBottom.scale);
const railTopBox = realBox(railTop.part_id, railTop.position, qRail, railTop.scale);
const panelYLo = railBottomBox.max.y, panelYHi = railTopBox.min.y;
const panelH = panelYHi - panelYLo;
const panel = {
  part_id: "product_3939", role: "dvirka-40-20-vyplen",
  position: [X_MID, (panelYLo + panelYHi) / 2, (Z_LO + Z_HI) / 2],
  quaternion: [qPanel.x, qPanel.y, qPanel.z, qPanel.w],
  scale: [LEN / 1000, panelH / 1000, 1],
};
console.log("panel Y rozsah:", panelYLo.toFixed(2), "-", panelYHi.toFixed(2), " vyska=", panelH.toFixed(2));

// --- zaslepky na 4 koncich (2x kazdy pricel) ---
// product_3070 (20x20, pivot na vnejsi cele, lokalni Z 0..7) / product_3150 (20x40) - stejna konvence.
// Otoceni: lokalni Z(hloubka zaslepky, sm. VEN z profilu) musi smerovat podel sveta Z, VEN z pricle.
function endCapQuat(outwardZ) {
  // lokalni X->svet X*outwardZ, lokalni Y-> svet Y, lokalni Z -> svet Z*outwardZ (ven) - obraceni DVOU os
  // (X i Z), aby determinant zustal +1 (obraceni jedne jediné osy je zrcadleni, ne rotace).
  return basisQuat(new THREE.Vector3(outwardZ, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, outwardZ));
}
// POZOR (zjisteno mereni - puvodni "ven" smer strkal zaslepku 7mm ZA
// hranici 2mm mezery, primo do nohy): zaslepka je "zatka" co jde DOVNITR
// dutiny profilu, ne flanz co trci ven - jeji lokalni +Z proto musi mirit
// SMEREM DO PRICLE (opacne, nez puvodni pokus).
const qCapNeg = endCapQuat(1);  // na strane Z_LO smeruje dovnitr = +Z
const qCapPos = endCapQuat(-1); // na strane Z_HI smeruje dovnitr = -Z

const capTop1 = { part_id: "product_3070", role: "dvirka-40-20-zaslepka-horni-a", position: [X_MID, railTop.position[1], Z_LO], quaternion: [qCapNeg.x, qCapNeg.y, qCapNeg.z, qCapNeg.w], scale: [1, 1, 1] };
const capTop2 = { part_id: "product_3070", role: "dvirka-40-20-zaslepka-horni-b", position: [X_MID, railTop.position[1], Z_HI], quaternion: [qCapPos.x, qCapPos.y, qCapPos.z, qCapPos.w], scale: [1, 1, 1] };
const capBot1 = { part_id: "product_3150", role: "dvirka-40-20-zaslepka-spodni-a", position: [X_MID, railBottom.position[1], Z_LO], quaternion: [qCapNeg.x, qCapNeg.y, qCapNeg.z, qCapNeg.w], scale: [1, 1, 1] };
const capBot2 = { part_id: "product_3150", role: "dvirka-40-20-zaslepka-spodni-b", position: [X_MID, railBottom.position[1], Z_HI], quaternion: [qCapPos.x, qCapPos.y, qCapPos.z, qCapPos.w], scale: [1, 1, 1] };

const NEW_PARTS = [railBottom, railTop, panel, capTop1, capTop2, capBot1, capBot2];

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
for (const p of NEW_PARTS) {
  const b = worldBox(p);
  console.log(p.role.padEnd(30), "X=[" + b.min.x.toFixed(1) + "," + b.max.x.toFixed(1) + "]", "Y=[" + b.min.y.toFixed(1) + "," + b.max.y.toFixed(1) + "]", "Z=[" + b.min.z.toFixed(1) + "," + b.max.z.toFixed(1) + "]");
}

// === nacti aktualni 384, odeber stary monoliticky "dvirka-police-1-test", pridej novych 7 dilu, over kolize ===
const d = JSON.parse(fs.readFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/a384_v2.json", "utf8"));
function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
function scan(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) || (() => { const glb = R.glbPath(p.part_id); if (!glb) return null; const mesh = parseGlbMesh(glb); mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale); mesh.updateMatrixWorld(true); return new THREE.Box3().setFromObject(mesh); })() }));
  const pairs = new Map(); let n = 0;
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { n++; pairs.set(m[i].p.role + "|" + m[j].p.role, [ox, oy, oz]); }
  }
  return { n, pairs };
}
const kept = d.parts.filter(p => p.role !== "dvirka-police-1-test");
const after = kept.concat(NEW_PARTS);
const before = scan(kept);
const afterScan = scan(after);
const newPairs = [...afterScan.pairs.keys()].filter(k => !before.pairs.has(k));
console.log("\ndilu:", d.parts.length, "->", after.length, " kolize bez dvirek=" + before.n + " s dvirky=" + afterScan.n);
console.log("nove pary:", newPairs.length);
for (const k of newPairs) console.log("  ", k, JSON.stringify(afterScan.pairs.get(k).map(v => +v.toFixed(1))));

fs.writeFileSync("/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad/a384_v4_final.json", JSON.stringify(after));
console.log("\nulozeno pro zapis (bez ohledu na kolize - manualni posouzeni nasleduje)");
