"""render_hdri.py - vyber HDRI mapy pro automaticke rendery.

Robert 2026-09-09: "chci mit moznost podle vyslednych renderu preklikavat
ktery hdri se pouzije priste" + "kdyz bude v adresari 20 hdri souborů
musi se mi nabidnout vsechny abch si vybral pro dalsi automaticke
rendery dokud to zase nezmenim".

JAK TO FUNGUJE (a proc takhle):

Robertuv .blend (Sdileny disk, napr. Rendering/X30/X30-1.blend) je zdroj
pravdy pro cely vzhled renderu. Jeho World ma vlastni HDRI. Prepnuti
mapy se proto NEDELA zapisem do jeho souboru - to by porusilo pravidlo
"cizi soubor se NIKDY nemeni" (PRODUKTOVE_RENDERY.md) a navic by se to
pralo s tim, ze si soubor kdykoli prepise vlastni verzi.

Misto toho se ulozi jen VOLBA (id souboru na Sdilenem disku) a vymena
probehne az pri priprave kopie sablony pro konkretni render - viz
scripts/2026-09-09_vps_dilna/priprav_sablonu.py, argument s cestou k
HDRI. Kopie je stejne potreba kvuli zabaleni obrazku, takze vymena nic
navic nestoji.

Prazdna volba (NULL) = pouzije se HDRI, ktere ma Robert ulozene ve svem
souboru. To je vychozi stav.

Rotace kolem svisle osy (bot16, 2026-09-12, zadani bot3/bot4 - Robert
potvrdil "120 stupnu je od ted preferovany uhel pro vsechny dalsi
sestavy"): stejny princip jako vyber souboru vyse, jen pro
`scripts/2026-09-09_vps_dilna/priprav_sablonu.py`'s Mapping uzel
(viz `--hdri-rotace-deg` v scripts/2026-09-09_turntable_render.py).
Predtim se resilo jen jednorazovym prepnutim per-render (bot4 rucne),
tohle je TRVALY vychozi uhel - jednorazovy --hdri-rotace-deg na
prikazove radce porad muze prebit i tohle, presne jako --hdri prebiji
vyber souboru.
"""
import json
import os
import re
import sys

from flask import jsonify, request

from app import app, get_conn, admin_required, log_audit, current_user
from drive import DRIVE_FILES_DIR
import shared_drive_pointer as sdp

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import _render_prirazeni_lib as _prirazeni  # noqa: E402

# Stejne pripony jako rendering_settings.HDRI_EXT - zamerne se
# neimportuje, aby tenhle modul nezavisel na tom (jina agenda: tam jde o
# nahled nabidky ve scene, tady o produktove rendery).
HDRI_EXT = (".hdr", ".exr")
# Karta pro jednorazove testovaci nahledy HDRI (Robert pres bot3,
# 2026-09-24) - Vandr, uz ma cerstva razitka a overenou geometrii z
# dnesnich fixu, dobry reprezentativni vzorek. Kdyby se mel test presunout
# na jinou kartu, staci zmenit tuhle jednu konstantu.
# Robert 2026-09-28 vecer: "renderovaci testovaci sestava: VD-2e1bc1a8-3da6-410f-a150-3a1725080050"
# (Regalova vestavba - Renault Master L2H2), driv 4910 Ford Transit L3H3 FWD.
TEST_RENDER_SHOP_PRODUCT_ID = 4474
NASTAVENI_KLIC = "render_hdri_file_id"
# Nazev souboru vedle id (bot9, 2026-09-11): Robert soubor pri uprave smaze
# a nahraje novy, takze samotne id vysi do prazdna - viz shared_drive_pointer.
NASTAVENI_KLIC_NAZEV = "render_hdri_file_name"
NASTAVENI_KLIC_ROTACE = "render_hdri_rotace_deg"
# Robert 2026-09-28: "modern_buildings < zakaz pouzivani" - nejde vybrat
# trvale, pro test ani v panelu prirazeni. Stejny seznam hlida
# scripts/2026-09-09_turntable_render.py primo pri renderu (ZAKAZANE_HDRI).
ZAKAZANE_HDRI = ("modern_buildings",)
CHYBA_ZAKAZANA_HDRI = "HDRI modern_buildings je zakázaná, nepoužívat."


def _je_zakazana_hdri(filename):
    return any(z in (filename or "").lower() for z in ZAKAZANE_HDRI)


def _aktivni_id(cur):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (NASTAVENI_KLIC,))
    row = cur.fetchone()
    if not row or not row["setting_value"]:
        return None
    try:
        return int(row["setting_value"])
    except (TypeError, ValueError):
        return None


