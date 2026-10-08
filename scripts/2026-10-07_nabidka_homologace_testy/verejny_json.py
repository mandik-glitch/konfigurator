# Pouziti (READ-ONLY, bez tokenu): systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_nabidka_homologace_testy/verejny_json.py <vystupni_slozka> Logiman0133 [dalsi cisla]
# Ulozi <cislo>.json = verejny JSON nabidky tak, jak ho vraci ZIVE API; pak realna_nabidka.js / rozlozeni_posledni_strany.js (env OUT, JSONDIR, CISLO) otevrou SKUTECNOU stranku s temito daty.
# READ-ONLY: verejny JSON nabidky tak, jak ho dnes vraci ZIVA verze API (GET /api/public/offers/<token>) pro nabidky z DB; zadny zapis, token se jen podvrhne pro vyhledani radku.
import json, os, sys
API = "/opt/konfigurator/api"; sys.path.insert(0, API); sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import scene_offers  # noqa: E402
OUT = sys.argv[1]; CISLA = sys.argv[2:]
orig = scene_offers._resolve_offer_by_token
cur_row = {}
def fake(cur, token):
    cur.execute("SELECT * FROM scene_offers WHERE offer_number=%s", (cur_row["cislo"],))
    return cur.fetchone()
scene_offers._resolve_offer_by_token = fake
cl = appmod.app.test_client()
for cislo in CISLA:
    cur_row["cislo"] = cislo
    r = cl.get("/api/public/offers/x-readonly-lookup")
    d = r.get_json(silent=True)
    open(os.path.join(OUT, cislo + ".json"), "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False))
    oo = (d or {}).get("offer_options") or {}
    print(cislo, "HTTP", r.status_code, "| is_vehicle_assembly:", oo.get("is_vehicle_assembly"), "| source:", (d or {}).get("source"), "| polozek:", len((d or {}).get("items") or []), "| klice voleb:", sorted(oo.keys())[:12])
