#!/usr/bin/env python3
"""2026-09-23_vandr_razitka_auto_dispatch.py - automat: sam najde Vandr
karty s hotovym GLB a bez aktualnich razitek a orazitkuje je.

Robert, ostre pres bot3 2026-09-23: "proc to neni automatizovane? mas to
za ukol koordinovat!!!" - do teto chvile se
2026-09-23_vandr_razitka_spocitat.py spoustel RUCNE, kartu po karte.
Tenhle skript je stejny vzor jako 2026-09-22_vandr_fbx_watcher.py /
2026-09-14_render_auto_dispatch.py (samostatny oneshot + systemd timer),
jen pro krok "razitka", ne "zalozeni karty" ani "render".

CO DELA:
  1. Najde shop_products se sku LIKE 'VD-%%', glb_file NOT NULL.
  2. Pro kazdy spocita sha256 aktualniho GLB souboru a porovna s
     ulozenym vandr_razitka_glb_otisk - shoda = preskoci (uz hotovo a
     aktualni), neshoda/NULL = potreba (pre)pocitat.
  3. Pro kazdou potrebnou kartu spusti
     scripts/2026-09-23_vandr_razitka_spocitat.py --shop-product-id
     (Blender headless subprocess - potrebuje bpy, viz ten skript).
  4. Loguje vysledek kazde karty zvlast (jedna spatna karta nesmi shodit
     cely beh - viz VLASTNOSTI_PROFILU.md "0 nalezeno musi znamenat
     zmereno a cisto, ne nezmereno": vypisuje se POCET ZKONTROLOVANYCH,
     POCET POTREBNYCH, POCET USPESNYCH/CHYBNYCH, ne jen "hotovo").

ZADNY zasah do product_assemblies (Robert/bot3: "2. vetev se vepisuje do
tabulky pro 1. vetev, to nelze" - viz 2026-09-22_vandr_fbx_watcher.py
hlavicka). ZADNY render se tady NESPOUSTI - to je samostatny krok
(render_auto_dispatch.py / bot10), tenhle automat jen pripravuje data,
ktera renderovaci krok pak potrebuje.

Pouziti:
    api/venv/bin/python3 scripts/2026-09-23_vandr_razitka_auto_dispatch.py [--dry-run]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep + "scripts", 1)[0]
KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")
BLENDER = "/opt/blender-5.2/blender"
SPOCITAT_SKRIPT = os.path.join(REPO, "scripts", "2026-09-23_vandr_razitka_spocitat.py")


def _env():
    env = {}
    for line in open(os.path.join(REPO, "api", ".env")):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def _conn():
    import glob
    venv_site = glob.glob(os.path.join(REPO, "api", "venv", "lib", "python3.*", "site-packages"))
    if venv_site and venv_site[0] not in sys.path:
        sys.path.insert(0, venv_site[0])
    import pymysql
    env = _env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vandr_razitka_otisk import otisk_glb, PRAVIDLO_VERZE  # noqa: E402  (bot10 2026-09-24: otisk nese verzi pravidla)


def _sha256_souboru(cesta):
    h = hashlib.sha256()
    with open(cesta, "rb") as fh:
        for blok in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(blok)
    return h.hexdigest()


def najdi_kandidaty(conn):
    """Vraci seznam (id, name, glb_path, otisk) karet, ktere POTREBUJI
    (pre)pocitat razitka - bud je nemaji vubec, nebo se GLB od posledniho
    vypoctu zmenil (otisk nesedi).

    `sku NOT LIKE 'VD-TEST-%%'`: 4899/4900/4901 jsou bot4uv vlastni starsi
    testovaci exporty (nazev zacina "TEST:", active=0) se zmerene TRVALE
    chybnymi jednotkami (metry misto mm v puvodnim GLB, viz CHYBA JEDNOTEK
    v spocitat.py) - historicky prvni obrana, ponechana pro jasnost, i
    kdyz `vandr_razitka_chyba_otisk` (viz nize) uz by je taky vyfiltroval.

    `vandr_razitka_chyba_otisk`: zaznam "uz jsme na tomhle PRESNE souboru
    zkusili a selhalo to" (bot3 2026-09-23, po ostrem nalezu, ze prvni
    verze automatu hlasila systemd sluzbu jako trvale "failed" -
    kandidat, ktery selhal a GLB se od te doby nezmenil, se PRESKAKUJE,
    ne zkousi znovu porad dokola. Zmeni-li se GLB (novy export/oprava),
    otisk uz nesedi a kandidat se zkusi znovu."""
    kandidati = []
    zkontrolovano = 0
    preskoceno_znama_chyba = []
    chybejici_soubor = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, glb_file, vandr_razitka_glb_otisk, vandr_razitka_chyba_otisk "
            "FROM shop_products WHERE sku LIKE 'VD-%%' AND sku NOT LIKE 'VD-TEST-%%' "
            "AND glb_file IS NOT NULL")
        radky = cur.fetchall()
    for r in radky:
        zkontrolovano += 1
        glb_path = os.path.join(KATALOG_DIR, r["glb_file"])
        if not os.path.isfile(glb_path):
            chybejici_soubor.append((r["id"], r["glb_file"]))
            continue
        aktualni_otisk = otisk_glb(glb_path)   # sha256(GLB)+PRAVIDLO_VERZE, viz _vandr_razitka_otisk.py
        if aktualni_otisk == (r["vandr_razitka_glb_otisk"] or ""):
            continue  # uz hotovo a aktualni
        if aktualni_otisk == (r["vandr_razitka_chyba_otisk"] or ""):
            preskoceno_znama_chyba.append(r["id"])
            continue  # uz zname selhani na TOMTO souboru, neopakovat navzdy
        kandidati.append((r["id"], r["name"], glb_path, aktualni_otisk))
    return kandidati, zkontrolovano, chybejici_soubor, preskoceno_znama_chyba


def zapis_znamou_chybu(conn, shop_product_id, otisk):
    with conn.cursor() as cur:
        cur.execute("UPDATE shop_products SET vandr_razitka_chyba_otisk=%s WHERE id=%s",
                    (otisk, shop_product_id))
    conn.commit()


def orazitkuj_kartu(shop_product_id, glb_path):
    """Spusti vypocet+zapis pro jednu kartu jako Blender headless subprocess.
    Vraci (ok, vystup_posledni_radky)."""
    proc = subprocess.run(
        [BLENDER, "-b", "-P", SPOCITAT_SKRIPT, "--",
         glb_path, "--shop-product-id", str(shop_product_id)],
        capture_output=True, text=True, timeout=600)
    vystup = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and "ZAPSANO do shop_products" in vystup
    posledni_radky = "\n".join(vystup.strip().splitlines()[-6:])
    return ok, posledni_radky


def _nahlas_novou_chybu(conn, shop_product_id, name, vystup):
    """Bot3 2026-09-23: sluzba nesmi hlasit "failed" navzdy kvuli znamemu,
    uz zaznamenanemu selhani (viz zapis_znamou_chybu) - ale novou/prvni
    chybu na danem GLB porad NEKDO videt musi. bot_ukoly je sdileny
    mechanismus napric automaty (vandr_fbx_watcher.py stejny vzor)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_ukoly (text, bot_id) VALUES (%s, 'bot4')",
                ("Vandr razitka: karta shop_products #%d (%s) nova chyba pri "
                 "vypoctu, viz posledni radky:\n%s" % (shop_product_id, name, vystup),))
        conn.commit()
    except Exception as e:
        print("VAROVANI: zapis do bot_ukoly selhal (%s) - chyba karty %s zustava "
              "jen v tomhle logu." % (e, shop_product_id))


