"""Priznak KOLIZNICH UHELNIKU na sestave - prepocet a zapis.

Robert 2026-09-11 (pres bot3): "oznac mi ve scene ty sestavy resp jejich
nazev cervenou barvou, tak budeme indikovat sestavy ktere maji kolizi a ja
se na ne podivam." Tyz udaj cte i prehledova tabulka na dashboardu, proto
se uklada JEDNOU pro obojí (sloupce `kolize_pocet` / `kolize_detail` /
`kolize_checked_at`, migrace sql/2026-09-11e, bot10).

=== CO PRIZNAK SLIBUJE A CO NE ===
Merí se KOLIZNI UHELNIKY, ne kolize obecne - uhelnik proti ostatnim dilum
sestavy. NEmerí se profil proti profilu ani eurobox proti nosniku. Proto se
sloupec jmenuje "Kolizni uhelniky" a ne "Kolize" (bot3 2026-09-11: "zelena,
ktera znamena 'uhelniky jsou v poradku', ale tvari se jako 'sestava je v
poradku', je presne ten druh polopravdy, co nas dnes stal den").

Rozsirit kontrolu na VSECHNY dvojice dilu je samostatne zadani, ne
prepinac - zmereno 2026-09-11: 12.6 s na sestavu misto 3.8 s na cely
katalog, a hlavne by to skoro cele byly FALESNE poplachy. Z 99 "kolizi"
na osmi sestavach bylo 21x zaslepka v prednim svislici, 21x zaslepka v
capu a 12x eurobox v nosniku - tedy dily, ktere se prekryvat MAJI.
Pokryti vsech dilu tedy potrebuje model "ktere dvojice smi sdilet hmotu",
ne vic vypocetniho casu.

=== TRI STAVY, KTERE SE NESMI SLIT ===
    kolize_pocet IS NULL   nikdy nemereno         -> v UI NIKDY zelene
    kolize_pocet = 0       zmereno a cisto
    kolize_pocet > 0       pocet koliznich uhelniku
Tatáž kontrola letos TRIKRAT po sobe ohlasila "0 kolizi" z duvodu, ktery
s cistotou nesouvisel (chybejici GLB, zamerne preskakovani partnera,
natvrdo psana mapa). "0 nalezeno" je nerozeznatelne od "nic jsem
neporovnal", pokud to radek nerozlisi - proto ten NULL.

=== JAK PRIZNAK NEZASTARA ===
Dva mechanismy, zamerne oba:
  1. pri zalozeni sestavy - prepocet te jedne, ~0.16 s, synchronne
     (`data` se v celem API zapisuje jen pri INSERT; scena pri ulozeni
     zaklada NOVOU sestavu, starou neupravuje)
  2. casovac `konfigurator-kolize-uhelniky.timer` - prepocet CELEHO
     katalogu, 3.8 s. Boti zapisuji `data` primo do DB mimo API, takze
     hacek v endpointu je sam o sobe deravy.

ZAMYSLENO BYLO TRETI, LEPSI: DB trigger BEFORE UPDATE, ktery by priznak
shodil na NULL pokazde, kdyz se zmeni `data` - to by neslo obejit
zapomenutim. NEJDE to: uzivatel `konfigurator_app` nema SUPER a binarni
log je zapnuty (MySQL 1419). Povolovat kvuli tomu `log_bin_trust_function_
creators` je oslabeni serveru kvuli jednomu priznaku, takze se to neudelalo
a pojistkou je casovac. Kdyby nekdy SUPER byl, trigger je lepsi reseni.

Take se zvazovalo poveset zneplatneni na `zrcadli_sestavu_na_disk()`, kterou
dnes volaji vsichni zapisovaci geometrie. Neudelalo se to, protoze ma dve
diry: (1) pri neodvoditelne znacce se vraci DRIV (`return None`), takze by
zneplatneni u takovych sestav tise vypadlo; (2) vola ji i
scripts/2026-09-09_zrcadlo_sestav_backfill.py, ktery geometrii NEMENI.
"""
import json
import os
import subprocess
import tempfile
from datetime import datetime