def aktivni_hdri_cesta(cur):
    """Cesta k vybrane HDRI mape NA DISKU, nebo None (= nechat world tak,
    jak ho ma Robert ve svem souboru). Vola se z renderovaci cesty.

    Od 2026-09-11 pres shared_drive_pointer: kdyz je ulozene `id` mrtve
    (Robert soubor smazal a nahral znovu), dohleda se podle NAZVU a
    ukazatel se uzdravi. Stav NENALEZENO (vybrano, ale nedohledatelne)
    vraci None stejne jako "nic nevybrano" - kdo potrebuje rozlisit, at
    vola primo `sdp.najdi_soubor`; renderovaci skript to tak dela a
    v tom pripade koncí hlasite."""
    _stav, cesta, _popis = sdp.najdi_soubor(
        cur, NASTAVENI_KLIC, NASTAVENI_KLIC_NAZEV, DRIVE_FILES_DIR)
    return cesta


def _cesta_slozky(cur, folder_id):
    """Citelna cesta 'Rendering / HDRi' pro zobrazeni v seznamu."""
    casti = []
    videno = set()
    while folder_id is not None and folder_id not in videno:
        videno.add(folder_id)
        cur.execute("SELECT name, parent_folder_id FROM shared_drive_folders WHERE id=%s", (folder_id,))
        row = cur.fetchone()
        if not row:
            break
        casti.append(row["name"])
        folder_id = row["parent_folder_id"]
    return " / ".join(reversed(casti)) if casti else "Kořen disku"


