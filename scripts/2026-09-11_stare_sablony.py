#!/usr/bin/env python3
"""Stare sablony Blenderu v private-files/blender-renders/ - soupis a uklid.

Robert 2026-09-11: *„stare sablony blenderu mazat."* (a predtim „jestli
mluvís o šablonách pro rendering, stare šablony se musí mazat").

VYCHOZI STAV JE "NEDELEJ NIC" - bez `--provest` skript jen vypise soupis.

    api/venv/bin/python3 scripts/2026-09-11_stare_sablony.py            # soupis
    api/venv/bin/python3 scripts/2026-09-11_stare_sablony.py --provest  # smaze

=== CO TO VLASTNE JSOU ZA SOUBORY ===
NEJSOU to Robertovy sablony. Jeho original lezi na Sdilenem disku a
NIKDY se nemeni (jeho pravidlo). Tohle jsou PRACOVNI KOPIE, ktere si
vyrabi `priprav_sablonu()` v scripts/2026-09-09_turntable_render.py:
originalu se dohledaji chybejici obrazky, prepoji a ZABALI dovnitr
(`img.pack()`), aby render na cizim stroji nevysel fialovy. Zabalene
obrazky je nafouknou - original X30-1.blend ma 66.5 MB, kopie 84-251 MB.
Kopie se proto daji kdykoli vyrobit znovu; smazat je znamena nanejvys
prvni render navic o par minut.

Jmeno kopie je `sablona_<klic>.blend`, kde klic =
sha1(abspath(zdroj) + "|" + hdri)[:12]. Kopie AKTUALNI dvojice
(sablona + HDRI z nastaveni) se proto da spocitat, ne hadat.

=== TRI POJISTKY, KAZDA PROTI JINE SKODE ===
1. NIKDY se nesmaze kopie AKTUALNI dvojice. Dohledava se pres
   `shared_drive_pointer.najdi_soubor()`, tedy podle `app_settings` a pri
   mrtvem id podle NAZVU - ne podle adresare. Duvod: Robert soubor pri
   kazde uprave smaze a nahraje novy, takze se `id` meni (2026-09-10
   dvakrat za vecer: 1784 -> 2058 -> 2064), a odvozeny strom
   `shared-drive-named` uz jednou obsahoval rozbity symlink, ktery podle
   nazvu vypadal jako Robertuv soubor a nebyl.
2. NIKDY se nesmaze soubor, ktery ma otevreny bezici proces. Kontroluje
   se TESNE PRED mazanim, ne pri priprave - mezi soupisem a spustenim
   muze render zacit. Kouka se na `/proc/*/cmdline` I na `/proc/*/fd`,
   protoze Blender muze mit soubor otevreny, i kdyz uz neni na prikazove
   radce.
3. Zaloha soupisu jako DOKONCENY krok (fsync + kontrola velikosti) pred
   prvnim smazanim.

=== PROC SE TADY VYPLATI RADSI NECHAT LEZET ===
Sablona je zdroj vzhledu VSECH renderu. Kdyby zmizela ta spravna,
nepoznalo by se to podle chybove hlasky, ale podle toho, ze rendery
zacnou vypadat jinak - a to az za dlouho. Proto radeji o jednu navic
nez o jednu min; misto to nestoji (1.4 GB ze 135 GB volnych).
"""
import argparse
import hashlib
import re
import json
import os
import sys
from datetime import datetime

REPO = "/opt/konfigurator"
RENDERS = os.path.join(REPO, "private-files", "blender-renders")
DRIVE = os.path.join(REPO, "private-files", "shared-drive")
ZALOHA = os.path.join(REPO, "backups", "2026-09-11_stare_sablony_pred_smazanim.json")

sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402

os.environ.update(_env.load_env())
import pymysql  # noqa: E402
import shared_drive_pointer as sdp  # noqa: E402


def _conn():
    e = _env.load_env()
    return pymysql.connect(host=e["DB_HOST"], port=int(e["DB_PORT"]), user=e["DB_USER"],
                           password=e["DB_PASSWORD"], database=e["DB_NAME"],
                           cursorclass=pymysql.cursors.DictCursor)


