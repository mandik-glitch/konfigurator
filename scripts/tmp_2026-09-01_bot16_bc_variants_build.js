// Bot16, 2026-09-01. B/C vyskove varianty euroboxu pro 4 jiz existujici
// sestavy (variant "A"): Berlingo id=95, Partner id=101, Trafic id=103,
// Caddy id=126. Nohy/nosniky/spojnice/zaslepky/car_body zustavaji ZCELA
// BEZE ZMENY (byte-identicke s variantou A) - meni se JEN ktery vyskovy
// produkt (product_3788/3793/3794/3795 = 120/170/220/270mm) sedi v kazdem
// jiz existujicim patre, a s tim spojena Y-pozice eurobxu.
//
// Klicovy empiricky fakt (overeno na vsech 4 existujicich sestavach, viz
// AGENTS_LOG.md): box_Y = rail_Y(patro) + K[vyska], kde K je KONSTANTA per
// vyska (nezavisla na sestave/rail_Y), protoze pochazi ze stejneho vzorce
// `targetYbottom - probe.box.min.y - 12` pouziteho pri puvodni stavbe (viz
// shape_geometry_methods.id=3, krok_4) - probe.box.min.y je vlastnost
// KONKRETNI GLB (pivotu dane vyskove varianty), ne rail_Y. Hodnoty K nize
// jsou tedy REALNE GLB-odvozene konstanty (ne hadane/hardcodovane napric
// vyskami - kazda vyska ma svou VLASTNI K, presne jak vyzaduje pravidlo
// "3793 ma jiny pivot"), jen ziskane z jiz existujicich overenych dat misto
// noveho volani parseGlbMesh - presnost overena na 6 des. mist napric 4
// sestavami a 9 ruznymi (rail_Y,vyska) kombinacemi.
const K = { 120: 584.086727, 170: -21.26733, 220: 696.567632, 270: 985.134522 };
const PID = { 120: "product_3788", 170: "product_3793", 220: "product_3794", 270: "product_3795" };
// DULEZITA PAST (viz KOMPONENTY_EUROBOXY.md "dulezita_vystraha_pivot"):
// product_3793 (170mm) ma JINY (symetricky) pivot nez ostatni 3 vysky
// (asymetricky pivot 3788/3794/3795) - X i Z centrovaci pozice pro 170mm
// jsou proto POSUNUTE o fixni konstantu oproti X/Z pouzitemu pro
// 120/220/270mm na STEJNEM slotu (X/Z pro 120/220/270 jsou vzajemne
// shodne, jen 170 se lisi). Konstanty overeny na 4 existujicich sestavach
// (9 vzorku), rozptyl <0.0001mm:
const DX170 = 142.966798; // X_170 = X_canonical(120/220/270) + DX170
const DZ170 = 392.557099; // Z_170 = Z_canonical(120/220/270) + DZ170 (per slot)

const fs = require("fs");
const THREE = require("three");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");
const MeshBVHLib = require("/opt/konfigurator/webapp/js/three-mesh-bvh.js");
THREE.BufferGeometry.prototype.computeBoundsTree = MeshBVHLib.computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = MeshBVHLib.disposeBoundsTree;
THREE.Mesh.prototype.raycast = MeshBVHLib.acceleratedRaycast;

const KAT = "/opt/konfigurator/webapp/katalog/";
const CARB = KAT + "car_bodies/";
function glbFor(part_id) {
  if (part_id === "Object_7") return KAT + "Object_7.glb";
  if (part_id === "product_3071") return KAT + "product_3071.glb";
  for (const h in PID) if (PID[h] === part_id) return KAT + `${part_id}.glb`;
  throw new Error("neznamy part_id " + part_id);
}
function meshOf(p) {
  const m = parseGlbMesh(glbFor(p.part_id));
  m.position.set(...p.position); m.quaternion.set(...p.quaternion); m.scale.set(...p.scale);
  m.updateMatrixWorld(true);
  return m;
}

