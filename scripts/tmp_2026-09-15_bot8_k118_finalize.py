import json, sys
sys.path.insert(0, "/opt/konfigurator/scripts")
import razitkovac
from _kod_sestavy import sestavit_kod_sestavy
from _env import get_conn

KATALOG_DIR = "/opt/konfigurator/webapp/katalog"
IDS = [int(x) for x in sys.argv[1:]]

conn = get_conn()
try:
    with conn.cursor() as cur:
        rozmery = razitkovac.rozmery_z_katalogu(cur, KATALOG_DIR)
        cur.execute("SELECT kod FROM regal_umisteni WHERE id=1")
        umisteni_kod = cur.fetchone()["kod"]
        cur.execute("SELECT kod FROM regal_typologie WHERE id=1")
        typologie_kod = cur.fetchone()["kod"]

        for aid in IDS:
            cur.execute("SELECT * FROM product_assemblies WHERE id=%s", (aid,))
            row = cur.fetchone()
            data = json.loads(row["data"])
            parts = list(data.get("parts") or [])
            ciste = [p for p in parts if not razitkovac.je_razitko(p.get("role"))]
            nove, chyba = razitkovac.orazitkuj_data_sestavy(ciste, aid, KATALOG_DIR, rozmery=rozmery)
            if chyba:
                print(f"id={aid}: CHYBA razitko - {chyba}")
                continue
            data["parts"] = ciste + nove
            data["razitka"] = {"otisk": razitkovac.otisk_sestavy(ciste, razitkovac.KAZDY_NTY),
                               "pocet": len(nove), "verze": razitkovac.OTISK_VERZE}

            cur.execute("SELECT kod FROM typologie_varianty WHERE id=%s", (row["typologie_varianta_id"],))
            varianta_kod = cur.fetchone()["kod"]
            cur.execute("SELECT kod FROM horni_blok_varianty WHERE id=%s", (row["horni_blok_varianta_id"],))
            hbv_kod = cur.fetchone()["kod"]
            kod = sestavit_kod_sestavy(
                karoserie_kod=row["karoserie_kod"], umisteni_kod=umisteni_kod,
                typologie_kod=typologie_kod, profil_mm=row["profil_mm"], verze=row["verze"],
                varianta_kod=varianta_kod, horni_blok_kod=hbv_kod, dodatek=row["dodatek"],
            )
            cur.execute("UPDATE product_assemblies SET data=%s, kod_sestavy=%s WHERE id=%s",
                        (json.dumps(data, ensure_ascii=False), kod, aid))
            print(f"id={aid} ({row['name'][:55]}): razitek={len(nove)} kod_sestavy={kod}")
    conn.commit()
finally:
    conn.close()
print("hotovo")
