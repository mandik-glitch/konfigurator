"""Znovu-orazitkuje novou serii K-075 (Doblo, 10/30mm od kolize, id 341-347)
aktualnim (opravenym) razitkovac.py - viz commit 8fb753752 (bot9, oprava
otoceni o 180 stupnu na 'horni' stene a 'zadni' u svisleho profilu)."""
import json
import sys
import os

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
IDS = [340, 348, 349, 350, 351, 353, 354]

conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    rozmery = razitkovac.rozmery_z_katalogu(cur, KATALOG_DIR)
    for aid in IDS:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        data = json.loads(row["data"])
        # force: prerazitkuj by kvuli nezmenenemu otisku (ten se pocita z
        # ostatnich dilu, ne z kodu razitkovace) rekl "aktualni" a nic
        # neudelal - opravili jsme algoritmus, ne geometrii, proto stary
        # otisk NEPOZNA, ze se ma prepocitat. Smaz stara razitka rucne a
        # zavolej orazitkuj_data_sestavy primo (presne to, co by prerazitkuj
        # udelal, kdyby stav_razitek rekl "zastarala").
        parts = list(data.get("parts") or [])
        ciste = [p for p in parts if not razitkovac.je_razitko(p.get("role"))]
        odebrano = len(parts) - len(ciste)
        nove, chyba = razitkovac.orazitkuj_data_sestavy(ciste, aid, KATALOG_DIR, rozmery=rozmery)
        if chyba:
            print(f"id={aid}: CHYBA - {chyba}")
            continue
        data["parts"] = ciste + nove
        data["razitka"] = {"otisk": razitkovac.otisk_sestavy(ciste, razitkovac.KAZDY_NTY),
                           "pocet": len(nove), "verze": razitkovac.OTISK_VERZE}
        cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                    (json.dumps(data, ensure_ascii=False), aid))
        print(f"id={aid}: force-orazitkovano ({odebrano} starych -> {len(nove)} novych dilu)")
    conn.commit()
conn.close()
print("hotovo")