function makeCollisionCtx(base) {
  const wallL = parseGlbMesh(base + "_L.glb");
  const wallR = parseGlbMesh(base + "_R_D.glb");
  const wallB = parseGlbMesh(base + "_B.glb");
  const wallMeshes = [wallL, wallR, wallB];
  wallMeshes.forEach(m => { m.updateMatrixWorld(true); m.geometry.computeBoundsTree(); });
  const raycaster = new THREE.Raycaster();
  raycaster.firstHitOnly = true;
  function collidesWithWalls(object3d) {
    object3d.updateMatrixWorld(true);
    let hit = false;
    object3d.traverse(n => {
      if (hit || !n.isMesh) return;
      const geo = n.geometry;
      const pos = geo && geo.attributes && geo.attributes.position;
      if (!pos) return;
      const idx = geo.index;
      const triCount = idx ? idx.count / 3 : pos.count / 3;
      const maxEdges = 300;
      const step = Math.max(1, Math.floor(triCount / (maxEdges / 3)));
      const vA = new THREE.Vector3(), vB = new THREE.Vector3(), vC = new THREE.Vector3();
      for (let t = 0; t < triCount && !hit; t += step) {
        let ia, ib, ic;
        if (idx) { ia = idx.getX(t * 3); ib = idx.getX(t * 3 + 1); ic = idx.getX(t * 3 + 2); }
        else { ia = t * 3; ib = t * 3 + 1; ic = t * 3 + 2; }
        vA.fromBufferAttribute(pos, ia).applyMatrix4(n.matrixWorld);
        vB.fromBufferAttribute(pos, ib).applyMatrix4(n.matrixWorld);
        vC.fromBufferAttribute(pos, ic).applyMatrix4(n.matrixWorld);
        for (const [p0, p1] of [[vA, vB], [vB, vC], [vC, vA]]) {
          const dir = p1.clone().sub(p0);
          const dist = dir.length();
          if (dist < 1e-6) continue;
          dir.normalize();
          raycaster.set(p0, dir);
          raycaster.far = dist;
          for (const wm of wallMeshes) {
            const hits = raycaster.intersectObject(wm, false);
            if (hits.length) { hit = true; break; }
          }
          if (hit) break;
        }
      }
    });
    return hit;
  }
  return { collidesWithWalls };
}

// ---------- vozidla ----------
const VEHICLES = {
  berlingo: { paId: 95, carBase: CARB + "Citroën_Berlingo_CI22_2021-", planB: [270, 220, 170, 120], planC: [220, 170, 170, 120] },
  partner: { paId: 101, carBase: CARB + "Peugeot_Partner_PE23_2021-", planB: [270, 220, 170, 120], planC: [220, 170, 170, 120] },
  trafic: { paId: 103, carBase: CARB + "Renault_Trafic_RE28_2026-", planB: [220, 220, 170, 120, 120], planC: [270, 170, 170, 120, 120] },
  caddy: { paId: 126, carBase: CARB + "Volkswagen_Caddy_VW31_2021-", planB: [270, 220, 120], planC: [220, 170, 120] },
};

