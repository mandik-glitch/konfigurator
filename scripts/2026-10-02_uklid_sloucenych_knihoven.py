#!/usr/bin/env python3
"""Jednorazovy uklid private-files/alu_test/tmp*.blend (bot4 2026-10-02). Jsou to DOCASNE slouceniny knihoven materialu
(scripts/_render_prirazeni_lib.py::sestav_material_knihovnu), z nichz se pro KAZDE zarazeni renderu vyrabel novy soubor a nikdy se
nemazal: k 2026-10-02 303 souboru / 5,4 GB, disk /opt na 97 %. Slouceniny jdou kdykoli znovu vyrobit z puvodnich knihoven.
Maze JEN tmp*.blend, ktere jsou starsi nez --min-minut (vychozi 60) a na ktere neodkazuje zadna konfigurace ulohy
(private-files/blender-renders/*.json). Rucni testovaci soubory (vd_materialy_*.blend) a knihovna_*.blend (cache) se nedotknou.
Spusteni:  python3 scripts/2026-10-02_uklid_sloucenych_knihoven.py [--apply] [--min-minut N]
"""
import argparse
import glob
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNIHOVNY = os.path.join(REPO, "private-files", "alu_test")
ULOHY = os.path.join(REPO, "private-files", "blender-renders")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-minut", type=int, default=60)
    a = ap.parse_args()
    odkazy = ""
    for f in glob.glob(os.path.join(ULOHY, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                odkazy += fh.read()
        except OSError:
            pass
    hranice = time.time() - a.min_minut * 60
    smazat, nechat_odkaz, nechat_cerstve = [], [], []
    for f in sorted(glob.glob(os.path.join(KNIHOVNY, "tmp*.blend"))):
        try:
            st = os.stat(f)
        except OSError:
            continue
        if os.path.basename(f) in odkazy:
            nechat_odkaz.append(f)
        elif st.st_mtime >= hranice:
            nechat_cerstve.append(f)
        else:
            smazat.append((f, st.st_size))
    velikost = sum(s for _, s in smazat)
    print("%s: %d souboru / %.2f GB ke smazani; ponechano %d (odkazuje na ne uloha) + %d (mladsi nez %d min)"
          % ("MAZU" if a.apply else "DRY-RUN", len(smazat), velikost / 1073741824, len(nechat_odkaz), len(nechat_cerstve), a.min_minut))
    if a.apply:
        smazano = 0
        for f, _ in smazat:
            try:
                os.remove(f)
                smazano += 1
            except OSError as e:
                print("nelze smazat %s: %s" % (f, e))
        print("smazano %d souboru" % smazano)


if __name__ == "__main__":
    main()