REPO = "/opt/konfigurator"
SWEEP = os.path.join(REPO, "scripts", "2026-09-11_sweep_kolizni_uhelniky.cjs")
NODE = "node"
# Cely katalog bezi 3.8 s, jedna sestava 0.16 s. Limit je hodne nad tim -
# ma chytit zaseknuti, ne pomalost.
TIMEOUT_S = 180


class PrepocetSelhal(RuntimeError):
    """Prepocet nedobehl duveryhodne. Priznak se v tom pripade NEZAPISUJE -
    stary udaj je porad lepsi nez novy vymysleny."""


def _spocitej(radky):
    """Pusti sweep v rezimu --jen-verdikt nad danymi radky sestav.

    Vraci dict z vystupu sweepu. Kdyz sweep skonci nenulove (nepodarilo se
    zmerit geometrii nejakeho dilu, neporovnal se ani jeden par...), vyhodi
    PrepocetSelhal - radeji nic nez falesne cisto.
    """
    if not radky:
        return {"sestavy": {}}
    vstup = vystup = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([{"id": r["id"], "name": r["name"],
                        "data": r["data"] if isinstance(r["data"], str) else json.dumps(r["data"])}
                       for r in radky], f, ensure_ascii=False)
            vstup = f.name
        vystup = vstup + ".out.json"
        p = subprocess.run([NODE, SWEEP, vstup, vystup, "--jen-verdikt"],
                           capture_output=True, text=True, timeout=TIMEOUT_S, cwd=REPO)
        if p.returncode != 0:
            raise PrepocetSelhal(
                f"sweep skoncil kodem {p.returncode}; NEZAPISUJI.\n{p.stderr[-2000:]}")
        if not os.path.exists(vystup):
            raise PrepocetSelhal("sweep nevytvoril vystupni soubor; NEZAPISUJI.")
        with open(vystup, encoding="utf-8") as f:
            return json.load(f)
    except subprocess.TimeoutExpired as e:
        raise PrepocetSelhal(f"sweep nedobehl do {TIMEOUT_S}s; NEZAPISUJI.") from e
    finally:
        for c in (vstup, vystup):
            if c and os.path.exists(c):
                os.unlink(c)


def prepocti(cur, ids=None, logger=None):
    """Prepocita priznak a zapise ho. `ids=None` = cely katalog.

    Bere HOTOVY kurzor a nezaklada vlastni spojeni - volajici si rizeni
    transakce drzi sam (stejny duvod jako u zrcadli_sestavu_na_disk:
    vlastni spojeni uvnitr cizi transakce = tichy rollback).
    Vraci dict {zapsano, s_kolizi, cistych}.
    """
    if ids is not None:
        ids = [int(i) for i in ids]
        if not ids:
            return {"zapsano": 0, "s_kolizi": 0, "cistych": 0}
        fmt = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT id, name, data FROM product_assemblies WHERE id IN ({fmt})", ids)
    else:
        cur.execute("SELECT id, name, data FROM product_assemblies")
    radky = cur.fetchall()
    vysledek = _spocitej(radky)
    sestavy = vysledek.get("sestavy") or {}

    hlavicka = {k: vysledek.get(k) for k in ("mereno", "pravidlo", "rezim", "nastroj", "kontroluje")}
    ted = datetime.now()
    zapsano = s_kolizi = cistych = 0
    for r in radky:
        z = sestavy.get(str(r["id"]))
        if z is None:
            # Sestava, kterou sweep neprosel (napr. prazdna `data`). Priznak
            # se NEPREPISUJE na 0 - "nemereno" se nesmi tvarit jako "cisto".
            continue
        detail = dict(hlavicka)
        detail["uhelniku"] = z.get("uhelniku", 0)
        detail["kusy"] = z.get("kusy", [])
        cur.execute(
            "UPDATE product_assemblies SET kolize_pocet=%s, kolize_detail=%s, "
            "kolize_checked_at=%s WHERE id=%s",
            (z["pocet"], json.dumps(detail, ensure_ascii=False), ted, r["id"]))
        zapsano += 1
        if z["pocet"]:
            s_kolizi += 1
        else:
            cistych += 1
    if logger:
        logger.info("kolize_priznak: zapsano %s sestav (s kolizi %s, cistych %s)",
                    zapsano, s_kolizi, cistych)
    return {"zapsano": zapsano, "s_kolizi": s_kolizi, "cistych": cistych}
