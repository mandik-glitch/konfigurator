#!/usr/bin/env python3
"""2026-09-09_turntable_job.py - rozpad produktove sestavy na RENDEROVACI
ULOHU pro Blender (bot8, Robert 2026-09-09).

Robert 2026-09-09: "tento blender na VPS budu ja obsluhovat z hlediska
nastaveni 3D sceny, zapojim novy pc s GPU do site a ty budes delat rendery
na nase produktove sestavy podle nastaveni VPS blenderu a na vzdalenem GPU,
a ty rendery si rovnou ukladat k tem produktovym sestavam".

DELBA PRACE (proc dva soubory misto jednoho):
  * TENHLE skript bezi na serveru pod api/venv (ma pymysql, NEMA bpy) a
    prelozi sestavu na cisty JSON - absolutni cesty ke .glb dilu, jejich
    transformace a kamerovy plan. Zadna geometrie se tu nenacita.
  * api/blender_render_turntable.py bezi UVNITR Blenderu (ma bpy, NEMA
    pymysql ani pristup do DB) a ten JSON jen provede.
Diky tomu muze druhy dil bezet na Robertove vzdalene GPU stanici, kde
zadne DB spojeni neni - worker si stahne JSON + .glb soubory a hotovo.

KAMEROVY KONTRAKT: prstence/stills/azimuty MUSI presne odpovidat
webapp/scene.html (TT_* konstanty + ttStillsForFront/ttAzimuthsForFront/
computeFrontAzimuthDeg) a api/turntable.py (ELEVATIONS, AZIMUTHS, TIERS,
STILL_VIEWS, FIELD_RE), jinak commit otocneho nahledu odmitne davku jako
nekompletni. Hodnoty se tu NEODVOZUJI znovu - ctou se z api/turntable.py
(jediny zdroj pravdy pro ulozne schema), krome tech, ktere zije jen ve
scene.html (FOV/okraje/pozadi) - ty jsou nize s odkazem na radek.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import razitkovac  # noqa: E402  (az po doplneni cesty)

# --- konstanty, ktere zijou JEN ve webapp/scene.html (render pass) -------
# scene.html:4631-4633, 4699, 4711-4712, 4727-4735
TT_FOV = 45.0
TT_MARGIN = 1.04
TT_STILL_MARGIN = 1.06
TT_BG_COLOR = "#f2f3f5"
# Robert 2026-09-10: "pozadi renderu chci prechod z sede do cerne smerem
# dolu". Horni barva zustava TT_BG_COLOR (kontrakt otocneho nahledu ji zna),
# dolni je nova. None = ploche pozadi jako driv.
TT_BG_COLOR_BOTTOM = "#000000"
TT_SHADOW_FADE = 150.0          # mm
TT_SHADOW_PAD = 0.5 * TT_SHADOW_FADE
TT_KEY_DIR = [0.3689, 0.9272, -0.0650]   # smer hlavniho svetla (three.js Y-up)
TT_JPEG_Q = 92
# Vzorky Cycles. Robert 2026-09-11: "vzorky pro render dejme 500".
# Prebiji hodnotu ze sablony (X30-1 ma 924) - duvod je CAS, ne vzhled:
# kompletni davka je 360 snimku, pri 924 vzorcich radove den na jednu
# variantu. Se zapnutym OpenImageDenoise je rozdil proti 500 opticky
# zanedbatelny. Robertuv .blend se nemeni, prepis se deje az v ulohe
# (viz api/blender_render_turntable.py, sekce VZORKY).
# Zmena bez zasahu do kodu: app_settings.render_samples.
TT_SAMPLES = 500


# --- material: PRESNY port webapp/js/scene/catalog-panels.js (tabulky) +
# hdri-panels-ui.js materialForLayer() (poradi rozliseni). Zamerne se to
# resi TADY, na serveru: Blender nema pristup do DB, a barva/kovovost/
# drsnost je vlastnost KATALOGU, ne shaderu. Blender pak jen dostane tri
# cisla a postavi z nich material - stejny rozpad jako ve scene.
PART_MATERIAL_COLOR = {
    "alu": "#c9cdd1", "black": "#242424", "zinc": "#b7bcc0",
    "guma": "#1c1c1e", "plast_svetly": "#666c73",
    # viz catalog-panels.js - MDF ma vlastni polozku (Robert 2026-09-10
    # "mdf chci zvlast"); obe kopie palety musi zustat v sync.
    "mdf": "#5c626a",
}
PART_MATERIAL_METALNESS = {"alu": 0.6, "zinc": 0.45, "black": 0.1, "guma": 0.05, "plast_svetly": 0.0, "mdf": 0.1}
PART_MATERIAL_ROUGHNESS = {"alu": 0.35, "zinc": 0.55, "black": 0.15, "guma": 0.75, "plast_svetly": 0.38, "mdf": 0.4}
# plast_svetly 2026-09-12 (Robert pres bot3/bot4, po overovacim renderu:
# "boxy do reálnějšího plastu") - snizeno z 0.1/0.3. POZOR: tyhle dve
# hodnoty jsou jen ZALOHA pro pripad, ze v app_settings.scene_material_
# defaults jeste nic neni (viz _nacti_vychozi_materialy nize) - SKUTECNY
# zdroj pravdy pri renderu je TAM (uz existujici radek pro plast_svetly),
# a ten byl aktualizovan primo v DB soubezne s timhle - obe kopie musi
# zustat v sync (stejna zasada jako uz existujici komentar u "mdf" vyse).
DEFAULT_PART_COLOR = "#9aa0a6"


def _nacti_vychozi_materialy():
    """Vychozi vlastnosti materialu ulozene ve scene tlacitkem "Ulozit jako
    vychozi" (app_settings.scene_material_defaults, viz api/scene_materials.py).

    Robert 2026-09-10: *"kdyz zmenim barvu napriklad na uhelniku tak se to
    nedostane do dalsi sestavy"*. Drive mel panel ve scene hodnoty jen v
    localStorage a TENHLE soubor mel vlastni, nezavislou kopii tychz cisel -
    naladeny material se do produktoveho renderu nikdy nedostal. Ted je
    zdrojem pravdy DB a hodnoty nize slouzi uz jen jako zaloha, kdyz jeste
    nic ulozeno neni.
    """
    try:
        import pymysql  # noqa: F401 - jen test dostupnosti
        conn = _connect()
    except Exception:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                        ("scene_material_defaults",))
            row = cur.fetchone()
        if not row or not row.get("setting_value"):
            return {}
        data = json.loads(row["setting_value"])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _pouzij_vychozi_materialy():
    """Prebije tabulky vyse hodnotami z DB (jen ty, ktere tam jsou)."""
    for klic, v in _nacti_vychozi_materialy().items():
        if klic not in PART_MATERIAL_COLOR:
            continue
        if isinstance(v.get("color"), str):
            PART_MATERIAL_COLOR[klic] = v["color"].lower()
        for pole, tabulka in (("metal", PART_MATERIAL_METALNESS),
                              ("rough", PART_MATERIAL_ROUGHNESS)):
            try:
                tabulka[klic] = float(v[pole])
            except (KeyError, TypeError, ValueError):
                pass




def resolve_material(layer, color_hex):
    """materialForLayer(layer, overrideColor) z hdri-panels-ui.js bez
    posuvniku HDRI ovladace (ty jsou interaktivni stav editoru, do
    produktoveho renderu nepatri). Produktove dily (shop_products) nemaji
    sloupec `layer` vubec - jejich material se pozna VYHRADNE podle
    color_hex pres HEX_TO_* tabulky.

    `transmission`/`ior` pribyly 2026-09-11 (Robert: "logo s barevnym
    sklem") - stejny vzorec jako metalness/roughness, vychozi 0.0/1.45
    (nepruhledne) pro celou standardni paletu, cokoli jineho jen tam, kde
    je vyslovne v HEX_TO_TRANSMISSION/HEX_TO_IOR (dnes jen logo)."""
    color = (color_hex or PART_MATERIAL_COLOR.get(layer) or DEFAULT_PART_COLOR).lower()
    metalness = HEX_TO_METALNESS.get(color)
    if metalness is None:
        metalness = PART_MATERIAL_METALNESS.get(layer, 0.35)
    roughness = HEX_TO_ROUGHNESS.get(color)
    if roughness is None:
        roughness = PART_MATERIAL_ROUGHNESS.get(layer, 0.4)
    transmission = HEX_TO_TRANSMISSION.get(color, 0.0)
    ior = HEX_TO_IOR.get(color, 1.45)
    return color, float(metalness), float(roughness), float(transmission), float(ior)


def hex_to_linear_rgb(h):
    """sRGB hex -> linearni RGB (Blender Base Color je linearni; three.js
    MeshStandardMaterial dostava hex a prevadi sam)."""
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def _load_env():
    env = {}
    with open(os.path.join(REPO, "api", ".env"), encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"^([A-Z_]+)=(.*)$", line.strip())
            if m:
                env[m.group(1)] = m.group(2)
    return env


def _connect():
    import pymysql
    env = _load_env()
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
        user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor)


def _turntable_consts():
    """ELEVATIONS/AZIMUTHS/TIERS/STILL_VIEWS z api/turntable.py bez importu
    celeho Flasku - modul na urovni souboru importuje `app`, takze se z nej
    ctou jen literaly (regexem nad zdrojem by to bylo krehke; misto toho
    prehrajeme tu par radku definic v prazdnem namespace)."""
    src = open(os.path.join(REPO, "api", "turntable.py"), encoding="utf-8").read()
    ns = {}
    # bloky, ktere nepotrebuji nic z okoli (poradi zachovano)
    for pat in (r"^FRONT_AZIMUTH_DEG *=.*$", r"^STEP_DEG *=.*$", r"^ARC_DEG *=.*$",
                r"^_arc_half_steps *=.*$",
                r"^ELEVATIONS *=.*$", r"^TIERS *=.*$", r"^ASPECT *=.*$",
                r"^def _azimuths_for_front\(front\):(?:\n(?:[ \t].*)?)*",
                r"^STILL_VIEWS *= *\{(?:[^}]*)\}"):
        m = re.search(pat, src, re.M)
        if not m:
            raise SystemExit("V api/turntable.py chybi definice %r - kamerovy "
                             "kontrakt nelze overit." % pat)
        exec(compile(m.group(0), "turntable.py", "exec"), ns)
    return ns


# POZOR NA PORADI: vychozi materialy se ctou z DB, takze tenhle blok MUSI
# byt az za definici _connect(). Kdyz byl vys, `except` uvnitr spolkl
# NameError a hodnoty z DB se tise ignorovaly - zmereno 2026-09-10:
# ulozeny zinc #ff0000/0.99/0.11 se do renderu nedostal vubec.
_pouzij_vychozi_materialy()

# HEX_TO_* se odvozuji AZ PO nacteni vychozich hodnot - jinak by mapovaly
# na stare odstiny a dil by se ke svemu materialu nepoznal.
HEX_TO_METALNESS = {v.lower(): PART_MATERIAL_METALNESS[k] for k, v in PART_MATERIAL_COLOR.items()}
HEX_TO_ROUGHNESS = {v.lower(): PART_MATERIAL_ROUGHNESS[k] for k, v in PART_MATERIAL_COLOR.items()}
# Transmission/IOR pro standardni paletu: vsechno neprulhledne (0.0), IOR
# je pak bezvyznamny, ale 1.45 (bezne plasty/pryskyrice) je rozumny default,
# kdyby se nekdy pouzil i bez transmission.
HEX_TO_TRANSMISSION = {v.lower(): 0.0 for v in PART_MATERIAL_COLOR.values()}
HEX_TO_IOR = {v.lower(): 1.45 for v in PART_MATERIAL_COLOR.values()}

# Logo ochrany LOGIMAN.CZ ma vlastni barvu (Robert 2026-09-11, pres bot3:
# "lehce oranzovou"), mimo standardni alu paletu vyse - viz
# razitkovac.LOGO_BARVA_HEX/LOGO_METALNESS/LOGO_ROUGHNESS. Bez tohohle
# zaznamu by `resolve_material()` pro cizi hex spadl na fallback vrstvy
# 'alu' (0.6/0.35 misto pozadovanych 0.65/0.30) - a hlavne: `cfg_dily.
# color_hex` pro tenhle dil byl do 2026-09-11 NULL (viz api/admin_profily.py
# komentar "layer='alu' zamerne, aby ve scene vypadalo jako hlinik"),
# takze SE MUSEL zmenit i katalogovy radek (scripts/2026-09-11_logo_barva_
# katalog.py), jinak by se oranzova ztratila hned pri prvnim znovunacteni
# ulozenych dat (`_JEN_PRO_RENDER` v razitkovac.py barvu pred zapisem do
# `product_assemblies.data` schvalne odstranuje - viz tamni komentar).
#
# transmission/ior pribyly 2026-09-11 (Robert: "logo s barevnym sklem") -
# stejny mechanismus, stejna past: bez zaznamu tady by HEX_TO_TRANSMISSION/
# HEX_TO_IOR pro tenhle hex spadly na standardni 0.0/1.45 (nepruhledne) a
# logo by vyslo jako plna barva, ne sklo.
HEX_TO_METALNESS[razitkovac.LOGO_BARVA_HEX.lower()] = razitkovac.LOGO_METALNESS
HEX_TO_ROUGHNESS[razitkovac.LOGO_BARVA_HEX.lower()] = razitkovac.LOGO_ROUGHNESS
HEX_TO_TRANSMISSION[razitkovac.LOGO_BARVA_HEX.lower()] = razitkovac.LOGO_TRANSMISSION
HEX_TO_IOR[razitkovac.LOGO_BARVA_HEX.lower()] = razitkovac.LOGO_IOR

# Robert 2026-09-15, pres bot8: obousmerna sipka u posuvnych cel - "material
# jako logo, jen v zelene". Stejna past jako u loga vyse - bez zaznamu tady
# by tenhle hex spadl na standardni 0.0/1.45 (nepruhledne), misto barevneho
# skla jako logo.
HEX_TO_METALNESS[razitkovac.POSUVNE_CELO_SIPKA_HEX.lower()] = razitkovac.POSUVNE_CELO_SIPKA_METALNESS
HEX_TO_ROUGHNESS[razitkovac.POSUVNE_CELO_SIPKA_HEX.lower()] = razitkovac.POSUVNE_CELO_SIPKA_ROUGHNESS
HEX_TO_TRANSMISSION[razitkovac.POSUVNE_CELO_SIPKA_HEX.lower()] = razitkovac.POSUVNE_CELO_SIPKA_TRANSMISSION
HEX_TO_IOR[razitkovac.POSUVNE_CELO_SIPKA_HEX.lower()] = razitkovac.POSUVNE_CELO_SIPKA_IOR


TT = _turntable_consts()


def azimuths_for_front(front):
    """scene.html ttAzimuthsForFront == api/turntable.py _azimuths_for_front."""
    return TT["_azimuths_for_front"](front)


def stills_for_front(front):  # noqa: ARG001 - `front` zustava kvuli volajicim
    """ZADNE stills. Vraci prazdny seznam - WORKFLOW.md pravidlo 29.

    Robert 2026-09-11 doslova: *"Zadne stills se nedelaji, zapiz to uz
    navzdycky do nejakeho mista, kde to bude jasne - obrazky pro e-shop
    budou prejimat z natacecich snimku."* Jedna sada je tedy **81 renderu**
    (3 elevace x 27 azimutu, tier 1024 se dopocita zmensenim), **ne 86**.

    HISTORIE, at to nikdo "neopravi" zpatky (dva kroky, oba 2026-09-11):
      1. Nejdriv jsem odsud smazal jen `back` a zbylé ctyri klice srovnal se
         STILL_VIEWS. Tim kontrola prosla, ale kontrolovala SPATNY invariant:
         STILL_VIEWS uz neni seznam "co se ma vyrobit" - zustava tam jen
         proto, aby upload nerozbil starsi klienty, kteri stills posilaji
         dal ("prijmou se, ulozi na disk a dal se ignoruji", viz komentar
         nad STILL_VIEWS v api/turntable.py).
      2. Nasel bot8: ty ctyri se porad SKUTECNE renderovaly
         (api/blender_render_turntable.py:679 `total = len(ring_dirs) +
         len(JOB["stills"])`, pak `for s in JOB["stills"]`) a nikdo je pak
         necetl - ulozene soubory nemaji ctenare (`_still_rel_path` se
         pouziva jen k zapisu), `stills_meta` se v commitu cte jen kvuli
         poctu do reportu a GPU ingest matchuje vyhradne `frame_*.jpg`.
         Pri ~150 s na snimek to delalo ~10 minut GPU navic NA SESTAVU.

    Commit davky stills NEVYZADUJE - kontrola uplnosti v api/turntable.py
    (r. 1267) porovnava jen EXPECTED_FRAME_COUNT (162 snimku prstence).
    Overeno, ne predpokladano.
    """
    out = []
    # Invariant uz NENI "sedi se STILL_VIEWS", ale "nic se nerenderuje".
    # Kontrolu zamerne nechavame (prave ona odhalila rozchod s `back`), jen
    # hlida to spravne: kdyz sem nekdo stills vrati, spadne to hned pri
    # stavbe ulohy a ne az po trech hodinach GPU.
    if out:
        raise SystemExit(
            "stills_for_front() ma vracet PRAZDNY seznam (WORKFLOW.md pravidlo 29: "
            "'Zadne stills se nedelaji ... nikdo je nesmi znovu zavadet'), "
            "ale vraci %s. Kanonicke obrazky pro e-shop se prebiraji z prstence "
            "(_canonical_ring_source v api/turntable.py), nerenderuji se zvlast."
            % sorted(s["key"] for s in out))
    return out


def compute_front_azimuth_deg(parts):
    """scene.html:4685 computeFrontAzimuthDeg - predni smer TETO sestavy z
    role-tagovanych dilu. None = volajici pouzije globalni fallback.

    Role bez pripony "-noha<i>" (K-020 rebuild 2026-09-17) - presny match
    bez normalizace tise vracel None pro tyhle sestavy, viz stejna oprava
    v razitkovac.py::predni_azimut (tenhle kod je jeho nezavisla kopie,
    ne import - opravit obe zvlast)."""
    bez_nohy = lambda role: re.sub(r"-noha\d+$", "", str(role or ""))
    front = next((p for p in parts if bez_nohy(p.get("role")) == "predni-svislice"), None)
    rear = (next((p for p in parts if bez_nohy(p.get("role")) == "cap"), None)
            or next((p for p in parts if str(p.get("role") or "").startswith("zadni-svislice")), None))
    if not front or not rear:
        return None
    fp, rp = front.get("position"), rear.get("position")
    if not (isinstance(fp, list) and isinstance(rp, list) and len(fp) == 3 and len(rp) == 3):
        return None
    dx, dz = fp[0] - rp[0], fp[2] - rp[2]
    if abs(dx) < 1e-6 and abs(dz) < 1e-6:
        return None
    az = (math.degrees(math.atan2(dx, dz)) % 360 + 360) % 360
    step = TT["STEP_DEG"]
    return int(round(az / step) * step) % 360


def resolve_karoserie_odraz(cur, raw_parts):
    """car_body_<id> dily sestavy -> zdrojove GLB (_L/_R_D/_B) + zmerena
    vyska stropu pro '_umisti_odraznou_desku()' (Robert 2026-09-11, pres
    bot3: "souhlasim s pouzitím karoserie na odrazy... melo by mit
    material ktery odrazi svetlo").

    Meri PRIMO scripts/2026-09-11_karoserie_odrazy_audit.js (--json) -
    STEJNY kod jako obecny diagnosticky nastroj pouzity pri overovani
    (viz AGENTS_LOG.md), zadna paralelni reimplementace mereni v
    Pythonu (presne ta trida chyby - "moje verze opravy" vs "produkcni
    kod" - co uz tenhle projekt jednou stala skutecnou opravu, viz
    VLASTNOSTI_PROFILU.md).

    Vraci {"ok": False, "reason": "..."} kdyz sestava nema karoserii
    nebo je zmerena vyska mimo rozumne meze (viz HEIGHT_MIN_MM/MAX_MM v
    tom nastroji) NEBO prekracuje vlastni deklarovanou vnejsi vysku
    vozidla z car_models.name - v obou pripadech ma volajici SPADNOUT na
    dnesni chovani bez karoserie/s genererickou vzdalenosti desky, NE
    hadat nahradni cislo. Kazdy fallback se hlasite vypise (Robert:
    "chybejici udaj nikdy nesmi vypadat jako v poradku").
    """
    body_ids = []
    for p in raw_parts:
        pid = p.get("part_id") or ""
        if pid.startswith("car_body_"):
            try:
                body_ids.append(int(pid[len("car_body_"):]))
            except ValueError:
                pass
    if not body_ids:
        print("KAROSERIE ODRAZY: sestava nema zadny car_body_* dil, nelze pouzit.")
        return {"ok": False, "reason": "sestava nema karoserii"}

    cur.execute(
        "SELECT cb.id, cb.glb_file, cm.name AS model_name FROM car_bodies cb "
        "JOIN car_models cm ON cm.id = cb.model_id WHERE cb.id IN (%s)"
        % ",".join(["%s"] * len(body_ids)), body_ids)
    rows = cur.fetchall()
    if not rows:
        print("KAROSERIE ODRAZY: car_body_* dily (%s) v car_bodies nenalezeny." % body_ids)
        return {"ok": False, "reason": "car_bodies zaznamy nenalezeny"}

    glb_files, base, model_name = [], None, rows[0].get("model_name")
    # Robertovo vlastni oznaceni vozidla ("K-075"), NE interni kod ze
    # zdrojove knihovny souboru ("FI14") - ten je cizi cislovani a
    # Robert se po nem ptal (bot3 2026-09-11). `base`/interni kod zustava
    # jen pro cesty k souborum, v logu/manifestu se ukazuje k_code.
    k_code_m = re.search(r"\[(K-\S+?)\]", model_name or "")
    k_code = k_code_m.group(1) if k_code_m else (model_name or "?")
    for r in rows:
        if not r.get("glb_file"):
            continue
        abspath = os.path.join(KATALOG_DIR, r["glb_file"])
        if not os.path.exists(abspath):
            continue
        glb_files.append(abspath)
        m = re.match(r"^(.*)_(?:L|R_D|B)\.glb$", r["glb_file"])
        if m and not base:
            base = m.group(1)
    if not base or len(glb_files) < 3:
        print("KAROSERIE ODRAZY: neuplna trojice L/R_D/B (%d/3 souboru nalezeno pro %s)."
              % (len(glb_files), k_code))
        return {"ok": False, "reason": "neuplna trojice L/R_D/B"}

    tool = os.path.join(REPO, "scripts", "2026-09-11_karoserie_odrazy_audit.js")
    try:
        proc = subprocess.run(["node", tool, "--json", base],
                               capture_output=True, text=True, timeout=30, check=True)
        measured = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        print("KAROSERIE ODRAZY: mereni (%s) selhalo - %s" % (k_code, e))
        return {"ok": False, "reason": "mereni selhalo: %s" % e}

    if not measured.get("ok"):
        print("KAROSERIE ODRAZY: mereni (%s) vratilo chybu - %s" % (k_code, measured.get("error")))
        return {"ok": False, "reason": measured.get("error") or "mereni neuspesne"}

    height_mm = measured["interiorHeightMM"]
    plausible = bool(measured["heightPlausible"])

    # Druha, NEZAVISLA sanitni vrstva - krizova kontrola proti vlastni
    # DEKLAROVANE VNEJSI vysce vozidla z car_models.name ("... 1981mm
    # (H)"). Nakladovy prostor nemuze byt vyssi nez cele auto - presne
    # takhle se 2026-09-11 ctyri "Multicab"/"L-Partition" zaznamy
    # potvrdily jako vadna data (2500-2900mm namereno proti 1978-1981mm
    # deklarovane VNEJSI vysce), ne jen hodnota mimo globalni meze.
    exterior_h_m = re.search(r"(\d+)\s*mm\s*\(H\)", model_name or "")
    if plausible and exterior_h_m:
        exterior_h = int(exterior_h_m.group(1))
        if height_mm > exterior_h - 200:
            plausible = False
            print("KAROSERIE ODRAZY: %s - zmerena vyska interieru %dmm prekracuje "
                  "(nebo je podezrele blizko) vlastni deklarovanou vnejsi vysku "
                  "vozidla %dmm (%s) - VADNA DATA, POUZIVAM FALLBACK."
                  % (k_code, height_mm, exterior_h, model_name))

    if not plausible:
        b = measured.get("heightBoundsMM", {})
        print("KAROSERIE ODRAZY: %s - zmerena vyska interieru %dmm mimo rozumne "
              "meze [%s,%s]mm - FALLBACK na dnesni chovani (bez merene vysky)."
              % (k_code, height_mm, b.get("min"), b.get("max")))
        return {"ok": False, "reason": "vyska implausible", "glb_files": glb_files,
                "interior_height_mm": height_mm, "k_code": k_code}

    print("KAROSERIE ODRAZY: %s - vyska interieru %dmm (merena, OK), sirka=%dmm, "
          "prepazka na strane %s (Z=%.0f)."
          % (k_code, height_mm, measured.get("widthMM", 0),
             measured.get("bulkheadSide"), measured.get("bulkheadZMM", 0)))
    return {
        "ok": True,
        "base": base,
        "k_code": k_code,
        "glb_files": glb_files,
        "interior_height_mm": height_mm,
        "interior_height_source": "merena",
        "width_mm": measured.get("widthMM"),
    }


def resolve_obklad_desky(karoserie_odraz):
    """Obklad karoserie ("desky prekliizky") - Robert 2026-09-12, pres
    bot3: skutecna plocha _L/_R_D/_B odsazena dovnitr o svou tloustku,
    zadne zplostovani (viz scripts/2026-09-12_karoserie_obklad_desky.js).
    Prototyp jen pro K-075. Stejny princip jako resolve_podlaha_obrys -
    posila se HOTOVA geometrie (vertexy+trojuhelniky) primo v JOB JSON,
    zadny novy soubor k prenosu na vzdalenou stanici."""
    if not karoserie_odraz.get("ok") or not karoserie_odraz.get("base"):
        return {"ok": False, "reason": "karoserie neni k dispozici"}
    base = karoserie_odraz["base"]
    # Prototyp JEN pro K-075 (Robert: "zadny katalog, jedna karoserie") -
    # vypocet produkuje ~1MB dat na jednu karoserii, proto se NEPOCITA
    # eagerly pro kazdou sestavu jako u lehcich karoserie_odraz/podlaha_
    # obrys vyse, jen pro tuhle jednu.
    if karoserie_odraz.get("k_code") != "K-075":
        return {"ok": False, "reason": "obklad je prototyp jen pro K-075"}
    tool = os.path.join(REPO, "scripts", "2026-09-12_karoserie_obklad_desky.js")
    try:
        proc = subprocess.run(["node", tool, base, "--json"],
                               capture_output=True, text=True, timeout=60, check=True)
        measured = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        print("OBKLAD DESKY: vypocet (%s) selhal - %s" % (karoserie_odraz.get("k_code", base), e))
        return {"ok": False, "reason": "vypocet selhal: %s" % e}
    if not measured.get("ok"):
        print("OBKLAD DESKY: vypocet (%s) vratil chybu - %s" % (karoserie_odraz.get("k_code", base), measured.get("error")))
        return {"ok": False, "reason": measured.get("error") or "vypocet neuspesny"}
    panels = measured.get("panels") or {}
    print("OBKLAD DESKY: %s - %s, tloustka=%smm."
          % (karoserie_odraz.get("k_code", base),
             ", ".join("%s=%dv/%dt" % (k, p["vertCount"], p["triCount"]) for k, p in panels.items()),
             measured.get("tloustka_mm")))
    return {"ok": True, "panels": panels}


def resolve_podlaha_obrys(karoserie_odraz):
    """Podlaha jako obrysova linka (Robert 2026-09-11, pres bot3:
    "podlahu muzeme udelat jako vyřez z karoserie, obrysová linka") -
    POUZE prototyp pro K-075 (Fiat Doblo), Robert vyslovne "zadny
    katalog, jedna karoserie, jeden zaver". `karoserie_odraz` je uz
    resolvnuty vysledek resolve_karoserie_odraz() - znovu se nedotazuje
    DB, jen posle stejne `base` do mericiho nastroje
    (2026-09-11_karoserie_podlaha_obrys.js --json), presne stejny princip
    jako u vysky (zadna paralelni reimplementace rezu v Pythonu).

    Vraci {"ok": False, ...} kdyz karoserie neni k dispozici NEBO mereni
    nevratilo pouzitelnou hlavni skupinu - volajici pak podlahu proste
    nepridava (zadny nahradni tvar, viz komentar u karoserie vyse).
    """
    if not karoserie_odraz.get("ok") or not karoserie_odraz.get("base"):
        return {"ok": False, "reason": "karoserie neni k dispozici"}
    base = karoserie_odraz["base"]
    tool = os.path.join(REPO, "scripts", "2026-09-11_karoserie_podlaha_obrys.js")
    try:
        proc = subprocess.run(["node", tool, base, "--json"],
                               capture_output=True, text=True, timeout=30, check=True)
        measured = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as e:
        print("PODLAHA OBRYS: mereni (%s) selhalo - %s" % (karoserie_odraz.get("k_code", base), e))
        return {"ok": False, "reason": "mereni selhalo: %s" % e}
    if not measured.get("ok") or not measured.get("mainLoop", {}).get("points"):
        print("PODLAHA OBRYS: mereni (%s) nevratilo pouzitelny hlavni obrys."
              % karoserie_odraz.get("k_code", base))
        return {"ok": False, "reason": "zadny pouzitelny obrys"}
    pts = measured["mainLoop"]["points"]
    print("PODLAHA OBRYS: %s - %d bodu (%s), rez Y=%smm."
          % (karoserie_odraz.get("k_code", base), len(pts),
             measured["mainLoop"].get("method"), measured.get("cutY")))
    return {"ok": True, "points_xz": pts}


def _render_materialy_zapnuto(cur):
    """Flag app_settings.render_materialy_katalogu_aktivni (vychozi vypnuto) - cte se JEDNOU na volani
    resolve_parts, ne pro kazdy dil. Chyba/chybejici knihovna = vypnuto."""
    try:
        import _render_prirazeni_lib as _rpl
        return bool(_rpl.render_materialy_zapnuto(cur))
    except Exception:
        return False


def _render_material_dilu(cur, pid, produkt_id):
    """Material katalogu pro dil ({"nazev","knihovna"} nebo None) - viz scripts/_render_prirazeni_lib.py
    render_material_pro_dil. Vypnuto flagem app_settings.render_materialy_katalogu_aktivni; nikdy nevyhazuje
    vyjimku (None = dil zustava po starem)."""
    try:
        import _render_prirazeni_lib as _rpl
        if produkt_id is not None:
            return _rpl.render_material_pro_dil(cur, "product", produkt_id)
        return _rpl.render_material_pro_dil(cur, "cfg", pid)
    except Exception:
        return None


def resolve_parts(cur, raw_parts):
    """part_id -> absolutni cesta ke .glb + material. Karoserie (car_body_*)
    se do renderu NEDAVA - stejne jako v prohlizeci (scene.html:4990,
    renderEntries filtruje source === "car_body")."""
    cfg_ids, prod_ids = set(), set()
    for p in raw_parts:
        pid = p.get("part_id") or ""
        if pid.startswith("car_body_"):
            continue
        if pid.startswith("product_"):
            try:
                prod_ids.add(int(pid.split("_", 1)[1]))
            except ValueError:
                pass
        else:
            cfg_ids.add(pid)

    cfg = {}
    if cfg_ids:
        cur.execute("SELECT id, glb_file, layer, color_hex FROM cfg_dily WHERE id IN (%s)"
                    % ",".join(["%s"] * len(cfg_ids)), sorted(cfg_ids))
        cfg = {r["id"]: r for r in cur.fetchall()}
    prod = {}
    if prod_ids:
        cur.execute("SELECT id, glb_file, color_hex, nativni_material FROM shop_products WHERE id IN (%s)"
                    % ",".join(["%s"] * len(prod_ids)), sorted(prod_ids))
        prod = {r["id"]: r for r in cur.fetchall()}

    rm_zapnuto = _render_materialy_zapnuto(cur)
    out, missing = [], []
    for p in raw_parts:
        pid = p.get("part_id") or ""
        if pid.startswith("car_body_"):
            continue
        if pid.startswith("product_"):
            r = prod.get(int(pid.split("_", 1)[1])) if pid.split("_", 1)[1].isdigit() else None
            # shop_products nema sloupec `layer` (viz catalog-panels.js
            # HEX_TO_METALNESS) - material nese jen color_hex.
            layer = None
        else:
            r = cfg.get(pid)
            layer = r["layer"] if r else None
        if not r or not r.get("glb_file"):
            missing.append(pid)
            continue
        glb = os.path.join(KATALOG_DIR, r["glb_file"])
        if not os.path.exists(glb):
            missing.append("%s (%s)" % (pid, r["glb_file"]))
            continue
        # bot16, 2026-09-12 (bot4 zivy nalez: "logo porad renderuje starou
        # barvu, i kdyz razitkovac.LOGO_BARVA_HEX je v kodu spravne") -
        # LOGO_BARVA_HEX byl driv jen zdroj pro HEX_TO_METALNESS/atd.
        # lookup, samotna BARVA se porad brala z cfg_dily.color_hex (jako
        # u kazdeho jineho dilu) - ktery se musel rucne synchronizovat
        # zvlast (viz scripts/2026-09-11_logo_barva_katalog.py) a snadno
        # se to zapomnelo pri dalsi zmene kandidata (presne co se ted
        # stalo s kandidatem D). Logo uz NENI "jen dalsi katalogovy dil"
        # s vlastni ulozenou barvou - je to jediny dil, jehoz barva se
        # aktivne ladi kandidat-po-kandidatu primo v kodu, takze kod (ne
        # DB radek) je ted jeho zdroj pravdy. cfg_dily.color_hex se pro
        # logo dal NECTE vubec - LOGO_BARVA_HEX se pouzije vzdy, zadna
        # dalsi synchronizace uz nikdy nebude potreba.
        hexc = razitkovac.LOGO_BARVA_HEX if pid == razitkovac.LOGO_PART_ID else r.get("color_hex")
        color, metalness, roughness, transmission, ior = resolve_material(layer, hexc)
        out.append({
            "part_id": pid,
            "glb": glb,
            # Robert 2026-10-01: material z knihovny katalogu (render_materialy); None = po starem.
            "render_material": (_render_material_dilu(
                cur, pid, int(pid.split("_", 1)[1]) if pid.startswith("product_") else None) if rm_zapnuto else None),
            "position": p.get("position") or [0, 0, 0],
            "quaternion": p.get("quaternion") or [0, 0, 0, 1],
            "scale": p.get("scale") or [1, 1, 1],
            "layer": layer,
            # nativni_material (2026-09-20, Robertovo rozhodnuti, vanDrawee
            # import): druha, paralelni vetev vedle standardni "1 dil = 1
            # color_hex" - kdyz je 1, renderer NEPREPISUJE material dilu
            # vypoctem z cisel nize, necha material(y) tak, jak je prinesl
            # samotny GLB import (vice materialu v jednom souboru, typicky
            # externi vicematerialovy export). cfg_dily zadny takovy
            # sloupec nema (jen shop_products - r.get() vraci None -> 0).
            "nativni_material": bool(r.get("nativni_material")),
            # vynechat_objekty (2026-09-20, Robert: "podlahu odstranit") -
            # data sestavy, ne katalogu (ruzne sestavy stejneho dilu mohou
            # chtit ruzne vyloucit) - primy pruchod z raw dat dilu.
            "vynechat_objekty": p.get("vynechat_objekty") or [],
            "color_hex": color,
            "base_color": hex_to_linear_rgb(color),
            "metalness": metalness,
            "roughness": roughness,
            # transmission/ior 2026-09-11 ("logo s barevnym sklem") - stejny
            # vzorec jako metalness/roughness, viz HEX_TO_TRANSMISSION/IOR.
            "transmission": transmission,
            "ior": ior,
            "role": p.get("role"),
            # bot4 2026-09-11: resolve_parts() stavi NOVY slovnik s pevnou
            # sadou klicu - `alpha` (razitkovac.py, vypln drazky, 50%
            # pruhlednost) v ni chybel, takze po ulozeni razitek do dat
            # sestavy (stav "aktualni", dily jdou přes tuhle funkci jako
            # kazdy jiny) alpha zmizelo a renderer ho cetl jako 1.0 (plna
            # neprůhlednost). `p.get("alpha")` je None pro VSECHNY dily,
            # ktere alpha nikdy nemely - zadny hardcoded default, jen
            # prunuseni toho, co uz v surovych datech je.
            "alpha": p.get("alpha"),
        })
    return out, missing


def _vzorky_z_nastaveni():
    """Pocet vzorku Cycles pro tuhle ulohu.

    Vychozi TT_SAMPLES (500), prepsatelne z DB klicem
    `app_settings.render_samples` - aby se dalo ladit bez zasahu do kodu.
    Kdyz DB neni k dispozici nebo je hodnota nesmysl, plati konstanta.
    Hodnota 0 znamena "nechat, co ma sablona".
    """
    try:
        conn = _connect()
    except Exception:
        return TT_SAMPLES
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                        ("render_samples",))
            row = cur.fetchone()
        if row and row.get("setting_value"):
            n = int(row["setting_value"])
            return n if n > 0 else None
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return TT_SAMPLES


def build_job_vandr(shop_product_id, out_dir, razitka_override=None, glb_override=None, predni_azimut_override=None):
    """Vandr karty (shop_products.sku LIKE 'VD-%') NEMAJI product_assemblies
    radek (Robert/bot3 2026-09-23: "2. vetev se vepisuje do tabulky pro 1.
    vetev, to nelze" - viz 2026-09-22_vandr_fbx_watcher.py hlavicka).
    Zaklada "sestavu" narovinu z jedineho monolitickeho GLB
    (part_id="product_<id>", identita) + razitka predpocitana samostatne
    (scripts/2026-09-23_vandr_razitka_spocitat.py --shop-product-id, viz
    shop_products.vandr_razitka_json) - zadny SELECT do product_assemblies
    v cele teto funkci. `assembly_id` v navracenem jobu je None -
    product_turntable_frames.assembly_id je NULLable presne pro tenhle
    pripad ("snimky patri produktu, ne sablone").

    glb_override (bot4 2026-10-08, karty stolu z generatoru STUL-S*): absolutni cesta k GLB, ktery se pouzije MISTO katalogoveho
    (model karty stolu S RAZITKY - scripts/stul_karta_glb.py --razitka; razitka jsou uz v nem, takze zadny extra seznam) a
    predni_azimut_override = otockovy azimut cela (z extras.v3d.front modelu). Nic se nezapisuje do DB."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, glb_file, vandr_razitka_json, vandr_predni_azimut_deg "
                "FROM shop_products WHERE id=%s",
                (shop_product_id,))
            row = cur.fetchone()
            if not row:
                raise SystemExit("shop_products %s neexistuje." % shop_product_id)
            if not row["glb_file"]:
                raise SystemExit("shop_products %s (%s) nema glb_file - FBX->GLB konverze "
                                 "jeste nedobehla." % (shop_product_id, row["name"]))
            if razitka_override is not None:
                # bot10 2026-09-24: nahledy NAVRHU razitek pro Roberta bez zapisu do
                # shop_products.vandr_razitka_json - vandr-render-dispatch timer reaguje na
                # kazdou zmenu toho sloupce a pustil by ostry render neschvaleneho navrhu.
                razitka = list(razitka_override)
                print("  razitka    : %d dilu z --razitka-json (override, DB se necte ani nemeni)" % len(razitka))
            else:
                razitka = json.loads(row["vandr_razitka_json"]) if row["vandr_razitka_json"] else []
            raw = [{
                "part_id": "product_%d" % shop_product_id,
                "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1],
                "role": "vandrawee-export",
                # Stejny vyloucovaci seznam jako u 671/672 (bot4 2026-09
                # overil zivym renderem) - konvence napric Vandr exporty.
                "vynechat_objekty": ["podlaha", "karoserie", "dimension",
                                     "fixarea", "legshoverbox", "logo"],
            }] + razitka
            if glb_override:
                raw[0]["vynechat_objekty"] = []          # model stolu: razitka (a nic z Vandr obalu) se NESMI vyradit
            parts, missing = resolve_parts(cur, raw)
            karoserie_odraz = resolve_karoserie_odraz(cur, raw)
    finally:
        conn.close()
    podlaha_obrys = resolve_podlaha_obrys(karoserie_odraz)
    if not parts:
        raise SystemExit("shop_products %s neobsahuje zadny renderovatelny dil." % shop_product_id)
    if glb_override:
        if not os.path.isfile(glb_override):
            raise SystemExit("--glb-override: soubor %s neexistuje." % glb_override)
        parts[0]["glb"] = glb_override
        print("  model      : %s (override, razitka v modelu)" % glb_override)
    elif not razitka:
        print("VAROVANI: shop_products %s nema spoctena razitka (vandr_razitka_json prazdny) - "
              "render pojede BEZ ochrany. Spust scripts/2026-09-23_vandr_razitka_spocitat.py "
              "--shop-product-id %s." % (shop_product_id, shop_product_id))
    else:
        print("  razitka    : %d dilu z shop_products.vandr_razitka_json" % len(razitka))

    front = predni_azimut_override if predni_azimut_override is not None else compute_front_azimuth_deg(raw)
    if front is None:
        # WORKFLOW.md pravidlo 52 (bot3/Robert 2026-09-24: "toto je na
        # pravou stranu auta... tak to je problem, udelej co je
        # potreba"): monoliticky import nema role-tagovane dily, takze
        # compute_front_azimuth_deg() tady vraci VZDY None - bez tohohle
        # by KAZDA Vandr karta sla na globalni FRONT_AZIMUTH_DEG (270),
        # coz je spravne jen nahodou u LEVYCH regalu. `vandr_predni_
        # azimut_deg` pocita PRO TUHLE KONKRETNI sestavu
        # scripts/2026-09-23_vandr_razitka_spocitat.py (Krok 3d,
        # karoserie/podlaha proximita + kovani) primo z monolitickeho
        # GLB, nezavisle na umisteni_id stitku - pouziva se tu jen jako
        # jiz spocitana hodnota, zadny novy vypocet.
        if row["vandr_predni_azimut_deg"] is not None:
            front = int(row["vandr_predni_azimut_deg"]) % 360
            front_source = "vandr-geometrie"
        else:
            front = TT["FRONT_AZIMUTH_DEG"]
            front_source = "fallback"
            print("VAROVANI: shop_products %s nema spocteny vandr_predni_azimut_deg (razitka "
                  "jeste nebyla spoctena) - render pojede na globalni fallback %s deg, muze "
                  "ukazat spatnou stranu." % (shop_product_id, front))
    else:
        front_source = "model-front" if predni_azimut_override is not None else "role-tagy"
    azimuths = azimuths_for_front(front)
    tiers = TT["TIERS"]

    return {
        "assembly_id": None,
        "assembly_name": row["name"],
        "shop_product_id": shop_product_id,
        "front_azimuth_deg": front,
        "front_source": front_source,
        "parts": parts,
        "missing_parts": missing,
        "elevations": list(TT["ELEVATIONS"]),
        "azimuths": list(azimuths),
        "tiers": {str(k): list(v) for k, v in tiers.items()},
        "stills": stills_for_front(front),
        "fov_deg": TT_FOV,
        "margin": TT_MARGIN,
        "still_margin": TT_STILL_MARGIN,
        "shadow_pad": TT_SHADOW_PAD,
        "shadow_fade": TT_SHADOW_FADE,
        "key_dir": TT_KEY_DIR,
        "bg_color": TT_BG_COLOR,
        "bg_color_bottom": TT_BG_COLOR_BOTTOM,
        "jpeg_quality": TT_JPEG_Q,
        "samples": _vzorky_z_nastaveni(),
        "out_dir": out_dir,
        "expected_frames": len(TT["ELEVATIONS"]) * len(azimuths) * len(tiers),
        "karoserie_odraz": karoserie_odraz,
        "podlaha_obrys": podlaha_obrys,
    }


def build_job(assembly_id, out_dir, vyzadovat_produkt=True):
    """vyzadovat_produkt=False = uloha jen na PODIVANOU, ne k publikaci.

    Plny otocny nahled se commituje k e-shopovemu produktu, takze bez nej
    nema kam patrit. Zkusebni jeden snimek (--test) se ale commitnout
    NEDA ani tak (dávka neni kompletni, viz turntable_render.py) - tam by
    ta podminka jen branila renderovat. Zesilelo to 2026-09-09, kdy Robert
    smazal vsechny karty SEST-* a bez teto vyjimky by uz neslo vyrenderovat
    ZADNOU sestavu.

    POZOR: tohle je NATIVNI (Logiman) cesta, vyzaduje product_assemblies
    radek. Vandr karty (shop_products.sku LIKE 'VD-%') ho NEMAJI a pouzivaji
    misto toho build_job_vandr() vyse - viz CLAUDE.md bod 6 (vanDrawee a
    nase logika se nemichaji v jednom souboru; tahle funkce zustava cista
    nativni, Vandr cesta je samostatna funkce, ne vetveni uvnitr teto).
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, shop_product_id, data FROM product_assemblies WHERE id=%s",
                        (assembly_id,))
            row = cur.fetchone()
            if not row:
                raise SystemExit("Sestava %s neexistuje." % assembly_id)
            if vyzadovat_produkt and not row["shop_product_id"]:
                raise SystemExit("Sestava %s (%s) nema navazany e-shopovy produkt - "
                                 "otocny nahled by nemel kam patrit." % (assembly_id, row["name"]))
            data_dict = json.loads(row["data"])
            raw = data_dict.get("parts") or []
            parts, missing = resolve_parts(cur, raw)
            karoserie_odraz = resolve_karoserie_odraz(cur, raw)
    finally:
        conn.close()
    podlaha_obrys = resolve_podlaha_obrys(karoserie_odraz)
    # resolve_obklad_desky() zamerne NENI volana tady - Robert 2026-09-12
    # zmenil zadani z "render s obkladem" na "jen ploche vzory do JSON"
    # (scripts/2026-09-12_karoserie_ploche_vzory.js), render cesta zustala
    # nedodelana/nepotrebna. Funkce zustava k dispozici pro pripadne
    # pozdejsi navrat k 3D obkladu, jen se nevola z kazdeho render jobu
    # (produkuje ~1MB dat na K-075, zbytecne pro vsechny ostatni sestavy).

    if not parts:
        raise SystemExit("Sestava %s neobsahuje zadny renderovatelny dil." % assembly_id)

    front = compute_front_azimuth_deg(raw)
    if front is None:
        # Rucni override (Robert 2026-09-23, Vandr/vanDrawee): tyhle importy
        # nemaji role-tagovane dily, takze compute_front_azimuth_deg() vzdy
        # vraci None a bez tohohle by se pouzil jen globalni FRONT_AZIMUTH_DEG
        # fallback (270), ktery pro Ducato (672) vylucoval prave 60/90/120 -
        # presne ty azimuty, co Robert potvrdil jako spravnou "pravou" sadu.
        # Zadna zmena DB schematu - jen volitelny klic v `data` JSON, ktery
        # normalni (role-tagovane) sestavy nikdy nemaji a nepouzivaji.
        override = data_dict.get("front_azimuth_override_deg")
        if isinstance(override, (int, float)) and not isinstance(override, bool):
            front = float(override) % 360
            front_source = "rucni-override"
        else:
            front = TT["FRONT_AZIMUTH_DEG"]
            front_source = "fallback"
    else:
        front_source = "role-tagy"

    azimuths = azimuths_for_front(front)
    tiers = TT["TIERS"]

    # Ochranna razitka LOGIMAN.CZ (Robert 2026-09-10).
    #
    # Od 2026-09-11 se razitka propisuji do DAT SESTAVY pri zarazeni do slozky
    # stromu (api/product_assemblies.py). Tady se proto NEJDRIV podivame, jestli
    # uz v sestave jsou - do teto zmeny se razitkovalo BEZPODMINECNE, takze
    # propsana sestava by do ulohy dostala DRUHOU sadu navrch (na sestave 134
    # by do renderu slo 12 log: 4 stara + 8 novych). Nasel bot4 revizi.
    stav_raz = razitkovac.stav_razitek(json.loads(row["data"]))
    if stav_raz == "aktualni":
        # Razitka uz v datech jsou a odpovidaji dnesni podobe sestavy -
        # resolve_parts je uz nacetl spolu se zbytkem dilu, nic se nepridava.
        print("  razitka    : z dat sestavy (otisk sedi), nepridavaji se")
    elif stav_raz == "zastarala":
        # ⭐ ZAMERNE SE TU TISE NEDORAZITKOVAVA (Robert pres bot3). Sestava se
        # po orazitkovani zmenila, takze razitka sedi na profilech, ktere uz
        # nemusi existovat. Tichá oprava pri renderu by tenhle fakt zakryla -
        # ma ho videt clovek a sestavu znovu zaradit, cimz se razitka obnovi.
        print("VAROVANI: sestava ma ZASTARALA razitka (otisk nesedi na dnesni "
              "podobu sestavy). Render je pouzije tak, jak jsou. Naprav tim, "
              "ze sestavu znovu zaradis do slozky stromu.")
    else:
        razitka, razitka_chyba = razitkovac.orazitkuj(parts, front, row["id"], KATALOG_DIR)
        if razitka:
            parts = parts + razitka
            print("  razitka    : %d dilu docasne pro render (v datech sestavy nejsou)"
                  % len(razitka))
        elif razitka_chyba:
            print("VAROVANI: razitka nepridana - %s" % razitka_chyba)

    return {
        "assembly_id": row["id"],
        "assembly_name": row["name"],
        "shop_product_id": row["shop_product_id"],
        "front_azimuth_deg": front,
        "front_source": front_source,
        "parts": parts,
        "missing_parts": missing,
        "elevations": list(TT["ELEVATIONS"]),
        "azimuths": list(azimuths),
        "tiers": {str(k): list(v) for k, v in tiers.items()},
        "stills": stills_for_front(front),
        "fov_deg": TT_FOV,
        "margin": TT_MARGIN,
        "still_margin": TT_STILL_MARGIN,
        "shadow_pad": TT_SHADOW_PAD,
        "shadow_fade": TT_SHADOW_FADE,
        "key_dir": TT_KEY_DIR,
        "bg_color": TT_BG_COLOR,
        "bg_color_bottom": TT_BG_COLOR_BOTTOM,
        "jpeg_quality": TT_JPEG_Q,
        "samples": _vzorky_z_nastaveni(),
        "out_dir": out_dir,
        "expected_frames": len(TT["ELEVATIONS"]) * len(azimuths) * len(tiers),
        # Data vzdycky spocitana (levne - jen GLB mereni), ZAPNUTI je ale
        # samostatny prepinac (turntable_render.py --karoserie-odrazy),
        # stejny vzor jako u odrazna_deska.
        "karoserie_odraz": karoserie_odraz,
        # Podlaha jako obrysova linka - prototyp JEN pro K-075, samostatny
        # prepinac (--karoserie-podlaha), stejny vzor.
        "podlaha_obrys": podlaha_obrys,
    }


# ---------------------------------------------------------------------------
# ONLINE NABIDKA = stejna cesta jako karty (bot4 2026-10-01, Robert: "renderovani v online nabidce musi mit i stejne
# pozadi jako automat na karty" + "propojit" materialy s panelem Rendering). Obrazky nabidky se driv delaly
# api/blender_render_scene.py (bez sablony, HDRI z okna renderu, materialy z barev ve scene), proto vypadaly jinak nez
# karty. Ted se z ZAPISU DILU sceny (part_id/position/quaternion/scale - presne to, co uklada sestava, viz
# serializeEntryForSave ve scene.html) postavi TENTYZ job jako u nativni karty (resolve_parts -> material z vrstvy/barvy
# katalogu + prepisy z panelu, sablona X30-02, pozadi, HDRI) a vyrenderuje se JEDEN snimek z kamery sceny.
# Co se od karty ZAMERNE lisi: bez ochrannych razitek (obrazek jde konkretnimu zakaznikovi, ne na verejny web), snimek
# jen v nejmensim tieru (1024 px - nabidka ho zobrazuje s object-fit: contain; 2048 by byl 4x delsi), zadny prstenec,
# zadny commit do product_turntable_frames (vystup je PNG k nabidce, viz api/render_worker.py::tt-result).
NABIDKA_TIER = 1024
NABIDKA_MAX_DILU = 1500


class NabidkaNeniKartovaCesta(Exception):
    """Zapis dilu ze sceny nejde vyrenderovat kartovou cestou (chybi dily v katalogu, prazdna scena...). Volajici
    ma spadnout na starou cestu (GLB ze sceny)."""


def _cisla(v, n):
    return isinstance(v, (list, tuple)) and len(v) == n and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) < 1e9 for x in v)


def normalizuj_dily_nabidky(raw):
    """Zapis dilu ze sceny -> cisty seznam {part_id, position, quaternion, scale[, role]}; vyhodi
    NabidkaNeniKartovaCesta pri cemkoli, co by se do renderu dostat nemelo (cizi klice se zahodi)."""
    if not isinstance(raw, list) or not raw:
        raise NabidkaNeniKartovaCesta("zapis dilu je prazdny nebo neni seznam")
    if len(raw) > NABIDKA_MAX_DILU:
        raise NabidkaNeniKartovaCesta("prilis mnoho dilu (%d > %d)" % (len(raw), NABIDKA_MAX_DILU))
    out = []
    for i, d in enumerate(raw):
        if not isinstance(d, dict) or not isinstance(d.get("part_id"), str) or not (0 < len(d["part_id"]) <= 120):
            raise NabidkaNeniKartovaCesta("dil %d nema platne part_id" % i)
        pos = d.get("position", [0, 0, 0])
        quat = d.get("quaternion", [0, 0, 0, 1])
        scale = d.get("scale", [1, 1, 1])
        if not (_cisla(pos, 3) and _cisla(quat, 4) and _cisla(scale, 3)):
            raise NabidkaNeniKartovaCesta("dil %d (%s) ma neplatnou pozici/otoceni/meritko" % (i, d["part_id"]))
        item = {"part_id": d["part_id"], "position": list(pos), "quaternion": list(quat), "scale": list(scale)}
        if isinstance(d.get("role"), str) and d["role"] and len(d["role"]) <= 60:
            item["role"] = d["role"]
        out.append(item)
    return out


def azimut_sceny_na_otocku(azimut_sceny_deg):
    """Azimut kamery ze SCENY (path-traced-preview.js::cameraDirToAzEl: az = atan2(-dz, dx) v three.js souradnicich,
    tj. uhel od osy +X proti smeru hodin v Blenderu, stejne jako camera_azimuth_deg v blender_render_scene.py) ->
    azimut OTOCKOVEHO skriptu (blender_render_turntable.py::_cam_dir: smer (cos(el)*sin(az), sin(el), cos(el)*cos(az)),
    tj. uhel od osy +Z k +X). Odvozeni: z dx = cos(el)cos(a_s), dz = -cos(el)sin(a_s) plyne sin(a_t) = cos(a_s),
    cos(a_t) = -sin(a_s), tedy a_t = a_s + 90. Hlida to test_nabidka_kartova_cesta.py."""
    return (azimut_sceny_deg + 90.0) % 360.0


def build_job_nabidka(raw_parts, out_dir, azimut_sceny_deg, elevace_deg, nazev="Online nabidka"):
    """Job pro JEDEN snimek nabidky z kamery sceny (azimut ve konvenci SCENY, viz azimut_sceny_na_otocku; elevace ve
    stupnich nad vodorovnou rovinou). Struktura = vystup build_job() (karta), aby ho zpracoval stejny
    blender_render_turntable.py i stejny worker."""
    raw = normalizuj_dily_nabidky(raw_parts)
    if not (isinstance(azimut_sceny_deg, (int, float)) and isinstance(elevace_deg, (int, float))
            and not isinstance(azimut_sceny_deg, bool) and not isinstance(elevace_deg, bool)
            and azimut_sceny_deg == azimut_sceny_deg and elevace_deg == elevace_deg):
        raise NabidkaNeniKartovaCesta("azimut/elevace nejsou cisla")
    conn = _connect()
    try:
        with conn.cursor() as cur:
            parts, missing = resolve_parts(cur, raw)
            karoserie_odraz = resolve_karoserie_odraz(cur, raw)
    finally:
        conn.close()
    if missing:
        raise NabidkaNeniKartovaCesta("v katalogu chybi dily: %s" % ", ".join(str(m) for m in missing[:5]))
    if not parts:
        raise NabidkaNeniKartovaCesta("scena neobsahuje zadny renderovatelny dil (jen karoserie?)")
    az = int(round(azimut_sceny_na_otocku(azimut_sceny_deg))) % 360
    el = max(-60, min(85, int(round(elevace_deg))))
    front = compute_front_azimuth_deg(raw)
    front_source = "role-tagy"
    if front is None:
        front, front_source = TT["FRONT_AZIMUTH_DEG"], "fallback"
    tier = NABIDKA_TIER if NABIDKA_TIER in TT["TIERS"] else max(TT["TIERS"])
    return {
        "assembly_id": None,
        "assembly_name": nazev,
        "shop_product_id": None,
        "front_azimuth_deg": front,
        "front_source": front_source,
        "parts": parts,
        "missing_parts": [],
        "elevations": [el],
        "azimuths": [az],
        "tiers": {str(tier): list(TT["TIERS"][tier])},
        "stills": [],
        "fov_deg": TT_FOV,
        "margin": TT_MARGIN,
        "still_margin": TT_STILL_MARGIN,
        "shadow_pad": TT_SHADOW_PAD,
        "shadow_fade": TT_SHADOW_FADE,
        "key_dir": TT_KEY_DIR,
        "bg_color": TT_BG_COLOR,
        "bg_color_bottom": TT_BG_COLOR_BOTTOM,
        "jpeg_quality": TT_JPEG_Q,
        "samples": _vzorky_z_nastaveni(),
        "out_dir": out_dir,
        "expected_frames": 1,
        "karoserie_odraz": karoserie_odraz,
        "podlaha_obrys": resolve_podlaha_obrys(karoserie_odraz),
    }


def main():
    ap = argparse.ArgumentParser(description="Rozpad produktove sestavy na renderovaci ulohu")
    ap.add_argument("assembly_id", type=int)
    ap.add_argument("-o", "--out", required=True, help="kam zapsat job JSON")
    ap.add_argument("--out-dir", default=None, help="kam Blender ulozi snimky (default: vedle job JSON)")
    a = ap.parse_args()
    out_dir = a.out_dir or os.path.join(os.path.dirname(os.path.abspath(a.out)), "frames")
    job = build_job(a.assembly_id, out_dir)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False, indent=1)
    print("Sestava %s (%s)" % (job["assembly_id"], job["assembly_name"]))
    print("  e-shop produkt : %s" % job["shop_product_id"])
    print("  dilu k renderu : %d" % len(job["parts"]))
    if job["missing_parts"]:
        print("  CHYBEJICI DILY : %s" % job["missing_parts"])
    print("  predni azimut  : %s deg (%s)" % (job["front_azimuth_deg"], job["front_source"]))
    print("  prstence       : %d elevaci x %d azimutu x %d tiery = %d snimku"
          % (len(job["elevations"]), len(job["azimuths"]), len(job["tiers"]), job["expected_frames"]))
    print("  stills         : %s" % ", ".join(s["key"] for s in job["stills"]))
    import collections as _c
    mats = _c.Counter((p["color_hex"], p["metalness"], p["roughness"]) for p in job["parts"])
    print("  materialy      :")
    for (c, m, r), n in mats.most_common():
        print("     %-9s metal %.2f  rough %.2f  x%d" % (c, m, r, n))
    print("  job JSON       : %s" % a.out)


if __name__ == "__main__":
    main()