@app.get("/api/admin/render-hdri")
@admin_required
def render_hdri_list():
    """VSECHNY HDRI mapy na Sdilenem disku (Robert: "musi se mi nabidnout
    vsechny") - nejen z jedne slozky, aby to fungovalo i kdyz si je casem
    prerovna jinam."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            aktivni = _aktivni_id(cur)
            cur.execute("SELECT id, filename, folder_id, size_bytes FROM shared_drive_files ORDER BY filename")
            vsechny = cur.fetchall()
            mapy = []
            for r in vsechny:
                if os.path.splitext(r["filename"])[1].lower() not in HDRI_EXT:
                    continue
                mapy.append({
                    "id": r["id"],
                    "filename": r["filename"],
                    "size_bytes": r["size_bytes"],
                    "folder": _cesta_slozky(cur, r["folder_id"]),
                    "active": r["id"] == aktivni,
                })
    finally:
        conn.close()
    return jsonify({"files": mapy, "active_id": aktivni})


@app.put("/api/admin/render-hdri")
@admin_required
def render_hdri_set():
    body = request.get_json(silent=True) or {}
    file_id = body.get("file_id")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if file_id in (None, "", 0):
                popis = "výchozí (z Blender souboru)"
            else:
                try:
                    file_id = int(file_id)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné file_id."}), 400
                cur.execute("SELECT id, filename FROM shared_drive_files WHERE id=%s", (file_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"error": "Soubor na Sdíleném disku nenalezen."}), 404
                if os.path.splitext(row["filename"])[1].lower() not in HDRI_EXT:
                    return jsonify({"error": "Vybraný soubor není HDRI mapa (.hdr/.exr)."}), 400
                if _je_zakazana_hdri(row["filename"]):
                    return jsonify({"error": CHYBA_ZAKAZANA_HDRI}), 400
                popis = row["filename"]
            # Uklada se id I nazev - podle nazvu se ukazatel dohleda, az
            # Robert soubor vymeni za novy (viz shared_drive_pointer).
            sdp.uloz_ukazatel(cur, NASTAVENI_KLIC, NASTAVENI_KLIC_NAZEV,
                              file_id, popis if file_id not in (None, "", 0) else "")
        conn.commit()
    finally:
        conn.close()
    user = current_user()
    log_audit(user["id"] if user else None, "update", "render_hdri", None,
              {"hdri": popis})
    return jsonify({"status": "ok", "active": popis})


@app.post("/api/admin/render-hdri/<int:file_id>/test-render")
@admin_required
def render_hdri_test_render(file_id):
    """Zaradi CELOU testovaci otocku (54 snimku, --bez-commitu - Robert:
    "Renderovou otočku chci vidět") testovaci karty s touhle HDRI mapou
    jako PER-JOB override - `app_settings` (trvala volba) se vubec
    nedotyka, viz WORKFLOW.md pravidlo 50 (Robert 2026-09-24, po
    incidentu s primym zapisem trvale volby). Trva desitky minut (cela
    produkcni davka na GPU), ne desitky sekund.

    Tenhle endpoint bezi jako www-data a NEMA (schvalne) pristup k
    renderovacimu klici - jen VLOZI radek do render_hdri_test_requests.
    Skutecne zarazeni do fronty dela samostatny root-owned automat
    (scripts/2026-09-24_render_hdri_test_dispatch.py).

    Volitelne materialove prekryvy (Robert 2026-09-28: "primo v tom
    disku/adminu chci priradovat material") - stejny princip jako HDRI,
    jen PER-JOB (nikdy trvala volba): alu_material/alu_knihovna_soubor
    (--alu-material/--vd-knihovna), klt_material/klt_knihovna_soubor
    (--klt-material, celo supliku - JINY material nez box KLT/Multibox),
    cub_seda_tmava_sila (0-1, sedy plast police). Knihovna = presny
    nazev souboru na Sdilenem disku (najde ho az dispatch automat)."""
    telo = request.get_json(silent=True) or {}

    def _txt(klic, max_delka=120):
        v = telo.get(klic)
        if v is None:
            return None
        v = str(v).strip()
        return v[:max_delka] if v else None

    alu_material = _txt("alu_material")
    alu_knihovna = _txt("alu_knihovna_soubor", 255)
    klt_material = _txt("klt_material")
    klt_knihovna = _txt("klt_knihovna_soubor", 255)
    ostatni_knihovna = _txt("ostatni_knihovna_soubor", 255)

    def _cislo(klic, lo, hi, popis):
        if telo.get(klic) in (None, ""):
            return None, None
        try:
            v = float(telo[klic])
        except (TypeError, ValueError):
            return None, (jsonify({"error": "%s musí být číslo." % popis}), 400)
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return v, None

    cub_seda_tmava_sila, chyba = _cislo("cub_seda_tmava_sila", 0.0, 1.0, "cub_seda_tmava_sila")
    if chyba:
        return chyba
    alu_ao_sila, chyba = _cislo("alu_ao_sila", 0.0, 1.0, "alu_ao_sila")
    if chyba:
        return chyba
    hdri_sila, chyba = _cislo("hdri_sila", 0.0, None, "hdri_sila")
    if chyba:
        return chyba
    hdri_rotace_deg, chyba = _cislo("hdri_rotace_deg", 0.0, 359.9, "hdri_rotace_deg")
    if chyba:
        return chyba

    # Kde renderovat (Robert 2026-09-29: "nastav mi tam moznost renderovat u
    # mě"): prazdne = vychozi GPU stanice; jiny stroj (notebook) jen kdyz je
    # ONLINE - jinak hlasita chyba hned, ne uloha, ktera by tise cekala.
    # Plati jen pro testovaci render, produkce/automat jde vzdy na vychozi.
    render_na = _txt("render_na", 60)
    if render_na:
        import render_worker as _rw
        if _rw.je_vychozi_worker(render_na):
            render_na = None
        else:
            cil = next((c for c in _rw.prehled_cilu()
                        if _rw._jmeno_klic(c["jmeno"]) == _rw._jmeno_klic(render_na)), None)
            if not cil:
                return jsonify({"error": "Stroj '%s' se ještě nikdy nepřipojil - nejdřív na něm spusť renderovací agent." % render_na}), 400
            if not cil["online"]:
                return jsonify({"error": "Stroj '%s' teď není dostupný: %s." % (cil["jmeno"], cil["duvod"])}), 409
            render_na = cil["jmeno"]

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename FROM shared_drive_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Soubor na Sdíleném disku nenalezen."}), 404
            if os.path.splitext(row["filename"])[1].lower() not in HDRI_EXT:
                return jsonify({"error": "Vybraný soubor není HDRI mapa (.hdr/.exr)."}), 400
            if _je_zakazana_hdri(row["filename"]):
                return jsonify({"error": CHYBA_ZAKAZANA_HDRI}), 400
            user = current_user()
            # Otisk ULOZENEHO stavu panelu (radky tabulky materialu, azimut,
            # kryci listy...) v okamziku kliknuti - Robert 2026-09-29:
            # "kdyz budu opakovane klikat spustit render a pritom menit
            # napr HDri nebo jine parametry, nech se to ukládá do fronty".
            # Klient pred odeslanim panel ulozi, takze tohle je stav PRESNE
            # z tohoto kliknuti; automat pak bere otisk, ne zivy app_settings.
            otisk_dict = dict(_prirazeni.nacti_ulozene_nastaveni(cur))
            if render_na:
                otisk_dict["render_na"] = render_na
            otisk = json.dumps(otisk_dict, ensure_ascii=False)
            cur.execute(
                "INSERT INTO render_hdri_test_requests "
                "(hdri_file_id, hdri_filename, shop_product_id, requested_by, "
                "alu_material, alu_knihovna_soubor, klt_material, klt_knihovna_soubor, "
                "ostatni_knihovna_soubor, cub_seda_tmava_sila, alu_ao_sila, hdri_sila, hdri_rotace_deg, "
                "nastaveni_json) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (file_id, row["filename"], TEST_RENDER_SHOP_PRODUCT_ID, user["id"] if user else None,
                 alu_material, alu_knihovna, klt_material, klt_knihovna,
                 ostatni_knihovna, cub_seda_tmava_sila, alu_ao_sila, hdri_sila, hdri_rotace_deg,
                 otisk),
            )
            request_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"request_id": request_id, "status": "pending", "render_na": render_na}), 202


@app.get("/api/admin/render-hdri/test-render")
@admin_required
def render_hdri_test_render_fronta():
    """Fronta testovacich renderu pro panel (cekajici + bezici + poslednich
    par hotovych) - kazde kliknuti na "Spustit testovaci render" je vlastni
    polozka s vlastnim otiskem nastaveni, viz render_hdri_test_render."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, frame_url, error_text, hdri_filename, drive_file_id, requested_at, "
                "hdri_sila, hdri_rotace_deg, nastaveni_json FROM render_hdri_test_requests "
                "WHERE status IN ('pending','dispatched') "
                "OR requested_at >= NOW() - INTERVAL 1 DAY ORDER BY id DESC LIMIT 15")
            rows = cur.fetchall()
    finally:
        conn.close()
    testy = []
    for r in rows:
        try:
            otisk = json.loads(r["nastaveni_json"]) if r["nastaveni_json"] else {}
        except ValueError:
            otisk = {}
        testy.append({
            "id": r["id"],
            "status": r["status"],
            "hdri_filename": r["hdri_filename"],
            "azimut_deg": otisk.get("azimut_deg") if isinstance(otisk, dict) else None,
            "render_na": otisk.get("render_na") if isinstance(otisk, dict) else None,
            "hdri_sila": float(r["hdri_sila"]) if r["hdri_sila"] is not None else None,
            "hdri_rotace_deg": float(r["hdri_rotace_deg"]) if r["hdri_rotace_deg"] is not None else None,
            "frame_url": r["frame_url"],
            "error": r["error_text"],
            "drive_download_url": (f"/api/admin/drive/files/{r['drive_file_id']}/download"
                                   if r["drive_file_id"] else None),
            "requested_at": r["requested_at"].strftime("%H:%M:%S") if r["requested_at"] else None,
        })
    return jsonify({"testy": testy})


