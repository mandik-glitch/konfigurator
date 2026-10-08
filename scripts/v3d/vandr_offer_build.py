"""Vandr (vanDrawee) karta -> cisty 3D model pro online nabidku + geom.json
(bot10, 2026-10-01, Robert: 3D scena online nabidky - koty, materialy jako
na renderech, ovladani, animace). NASLEDNIK scripts/2026-09-28_vandr_offer_
geometry.py - CLI je kompatibilni (api/vandr_scene_offers.py ho vola stejne,
kontroluje "GEOM_OK" ve stdout a cte geom["overall_size"] a geom["profily"]).

Pouziti (jen CPU, zadny render):
    blender -b -P vandr_offer_build.py -- <glb_in> <geom_json_out> <clean_glb_out>
            [--ctx ctx.json] [--motions vandr_motions.py] [--no-embed-v3d]
            [--no-motions] [--bez-normal]
  --bez-normal  GLB bez normal (o ~45 % mensi; three GLTFLoader pak sam
                zapne flatShading - plochy vzhled jako render use_smooth=False)

OCHRANA MODELU (zavazne, project_ochrana_3d_modelu_sestav): vystupni GLB
nese jen neutralni jmena (uzly n<i>, pivoty p<i>, materialy m<i>), zadne
extras krome scenes[0].extras.v3d (datova struktura v3d v1, viz nize),
zadna jmena dilu/SKU/unity_id, zadne UV. Logo vanDrawee, kolize (colliders),
fixarea, LegsBox/legshoverbox, dimension, podlaha, karoserie a obal pryc.
Na konci se kazdy retezec JSON casti GLB proveri regexem zakazanych slov -
pri shode skript skonci chybou (model nevznikne, nic tise neprojde).

Kroky:
 (1) import GLB (Blender glTF importer, bez extras, ploche stinovani)
 (2) vyrazeni: cervene/modre plosky nulove tloustky do 20 mm (stohovaci
     znacky, VANDR_DILY_ZNACENI.md); retezec jmen/materialu (VYNECHAT - stejny seznam jako
     vynechat_objekty v scripts/2026-09-09_turntable_job.py + colliders/
     LegsBox), skupiny "colliders" UVNITR komponent (horni uzel "colliders"
     je predek celeho regalu - ten se nemaze!), vse mimo regal (mimo
     colliders/left|right|bulkhead), obal (pravidlo 60 % ve 2 osach jako
     dnesni skript - jen pro meshe mimo komponenty) a kryci listy v drazce,
     pokud je v panelu kryci_listy_skryt
 (3) materialy podle role: IMPORT scripts/_render_prirazeni_lib.py
     (role_dilu, typ_dilu, rodina_materialu) + snimek tabulky panelu z
     ctx.json; poradi pravidel = api/blender_render_turntable.py (radek
     role/rodiny > cub seda > kryci lista > celo supliku > hlinik > material
     z modelu). Kazdy material -> Principled BSDF s konstantami
     (MATERIAL_KONSTANTY), duplicity sloucene na m01..
 (4) staticke meshe slouceny do jednoho uzlu (1 primitiva na material);
     pohyblive skupiny z modulu vandr_motions.py (pokud existuje) se
     neslucuji se statikou - kazda skupina pod vlastnim pivotem p<i>
 (5) front (z matic komponent: lokalni -Y = celo; jinak/pri neshode
     shop_products.vandr_predni_azimut_deg, stejny vzorec jako kontrola.html
     vdCameraDir), box (AABB produktu), dims L1 (sirka/hloubka/vyska v ramu
     cela)
 (6) prejmenovani na n<i>/m<i>/p<i>, smazani custom props, export glTF
     binarne (export_extras=False, Y-up, bez UV), dopsani v3d do
     scenes[0].extras, kontrola jednotek (AABB po exportu == AABB pred
     exportem v mm) a zakazanych retezcu
 (7) geom.json

HOOK POHYBU (modul vandr_motions.py, nepovinny; hleda se vedle tohoto
skriptu nebo cestou z --motions):
    vandr_motions.detect(api) -> dict | None
  api.ctx          dict z ctx.json ({} bez ctx)
  api.front        (x, 0, z) glTF - jednotkovy smer k zakaznikovi
  api.components   [{"obj": bpy Object uzlu komponenty "(Clone)",
                     "name": jmeno uzlu v Blenderu, "key": normalizovany
                     klic (jako unity_id bez tecek), "ctx": zaznam
                     ctx["komponenty"] se stejnym klicem nebo None,
                     "side": "left"|"right"|"bulkhead"|"",
                     "front": (x, y, z) glTF smer lokalni -Y komponenty,
                     "meshes": [bpy Object mesh, ktere prezily vyrazeni]}]
  api.info(obj)    {"role", "typ", "rodiny": [rodina materialu...],
                    "cesta": [jmena od korene k dilu]} (puvodni jmena)
  api.aabb(obj)    ((minx,miny,minz), (maxx,maxy,maxz)) svetovy AABB, glTF mm
  api.verts(obj)   numpy (N,3) svetove souradnice vrcholu, glTF mm
  api.tris(obj)    numpy (N,3,3) svetove trojuhelniky, glTF mm (kontrola drahy)
  api.to_gltf(v) / api.from_gltf(v)   prevod Blender <-> glTF souradnic
  api.warn(text)   varovani do geom.json (vidi jen admin)
  api.produkt      seznam mesh objektu produktu (meni ho jen api.split)
  api.split(obj, bod, normala)  rozrizne dil rovinou (glTF svet mm) na dva
                   nove objekty (pod, nad) a zaregistruje je misto puvodniho
                   (pant = jeden mesh pro obe kridla: horni pulka jede s
                   dvirky); vraci (pod, nad) nebo None
  api.add_part(jmeno, verts, tris, role="red", typ="doraz", rodina="Red")
                   prida DOPLNENY dil, ktery zdrojovy model nema (Robert 2026-10-02:
                   dorazy beznych dvirek): verts (N,3) svetove glTF mm, tris (M,3)
                   indexy s vnejsi normalou; novy bpy objekt je dil produktu (jde
                   i do pivotu v "objects") a material dostane stejnou cestou
                   jako ostatni dily (role "red" -> panel -> konstanty "red")
  api.remove_part(obj)  zrusi dil pridany add_part (komponenta pri detekci selhala)
 vraci {"pivots": [{"id": "p1", "origin": [x,y,z] glTF mm (osa pantu /
                    zacatek kolejnice), "parent": None | id jineho pivotu,
                    "objects": [jmena bpy objektu, ktere se s pivotem hybou]}],
        "motions": [motion dle kontraktu v3d v1 - steps[].p a pick[]
                    odkazuji na id pivotu, ax v glTF souradnicich (= rodic
                    pivotu, vsechny pivoty maji jednotkovou rotaci);
                    nepovinne "sub" (jen k=box: klt|multibox|eurobox|kufrik) -
                    neplatne se zahodi s varovanim, pohyb zustane],
        "dims": [volitelne koty L2, "p" = id pivotu; a/b/o VZDY ve svetovych
                 glTF souradnicich zavreneho stavu - prohlizec je k pivotu
                 pripoji pres Object3D.attach (zachova svetovou polohu)],
        "warnings": [str],
        "info": {volitelne: verze a pocty modulu -> geom.json stats.pohyby_modul}}
 Build pivoty precisluje na p01.. (deterministicky v poradi z modulu) a
 odkazy v motions/dims prepise. Neplatny pohyb/pivot = varovani, dil
 zustane staticky (nic se nehada). Pohyblive dily se NESLUCUJI se statikou:
 kazdy pivot dostane vlastni mesh (1 primitiva na material), vnorene pivoty
 (pin pod dvirky, box pod vysuvem) zustanou vnorene. Skutecna detekce =
 scripts/v3d/vandr_motions.py (vychozi hodnoty z ctx.pohyby_vychozi =
 pohyby-vychozi.json).

Datova struktura v3d v1 (scenes[0].extras.v3d), jednotky mm, Y nahoru:
 {"v":1,"u":"mm","up":[0,1,0],"front":[fx,0,fz],"box":{"min":[..],"max":[..]},
  "look":"vd","dims":[{"a":[..],"b":[..],"o":[..],"t":"1 685","l":1,"p":null}],
  "motions":[...]}
"""
import importlib.util
import json
import math
import os
import re
import struct
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

T0 = time.time()

# --------------------------------------------------------------- argumenty
_argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
_pos, _opt = [], {}
_i = 0
while _i < len(_argv):
    a = _argv[_i]
    if a in ("--ctx", "--motions"):
        _opt[a[2:]] = _argv[_i + 1]
        _i += 2
        continue
    if a in ("--no-embed-v3d", "--no-motions", "--bez-normal"):
        _opt[a[2:]] = True
        _i += 1
        continue
    _pos.append(a)
    _i += 1
if len(_pos) < 3:
    raise SystemExit("Pouziti: blender -b -P vandr_offer_build.py -- <glb_in> <geom_json_out> <clean_glb_out> "
                     "[--ctx ctx.json] [--motions vandr_motions.py] [--no-embed-v3d]")
GLB_IN, GEOM_JSON_OUT, CLEAN_GLB_OUT = _pos[:3]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WARNINGS = []


def warn(text):
    text = str(text)
    if text not in WARNINGS:
        WARNINGS.append(text)
    print("VAROVANI:", text)


# ------------------------------------------------- sdilena knihovna roli
def _najdi_lib():
    """scripts/_render_prirazeni_lib.py - v repu je o adresar vys
    (scripts/v3d/ -> scripts/), v kandidatni kopii mimo repo se pouzije
    produkcni /opt/konfigurator/scripts. Zadna kopie logiky."""
    kandidati = [os.environ.get("V3D_LIB_DIR") or "", os.path.dirname(SCRIPT_DIR),
                 "/opt/konfigurator/scripts"]
    for d in kandidati:
        if d and os.path.isfile(os.path.join(d, "_render_prirazeni_lib.py")):
            return d
    raise SystemExit("Nenalezen scripts/_render_prirazeni_lib.py (role_dilu/typ_dilu/rodina_materialu).")


# zadny __pycache__ do scripts/ repa (Blender = jiny Python nez api/venv)
sys.dont_write_bytecode = True
sys.path.insert(0, _najdi_lib())
import _render_prirazeni_lib as PL  # noqa: E402

# ------------------------------------------------------------------ ctx
CTX = {}
if _opt.get("ctx"):
    with open(_opt["ctx"], encoding="utf-8") as f:
        CTX = json.load(f)

# Vychozi snimek panelu, kdyz build bezi bez ctx (stara 3-argumentova CLI):
# kopie stavu app_settings.render_prirazeni_materialu k 2026-10-01 (jen
# polozky, ktere build pouziva). S ctx se VZDY bere snimek z ctx.
PANEL_VYCHOZI = {
    "alu_material": "Alumi2", "alu_knihovna_soubor": "Alumi2.blend",
    "klt_material": "Blue Ceramic", "klt_knihovna_soubor": "modrecelo.blend",
    "cub_seda_tmava_sila": 0.1, "kryci_listy_skryt": True,
    "nahrady": [
        {"role": "black", "material": "Black"}, {"role": "plastgr", "material": "Grey"},
        {"role": "preklizkahl", "material": "brown"}, {"role": "sroub", "material": "Chrome"},
        {"role": "blueklt", "material": "KLT1"}, {"role": "multiboxarc", "material": "Multibox"},
        {"role": "red", "material": "Red"}, {"role": "zinc", "material": "Grey"},
    ],
}
PANEL = CTX.get("prirazeni_materialu")
if not isinstance(PANEL, dict):
    PANEL = PANEL_VYCHOZI
    warn("bez snimku panelu prirazeni materialu (ctx) - pouzito vychozi prirazeni k 2026-10-01")
