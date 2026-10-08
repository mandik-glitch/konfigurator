// Presnejsi overeni: misto "nova kolize vs prazdny horni blok" (ktere
// spravne odhali VSECHNY zamerne zasuny do drazky jako "nove") porovnej
// PLNOU sadu kolizi hornibloko-souvisejicich paru v prestavenem C se
// STEJNOU sadou v UZ ZIVE, Robertem schvalene A-sestave se stejnou
// variantou. Pokud se presne shoduji (stejne pary, stejne rozmery),
// port na C je STEJNE bezpecny jako to, co uz dnes bezi v A/B.
const fs = require("fs");
const THREE = require("three");
const R = require("/opt/konfigurator/scripts/2026-09-11_glb_resolver.js");
const { parseGlbMesh } = require("/opt/konfigurator/scripts/2026-08-19_glb_real_geometry.js");

const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const P = JSON.parse(fs.readFileSync(`${SCRATCH}/c_rebuild_payload.json`, "utf8"));
const REF = { 344: 369, 343: 382, 345: 383, 347: 384 }; // C-id -> jeho A-protejsek (uz zivy, schvaleny)

function worldBox(p) {
  const glb = R.glbPath(p.part_id); if (!glb) return null;
  const mesh = parseGlbMesh(glb);
  mesh.position.set(p.position[0], p.position[1], p.position[2]);
  mesh.quaternion.set(p.quaternion[0], p.quaternion[1], p.quaternion[2], p.quaternion[3]);
  mesh.scale.set(p.scale[0], p.scale[1], p.scale[2]);
  mesh.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(mesh);
}
function overlap3(A, B) { return [Math.min(A.max.x, B.max.x) - Math.max(A.min.x, B.min.x), Math.min(A.max.y, B.max.y) - Math.max(A.min.y, B.min.y), Math.min(A.max.z, B.max.z) - Math.max(A.min.z, B.min.z)]; }
const HB_PREFIXES = ["podelnik-", "pricka-spodni", "pricka-horni", "pricka-police", "vypln-"];
const isHb = (p) => HB_PREFIXES.some(pre => (p.role || "").startsWith(pre));
function scanHbPairs(parts) {
  const m = parts.filter(p => !R.jeKaroserie(p.part_id)).map(p => ({ p, box: worldBox(p) }));
  const pairs = new Map();
  for (let i = 0; i < m.length; i++) for (let j = i + 1; j < m.length; j++) {
    if (!isHb(m[i].p) && !isHb(m[j].p)) continue; // zajima nas jen kdyz je aspon jeden dil z horniho bloku
    const [ox, oy, oz] = overlap3(m[i].box, m[j].box);
    if (ox > 0.5 && oy > 0.5 && oz > 0.5) {
      const key = [m[i].p.role, m[j].p.role].sort().join("|");
      pairs.set(key, [ox, oy, oz].sort((a, b) => a - b).map(v => +v.toFixed(1)));
    }
  }
  return pairs;
}

async function main() {
  const mysql = require("child_process");
  for (const [cIdStr, info] of Object.entries(P)) {
    const cId = Number(cIdStr);
    const aId = REF[cId];
    const cPairs = scanHbPairs(info.after_parts);

    // nacti aktualni A-referencni sestavu z DB (fresh)
    const out = mysql.execSync(
      `/opt/konfigurator/api/venv/bin/python3 -c "import sys,json; sys.path.insert(0,'/opt/konfigurator/scripts'); from _env import get_conn; c=get_conn(); cur=c.cursor(); cur.execute('SELECT data FROM product_assemblies WHERE id=%s',(${aId},)); print(cur.fetchone()['data']); c.close()"`,
      { maxBuffer: 1024 * 1024 * 50 }
    ).toString();
    const aData = JSON.parse(out);
    const aPairs = scanHbPairs(aData.parts);

    const onlyInC = [...cPairs.keys()].filter(k => !aPairs.has(k));
    const onlyInA = [...aPairs.keys()].filter(k => !cPairs.has(k));
    const differing = [...cPairs.keys()].filter(k => aPairs.has(k) && JSON.stringify(aPairs.get(k)) !== JSON.stringify(cPairs.get(k)));

    console.log(`\n=== C id=${cId} (var ${info.label}) vs A referencni id=${aId} ===`);
    console.log(`HB-souvisejicich paru: C=${cPairs.size} A(ref)=${aPairs.size}`);
    if (onlyInC.length) { console.log(" JEN V C (potencialne nove/skutecne):"); for (const k of onlyInC) console.log("   ", k, JSON.stringify(cPairs.get(k))); }
    if (onlyInA.length) { console.log(" JEN V A-ref (chybi v C - neocekavane):"); for (const k of onlyInA) console.log("   ", k, JSON.stringify(aPairs.get(k))); }
    if (differing.length) { console.log(" ROZDILNA VELIKOST prekryvu:"); for (const k of differing) console.log("   ", k, "C=", JSON.stringify(cPairs.get(k)), "A=", JSON.stringify(aPairs.get(k))); }
    if (!onlyInC.length && !onlyInA.length && !differing.length) console.log(" PRESNA SHODA s jiz zivou/schvalenou A-sestavou - port je stejne bezpecny jako dnesni stav A/B.");
  }
}
main();