@app.get("/api/admin/render-hdri/test-render/<int:request_id>")
@admin_required
def render_hdri_test_render_status(request_id):
    """Stav jednoho testovaciho nahledu - admin JS na tohle polluje, dokud
    status neni 'done'/'error'."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, frame_url, error_text, hdri_filename, drive_file_id FROM render_hdri_test_requests "
                "WHERE id=%s", (request_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Požadavek nenalezen."}), 404
    return jsonify({
        "status": row["status"],
        "frame_url": row["frame_url"],
        "error": row["error_text"],
        "hdri_filename": row["hdri_filename"],
        # Kopie na Sdilenem disku (Rendering/HDRi/testy) - Robert 2026-09-24:
        # "chci to prece pristupne na disku!!! jako vsechno ostatni". Muze
        # byt None, kdyz se kopie nepovedla (varovani v logu automatu) -
        # `frame_url` porad funguje jako zalozni odkaz.
        "drive_download_url": (f"/api/admin/drive/files/{row['drive_file_id']}/download"
                               if row["drive_file_id"] else None),
    })


def _aktivni_rotace_deg(cur):
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (NASTAVENI_KLIC_ROTACE,))
    row = cur.fetchone()
    if not row or row["setting_value"] in (None, ""):
        return None
    try:
        return float(row["setting_value"])
    except (TypeError, ValueError):
        return None


@app.get("/api/admin/render-hdri-rotace")
@admin_required
def render_hdri_rotace_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deg = _aktivni_rotace_deg(cur)
    finally:
        conn.close()
    return jsonify({"rotace_deg": deg})


@app.put("/api/admin/render-hdri-rotace")
@admin_required
def render_hdri_rotace_set():
    body = request.get_json(silent=True) or {}
    hodnota = body.get("rotace_deg")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if hodnota in (None, ""):
                ulozit = None
            else:
                try:
                    ulozit = float(hodnota)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatný úhel."}), 400
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                (NASTAVENI_KLIC_ROTACE, "" if ulozit is None else str(ulozit)),
            )
        conn.commit()
    finally:
        conn.close()
    user = current_user()
    log_audit(user["id"] if user else None, "update", "render_hdri_rotace", None,
              json.dumps({"rotace_deg": ulozit}))
    return jsonify({"status": "ok", "rotace_deg": ulozit})


# Prirazeni materialu/HDRi (Robert 2026-09-28: "to co vyplnim v renderovaci
# tabulce musi zustat ulozeno pro dalsi pouziti" + zatrzitko "plati i pro
# automatickou linku renderu") - CELY panel jako jeden JSON blob v
# app_settings (stejny klic jako scripts/_render_prirazeni_lib.py cte),
# aby prezil znovunacteni stranky/jineho pocitace, ne jen localStorage
# jednoho prohlizece. Zatrzitko samo o sobe NEPOSILA zadny render - jen
# rika automatu (2026-09-23_vandr_render_auto_dispatch.py), ze ma pri
# KAZDEM dalsim zarazeni pouzit tenhle prekryv misto puvodnich vychozich
# hodnot; test-render tlacitko v panelu posila hodnoty jako PER-JOB
# override uplne nezavisle na tomhle nastaveni (viz render_hdri_test_render
# vyse), takze testovani neceho noveho nemusi cekat na odskrtnuti.
_PRIRAZENI_TXT_POLE = ("alu_material", "alu_knihovna_soubor", "klt_material",
                       "klt_knihovna_soubor", "ostatni_knihovna_soubor",
                       # Robert 2026-09-29: "nastaveni svetel podle nejakeho
                       # souboru" (X1_SCENA.blend) - svetla z .blend souboru
                       "svetla_soubor")
_PRIRAZENI_CISLO_POLE = {
    "cub_seda_tmava_sila": (0.0, 1.0), "alu_ao_sila": (0.0, 1.0),
    "hdri_sila": (0.0, None), "hdri_rotace_deg": (0.0, 359.9),
    # Robert 2026-09-28: "nech se zadava take azimut sestavy/objektu" -
    # uhel testovaciho snimku (--azimut), prazdne = zepredu
    "azimut_deg": (0.0, 359.0),
    # nasobek vykonu svetel ze souboru (--svetla-sila), 1 = jak jsou v souboru
    "svetla_sila": (0.0, 50.0),
}


@app.get("/api/admin/render-prirazeni")
@admin_required
def render_prirazeni_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                        (_prirazeni.NASTAVENI_APP_SETTINGS_KLIC,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row["setting_value"]:
        return jsonify({})
    try:
        n = json.loads(row["setting_value"])
    except (TypeError, ValueError):
        return jsonify({})
    return jsonify(n if isinstance(n, dict) else {})


@app.get("/api/admin/render-prirazeni/rodiny")
@admin_required
def render_prirazeni_rodiny():
    """Radky tabulky "kazdy material jeden radek" - rodiny materialu, ktere
    se v Vandr GLB skutecne vyskytuji (ne natvrdo psany seznam, pribude-li
    nova rodina v novem modelu, objevi se sama). Hlinik a celo supliku
    maji vlastni radek nahore, tady se nevypisuji."""
    vsechny = _prirazeni.rodiny_materialu_vandr()
    # 3D nahled (Robert 2026-09-28: "vykreslit celou sestavu, takovou která
    # obsahuje všechny materiály a zvýraznit materiál ve 3D modelu") - zadna
    # jedina sestava nema vsech 29 rodin, proto hladove pokryti (vychozi =
    # ta s nejvic rodinami) a ke kazde rodine karta PRVNI sestavy z pokryti,
    # ktera ji obsahuje (prepinani zustava mezi par sestavami, ne 105).
    pokryti = _prirazeni.pokryti_rodin_sestavami()
    po_glb = _prirazeni.vandr_glb_rodiny()
    karty = {}
    if po_glb:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name, glb_file FROM shop_products WHERE glb_file IN (%s) ORDER BY id"
                            % ",".join(["%s"] * len(po_glb)), list(po_glb))
                for row in cur.fetchall():
                    karty.setdefault(row["glb_file"], row)
        finally:
            conn.close()
    sestavy, karta_rodiny = [], {}
    for g, vse, _nove in pokryti:
        row = karty.get(g)
        if not row:
            continue
        sestavy.append({"karta": row["id"], "nazev": row["name"], "pocet_rodin": len(vse),
                        "rodiny": sorted(vse, key=str.lower)})
        for r in vse:
            karta_rodiny.setdefault(r.lower(), row["id"])
    rodiny = [dict(r, karta=karta_rodiny.get(r["rodina"].lower())) for r in vsechny
              if r["rodina"].lower() not in _prirazeni.RODINY_SE_SPECIALNIM_RADKEM]
    specialni = {r["rodina"].lower(): karta_rodiny.get(r["rodina"].lower()) for r in vsechny
                 if r["rodina"].lower() in _prirazeni.RODINY_SE_SPECIALNIM_RADKEM}
    # Robert 2026-09-28: "může v tom být chaos... budu předpokládat, že se
    # ve všech sestavách bude ten materiál chovat stejně" - NEPLATI vzdy
    # (blue KLT = loga ve Vito, KLT boxy v Transitu), proto ke kazde rodine
    # VSECHNY karty, ktere ji maji (tlacitko "dalsi sestava s timto
    # materialem"). Poradi: nejdriv sestavy z pokryti, pak podle poctu rodin.
    poradi_pokryti = {g: i for i, (g, _, _) in enumerate(pokryti)}
    po_glb_typy = _prirazeni.vandr_glb_rodiny_typy()
    karty_rodiny, karty_rodiny_typ, nazvy_karet = {}, {}, {}
    for g in sorted(po_glb, key=lambda k: (poradi_pokryti.get(k, 999), -len(po_glb[k]), k)):
        row = karty.get(g)
        if not row:
            continue
        nazvy_karet[row["id"]] = row["name"]
        for r in po_glb[g]:
            karty_rodiny.setdefault(r.lower(), []).append(row["id"])
        # "rodina|typ" -> karty (radky "rozdělit podle dílu", 3D prepnuti)
        for r, typ in po_glb_typy.get(g, ()):
            seznam = karty_rodiny_typ.setdefault("%s|%s" % (r.lower(), typ), [])
            if row["id"] not in seznam:
                seznam.append(row["id"])
    # Role dilu (Robert 2026-09-28: "v různých sestavách mají multiboxy různý
    # materiál") - radky tabulky podle role, ne podle materialu ze zdroje.
    po_glb_role = _prirazeni.vandr_glb_role()
    karty_role, karty_role_typ = {}, {}
    for g in sorted(po_glb, key=lambda k: (poradi_pokryti.get(k, 999), -len(po_glb[k]), k)):
        row = karty.get(g)
        if not row:
            continue
        for ro, typ in po_glb_role.get(g, ()):
            for klic, cil in ((ro, karty_role), ("%s|%s" % (ro, typ), karty_role_typ)):
                seznam = cil.setdefault(klic, [])
                if row["id"] not in seznam:
                    seznam.append(row["id"])
    role = [r for r in _prirazeni.role_dilu_vandr() if r["role"] not in _prirazeni.ROLE_MIMO_TABULKU]
    sestavy_role = []
    for g, vse, _nove in _prirazeni.pokryti_roli_sestavami():
        row = karty.get(g)
        if row:
            sestavy_role.append({"karta": row["id"], "nazev": row["name"], "pocet_roli": len(vse)})
    return jsonify({"rodiny": rodiny, "sestavy": sestavy, "specialni_karta": specialni,
                    "celkem_rodin": len(vsechny), "karty_rodiny": karty_rodiny,
                    "karty_rodiny_typ": karty_rodiny_typ, "nazvy_karet": nazvy_karet,
                    "typy_dilu": _prirazeni.NAZEV_TYPU, "role": role, "sestavy_role": sestavy_role,
                    "karty_role": karty_role, "karty_role_typ": karty_role_typ})


@app.get("/api/admin/render-prirazeni/materialy")
@admin_required
def render_prirazeni_materialy():
    """Materialy, ktere .blend knihovna OPRAVDU obsahuje - panel z nich dela
    rozbalovaci seznam (Robert 2026-09-29: "vyber ze seznamu materialu,
    ktere vybrany soubor opravdu obsahuje"). Prazdna knihovna = vychozi
    vd_materialy.blend (stejne jako u radku dilu bez knihovny)."""
    knihovna = (request.args.get("knihovna") or "").strip() or "vd_materialy.blend"
    if "/" in knihovna or "\\" in knihovna or not knihovna.lower().endswith(".blend"):
        return jsonify({"error": "knihovna musí být jméno .blend souboru"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cesta = _prirazeni.cesta_k_souboru_podle_jmena(cur, knihovna)
    finally:
        conn.close()
    if cesta is None:
        return jsonify({"error": "soubor '%s' na Sdíleném disku není" % knihovna}), 404
    materialy = _prirazeni.materialy_v_knihovne(cesta)
    if not materialy:
        return jsonify({"error": "soubor '%s' neobsahuje žádný materiál (nebo ho nejde přečíst)" % knihovna}), 422
    return jsonify({"knihovna": knihovna, "materialy": sorted(materialy, key=str.lower)})


@app.get("/api/admin/render-prirazeni/svetla")
@admin_required
def render_prirazeni_svetla():
    """Svetla, ktera .blend soubor OPRAVDU obsahuje - panel je ukaze pod
    polem "svetla podle souboru", aby Robert videl, co se pouzije."""
    soubor = (request.args.get("soubor") or "").strip()
    if not soubor or "/" in soubor or "\\" in soubor or not soubor.lower().endswith(".blend"):
        return jsonify({"error": "soubor musí být jméno .blend souboru"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cesta = _prirazeni.cesta_k_souboru_podle_jmena(cur, soubor)
    finally:
        conn.close()
    if cesta is None:
        return jsonify({"error": "soubor '%s' na Sdíleném disku není" % soubor}), 404
    data = _prirazeni.svetla_v_souboru(cesta)
    if data is None:
        return jsonify({"error": "soubor '%s' nejde přečíst" % soubor}), 422
    if not data.get("svetla"):
        return jsonify({"error": "soubor '%s' neobsahuje žádné světlo (viditelné v renderu)" % soubor}), 422
    typy = {"POINT": "bodové", "SUN": "slunce", "SPOT": "reflektor", "AREA": "plošné"}
    vychozi = set(_prirazeni.svetla_vychozi_jmena(data["svetla"]))
    return jsonify({"soubor": soubor, "svetla": [
        {"jmeno": sv["jmeno"], "typ": typy.get(sv["typ"], sv["typ"]), "vykon": sv["vykon"],
         "vychozi": sv["jmeno"] in vychozi}
        for sv in data["svetla"]], "preskoceno": len(data.get("preskoceno") or [])})


@app.put("/api/admin/render-prirazeni")
@admin_required
def render_prirazeni_set():
    telo = request.get_json(silent=True) or {}
    n = {}
    for klic in _PRIRAZENI_TXT_POLE:
        v = telo.get(klic)
        if v is None:
            continue
        v = str(v).strip()
        if v:
            n[klic] = v[:255]
    for klic, (lo, hi) in _PRIRAZENI_CISLO_POLE.items():
        if telo.get(klic) in (None, ""):
            continue
        try:
            v = float(telo[klic])
        except (TypeError, ValueError):
            return jsonify({"error": "%s musí být číslo." % klic}), 400
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        n[klic] = v
    # Robert 2026-09-30: zatrzitko "svetla ze souboru" (jasne zapnuto/vypnuto,
    # soubor a sila zustanou ulozene). Klient bez klice = beze zmeny chovani.
    if "svetla_aktivni" in telo:
        n["svetla_aktivni"] = bool(telo["svetla_aktivni"])
    # Robert 2026-09-30 ("nech jen 2 svetla"): jmena svetel souboru, ktera se
    # pouziji. Bez klice / null = vychozi 2 nejsilnejsi (svetla_vybrana_jmena).
    if telo.get("svetla_vybrana") is not None:
        vyber = telo["svetla_vybrana"]
        if (not isinstance(vyber, list) or not vyber or len(vyber) > 64
                or not all(isinstance(j, str) and j.strip() for j in vyber)):
            return jsonify({"error": "svetla_vybrana musí být neprázdný seznam jmen světel."}), 400
        n["svetla_vybrana"] = [j[:255] for j in vyber]
    if telo.get("hdri_file_id") not in (None, ""):
        try:
            n["hdri_file_id"] = int(telo["hdri_file_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "hdri_file_id musí být číslo."}), 400
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT filename FROM shared_drive_files WHERE id=%s", (n["hdri_file_id"],))
                row = cur.fetchone()
        finally:
            conn.close()
        if row and _je_zakazana_hdri(row["filename"]):
            return jsonify({"error": CHYBA_ZAKAZANA_HDRI}), 400
    # Robert 2026-09-28: "každý materiál udělej jeden řádek" - radky
    # [{rodina, material, knihovna_soubor}], ulozi se jen vyplnene.
    nahrady = []
    for radek in (telo.get("nahrady") or []):
        if not isinstance(radek, dict):
            continue
        rodina = str(radek.get("rodina") or "").strip()[:120]
        material = str(radek.get("material") or "").strip()[:120]
        knihovna = str(radek.get("knihovna_soubor") or "").strip()[:255]
        # typ dilu (Robert 2026-09-28: KLT box vs Multibox) - id z
        # _render_prirazeni_lib.TYPY_DILU, prazdny = vsechny typy dilu
        typ = str(radek.get("typ") or "").strip().lower()
        if typ and typ not in _prirazeni.NAZEV_TYPU:
            return jsonify({"error": "Neznámý typ dílu '%s'." % typ[:40]}), 400
        role = re.sub(r"[^a-z]", "", str(radek.get("role") or "").lower())[:40]
        # knihovna bez nazvu materialu staci - material se vezme z ni az pri
        # renderu (_render_prirazeni_lib.material_z_knihovny)
        if (rodina or role) and (material or knihovna):
            nahrady.append({"rodina": rodina, "role": role, "material": material,
                            "knihovna_soubor": knihovna, "typ": typ})
    # Robert 2026-09-29: "proto jsme delali priradovaci tabulku aby vsechno
    # fungovalo transparentne" - nazev materialu se overi v souboru knihovny
    # uz PRI ULOZENI (jinak Blender tise nechal material z modelu: 'klt1' vs
    # 'KLT1' a neexistujici 'modrecelo' daly cela suplíku svetle modra).
    # Uklada se PRESNY nazev z knihovny, tabulka pak ukazuje, co se opravdu pouzije.
    chyby_mat = []
    dvojice_kolize = []
    cilove_radky = [(n, "alu_material", "alu_knihovna_soubor", "hliník"),
                    (n, "klt_material", "klt_knihovna_soubor", "čelo šuplíku")]
    cilove_radky += [(r, "material", "knihovna_soubor", "řádek %s" % (r["role"] or r["rodina"]))
                     for r in nahrady]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for kam, klic_mat, klic_kn, popis in cilove_radky:
                knihovna = (kam.get(klic_kn) or "").strip()
                if not knihovna:
                    continue
                cesta = _prirazeni.cesta_k_souboru_podle_jmena(cur, knihovna)
                if cesta is None:
                    chyby_mat.append("%s: knihovna '%s' není na Sdíleném disku." % (popis, knihovna))
                    continue
                ch = []
                presny = _prirazeni.urci_material_v_knihovne(knihovna, cesta, kam.get(klic_mat), ch)
                if presny is None:
                    chyby_mat.append("%s: %s" % (popis, "; ".join(ch)))
                    continue
                if (kam.get(klic_mat) or "").strip():
                    kam[klic_mat] = presny
                dvojice_kolize.append((presny, cesta))
            # svetla podle souboru: musi byt na disku a obsahovat aspon jedno svetlo
            # (jinak by test bezel s vestavenym osvetlenim a nikdo by si nevsiml)
            svetla_args_chyby = []
            if _prirazeni.svetla_args(cur, n, svetla_args_chyby) is None:
                chyby_mat.extend("světla: " + ch for ch in svetla_args_chyby)
    finally:
        conn.close()
    _prirazeni.zkontroluj_kolize_nazvu(dvojice_kolize, chyby_mat)
    if chyby_mat:
        return jsonify({"error": "Tabulka se neuložila - " + " | ".join(chyby_mat)}), 400
    if nahrady:
        n["nahrady"] = nahrady
    n["aktivni_pro_automat"] = bool(telo.get("aktivni_pro_automat"))
    # Robert 2026-09-28: "schované krycí lišty < aplikuj do renderovací
    # tabulky jako zatržítko" -> --kryci-listy-pruhledne (test i automat)
    n["kryci_listy_skryt"] = bool(telo.get("kryci_listy_skryt"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
                (_prirazeni.NASTAVENI_APP_SETTINGS_KLIC, json.dumps(n)),
            )
        conn.commit()
    finally:
        conn.close()
    user = current_user()
    # detail je v audit_log TEXT sloupec - log_audit ho predava pymysql
    # beze zmeny, slovnik tam nejde ("dict can not be used as parameter",
    # HTTP 500 pri kazdem ulozeni panelu, Robert 2026-09-28 screenshot).
    log_audit(user["id"] if user else None, "update", "render_prirazeni_materialu", None,
              json.dumps(n, ensure_ascii=False))
    return jsonify({"status": "ok", **n})