def aktualni_kopie():
    """Nazev souboru kopie pro AKTUALNI (sablona + HDRI). Vraci (nazev, popis)."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            st_t, sablona, pop_t = sdp.najdi_soubor(
                cur, "render_template_file_id", "render_template_file_name", DRIVE, uzdravit=False)
            st_h, hdri, pop_h = sdp.najdi_soubor(
                cur, "render_hdri_file_id", "render_hdri_file_name", DRIVE, uzdravit=False)
    finally:
        conn.close()
    if st_t != sdp.OK or not sablona:
        raise SystemExit(
            "ODMITNUTO: nejde dohledat aktualni sablonu z nastaveni (%s: %s).\n"
            "Bez ni nevim, kterou kopii NESMIM smazat - radeji nemazu nic." % (st_t, pop_t))
    klic = hashlib.sha1(("%s|%s" % (os.path.abspath(sablona), hdri or "")).encode()).hexdigest()[:12]
    return "sablona_%s.blend" % klic, "%s + %s" % (pop_t, pop_h or "(bez HDRI)")


def pouzivane_soubory():
    """Cesty, ktere ma otevreny nejaky bezici proces. Kontroluje prikazovou
    radku I otevrene deskriptory - Blender muze mit soubor otevreny, i kdyz
    uz neni na prikazove radce."""
    pouzite = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as fh:
                cmd = fh.read().decode("utf-8", "replace").replace("\0", " ")
        except OSError:
            cmd = ""
        for kus in cmd.split():
            if kus.startswith(RENDERS) and kus.endswith((".blend", ".blend1")):
                pouzite.setdefault(os.path.basename(kus), set()).add(pid)
        fd = f"/proc/{pid}/fd"
        try:
            for f in os.listdir(fd):
                try:
                    cil = os.readlink(os.path.join(fd, f))
                except OSError:
                    continue
                if cil.startswith(RENDERS) and cil.endswith((".blend", ".blend1")):
                    pouzite.setdefault(os.path.basename(cil), set()).add(pid)
        except OSError:
            pass
    return {k: sorted(v) for k, v in pouzite.items()}


def soupis():
    chranena, popis_chranene = aktualni_kopie()
    pouzite = pouzivane_soubory()
    radky = []
    for nazev in sorted(os.listdir(RENDERS)):
        if not nazev.endswith((".blend", ".blend1")):
            continue
        cesta = os.path.join(RENDERS, nazev)
        st = os.stat(cesta)
        with open(cesta, "rb") as fh:
            otisk = hashlib.sha256(fh.read()).hexdigest()
        # Kopie vyrobena automaticky ma VZDY tvar `sablona_<12 hex>.blend`
        # (klic = sha1(zdroj|hdri)[:12]). `.blend1` je Blenderova automaticka
        # zaloha SOUROZENCE, takze patri k nemu - `sablona_<hex>.blend1` je
        # taky cache, ne necí rozhodnuti.
        #
        # Cokoli jineho pojmenoval CLOVEK. To uz neni mrtva cache a nemaze se
        # samo - vypise se zvlast, at rozhodne clovek. Vyjimka je
        # `vps_dilna.*`: dilnu Robert 2026-09-10 nechal smazat vyslovne
        # ("smazat dilna", "vps_dilna.blend smazat at te nenapada tam
        # renderovat"), takze jeji zbytek rozhodnuti nepotrebuje.
        rucni = not re.fullmatch(r"sablona_[0-9a-f]{12}\.blend1?", nazev)
        if nazev.startswith("vps_dilna."):
            rucni = False       # uz rozhodnuto driv, viz vyse
        duvod = None
        if nazev == chranena:
            duvod = "kopie AKTUALNI sablony (%s)" % popis_chranene
        elif nazev in pouzite:
            duvod = "pouziva ji bezici proces (pid %s)" % ", ".join(pouzite[nazev])
        if duvod is None and rucni:
            duvod = "ručně pojmenovaný - nevznikl automatickou kopií, rozhodne člověk"
        radky.append({
            "rucni": rucni,
            "nazev": nazev, "bajtu": st.st_size, "MB": round(st.st_size / 1024 / 1024, 1),
            "zmeneno": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "otisk": otisk[:16], "otisk_plny": otisk,
            "nechat": duvod is not None, "duvod": duvod,
        })
    # duplicity podle otisku
    podle = {}
    for r in radky:
        podle.setdefault(r["otisk_plny"], []).append(r["nazev"])
    for r in radky:
        stejne = [n for n in podle[r["otisk_plny"]] if n != r["nazev"]]
        r["shodny_obsah_s"] = stejne
    return radky, chranena, popis_chranene


def vypis(radky, chranena, popis_chranene):
    print(f"Aktuální šablona podle nastavení: {popis_chranene}")
    print(f"Její pracovní kopie (NEMAZAT):    {chranena}\n")
    print(f"{'soubor':<34}{'MB':>8}  {'změněno':<17}{'otisk':<18}stav")
    maze = nechava = 0
    bajtu = 0
    for r in radky:
        stav = ("NECHAT - " + r["duvod"]) if r["nechat"] else "smazat"
        if r["shodny_obsah_s"]:
            stav += "  [bajtově shodný s %s]" % ", ".join(r["shodny_obsah_s"])
        print(f"{r['nazev']:<34}{r['MB']:>8}  {r['zmeneno']:<17}{r['otisk']:<18}{stav}")
        if r["nechat"]:
            nechava += 1
        else:
            maze += 1
            bajtu += r["bajtu"]
    print(f"\nsouborů celkem: {len(radky)} | nechat: {nechava} | SMAZAT: {maze} "
          f"({round(bajtu / 1024 / 1024 / 1024, 2)} GB)")
    rucne = [r["nazev"] for r in radky if r.get("rucni")]
    if rucne:
        print(f"ručně pojmenované (NEMAŽOU se samy, rozhodne člověk): {', '.join(rucne)}")
    ruznych = len({r["otisk_plny"] for r in radky})
    print(f"různých obsahů (podle sha256): {ruznych} z {len(radky)} souborů")
    return maze, bajtu


def main():
    ap = argparse.ArgumentParser(description="Soupis a úklid starých šablon Blenderu")
    ap.add_argument("--provest", action="store_true",
                    help="SMAZAT vypsané soubory (bez toho se jen vypíše soupis)")
    a = ap.parse_args()

    radky, chranena, popis_chranene = soupis()
    maze, bajtu = vypis(radky, chranena, popis_chranene)

    if not a.provest:
        print("\nSOUPIS, nic se nemaže. Smazání spustíš přidáním --provest.")
        return 0
    if not maze:
        print("\nNení co mazat.")
        return 0

    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump({"vytvoreno": datetime.now().isoformat(),
                   "duvod": "Robert 2026-09-11: 'stare sablony blenderu mazat'",
                   "aktualni_sablona": popis_chranene, "chranena_kopie": chranena,
                   "soubory": radky}, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    vel = os.path.getsize(ZALOHA)
    if vel < 500:
        print(f"CHYBA: záloha soupisu {ZALOHA} je podezřele malá ({vel} B) - NEMAŽU NIC.",
              file=sys.stderr)
        return 1
    print(f"\nZáloha soupisu: {ZALOHA} ({vel} B)")

    # POJISTKA: stav "co běží" se čte ZNOVU, těsně před mazáním. Mezi
    # soupisem a spuštěním mohl render začít.
    pouzite_ted = pouzivane_soubory()
    smazano, preskoceno = 0, []
    for r in radky:
        if r["nechat"]:
            continue
        if r["nazev"] in pouzite_ted:
            preskoceno.append("%s (mezitím ji otevřel pid %s)"
                              % (r["nazev"], ", ".join(pouzite_ted[r["nazev"]])))
            continue
        cesta = os.path.join(RENDERS, r["nazev"])
        try:
            os.unlink(cesta)
            smazano += 1
            print(f"  smazáno {r['nazev']} ({r['MB']} MB)")
        except OSError as e:
            preskoceno.append("%s (%s)" % (r["nazev"], e))
    if preskoceno:
        print("\nPŘESKOČENO:")
        for x in preskoceno:
            print("  " + x)

    zbylo = [f for f in os.listdir(RENDERS) if f.endswith((".blend", ".blend1"))]
    print(f"\nKontrola po zásahu: smazáno {smazano}, na disku zbývá {len(zbylo)} souborů:")
    for f in sorted(zbylo):
        print("  " + f)
    if chranena not in zbylo:
        print(f"\nCHYBA: chráněná kopie {chranena} na disku NENÍ!", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