KRYCI_LISTY_SKRYT = bool(CTX.get("kryci_listy_skryt", PANEL.get("kryci_listy_skryt", True)))

# Konstanty materialu pro three.js (pruzkum C 2026-10-01: prumery textur
# knihoven ze Sdileneho disku, hex = sRGB). Klic = normalizovany nazev
# materialu z panelu (jen [a-z0-9]). ctx["material_konstanty"] je muze
# prepsat/doplnit. Material z panelu bez radku tady = varovani + material
# z modelu (nikdy tichy vymysl).
MATERIAL_KONSTANTY = {
    "alumi2": {"hex": "#BBBAB3", "met": 1.0, "rough": 0.28},
    "klt1": {"hex": "#002995", "met": 0.224, "rough": 0.35, "coat": 0.08, "coat_rough": 0.15},
    "blueceramic": {"hex": "#0700FF", "met": 0.0755, "rough": 0.05, "coat": 1.0, "coat_rough": 0.1},
    "multibox": {"hex": "#00039A", "met": 1.0, "rough": 0.5, "coat": 1.0, "coat_rough": 0.03},
    "black": {"hex": "#000000", "met": 0.0, "rough": 0.45},
    "grey": {"hex": "#5D5D5B", "met": 0.0725, "rough": 0.263},
    "brown": {"hex": "#2B1407", "met": 0.51, "rough": 0.31},
    "chrome": {"hex": "#FCFBF7", "met": 1.0, "rough": 0.12},
    "red": {"hex": "#C1121F", "met": 0.0, "rough": 0.08},
    # kryci lista, kdyz NENI skryta (stejny sedy plast jako katalogove
    # kryci listy drazek, PALETTE_BY_HEX #666c73 v blender_render_turntable)
    "plastsvetly": {"hex": "#666C73", "met": 0.1, "rough": 0.28},
}
for _k, _v in (CTX.get("material_konstanty") or {}).items():
    if isinstance(_v, dict) and _v.get("hex"):
        MATERIAL_KONSTANTY[re.sub(r"[^a-z0-9]", "", _k.lower())] = _v
# aliasy podle jmena knihovny, kdyz je v panelu jen soubor bez nazvu materialu
MATERIAL_ALIAS = {"modrecelo": "blueceramic", "alumi2blend": "alumi2"}

# Vyrazovane retezce (jmeno uzlu/predka nebo materialu, podretezec,
# case-insensitive): vynechat_objekty z 2026-09-09_turntable_job.py +
# legsbox. "colliders" se resi zvlast (viz _je_kolizni_skupina).
VYNECHAT = ["podlaha", "karoserie", "dimension", "fixarea", "legshoverbox", "logo", "legsbox"]
OBAL_POMER = 0.6
CAND_RE = re.compile(r"^[A-Za-z_]*(\d+)x(\d+)x(\d+)", re.IGNORECASE)
CLONE_RE = re.compile(r"\(clone\)", re.IGNORECASE)
SUFFIX_RE = re.compile(r"\.\d{3}$")
ZAKAZANE_RE = re.compile(
    r"\d+x\d+x\d+|Clone|Noha|Nohy|Suplik|Police|Vysuv|Zamek|Zapadka|Doraz|pant|Kluz|logo|collider|"
    r"fixarea|LegsBox|dimension|vandr|bomgrp|sse_|Solid_|Object_|Instance|KLT|Multibox|Eurobox|Kufrik|"
    r"Pojezd|Blender|Unity|THREE|podlaha|karoser", re.IGNORECASE)
POVOLENE_JMENO_RE = re.compile(r"^(n\d+|p\d+|m\d+)?$")


# ------------------------------------------------------- souradnice
def to_gltf(v):
    """Blender (Z nahoru) -> glTF (Y nahoru). Importer pouziva swizzle
    (x, y, z)_gltf -> (x, -z, y)_blender."""
    return (float(v[0]), float(v[2]), -float(v[1]))


def from_gltf(v):
    return Vector((float(v[0]), -float(v[2]), float(v[1])))


