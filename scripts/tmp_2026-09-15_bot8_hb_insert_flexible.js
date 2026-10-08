const fs = require("fs");
const { execSync } = require("child_process");
const SCRATCH = "/tmp/claude-0/-opt-konfigurator/68994686-5a6b-46d4-b3c7-14bc1f68c6ac/scratchpad";
const AID = process.argv[2];
const build = JSON.parse(fs.readFileSync(`${SCRATCH}/hb_build_${AID}.json`, "utf8"));
const LABELS = {
  "01": { hbv: 8, popis: "jedno pásmo, rám + dna [ZÁKLAD]" },
  "02": { hbv: 5, popis: "dvě pásma, police jen příčky" },
  "03": { hbv: 6, popis: "dvě pásma, plné výplně, bez police" },
  "04": { hbv: 7, popis: "dvě pásma, plné výplně, s policí" },
};
// bot8 2026-09-15: flexibilni varianta k118_hb_insert.js - zpracuje jen
// labely, ktere ve `build` skutecne existuji a jsou OK (na rozdil od
// puvodni verze, ktera vzdy vyzadovala vsechny 4 najednou) - potreba pro
// K-020 B (198), kde varianta 02 je genuinne geometricky nemozna (kanal
// 29mm < potrebnych 30mm pro policovy profil, viz horni_ram.js throw).
const availableLabels = Object.keys(LABELS).filter(l => build[l] && build[l].ok);
console.log(`dostupne labely pro ${AID}: ${availableLabels.join(", ")}`);
const py = `
import sys, json
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn
conn = get_conn()
with conn.cursor() as cur:
    cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (${AID},))
    src = cur.fetchone()
conn.close()
print(json.dumps({k: v for k, v in src.items() if k != "data"}, default=str))
`;
fs.writeFileSync(`${SCRATCH}/_fetch_src_row.py`, py);
const srcRow = JSON.parse(execSync(`/opt/konfigurator/api/venv/bin/python3 ${SCRATCH}/_fetch_src_row.py`).toString());
const m = srcRow.name.match(/^(.*?)\s+([A-Z])\s+-\s+(boxy43-[\dx-]+.*?)(\s*\[10\/30mm od kolize\])?$/);
if (!m) throw new Error("nazev nesedi na ocekavany vzor: " + srcRow.name);
const [, prefix, verze, boxPopis] = m;
const inserts = [];
for (const label of availableLabels) {
  const cfg = LABELS[label];
  const name = `${prefix} ${verze}-${label} - ${boxPopis}, ${cfg.popis} [10/30mm od kolize]`;
  inserts.push({
    name, karoserie_kod: srcRow.karoserie_kod, typologie_id: srcRow.typologie_id,
    umisteni_id: srcRow.umisteni_id, profil_mm: srcRow.profil_mm, verze: srcRow.verze,
    typologie_varianta_id: srcRow.typologie_varianta_id, horni_blok_varianta_id: cfg.hbv,
    dodatek: srcRow.dodatek, prepazka_rezerva_mm: srcRow.prepazka_rezerva_mm,
    podbeh_rezerva_mm: srcRow.podbeh_rezerva_mm, car_model_id: srcRow.car_model_id,
    // Robert 2026-09-17: mezera_police_mm se ted zapisuje uz pri vlozeni
    // (drive zustavalo NULL a "_mezera_ok" NULL bral jako "projde" - viz
    // tmp_2026-09-16_bot8_hb_build.js komentar), primo z horni_ram.js
    // "svetlaVyskaRamu" zmereneho pro tenhle label (null u "01").
    mezera_police_mm: build[label].mezera_police_mm,
    parts: build[label].parts,
  });
}
fs.writeFileSync(`${SCRATCH}/hb_insert_payload_${AID}.json`, JSON.stringify(inserts));
inserts.forEach(i => console.log(i.name, "hbv="+i.horni_blok_varianta_id, "dilu="+i.parts.length));