function buildVariant(origParts, plan, capsCheck) {
  // seskup eurobox role podle (col,patro), zjisti puvodni railY a puvodni H (cap)
  const byLevel = {}; // patro -> {railY, entries:[idx...]}
  const railY = {};
  origParts.forEach((p, idx) => {
    const role = p.role || "";
    let m = role.match(/^nosnik-(?:sloupec(\d+)-patro(\d+)|col(\d+)-p(\d+))$/);
    if (m) { const pt = parseInt(m[2] ?? m[4]); if (!(pt in railY)) railY[pt] = p.position[1]; }
    m = role.match(/^eurobox-(?:sloupec(\d+)-patro(\d+)|col(\d+)-p(\d+))$/);
    if (m) { const pt = parseInt(m[2] ?? m[4]); (byLevel[pt] = byLevel[pt] || []).push(idx); }
  });
  const levels = Object.keys(byLevel).map(Number).sort((a, b) => a - b);
  if (levels.length !== plan.length) throw new Error(`ocekavano ${plan.length} pater, nalezeno ${levels.length}`);
  // cap kontrola: puvodni vyska na kazdem patre >= nova (nikdy nezvysovat nad puvodni rail-to-rail mezeru)
  const origHeightAt = {};
  levels.forEach(pt => {
    const idx0 = byLevel[pt][0];
    for (const h in PID) if (PID[h] === origParts[idx0].part_id) origHeightAt[pt] = parseInt(h);
  });
  levels.forEach((pt, i) => {
    if (plan[i] > origHeightAt[pt]) throw new Error(`patro${pt}: nova vyska ${plan[i]} > puvodni cap ${origHeightAt[pt]}`);
  });
  for (let i = 1; i < plan.length; i++) if (plan[i] > plan[i - 1]) throw new Error(`neni nerostouci: ${plan}`);
  const distinctCount = new Set(plan).size;
  if (distinctCount < 3) throw new Error(`min. 3 distinct vysky pozadovano, mam jen ${distinctCount}: ${plan}`);

  // kanonicka (nezavisla na vysce, krome 170) X/Z reference per slot - vezmi
  // z libovolneho patra teto sestavy, ktere v puvodnich datech NEMA vysku 170
  let canonRef = null;
  for (const pt of levels) {
    if (origHeightAt[pt] !== 170) { canonRef = byLevel[pt].map(idx => [origParts[idx].position[0], origParts[idx].position[2]]); break; }
  }
  if (!canonRef) throw new Error("zadne non-170 patro v puvodnich datech - nelze odvodit kanonicke X/Z");

  const newParts = origParts.map(p => ({ ...p, position: [...p.position], quaternion: [...p.quaternion], scale: [...p.scale] }));
  levels.forEach((pt, i) => {
    const h = plan[i];
    const ry = railY[pt];
    byLevel[pt].forEach((idx, j) => {
      const [baseX, baseZ] = canonRef[j];
      newParts[idx].part_id = PID[h];
      newParts[idx].position[0] = h === 170 ? baseX + DX170 : baseX;
      newParts[idx].position[2] = h === 170 ? baseZ + DZ170 : baseZ;
      newParts[idx].position[1] = ry + K[h];
    });
  });
  return { newParts, levels, origHeightAt, plan };
}

