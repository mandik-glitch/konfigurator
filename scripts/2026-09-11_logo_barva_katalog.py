#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zapise oranzovou barvu loga do katalogu (`cfg_dily.color_hex`).

PROC EXISTUJE
--------------
Robert 2026-09-11 (pres bot3): "na razitka musime pridat barvu, lehce
oranzovou" - logo LOGIMAN.CZ (`cfg_dily.id='logo_logiman_cz'`) dostalo
barvu jen v `scripts/razitkovac.py` (`_razitko_pro_profil()`, LOGO_BARVA_HEX
atd.) - to ale stihne obarvit jen DOCASNE dily pro jeden konkretni render
(build_job() vetev "zadna", kdy se razitkuje ZIVE za behu).

Jakmile se razitka jednou ULOZI do `product_assemblies.data` (spoustec pri
zarazeni do slozky - `api/product_assemblies.py::_orazitkuj_pri_zarazeni`,
nebo tento skript `scripts/orazitkovat_sestavy.py --zapsat`), volaji se
`razitkovac.prerazitkuj()` -> `orazitkuj_data_sestavy()`, ktera VYSLOVNE
odstranuje `color_hex`/`base_color`/`metalness`/`roughness` z ulozenych dat
(`_JEN_PRO_RENDER`, viz komentar tamtez) - je to spravne pro VSECHNY OSTATNI
dily (jejich material se vzdy odvozuje znovu z katalogu podle `part_id`),
ale u loga to znamena, ze oranzova barva se PRI KAZDEM DALSIM CTENI (dalsi
render, scene.html, `GET /api/public/offers/<token>/model`) ZTRATI -
`resolve_parts()`/`fetch_katalog_parts()` sáhne zpet do `cfg_dily`, kde
`logo_logiman_cz` ma `layer='alu'` a `color_hex=NULL` (zamerne nastaveno
2026-09-09, "aby ve scene vypadalo jako hlinik" - viz api/admin_profily.py
komentar - dnes uz neplatne, Robert chce oranzovou).

Zjisteno 2026-09-11 pri overovani ctyrstranneho razitkovani (bot16) -
bez tohohle zapisu by "logo dostane oranzovou barvu" vypadalo hotove v
kodu, ale na zadnem dalsim renderu/zobrazeni by se neprojevilo.

Meni jen JEDEN radek, jeden sloupec, u dilu, ktery se pouziva VYHRADNE
jako razitko (neni to sdileny material s necim jinym v katalogu).
`vypln_drazky_30` se NEMENI - drazka zustava barvy hostitelskeho profilu
(Robert: barvu chce jen na logu, ne na vyplni).

POUZITI
-------
    api/venv/bin/python3 scripts/2026-09-11_logo_barva_katalog.py          # nahled
    sudo -u www-data api/venv/bin/python3 scripts/2026-09-11_logo_barva_katalog.py --zapsat
"""
import argparse
import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import razitkovac as rz  # noqa: E402
import _env  # noqa: E402

PART_ID = "logo_logiman_cz"
ZALOHY = os.path.join(REPO, "backups")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zapsat", action="store_true",
                    help="bez tohohle se JEN vypise, co by se stalo")
    a = ap.parse_args()

    env = _env.load_env()
    conn = _env.get_conn(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, glb_file, layer, color_hex FROM cfg_dily WHERE id=%s", (PART_ID,))
            row = cur.fetchone()
            if not row:
                raise SystemExit("cfg_dily nema radek '%s'." % PART_ID)

            cur.execute("SELECT COUNT(*) AS n FROM cfg_dily WHERE id != %s AND glb_file = %s",
                        (PART_ID, row["glb_file"]))
            sdileny = cur.fetchone()["n"]

            print("Soucasny stav: %s" % row)
            print("Novy color_hex: %s (metalness=%.2f, roughness=%.2f - viz razitkovac.LOGO_*)"
                  % (rz.LOGO_BARVA_HEX, rz.LOGO_METALNESS, rz.LOGO_ROUGHNESS))
            if sdileny:
                raise SystemExit("STOP: glb_file '%s' pouziva jeste %d dalsi katalogovy radek - "
                                 "zmena barvy by zasahla i je." % (row["glb_file"], sdileny))

            if row["color_hex"] and row["color_hex"].lower() == rz.LOGO_BARVA_HEX.lower():
                print("Beze zmeny - color_hex uz je na pozadovane hodnote.")
                return

            if not a.zapsat:
                print("\nNAHLED - nic se nezapsalo. Ostry beh: pridej --zapsat")
                return

            os.makedirs(ZALOHY, exist_ok=True)
            cesta = os.path.join(ZALOHY, "%s_logo_barva_katalog_pred_zapisem.json"
                                 % datetime.now().strftime("%Y-%m-%d_%H%M%S"))
            with open(cesta, "w", encoding="utf-8") as fh:
                json.dump(dict(row), fh, ensure_ascii=False, indent=1)
            print("Zaloha puvodniho radku: %s" % cesta)

            cur.execute("UPDATE cfg_dily SET color_hex=%s WHERE id=%s",
                        (rz.LOGO_BARVA_HEX, PART_ID))
            conn.commit()

            cur.execute("SELECT id, glb_file, layer, color_hex FROM cfg_dily WHERE id=%s", (PART_ID,))
            po = cur.fetchone()
            if po["color_hex"] != rz.LOGO_BARVA_HEX:
                raise SystemExit("ZAPIS NESEDI: po UPDATE je color_hex=%r, cekano %r"
                                 % (po["color_hex"], rz.LOGO_BARVA_HEX))
            print("ZAPSANO a overeno zpetnym cteni: %s" % po)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
