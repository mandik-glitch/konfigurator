"""Robert 2026-09-14: 'smazat razitka na vsech sestavach A a B a orazitkovat
nove' - po dnesni prestavbe horniho bloku (posun/revert/rebuild) uz stara
razitka nemusi sedet na aktualni sadu profilu. Force re-stamp (stejny vzor
jako tmp_2026-09-12_bot8_razitkuj_doblo_serii.py) - explicitni smazani +
prime volani orazitkuj_data_sestavy, nespolehat na otisk-idempotenci."""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import razitkovac

env = {}
with open("/opt/konfigurator/api/.env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
import pymysql

KATALOG_DIR = "/opt/konfigurator/webapp/katalog"
IDS = [374, 369, 382, 383, 384, 376, 370, 379, 380, 385]  # aktivni A-00..04, B-00..04

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    rozmery = razitkovac.rozmery_z_katalogu(cur, KATALOG_DIR)
    for aid in IDS:
        cur.execute("SELECT name, data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        data = json.loads(row["data"])
        parts = list(data.get("parts") or [])
        ciste = [p for p in parts if not razitkovac.je_razitko(p.get("role"))]
        odebrano = len(parts) - len(ciste)
        nove, chyba = razitkovac.orazitkuj_data_sestavy(ciste, aid, KATALOG_DIR, rozmery=rozmery)
        if chyba:
            print(f"id={aid} ({row['name'][:40]}): CHYBA - {chyba}")
            continue
        data["parts"] = ciste + nove
        data["razitka"] = {"otisk": razitkovac.otisk_sestavy(ciste, razitkovac.KAZDY_NTY),
                           "pocet": len(nove), "verze": razitkovac.OTISK_VERZE}
        data["_note"] = (data.get("_note") or "") + (
            "\n\nbot8 2026-09-14: force-orazitkovano znovu (%d starych odebrano -> %d "
            "novych) po dnesni prestavbe horniho bloku - stara razitka mohla sedet na "
            "uz neexistujici/presunute profily." % (odebrano, len(nove)))
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                    (json.dumps(data, ensure_ascii=False), aid))
        print(f"id={aid} ({row['name'][:40]}): {odebrano} starych -> {len(nove)} novych razitek")
    conn.commit()
conn.close()
print("hotovo")
