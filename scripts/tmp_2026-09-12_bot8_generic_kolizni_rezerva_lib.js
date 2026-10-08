// Genericka, datove-rizena implementace shape_geometry_methods.id=11
// "prepocet-kolizni-rezervy-existujici-sestavy" - pouzitelna napric CELOU
// "Proace" rodinou (2026-08-31_proace_full_build.js + proace_leg_builder.js
// a pripbuznymi jednoduchymi 2-noha variantami bez vyrezu), NEZAVISLE na
// konkretnim poctu noh/sloupcu/nazvoslovi (sloupecN/patroN vs colN/pN,
// "zadni-svislice" vs "zadni-svislice-dolni").
//
// Princip (misto natvrdo psanych Z-hodnot pro kazdou sestavu jako v drivejsich
// K-075/K-118 skriptech): topologie se ODVODI PRIMO Z DAT teto konkretni
// sestavy (role + Z-klastry), pak se overi self-checkem proti uz Robertem
// schvalenemu paru K-075 279(pred)->340(po) - teprve po zelenem self-checku
// se smi pouzit na novou sestavu.
//
// KLICOVE PRAVIDLO (empiricky potvrzeno na VSECH dosud zpracovanych parech
// K-075/K-118 aug 2026-09-12, viz AGENTS_LOG): noha s NEJNIZSIM (nejvic
// zapornym) Z je VZDY ta "u prepazky" (leg0/noha0) - dostava CELE deltaZ.
// Ostatni nohy deltaZ NEDOSTAVAJI (bez ohledu na typ plna/vyrezova) - jen
// vyrezove z nich dostavaji deltaY. Potvrzeno i rozsahem car_body B.glb
// Z-hranic (noha0 vzdy nejblize/uvnitr Z-rozsahu B.glb, viz krok "over
// nearWall" nize) napric vsemi 13 timto skriptem zpracovavanymi modely.

const fs = require("fs");
const THREE = require("three");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const MK = require("/opt/konfigurator/scripts/2026-09-11_mesh_kolize_lib.js");

const KAT = "/opt/konfigurator/webapp/katalog/";
const near = (a, b, eps) => Math.abs(a - b) < eps;

const VYREZ_ROLES = new Set(["sloupek-pred-podbehem", "zadni-svislice-nad-zarezem", "pricka-uzavreni-vyrezu"]);

