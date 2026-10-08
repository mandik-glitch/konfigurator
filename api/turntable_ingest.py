"""
Prevzeti hotoveho renderu z GPU do uloziste otocneho nahledu (bot8, 2026-09-11).

PROC TENHLE SOUBOR VZNIKL
-------------------------
Retez otocneho nahledu mel dosud DIRU presne uprostred:

    scena (scene.html)  -> /turntable/frames -> /turntable/commit -> e-shop
    GPU (render_worker) -> <job>.frames/     -> ??? ----------------> nic

`render_worker_tt_result` (api/render_worker.py) rozbali ZIP od agenta do
`<job>.frames/`, napise do stavu ulohy `state="done"` a tim to koncilo. Nikdo
soubory nikam neprebiral - endpointy /turntable/frames a /turntable/commit
vola VYHRADNE prohlizec (scene.html). Vysledek k 2026-09-11: 40 hotovych sad
snimku na disku a v `product_turntable_frames` NULA radku. Uloha pritom
svitila zelene "hotovo", takze to navenek vypadalo jako uspech - to je horsi
nez chyba, protoze chyba se aspon hlasi.

CO TENHLE MODUL DELA
--------------------
Vezme `<job>.frames/` (snimky + manifest.json od render skriptu), zvaliduje
ho STEJNYM kodem jako upload z prohlizece (`zkontroluj_snimek`), zapise ho
STEJNYM kodem (`ulozit_snimky`) a commitne ho STEJNYM kodem (`commit_batch`).
Zadna druha implementace teze veci - kdyz se zmeni pravidla davky, zmeni se
na jednom miste pro oba vstupy.

PREDNI AZIMUT SE NEDOSAZUJE
---------------------------
Manifest MUSI nest `camera.front_azimuth_deg`. Kdyz chybi, ingest skonci
chybou a snimky necha lezet - NEDOSADI globalnich 270. Duvod je konkretni:
manifesty uloh na disku maji front=90, takze tise dosazenych 270 by posunulo
celou 270stupnovou vysec a commit by hlasil 54 ze 162 snimku chybejicich,
prestoze davka je kompletni. Kdo snimky vyrobil, ten jediny vi, kam se
kamera divala; server to hadat nesmi. (Tataz podminka plati od 2026-09-11 i
pro upload z prohlizece - viz turntable_frames_upload.)

PAMET
-----
Dva pruchody po disku: prvni VSECHNO zvaliduje (bajty zahodi, nechá si jen
metadata), druhy je po davkach znovu nacte a zapise. Zachovava to pravidlo
"nic se nezapise, dokud nesedi cela sada", aniz by se 162 souboru drzelo
naraz v pameti.
"""
import hashlib
import json
import os
import re
import shutil

from app import get_conn
# ZAMERNE `import turntable`, ne `from turntable import ...`: app.py tenhle
# modul importuje hned za turntable kvuli fail-fast pri startu, takze kdyz
# neco naimportuje `turntable` DRIV nez `app` (skripty, testy), je turntable
# v tu chvili jeste rozestaveny a jmenovity import by spadl na kruhovou
# zavislost. Modulovy objekt se naveze vzdy, atributy se ctou az za behu.
import turntable as tt

FRAME_FILE_RE = re.compile(r"^(frame_e-?\d{1,2}_a\d{1,3}_t\d{4})\.jpg$")
ZAPIS_PO = 24  # kolik snimku se najednou nacte a zapise ve druhem pruchodu


class IngestError(Exception):
    """Ingest se nepovedl. Snimky zustavaji na disku, nic se nesmazalo."""


def _kamera_z_manifestu(man):
    """Kamera z manifestu render skriptu -> tvar, ktery bere tt._validate_camera.

    Render skript pise `fov_deg`/`box_min`/`box_max`, ulozene camera.json
    (a scena, ktera z nej pak staví pohled) zna `fov`/`bbox_min`/`bbox_max`.
    Neprelozene klice by tt._validate_camera tise zahodil a skok z nahledu do
    sceny by prisel o ohnisko - proto prekladame tady, ne "nejak pozdeji".
    """
    cam = dict(man.get("camera") or {})
    for zdroj, cil in (("fov_deg", "fov"), ("box_min", "bbox_min"), ("box_max", "bbox_max")):
        if zdroj in cam and cil not in cam:
            cam[cil] = cam.pop(zdroj)
    return tt._validate_camera(cam)