def _bl_aabb(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def gltf_aabb(o):
    mn, mx = _bl_aabb(o)
    return (mn.x, mn.z, -mx.y), (mx.x, mx.z, -mn.y)


def _mesh_co(me):
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(n, 3)


def gltf_verts(o):
    co = _mesh_co(o.data)
    m = np.array(o.matrix_world, dtype=np.float64)
    w = co @ m[:3, :3].T + m[:3, 3]
    return np.stack([w[:, 0], w[:, 2], -w[:, 1]], axis=1)


def gltf_tris(o):
    """Trojuhelniky meshe (N, 3, 3) ve svetovych glTF mm (loop_triangles)."""
    me = o.data
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    if n == 0:
        return np.zeros((0, 3, 3))
    idx = np.empty(n * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", idx)
    return gltf_verts(o)[idx.reshape(n, 3)]


def _cesta(o):
    retez, p = [], o
    while p is not None:
        retez.append(p.name)
        p = p.parent
    return retez[::-1]


def _klic_jmena(jmeno):
    """'Suplikocel20kg130537459(Clone).001' -> 'suplikocel20kg130537459'.
    Stejny tvar jako unity_id po three.js PropertyBinding.sanitizeNodeName
    (mezery -> '_', [ ] . : / pryc), viz build_ctx.klic_unity_id."""
    n = SUFFIX_RE.sub("", jmeno or "")
    n = CLONE_RE.sub("", n)
    n = re.sub(r"_\(\d+\)$", "", n)
    return re.sub(r"[^0-9a-z_?]", "", n.lower())


# ===================================================================== (1)
bpy.ops.wm.read_factory_settings(use_empty=True)
_t_import = time.time()
bpy.ops.import_scene.gltf(filepath=GLB_IN, import_scene_extras=False, import_shading="FLAT",
                          merge_vertices=False, import_select_created_objects=False)
T_IMPORT = time.time() - _t_import
sc = bpy.context.scene
bpy.context.view_layer.update()
vsechny = list(sc.objects)
meshe_vse = [o for o in vsechny if o.type == "MESH" and o.data is not None]
MESHES_BEFORE = len(meshe_vse)
MATERIALS_BEFORE = len(bpy.data.materials)
print("IMPORT %.1fs: %d objektu, %d meshu, %d materialu" % (T_IMPORT, len(vsechny), MESHES_BEFORE, MATERIALS_BEFORE))

# Jednotky: katalogove Vandr GLB jsou v mm (scale_to_mm). Stare testovaci
# exporty (vd_test_*, karty 4899-4901) jsou v METRECH - prevod x1000 HNED
# TED, pred pravidly s prahy v mm (kryci lista 15/50 mm, znacky 20 mm,
# celo > 300 mm). Konjugace lokalnich matic S*L*S^-1 meni jen posuny,
# vrcholy se skaluji v mesh datech -> o.dimensions jsou pak take v mm.
PREVOD_Z_METRU = False
_vb = [_bl_aabb(o) for o in meshe_vse if len(o.data.vertices)]
if _vb and max(max(b[1][i] for b in _vb) - min(b[0][i] for b in _vb) for i in range(3)) < 50.0:
    PREVOD_Z_METRU = True
    _S = Matrix.Scale(1000.0, 4)
    _Si = _S.inverted()
    for _me in set(o.data for o in meshe_vse):
        _me.transform(_S)
    for _o in vsechny:
        _o.matrix_parent_inverse = _S @ _o.matrix_parent_inverse @ _Si
        _o.matrix_basis = _S @ _o.matrix_basis @ _Si
    bpy.context.view_layer.update()
    warn("vstupni GLB je v metrech (stary testovaci export) - prevedeno na mm (x1000)")

# ===================================================================== (2)
# Mapa potomku predem (Object.children v Blenderu prochazi VSECHNY objekty
# sceny - volane v cyklu to bylo O(n^2), 4917 = 18 s).
DETI = {}
for _o in vsechny:
    if _o.parent is not None:
        DETI.setdefault(_o.parent.name, []).append(_o)


def _potomci(o):
    out, fronta = [], list(DETI.get(o.name, []))
    while fronta:
        c = fronta.pop()
        out.append(c)
        fronta.extend(DETI.get(c.name, []))
    return out


_clone_cache = {}


def _ma_clone_potomka(o):
    """Koreny regalu: colliders/left|right|bulkhead, ktere obsahuji komponenty."""
    if o.name not in _clone_cache:
        _clone_cache[o.name] = any(CLONE_RE.search(c.name) for c in _potomci(o))
    return _clone_cache[o.name]


KORENY_REGALU = []
for o in vsechny:
    jm = SUFFIX_RE.sub("", o.name).lower()
    if jm in ("left", "right", "bulkhead") and o.parent is not None \
            and o.parent.name.lower().startswith("colliders") and _ma_clone_potomka(o):
        KORENY_REGALU.append(o)
STRANA_KORENE = {o.name: SUFFIX_RE.sub("", o.name).lower() for o in KORENY_REGALU}


def _koren_regalu(o):
    p = o
    while p is not None:
        if p.name in STRANA_KORENE:
            return p
        p = p.parent
    return None


def _je_kolizni_skupina(o):
    """Skupina 'colliders' UVNITR komponenty (BoxCollidery, *Dimension...).
    Horni 'colliders' je predek celeho regalu - ten ma potomky '(Clone)'."""
    return o.name.lower().startswith("colliders") and not _ma_clone_potomka(o)


def _vyrazen_jmenem(o):
    for p in _cesta(o):
        pl = p.lower()
        if any(s in pl for s in VYNECHAT):
            return True
    p = o
    while p is not None:
        if _je_kolizni_skupina(p):
            return True
        p = p.parent
    if o.type == "MESH" and o.data:
        for m in o.data.materials:
            if m is not None and any(s in m.name.lower() for s in VYNECHAT):
                return True
    return False


def _uvnitr_komponenty(o):
    p = o.parent
    while p is not None:
        if CLONE_RE.search(p.name) and p.parent is not None and "nohy" in p.parent.name.lower():
            return True
        p = p.parent
    return False


BL_BOX = {o.name: _bl_aabb(o) for o in meshe_vse}
_mn = Vector((min(b[0].x for b in BL_BOX.values()), min(b[0].y for b in BL_BOX.values()), min(b[0].z for b in BL_BOX.values())))
_mx = Vector((max(b[1].x for b in BL_BOX.values()), max(b[1].y for b in BL_BOX.values()), max(b[1].z for b in BL_BOX.values())))
SCENA_SIZE = _mx - _mn

VYRAZENO = {"jmeno": 0, "mimo_regal": 0, "obal": 0, "kryci_lista": 0, "znacka": 0, "prazdny": 0}
INFO = {}       # jmeno mesh objektu -> role/typ/rodiny/cesta (puvodni)
PRODUKT = []    # mesh objekty, ktere zustavaji
for o in meshe_vse:
    if len(o.data.polygons) == 0:
        VYRAZENO["prazdny"] += 1
        continue
    if _vyrazen_jmenem(o):
        VYRAZENO["jmeno"] += 1
        continue
    if KORENY_REGALU and _koren_regalu(o) is None:
        VYRAZENO["mimo_regal"] += 1
        continue
    mn, mx = BL_BOX[o.name]
    span = mx - mn
    velke = sum(1 for i in range(3) if SCENA_SIZE[i] > 0 and span[i] >= OBAL_POMER * SCENA_SIZE[i])
    if velke >= 2 and not _uvnitr_komponenty(o):
        VYRAZENO["obal"] += 1
        continue
    if min(span) < 0.01 and max(span) <= 20.0 and (
            PL.role_dilu(o.parent.name if o.parent else "") in ("red", "blueklt", "blue")
            or any(m is not None and PL.rodina_materialu(m.name).lower() in ("red", "blue klt") for m in o.data.materials)):
        # plocha cervena/modra ploska nulove tloustky (stohovaci znacky,
        # VANDR_DILY_ZNACENI.md - konvence zdrojoveho modelu, ne fyzicky dil).
        # Ploche chromove ctverecky 8x8 (sroub) render ukazuje - zustavaji.
        VYRAZENO["znacka"] += 1
        continue
    if KRYCI_LISTY_SKRYT:
        dims = sorted(o.dimensions)
        if any(m is not None and "klt" in m.name.lower() for m in o.data.materials) \
                and dims[0] < 15.0 and dims[1] < 50.0:
            # _je_kryci_lista_klt (blender_render_turntable.py) - render ji skryva
            VYRAZENO["kryci_lista"] += 1
            continue
    cesta = _cesta(o)
    INFO[o.name] = {
        "role": PL.role_dilu(o.parent.name) if o.parent is not None else "",
        "typ": PL.typ_dilu(cesta),
        "rodiny": [PL.rodina_materialu(m.name) if m is not None else "" for m in o.data.materials],
        "cesta": cesta,
    }
    PRODUKT.append(o)

T_VYRAZENI = time.time() - _t_import - T_IMPORT
if not PRODUKT:
    raise SystemExit("Po vyrazeni nezustal zadny dil produktu - neni co exportovat.")
_pmn = [min(BL_BOX[o.name][0][i] for o in PRODUKT) for i in range(3)]
_pmx = [max(BL_BOX[o.name][1][i] for o in PRODUKT) for i in range(3)]
if max(_pmx[i] - _pmn[i] for i in range(3)) < 50.0:
    raise SystemExit("Model je po prevodu porad mensi nez 50 mm (%.2f) - neplatny vstup."
                     % max(_pmx[i] - _pmn[i] for i in range(3)))
if not KORENY_REGALU:
    warn("GLB nema strukturu colliders/left|right|bulkhead - vyrazeni jen podle jmen a obalu")
print("VYRAZENO:", VYRAZENO, "zustava meshu:", len(PRODUKT))

# Profily pro geom.json (zpetna kompatibilita - API vraci pocet_profilu)
PROFILY = []
for o in PRODUKT:
    m = CAND_RE.match(o.name or "")
    if not m:
        continue
    mn, mx = BL_BOX[o.name]
    d = (mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    PROFILY.append({"prurez": sorted((int(m.group(1)), int(m.group(2)))), "delka_mm": round(max(d), 1)})

# ===================================================== komponenty a front
KOMPONENTY = []
_ctx_podle_klice = {}
for k in (CTX.get("komponenty") or []):
    if isinstance(k, dict) and k.get("klic"):
        _ctx_podle_klice.setdefault(k["klic"], k)
_produkt_set = set(o.name for o in PRODUKT)
for o in vsechny:
    if not CLONE_RE.search(o.name) or o.parent is None or "nohy" not in o.parent.name.lower():
        continue
    jl = o.name.lower()
    if jl.startswith("noha") or "legsbox" in jl:
        continue
    d = o.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))   # glTF lokalni -Y
    g = to_gltf(d)
    h = math.hypot(g[0], g[2])
    front_c = (g[0] / h, 0.0, g[2] / h) if h > 1e-6 else None
    koren = _koren_regalu(o)
    meshes = [c for c in _potomci(o) if c.name in _produkt_set]
    klic = _klic_jmena(o.name)
    KOMPONENTY.append({
        "obj": o, "name": o.name, "key": klic, "ctx": _ctx_podle_klice.get(klic),
        "side": STRANA_KORENE.get(koren.name, "") if koren else "", "front": front_c, "meshes": meshes,
    })
if _ctx_podle_klice:
    nesparovane = sorted(set(k["key"] for k in KOMPONENTY if k["ctx"] is None))
    if nesparovane:
        warn("komponenty bez zaznamu v ctx (unity_id): %d" % len(nesparovane))


def _front_z_azimutu(az):
    a = math.radians(float(az))
    return (math.sin(a), 0.0, math.cos(a))   # kontrola.html vdCameraDir (el=0)


FRONT, FRONT_ZDROJ = None, ""
smery = [k["front"] for k in KOMPONENTY if k["front"] is not None]
az_db = CTX.get("vandr_predni_azimut_deg")
f_db = _front_z_azimutu(az_db) if az_db is not None else None
if smery:
    sx, sz = sum(s[0] for s in smery), sum(s[2] for s in smery)
    h = math.hypot(sx, sz)
    prumer = (sx / h, 0.0, sz / h) if h > 1e-6 else None
    jednotne = prumer is not None and all(s[0] * prumer[0] + s[2] * prumer[2] > math.cos(math.radians(15)) for s in smery)
    if jednotne:
        FRONT, FRONT_ZDROJ = prumer, "komponenty"
        if f_db is not None and FRONT[0] * f_db[0] + FRONT[2] * f_db[2] < math.cos(math.radians(30)):
            warn("celo z matic komponent (%.2f, %.2f) nesouhlasi s vandr_predni_azimut_deg %s - pouzito z komponent"
                 % (FRONT[0], FRONT[2], az_db))
    elif f_db is not None:
        FRONT, FRONT_ZDROJ = f_db, "azimut_db"
        warn("komponenty miri do vice smeru (obe strany?) - celo podle vandr_predni_azimut_deg %s" % az_db)
    else:
        # vetsina podle stran
        FRONT, FRONT_ZDROJ = max(smery, key=lambda s: sum(1 for t in smery if s[0] * t[0] + s[2] * t[2] > 0.9)), "vetsina"
        warn("komponenty miri do vice smeru a chybi vandr_predni_azimut_deg - celo podle vetsiny komponent")
elif f_db is not None:
    FRONT, FRONT_ZDROJ = f_db, "azimut_db"
else:
    # odhad z geometrie: osa cela = vodorovna osa s mensim rozmerem produktu
    # (hloubka regalu), smer k ose vozu (pocatek; levy regal X>0 -> -X,
    # pravy X<0 -> +X, overeno na 4917)
    _pcx, _pcz = (_pmn[0] + _pmx[0]) / 2.0, -(_pmn[1] + _pmx[1]) / 2.0
    if (_pmx[0] - _pmn[0]) <= (_pmx[1] - _pmn[1]):
        FRONT = (-1.0 if _pcx > 0 else 1.0, 0.0, 0.0)
    else:
        FRONT = (0.0, 0.0, -1.0 if _pcz > 0 else 1.0)
    FRONT_ZDROJ = "odhad_geometrie"
    warn("celo nelze urcit z komponent ani z azimutu - odhad z geometrie (hloubka regalu, smer k ose vozu)")


def _smer_txt(v):
    if v is None:
        return "?"
    for jm, ax in (("+X", (1, 0)), ("-X", (-1, 0)), ("+Z", (0, 1)), ("-Z", (0, -1))):
        if v[0] * ax[0] + v[2] * ax[1] > math.cos(math.radians(10)):
            return jm
    return "%.0f deg" % (math.degrees(math.atan2(v[0], v[2])) % 360)


FRONT_SMERY = {}
for _k in KOMPONENTY:
    _t = "%s %s" % (_k["side"] or "?", _smer_txt(_k["front"]))
    FRONT_SMERY[_t] = FRONT_SMERY.get(_t, 0) + 1
# zaokrouhleni na osu, kdyz je do 1 stupne (cisty vektor v datech)
_fx, _fz = FRONT[0], FRONT[2]
for ax in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    if _fx * ax[0] + _fz * ax[1] > math.cos(math.radians(1)):
        _fx, _fz = float(ax[0]), float(ax[1])
FRONT = (_fx, 0.0, _fz)


# ============================================= hook pohyblivych skupin (4)
ROZRIZNUTO = [0]


def rozdel_rovinou(o, bod, normala):
    """Rozdeli mesh dilu rovinou (bod a normala v glTF svete, mm) na dva NOVE
    objekty (pod, nad) - napr. pant, ktery je v Unity jeden mesh pro obe
    kridla. Rez se zaslepi (holes_fill jen na hranach rezu). Puvodni dil
    se vyradi z PRODUKT, nove se zaregistruji (INFO, PRODUKT), materialove
    sloty zustanou. Vraci (pod, nad) nebo None (rovina dil neprotina)."""
    import bmesh
    if o not in PRODUKT or o.type != "MESH" or o.name not in INFO:
        return None
    mw = o.matrix_world.copy()
    p_loc = mw.inverted() @ from_gltf(bod)
    n_loc = (mw.to_3x3().transposed() @ from_gltf(normala)).normalized()
    vystup = []
    for strana in ("pod", "nad"):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-4,
                                     plane_co=p_loc, plane_no=n_loc,
                                     clear_outer=(strana == "pod"), clear_inner=(strana == "nad"))
        hrany = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_valid and e.is_boundary]
        if hrany:
            bmesh.ops.holes_fill(bm, edges=hrany, sides=0)
        if not bm.faces:
            bm.free()
            break
        me = bpy.data.meshes.new("v3dsplit")
        bm.to_mesh(me)
        bm.free()
        for m in o.data.materials:
            me.materials.append(m)
        ob = bpy.data.objects.new("v3dsplit_" + strana, me)
        sc.collection.objects.link(ob)
        ob.matrix_world = mw
        vystup.append(ob)
    if len(vystup) != 2:
        bpy.data.batch_remove([ob for ob in vystup] + [ob.data for ob in vystup])
        return None
    bpy.context.view_layer.update()
    for ob in vystup:
        INFO[ob.name] = dict(INFO[o.name])
        PRODUKT.append(ob)
    PRODUKT.remove(o)
    ROZRIZNUTO[0] += 1
    return vystup[0], vystup[1]


PRIDANO = [0]


