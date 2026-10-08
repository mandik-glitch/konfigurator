// Prepocet `product_assemblies.data` (JSON {parts:[...], ...}) po fyzickem
// 180Y-flipu podkladove karoserie (viz scripts/2026-08-31_flip_car_body_ci25_180.js
// a KAROSERIE_UMISTENI.md "Audit orientace VSECH karoserii v katalogu").
//
// DULEZITE (zjisteno bot16, 2026-08-31, po nalezu ze regaly CI25
// product_assemblies.id=53/54/55 renderovaly MIMO karoserii po flipu GLB):
// pokud `data.parts` obsahuje primo i car_body_* dily (part_id ve tvaru
// "car_body_<car_bodies.id>"), TY SE NESMI transformovat - podkladovy GLB
// mesh uz je fyzicky prepsan (baked) do nove orientace, takze car_body
// cast musi zustat na identite (position [0,0,0], quaternion [0,0,0,1]),
// stejne jako pred flipem. Transformuje se VYHRADNE zbytek dilu (nohy,
// nosniky, spojnice, euroboxy...) - ty byly postaveny v PUVODNI (pred-flip)
// souradnicove soustave karoserie a je potreba je "presunout" do nove.
//
// Pouziti:
//   node 2026-08-31_flip_product_assembly_parts_180.js <input.json> <output.json>
// (input.json = obsah sloupce `data` pro dany product_assemblies.id,
// output.json = stejna struktura, jen s prepocitanymi non-car_body dily)
//
// Overeno na CI14 precedentu (scripts/tmp_2026-08-30_flip_assembly_180.js -
// stejna position/quaternion matematika, jen jina vstupni struktura dat).

const fs = require("fs");
const THREE = require("three");

const [, , inPath, outPath] = process.argv;
if (!inPath || !outPath) {
  console.error("Pouziti: node 2026-08-31_flip_product_assembly_parts_180.js <input.json> <output.json>");
  process.exit(1);
}

const q180Y = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI);

function isCarBodyPart(partId) {
  return /^car_body_\d+$/.test(partId);
}

function flipPart(p) {
  const [x, y, z] = p.position;
  const q = new THREE.Quaternion(...p.quaternion);
  const newQ = q180Y.clone().multiply(q);
  return {
    ...p,
    position: [-x, y, -z],
    quaternion: [newQ.x, newQ.y, newQ.z, newQ.w],
  };
}

const data = JSON.parse(fs.readFileSync(inPath, "utf8"));
let flippedCount = 0, keptCount = 0;
data.parts = data.parts.map(p => {
  if (isCarBodyPart(p.part_id)) {
    keptCount++;
    return p; // beze zmeny - mesh uz je baked-flipnuty
  }
  flippedCount++;
  return flipPart(p);
});

fs.writeFileSync(outPath, JSON.stringify(data, null, 1));
console.log(`Hotovo: ${flippedCount} dilu prepocitano, ${keptCount} car_body dilu ponechano na identite. Zapsano do ${outPath}.`);
console.log("Pred ulozenim do DB: znovu overit koliznim testem proti NOVE (jiz otocene) karoserii GLB (checkCarBodyCollisions/ekvivalentni Node skript).");