function verify(name, tag, allParts, carBase) {
  const errors = [];
  const meshes = allParts.filter(p => p.part_id !== "Object_11" && !/^car_body_/.test(p.part_id)).map(p => ({ p, m: meshOf(p) }));
  const boxes = meshes.map(({ p, m }) => { const b = new THREE.Box3().setFromObject(m); return { role: p.role, part_id: p.part_id, min: [b.min.x, b.min.y, b.min.z], max: [b.max.x, b.max.y, b.max.z] }; });

  boxes.forEach(b => {
    if ([...b.min, ...b.max].some(v => !Number.isFinite(v))) errors.push(`NaN box: ${b.role}`);
    if (b.max[0] <= b.min[0] || b.max[1] <= b.min[1] || b.max[2] <= b.min[2]) errors.push(`degenerovany box: ${b.role}`);
  });
  const legBoxes = boxes.filter(b => b.part_id === "Object_7" && /svislice/.test(b.role));
  if (legBoxes.length) {
    const floorY = Math.min(...legBoxes.map(b => b.min[1]));
    legBoxes.forEach(b => { if (b.min[1] - floorY > 5.01) errors.push(`svislice ${b.role} nezacina na podlaze`); });
  }
  const euroBoxes = boxes.filter(b => Object.values(PID).includes(b.part_id));
  euroBoxes.forEach(b => { const h = b.max[1] - b.min[1]; if (h < 100 || h > 300) errors.push(`eurobox ${b.role} podezrela vyska ${h.toFixed(1)}`); });

  const allZ = boxes.flatMap(b => [b.min[2], b.max[2]]), allX = boxes.flatMap(b => [b.min[0], b.max[0]]), allY = boxes.flatMap(b => [b.min[1], b.max[1]]);
  const dims = { lengthZ: Math.max(...allZ) - Math.min(...allZ), depthX: Math.max(...allX) - Math.min(...allX), heightY: Math.max(...allY) - Math.min(...allY) };
  if (dims.lengthZ <= 0 || dims.lengthZ > 6000) errors.push(`podezrela delka ${dims.lengthZ}`);
  if (dims.depthX <= 0 || dims.depthX > 500) errors.push(`podezrela hloubka ${dims.depthX}`);
  if (dims.heightY <= 0 || dims.heightY > 2000) errors.push(`podezrela vyska ${dims.heightY}`);

  // self-kolize: pouze eurobox<->eurobox mezi ruznymi patry (rail/leg nezmeneno,
  // uz overeno variantou A) - AABB overlap na vsech osach > 0.5mm bez ocekavane nesting vyjimky.
  const nonEuro = boxes.filter(b => !Object.values(PID).includes(b.part_id));
  const euroOnly = boxes.filter(b => Object.values(PID).includes(b.part_id));
  let unexpected = 0;
  for (let i = 0; i < euroOnly.length; i++) for (let j = i + 1; j < euroOnly.length; j++) {
    const A = euroOnly[i], B = euroOnly[j];
    const ox = Math.min(A.max[0], B.max[0]) - Math.max(A.min[0], B.min[0]);
    const oy = Math.min(A.max[1], B.max[1]) - Math.max(A.min[1], B.min[1]);
    const oz = Math.min(A.max[2], B.max[2]) - Math.max(A.min[2], B.min[2]);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) { unexpected++; errors.push(`neocekavana eurobox-eurobox kolize: ${A.role} <-> ${B.role}`); }
  }

  // car body kolize - jen eurobox mesh (nohy/rail beze zmeny, uz overeno u varianty A)
  const { collidesWithWalls } = makeCollisionCtx(carBase);
  const boxGroup = new THREE.Group();
  meshes.filter(x => Object.values(PID).includes(x.p.part_id)).forEach(x => boxGroup.add(x.m));
  boxGroup.updateMatrixWorld(true);
  const boxesCollide = collidesWithWalls(boxGroup);
  if (boxesCollide) errors.push("eurobox koliduje s karoserii");

  return { name, tag, dims, errors, ok: errors.length === 0, boxCount: boxes.length, boxesCollide, unexpectedSelfCollisions: unexpected };
}

const { execSync } = require("child_process");
const results = {};
for (const [key, cfg] of Object.entries(VEHICLES)) {
  const raw = execSync(`mysql --raw -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME -N -e "SELECT data FROM product_assemblies WHERE id=${cfg.paId}"`, { shell: "/bin/bash", env: { ...process.env }, maxBuffer: 1024 * 1024 * 20 }).toString();
  const orig = JSON.parse(raw);
  const origParts = orig.parts;
  results[key] = {};
  for (const [tag, plan] of [["B", cfg.planB], ["C", cfg.planC]]) {
    const { newParts } = buildVariant(origParts, plan);
    const v = verify(key, tag, newParts, cfg.carBase);
    console.log(key, tag, JSON.stringify({ ok: v.ok, dims: v.dims, errors: v.errors, boxCount: v.boxCount }));
    if (!v.ok) throw new Error(`${key} ${tag} NEPROSEL: ${v.errors.join("; ")}`);
    results[key][tag] = { parts: newParts, verify: v, plan };
  }
}
fs.writeFileSync("/opt/konfigurator/scripts/tmp_2026-09-01_bot16_bc_variants_result.json", JSON.stringify(results, null, 1));
console.log("HOTOVO, vysledky ulozeny.");