def pridej_dil(jmeno, verts, tris, role="red", typ="doraz", rodina="Red"):
    """Pridani DOPLNENEHO dilu, ktery zdrojovy model nema (Robert 2026-10-02:
    dorazy beznych dvirek). verts (N, 3) numpy ve svetovych glTF mm, tris (M, 3)
    indexy (poradi vrcholu = vnejsi normala); novy mesh objekt se zaregistruje
    jako dil produktu (PRODUKT, INFO) s rolí/rodinou materialu - material pak
    jde stejnou cestou jako kazdy jiny dil (panel prirazeni, role "red" ->
    konstanty "red"). Zadny dil se nepridava mimo tuhle funkci. Vraci bpy objekt."""
    mat = bpy.data.materials.get(rodina)
    if mat is None:
        mat = bpy.data.materials.new(rodina)
        if mat.node_tree is None:
            mat.use_nodes = True
        b = next((n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
        if b is not None:
            b.inputs["Base Color"].default_value = _hex_lin_barva("#C1121F") + (1.0,)
    V = np.asarray(verts, dtype=np.float64)
    bl = [(float(v[0]), -float(v[2]), float(v[1])) for v in V]       # glTF -> Blender (from_gltf)
    me = bpy.data.meshes.new("v3dpridany")
    me.from_pydata(bl, [], [tuple(int(i) for i in t) for t in tris])
    me.update(calc_edges=True)
    me.materials.append(mat)
    ob = bpy.data.objects.new("v3dpridany_" + jmeno, me)
    sc.collection.objects.link(ob)
    bpy.context.view_layer.update()
    INFO[ob.name] = {"role": role, "typ": typ, "rodiny": [rodina], "cesta": ["v3dpridany", jmeno]}
    PRODUKT.append(ob)
    PRIDANO[0] += 1
    return ob


def odeber_dil(ob):
    """Zrusi dil pridany pridej_dil (kdyz komponenta pri detekci selze)."""
    if ob in PRODUKT:
        PRODUKT.remove(ob)
    INFO.pop(ob.name, None)
    me = ob.data
    bpy.data.objects.remove(ob)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    PRIDANO[0] -= 1


def _hex_lin_barva(hexc):
    h = hexc.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


class BuildApi:
    def __init__(self):
        self.ctx = CTX
        self.front = FRONT
        self.components = KOMPONENTY
        self.produkt = PRODUKT

    @staticmethod
    def info(o):
        return INFO.get(o.name if hasattr(o, "name") else o)

    @staticmethod
    def aabb(o):
        return gltf_aabb(o)

    @staticmethod
    def verts(o):
        return gltf_verts(o)

    @staticmethod
    def tris(o):
        return gltf_tris(o)

    to_gltf = staticmethod(to_gltf)
    from_gltf = staticmethod(from_gltf)
    warn = staticmethod(warn)
    split = staticmethod(rozdel_rovinou)
    add_part = staticmethod(pridej_dil)
    remove_part = staticmethod(odeber_dil)


POHYBY_INFO = {}


def nacti_pohyblive_skupiny(api):
    """Zavola vandr_motions.detect(api), pokud modul existuje. Vraci
    (pivots, motions, dims) po validaci; chyba modulu = varovani a zadne
    pohyby (vse staticke). Rozriznute dily (api.split) zustavaji v PRODUKT
    i pri chybe modulu - obe pulky jsou pak staticke (vizualne beze zmeny)."""
    if _opt.get("no-motions"):
        return [], [], []
    cesta = _opt.get("motions") or os.path.join(SCRIPT_DIR, "vandr_motions.py")
    if not os.path.isfile(cesta):
        return [], [], []
    try:
        spec = importlib.util.spec_from_file_location("vandr_motions", cesta)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["vandr_motions"] = mod
        spec.loader.exec_module(mod)
        res = mod.detect(api) if hasattr(mod, "detect") else None
    except Exception as e:  # modul je cizi kod - nesmi shodit build
        import traceback
        traceback.print_exc()
        warn("modul pohybu selhal (%s: %s) - model bez animaci" % (type(e).__name__, e))
        return [], [], []
    if not res:
        return [], [], []
    for w in (res.get("warnings") or []):
        warn(w)
    if isinstance(res.get("info"), dict):
        POHYBY_INFO.update(res["info"])
    return validuj_pohyby(res.get("pivots") or [], res.get("motions") or [], res.get("dims") or [])


def _cislo(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _vec3(x):
    return isinstance(x, (list, tuple)) and len(x) == 3 and all(_cislo(c) for c in x)


DIM_T_RE = re.compile(r"^[0-9 ]{1,7}( mm)?$")
DRUHY_POHYBU = {"drawer", "door", "floor_door", "box", "slide"}
SUBS_POHYBU = ("klt", "multibox", "eurobox", "kufrik")                 # motions[].sub, jen k=box


def validuj_pohyby(pivots, motions, dims):
    objekty = {o.name: o for o in PRODUKT}
    platne, pouzite, mapa = [], set(), {}
    for pv in pivots:
        pid = pv.get("id") if isinstance(pv, dict) else None
        if not isinstance(pid, str) or not pid or pid in mapa or not _vec3(pv.get("origin")):
            warn("pivot zahozen (chybi id/origin nebo duplicita)")
            continue
        obj = []
        for jm in (pv.get("objects") or []):
            if jm in objekty and jm not in pouzite:
                obj.append(jm)
                pouzite.add(jm)
            elif jm in pouzite:
                warn("dil je ve dvou pivotech - ponechan v prvnim")
        par = pv.get("parent")
        if par is not None and par not in mapa:
            warn("pivot s neznamym rodicem zahozen")
            for jm in obj:
                pouzite.discard(jm)
            continue
        mapa[pid] = "p%02d" % (len(mapa) + 1)
        platne.append({"id": mapa[pid], "origin": [float(c) for c in pv["origin"]],
                       "parent": mapa[par] if par is not None else None, "objects": obj})
    vystup_m = []
    for m in motions:
        try:
            k = m.get("k")
            steps = []
            for s in m.get("steps") or []:
                if s.get("p") not in mapa or s.get("op") not in ("T", "R") or not _vec3(s.get("ax")) \
                        or not _cislo(s.get("v")) or not _cislo(s.get("ms")):
                    raise ValueError("krok")
                ax = [float(c) for c in s["ax"]]
                n = math.sqrt(sum(c * c for c in ax))
                if n < 1e-6:
                    raise ValueError("osa")
                steps.append({"p": mapa[s["p"]], "op": s["op"], "ax": [round(c / n, 6) + 0.0 for c in ax],
                              "v": round(float(s["v"]), 3), "ms": int(s["ms"])})
            if k not in DRUHY_POHYBU or not steps:
                raise ValueError("druh")
            pick = [mapa[p] for p in (m.get("pick") or []) if p in mapa]
            mo = {"id": "m%d" % (len(vystup_m) + 1), "k": k}
            if m.get("sub") is not None:
                if k == "box" and m["sub"] in SUBS_POHYBU:
                    mo["sub"] = m["sub"]
                else:
                    warn("pohyb %s: neplatny druh (sub) zahozen" % mo["id"])
            mo["n"] = int(m.get("n") or (len(vystup_m) + 1))
            mo["steps"] = steps
            mo["pick"] = pick or [steps[-1]["p"]]
            vystup_m.append(mo)
        except (ValueError, AttributeError, TypeError) as e:
            warn("pohyb zahozen (neplatny %s)" % e)
    vystup_d = []
    for d in dims:
        try:
            if not (_vec3(d.get("a")) and _vec3(d.get("b")) and _vec3(d.get("o"))):
                raise ValueError
            t = str(d.get("t"))
            if not DIM_T_RE.match(t):
                raise ValueError
            p = d.get("p")
            vystup_d.append({"a": [round(float(c), 1) for c in d["a"]], "b": [round(float(c), 1) for c in d["b"]],
                             "o": [round(float(c), 1) for c in d["o"]], "t": t, "l": 2 if d.get("l") == 2 else 1,
                             "p": mapa.get(p) if p is not None else None})
        except (ValueError, AttributeError, TypeError):
            warn("kota z modulu pohybu zahozena (neplatna)")
    return platne, vystup_m, vystup_d


API = BuildApi()
_t_poh = time.time()
PIVOTS, MOTIONS, DIMS_L2 = nacti_pohyblive_skupiny(API)
T_POHYBY = time.time() - _t_poh
POHYBLIVE = {}
for pv in PIVOTS:
    for jm in pv["objects"]:
        POHYBLIVE[jm] = pv["id"]
POHYBY_DRUHY = {}
POHYBY_BOXY_SUB = {}
for _m in MOTIONS:
    POHYBY_DRUHY[_m["k"]] = POHYBY_DRUHY.get(_m["k"], 0) + 1
    if _m["k"] == "box":
        POHYBY_BOXY_SUB[_m.get("sub") or "?"] = POHYBY_BOXY_SUB.get(_m.get("sub") or "?", 0) + 1
print("POHYBY: %d pivotu, %d pohybu %s, %d pohyblivych meshu, %d rozriznutych dilu"
      % (len(PIVOTS), len(MOTIONS), POHYBY_DRUHY, len(POHYBLIVE), ROZRIZNUTO[0]))


# ===================================================================== (3)
def _hex_lin(hexc):
    h = hexc.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


VD_ROLE, VD_NAHRADY = {}, {}
for radek in (PANEL.get("nahrady") or []):
    if not isinstance(radek, dict):
        continue
    material = (radek.get("material") or "").strip() or os.path.splitext((radek.get("knihovna_soubor") or "").strip())[0]
    if not material:
        continue
    typ = (radek.get("typ") or "").strip().lower()
    role = (radek.get("role") or "").strip().lower()
    rodina = (radek.get("rodina") or "").strip().lower()
    if role:
        VD_ROLE[(role, typ)] = material
    elif rodina:
        VD_NAHRADY[(rodina, typ)] = material


def _panel_material(klic_mat, klic_kn):
    if not (PANEL.get(klic_kn) or "").strip():
        return ""
    return (PANEL.get(klic_mat) or "").strip() or os.path.splitext(PANEL[klic_kn].strip())[0]


ALU_MATERIAL = _panel_material("alu_material", "alu_knihovna_soubor")
KLT_MATERIAL = _panel_material("klt_material", "klt_knihovna_soubor")
CUB_SEDA_SILA = float(PANEL.get("cub_seda_tmava_sila") or 0.0)


def _konstanty_panelu(nazev):
    k = _norm(nazev)
    k = MATERIAL_ALIAS.get(k, k)
    c = MATERIAL_KONSTANTY.get(k)
    if c is None:
        warn("material '%s' z panelu nema konstanty pro 3D nabidku - pouzit material z modelu" % nazev.strip())
        return None
    return {"rgb": _hex_lin(c["hex"]), "a": 1.0, "met": float(c.get("met", 0.0)), "rough": float(c.get("rough", 0.5)),
            "coat": float(c.get("coat", 0.0)), "coat_rough": float(c.get("coat_rough", 0.03))}


def _konstanty_z_modelu(m, ztmavit=0.0):
    b = None
    if m is not None and m.node_tree is not None:
        b = next((n for n in m.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if b is None:
        return {"rgb": (0.6, 0.6, 0.6), "a": 1.0, "met": 0.0, "rough": 0.5, "coat": 0.0, "coat_rough": 0.03}
    rgb = tuple(float(c) for c in b.inputs["Base Color"].default_value[:3])
    if ztmavit > 0:
        rgb = tuple(c * (1.0 - ztmavit) for c in rgb)
    return {"rgb": rgb, "a": float(b.inputs["Alpha"].default_value), "met": float(b.inputs["Metallic"].default_value),
            "rough": float(b.inputs["Roughness"].default_value), "coat": 0.0, "coat_rough": 0.03}


def _je_celo_supliku(o, info):
    # _je_celo_supliku_klt (blender_render_turntable.py): tyrkys + role drawer
    # nebo (>300 mm a typ suplik)
    if not any("tyrkys" in (m.name.lower() if m else "") for m in o.data.materials):
        return False
    return info["role"] == "drawer" or (max(o.dimensions) > 300.0 and info["typ"] == "suplik")


def cilove_konstanty(o, m):
    """Poradi = blender_render_turntable.py: radek role/rodiny (ne pro kryci
    listu) > cub seda > kryci lista (skryta uz ve vyrazeni, jinak sedy plast)
    > celo supliku > hlinik > material z modelu."""
    info = INFO[o.name]
    nazev = m.name.lower() if m is not None else ""
    ro, typ = info["role"], info["typ"]
    _d = sorted(o.dimensions)
    je_lista = "klt" in nazev and _d[0] < 15.0 and _d[1] < 50.0
    cil = None
    if not je_lista:
        cil = VD_ROLE.get((ro, typ)) or VD_ROLE.get((ro, ""))
        if not cil and m is not None:
            r = PL.rodina_materialu(m.name).lower()
            cil = VD_NAHRADY.get((r, typ)) or VD_NAHRADY.get((r, ""))
    if cil:
        c = _konstanty_panelu(cil)
        if c is not None:
            return c
    if CUB_SEDA_SILA > 0 and "cub seda" in nazev:
        return _konstanty_z_modelu(m, CUB_SEDA_SILA)
    if je_lista:
        return _konstanty_panelu("plastsvetly")
    if KLT_MATERIAL and _je_celo_supliku(o, info):
        c = _konstanty_panelu(KLT_MATERIAL)
        if c is not None:
            return c
    if ALU_MATERIAL and "alu" in nazev:
        c = _konstanty_panelu(ALU_MATERIAL)
        if c is not None:
            return c
    return _konstanty_z_modelu(m)   # nevyplneny radek = material z modelu


MATERIALY = {}   # klic konstant -> bpy material (zatim docasne jmeno)


def _klic_konstant(c):
    return (tuple(round(x, 3) for x in c["rgb"]), round(c["a"], 3), round(c["met"], 3), round(c["rough"], 3),
            round(c["coat"], 3), round(c["coat_rough"], 3))


def material_pro(c):
    k = _klic_konstant(c)
    if k in MATERIALY:
        return MATERIALY[k]
    mat = bpy.data.materials.new("v3dtmp%d" % len(MATERIALY))
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(out.inputs["Surface"], b.outputs["BSDF"])
    b.inputs["Base Color"].default_value = (k[0][0], k[0][1], k[0][2], 1.0)
    b.inputs["Metallic"].default_value = k[2]
    b.inputs["Roughness"].default_value = k[3]
    b.inputs["Alpha"].default_value = k[1]
    b.inputs["Coat Weight"].default_value = k[4]
    # glTF exporter vynecha Coat Roughness rovne Blender vychozi 0.03 (glTF
    # vychozi je 0) - lak by vysel zrcadlovy; 0.0301 se zapise. BEZ laku
    # (coat 0) musi zustat presne 0.03, jinak exporter prida KHR_materials_
    # clearcoat ke kazdemu materialu a three pouzije vsude MeshPhysicalMaterial.
    if k[4] > 0:
        b.inputs["Coat Roughness"].default_value = 0.0301 if abs(k[5] - 0.03) < 1e-4 else k[5]
    else:
        b.inputs["Coat Roughness"].default_value = 0.03
    if k[1] < 0.999:
        mat.surface_render_method = "BLENDED"
    mat.diffuse_color = (k[0][0], k[0][1], k[0][2], k[1])
    MATERIALY[k] = mat
    return mat


# Prirazeni: kazdy slot kazdeho dilu -> cilovy material (podle puvodniho
# slotu, pred jakoukoli zmenou)
_t_mat = time.time()
SLOTY = {}
_LADENI = {}
for o in PRODUKT:
    SLOTY[o.name] = [material_pro(cilove_konstanty(o, m)) for m in o.data.materials] or \
                    [material_pro(_konstanty_z_modelu(None))]
    if os.environ.get("V3D_DEBUG"):
        for m, cil in zip(o.data.materials, SLOTY[o.name]):
            k = (INFO[o.name]["role"], INFO[o.name]["typ"], PL.rodina_materialu(m.name) if m else "", cil.name)
            _LADENI[k] = _LADENI.get(k, 0) + 1
T_MATERIALY = time.time() - _t_mat
if _LADENI:
    for k in sorted(_LADENI, key=lambda k: k[3]):
        print("LADENI material role=%s typ=%s rodina=%s -> %s (%dx)" % (k + (_LADENI[k],)))


# ===================================================================== (4)
ZRCADLENE = [0]
MAT_KLIC = {m.name: k for k, m in MATERIALY.items()}
# Draw cally pohyblivych skupin (kazdy pivot = 1 primitiva na material): v
# pivotu se material, ktery nesou JEN drobne dily (nejvetsi rozmer do
# DROBNY_MM - srouby, krytky, knofliky, pin), prevezme od nejpodobnejsiho
# materialu velkeho dilu tehoz pivotu (metaliza, jas, drsnost) - ale jen kdyz
# je vzhledove blizko (VZHLED_MAX, napr. chrom -> hlinik) nebo jsou dily
# nepatrne (do NEPATRNY_MM, srouby); cerna krytka 30 mm tak modra nezbude.
# Vzhledove blizke materialy velkych dilu tehoz pivotu se slouci take (chrom
# vnitrnich kolejnic -> hlinik). Pivot jen z drobnych dilu (pin = kolik +
# knoflik) dostane jeden material - ten s nejvetsim objemem. Staticky uzel
# se nemeni.
DROBNY_MM = 30.0
NEPATRNY_MM = 12.0
VZHLED_MAX = 0.6
OMEZENE_MATERIALY = {"pivotu": 0, "slotu": 0}


def _srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055


def _vzhled(mat):
    """(sRGB r, g, b, metaliza, drsnost) materialu (z klice konstant)."""
    k = MAT_KLIC[mat.name]
    return tuple(_srgb(c) for c in k[0]) + (k[2], k[3])


def _hex(mat):
    return "#%02X%02X%02X" % tuple(int(round(max(0.0, min(1.0, c)) * 255)) for c in _vzhled(mat)[:3])


def omez_materialy_pivotu(objs):
    """{jmeno materialu: cilovy material} pro jeden pivot (drobne dily a vzhledove blizke materialy)."""
    vel, objem, mats = {}, {}, {}
    for o in objs:
        if o.name.startswith("v3dpridany_r"):
            continue       # razitka loga (bot4 2026-10-06) si drzi svuj material - oranzove logo nesmi splynout s okolim
        d = sorted(float(c) for c in o.dimensions)
        for mat in SLOTY[o.name]:
            mats[mat.name] = mat
            vel[mat.name] = max(vel.get(mat.name, 0.0), d[2])
            objem[mat.name] = objem.get(mat.name, 0.0) + max(d[0], 1.0) * max(d[1], 1.0) * max(d[2], 1.0)
    if os.environ.get("V3D_DEBUG") == "2":
        print("LADENI pivot %s: %s" % (sorted(o.name for o in objs)[0][:20], "; ".join(
            "%s %s met=%.2f vel=%.0f n=%d" % (n, _hex(mats[n]), _vzhled(mats[n])[3], vel[n],
                                    sum(1 for o in objs if any(m.name == n for m in SLOTY[o.name])))
            for n in sorted(mats))))
    if len(mats) < 2:
        return {}
    velke = [n for n in mats if vel[n] > DROBNY_MM]
    remap = {}

    def vzdal(n, v):
        a, b = _vzhled(mats[n]), _vzhled(mats[v])
        return math.dist(a[:3], b[:3]) + 2.0 * abs(a[3] - b[3]) + 0.5 * abs(a[4] - b[4])
    if not velke:
        cil = max(mats, key=lambda n: (objem[n], n))
        remap = {n: mats[cil] for n in mats if n != cil}
    else:
        for n in mats:
            if n in velke:
                continue
            cil = min(velke, key=lambda v: (vzdal(n, v), v))
            if vel[n] <= NEPATRNY_MM or vzdal(n, cil) <= VZHLED_MAX:
                remap[n] = mats[cil]
        # zbyle vzhledove blizke materialy (chrom kolejnic -> hlinik) do toho s vetsim objemem
        zbyle = sorted((n for n in mats if n not in remap), key=lambda n: (objem[n], n))
        for i, n in enumerate(zbyle):
            vetsi = [v for v in zbyle[i + 1:] if v not in remap and vzdal(n, v) <= VZHLED_MAX]
            if vetsi:
                remap[n] = mats[min(vetsi, key=lambda v: (vzdal(n, v), v))]
        for n in list(remap):          # retezeni a -> b -> c
            c = remap[n]
            while c.name in remap:
                c = remap[c.name]
            remap[n] = c
    if remap:
        OMEZENE_MATERIALY["pivotu"] += 1
        OMEZENE_MATERIALY["slotu"] += len(remap)
        if os.environ.get("V3D_DEBUG"):
            print("LADENI omez_materialy %s: %s" % (
                sorted(set(o.name for o in objs))[:3],
                ", ".join("%s %s(%.0f mm %s)->%s %s" % (n, _hex(mats[n]), vel[n], ",".join(sorted(set(
                    o.name[:14] for o in objs if any(m.name == n for m in SLOTY[o.name]))))[:60], c.name, _hex(c))
                          for n, c in sorted(remap.items()))))
    return remap


def _sluc(objs, jmeno, posun=None, remap=None):
    """Slouci meshe (svetove souradnice Blenderu, volitelne posunute o
    -posun) do jednoho nove vytvoreneho mesh datablocku. Material slotu =
    SLOTY (pripadne prevedeny pres remap {jmeno: material}). Zaporny
    determinant matice = otoceni poradi vrcholu polygonu."""
    co_all, loops_all, starts_all, matidx_all = [], [], [], []
    mats, mat_idx = [], {}
    v_off = l_off = 0
    for o in objs:
        me = o.data
        mw = np.array(o.matrix_world, dtype=np.float64)
        co = _mesh_co(me)
        w = co @ mw[:3, :3].T + mw[:3, 3]
        if posun is not None:
            w = w - np.array(posun, dtype=np.float64)
        npoly = len(me.polygons)
        nloop = len(me.loops)
        ls = np.empty(npoly, dtype=np.int64)
        lt = np.empty(npoly, dtype=np.int64)
        me.polygons.foreach_get("loop_start", ls)
        me.polygons.foreach_get("loop_total", lt)
        vi = np.empty(nloop, dtype=np.int64)
        me.loops.foreach_get("vertex_index", vi)
        mi = np.empty(npoly, dtype=np.int64)
        me.polygons.foreach_get("material_index", mi)
        if np.linalg.det(mw[:3, :3]) < 0:
            ZRCADLENE[0] += 1
            pid = np.repeat(np.arange(npoly), lt)
            pos = np.arange(nloop) - ls[pid]
            vi = vi[ls[pid] + (lt[pid] - 1 - pos)]
        sloty = [remap.get(m.name, m) for m in SLOTY[o.name]] if remap else SLOTY[o.name]
        mapa = np.empty(max(len(sloty), 1), dtype=np.int64)
        for si, mat in enumerate(sloty):
            if mat.name not in mat_idx:
                mat_idx[mat.name] = len(mats)
                mats.append(mat)
            mapa[si] = mat_idx[mat.name]
        mi = mapa[np.clip(mi, 0, len(sloty) - 1)]
        co_all.append(w)
        loops_all.append(vi + v_off)
        starts_all.append(ls + l_off)
        matidx_all.append(mi)
        v_off += len(me.vertices)
        l_off += nloop
    me_new = bpy.data.meshes.new(jmeno)
    co = np.concatenate(co_all) if co_all else np.zeros((0, 3))
    lo = np.concatenate(loops_all) if loops_all else np.zeros(0, dtype=np.int64)
    st = np.concatenate(starts_all) if starts_all else np.zeros(0, dtype=np.int64)
    mi = np.concatenate(matidx_all) if matidx_all else np.zeros(0, dtype=np.int64)
    me_new.vertices.add(len(co))
    me_new.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me_new.loops.add(len(lo))
    me_new.loops.foreach_set("vertex_index", lo.astype(np.int32))
    me_new.polygons.add(len(st))
    me_new.polygons.foreach_set("loop_start", st.astype(np.int32))
    me_new.polygons.foreach_set("material_index", mi.astype(np.int32))
    me_new.polygons.foreach_set("use_smooth", np.zeros(len(st), dtype=bool))
    me_new.update(calc_edges=True)
    for mat in mats:
        me_new.materials.append(mat)
    return me_new


# ============================================================ razitka loga (bot4 2026-10-06)
# Robert 2026-10-06 ("v modelu 3D v online nabidce postradam razitka logo"), pravidlo 2026-09-06: razitkovani = stupen 2 = model
# v nabidce. ctx["razitka"] (scripts/v3d/build_ctx.py, z shop_products.vandr_razitka_json): vypln drazky + logo LOGIMAN.CZ, pozice
# v mm a quaternion v glTF ramu katalogoveho GLB karty. Razitka se vlozi JAKO DALSI DILY PRED slucovanim (stejna cesta jako
# pridej_dil) pod NEUTRALNIM jmenem a materialem (v3dpridany_r<N> -> po prejmenovani n<i>/m<NN>; sanitizer v api/v3d_glb.py
# odmita jmena logo|vandr|..., "logo" v ZDROJOVEM modelu = logo dodavatele, to zustava vyrazene) a priradi se POHYBLIVE SKUPINE,
# jejiz profil lezi pod razitkem (stred razitka v AABB dilu skupiny, tolerance), aby se hybala se suplikem/dvirky; jinak jsou
# staticka. Razitka do rozmeru ani kot nepatri (PROFIL_V je jen z profilu, INFO cesta razitka nema prurez).
RAZITKA_N = [0]
RAZITKA_POHYBLIVA = [0]
RAZITKO_TOL_MM = 4.0


def _rot_z_quat(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


RAZITKO_TRI_MAX = 1000     # katalogove logo ma 8152 trojuhelniku (zaoblene hranoly) - 9 kusu by zvetsilo zakaznicky model 0,8 -> 6,4 MB


def _nacti_razitkovy_dil(cesta):
    """Katalogovy GLB razitka -> (vrcholy (N,3) v glTF mm, trojuhelniky (M,3)); dily GLB se slouci. Mesh nad RAZITKO_TRI_MAX
    trojuhelniku se zjednodusi (Decimate collapse; logo = rada zaoblenych hranolu, po zjednoduseni jen ostrejsi rohy).
    Importovane objekty se hned odstrani (meshe/materialy uklidi zaverecny batch_remove)."""
    pred = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=cesta, import_scene_extras=False, import_shading="FLAT",
                              merge_vertices=False, import_select_created_objects=False)
    bpy.context.view_layer.update()
    nove = [o for o in bpy.data.objects if o not in pred]
    V, T, off = [], [], 0
    for o in nove:
        if o.type != "MESH" or o.data is None or len(o.data.vertices) == 0:
            continue
        me = o.data
        me.calc_loop_triangles()
        puvodne = len(me.loop_triangles)
        if puvodne > RAZITKO_TRI_MAX:
            mod = o.modifiers.new("v3d_decim", "DECIMATE")
            mod.ratio = max(0.02, RAZITKO_TRI_MAX / float(puvodne))
            ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
            me = bpy.data.meshes.new_from_object(ev)
            me.calc_loop_triangles()
        n = len(me.loop_triangles)
        if n == 0:
            continue
        idx = np.empty(n * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("vertices", idx)
        co = _mesh_co(me)
        m = np.array(o.matrix_world, dtype=np.float64)
        w = co @ m[:3, :3].T + m[:3, 3]
        v = np.stack([w[:, 0], w[:, 2], -w[:, 1]], axis=1)            # Blender -> glTF (jako gltf_verts)
        V.append(v)
        T.append(idx.reshape(n, 3) + off)
        off += len(v)
    for o in nove:
        bpy.data.objects.remove(o)
    if not V:
        return None, None
    return np.concatenate(V), np.concatenate(T)


def _pivot_pod_razitkem(stred):
    """id pivotu, jehoz dil (AABB + tolerance) obsahuje stred razitka; pri vice shodach dil s nejmensim objemem (nejkonkretnejsi);
    None = staticke."""
    nejlepsi, objem_min = None, None
    for pv in PIVOTS:
        jmena = set(pv["objects"])
        for o in PRODUKT:
            if o.name not in jmena or o.name.startswith("v3dpridany_r"):
                continue
            lo, hi = gltf_aabb(o)
            if all(lo[i] - RAZITKO_TOL_MM <= stred[i] <= hi[i] + RAZITKO_TOL_MM for i in range(3)):
                obj = float(np.prod([max(hi[i] - lo[i], 1.0) for i in range(3)]))
                if objem_min is None or obj < objem_min:
                    nejlepsi, objem_min = pv["id"], obj
    return nejlepsi


_RAZ = CTX.get("razitka")
if _RAZ and _RAZ.get("dily"):
    _t_raz = time.time()
    _geom = {}
    try:
        for _pid, _g in _RAZ["glb"].items():
            _geom[_pid] = _nacti_razitkovy_dil(_g["cesta"])
        _mat_logo = material_pro({"rgb": _hex_lin_barva(_RAZ["logo"]["hex"]), "a": 1.0, "met": float(_RAZ["logo"]["met"]),
                                  "rough": float(_RAZ["logo"]["rough"]), "coat": 0.0, "coat_rough": 0.03})
        for _i, _d in enumerate(_RAZ["dily"], 1):
            _v0, _t0 = _geom.get(_d["part_id"], (None, None))
            if _v0 is None:
                warn("razitko %s: katalogovy GLB bez geometrie, preskoceno" % _d["part_id"])
                continue
            _R = _rot_z_quat(_d["quaternion"])
            _S = np.array(_d["scale"], dtype=np.float64)
            _V = (_v0 * _S) @ _R.T + np.array(_d["position"], dtype=np.float64)
            if _d["part_id"] == "vypln_placka":
                _mat = material_pro({"rgb": tuple(_d.get("base_color") or (0.6, 0.6, 0.6)), "a": 1.0,
                                     "met": float(_d.get("metalness", 0.6)), "rough": float(_d.get("roughness", 0.4)),
                                     "coat": 0.0, "coat_rough": 0.03})
            else:
                _mat = _mat_logo
            _ob = pridej_dil("r%d" % _i, _V, _t0, role="razitko", typ="razitko", rodina="razitko")
            PRIDANO[0] -= 1                                  # razitka se hlasi zvlast (stats.razitka), ne jako doplnene dily
            SLOTY[_ob.name] = [_mat]
            _stred = (_V.min(axis=0) + _V.max(axis=0)) / 2.0
            _pv = _pivot_pod_razitkem(_stred)
            if os.environ.get("V3D_DEBUG"):
                print("LADENI razitko %s stred=%s stena=%s -> pivot %s" % (_d["part_id"], [round(float(x)) for x in _stred], _d.get("stena"), _pv))
            if _pv is not None:
                for _p in PIVOTS:
                    if _p["id"] == _pv:
                        _p["objects"].append(_ob.name)
                POHYBLIVE[_ob.name] = _pv
                RAZITKA_POHYBLIVA[0] += 1
            RAZITKA_N[0] += 1
    except Exception as _e:  # noqa: BLE001 - razitka nesmi shodit model nabidky; chyba jde do varovani
        warn("razitka do modelu nebyla pridana celá (%s: %s)" % (type(_e).__name__, str(_e)[:200]))
    print("RAZITKA: %d vlozeno (%d v pohyblivych skupinach) za %.1fs" % (RAZITKA_N[0], RAZITKA_POHYBLIVA[0], time.time() - _t_raz))

# ===================================================================== multiboxy (Robert 2026-10-07: pricky do Multiboxu v online nabidce)
# Seznam boxu pro vyber pricek v nabidce. Kazdy mesh pod kontejnerem Multibox_Arc je jeden Multibox (Vandr export: delka 395,5 | 288, sirka 186 | 91 | 92, vyska 81 mm).
# Do spec jde POLOHA (svetovy AABB zavreneho stavu, glTF mm), strana konce s vykrojem/lemem (e) a pivot, kdyz box jede s vysuvem; ZADNA jmena komponent.
# e = +1: konec s vykrojem je na MIN strane delky boxu (osa podle rozmeru AABB: delsi vodorovny rozmer), e = -1: na MAX strane (tvar boxu: viz docs/KONTRAKT_NABIDKA_PRICKY.md).
# v5 (Robert 2026-10-07: "pricky i v suplíku, jen ocelove s modrym celem"): do stejneho seznamu patri i PODNOSY ocelovych suplíku (komponenty Suplikocel* / 2suplikyocel*, mesh pod "Default"), sk = 4;
# u nich e = +1: CELO (konec s malou mezerou dutiny od dna, 0,4-0,5 mm; vzadu je lem 18-21 mm) je na MIN strane KRATSI vodorovne osy (hloubky), e = -1: na MAX strane.
MBX = []
# delky po tridach (Robert 2026-10-07: "300" = 288 mm, "400" = 395,5 mm, "500" = zatim nepouzivame; pocet slotu pro pricky 4 / 6 / 8), sirka 186 | 91 | 92, vyska 81 mm
_MBX_DELKY_TR, _MBX_SIRKY, _MBX_VYSKA, _MBX_TOL = ((270.0, 310.0), (380.0, 410.0), (480.0, 520.0)), (186.0, 91.0, 92.0), 81.0, 1.5


def _mbx_zaokr(c):
    return round(float(c), 1) + 0.0


def _mbx_box(o):
    """dict polohy boxu nebo None (nezname rozmery / nelze urcit konec s vykrojem -> varovani)."""
    V = gltf_verts(o)
    mn, mx = V.min(axis=0), V.max(axis=0)
    sz = mx - mn
    a = 0 if sz[0] >= sz[2] else 2                       # osa delky (X nebo Z)
    L, W, H = float(sz[a]), float(sz[2 - a]), float(sz[1])
    if abs(H - _MBX_VYSKA) > _MBX_TOL or not any(lo <= L <= hi for lo, hi in _MBX_DELKY_TR) or not any(abs(W - s_) <= _MBX_TOL for s_ in _MBX_SIRKY):
        warn("multibox: nezname rozmery %.1f x %.1f x %.1f - preskoceno (pricky se u nej nenabizi)" % (L, W, H))
        return None
    ust = V[:, a]
    dole = V[:, 1] < mn[1] + 10.0
    spodek_min = bool(np.any((ust < mn[a] + 20.0) & dole))      # u konce s vykrojem dno chybi (spodek je vykrojeny do ~33 mm)
    spodek_max = bool(np.any((ust > mx[a] - 20.0) & dole))
    if spodek_min == spodek_max:
        warn("multibox %.0f x %.0f: nelze urcit konec s vykrojem - preskoceno" % (L, W))
        return None
    return {"min": [_mbx_zaokr(c) for c in mn], "max": [_mbx_zaokr(c) for c in mx], "e": 1 if not spodek_min else -1}


def _mbx_skupina(o, cesta):
    """(klic skupiny, druh): druh 1 = police s multiboxy, 2 = vysuv (suplik) s multiboxy, 3 = samostatne boxy (jedna skupina na zdroj). Instance komponenty = nejblizsi predek s "(Clone)"."""
    i = next((k for k, c in enumerate(cesta) if str(c).startswith("Multibox_Arc")), None)
    predek = o.parent
    while predek is not None and "(Clone)" not in predek.name:
        predek = predek.parent
    jmeno = ("/".join(map(str, cesta[:i])) if i else "") if predek is None else predek.name
    if "PoliceMultibox" in jmeno:
        return (predek.name if predek is not None else jmeno), 1
    if "VysuvMultibox" in jmeno:
        return (predek.name if predek is not None else jmeno), 2
    return "samostatne", 3


# podnosy ocelovych suplíku: hloubka (zepredu dozadu) 332 | 384, sirka 443 | 695 | 950, vyska 101 | 137 | 210 mm (rozmery AABB, shodne s api/nabidka_pricky.py SUP_*); kombinace hloubka x vyska s dilem
_SUP_HLOUBKY, _SUP_SIRKY, _SUP_VYSKY, _SUP_TOL = (332.0, 384.0), (443.0, 695.0, 950.0), (101.0, 137.0, 210.0), 2.5
_SUP_KOMB = {(332, 137), (332, 210), (384, 101), (384, 137), (384, 210)}


def _sup_box(o):
    """dict polohy podnosu suplíku nebo None (nezname rozmery / nelze urcit celo -> varovani). e: viz hlavicka (osa b = kratsi vodorovna osa = hloubka)."""
    V = gltf_verts(o)
    mn, mx = V.min(axis=0), V.max(axis=0)
    sz = mx - mn
    if max(float(sz[0]), float(sz[2])) < 300.0 or float(sz[1]) < 90.0:         # drobne dily pod "Default" (kovani, vodici listy) nejsou podnosy - bez varovani
        return None
    b = 0 if sz[0] < sz[2] else 2                          # osa hloubky (kratsi vodorovna)
    D, Wd, H = float(sz[b]), float(sz[2 - b]), float(sz[1])
    hl = next((h for h in _SUP_HLOUBKY if abs(D - h) <= _SUP_TOL), None)
    sr = next((s_ for s_ in _SUP_SIRKY if abs(Wd - s_) <= _SUP_TOL), None)
    vy = next((v for v in _SUP_VYSKY if abs(H - v) <= _SUP_TOL), None)
    if hl is None or sr is None or vy is None or (int(hl), int(vy)) not in _SUP_KOMB:
        warn("suplik: nezname rozmery %.1f x %.1f x %.1f - preskoceno (pricky se u nej nenabizeji)" % (Wd, D, H))
        return None
    dno = V[:, 1] < mn[1] + 3.0                           # vrcholy u dna (vnejsi dno + podlaha dutiny)
    g_min = float(V[dno][:, b].min() - mn[b])             # mezera dna od MIN konce hloubky
    g_max = float(mx[b] - V[dno][:, b].max())             # mezera dna od MAX konce (zadni lem je siroky, celo ma mezeru ~0)
    if abs(g_min - g_max) < 5.0:
        warn("suplik %.0f x %.0f: nelze urcit celo - preskoceno" % (Wd, D))
        return None
    return {"min": [_mbx_zaokr(c) for c in mn], "max": [_mbx_zaokr(c) for c in mx], "e": 1 if g_min < g_max else -1}


def _sup_skupina(o):
    """(klic skupiny, 4): skupina = instance komponenty suplíku (nejblizsi predek s "(Clone)"; jmeno objektu je v Blenderu unikatni)."""
    predek = o.parent
    while predek is not None and "(Clone)" not in predek.name:
        predek = predek.parent
    return (predek.name if predek is not None else "suplik"), 4


for _o in PRODUKT:
    _inf = INFO.get(_o.name)
    if not _inf:
        continue
    if any(str(_c).startswith("Multibox_Arc") for _c in _inf["cesta"]):
        _b = _mbx_box(_o)
        _skup = (lambda oo=_o, cc=_inf["cesta"]: _mbx_skupina(oo, cc))
    elif _inf["role"] == "default" and any(re.match(r"(Suplikocel|2suplikyocel)", str(_c)) for _c in _inf["cesta"]):
        _b = _sup_box(_o)
        _skup = (lambda oo=_o: _sup_skupina(oo))
    else:
        continue
    if _b is None:
        continue
    _b["p"] = POHYBLIVE.get(_o.name)
    _b["_sk"] = _skup()
    MBX.append(_b)
MBX.sort(key=lambda b: (-round((b["min"][1] + b["max"][1]) / 20.0), b["min"][0], b["min"][2]))        # shora dolu, pak podle polohy (stabilni poradi)
for _i, _b in enumerate(MBX, 1):
    _b["id"] = "b%02d" % _i
    _b["n"] = _i
# cisla skupin: podle prvniho vyskytu v tomto poradi (nejvyssi polica / suplik = 1)
_SKUPINY = {}
for _b in MBX:
    _kl, _dr = _b.pop("_sk")
    _b["s"] = _SKUPINY.setdefault(_kl, len(_SKUPINY) + 1)
    _b["sk"] = _dr
print("MULTIBOXY a PODNOSY SUPLIKU: %d (z toho podnosu suplíku %d; v pohyblivych skupinach %d) ve %d skupinach (police / vysuvy / suplíky)" % (len(MBX), sum(1 for b in MBX if b["sk"] == 4), sum(1 for b in MBX if b["p"]), len(_SKUPINY)))

bpy.context.view_layer.update()
# Robert 2026-10-01: "vnejsi koty sestav musi byt po steny profilu, nikoli
# podle trcicich drobnych komponentu" - obalka pro koty L1 jen z PROFILU
# (cesta uzlu obsahuje prurez delka, napr. 45x45x369 / SL40x40x1200), vrcholy
# se berou pred slucovanim (pak uz jmena nejsou). spec.box zustava cely model.
_PROFIL_RE = re.compile(r"(?<![0-9])\d{2}x\d{2}x\d{2,4}(?![0-9])")
PROFIL_V = [gltf_verts(o) for o in PRODUKT if o.name in INFO and _PROFIL_RE.search(" ".join(map(str, INFO[o.name]["cesta"])) if isinstance(INFO[o.name]["cesta"], (list, tuple)) else str(INFO[o.name]["cesta"]))]
POCET_PROFILU = len(PROFIL_V)
_t_sluc = time.time()
staticke = [o for o in PRODUKT if o.name not in POHYBLIVE]
NOVE = []   # nove mesh objekty (staticky + jeden na pivot)
me_stat, ob_stat = None, None
if staticke:
    me_stat = _sluc(staticke, "v3dstat")
    ob_stat = bpy.data.objects.new("v3dstat", me_stat)
    sc.collection.objects.link(ob_stat)
    NOVE.append(ob_stat)

PIVOT_OBJ = {}
for pv in PIVOTS:
    origin_bl = from_gltf(pv["origin"])
    e = bpy.data.objects.new("v3dpiv_" + pv["id"], None)
    e.empty_display_type = "PLAIN_AXES"
    sc.collection.objects.link(e)
    if pv["parent"]:
        rodic = PIVOT_OBJ[pv["parent"]]
        e.parent = rodic
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.location = origin_bl - from_gltf(next(p["origin"] for p in PIVOTS if p["id"] == pv["parent"]))
    else:
        e.location = origin_bl
    PIVOT_OBJ[pv["id"]] = e
    objs = [o for o in PRODUKT if o.name in set(pv["objects"])]
    if objs:
        me_p = _sluc(objs, "v3dmov_" + pv["id"], posun=tuple(origin_bl), remap=omez_materialy_pivotu(objs))
        ob_p = bpy.data.objects.new("v3dmov_" + pv["id"], me_p)
        sc.collection.objects.link(ob_p)
        ob_p.parent = e
        ob_p.matrix_parent_inverse = Matrix.Identity(4)
        NOVE.append(ob_p)

T_SLUCOVANI = time.time() - _t_sluc
# puvodni objekty, meshe a materialy pryc (nic z nich se nesmi exportovat).
# batch_remove - remove() po jednom prepocitava vazby celeho souboru (O(n^2)).
_t_uklid = time.time()
_ponechat = set(o.name for o in NOVE) | set(e.name for e in PIVOT_OBJ.values())
_nove_meshe = set(o.data.name for o in NOVE)
_nove_mat = set(m.name for m in MATERIALY.values())
_pryc = [o for o in bpy.data.objects if o.name not in _ponechat]
_pryc += [me for me in bpy.data.meshes if me.name not in _nove_meshe]
_pryc += [m for m in bpy.data.materials if m.name not in _nove_mat]
_pryc += list(bpy.data.collections) + list(bpy.data.images)
bpy.data.batch_remove(_pryc)
bpy.context.view_layer.update()
T_UKLID = time.time() - _t_uklid

# ===================================================================== (5)
vsechny_v = []
for o in NOVE:
    vsechny_v.append(gltf_verts(o))
V = np.concatenate(vsechny_v)
BOX_MIN = V.min(axis=0)
BOX_MAX = V.max(axis=0)
f = np.array(FRONT, dtype=np.float64)
u = np.array((0.0, 1.0, 0.0))
r = np.cross(-f, u)            # vpravo z pohledu zakaznika (kamera na +front)
if PROFIL_V:
    _VK = np.concatenate(PROFIL_V)          # koty po steny profilu
else:
    _VK = V
    WARNINGS.append("koty: v modelu nenalezen zadny profil (prurez v nazvu), koty z cele obalky")
pf, pu, pr = _VK @ f, _VK @ u, _VK @ r
F0, F1, U0, U1, R0, R1 = pf.min(), pf.max(), pu.min(), pu.max(), pr.min(), pr.max()
SIRKA, HLOUBKA, VYSKA = R1 - R0, F1 - F0, U1 - U0


def _r1(c):
    return round(float(c), 1) + 0.0   # + 0.0 = bez "-0.0"


def _bod(rr, uu, ff):
    p = r * rr + u * uu + f * ff
    return [_r1(c) for c in p]


def _t(mm):
    s = "%d" % int(round(mm))
    return re.sub(r"(\d)(?=(\d{3})+$)", r"\1 ", s)


_ods = float(max(60.0, round(0.06 * max(SIRKA, HLOUBKA, VYSKA) / 10.0) * 10.0))
DIMS = [
    # sirka: horni hrana cela, odsazeni nahoru
    {"a": _bod(R0, U1, F1), "b": _bod(R1, U1, F1), "o": [_r1(c) for c in u * _ods], "t": _t(SIRKA), "l": 1, "p": None},
    # vyska: prava hrana cela, odsazeni doprava
    {"a": _bod(R1, U0, F1), "b": _bod(R1, U1, F1), "o": [_r1(c) for c in r * _ods], "t": _t(VYSKA), "l": 1, "p": None},
    # hloubka: prava horni hrana, odsazeni nahoru
    {"a": _bod(R1, U1, F0), "b": _bod(R1, U1, F1), "o": [_r1(c) for c in u * _ods], "t": _t(HLOUBKA), "l": 1, "p": None},
] + DIMS_L2

V3D = {
    "v": 1, "u": "mm", "up": [0, 1, 0],
    "front": [round(FRONT[0], 6) + 0.0, 0, round(FRONT[2], 6) + 0.0],
    "box": {"min": [_r1(c) for c in BOX_MIN], "max": [_r1(c) for c in BOX_MAX]},
    "look": "vd", "dims": DIMS, "motions": MOTIONS,
}
if MBX:
    V3D["mbx"] = [{"id": b["id"], "min": b["min"], "max": b["max"], "e": b["e"], "p": b["p"], "n": b["n"], "s": b["s"], "sk": b["sk"]} for b in MBX]

# ===================================================================== (6)
for i, o in enumerate(NOVE, 1):   # staticky uzel (je-li) = n1
    o.name = "n%d" % i
    o.data.name = "n%d" % i
for pid, e in PIVOT_OBJ.items():
    e.name = pid
for i, m in enumerate(sorted(MATERIALY.values(), key=lambda m: int(m.name[6:])), 1):
    m.name = "m%02d" % i
for idb in list(bpy.data.objects) + list(bpy.data.meshes) + list(bpy.data.materials) + [sc, bpy.context.scene.world] \
        + list(bpy.data.scenes):
    if idb is None:
        continue
    for k in list(idb.keys()):
        del idb[k]
sc.name = "s"

_tmp_glb = CLEAN_GLB_OUT + ".tmp.glb"
_t_exp = time.time()
bpy.ops.export_scene.gltf(
    filepath=_tmp_glb, export_format="GLB", export_extras=False, export_yup=True,
    export_texcoords=False, export_normals=not _opt.get("bez-normal"), export_tangents=False, export_materials="EXPORT",
    export_vertex_color="NONE", export_attributes=False, export_cameras=False, export_lights=False,
    export_animations=False, export_skins=False, export_morph=False, use_selection=False,
    export_apply=False, export_copyright="", export_image_format="NONE", export_original_specular=False,
)
T_EXPORT = time.time() - _t_exp


def _read_glb(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"glTF":
        raise SystemExit("Export neni GLB.")
    off, js, binc = 12, None, b""
    while off < len(data):
        ln, typ = struct.unpack("<I4s", data[off:off + 8])
        chunk = data[off + 8:off + 8 + ln]
        if typ == b"JSON":
            js = json.loads(chunk.decode("utf-8"))
        elif typ == b"BIN\x00":
            binc = chunk
        off += 8 + ln
    return js, binc


def _write_glb(path, js, binc):
    jb = json.dumps(js, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    bb = binc + b"\x00" * ((4 - len(binc) % 4) % 4)
    total = 12 + 8 + len(jb) + (8 + len(bb) if bb else 0)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<4sII", b"glTF", 2, total))
        fh.write(struct.pack("<I4s", len(jb), b"JSON"))
        fh.write(jb)
        if bb:
            fh.write(struct.pack("<I4s", len(bb), b"BIN\x00"))
            fh.write(bb)


def _uzlove_matice(js):
    def lokal(n):
        if "matrix" in n:
            return np.array(n["matrix"], dtype=np.float64).reshape(4, 4).T
        t = np.array(n.get("translation", [0, 0, 0]), dtype=np.float64)
        q = n.get("rotation", [0, 0, 0, 1])
        s = np.array(n.get("scale", [1, 1, 1]), dtype=np.float64)
        x, y, z, w = q
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4)
        M[:3, :3] = R * s
        M[:3, 3] = t
        return M
    world = {}

    def jdi(i, P):
        W = P @ lokal(js["nodes"][i])
        world[i] = W
        for c in js["nodes"][i].get("children", []):
            jdi(c, W)
    for root in js["scenes"][js.get("scene", 0)]["nodes"]:
        jdi(root, np.eye(4))
    return world


js, binc = _read_glb(_tmp_glb)
os.remove(_tmp_glb)
# vycisteni JSON (pojistka - sanitizer na serveru dela totez znovu)
js["asset"] = {"version": "2.0"}
for kl in ("extras", "extensions"):
    js.pop(kl, None)
for sekce in ("nodes", "meshes", "materials", "scenes", "accessors", "bufferViews", "buffers", "images",
              "textures", "samplers", "cameras", "skins", "animations"):
    for it in js.get(sekce, []):
        it.pop("extras", None)
        if sekce in ("nodes", "meshes", "materials"):
            if not POVOLENE_JMENO_RE.match(it.get("name", "")):
                it.pop("name", None)
        else:
            it.pop("name", None)
if not _opt.get("no-embed-v3d"):
    js["scenes"][js.get("scene", 0)]["extras"] = {"v3d": V3D}

# kontrola jednotek: AABB z exportu musi sedet s AABB pred exportem (mm)
world = _uzlove_matice(js)
emn = np.full(3, 1e18)
emx = np.full(3, -1e18)
DRAW_CALLS = 0
TROJUHELNIKY = 0
for i, n in enumerate(js["nodes"]):
    if "mesh" not in n:
        continue
    for p in js["meshes"][n["mesh"]]["primitives"]:
        DRAW_CALLS += 1
        acc = js["accessors"][p["attributes"]["POSITION"]]
        if "indices" in p:
            TROJUHELNIKY += js["accessors"][p["indices"]]["count"] // 3
        mn, mx = np.array(acc["min"]), np.array(acc["max"])
        for c in range(8):
            pt = np.array([mx[0] if c & 1 else mn[0], mx[1] if c & 2 else mn[1], mx[2] if c & 4 else mn[2], 1.0])
            w = world[i] @ pt
            emn = np.minimum(emn, w[:3])
            emx = np.maximum(emx, w[:3])
_odchylka = float(max(np.abs(emn - BOX_MIN).max(), np.abs(emx - BOX_MAX).max()))
if _odchylka > 1.0:
    raise SystemExit("Kontrola jednotek selhala: AABB po exportu se lisi o %.2f mm (%s..%s vs %s..%s)"
                     % (_odchylka, emn, emx, BOX_MIN, BOX_MAX))

# kontrola zakazanych retezcu (klice i hodnoty, krome binarni casti)
_nalezy = []


def _prover(x, cesta="$"):
    if isinstance(x, dict):
        for k, v in x.items():
            if ZAKAZANE_RE.search(k):
                _nalezy.append(cesta + "." + k)
            _prover(v, cesta + "." + k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _prover(v, "%s[%d]" % (cesta, i))
    elif isinstance(x, str):
        if ZAKAZANE_RE.search(x):
            _nalezy.append("%s=%r" % (cesta, x))


# motions[].sub (vycet klt|multibox|eurobox|kufrik, jen u boxu) je JEDINY retezec, ktery smi nest
# zakazana slova (KLT, Multibox, Eurobox, Kufrik) - overuje se vyctem a jen na ceste
# scenes[i].extras.v3d.motions[j].sub; pro ZAKAZANE_RE se z kopie JSON vyjme, ostatni beze zmeny
_js_kontrola = json.loads(json.dumps(js))
for _sc in _js_kontrola.get("scenes", []):
    for _mo in ((_sc.get("extras") or {}).get("v3d") or {}).get("motions", []):
        if "sub" in _mo:
            if not (_mo.get("k") == "box" and _mo["sub"] in SUBS_POHYBU):
                _nalezy.append("motions[].sub neplatny %r" % (_mo["sub"],))
            del _mo["sub"]
_prover(_js_kontrola)
for sekce in ("nodes", "meshes", "materials"):
    for it in js.get(sekce, []):
        if not POVOLENE_JMENO_RE.match(it.get("name", "")):
            _nalezy.append("%s jmeno %r" % (sekce, it.get("name")))
for i, n in enumerate(js.get("nodes", [])):
    if set(n.get("extras", {}).keys()) - {"g"}:
        _nalezy.append("nodes[%d].extras" % i)
if _nalezy:
    raise SystemExit("OCHRANA: vystupni GLB obsahuje zakazane retezce: %s" % "; ".join(_nalezy[:10]))

_write_glb(CLEAN_GLB_OUT, js, binc)

# ===================================================================== (7)
STATIC_DC = len(me_stat.materials) if me_stat is not None else 0
geom_out = {
    # zpetna kompatibilita s api/vandr_scene_offers.py (rozmer_mm = overall_size,
    # osy jako ve stare verzi: Blender X, Y, Z = glTF X, -Z, Y)
    "overall_min": [round(float(BOX_MIN[0]), 1), round(float(-BOX_MAX[2]), 1), round(float(BOX_MIN[1]), 1)],
    "overall_max": [round(float(BOX_MAX[0]), 1), round(float(-BOX_MIN[2]), 1), round(float(BOX_MAX[1]), 1)],
    "overall_size": [round(float(BOX_MAX[0] - BOX_MIN[0]), 1), round(float(BOX_MAX[2] - BOX_MIN[2]), 1),
                     round(float(BOX_MAX[1] - BOX_MIN[1]), 1)],
    "profily": PROFILY,
    # nove: [sirka, hloubka, vyska] v ramu cela (sirka zleva doprava z pohledu
    # zakaznika, hloubka ve smeru front, vyska nahoru)
    "overall_size_mm": [round(float(SIRKA), 1), round(float(HLOUBKA), 1), round(float(VYSKA), 1)],
    "v3d": V3D,
    "warnings": WARNINGS,
    "stats": {
        "meshes_before": MESHES_BEFORE, "meshes_after": len(NOVE),
        "materials_before": MATERIALS_BEFORE, "materials_after": len(MATERIALY),
        "draw_calls": DRAW_CALLS, "draw_calls_static": STATIC_DC, "draw_calls_moving": DRAW_CALLS - STATIC_DC,
        "triangles": TROJUHELNIKY, "nodes": len(js.get("nodes", [])), "pivots": len(PIVOTS),
        "motions": len(MOTIONS), "pohyby_druhy": POHYBY_DRUHY, "pohyby_boxy_sub": POHYBY_BOXY_SUB,
        "pohyby_modul": POHYBY_INFO,
        "rozriznute_dily": ROZRIZNUTO[0], "pridane_dily": PRIDANO[0], "razitka": RAZITKA_N[0], "razitka_pohyblivych": RAZITKA_POHYBLIVA[0], "multiboxy": len(MBX), "omezene_materialy": OMEZENE_MATERIALY,
        "vyrazeno": VYRAZENO, "front_zdroj": FRONT_ZDROJ,
        "front_komponent": FRONT_SMERY, "zrcadlene_dily": ZRCADLENE[0],
        "komponenty": len(KOMPONENTY), "glb_bytes": os.path.getsize(CLEAN_GLB_OUT),
        "kontrola_jednotek_mm": round(_odchylka, 3), "prevod_z_metru": PREVOD_Z_METRU,
        "sekundy": round(time.time() - T0, 2), "sekundy_import": round(T_IMPORT, 2),
        "sekundy_export": round(T_EXPORT, 2), "sekundy_vyrazeni": round(T_VYRAZENI, 2),
        "sekundy_pohyby": round(T_POHYBY, 2), "sekundy_materialy": round(T_MATERIALY, 2),
        "sekundy_slucovani": round(T_SLUCOVANI, 2), "sekundy_uklid": round(T_UKLID, 2),
    },
}
with open(GEOM_JSON_OUT, "w", encoding="utf-8") as fh:
    json.dump(geom_out, fh, ensure_ascii=False)
print("GEOM_OK profilu=%d obal=%d dc=%d (staticke %d) tri=%d %.1fs"
      % (len(PROFILY), VYRAZENO["obal"], DRAW_CALLS, STATIC_DC, TROJUHELNIKY, time.time() - T0))
print("CLEAN_GLB_OK", CLEAN_GLB_OUT)