def _uzivatel_sestavy(assembly_id):
    """Do auditu se ingest podepise vlastnikem sestavy, ne nulou.

    `audit_log.user_id` ma FK na `app_users` - 0 by ho porusila a shodila
    by commit az uplne na konci, po zapsanych snimcich. NULL je povoleny,
    takze neznamy vlastnik = NULL, ne vymysleny uzivatel.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT created_by FROM product_assemblies WHERE id=%s", (assembly_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    return (row or {}).get("created_by")


def _zapsat_render_razitka_otisk(shop_product_id):
    """Po uspesnem commitu davky (Vandr karta) ulozi otisk PRAVE
    AKTIVNIHO `vandr_razitka_json` - stejny princip jako
    `vandr_razitka_glb_otisk` (sql/2026-09-23_shop_products_vandr_
    razitka.sql), jen o krok dal v retezci (GLB -> razitka -> RENDER).

    Bot4/bot3, 2026-09-23: uzavira mezeru, kterou 2026-09-14_render_
    auto_dispatch.py cestne priznaval u nativni vetve ("NEDETEKUJE
    staleness JIZ vyrenderovane sestavy") - u Vandr vetve se skutecne
    projevila (karta 4903: aktivni davka z doby PRED velkym prepisem
    algoritmu razitek, Robert primo "ma prilis mnoho razitek").
    `2026-09-23_vandr_render_auto_dispatch.py::kandidati()` pak muze
    porovnat tenhle otisk se SOUCASNYM `vandr_razitka_json` a poznat
    zastaralou davku, i kdyz uz "ma aktivni snimek".

    Hashuje se RAW retezec z DB (ne znovu-serializovany JSON) - vyhne
    se falesne neshode z poradi klicu. Karta bez `vandr_razitka_json`
    (typicky NENI Vandr, nebo jeste nema razitka spoctena) se tise
    preskoci - `shop_product_id=None` (nativni sestavy) taky."""
    if shop_product_id is None:
        return
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT vandr_razitka_json FROM shop_products WHERE id=%s", (shop_product_id,))
            row = cur.fetchone()
            razitka_json = (row or {}).get("vandr_razitka_json")
            otisk = hashlib.sha256(razitka_json.encode("utf-8")).hexdigest() if razitka_json else None
            cur.execute("UPDATE shop_products SET vandr_render_razitka_otisk=%s WHERE id=%s",
                        (otisk, shop_product_id))
        conn.commit()
    finally:
        conn.close()


def _precti_manifest(frames_dir):
    cesta = os.path.join(frames_dir, "manifest.json")
    try:
        with open(cesta, "r", encoding="utf-8") as fh:
            man = json.load(fh)
    except OSError as e:
        raise IngestError(f"Manifest nelze precist ({cesta}): {e}")
    except ValueError as e:
        raise IngestError(f"Manifest neni platny JSON ({cesta}): {e}")
    if not isinstance(man, dict):
        raise IngestError("Manifest musi byt objekt.")
    return man


def _predni_azimut(man):
    """POVINNY udaj - viz hlavicka modulu. Zadny fallback."""
    cam = man.get("camera")
    front = cam.get("front_azimuth_deg") if isinstance(cam, dict) else None
    if front is None:
        raise IngestError(
            "Manifest neobsahuje camera.front_azimuth_deg. Ingest predni azimut NEDOSAZUJE "
            "- bez nej nelze urcit, ktera 270stupnova vysec se vlastne vyrenderovala. "
            "Doplnit ho musi render skript (scripts/2026-09-09_turntable_render.py)."
        )
    try:
        front = int(front) % 360
    except (TypeError, ValueError):
        raise IngestError(f"camera.front_azimuth_deg neni cislo: {front!r}")
    if front % tt.STEP_DEG != 0:
        raise IngestError(f"camera.front_azimuth_deg={front} neni nasobek {tt.STEP_DEG}.")
    return front


def ingest_frames_dir(frames_dir, assembly_id, shop_product_id, user_id=None, dry_run=False,
                      commit=True, libovolny_azimut=False):
    """Prevezme `<job>.frames/` do uloziste otocneho nahledu.

    Vraci slovnik se zpravou (`upload_ok`, `commit_ok`, pocty, pripadne
    `commit_error`). Vyhazuje IngestError, kdyz se neda pokracovat -
    volajici ma pak na disku porad vsechno, co agent poslal.

    `commit=False` = snimky se ZAPISOU (is_active=0), ale davka se
    NEAKTIVUJE - na e-shopu se tim nezmeni vubec nic. Zavedeno 2026-09-11
    (bot8 pro bot3) na situaci "uz vyrenderovano, ale jeste neschvaleno":
    zachrani to hodiny GPU, aniz by se cokoli zverejnilo driv, nez to
    nekdo videl. Davka pak ceka na `commit_davku()` niz. Slozka snimku
    se v tomhle rezimu NEMAZE - je porad jedinym zdrojem kamery pro
    pozdejsi commit.
    """
    if not os.path.isdir(frames_dir):
        raise IngestError(f"Slozka snimku neexistuje: {frames_dir}")
    man = _precti_manifest(frames_dir)
    front = _predni_azimut(man)
    azimuths_ok = tt._azimuths_for_front(front)
    if libovolny_azimut and not commit:
        # testovaci snimek s presnym azimutem z panelu (Robert 2026-09-28:
        # "musi udelat uhel jaky mu napisu") - davka se nikdy neaktivuje
        azimuths_ok = set(range(360))
    camera = _kamera_z_manifestu(man)

    # --- 1. pruchod: zvalidovat uplne vsechno, bajty zahodit -------------
    soubory = sorted(n for n in os.listdir(frames_dir) if FRAME_FILE_RE.match(n))
    if not soubory:
        raise IngestError(f"Ve slozce {frames_dir} nejsou zadne snimky prstence (frame_*.jpg).")
    popisy = []
    chyby = []
    for nazev in soubory:
        cesta = os.path.join(frames_dir, nazev)
        pole = FRAME_FILE_RE.match(nazev).group(1)
        try:
            with open(cesta, "rb") as fh:
                elev, azim, tier, raw, w, h = tt.zkontroluj_snimek(pole, fh.read, azimuths_ok)
        except (ValueError, OSError) as e:
            chyby.append(f"{nazev}: {e}")
            continue
        popisy.append({"nazev": nazev, "elev": elev, "azim": azim, "tier": tier,
                       "w": w, "h": h, "bytes": len(raw)})
    if chyby:
        raise IngestError(f"Vadne snimky ({len(chyby)} z {len(soubory)}): " + "; ".join(chyby[:5]))

    zprava = {
        "frames_dir": frames_dir, "front_azimuth_deg": front,
        "found": len(popisy), "expected": tt.EXPECTED_FRAME_COUNT,
        "complete": len(popisy) == tt.EXPECTED_FRAME_COUNT,
        "bytes": sum(p["bytes"] for p in popisy),
        "camera_keys": sorted(camera or {}),
        "dry_run": bool(dry_run),
        "upload_ok": False, "commit_ok": False,
    }
    if dry_run:
        # Nasucho: rekne PRESNE to same, co by rekl ostry beh, jen nic
        # nezapise. Dela se tim overitelnou i nekompletni sada na disku.
        zprava["note"] = ("nasucho - nic se nezapsalo"
                          if zprava["complete"] else
                          f"nasucho - sada je NEKOMPLETNI ({len(popisy)}/{tt.EXPECTED_FRAME_COUNT}), "
                          f"ostry beh by ji nahral, ale commit by ji odmitl")
        return zprava

    # --- 2. pruchod: zapis po davkach ------------------------------------
    batch = tt._new_batch_id()
    os.makedirs(tt._batch_dir(shop_product_id, batch), exist_ok=True)
    tt._write_batch_json(shop_product_id, batch, "front.json", {"front_azimuth_deg": front})
    ulozeno, total = 0, 0
    for i in range(0, len(popisy), ZAPIS_PO):
        items = []
        for p in popisy[i:i + ZAPIS_PO]:
            with open(os.path.join(frames_dir, p["nazev"]), "rb") as fh:
                items.append((p["elev"], p["azim"], p["tier"], fh.read(), p["w"], p["h"]))
        _, total = tt.ulozit_snimky(shop_product_id, assembly_id, batch, items)
        ulozeno += len(items)
    zprava.update({"upload_ok": True, "batch": batch, "uploaded": ulozeno, "batch_total": total})

    # --- commit ----------------------------------------------------------
    if not commit:
        zprava.update({
            "commit_ok": False, "commit_skipped": True,
            "note": ("snimky zapsany jako is_active=0, davka NENI aktivni - "
                     "na e-shopu se nezmenilo nic; aktivuje ji az commit_davku('%s')" % batch),
        })
        return zprava
    if not user_id:
        user_id = _uzivatel_sestavy(assembly_id)
    payload, kod = tt.commit_batch(assembly_id, shop_product_id, batch, camera, front, user_id)
    zprava["commit_status"] = kod
    if kod == 200:
        zprava.update({"commit_ok": True, "commit": payload})
        _zapsat_render_razitka_otisk(shop_product_id)
        # Archiv na Sdileny disk (bot16, api/turntable_archiv.py) - TRVALA
        # kopie masteru mimo tenhle server, pro sestavy ktere jsou schvalene
        # a maji aktualni razitka. Modul sam rozhodne, jestli davka na archiv
        # ma narok (vraci "nema_narok", neni to chyba) a NIKDY nevyhazuje
        # vyjimku - volat se muze bezpecne primo tady.
        try:
            import turntable_archiv
            zprava["archiv"] = turntable_archiv.archivuj_davku(assembly_id, shop_product_id, batch)
        except Exception as e:  # noqa: BLE001 - archiv nesmi shodit uspesny prijem davky
            zprava["archiv"] = {"stav": "chyba", "popis": f"archiv se nespustil: {e}"}
        # Po uspesnem commitu je `<job>.frames/` uz jen duplikat toho, co lezi
        # v ulozisti otocneho nahledu. Nikdo ji dosud neuklizel (_cleanup_job
        # umi jen os.remove, na adresar neplati), takze na disku zustavalo
        # 40 sirotcich sad. Mazeme JEN po uspechu - po neuspechu je to jediny
        # zachranny bod a nekolik hodin renderu na GPU.
        try:
            shutil.rmtree(frames_dir)
            zprava["frames_dir_removed"] = True
        except OSError as e:
            zprava["frames_dir_removed"] = f"nepodarilo se smazat: {e}"
    else:
        # Nahrane snimky ZUSTAVAJI (is_active=0) - dokoncit je muze dalsi
        # davka nebo rucni commit; mazat je tady by zahodilo hodiny renderu.
        zprava["commit_error"] = payload.get("error") or payload
    return zprava


def commit_davku(frames_dir, assembly_id, shop_product_id, batch, user_id=None):
    """Aktivuje davku, ktera uz je nahrana (ingest s commit=False).

    Kameru i predni azimut bere z TEHOZ manifestu, jakym se davka nahrala -
    proto se slozka snimku v rezimu bez commitu nemaze. Vraci (payload, kod)
    stejne jako `commit_batch`.
    """
    man = _precti_manifest(frames_dir)
    front = _predni_azimut(man)
    camera = _kamera_z_manifestu(man)
    if not user_id:
        user_id = _uzivatel_sestavy(assembly_id)
    payload, kod = tt.commit_batch(assembly_id, shop_product_id, batch, camera, front, user_id)
    if kod == 200:
        _zapsat_render_razitka_otisk(shop_product_id)
        try:
            import turntable_archiv
            turntable_archiv.archivuj_davku(assembly_id, shop_product_id, batch)
        except Exception:
            pass  # archiv nesmi shodit uspesny commit; sam si loguje
        try:
            shutil.rmtree(frames_dir)
        except OSError:
            pass
    return payload, kod


def ingest_job(job, assembly_id, shop_product_id, user_id=None, dry_run=False):
    """Totez podle ID ulohy - slozka se odvodi z RENDER_OUT_DIR."""
    import blender_render as br
    return ingest_frames_dir(os.path.join(br.RENDER_OUT_DIR, f"{job}.frames"),
                             assembly_id, shop_product_id, user_id, dry_run=dry_run)


if __name__ == "__main__":  # rucni prevzeti/kontrola sady z prikazove radky
    import argparse
    ap = argparse.ArgumentParser(description="Prevzeti sady snimku z GPU do otocneho nahledu.")
    ap.add_argument("frames_dir", help="slozka <job>.frames")
    ap.add_argument("--assembly", type=int, required=True)
    ap.add_argument("--product", type=int, required=True)
    ap.add_argument("--user", type=int, default=None,
                    help="ID uzivatele do auditu (vychozi: vlastnik sestavy)")
    ap.add_argument("--dry-run", action="store_true", help="jen zkontrolovat, nic nezapsat")
    ap.add_argument("--bez-commitu", action="store_true", dest="bez_commitu",
                    help="snimky zapsat (is_active=0), ale davku NEAKTIVOVAT - "
                         "na e-shopu se nezmeni nic, ceka se na schvaleni")
    ap.add_argument("--commit-davku", default=None, metavar="BATCH",
                    help="jen aktivovat uz nahranou davku (po schvaleni)")
    a = ap.parse_args()
    try:
        if a.commit_davku:
            payload, kod = commit_davku(a.frames_dir, a.assembly, a.product, a.commit_davku, a.user)
            print(json.dumps({"commit_status": kod, "commit": payload}, ensure_ascii=False, indent=1))
            raise SystemExit(0 if kod == 200 else 1)
        print(json.dumps(ingest_frames_dir(a.frames_dir, a.assembly, a.product, a.user,
                                           dry_run=a.dry_run, commit=not a.bez_commitu),
                         ensure_ascii=False, indent=1))
    except IngestError as e:
        raise SystemExit(f"CHYBA: {e}")