// === 1) TOPOLOGIE Z DAT ===
function detectTopology(parts, T) {
  const half = T / 2;
  // a) legy: distinct Z klastry z "predni-svislice" (KAZDA noha, plna i vyrezova, ji ma - viz proace_leg_builder.js)
  const psZ = parts.filter(p => p.role === "predni-svislice").map(p => p.position[2]).sort((a, b) => a - b);
  const legZ = [];
  for (const z of psZ) { if (!legZ.length || Math.abs(z - legZ[legZ.length - 1]) > 5) legZ.push(z); }
  if (legZ.length < 2) throw new Error(`detectTopology: nalezeno jen ${legZ.length} noh (ocekavano >=2) - zkontroluj roli 'predni-svislice'.`);

  const legs = legZ.map((z, i) => {
    const vyrezParts = parts.filter(p => VYREZ_ROLES.has(p.role) && near(p.position[2], z, 2));
    const isVyrez = vyrezParts.length > 0;
    let oldYnew = null;
    if (isVyrez) {
      const sloupek = parts.find(p => p.role === "sloupek-pred-podbehem" && near(p.position[2], z, 2));
      const svisl = parts.find(p => p.role === "zadni-svislice-nad-zarezem" && near(p.position[2], z, 2));
      if (sloupek) {
        const topSloupek = sloupek.position[1] + sloupek.scale[1] * 1000 / 2;
        oldYnew = topSloupek;
        if (svisl) {
          const botSvisl = svisl.position[1] - svisl.scale[1] * 1000 / 2;
          if (Math.abs(topSloupek - botSvisl) > 0.05) {
            throw new Error(`detectTopology: noha Z=${z.toFixed(2)} - svar sloupek/svislice nesedi (${topSloupek.toFixed(3)} vs ${botSvisl.toFixed(3)}) - nedomnivat se, opravit rucne.`);
          }
        }
      }
    }
    return { idx: i, z, type: isVyrez ? "vyrez" : "plain", oldYnew, isNearWall: i === 0 };
  });

  // b) sloupce: kazdy unikatni "<prefix>" z role /^(nosnik|spojnice|eurobox)-(\w+)-(?:p|patro)(\d+)$/
  const colRe = /^(nosnik|spojnice|eurobox)-(\w+)-(?:p|patro)(\d+)$/;
  const colZ = {};
  for (const p of parts) {
    const m = colRe.exec(p.role || "");
    if (!m) continue;
    const prefix = m[2];
    (colZ[prefix] = colZ[prefix] || []).push(p.position[2]);
  }
  const colEntries = Object.entries(colZ).map(([prefix, zs]) => ({ prefix, z: zs.reduce((a, b) => a + b, 0) / zs.length }));
  colEntries.sort((a, b) => a.z - b.z);
  if (colEntries.length !== legs.length - 1) {
    throw new Error(`detectTopology: ${colEntries.length} sloupcu, ale ${legs.length} noh (ocekavano N-1 sloupcu) - topologie neni jednoduchy retezec, over rucne.`);
  }
  const columns = colEntries.map((c, i) => ({ prefix: c.prefix, legAIdx: i, legBIdx: i + 1, z: c.z }));
  for (const col of columns) {
    if (!(col.z > legs[col.legAIdx].z && col.z < legs[col.legBIdx].z)) {
      throw new Error(`detectTopology: sloupec ${col.prefix} Z=${col.z.toFixed(1)} nelezi mezi ocekavanymi nohama ${legs[col.legAIdx].z.toFixed(1)}..${legs[col.legBIdx].z.toFixed(1)} - poradi neni sekvencni, over rucne.`);
    }
  }

  return { legs, columns, colRe };
}

