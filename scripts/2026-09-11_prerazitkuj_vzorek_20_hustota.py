#!/usr/bin/env python3
"""Robertovo doladeni hustoty vzoru pres bot3 2026-09-11: "ty loga jsou
nahusto, prosim lehce zmensit hustotu o 10%" - PRVNI OSTRA ZKOUSKA
VRATNOSTI (bot4 ji overil jen na kopii): obnov puvodnich 20 souboru ze
zalohy (SHA overena proti manifestu DRIV nez cokoli), pak znovu
orazitkuj s novou hodnotou mezera_nasobek.

Vypocet nove hodnoty (bot3 chtel presne, ne odhad "zhruba 1.476"):
hustota (otisku na plochu) ~ 1/(krok_u*krok_v), krok_u=tile_w*(1+m),
krok_v=tile_w*(aspect+m) kde aspect=139/996 (nativni pomer loga).
Snizit hustotu o 10% => (1+m')(aspect+m') = (1+m)(aspect+m)/0.9,
reseno kvadratickou rovnici pro m' - viz MEZERA_NASOBEK_NOVE nize.
Puvodni kodovy vychozi (1.4 v nacti_konfiguraci) se NEMENI, dokud
Robert novy vzorek nepotvrdi - tohle je rucni jednorazovy prepis cfg.

Spoustet VYHRADNE jako www-data (systemd-run, viz
2026-09-11_razitkuj_vzorek_20.py pro presny prikaz).
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402

MEZERA_NASOBEK_NOVE = 1.5016  # presny vypocet: 1.501592079090395, viz docstring

PUBLIC_BASE = "https://autovestavby.logiman.cz"


def main():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rel_path, original_backup_path, original_sha256 "
                "FROM image_watermark_manifest ORDER BY rel_path")
            radky = cur.fetchall()
    finally:
        conn.close()

    print(f"nalezeno v manifestu: {len(radky)} radku")
    vysledky = []
    for radek in radky:
        rel = radek["rel_path"]
        backup_path = radek["original_backup_path"]
        original_sha = radek["original_sha256"]
        abs_path = os.path.join(orz.WEBAPP_ROOT, rel)

        # 1) OBNOVA + OVEREN­I - DRIV nez cokoli jineho
        with open(backup_path, "rb") as f:
            zaloha_bytes = f.read()
        if orz._sha256(zaloha_bytes) != original_sha:
            print(f"STOP {rel}: zaloha se neshoduje s manifestem, PRESKAKUJI")
            vysledky.append((rel, "CHYBA-zaloha-neshoda", None))
            continue
        orz._atomicky_zapis(abs_path, zaloha_bytes)
        with open(abs_path, "rb") as f:
            po_obnove = f.read()
        if orz._sha256(po_obnove) != original_sha:
            print(f"STOP {rel}: po obnove neshoda, PRESKAKUJI (nestamplovan)")
            vysledky.append((rel, "CHYBA-obnova-neshoda", None))
            continue
        print(f"OBNOVENO+OVERENO {rel}")

        # 2) ZNOVU ORAZITKOVAT s novou hustotou
        conn2 = app.get_conn()
        try:
            with conn2.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                cfg["mezera_nasobek"] = MEZERA_NASOBEK_NOVE
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn2.commit()
        except Exception as e:  # noqa: BLE001
            conn2.rollback()
            vysl = f"CHYBA: {e}"
        finally:
            conn2.close()
        url = f"{PUBLIC_BASE}/{rel}"
        vysledky.append((rel, vysl, url))
        print(f"  {vysl:20} {url}")

    print("\n--- shrnuti ---")
    from collections import Counter
    print(Counter(v[1] for v in vysledky))
    print("\n--- URL seznam (Ctrl+F5, prohlizec drzi stare v cache!) ---")
    for rel, vysl, url in vysledky:
        if url:
            print(url)


if __name__ == "__main__":
    main()
