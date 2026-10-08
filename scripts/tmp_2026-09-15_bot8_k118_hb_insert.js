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
for (const [label] of Object.entries(LABELS)) {
  if (!build[label] || !build[label].ok) throw new Error(`${label} neni OK`);
}
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
const m = srcRow.name.match(/^(.*?)\s+([A-C])\s+-\s+(boxy43-[\dx-]+.*?)(\s*\[10\/30mm od kolize\])?$/);
if (!m) throw new Error("nazev nesedi na ocekavany vzor: " + srcRow.name);
const [, prefix, verze, boxPopis] = m;
const inserts = [];
for (const [label, cfg] of Object.entries(LABELS)) {
  const name = `${prefix} ${verze}-${label} - ${boxPopis}, ${cfg.popis} [10/30mm od kolize]`;
  inserts.push({
    name, karoserie_kod: srcRow.karoserie_kod, typologie_id: srcRow.typologie_id,
    umisteni_id: srcRow.umisteni_id, profil_mm: srcRow.profil_mm, verze: srcRow.verze,
    typologie_varianta_id: srcRow.typologie_varianta_id, horni_blok_varianta_id: cfg.hbv,
    dodatek: srcRow.dodatek, prepazka_rezerva_mm: srcRow.prepazka_rezerva_mm,
    podbeh_rezerva_mm: srcRow.podbeh_rezerva_mm, car_model_id: srcRow.car_model_id,
    parts: build[label].parts,
  });
}
fs.writeFileSync(`${SCRATCH}/hb_insert_payload_${AID}.json`, JSON.stringify(inserts));
inserts.forEach(i => console.log(i.name, "hbv="+i.horni_blok_varianta_id, "dilu="+i.parts.length));