// === 2) TRANSFORM (kroky 3-6 procedury) ===
function shiftVyrezPart(p, role, oldYnew, deltaY, T) {
  const [x, y, z] = p.position;
  const newYnew = oldYnew + deltaY;
  const half = T / 2;
  if (role === "sloupek-pred-podbehem") {
    const oldH = p.scale[1] * 1000, floorY = y - oldH / 2, newH = newYnew - floorY;
    return { ...p, position: [x, floorY + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "zadni-svislice-nad-zarezem") {
    const oldH = p.scale[1] * 1000, topY = y + oldH / 2, newH = topY - newYnew;
    return { ...p, position: [x, newYnew + newH / 2, z], scale: [p.scale[0], newH / 1000, p.scale[2]] };
  }
  if (role === "pricka-uzavreni-vyrezu") {
    return { ...p, position: [x, newYnew + half, z] };
  }
  throw new Error("neznama vyrez role: " + role);
}

function transformAssembly(parts, topo, DELTA_Z, DELTA_Y, T) {
  const { legs, columns, colRe } = topo;
  const NEAR_LEG_TOL = 60;
  const log = { legRigid: 0, legUnaffected: 0, vyrezShift: 0, uhelnikShift: 0, uhelnikUnaffected: 0,
    colBeam: 0, colSpojEnd: 0, colSpojMid: 0, colUnaffected: 0, carBody: 0, dorovnani: 0, other: 0 };
  const out = parts.map(orig => {
    const p = JSON.parse(JSON.stringify(orig));
    const role = p.role || "";
    const [x, y, z] = p.position;

    if (String(p.part_id || "").startsWith("car_body_")) { log.carBody++; return p; }

    // uhelnik-noha<N>
    let m = /^uhelnik-noha(\d+)$/.exec(role);
    if (m) {
      const leg = legs[Number(m[1])];
      if (!leg) throw new Error(`uhelnik odkazuje na neznamou nohu ${role}`);
      let ny = y, moved = false;
      if (leg.type === "vyrez" && (near(y, leg.oldYnew, 3) || near(y, leg.oldYnew + 30, 3))) { ny = y + DELTA_Y; moved = true; }
      const nz = leg.isNearWall ? z + DELTA_Z : z;
      if (moved || leg.isNearWall) log.uhelnikShift++; else log.uhelnikUnaffected++;
      return { ...p, position: [x, ny, nz] };
    }

    // sloupec role (nosnik/spojnice/eurobox)
    m = colRe.exec(role);
    if (m) {
      const prefix = m[2];
      const col = columns.find(c => c.prefix === prefix);
      if (!col) throw new Error(`sloupec ${prefix} neznamy`);
      const legA = legs[col.legAIdx], legB = legs[col.legBIdx];
      const kind = m[1]; // nosnik|spojnice|eurobox
      if (!legA.isNearWall) { log.colUnaffected++; return p; } // sloupec se nedotyka noha0 -> Z beze zmeny (dorovnani se resi zvlast nize)
      if (kind === "eurobox") { log.colBeam++; return { ...p, position: [x, y, z + DELTA_Z / 2] }; }
      if (kind === "nosnik") {
        const newLenMm = p.scale[1] * 1000 - DELTA_Z;
        log.colBeam++;
        return { ...p, position: [x, y, z + DELTA_Z / 2], scale: [p.scale[0], newLenMm / 1000, p.scale[2]] };
      }
      // spojnice: 3 varianty (blizko legA/blizko legB/uprostred)
      const dA = Math.abs(z - legA.z), dB = Math.abs(z - legB.z);
      if (dA < NEAR_LEG_TOL) { log.colSpojEnd++; return { ...p, position: [x, y, z + DELTA_Z] }; }
      if (dB < NEAR_LEG_TOL) { log.colSpojEnd++; return p; }
      log.colSpojMid++; return { ...p, position: [x, y, z + DELTA_Z / 2] };
    }

    // vyrezova trojice (na libovolne noze, vc. pripadne noha0 - Z i Y nezavisle)
    if (VYREZ_ROLES.has(role)) {
      const leg = legs.find(l => near(z, l.z, 2));
      if (!leg) throw new Error(`vyrez cast role=${role} Z=${z} nelezi na zadne zname noze`);
      if (leg.type !== "vyrez") throw new Error(`vyrez cast role=${role} na noze idx=${leg.idx} ktera neni klasifikovana jako vyrezova`);
      let sp = shiftVyrezPart(p, role, leg.oldYnew, DELTA_Y, T);
      if (leg.isNearWall) sp = { ...sp, position: [sp.position[0], sp.position[1], sp.position[2] + DELTA_Z] };
      log.vyrezShift++;
      return sp;
    }

    // zbytek = leg-frame role (predni-svislice/cap/spojnice-dolni/spojnice-horni(-uzavreni)/
    // zadni-svislice(-dolni)/zaslepka-*) - Z-match na nejblizsi nohu
    const leg = legs.find(l => near(z, l.z, 2));
    if (leg) {
      if (leg.isNearWall) { log.legRigid++; return { ...p, position: [x, y, z + DELTA_Z] }; }
      log.legUnaffected++; return p;
    }
    log.other++;
    return p;
  });

  // krok 4/5/6: dorovnani luzek po sloupcich, kde bounding noha je vyrezova
  for (const col of columns) {
    const legA = legs[col.legAIdx], legB = legs[col.legBIdx];
    const vyrezLegs = [legA, legB].filter(l => l.type === "vyrez");
    if (!vyrezLegs.length) continue;
    const limitingYnew = Math.max(...vyrezLegs.map(l => l.oldYnew + DELTA_Y));
    const rx = new RegExp(`^nosnik-${col.prefix}-(?:p|patro)(\\d+)$`);
    const floors = new Map();
    for (const p of out) {
      const mm = rx.exec(p.role || "");
      if (!mm) continue;
      const i = Number(mm[1]);
      if (!floors.has(i)) floors.set(i, []);
      floors.get(i).push(p);
    }
    if (!floors.size) continue;
    const N = Math.max(...floors.keys()) + 1;
    const p0 = floors.get(0)[0];
    const bottomEdge = p0.position[1] - T / 2;
    const missing = limitingYnew - bottomEdge;
    if (missing <= 0.01) continue;
    const shiftFor = i => (N === 1 ? missing : missing * (N - 1 - i) / (N - 1));
    const rx2 = new RegExp(`^(nosnik|spojnice|eurobox)-${col.prefix}-(?:p|patro)(\\d+)$`);
    for (const p of out) {
      const mm = rx2.exec(p.role || "");
      if (!mm) continue;
      const i = Number(mm[2]);
      const sh = shiftFor(i);
      if (sh === 0) continue;
      p.position = [p.position[0], p.position[1] + sh, p.position[2]];
      log.dorovnani++;
    }
  }

  return { parts: out, log };
}

// === 3) OVERENI (krok 7): SAT vs realna GLB karoserie + presna mezera + self-kolize ===
function wallMeshes(carBodyBase) {
  const L = parseGlbMesh(KAT + carBodyBase + "_L.glb");
  const Rd = parseGlbMesh(KAT + carBodyBase + "_R_D.glb");
  const B = parseGlbMesh(KAT + carBodyBase + "_B.glb");
  [L, Rd, B].forEach(m => { m.updateMatrixWorld(true); m.geometry.computeBoundsTree(); });
  return [L, Rd, B];
}
function meshWorldEdges(mesh, maxEdges) {
  const geo = mesh.geometry, pos = geo.attributes.position, idx = geo.index;
  const triCount = idx ? idx.count / 3 : pos.count / 3;
  const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
  const edges = [];
  const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
  for (let t = 0; t < triCount; t += step) {
    let ia, ib, ic;
    if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
    else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
    vA.fromBufferAttribute(pos, ia).applyMatrix4(mesh.matrixWorld);
    vB.fromBufferAttribute(pos, ib).applyMatrix4(mesh.matrixWorld);
    vC.fromBufferAttribute(pos, ic).applyMatrix4(mesh.matrixWorld);
    edges.push([vA.clone(), vB.clone()], [vB.clone(), vC.clone()], [vC.clone(), vA.clone()]);
  }
  return edges;
}
function isKnownNesting(a, b) {
  const roles = [a.role, b.role];
  const has = re => roles.some(r => re.test(r || ""));
  if (has(/^eurobox-/) && has(/^(nosnik|spojnice)-/)) return true;
  if (has(/^zaslepka/) && has(/^(predni-svislice|cap|zadni-svislice|sloupek-pred-podbehem)/)) return true;
  if (has(/^logo-ochrana-vypln-/) && has(/^(predni-svislice|zadni-svislice|sloupek-pred-podbehem|cap)/)) return true;
  return false;
}

function verifyAssembly(parts, carBodyBase, topo, DELTA_Y, T, precomputedWalls) {
  const walls = precomputedWalls || wallMeshes(carBodyBase);
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;
  function collidesWithWalls(mesh) {
    for (const [p0, p1] of meshWorldEdges(mesh, 400)) {
      const dir = p1.clone().sub(p0), dist = dir.length();
      if (dist < 1e-6) continue;
      dir.normalize(); raycaster.set(p0, dir); raycaster.far = dist;
      if (raycaster.intersectObjects(walls, false).length) return true;
    }
    return false;
  }
  const measurable = parts.filter(p => !R.jeKaroserie(p.part_id) && !String(p.role || "").startsWith("kontrolni-pomucka"));
  const glbCache = new Map();
  function meshOf(p) {
    const gp = R.glbPath(p.part_id);
    if (!gp) throw new Error(`glb_resolver nenasel GLB pro part_id=${p.part_id} (role=${p.role})`);
    let base = glbCache.get(gp);
    if (!base) { base = parseGlbMesh(gp); glbCache.set(gp, base); }
    const mesh = base.clone(); mesh.geometry = base.geometry;
    mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
    mesh.updateMatrixWorld(true);
    return mesh;
  }

  let satCollisions = 0; const satHits = [];
  for (const p of measurable) {
    const mesh = meshOf(p);
    if (collidesWithWalls(mesh)) { satCollisions++; satHits.push({ role: p.role, part_id: p.part_id, position: p.position }); }
  }

  // presna mezera na kazdem vyrezovem svaru: spáruj sloupek<->svislice podle
  // nejblizsi Z k sobe navzajem (v transformovanych datech, robustni i kdyz
  // leg0 pripad by Z posunul o DELTA_Z stejne u obou dilu daneho svaru).
  let seamFail = 0; const seamReport = [];
  const pairs = [];
  {
    const candSloupek = parts.filter(p => p.role === "sloupek-pred-podbehem").slice();
    const candSvisl = parts.filter(p => p.role === "zadni-svislice-nad-zarezem").slice();
    const usedV = new Set();
    for (const s of candSloupek) {
      let bestJ = -1, bestD = Infinity;
      for (let j = 0; j < candSvisl.length; j++) {
        if (usedV.has(j)) continue;
        const d = Math.abs(candSvisl[j].position[2] - s.position[2]);
        if (d < bestD) { bestD = d; bestJ = j; }
      }
      if (bestJ >= 0 && bestD < 5) { usedV.add(bestJ); pairs.push([s, candSvisl[bestJ]]); }
    }
  }
  function box3World(p) {
    const gp = R.glbPath(p.part_id);
    let base = glbCache.get(gp);
    if (!base) { base = parseGlbMesh(gp); glbCache.set(gp, base); }
    const mesh = base.clone(); mesh.geometry = base.geometry;
    mesh.position.set(...p.position); mesh.quaternion.set(...p.quaternion); mesh.scale.set(...p.scale);
    mesh.updateMatrixWorld(true);
    return new THREE.Box3().setFromObject(mesh);
  }
  for (const [sloupek, svisl] of pairs) {
    const bS = box3World(sloupek), bV = box3World(svisl);
    const gap = bV.min.y - bS.max.y;
    seamReport.push({ z: sloupek.position[2], gap });
    if (Math.abs(gap) > 0.02) seamFail++;
  }
  // dorovnani seam (nejnizsi patro kazdeho sloupce vs limitujici Y_new)
  for (const col of topo.columns) {
    const legA = topo.legs[col.legAIdx], legB = topo.legs[col.legBIdx];
    const vyrezLegs = [legA, legB].filter(l => l.type === "vyrez");
    if (!vyrezLegs.length) continue;
    const limitingYnew = Math.max(...vyrezLegs.map(l => l.oldYnew + DELTA_Y));
    const p0 = parts.find(p => new RegExp(`^nosnik-${col.prefix}-(?:p|patro)0$`).test(p.role || ""));
    if (!p0) continue;
    const bottom = p0.position[1] - T / 2;
    const gap = bottom - limitingYnew;
    seamReport.push({ col: col.prefix, gap });
    if (gap < -0.02) seamFail++;
  }

  // self-kolize
  const measurableSelf = measurable.filter(p => !String(p.part_id || "").startsWith("car_body_"));
  const dils = measurableSelf.map(p => ({ p, D: MK.dilVeSvete(R.glbPath(p.part_id), p, parseGlbMesh) }));
  let selfCollisions = 0; const selfHits = [];
  for (let i = 0; i < dils.length; i++) {
    for (let j = i + 1; j < dils.length; j++) {
      const A = dils[i], B = dils[j];
      const bov = MK.prekryvBoxu(A.D.box, B.D.box);
      if (Math.min(...bov) <= 0.05) continue;
      // znama vnorovaci geometrie se presne NEMERI (usetri drahy kolize() vypocet
      // pro casty pripad eurobox<->kolejnicka/zaslepka<->profil, ktere se stejne
      // vzdy zahodi) - jen SKUTECNE neznama kandidatni dvojice jdou do presneho testu.
      if (isKnownNesting(A.p, B.p)) continue;
      const k = MK.kolize(A.D, B.D, 0.05, false);
      if (!k.koliduje) continue;
      const vol = k.oblast[0] * k.oblast[1] * k.oblast[2];
      if (vol <= 2000) continue;
      selfCollisions++;
      selfHits.push({ a: A.p.role, aId: A.p.part_id, b: B.p.role, bId: B.p.part_id, oblast: k.oblast });
    }
  }

  return {
    measured: measurable.length, satCollisions, satHits, seamFail, seamReport,
    selfCollisions, selfHits,
    verdict: (satCollisions === 0 && seamFail === 0 && selfCollisions === 0) ? "OK" : "BLOCKED",
  };
}

module.exports = { detectTopology, transformAssembly, verifyAssembly, wallMeshes, VYREZ_ROLES };