def main():
    ap = argparse.ArgumentParser(description="Automat: orazitkuj Vandr karty s hotovym GLB")
    ap.add_argument("--dry-run", action="store_true",
                    help="jen vypis kandidaty, nic nespoustej ani nezapisuj")
    a = ap.parse_args()

    conn = _conn()
    try:
        kandidati, zkontrolovano, chybejici_soubor, preskoceno_znama_chyba = najdi_kandidaty(conn)
    finally:
        conn.close()

    print("ZKONTROLOVANO karet (VD-%%, glb_file NOT NULL): %d" % zkontrolovano)
    if chybejici_soubor:
        print("POZOR - glb_file zapsany v DB, ale soubor na disku chybi: %d: %s"
              % (len(chybejici_soubor), chybejici_soubor))
    if preskoceno_znama_chyba:
        print("PRESKOCENO (jiz znama chyba na tomto GLB, neopakuje se navzdy): %d: %s"
              % (len(preskoceno_znama_chyba), preskoceno_znama_chyba))
    print("KANDIDATU k (pre)pocitani razitek: %d" % len(kandidati))
    if not kandidati:
        print("Nic k udelani - vsechny karty s hotovym GLB maji aktualni razitka "
              "(nebo jiz znamou, zaznamenanou chybu).")
        return

    if a.dry_run:
        for pid, name, glb_path, _otisk in kandidati:
            print("  [dry-run] %d - %s (%s)" % (pid, name, os.path.basename(glb_path)))
        return

    uspesne, chybne = [], []
    conn = _conn()
    try:
        for pid, name, glb_path, otisk in kandidati:
            print("--- shop_product %d (%s) ---" % (pid, name))
            try:
                ok, vystup = orazitkuj_kartu(pid, glb_path)
            except subprocess.TimeoutExpired:
                ok, vystup = False, "TIMEOUT (600s)"
            print(vystup)
            if ok:
                uspesne.append(pid)
            else:
                chybne.append(pid)
                print("CHYBA: karta %d se neorazitkovala (viz vystup vyse)." % pid)
                # Bot3 2026-09-23, ostry nalez: bez tohohle by sluzba hlasila
                # "failed" pri KAZDEM dalsim behu navzdy, i kdyz jde o uz
                # zdokumentovanou, spravne odmitnutou chybu (napr. jednotky).
                # Zaznamenat otisk = priste se STEJNY soubor jiz nezkousi.
                zapis_znamou_chybu(conn, pid, otisk)
                _nahlas_novou_chybu(conn, pid, name, vystup)
    finally:
        conn.close()

    print("=== SHRNUTI: %d uspesnych, %d chybnych (z %d kandidatu) ==="
          % (len(uspesne), len(chybne), len(kandidati)))
    # Zamerne BEZ sys.exit(1) i pri chybnych kartach (bot3 2026-09-23):
    # odmitnuti spatneho kandidata je USPESNE chovani automatu (zabranilo
    # zapisu nesmyslnych dat), ne selhani automatu - a chyba uz je zaroven
    # zaznamenana v bot_ukoly/vandr_razitka_chyba_otisk, takze se neztrati.
    # Nenulovy exit zustava vyhrazeny genuinne neocekavanym vyjimkam nize
    # v teto funkci (DB spojeni, atd.) - ty projdou normalne jako
    # nezachycena vyjimka.


if __name__ == "__main__":
    main()
