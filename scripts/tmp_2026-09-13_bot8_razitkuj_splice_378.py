"""Znovu-orazitkuje #378 (Doblo B hbv=4) po chirurgicke oprave horniho pasma -
stejny vzor jako tmp_2026-09-13_bot8_razitkuj_splice_a.py (verze A)."""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import razitkovac
from _env import get_conn

KATALOG_DIR = "/opt/konfigurator/webapp/katalog"
IDS = [378]

conn = get_conn()
with conn.cursor() as cur:
    rozmery = razitkovac.rozmery_z_katalogu(cur, KATALOG_DIR)
    for aid in IDS:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        data = json.loads(row["data"])
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
        print(f"id={aid}: orazitkovano ({odebrano} bez razitek -> {len(nove)} novych)")
    conn.commit()
conn.close()
print("hotovo")
