"""blender_render_turntable.py - vyrenderuje OTOCNY NAHLED produktove
sestavy (prstence + stills) v Blenderu podle ulohy ze
scripts/2026-09-09_turntable_job.py (bot8, Robert 2026-09-09).

Robert 2026-09-09: "tento blender na VPS budu ja obsluhovat z hlediska
nastaveni 3D sceny, zapojim novy pc s GPU do site a ty budes delat rendery
na nase produktove sestavy podle nastaveni VPS blenderu a na vzdalenem GPU,
a ty rendery si rovnou ukladat k tem produktovym sestavam."

Nahrazuje RENDEROVACI cast dosavadniho otocneho nahledu (ktera bezela ve
WebGL v prohlizeci admina - webapp/scene.html paRenderTurntable). Ulozne
schema, nazvy poli, pocty snimku a e-shopovy widget zustavaji NEZMENENE -
meni se jen to, co snimky vyrobi. Diky tomu funguje stary i novy zdroj
vedle sebe a da se kdykoli vratit.

SPUSTENI:
    blender -b -noaudio [sablona.blend] -P blender_render_turntable.py -- job.json

SABLONA (Robertuv .blend z VPS Blenderu) - VOLITELNA, kdyz se neuvede,
pouziji se vestavene vychozi hodnoty odpovidajici dosavadnimu prohlizecovemu
renderu. Ze sablony se PREBIRA:
  * World (HDRI/pozadi/sila) - cely, jak je ulozeny
  * svetla (vsechny objekty typu LIGHT)
  * render engine, vzorky, denoise, color management (Filmic/AgX/...)
  * objekt jmenem TT_FLOOR (podlaha/shadow catcher) - kdyz existuje,
    NEVYRABI se vlastni; posune se jen pod sestavu
  * materialy jmenem TT_ALU / TT_ZINC / TT_BLACK / TT_GUMA / TT_PLAST -
    kdyz existuji, dily je dostanou misto proceduralne postaveneho
    Principled BSDF (Robert si je muze naladit vizualne v GUI).
    Vedle TT_* se hlinik a plast berou i pod VLASTNIMI jmeny z X30-1
    ("Sandblasted aluminium", "Scratched grey plastic") - v Robertove
    souboru se nic neprejmenovava. Texturovane materialy se pritom
    kopiruji na BOX projekci, protoze nase GLB nemaji UV (viz
    _na_box_projekci nize).
  * material jmenem LOGO_SABLONOVY_MATERIAL (`_material_for()` nize) pro
    razitkove logo - 2026-09-11 (Robert: "aplikuj [UDIN] doplnek na scenu
    X30-1 a pouzij material na 3D loga"), stejny princip jako TT_* vyse,
    jen vazany na `part_id`, ne na barvu/vrstvu. Kdyz sablona material
    tohoto jmena nema, spada se na vypocet z cisel (metalness/roughness/
    transmission/ior) beze zmeny.
Ze sablony se ZAHAZUJE geometrie (mesh objekty) a kamery - ty si stavi
tenhle skript sam, jinak by v produktovem renderu zustala Robertova
zkusebni scena.

CO SE NEPREBIRA A PROC: rozliseni a pomer stran. Ty jsou KONTRAKT
otocneho nahledu (api/turntable.py TIERS/STILL_VIEWS, widget je ctvercovy)
- kdyby je sablona prebila, commit davky by ji odmitl jako nekompletni.

KAMEROVY KONTRAKT: presny port webapp/scene.html ttComputeDistance /
ttCameraPosition / ttFitStill (viz tam komentare k odvozeni vzorcu).
Snimky proto sedi na stejne pozice jako dosavadni davky - prechod
placeholder -> widget zustava neviditelny a "faze C" (skok z nahledu do
sceny) dal funguje.

PASTI, KTERE UZ STALY CAS (nemazat):
 1. cam.clip_end - vychozich 100 jednotek je pro scenu v MILIMETRECH
    (regal ~2000) daleko malo, model by byl za clip rovinou. Viz
    blender_render_scene.py, stejna past.
 2. flatShading - GLB profily maji prumerovane vertex normaly pres cele
    hrany prurezu; bez shade_flat by ostre 90 stupnove hrany vypadaly
    zaoblene (viz materialForLayer v hdri-panels-ui.js, stejny duvod).
 3. Souradnice - prohlizec je Y-nahoru, Blender Z-nahoru; glTF importer
    prevadi (x, y, z) -> (x, -z, y). Transformace dilu ze sestavy je
    zapsana v souradnicich PROHLIZECE, musi se tedy konjugovat:
    M_blender = C @ M_three @ C^-1 (viz _three_to_blender_matrix).
"""
import json
import math
import os
import re
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

# ---------------------------------------------------------------- uloha
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    raise SystemExit("Chybi cesta k job JSON (blender ... -P skript.py -- job.json)")
with open(argv[0], "r", encoding="utf-8") as fh:
    JOB = json.load(fh)

OUT_DIR = JOB["out_dir"]
os.makedirs(OUT_DIR, exist_ok=True)

# Bez sablony se MUSI zahodit i Blenderova startovni scena (kostka, kamera,
# slabe bodove svetlo, tmave sede pozadi) - jinak by se tvarila jako
# "sablona, ktera uz world i svetlo ma" a fallbacky nize by se nespustily
# (render pak vysel temer cerny). Stejne jako blender_render_scene.py.
HAS_TEMPLATE = bool(bpy.data.filepath)
if not HAS_TEMPLATE:
    bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
print("SABLONA soubor: %s" % (bpy.data.filepath or "(zadna - vestavene vychozi hodnoty)"))

# ⭐ BAREVNY PREVOD (view_transform) - JEDNA HODNOTA, JEDNO MISTO (Robert
# 2026-09-11, pres bot3): "gradientu musime odstranit hnedy nadech".
#
# PRICINA: sablona ma nastaveny AgX, a AgX je znamy tim, ze u neutralnich/
# skoro-bilych tonu zavadi teply (hnedavy) nadech - to neni chyba v
# Blenderu, je to charakteristika jeho tonemapovaci krivky. Nejde o vadu
# pozadi (JOB["bg_color"]/JOB["bg_color_bottom"] jsou overene ciste
# neutralni, #f2f3f5/#000000) ani o spatne HDRI (v sablone zadny
# brown_photostudio neni) - overeno primym ctenim souboru (bot8, 2026-09-11).
#
# STEJNY MECHANISMUS, JINY SMER: bot4 drive zmeril, ze pod AgX cte MDF
# `#5c626a` domodra - tedy AgX prokazatelne posouva odstiny v tomhle
# pipeline, nejen teoreticky. Az Robert vybere finalni prevod, zkontroluj
# u nej i MDF - jedna zmena muze vyresit oboji, nebo jedno zhorsit druhe.
#
# ROBERTOVO ROZHODNUTI (2026-09-11): prevod se vynucuje TADY V KODU, ne v
# .blend souboru - v Blenderu pri praci na sablone tedy uvidi jiny odstin,
# nez jaky vyjde z renderu; tenhle rozdil VZAL NA VEDOMI a prijal.
#
# VRACENO ZPET PODRUHE (Robert, 2026-09-26, do par minut od zavedeni):
# Standard opravil kov, ale pod stejnym prevodem se KLT/Multibox boxy
# vyplavi/prepali (overeno primo srovnavacim renderem stejne sestavy -
# Robert: "co to je za hnus"). Globalni prepinac AgX<->Standard neni
# spravne reseni, protoze pri kazde volbe pokazi neco jineho (barvy vs.
# kov vs. lesky plasty). Zpet na sablonovy vychozi stav (AgX, jak ji ma
# Robert v X30-02) - dokud se nenajde presnejsi oprava (napr. per-
# material, expozice, nebo jiny tonemap), sahat do tohohle prepinace uz
# NE bez noveho vyslovneho zadani.
print("BAREVNY PREVOD: sablonovy (%s) - zadne vynuceni"
      % sc.view_settings.view_transform)

# Y-nahoru (three.js) -> Z-nahoru (Blender): rotace +90 kolem X.
C = Matrix.Rotation(math.radians(90.0), 4, "X")
C_INV = C.inverted()


def _three_to_blender_matrix(pos, quat, scale):
    """Transformace dilu zapsana v souradnicich prohlizece -> ekvivalentni
    transformace v Blenderu. glTF importer uz na geometrii aplikoval C,
    takze stejnou transformaci musime aplikovat "skrz" nej: konjugaci."""
    q = Quaternion((float(quat[3]), float(quat[0]), float(quat[1]), float(quat[2])))  # w, x, y, z
    m = Matrix.Translation(Vector((float(pos[0]), float(pos[1]), float(pos[2])))) @ q.to_matrix().to_4x4()
    m = m @ Matrix.Diagonal(Vector((float(scale[0]), float(scale[1]), float(scale[2]), 1.0)))
    return C @ m @ C_INV


# ------------------------------------------------------------- sablona
# Geometrie a kamery ze sablony pryc (Robertova zkusebni scena do
# produktoveho renderu nepatri); World, svetla, TT_FLOOR a TT_* materialy
# zustavaji.
template_floor = None
for o in list(sc.objects):
    if o.name == "TT_FLOOR":
        template_floor = o
        continue
    if o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT", "CAMERA", "EMPTY"}:
        bpy.data.objects.remove(o, do_unlink=True)

# Robert 2026-09-10: *"pokud zvladneme pouzivat ten material sandblasted
# aluminium, nepotrebujeme to nase piskovani"* a *"idealne i na plasty vzit
# ten co je na boxech v X30"* -> jmenovite `Scratched grey plastic`.
#
# Sablona je Robertuv soubor a NIC se v ni neprejmenovava (*"nic tam
# nemenit"*), proto se material hleda i pod svym VLASTNIM jmenem, ne jen pod
# dohodnutym TT_*. TT_* ma prednost - kdyby si Robert nekdy vlastni TT_ALU
# vytvoril, prebije puvodni material bez zasahu do kodu.
TEMPLATE_MAT_NAMES = {
    "alu": ("TT_ALU", "Sandblasted aluminium"),
    "zinc": ("TT_ZINC",),
    "black": ("TT_BLACK",),
    "guma": ("TT_GUMA",),
    "plast_svetly": ("TT_PLAST", "Scratched grey plastic", "Light grey metallic plastic"),
}

# Nase dily NEMAJI UV souradnice - GLB nese jen POSITION a NORMAL (overeno
# 2026-09-10 na Object_7.glb i product_2895.glb). Materialy ze sablony ale
# texturuji pres Texture Coordinate -> UV, takze bez zasahu by kazda plocha
# vzala jediny texel a vysla by plocha barva bez kresby. Resi to projekce
# BOX nad OBJEKTOVYMI souradnicemi - presne to, co uz roky dela nas vlastni
# AluPBR (blender_render_scene.py, "funguje i BEZ UV souradnic").
#
# Material se KOPIRUJE, nikdy nemeni na miste - sablona je Robertuv soubor
# (pravidlo 2 v PRODUKTOVE_RENDERY.md) a tentyz material muze byt zaroven
# pouzity necim, co UV ma.
TEXTURE_TILE_MM = float(JOB.get("texture_tile_mm") or 40.0)
# REALNY HLINIK (opt-in, VYCHOZI VYPNUTO; Robert 2026-09-26 "hlinik reanejsi,
# zkusme to zapect"). Pruzkum ukazal, ze "Sandblasted aluminium" z Robertovy
# sablony je cisty obrazkovy material (barva/kovovost/drsnost/normala/relief),
# ktery je uz hotovy - zapekani by nic nepridalo. Skutecny rozdil proti jeho
# Blenderu je MERITKO: sablona je v metrech (zrno 0.5 mm na opakovani, relief
# 0.01 m), nase scena je v mm. Katalogove profily maji dnes zrno 40 mm na
# opakovani (box-projekce), Vandr profily jejich vlastni UV (delka-zavisla),
# relief je v mm scene ~1000x slabsi. Volby jen pro A/B testy jednoho snimku:
#   alu_realny    - hlinik VSUDE (katalog i Vandr) = kopie originalu ze
#                   sablony s box-projekci nad Object souradnicemi
#   alu_tile_mm   - delka strany opakovani textury v mm (bez zadani 40 = dnes)
#   alu_disp_mult - nasobek sily reliefu (1000 = prepocet metry -> mm)
ALU_REALNY = bool(JOB.get("alu_realny"))
ALU_TILE_MM = float(JOB.get("alu_tile_mm") or TEXTURE_TILE_MM)
ALU_DISP_MULT = float(JOB.get("alu_disp_mult") or 1.0)
# alu_material (opt-in, VYCHOZI VYPNUTO; Robert 2026-09-26 "zkus jiny nez
# Sandblasted, treba ten PB..."): jmeno jineho hlinikoveho materialu z VD_
# knihovny (job.vd_materialy_blend) misto "Sandblasted aluminium", pro
# katalogove profily I Vandr "ALU (Instance)". Jen pro A/B testy jednoho
# snimku, nastavi ho dispatch skript volbami --alu-material/--vd-knihovna.
ALU_MATERIAL = (JOB.get("alu_material") or "").strip()
# klt_material (opt-in, VYCHOZI VYPNUTO; Robert 2026-09-28: "Blue_GloPLA.blend,
# aplikuj na celo supliku") - jmeno materialu z VD_ knihovny (job.vd_materialy_path,
# stejna --vd-knihovna jako u ALU_MATERIAL) misto puvodniho "blue KLT" na
# supliku/KLT boxu (ne na uzke liste v drazce - ta se resi drive, viz "past c. 1").
KLT_MATERIAL = (JOB.get("klt_material") or "").strip()
# vd_puvodni_nevyplnene (Robert 2026-09-28: "nevyplnene materialy nech se
# nasadi puvodni co si nese objekt sebou") - render podle tabulky prirazeni:
# dil BEZ vyplneneho radku si necha svuj material z modelu, zadna vychozi
# VD_ nahrada podle jmena ani sablonovy hlinik (kdyz radek hliniku prazdny).
VD_PUVODNI_NEVYPLNENE = bool(JOB.get("vd_puvodni_nevyplnene"))
# POZOR (bot4, po opravě nize): navzdory nazvu promenne uz nejde o
# "blue klt" material - viz postmortem u _je_celo_supliku_klt nize,
# skutecny puvodni material cela je "tyrkys".
# Rozliseni "cela supliku" od KLT boxu/kolejnicek/klipsu (Robert 2026-09-28,
# po DVOU chybnych pokusech - viz postmortem nize).
#
# POSTMORTEM (bot4): prvni pokus prekryval kazdy material s "klt" v nazvu -
# zasahl box KLT i celo najednou (presne to, co Robert zakazal). Druhy
# pokus (tenhle komentar puvodne rikal, ze "cela supliku" jsou plocha
# 0mm-tloustky "blue KLT" telesa) byl TAKY spatne: ta plocha jsou ve
# skutecnosti delici/kryci panely UVNITR "blue KLT" rodiny (box/Multibox),
# ne supliky. Rozpoznano az primym rozborem hierarchie uzlu v
# vd_export_ford_transit_l3h3_fwd.glb (dump_drawer_children.py, bot4,
# po Robertove "rozdej mi na ty čela šuplíku různé materiály ať vidím
# jestli vůbec víš co jsou čela šuplíku"): kazdy "Suplikocel*" (= supliku
# "ocel", nazev primo z Unity/vanDrawee zdroje) drawer-komponent ma
# vlastni EMPTY podskupinu doslova pojmenovanou "drawer"/"drawer.NNN" a
# JEJI mesh deti pouzivaji material "tyrkys (Instance).NNN" - NE "blue
# klt" (barva materialu prekvapive vychazi jako svetle modra, ne
# tyrkysova - odtud vizualni zamena). "blue KLT" rodina patri VYHRADNE
# boxum/prihradkam (Multibox), tyrkys je VYHRADNE celo supliku - uz se
# NEPREKRYVaji, netreba delit podle geometrie tloustky jako drive.
# Rozmerovy filtr (>300mm v nejvetsim rozmeru) uvnitr "tyrkys" rodiny
# navic vyloucí drobne tyrkysove rozky/uchyty (35x35x1mm, 15x23x30mm) -
# zbyde cistě hlavni celni panel (443x139x20mm) + jeho ramecek (443x1.3x20mm).
def _je_celo_supliku_klt(o):
    if "tyrkys" not in _mat_nazev_bez_instance(o):
        return False
    # Robert 2026-09-28: celo supliku NESMI sdilet prirazeni s KLT boxem ani
    # Multiboxem - v "Police s Multiboxy" jsou 3 tyrkysove dily > 300 mm
    # (zmereno pres vsech 105 GLB), ktere by bez omezeni na typ dilu
    # prekryv cela chytil taky.
    return _role_dilu(o) == "drawer" or (max(o.dimensions) > 300.0 and _typ_dilu(o) == "suplik")


# Typ dilu = komponenta Unity/vanDrawee exportu (Robert 2026-09-28: "jeden
# materiál je pro boxy KLT i pro Multiboxy - pokud to bude sloučené, nikdy
# to nepůjde reálně rozdělit v renderu"). KOPIE seznamu a pravidla ze
# scripts/_render_prirazeni_lib.py TYPY_DILU/typ_dilu (tenhle skript bezi
# samostatne na GPU workeru, knihovnu importovat nemuze) - pri zmene
# upravit OBA (+ webapp/kontrola.html typDilu). Prvni shoda klicoveho slova
# v retezci jmen od KORENE k dilu; specifictejsi slova pred obecnejsimi.
_TYPY_DILU = [
    ("multibox", "multibox"), ("vysuvklt", "vysuvklt"), ("vysuveurobox", "vysuveurobox"),
    ("kufrik", "kufrik"), ("boxpolice", "boxpolice"), ("suplik", "suplik"), ("drawer", "suplik"),
    ("policedoor", "policedoor"), ("doorfloor", "doorfloor"), ("frontfloor", "frontfloor"),
    ("upinaci", "upinaci"), ("zavetrovani", "zavetrovani"), ("pricka", "pricka"), ("stul", "stul"),
    ("ramsikmy", "ramsikmy"), ("bocniram", "bocniram"), ("noha", "noha"), ("popruh", "popruh"),
    ("legsbox", "legsbox"), ("police", "police"), ("logo", "logo"), ("podlaha", "podlaha"),
]
_typ_dilu_cache = {}


def _role_dilu(o):
    """Role dilu = skupina PRIMO nad dilem (Unity/vanDrawee export:
    "Multibox_Arc.015", "drawer.002", "dark_grey_bin"...), klic = jen mala
    pismena bez "(Clone)". KOPIE scripts/_render_prirazeni_lib.role_dilu
    (+ webapp/kontrola.html roleDilu) - Robert 2026-09-28: "v různých
    sestavách mají multiboxy různý materiál" (blue KLT / multibox), role je
    ale vzdy stejna."""
    if o.parent is None:
        return ""
    return re.sub(r"[^a-z]", "", re.sub(r"\(clone\)", "", o.parent.name, flags=re.I).lower())


def _typ_dilu(o):
    if o.name in _typ_dilu_cache:
        return _typ_dilu_cache[o.name]
    retez, p = [], o
    while p is not None:
        retez.append(p.name.lower())
        p = p.parent
    typ = ""
    for jmeno in reversed(retez):
        typ = next((t for k, t in _TYPY_DILU if k in jmeno), "")
        if typ:
            break
    _typ_dilu_cache[o.name] = typ
    return typ


def _rodina_materialu(jmeno):
    """'CUB seda (Instance).003' -> 'cub seda' - jmeno materialu tak, jak
    je v Unity/vanDrawee zdroji, bez glTF/Blender pripon kopii. Stejne
    pravidlo jako scripts/_render_prirazeni_lib.rodina_materialu (podle
    nej se v adminu vypisuji radky tabulky)."""
    n = (jmeno or "").strip()
    n = re.sub(r"\s*\(instance\).*$", "", n, flags=re.I)
    n = re.sub(r"\.\d{3}$", "", n)
    return n.lower()


# vd_nahrady (Robert 2026-09-28: "každý materiál udělej jeden řádek") -
# [[rodina, material_v_knihovne], ...] z adminu, pro KAZDOU rodinu
# materialu Vandr GLB zvlast. Presna shoda rodiny (ne podretezec - jinak
# by "material_1" zasahl i "material_11"). Ma prednost pred vsemi
# vychozimi pravidly nize (VD_NAHRADA_PODLE_JMENA, cub seda...), krome
# kryci listy v drazce (ta zustava podle geometrie, viz _je_kryci_lista_klt).
# Klic (rodina, typ_dilu) - typ "" = vsechny typy dilu (radek rodiny),
# konkretni typ (radek "rozdělit podle dílu") ma prednost, viz _cil_nahrady.
VD_NAHRADY = {}
for _nh in (JOB.get("vd_nahrady") or []):
    if len(_nh) >= 2 and _nh[0] and _nh[1]:
        VD_NAHRADY[(str(_nh[0]).strip().lower(), str(_nh[2] if len(_nh) > 2 and _nh[2] else "").strip().lower())] = str(_nh[1]).strip()


def _cil_nahrady(o, jmeno_materialu):
    # role dilu (radky tabulky "podle role") ma prednost pred rodinou materialu
    ro, typ = _role_dilu(o), _typ_dilu(o)
    cil = VD_ROLE.get((ro, typ)) or VD_ROLE.get((ro, ""))
    if cil:
        return cil
    r = _rodina_materialu(jmeno_materialu)
    return VD_NAHRADY.get((r, typ)) or VD_NAHRADY.get((r, ""))


# vd_role: [[role, material, typ], ...] - role = klic _role_dilu, typ ""=vsechny
VD_ROLE = {}
for _vr in (JOB.get("vd_role") or []):
    if len(_vr) >= 2 and _vr[0] and _vr[1]:
        VD_ROLE[(str(_vr[0]).strip().lower(), str(_vr[2] if len(_vr) > 2 and _vr[2] else "").strip().lower())] = str(_vr[1]).strip()


def _je_kryci_lista_klt(o, nazev):
    """Kryci lista v drazce (tenky prouzek "blue KLT") - viz dlouhy
    komentar u puvodniho mista pouziti v hlavni smycce materialu."""
    return ("klt" in nazev and min(o.dimensions) < 15.0
            and sorted(o.dimensions)[1] < 50.0)


def _mat_nazev_bez_instance(o):
    """Material name(s) pro aktualni slot, lowercase - jen pro
    _je_celo_supliku_klt vyse."""
    if not o.data or not hasattr(o.data, "materials"):
        return ""
    return " | ".join((m.name if m else "").lower() for m in o.data.materials)
ALU_PREPSAN = ALU_REALNY   # True = Vandr ALU bere TEMPLATE_MATS["alu"] (viz alu_zaklad)
# alu_uv_mm (opt-in, VYCHOZI VYPNUTO; Robert 2026-09-26, ukazal Alumi2 na
# profilu "45x45x1450_noha": Texture Coordinate UV -> Mapping (Point, scale 1)
# -> obrazky, zadne promitani): hlinikovym dilum dat kubicke UV se SKUTECNOU
# velikosti vzoru ALU_UV_MM mm na opakovani a material pouzit BEZ box-
# projekce, presne jak je. Displacement se prepocte z metru na mm (x1000).
ALU_UV_MM = float(JOB.get("alu_uv_mm") or 0.0)
_box_cache = {}


def _na_box_projekci(zaklad):
    """Kopie materialu, ktera se obejde bez UV souradnic.

    Kdyz material zadnou obrazkovou texturu nema (rucne naladeny Principled
    BSDF), vraci se beze zmeny - neni co promitat."""
    if zaklad is None or not zaklad.use_nodes:
        return zaklad
    obrazkove = [n for n in zaklad.node_tree.nodes
                 if n.bl_idname == "ShaderNodeTexImage"]
    if not obrazkove:
        return zaklad
    if zaklad.name in _box_cache:
        return _box_cache[zaklad.name]
    m = zaklad.copy()
    m.name = "%s_box" % zaklad.name
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0 / TEXTURE_TILE_MM,) * 3
    nt.links.new(mp.inputs["Vector"], tc.outputs["Object"])
    for n in nt.nodes:
        if n.bl_idname != "ShaderNodeTexImage":
            continue
        n.projection = "BOX"
        n.projection_blend = 0.3
        n.extension = "REPEAT"
        for odkaz in list(n.inputs["Vector"].links):
            nt.links.remove(odkaz)
        nt.links.new(n.inputs["Vector"], mp.outputs["Vector"])
    _box_cache[zaklad.name] = m
    print("MATERIAL: %s -> box-projekce (%d textur, dlazdice %.0f mm)"
          % (zaklad.name, len(obrazkove), TEXTURE_TILE_MM))
    return m


def _alu_realny_kopie(zaklad):
    """Kopie originalniho hliniku ze sablony (NIKDY ne zmena na miste - sablona
    je Robertova) s meritkem prepocitanym pro mm scenu: vsechny obrazky
    hliniku ctou Object souradnice pres Mapping se skalou 1/ALU_TILE_MM (box
    projekce, funguje i bez UV) a uzel Displacement ma silu nasobenou
    ALU_DISP_MULT. Barva/kovovost/drsnost/coat se nemeni - zustavaji z map."""
    if zaklad is None or not zaklad.use_nodes:
        return zaklad
    m = zaklad.copy()
    m.name = "%s_alu_realny" % zaklad.name
    nt = m.node_tree
    obrazkove = [n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage"]
    if obrazkove:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1.0 / ALU_TILE_MM,) * 3
        nt.links.new(mp.inputs["Vector"], tc.outputs["Object"])
        for n in obrazkove:
            n.projection = "BOX"
            n.projection_blend = 0.3
            n.extension = "REPEAT"
            for odkaz in list(n.inputs["Vector"].links):
                nt.links.remove(odkaz)
            nt.links.new(n.inputs["Vector"], mp.outputs["Vector"])
    disp = [n for n in nt.nodes if n.bl_idname == "ShaderNodeDisplacement"]
    for n in disp:
        n.inputs["Scale"].default_value *= ALU_DISP_MULT
    print("ALU REALNY: %s -> %d textur, dlazdice %g mm, relief x%g (%d uzel/uzlu)"
          % (zaklad.name, len(obrazkove), ALU_TILE_MM, ALU_DISP_MULT, len(disp)))
    return m


def _najdi_sablonovy_mat(jmena):
    for j in jmena:
        m = bpy.data.materials.get(j)
        if m is not None:
            return _na_box_projekci(m)
    return None


def _najdi_sablonovy_mat_syrovy(jmena):
    """Stejne jako _najdi_sablonovy_mat, ale BEZ vynucene box-projekce.
    Box-projekce existuje jen proto, ze NASE VLASTNI profily nemaji UV
    souradnice vubec (viz komentar u _na_box_projekci) - vanDrawee/Unity
    import ale UV MA (overeno 2026-09-22 na "20x40x1258": vrstva
    "UVMap"), takze vynucena box-projekce tam jen prepisuje spravne UV
    mapovani generickym Object-coords mapovanim a vyrabi jiny (spatny)
    vzhled, nez jaky Robert vidi na cistem materialu primo v Blenderu."""
    for j in jmena:
        m = bpy.data.materials.get(j)
        if m is not None:
            return m
    return None


TEMPLATE_MATS = {k: _najdi_sablonovy_mat(v)
                 for k, v in TEMPLATE_MAT_NAMES.items()}
if ALU_REALNY:
    # hlinik katalogovych profilu (TEMPLATE_MATS["alu"]) i Vandr ("ALU
    # (Instance)", viz alu_zaklad nize) je od ted TATENTO kopie - jeden
    # hlinik v cele scene, ne dva ruzne (profil surovy vs vypln box).
    for _jm in TEMPLATE_MAT_NAMES["alu"]:
        _alu_zdroj = bpy.data.materials.get(_jm)
        if _alu_zdroj is not None:
            TEMPLATE_MATS["alu"] = _alu_realny_kopie(_alu_zdroj)
            break
has_template_world = sc.world is not None and sc.world.use_nodes
has_template_light = any(o.type == "LIGHT" for o in sc.objects)
print("SABLONA: world=%s svetla=%s podlaha=%s materialy=%s"
      % (has_template_world, has_template_light, bool(template_floor),
         sorted(k for k, v in TEMPLATE_MATS.items() if v)))

# ------------------------------------------------------------- materialy
PALETTE_BY_HEX = {
    "#c9cdd1": "alu", "#242424": "black", "#b7bcc0": "zinc",
    "#1c1c1e": "guma", "#666c73": "plast_svetly",
}
_mat_cache = {}
_kryci_lista_pruhledna = [None]


def _pruhledny_material_kryci_listy():
    """Kopie beze zmeny nikoho jineho - vlastni material, jednou vytvoren a
    cachovan (viz _kryci_lista_pruhledna), Alpha=0 (uplne pruhledny). Robert
    2026-09-27: 'sedy material na krycich listach je flekaty, drsny... kdyz
    dam listam pruhlednost 100% nebudou videt a bude tam stin' - misto sede
    barvy prouzek zmizi, zustane jen prohlubeny drazky v profilu (pripadne
    jeste ztmavena AO, viz alu_ao_sila)."""
    if _kryci_lista_pruhledna[0] is None:
        m = bpy.data.materials.new("TT_KRYCI_LISTA_PRUHLEDNA")
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        if b is not None and "Alpha" in b.inputs:
            b.inputs["Alpha"].default_value = 0.0
        for atribut, hodnota in (("blend_method", "BLENDED"), ("surface_render_method", "BLENDED")):
            try:
                setattr(m, atribut, hodnota)
            except (AttributeError, TypeError):
                pass
        _kryci_lista_pruhledna[0] = m
    return _kryci_lista_pruhledna[0]

# Robert 2026-09-11: "aplikuj [UDIN] doplnek na scenu X30-1 a pouzij material
# na 3D loga" - misto skladani z cisel (metalness/roughness/transmission/
# ior nize) se muze pouzit HOTOVY material ze sablony, kdyz tam je. Jmeno
# NENI zadratovane v `_material_for()` - je to tahle jedna konstanta, zmena
# nevyzaduje zasah do logiky. `LOGO_PART_ID` je doslovna shoda s
# `razitkovac.LOGO_PART_ID` ("logo_logiman_cz") - nejde o import (Blenderovo
# vestavene Python nema jiste `scripts/` na sys.path a razitkovac.py by sem
# tahl zavislost, kterou tenhle soubor jinak nema), jde o stejny retezec
# ridici stejnou vec ve dvou procesech - zmena part_id loga by se musela
# promitnout na obou mistech uz tak (je to `part_id` v katalogu, ne
# libovolny nazev).
LOGO_PART_ID = "logo_logiman_cz"
# Tuple, stejny vzor jako TEMPLATE_MAT_NAMES vyse (bot4, 2026-09-12):
# Robert v sablone X30-02 material prejmenoval/vytvoril pod vlastnim
# jmenem "logo Logiman" - puvodni UDIN jmeno zustava PRVNI (zpetna
# kompatibilita se starsimi cache sablonami, ktere jeste vlastni jmeno
# nemaji), _najdi_sablonovy_mat() nize zkousi postupne a vezme prvni
# nalezene.
LOGO_SABLONOVY_MATERIAL = ("TRANSPARENT PLASTIC - orange", "logo Logiman")  # UDIN Shaders Free, vybral Robert 2026-09-11

# Robert 2026-09-11: "zkus otestovat i material METAL raw na profily" -
# DRUHA konstanta se jmenem (ne natvrdo v logice), jen pro hlinikove
# profily (`layer == "alu"`), NE desky/vyplne/euroboxy (Robert vyslovne:
# "omez to na hlinikove", ne na "vsechny profily" v sirsim slova smyslu).
#
# ⭐ PROC PER-BARVA, NE JEDEN SDILENY MATERIAL JAKO U LOGA: logo ma jednu
# pevnou barvu, profily maji desitky - stribrne, cerne, bile z katalogu.
# "METAL - raw" je node GROUP s VLASTNIM otevrenym vstupem `color` (dnes
# neutralni sedá "syrovy hlinik") - misto prevzeti materialu 1:1 (to by
# smazalo cernou/bilou na vsem) se pro KAZDOU ODLISNOU barvu vyrobi JEDNA
# kopie (bpy.data.materials.copy()) s timhle vstupem prepsanym na
# `part["base_color"]`, cachovana podle (jmeno, hex) - `_mat_cache`
# uz presne tenhle vzor dela pro cisla nize, jen o krok driv.
PROFIL_SABLONOVY_MATERIAL = "METAL - raw"  # UDIN Shaders Free, Robert 2026-09-11
PROFIL_SABLONOVY_VRSTVA = "alu"


def _sablonovy_material_barva(zaklad, hexc, base_color):
    """Kopie sablonoveho materialu SE SKUPINOU (node group), ktera ma
    vlastni otevreny vstup `color` - vstup se prepise na `base_color`
    dilu, kopie se cachuje podle (jmeno zakladu, hex), ne vyrabi pro
    kazdy dil znovu (jinak by se pri stovce dilu vyrobilo sto materialu -
    viz komentar u PROFIL_SABLONOVY_MATERIAL). Pouziva se pro profily
    (desitky ruznych barev z katalogu) I pro logo (2026-09-11 - bot3
    nachytal, ze puvodni "vem material 1:1" nechalo logu UDIN VLASTNI
    oranzovou misto Robertovy #D4863F; stejnych 11 log v sestave ma
    stejny hex, takze i tady vznikne jen JEDEN material, ne 11).

    Vraci `zaklad` beze zmeny, kdyz v nem zadna skupina s `color` vstupem
    neni (jina/starsi verze sablonoveho materialu) - cesta zpet na cisla
    resi volajici (_material_for), tady se jen tise NEPREPISUJE barva."""
    klic = ("sablona_barva", zaklad.name, hexc)
    if klic in _mat_cache:
        return _mat_cache[klic]
    grp = next((n for n in zaklad.node_tree.nodes
               if n.type == "GROUP" and n.inputs.get("color") is not None), None)
    if grp is None:
        return zaklad   # sablona bez otevreneho `color` vstupu - nic k prepsani
    kopie = zaklad.copy()
    kopie.name = "%s_%s" % (zaklad.name, hexc.lstrip("#"))
    grp_kopie = next(n for n in kopie.node_tree.nodes
                    if n.type == "GROUP" and n.inputs.get("color") is not None)
    grp_kopie.inputs["color"].default_value = (base_color[0], base_color[1], base_color[2], 1.0)
    _mat_cache[klic] = kopie
    return kopie


def _transmission_input(b):
    """Nazev vstupu Principled BSDF pro pruhlednost se mezi verzemi
    Blenderu lisi (4.0+ prejmenoval "Transmission" na "Transmission
    Weight") - zkusit obe jistoty radsi nez tvrdy KeyError uprostred
    renderu."""
    for jmeno in ("Transmission Weight", "Transmission"):
        if jmeno in b.inputs:
            return b.inputs[jmeno]
    return None


def _material_for(part):
    """Material dilu. Kdyz sablona nabizi TT_<VRSTVA> pro paletovou barvu
    dilu, pouzije se ON (Robert si ho naladil v GUI). Jinak se postavi
    Principled BSDF presne z (barva, kovovost, drsnost, pruhlednost, IOR)
    spoctenych na serveru - stejna petice, jakou dostane material ve
    scene.

    transmission/ior pribyly 2026-09-11 (Robert: "logo s barevnym sklem").
    Kdyby jednou existoval TT_<VRSTVA> sablonovy material i pro sklo,
    `tmpl` vetev vyse pruhlednost NERESI (bere material tak, jak si ho
    Robert naladil v GUI) - dnes to nevadi, PALETTE_BY_HEX pro sklo zaznam
    nema (zamerne, viz razitkovac.py komentar u LOGO_BARVA_HEX)."""
    hexc = (part.get("color_hex") or "").lower()

    # Sablonovy material podle jmena, JEN pro razitkove logo (viz
    # LOGO_SABLONOVY_MATERIAL vyse). Kdyz sablona material tohoto jmena
    # NEMA (jina/starsi sablona, nebo doplnek jeste nepripojen), spada se
    # tise na vypocet z cisel nize - beze zmeny, nic se nerozbije.
    #
    # ⭐ Material se NEBERE 1:1 (do 2026-09-11 se bral - bot3 nachytal, ze
    # logo tim dostalo UDIN VLASTNI oranzovou barvu materialu, ne
    # Robertovu #D4863F, na AgX vysly do cervena). Overeno prosledovanim
    # uzlu skupiny: vstup `color` vede (primo i pres Combine Color
    # rekombinaci R/G/B) do OBOU Glass BSDF uzlu, tedy tonuje i PROSLE
    # svetlo, ne jen odlesk - prepsani na Robertovu barvu je proto
    # spravna a plna oprava, ne jen kosmeticka zmena odlesku.
    if part.get("part_id") == LOGO_PART_ID:
        # _najdi_sablonovy_mat (ne primy .get()) - LOGO_SABLONOVY_MATERIAL
        # je ted tuple vice moznych jmen, stejny helper uz pouziva
        # TEMPLATE_MATS vyse. Box-projekce uvnitr helperu je pro tenhle
        # material no-op (UDIN glass/plast shader nema zadne obrazkove
        # textury), akorat se sdili jedna overena cesta hledani jmena.
        zaklad = _najdi_sablonovy_mat(LOGO_SABLONOVY_MATERIAL)
        if zaklad is not None:
            barevny = _sablonovy_material_barva(zaklad, hexc, part.get("base_color") or [0.6, 0.6, 0.6])
            # Kdyby sablona jednou nemela otevreny `color` vstup (jina
            # verze doplnku), `barevny is zaklad` a barva by tise zustala
            # UDIN vychozi - presne dnesni bug. Radeji spadnout na cisla
            # (zaruceny spravny odstin) nez tise ukazat spatnou barvu.
            if barevny is not zaklad:
                return _s_alfou(barevny, part)

    # Sablonovy material podle jmena PRO HLINIKOVE PROFILY (viz
    # PROFIL_SABLONOVY_MATERIAL vyse) - JEN `layer == "alu"`, ne desky/
    # vyplne/euroboxy (Robert vyslovne). Na rozdil od loga se material
    # NEVEZME 1:1 - profily maji desitky ruznych barev z katalogu (cerna/
    # stribrna/bila), takze se pro KAZDOU ODLISNOU barvu vyrobi (a
    # cachuje) vlastni kopie s prepsanym `color` vstupem skupiny, viz
    # _sablonovy_material_barva. Kdyz sablona material nema, nebo nema
    # otevreny `color` vstup, funkce tise vrati zaklad beze zmeny barvy -
    # tady se to detekuje (`is base`) a spada se na cisla, presne jako
    # u loga.
    if part.get("layer") == PROFIL_SABLONOVY_VRSTVA:
        zaklad = bpy.data.materials.get(PROFIL_SABLONOVY_MATERIAL)
        if zaklad is not None:
            barevny = _sablonovy_material_barva(zaklad, hexc, part.get("base_color") or [0.6, 0.6, 0.6])
            if barevny is not zaklad:
                return _s_alfou(barevny, part)

    # ⭐ Puvodni TT_<VRSTVA>/vlastni-jmeno vetev (Robertovo GUI-naladene
    # "Sandblasted aluminium"/"Scratched grey plastic" atd.) - AZ TADY,
    # PO METAL_RAW zkousce vyse. 2026-09-11 bot3 zmeril, ze render s
    # "METAL - raw" vysel bit na bit stejny jako cisla - PRICINA: tenhle
    # blok byl puvodne NAHORE a pro `#c9cdd1` (hlinik) `TEMPLATE_MATS["alu"]`
    # NAJDE Robertovu "Sandblasted aluminium" v sablone driv, nez se
    # METAL_RAW test vubec stihne zeptat - vracelo se VZDY tohle, kod pro
    # METAL_RAW byl mrtvy (nedosazitelny). Presunutim za METAL_RAW test
    # se poradi zmenilo na: nova UDIN zkouska (kdyz je pripojena a barevna)
    # -> Robertuv vlastni naladeny material (kdyz existuje) -> cisla.
    layer = PALETTE_BY_HEX.get(hexc)
    tmpl = TEMPLATE_MATS.get(layer) if layer else None
    if tmpl is not None:
        return _s_alfou(tmpl, part)

    key = (hexc, round(float(part["metalness"]), 3), round(float(part["roughness"]), 3),
          round(float(part.get("transmission") or 0.0), 3), round(float(part.get("ior") or 1.45), 3))
    if key not in _mat_cache:
        m = bpy.data.materials.new("TT_%s" % (hexc.lstrip("#") or "def"))
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        col = part.get("base_color") or [0.6, 0.6, 0.6]
        b.inputs["Base Color"].default_value = (col[0], col[1], col[2], 1.0)
        b.inputs["Metallic"].default_value = key[1]
        b.inputs["Roughness"].default_value = key[2]
        trans_in = _transmission_input(b)
        if trans_in is not None:
            trans_in.default_value = key[3]
        if "IOR" in b.inputs:
            b.inputs["IOR"].default_value = key[4]
        _mat_cache[key] = m
    return _s_alfou(_mat_cache[key], part)


def _s_alfou(zaklad, part):
    """Poloprusvitna varianta materialu, kdyz si dil rekne o `alpha` < 1.

    Pouziva to vypln drazky pod razitkem (Robert 2026-09-10: "pruhlednost
    vyplne drazky 50%"). Material se KOPIRUJE, nikdy nemeni na miste -
    jinak by pruhlednost chytly i profily, ktere s vypln sdileji tentyz
    TT_ALU ze sablony.
    """
    alfa = float(part.get("alpha") or 1.0)
    if alfa >= 0.999:
        return zaklad
    klic = ("alfa", zaklad.name, round(alfa, 3))
    if klic in _mat_cache:
        return _mat_cache[klic]
    m = zaklad.copy()
    m.name = "%s_a%02d" % (zaklad.name, round(alfa * 100))
    b = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
    if b is not None and "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = alfa
    # EEVEE potrebuje rezim michani; Cycles si vystaci s Alpha vstupem.
    # Nazev vlastnosti se mezi verzemi Blenderu lisi, proto opatrne.
    for atribut, hodnota in (("blend_method", "BLEND"),
                             ("surface_render_method", "BLENDED")):
        try:
            setattr(m, atribut, hodnota)
        except (AttributeError, TypeError):
            pass
    _mat_cache[klic] = m
    return m


# ------------------------------------------------- vd materialy (nativni_material)
# 2026-09-21, Robert: vanDrawee vetev NEPREBIRA materialy ze zdrojoveho
# FBX/GLB a NESDILI se s hlavni katalogovou radou (TEMPLATE_MATS vyse) -
# stavi se rovnou v Blenderu, viz VD_ prefix. Na rozdil od ALU (ktery uz
# v X30-02.blend sablone existuje - TEMPLATE_MATS["alu"]) tahle knihovna
# NENI soucasti sablony, je to samostatny .blend (scripts/2026-09-21_vd_
# materialy/vd_materialy.blend, mimo hlidane webapp/*+api/*.py cesty) -
# nacita se sem pres bpy.data.libraries.load(), lazy (jen kdyz prijde
# nativni dil), jednou za beh skriptu.
# Na vzdalenem GPU workeru (Logiman2) tenhle skript bezi z docasneho
# stazeneho adresare, ne z repa - `__file__`-relativni cesta by tam NIC
# nenasla (worker si stahuje jen job.json/skript/GLB/sablonu, viz
# scripts/render_worker_agent.py run_turntable_job). Server ji tam proto
# posila zvlast (vd_materialy_url -> JOB["vd_materialy_path"], stejny
# vzor jako template_blend) - nalezeno 2026-09-21 (bot4): bez tohohle
# oprava materialu ZE DVOU RENDERU vysla bit-identicky, protoze knihovna
# se na workeru tise nenasla ani jednou (viz AGENTS_LOG).
VD_MATERIALY_BLEND = JOB.get("vd_materialy_path") or os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..",
    "scripts", "2026-09-21_vd_materialy", "vd_materialy.blend"))
# Shoda podle CASE-INSENSITIVE podretezce ve jmenu PUVODNIHO (glTF-importem
# prirazeneho) materialu -> jmeno VD_ materialu v knihovne vyse. Poradi
# nerozhoduje (podretezce se navzajem nekryji). Material_3 (2 pouziti)
# zustava ZAMERNE nenahrazen - Robert 2026-09-22 ve vd_material_vzorky_01.blend
# prirazuje "Material_3_Instance" jeho vlastnimu puvodnimu jmenu ("Material_3
# (Instance)"), tedy vyslovne "nechat nativni". Material_11 uz VYBRAN je
# (nize) - puvodni "zadny vyber pro tyhle dva" uz neplati jen pro nej.
#
# ⭐ OPRAVENO 2026-09-22 (Robert, presnou identifikaci nasel sam nad
# "drawer.015/016" empty pivoty): "PolicedoorB2040S40*" NENI suplik -
# je to JINY typ skrinky (otocna dvirka), s "blue KLT" jen jako malym
# lemem (4 objekty). SKUTECNA vysuvna ocelova zasuvka je rodina
# "2suplikyocel20kg*" a VSECH jejich 8+8 panelu ma zdrojovy material
# "tyrkys" - tedy PRESNE to, co Robert cele tyhle noci myslel "modrou
# pro supliky" (viz feedback k "Blue Glossy Plastic"). Puvodni
# ancestor-based rozliseni u "klt"/"chrome" (_vd_material_klt/_chrome
# nize, driv resily nespravnou domnenku "policedoor=suplik") uz neni
# potreba - obe jmena mapuji rovnou, beze specialniho pripadu.
VD_NAHRADA_PODLE_JMENA = [
    ("chrome", "VD_CHROME"),
    ("preklizka", "VD_PREKLIZKA"),
    ("tyrkys", "VD_SUPLIK_MODRA"),
    ("klt", "VD_KLT_MODRA"),
    ("cub", "VD_CUB_SEDA"),
    ("black", "VD_BLACK"),
    ("material_11", "VD_MATERIAL_11"),
    ("orange", "VD_ORANGE"),
    # material_2 = bocni stena (bok) spodniho suplíku (Ducato 672,
    # zjisteno 2026-09-23 zvyraznovacim debug renderem) - Robert: "obycejnou
    # svetle sedou painted".
    ("material_2", "VD_SEDA_LAKOVANA"),
    # material_3 (Trafic 671) - "2suplikyocel20kg.../Object_2" telo suplíku,
    # PRESNE 2x pouziti - stejny pocet a stejna role jako material_11 (taky
    # 2x, jiny suplik na tehoz regalu). Robert 2026-09-23: "tělo šuplíku
    # musí být pořád v jedné barvě" - bez tohohle zustaval material_3
    # nativni (holy sedy 0.502 bez textury), material_11 uz mel
    # VD_MATERIAL_11 (texturovany) - 2 telesa svetle + 2 tmave na
    # stejnem regalu. Mapuje se na STEJNY VD_ material jako material_11
    # (ne jen podobny), aby byla shoda zarucena bit-presne.
    ("material_3", "VD_MATERIAL_11"),
]
_vd_mat_lib_stav = {"nacteno": False}


def _vd_material(jmeno):
    """Lazy-nacte VD_ knihovnu (jen prvni volani) a vrati material podle
    jmena, nebo None kdyz knihovna chybi/material v ni neni (tise se pak
    ponecha puvodni glTF material - viz volajici)."""
    if not _vd_mat_lib_stav["nacteno"]:
        _vd_mat_lib_stav["nacteno"] = True
        if os.path.exists(VD_MATERIALY_BLEND):
            with bpy.data.libraries.load(VD_MATERIALY_BLEND, link=False) as (data_from, data_to):
                data_to.materials = list(data_from.materials)
            nactene = sorted(m.name for m in bpy.data.materials if m.name.startswith("VD_"))
            print("VD MATERIALY: nacteno z knihovny: %s" % ", ".join(nactene))
        else:
            print("VD MATERIALY: knihovna nenalezena (%s) - VD_* prekryv preskocen" % VD_MATERIALY_BLEND)
    m = bpy.data.materials.get(jmeno)
    if m is not None:
        return m
    # tolerantne na mezery na okraji a velikost pismen (v knihovne je
    # napr. 'Red ' s mezerou, jmeno z CLI je vzdy orezane) - jen kdyz je
    # shoda JEDNOZNACNA
    def _norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())
    shoda = [x for x in bpy.data.materials if _norm(x.name) == _norm(jmeno)]
    return shoda[0] if len(shoda) == 1 else None


def _vyzadovany_material(jmeno, kde):
    """Material, ktery si VYSLOVNE vyzadala tabulka (ne vychozi VD_ jmeno):
    kdyz v knihovne neni, render se zastavi s jasnou hlaskou. Drive se tise
    nechal material z modelu a cela suplíku zustala svetle modra, ackoli
    v tabulce byl tmavy material (Robert 2026-09-29: "proto jsme delali
    priradovaci tabulku aby vsechno fungovalo transparentne")."""
    m = _vd_material(jmeno)
    if m is None:
        raise SystemExit("CHYBA TABULKY: material '%s' (%s) neni v zadne nactene knihovne - "
                         "render zastaven, aby se tise nepouzil jiny material." % (jmeno, kde))
    return m


def _uv_kubicka_mm(o, tile_mm):
    """Kubicka UV projekce v mm: pro kazdy polygon dominantni osa normaly, UV
    = ostatni dve LOKALNI souradnice / tile_mm (1 UV = tile_mm mm). Vandr GLB
    ma UV nesmyslna (delka-zavisla), katalogove profily zadna - tohle jim dava
    stejne, izotropni a fyzicke UV jako Robertova 'automap' (tam 0.5 mm).
    Nova vrstva TT_UV_MM je aktivni i pro render (tangenty normalove mapy)."""
    me = o.data
    if me.get("_tt_uv_mm") == tile_mm or len(me.polygons) == 0:
        return 0
    uv = me.uv_layers.get("TT_UV_MM") or me.uv_layers.new(name="TT_UV_MM")
    verts = me.vertices
    loops = me.loops
    uvd = uv.data
    for poly in me.polygons:
        n = poly.normal
        ax = 0 if (abs(n[0]) >= abs(n[1]) and abs(n[0]) >= abs(n[2])) else (1 if abs(n[1]) >= abs(n[2]) else 2)
        a, b = [i for i in (0, 1, 2) if i != ax]
        for li in poly.loop_indices:
            co = verts[loops[li].vertex_index].co
            uvd[li].uv = (co[a] / tile_mm, co[b] / tile_mm)
    uv.active_render = True
    me.uv_layers.active = uv
    me["_tt_uv_mm"] = tile_mm
    return 1


if ALU_MATERIAL:
    _alu_mat = _vyzadovany_material(ALU_MATERIAL, "hliník")
    if _alu_mat is not None and ALU_UV_MM > 0.0:
        # material beze zmeny (UV -> Mapping -> obrazky), jen KOPIE s
        # Displacement prepocitanym z metru na mm (Robert: scale 0.002 = 2 mm
        # v metrove scene; nase scena je v mm => x1000).
        _alu_uv = _alu_mat.copy()
        _alu_uv.name = "%s_uv" % _alu_mat.name
        _nd = 0
        if _alu_uv.use_nodes:
            for _n in _alu_uv.node_tree.nodes:
                if _n.bl_idname == "ShaderNodeDisplacement":
                    _n.inputs["Scale"].default_value *= 1000.0
                    _nd += 1
        TEMPLATE_MATS["alu"] = _alu_uv
        ALU_PREPSAN = True
        print("ALU MATERIAL: '%s' s UV %.3g mm/opakovani, displacement x1000 (%d uzlu), BEZ box-projekce"
              % (ALU_MATERIAL, ALU_UV_MM, _nd))
    elif _alu_mat is not None:
        # obrazkove materialy (bez UV na nasich profilech) pres box-projekci,
        # procedury (Object souradnice) beze zmeny - _na_box_projekci to
        # rozlisi samo. Material se KOPIRUJE jen kdyz ma obrazky.
        # meritko textury: alu_tile_mm z jobu (jinak TEXTURE_TILE_MM, 40 mm);
        # _na_box_projekci cte globalni TEXTURE_TILE_MM, proto ho jen na
        # tenhle jediny volani prepneme a hned vratime.
        _tile_pred = TEXTURE_TILE_MM
        TEXTURE_TILE_MM = ALU_TILE_MM
        TEMPLATE_MATS["alu"] = _na_box_projekci(_alu_mat)
        TEXTURE_TILE_MM = _tile_pred
        ALU_PREPSAN = True
        print("ALU MATERIAL: '%s' misto Sandblasted aluminium (katalog i Vandr)" % ALU_MATERIAL)
    else:
        print("ALU MATERIAL: '%s' v knihovne NENI - zustava Sandblasted aluminium" % ALU_MATERIAL)


def _pridej_ao_hlinik(mat, sila, vzdalenost_mm):
    """Kopie materialu s pridanym Ambient Occlusion do Base Color - Robert
    2026-09-27: 'drazky by mely byt tmavsi, rohy a zakouti take jakoby ve
    stinu'. Na rozdil od bodoveho svetla (funguje jen z jednoho uhlu, viz
    key_svetlo) je tohle cista geometrie - stejne tmave drazky/rohy na
    KAZDEM snimku otocky, ne jen na jednom pohledu.

    AO uzel: vstup Color = puvodni retezec barvy (cokoli dnes jde do
    Base Color), vystup Color = tenhle vstup VYNASOBENY occlusion faktorem
    (0=uplne zakryte/tmava skvira, 1=volny prostor beze zmeny) - presne
    "tmave drazky, svetle plochy". `sila` mixuje puvodni a AO-tmavenou
    barvu (0=beze zmeny, 1=plny efekt), aby se dalo doladit, jak moc tmave
    to je, bez zasahu do samotneho AO vypoctu."""
    if sila <= 0.0 or mat is None or not mat.use_nodes:
        return mat
    m = mat.copy()
    m.name = "%s_ao" % mat.name
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if p is None:
        return mat
    vstup = p.inputs["Base Color"]
    if vstup.links:
        zdroj = vstup.links[0].from_socket
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = vstup.default_value
        zdroj = rgb.outputs[0]
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = vzdalenost_mm
    nt.links.new(ao.inputs["Color"], zdroj)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["Factor"].default_value = min(1.0, max(0.0, sila))
    nt.links.new(mix.inputs["A"], zdroj)
    nt.links.new(mix.inputs["B"], ao.outputs["Color"])
    nt.links.new(p.inputs["Base Color"], mix.outputs["Result"])
    return m


ALU_AO_SILA = float(JOB.get("alu_ao_sila") or 0.0)
ALU_AO_VZDALENOST_MM = float(JOB.get("alu_ao_vzdalenost_mm") or 8.0)
if ALU_AO_SILA > 0.0 and TEMPLATE_MATS.get("alu") is not None:
    TEMPLATE_MATS["alu"] = _pridej_ao_hlinik(TEMPLATE_MATS["alu"], ALU_AO_SILA, ALU_AO_VZDALENOST_MM)
    print("ALU AO: sila %.2f, vzdalenost %.1f mm" % (ALU_AO_SILA, ALU_AO_VZDALENOST_MM))


def _ztmav_material_barvu(mat, sila):
    """Kopie materialu s znasobenou (ztmavenou) Base Color - Robert
    2026-09-28 (test HDRi 'telocvicna'): 'hlinik je hezky, ale sedy plast
    nam zbelal' - zmereno primo (~208 misto ~150-170 na zivem TV-studio
    receptu), plast_svetly pod nekterymi oblohami vychazi moc svetle.
    Na rozdil od AO vyse (geometricky efekt, tmavi jen drazky/rohy) tohle
    je plosne ztmaveni CELE plochy stejnym cislem - `sila` 0=beze zmeny,
    1=cerna, jednoduchy multiply puvodni barvy cislem (1-sila)."""
    if sila <= 0.0 or mat is None or not mat.use_nodes:
        return mat
    m = mat.copy()
    m.name = "%s_tmava" % mat.name
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if p is None:
        return mat
    vstup = p.inputs["Base Color"]
    if vstup.links:
        zdroj = vstup.links[0].from_socket
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = vstup.default_value
        zdroj = rgb.outputs[0]
    nasobek = max(0.0, 1.0 - min(1.0, sila))
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    mul.inputs["B"].default_value = (nasobek, nasobek, nasobek, 1.0)
    nt.links.new(mul.inputs["A"], zdroj)
    nt.links.new(p.inputs["Base Color"], mul.outputs["Result"])
    return m


PLAST_SVETLY_TMAVA_SILA = float(JOB.get("plast_svetly_tmava_sila") or 0.0)
if PLAST_SVETLY_TMAVA_SILA > 0.0 and TEMPLATE_MATS.get("plast_svetly") is not None:
    TEMPLATE_MATS["plast_svetly"] = _ztmav_material_barvu(TEMPLATE_MATS["plast_svetly"], PLAST_SVETLY_TMAVA_SILA)
    print("PLAST_SVETLY ZTMAVENI: sila %.2f" % PLAST_SVETLY_TMAVA_SILA)

# ⭐ OPRAVA 2026-09-28 (stejny vecer): prvni pokus vyse cilil na
# TEMPLATE_MATS["plast_svetly"] (#666c73) - to je ale material KRYCICH
# LIST v drazce, ktere bezne bezi SCHOVANE (--kryci-listy-pruhledne =
# hide_render, viz "past c. 1" nize v hlavni smycce), takze zadne
# ztmaveni nemelo jak byt videt. Sedy panel, ktery Robert skutecne vidi
# ("hlinik je hezky, ale sedy plast nam zbelal") je puvodni/necileny
# material "CUB seda (Instance)*" (#bbbbbb v GLB, zmereno v renderu
# ~208 - viz AGENTS_LOG) - NENI v PALETTE_BY_HEX, zustava tedy jako
# svuj vlastni nezmeneny material, ne jako TEMPLATE_MATS klic. Cileni
# proto musi byt PODLE JMENA MATERIALU (case-insensitive substring),
# stejnym zpusobem jako "klt"/"alu" nize v hlavni smycce pres objekty -
# viz CUB_SEDA_TMAVA_SILA blok tam.
CUB_SEDA_TMAVA_SILA = float(JOB.get("cub_seda_tmava_sila") or 0.0)
_cub_seda_tmava_cache = {}


def _cub_seda_tmava(mat):
    klic = mat.name
    if klic not in _cub_seda_tmava_cache:
        _cub_seda_tmava_cache[klic] = _ztmav_material_barvu(mat, CUB_SEDA_TMAVA_SILA)
    return _cub_seda_tmava_cache[klic]


# ---- vd_tint_overrides (2026-09-23, Robert: "kazdy testovaci render ponese
# informaci... material hliniku, cela suplíku, plastove vyplne") -----------
# Zadny z realnych VD_/ALU materialu NEMA hotovou druhou variantu k
# prepnuti (overeno primo v souborech, ne odhadem) - "Sandblasted
# aluminium"/VD_SUPLIK_MODRA/VD_KLT_MODRA jsou slozite procedury/textury
# (Image Texture, Voronoi, ColorRamp...), ne proste Principled cisla, takze
# prepsani Base Color/Roughness na Principled uzlu by se u nich tise
# NEPROJEVILO (vstup je linked, default_value se ignoruje). Misto
# prepisovani/hadani jejich vnitrni struktury se PRED Base Color vlozi
# jeden Mix(Color) uzel, ktery puvodni (nedotcenou) barvu/texturu smicha se
# zadanym cilovym odstinem podle `mix` faktoru - zachova skutecny povrch
# (skvrny, rysky, normal mapa...), jen posune celkovy ton/jas. Jednorazove
# PER RENDER (kopie materialu, cachovana podle klice), nic v knihovne na
# disku se netrvale nemeni.
_tint_cache = {}


def _apply_vd_tint(mat, nazev_lower):
    """Kdyz JOB['vd_tint_overrides'] obsahuje zaznam, jehoz 'match'
    podretezec je v `nazev_lower`, vrati OTINTOVANOU KOPII `mat` (barva
    posunuta smerem k zadanemu hex o `mix`, 0=beze zmeny/puvodni,
    1=cista cilova barva). Bez shody vraci `mat` beze zmeny."""
    if mat is None or not mat.use_nodes:
        return mat
    prekryvy = JOB.get("vd_tint_overrides") or []
    zaznam = next((p for p in prekryvy if p.get("match", "").lower() in nazev_lower), None)
    if zaznam is None:
        return mat
    hexc = (zaznam.get("hex") or "#808080").lstrip("#")
    mix = float(zaznam.get("mix", 0.5))
    r, g, b = (int(hexc[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    klic = (mat.name, hexc, round(mix, 3))
    if klic in _tint_cache:
        return _tint_cache[klic]
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return mat
    kopie = mat.copy()
    kopie.name = "%s_tint_%s_%s" % (mat.name, hexc, str(round(mix, 3)).replace(".", ""))
    b2 = next(n for n in kopie.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bc_in = b2.inputs["Base Color"]
    puvodni_link_from = bc_in.links[0].from_socket if bc_in.is_linked else None
    puvodni_default = tuple(bc_in.default_value)
    nt = kopie.node_tree
    mix_node = nt.nodes.new("ShaderNodeMix")
    mix_node.data_type = "RGBA"
    mix_node.blend_type = "MIX"
    mix_node.inputs["Factor"].default_value = mix
    mix_node.inputs["B"].default_value = (r, g, b, 1.0)
    if puvodni_link_from is not None:
        nt.links.new(puvodni_link_from, mix_node.inputs["A"])
    else:
        mix_node.inputs["A"].default_value = puvodni_default
    nt.links.new(mix_node.outputs["Result"], bc_in)
    _tint_cache[klic] = kopie
    print("VD TINT: %s -> %s (cil #%s, mix %.2f)" % (mat.name, kopie.name, hexc, mix))
    return kopie



# ---------------------------------------------------------------- dily
imported = []
glb_cache = {}
for part in JOB["parts"]:
    before = set(sc.objects)
    bpy.ops.import_scene.gltf(filepath=part["glb"])
    new = [o for o in sc.objects if o not in before]
    # vynechat_objekty (2026-09-20, Robert: "podlahu odstranit", vanDrawee
    # import) - nazvy (case-insensitive podretezec), ktere se ze SAMOTNEHO
    # GLB nemaji vubec renderovat (typicky vlastni znackova podlozka
    # externiho exportu, ne nase karoserie/podlaha). Smaze se CELY podstrom
    # (vc. deti), jinak by osirely potomek zustal viset bez rodice ve scene.
    vynechat = [s.lower() for s in (part.get("vynechat_objekty") or [])]
    if vynechat:
        # Bot4 2026-09-23: appka obcas neserializuje jmeno uzlu (Unity
        # runtime FBX export) a appka dosadi genericke "SomeName<N>_
        # Mesh_<M>" - substr match na NAZVU pak minul realnou podlahu/
        # karoserii, protoze prezila jen v nazvu MATERIALU (napr.
        # "podlaha_2"). Kontrola proto bezi na obou - nazvu objektu I
        # nazvech jeho materialu.
        #
        # Bot4 2026-09-23, druhy nalez (4582/4600/4601/4604 - "vodoznak
        # vanDrawee v renderu", bot3): stejny problem o patro vys - cely
        # vodoznak "vanDrawee" je 9 plochych mesh objektu (Object_1..9,
        # material "blue KLT" - beze stopy "logo" na nich samotnych) vsech
        # zavesenych pod JEDNOU rodicovskou Empty jmenem "logo". Kontrola
        # jmena/materialu samotneho objektu ho tedy minula uplne - "logo"
        # existovalo jen o uroven vys v hierarchii. Vyhledani proto lozi i
        # CELY RODICOVSKY RETEZEC (o.parent, o.parent.parent, ...), ne jen
        # primy objekt - presne stejna trida chyby ("jmeno prezilo jen u
        # predka, ne u listu"), tak i stejne reseni.
        def _ma_zamitnuty_predka(o):
            p = o.parent
            while p is not None:
                if any(s in p.name.lower() for s in vynechat):
                    return True
                p = p.parent
            return False
        def _ma_zamitnuty_nazev(o):
            if any(s in o.name.lower() for s in vynechat):
                return True
            if o.type == "MESH" and o.data:
                if any(m and any(s in m.name.lower() for s in vynechat) for m in o.data.materials):
                    return True
            return _ma_zamitnuty_predka(o)
        shoda = [o for o in new if _ma_zamitnuty_nazev(o)]
        # Bot3 2026-09-23, druhy nalez (Trafic 4904, pravdepodobne i
        # Transporter 4582/4587/4591): "SomeName<N>_Mesh_<M>" (ztracene
        # jmeno) muze byt MALA soucastka (podlaha, uz chycena vyse pres
        # material "podlaha_2") NEBO CELA KAROSERIE/kabina vozidla - bez
        # zadne jmenne ani materialove stopy k "karoserie" (na Trafic
        # material "plexi"/"red"). Overeno geometricky (bot4): tahle
        # dvojice ma bbox PRESNE 100% bbox CELE importovane casti ve
        # VSECH 3 osach (rack samotny 848x1970x1259mm, cela scena
        # 1720x2613x1446mm) - kamera pak zabira celou tuhle velkou
        # obalku, regal vyjde zmenseny/v rohu zaberu (presne to, co bot3
        # videl). Heuristika: "SomeName*" objekt pokryvajici >= 60% bbox
        # CELE importovane casti VE VSECH 3 OSACH NAJEDNOU = karoserie,
        # vyloucit bez ohledu na jmeno materialu.
        somename = [o for o in new if o.name.lower().startswith("somename") and o.type == "MESH"]
        if somename:
            def _bbox_world(o):
                corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
                mn = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
                mx = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
                return mn, mx
            mn_scena = Vector((1e18, 1e18, 1e18))
            mx_scena = Vector((-1e18, -1e18, -1e18))
            for o in new:
                if o.type != "MESH":
                    continue
                mn, mx = _bbox_world(o)
                for i in range(3):
                    mn_scena[i] = min(mn_scena[i], mn[i])
                    mx_scena[i] = max(mx_scena[i], mx[i])
            velikost_sceny = mx_scena - mn_scena
            for o in somename:
                if o in shoda:
                    continue
                mn, mx = _bbox_world(o)
                velikost_o = mx - mn
                if all(velikost_sceny[i] <= 1e-6 or velikost_o[i] / velikost_sceny[i] >= 0.6 for i in range(3)):
                    print("VYNECHANO (SomeName pokryva >= 60%% sceny, povazovano za "
                         "karoserii se ztracenym jmenem): %s" % o.name)
                    shoda.append(o)
        odstranit = set()
        fronta = list(shoda)
        while fronta:
            o = fronta.pop()
            if o in odstranit:
                continue
            odstranit.add(o)
            fronta.extend(o.children)
        pocet = len(odstranit)
        for o in odstranit:
            bpy.data.objects.remove(o, do_unlink=True)
        # ⭐ znovu ze ZIVE kolekce (sc.objects), NE filtrem stareho seznamu -
        # smazany objekt muze byt rodicem/nepratelim jineho objektu v `new`
        # zpusobem, ktery rekurze o.children nezachyti (napr. parent-child
        # vazba bez odpovidajiciho zaznamu v .children pri urcitem poradi
        # importu) - pak by po sc.objects.remove() zbyla v `new` mrtva
        # reference a i pouhe cteni o.parent na ni spadne na ReferenceError
        # "StructRNA of type Object has been removed" (nalezeno 2026-09-20).
        new = [o for o in sc.objects if o not in before]
        print("VYNECHANO (vynechat_objekty): %d objektu (%s)" % (pocet, ", ".join(sorted(vynechat))))
    roots = [o for o in new if o.parent is None]
    M = _three_to_blender_matrix(part["position"], part["quaternion"], part["scale"])
    # nativni_material (2026-09-20, Robertovo rozhodnuti, vanDrawee import):
    # DRUHA, PARALELNI vetev vedle standardni "1 dil = 1 color_hex" nize -
    # kdyz dil prinasi vlastni material(y) primo v GLB (typicky externi
    # vicematerialovy export, ne nas katalogovy 1-barva-na-dil vzor),
    # _material_for() se VUBEC nevola (bere primo z part["metalness"] atd.,
    # ktere pro takovy dil nemaji smysl) a puvodni glTF-importem prirazeny
    # material se NEPREPISUJE. Standardni vetev (default, VSECHNY dosavadni
    # katalogove dily) beze zmeny.
    nativni = bool(part.get("nativni_material"))
    mat = None if nativni else _material_for(part)
    # ALU prekryv (2026-09-21, Robert: "potrebujeme dostat material hliniku
    # na tuto novou radu" - vanDrawee/externi importy). I v "nativni" vetvi
    # CHCEME nasi overenou sablonu pro hlinik ("TT_ALU"/"Sandblasted
    # aluminium" - viz TEMPLATE_MAT_NAMES vyse), misto spolehnuti na to, ze
    # kazdy dalsi FBX->GLB export bude mit spravne metalness/roughness
    # (prvni pokus mel 0/1 pro vsechno - viz AGENTS_LOG 2026-09-20).
    # ⭐ POZOR: PROFIL_SABLONOVY_MATERIAL ("METAL - raw") je JINA, STARSI
    # konstanta pro jinou/starsi verzi sablony - v aktualni X30-02.blend
    # NEEXISTUJE (bpy.data.materials.get() by tise vratil None a cely
    # prekryv by se nikdy neaplikoval - presne tenhle bug byl v prvni verzi
    # tohohle bloku, nalezeno 2026-09-21 - 0 rozdilu v pixelech pred/po).
    #
    # ⭐ OPRAVENO 2026-09-22 (Robert: "pri hdri 0,3 uz to mam v blenderu
    # celkem tmave a ty to mas porad svetle"): POUZIVA SE _najdi_sablonovy_
    # mat_SYROVY (bez box-projekce), NE TEMPLATE_MATS["alu"] (ktere JE
    # box-projektovane). Duvod: box-projekce existuje jen jako nahrada za
    # chybejici UV na NASICH VLASTNICH profilech - vanDrawee/Unity import
    # ale realne UV MA (overeno na "20x40x1258": vrstva "UVMap"), takze
    # vynucena box-projekce prepisovala spravne UV mapovani a vyrabela jiny
    # (svetlejsi/plossi) vzhled, nez jaky ma cisty material v Blenderu.
    #
    # Prekryje se JEN material, jehoz jmeno obsahuje "alu" (case-insensitive,
    # Unity/vanDrawee konvence "ALU (Instance)") - ostatni nativni materialy
    # (plasty, cerna...) zustavaji nedotcene. Barva se PRENASI ze zdroje
    # (baseColorFactor, uz nactene glTF importem do Principled BSDF Base
    # Color), jen finish/lesk je nas.
    alu_zaklad = _najdi_sablonovy_mat_syrovy(TEMPLATE_MAT_NAMES["alu"]) if nativni else None
    if ALU_PREPSAN and nativni and TEMPLATE_MATS.get("alu") is not None:
        alu_zaklad = TEMPLATE_MATS["alu"]
    if VD_PUVODNI_NEVYPLNENE and not ALU_MATERIAL:
        alu_zaklad = None   # radek hliniku prazdny = hlinik z modelu
    for r in roots:
        r.matrix_world = M @ r.matrix_world
    for o in new:
        if o.type != "MESH":
            continue
        if not nativni:
            o.data.materials.clear()
            o.data.materials.append(mat)
        else:
            for i, m in enumerate(o.data.materials):
                if m is None:
                    continue
                nazev = m.name.lower()
                if (VD_NAHRADY or VD_ROLE) and not _je_kryci_lista_klt(o, nazev):
                    _cil = _cil_nahrady(o, m.name)
                    if _cil:
                        o.data.materials[i] = _vyzadovany_material(
                            _cil, "nahrada dilu '%s' (%s)" % (m.name, o.name))
                        continue
                if CUB_SEDA_TMAVA_SILA > 0.0 and "cub seda" in nazev:
                    o.data.materials[i] = _cub_seda_tmava(m)
                    continue
                # Kryci lista v drazce profilu (Vandr import, nalezeno na
                # Ducato 2b6d4dd7) sdili material "blue KLT" se supliky/
                # boxy - ROZLISUJE JE JEN GEOMETRIE: prouzek v drazce ma
                # nejtensi rozmer pod 15 mm A PROSTREDNI rozmer nejvyse
                # 20 mm (kryci listy/zamky, zmereno na vsech 101 mm-GLB,
                # 645 kusu). Robert 2026-09-26: "kryci listy chci nechat
                # sede, KLT boxy musi byt tmave modre" - box tedy jde
                # beze zmeny na normalni "klt" substr cestu nize, prouzek
                # dostane STEJNY sedy plast jako katalogove kryci listy
                # drazek (#666c73/"plast_svetly", viz PALETTE_BY_HEX) - je
                # to fyzicky stejna cast, ne nova barva. Test pred timhle
                # pravidlem, aby nedostal modrou drive, nez se sem kod
                # vubec dostane.
                # POZOR - DNO KLT boxu (rodina "Vysuv KLT*closed") je
                # taky tenke, presne 14.0 mm, se STEJNYM materialem
                # "blue KLT" jako box, ale je to plocha aspon 266 mm siroka.
                # Box je bez dna, dno je soucast KLT (Robert 2026-09-26:
                # "ta plotna pod KLT boxem je jeji dno") a MA BYT MODRE.
                # Samotny prah 15 mm (verze do 2026-09-26) ho obarvil
                # sede na 118 dnech ve 24 GLB (chyba bot4, prah
                # nerozlisoval dno od listy) - proto druha podminka.
                if _je_kryci_lista_klt(o, nazev):
                    if JOB.get("kryci_listy_debug"):
                        # DOCASNE, jen pro hledani (Robert 2026-09-27:
                        # "pokracuj s temi neviditelnyma krycima listama") -
                        # jasna emisni barva, at je videt presne kde na
                        # snimku tyhle objekty jsou, bez ohledu na svetlo.
                        _dbg = bpy.data.materials.get("TT_KRYCI_LISTA_DEBUG")
                        if _dbg is None:
                            _dbg = bpy.data.materials.new("TT_KRYCI_LISTA_DEBUG")
                            _dbg.use_nodes = True
                            _e = _dbg.node_tree.nodes.new("ShaderNodeEmission")
                            _e.inputs["Color"].default_value = (1.0, 0.0, 1.0, 1.0)
                            _e.inputs["Strength"].default_value = 3.0
                            _out = _dbg.node_tree.nodes.get("Material Output")
                            _dbg.node_tree.links.new(_out.inputs["Surface"], _e.outputs["Emission"])
                        o.data.materials[i] = _dbg
                        print("KRYCI LISTA DEBUG: %s rozmery=%s stred(world)=%s"
                              % (o.name, tuple(round(x, 1) for x in o.dimensions),
                                 tuple(round(x, 1) for x in o.matrix_world.translation)))
                        continue
                    if JOB.get("kryci_listy_pruhledne"):
                        # Robert 2026-09-27: "nemusis je davat pruhledne
                        # pokud je umis proste z geometrie na rendery
                        # skryt" - primo hide_render misto pruhledneho
                        # materialu (zjisteno: za listou casto neni zadna
                        # dalsi geometrie, pruhledny material tak odkryval
                        # cernou prazdnotu sceny - hide_render dava STEJNY
                        # vizualni vysledek, ale bez zbytecne kopie
                        # materialu a jednoznacne "neni soucasti dodavky").
                        o.hide_render = True
                        continue
                    seda = TEMPLATE_MATS.get("plast_svetly")
                    if seda is not None:
                        o.data.materials[i] = seda
                        continue
                if JOB.get("klt_debug") and _je_celo_supliku_klt(o):
                    # DOCASNE, jen pro hledani (Robert 2026-09-28: "cela
                    # supliku nesmi mit stejny material jako box KLT ani
                    # Multibox") - kazdy OBJEKT dostane jinou jasnou barvu
                    # podle hashe sveho jmena, at jde v renderu rozeznat
                    # kus od kusu (misto jedne spolecne magenty).
                    _h = abs(hash(o.name))
                    _barva = ((_h % 7) / 6.0, ((_h // 7) % 7) / 6.0, ((_h // 49) % 7) / 6.0, 1.0)
                    _kl = "klt_dbg_%s" % o.name
                    _dbg2 = bpy.data.materials.get(_kl)
                    if _dbg2 is None:
                        _dbg2 = bpy.data.materials.new(_kl)
                        _dbg2.use_nodes = True
                        _e2 = _dbg2.node_tree.nodes.new("ShaderNodeEmission")
                        _e2.inputs["Color"].default_value = _barva
                        _e2.inputs["Strength"].default_value = 2.0
                        _out2 = _dbg2.node_tree.nodes.get("Material Output")
                        _dbg2.node_tree.links.new(_out2.inputs["Surface"], _e2.outputs["Emission"])
                    o.data.materials[i] = _dbg2
                    print("KLT DEBUG: %s rozmery=%s stred(world)=%s barva=%s"
                          % (o.name, tuple(round(x, 1) for x in o.dimensions),
                             tuple(round(x, 1) for x in o.matrix_world.translation),
                             tuple(round(x, 2) for x in _barva[:3])))
                    continue
                if KLT_MATERIAL and _je_celo_supliku_klt(o):
                    # Robert 2026-09-28: "Blue_GloPLA.blend, aplikuj na celo
                    # supliku" - siroka/hlavni cast KLT boxu (cely suplik
                    # vc. viditelneho cela, NE uzka lista v drazce - ta uz
                    # skoncila vyse). Stejny vzor jako ALU_MATERIAL - jednorazovy
                    # A/B test jednoho snimku, nic v knihovne na disku se
                    # trvale nemeni.
                    _klt_mat = _vyzadovany_material(KLT_MATERIAL, "celo supliku")
                    if _klt_mat is not None:
                        o.data.materials[i] = _klt_mat
                        # (visible_diffuse/glossy=False zde bylo 2026-09-28
                        # kratce - ODSTRANENO: zmena Multiboxu nebyla odraz
                        # svetla, ale --vd-knihovna NAHRAZUJICI vychozi
                        # vd_materialy.blend, viz 2026-09-09_turntable_render.py.
                        # Dukaz: Multibox pixel-presne stejny s PM Blue i
                        # GloPLA, s flagy i bez.)
                        continue
                if alu_zaklad is not None and "alu" in nazev:
                    b = m.node_tree.nodes.get("Principled BSDF") if m.use_nodes else None
                    zdroj_barva = tuple(b.inputs["Base Color"].default_value[:3]) if b else (0.6, 0.6, 0.6)
                    synth_klic = "nativealu_%02x%02x%02x" % tuple(
                        min(255, max(0, int(round(c * 255)))) for c in zdroj_barva)
                    final_mat = _sablonovy_material_barva(alu_zaklad, synth_klic, zdroj_barva)
                    o.data.materials[i] = _apply_vd_tint(final_mat, "alu")
                    continue
                if VD_PUVODNI_NEVYPLNENE:
                    continue   # nevyplneny radek tabulky = material z modelu
                for podretezec, vd_jmeno in VD_NAHRADA_PODLE_JMENA:
                    if podretezec in nazev:
                        vd_mat = _vd_material(vd_jmeno)
                        if vd_mat is not None:
                            o.data.materials[i] = _apply_vd_tint(vd_mat, podretezec)
                        break
        # past c. 2 - bez tohohle vypadaji ostre hrany profilu zaoblene
        for poly in o.data.polygons:
            poly.use_smooth = False
        imported.append(o)

if not imported:
    raise SystemExit("Zadny dil se nenaimportoval - neni co renderovat.")
print("DILU naimportovano: %d mesh objektu z %d zaznamu" % (len(imported), len(JOB["parts"])))

# PAST c. 3 (nalezeno 2026-09-10 na sestave 279): kazdy nas .glb ma
# hierarchii `world` (EMPTY, root) -> `geometry_0` (MESH, dite). Vyse se
# transformace nastavuje POUZE rootum (`r.matrix_world = M @ ...`), ale
# bounding box nize se cte z `o.matrix_world` MESH POTOMKU - a ta se v
# Blenderu prepocita az pri aktualizaci depsgraphu. Bez tohohle radku
# vraci cast potomku JESTE NEPOSUNUTOU matici, takze se do boxu pridaji
# body kolem pocatku (u profilu Object_7 rozsah +-500 mm podle jeho
# vlastni delky). Dolozeno merenim: posun rootu o +1000 mm dal bez
# update() bbox -15..15, po update() spravnych 985..1015.
#
# Dusledek te chyby NENI spatna geometrie - ta se vykresli spravne,
# protoze render si depsgraph vyhodnoti sam. Spatne je RAMOVANI KAMERY:
# BOX_CENTER i vzdalenost se pocitaji z nafouknuteho boxu, takze sestava
# na prstencovych snimcich plave mimo stred a je mensi, nez ma byt.
bpy.context.view_layer.update()

# UV v mm pro hlinikove dily (opt-in alu_uv_mm) - AZ PO prirazeni materialu:
# hlinik = kazdy objekt, ktery ma slot s materialem TEMPLATE_MATS["alu"]
# (katalogove profily i Vandr "ALU (Instance)"), i alfa/tint kopie po nem.
if ALU_UV_MM > 0.0 and TEMPLATE_MATS.get("alu") is not None:
    _alu_zaklad_jmeno = TEMPLATE_MATS["alu"].name
    _n_uv = 0
    for _o in imported:
        if _o.type == "MESH" and any(s.material is not None and s.material.name.startswith(_alu_zaklad_jmeno)
                                     for s in _o.material_slots):
            _n_uv += _uv_kubicka_mm(_o, ALU_UV_MM)
    print("ALU UV: kubicke UV %.3g mm/opakovani na %d hlinikovych meshich" % (ALU_UV_MM, _n_uv))

# ------------------------------------------------------------------ box
# Bounding box sestavy v souradnicich PROHLIZECE (aby kamerova matematika
# byla doslovny port scene.html) - z Blenderu zpet pres C^-1.
mins = [1e18] * 3
maxs = [-1e18] * 3
for o in imported:
    for c in o.bound_box:
        w = C_INV @ (o.matrix_world @ Vector(c))
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
BOX_MIN = Vector(mins)
BOX_MAX = Vector(maxs)
BOX_CENTER = (BOX_MIN + BOX_MAX) / 2.0
BOX_SIZE = BOX_MAX - BOX_MIN
MAX_DIM = max(BOX_SIZE.x, BOX_SIZE.y, BOX_SIZE.z) or 1.0
print("BOX (mm, three.js osy): %.0f x %.0f x %.0f" % (BOX_SIZE.x, BOX_SIZE.y, BOX_SIZE.z))

# ---------------------------------------------------- karoserie (odrazy)
# Robert 2026-09-11, pres bot3: "souhlasim s pouzitím karoserie na
# odrazy, ale nebude videt, musí však mít materiál/povrch který odráží
# svetlo, tzn muze mít klidně hliník jako materiál, melo by se to
# projevit". Stejny mechanismus jako ODRAZNA DESKA nize
# (cycles_visibility.camera=False) - ale tohle je SKUTECNA geometrie
# vozu (podlaha+boky+prepazka, viz scripts/2026-09-11_karoserie_odrazy_
# audit.js a resolve_karoserie_odraz() v turntable_job.py), ne umela
# pomocna plocha. Vzadu ZAMERNE OTEVRENO (Robert: "otevrena zad
# odpovida tomu, jak se takovy regal fotí") - zadne dvere se
# nepridavaji, zdrojova data proste zadnou geometrii pro ne nemaji.
#
# Karoserie se K SESTAVE VZDY VAZE (JOB["karoserie_odraz"] pocita
# scripts/2026-09-09_turntable_job.py z jejich vlastnich car_body_* dilu),
# nikdy pevna - kdyz se nenajde nebo je zmerena vyska implausible (viz
# ten skript), `ok` je False a nize se hlasite spadne na chovani bez ni.
#
# ZAMERNE VYPNUTO VE VYCHOZIM STAVU (JOB["karoserie_odrazy"] musi byt
# truthy), stejny vzor jako u odrazne desky - je to pokus s parametrem k
# doladeni (drsnost), ne trvala zmena vzhledu.
_karoserie_data = JOB.get("karoserie_odraz") or {}
_karoserie_zapnuta = bool(JOB.get("karoserie_odrazy")) and bool(_karoserie_data.get("ok"))
_karoserie_objs = []
_karoserie_drsnost = float(JOB.get("karoserie_odrazy_drsnost", 0.3))


def _naimportuj_karoserii():
    """Cele telo "karoserie jako odraz" - VYCLENENO do funkce a volane pod
    jedinym try/except (bot3 2026-09-11, druhy pad: puvodni pojistka byla
    jen kolem `import_scene.gltf()`, ale spadlo to o radek DRIV, na
    `_karoserie_data.get("glb_files", [])` - ten vratil `None` misto []
    (server ulozil null MISTO prazdneho seznamu, `.get(x, [])` proti
    ulozenemu null nechrani, jen proti chybejicimu klici). Robertovo
    pravidlo 10.9.: pojistka musi byt tam, kde vznika skoda - tady to je
    UZ PRI SAHNUTI na data karoserie, ne az pri importu jednoho souboru.
    Karoserie je DOPLNEK, ne podminka - cokoli se pokazi (chybejici/None
    seznam, vadny soubor, cokoli neceka), se zaloguje a render pokracuje
    bez ni."""
    _kar_mat = bpy.data.materials.new("TT_KAROSERIE_MAT")
    _kar_mat.use_nodes = True
    _kb = _kar_mat.node_tree.nodes.get("Principled BSDF")
    if _kb:
        # Hlinik, NE matny povrch (Robert vyslovne: matny by nic
        # neodrazil). Drsnost je JOB parametr k doladeni cislem misto
        # commitem - 0.3 = viditelny, ne oslniva odraz (realny interier
        # dodavky je lakovany plech, ne zrcadlo).
        _kb.inputs["Base Color"].default_value = (0.82, 0.83, 0.85, 1.0)
        _kb.inputs["Metallic"].default_value = 1.0
        _kb.inputs["Roughness"].default_value = _karoserie_drsnost
    # `or []`, NE `.get(x, [])` - druhy jmenovany chrani jen kdyz klic
    # chybi, ne kdyz je ulozeny jako null (presne tahle mezera dnes
    # shodila render, viz komentar funkce vyse).
    for _glb_path in (_karoserie_data.get("glb_files") or []):
        if not _glb_path or not os.path.exists(_glb_path):
            print("KAROSERIE ODRAZY: soubor chybi (%r), preskakuji." % _glb_path)
            continue
        _before = set(sc.objects)
        try:
            bpy.ops.import_scene.gltf(filepath=_glb_path)
        except Exception as _e:
            print("KAROSERIE ODRAZY: import %s selhal (%s), preskakuji." % (_glb_path, _e))
            continue
        _new = [o for o in sc.objects if o not in _before]
        _roots = [o for o in _new if o.parent is None]
        _M = _three_to_blender_matrix([0, 0, 0], [0, 0, 0, 1], [1, 1, 1])
        for r in _roots:
            r.matrix_world = _M @ r.matrix_world
        for o in _new:
            if o.type != "MESH":
                continue
            o.data.materials.clear()
            o.data.materials.append(_kar_mat)
            # NA ROZDIL od profilu (use_smooth=False, past c.2 vyse) -
            # karoserie ma skutecne per-vertex normaly (overeno
            # 2026-09-11 auditnim nastrojem), hladke stinovani je tu
            # spravne, flat by vyrobilo umele facety navic.
            for poly in o.data.polygons:
                poly.use_smooth = True
            try:
                o.cycles_visibility.camera = False
                o.cycles_visibility.shadow = False
            except AttributeError:
                try:
                    o.visible_camera = False
                    o.visible_shadow = False
                except AttributeError:
                    pass
            _karoserie_objs.append(o)


if _karoserie_zapnuta:
    try:
        _naimportuj_karoserii()
    except Exception as _e:
        print("KAROSERIE ODRAZY: neocekavana chyba (%s), pokracuji BEZ karoserie." % _e)
        _karoserie_objs = []
    if _karoserie_objs:
        print("KAROSERIE ODRAZY: zapnuta - %s, %d mesh objektu, drsnost=%.2f"
              % (_karoserie_data.get("k_code") or _karoserie_data.get("base", "?"),
                 len(_karoserie_objs), _karoserie_drsnost))
    else:
        print("KAROSERIE ODRAZY: zadany, ale NEPODARILO SE naimportovat zadny "
              "mesh objekt - render pokracuje bez karoserie.")
        _karoserie_zapnuta = False
elif JOB.get("karoserie_odrazy") and not _karoserie_data.get("ok"):
    print("KAROSERIE ODRAZY: JOB['karoserie_odrazy'] zadano, ale karoserie pro "
          "tuhle sestavu NENI POUZITELNA (%s) - FALLBACK bez ni."
          % _karoserie_data.get("reason", "neznamy duvod"))
else:
    print("KAROSERIE ODRAZY: JOB['karoserie_odrazy'] nezadano, vypnuto (vychozi stav)")

FOV = float(JOB["fov_deg"])
SHADOW_PAD = float(JOB["shadow_pad"])


def _cam_dir(el_deg, az_deg):
    """scene.html ttCameraPosition s distance=1 a center=0 - jednotkovy
    smer stred -> kamera (souradnice prohlizece)."""
    el, az = math.radians(el_deg), math.radians(az_deg)
    return Vector((math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)))


def _basis(d):
    fwd = -d
    right = fwd.cross(Vector((0.0, 1.0, 0.0)))
    right.normalize()
    cam_up = right.cross(fwd)
    cam_up.normalize()
    return fwd, right, cam_up


def _box_points(with_ground_pad):
    pts = []
    for i in range(8):
        pts.append(Vector((BOX_MAX.x if i & 1 else BOX_MIN.x,
                           BOX_MAX.y if i & 2 else BOX_MIN.y,
                           BOX_MAX.z if i & 4 else BOX_MIN.z)))
    if with_ground_pad:
        for sx, sz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            pts.append(Vector((
                (BOX_MAX.x if sx > 0 else BOX_MIN.x) + sx * SHADOW_PAD, BOX_MIN.y,
                (BOX_MAX.z if sz > 0 else BOX_MIN.z) + sz * SHADOW_PAD)))
    return pts


def tt_compute_distance(aspect, margin, dirs, ground_pad=True):
    """scene.html:4757 ttComputeDistance - nejmensi vzdalenost, pri ktere se
    vsechny body vejdou do zorneho pole pro KAZDY smer z dirs."""
    pts = [p - BOX_CENTER for p in _box_points(ground_pad)]
    tan_v = math.tan(math.radians(FOV) / 2.0)
    tan_h = tan_v * aspect
    distance = 0.0
    for el_deg, az_deg in dirs:
        d = _cam_dir(el_deg, az_deg)
        _fwd, right, cam_up = _basis(d)
        for q in pts:
            along = q.dot(d)
            x = abs(q.dot(right))
            y = abs(q.dot(cam_up))
            distance = max(distance, along + x * margin / tan_h, along + y * margin / tan_v)
    return distance


def tt_fit_still(el_deg, az_deg, aspect, margin):
    """scene.html:4811 ttFitStill - tesny fit jednoho stillu, kde se smi
    posunout i cil kamery (perspektiva jinak vytlaci bližší roh mimo osu).
    8 iteraci, stejne jako v prohlizeci."""
    corners = _box_points(True)
    tan_v = math.tan(math.radians(FOV) / 2.0)
    tan_h = tan_v * aspect
    d = _cam_dir(el_deg, az_deg)
    fwd, right, cam_up = _basis(d)
    target = BOX_CENTER.copy()
    distance = tt_compute_distance(aspect, margin, [(el_deg, az_deg)])
    for _ in range(8):
        cam_pos = target + d * distance
        x_min, x_max = 1e18, -1e18
        y_min, y_max = 1e18, -1e18
        for c in corners:
            rel = c - cam_pos
            depth = max(1e-6, rel.dot(fwd))
            x = rel.dot(right) / (depth * tan_h)
            y = rel.dot(cam_up) / (depth * tan_v)
            x_min, x_max = min(x_min, x), max(x_max, x)
            y_min, y_max = min(y_min, y), max(y_max, y)
        target = target + right * ((x_max + x_min) / 2.0 * distance * tan_h)
        target = target + cam_up * ((y_max + y_min) / 2.0 * distance * tan_v)
        occ = max((x_max - x_min) / 2.0, (y_max - y_min) / 2.0)
        distance *= occ * margin
    return target, distance


# --------------------------------------------------------------- podlaha
# Shadow catcher: v Cycles je to nativni vlastnost objektu (kvalitnejsi nez
# ShadowMaterial + fade shader v prohlizeci). Kdyz sablona nese TT_FLOOR,
# jen se posune pod sestavu; jinak se vyrobi rovina pres pudorys + fade.
def _to_blender_point(v):
    return C @ Vector((v[0], v[1], v[2]))


floor_r = max(BOX_SIZE.x, BOX_SIZE.z) / 2.0 + float(JOB["shadow_fade"]) + SHADOW_PAD
floor_center_three = Vector((BOX_CENTER.x, BOX_MIN.y, BOX_CENTER.z))
if template_floor is not None:
    template_floor.location = _to_blender_point(floor_center_three)
    template_floor.is_shadow_catcher = True
else:
    bpy.ops.mesh.primitive_plane_add(size=floor_r * 2.0, location=_to_blender_point(floor_center_three))
    template_floor = bpy.context.active_object
    template_floor.name = "TT_FLOOR"
    template_floor.is_shadow_catcher = True

# ⭐ PODLAHA JAKO OBRYSOVA LINKA (Robert 2026-09-11, pres bot3, po
# zjednoduseni "cely interier" napadu): "nejaky náznak karoserie a
# podlahu, podlahu muzeme udelat jako vyřez z karoserie, obrysová
# linka". Na rozdil od KAROSERIE (nize, kamera ji NEVIDI, jen odrazy) je
# tenhle plosny obrys VIDITELNY - ma se ukazat, ne jen odrazet ("chce
# vidět náznak vozu a podlahu... ukaz to v renderu"). Data (X/Z body
# konvexniho obalu vodorovneho rezu karoserie) pocita scripts/2026-09-09_
# turntable_job.py::resolve_podlaha_obrys() - PROTOTYP jen pro K-075
# (Fiat Doblo), Robert vyslovne "zadny katalog, jedna karoserie".
#
# +1mm nad TT_FLOOR (shadow catcher vyse sedi na stejne Y jako karoserie
# Y=0, tenhle obrys by se s nim jinak z-fightoval) - viditelny detail
# NAD genererickou podlahou, ne misto ni.
_podlaha_data = JOB.get("podlaha_obrys") or {}
_podlaha_zapnuta = bool(JOB.get("karoserie_podlaha")) and bool(_podlaha_data.get("ok"))
_podlaha_obj = None
if _podlaha_zapnuta:
    try:
        import bmesh
        _pts_xz = _podlaha_data.get("points_xz") or []
        if len(_pts_xz) < 3:
            raise ValueError("min 3 body potreba, mam %d" % len(_pts_xz))
        _bm = bmesh.new()
        _verts = [_bm.verts.new(_to_blender_point([x, 1.0, z])) for x, z in _pts_xz]
        # convexHull() v Node nastroji vraci body CCW v (X,Z) jako "plocha
        # matematika" - vlozeno do 3D s Y=nahoru to dava normalu MIRICI
        # DOLU (overeno vypoctem), proto se poradi tady obraci, aby
        # podlaha byla videt SHORA (kamera se diva dolu).
        _bm.faces.new(list(reversed(_verts)))
        _mesh = bpy.data.meshes.new("TT_PODLAHA_OBRYS")
        _bm.to_mesh(_mesh)
        _bm.free()
        _podlaha_obj = bpy.data.objects.new("TT_PODLAHA_OBRYS", _mesh)
        sc.collection.objects.link(_podlaha_obj)
        for poly in _mesh.polygons:
            poly.use_smooth = False
        _podlaha_mat = bpy.data.materials.new("TT_PODLAHA_MAT")
        _podlaha_mat.use_nodes = True
        _pb = _podlaha_mat.node_tree.nodes.get("Principled BSDF")
        if _pb:
            # Matny - "podlaha dodávky je překližka nebo plech s
            # protiskluzem, ne zrcadlo" (Robert).
            _pb.inputs["Base Color"].default_value = (0.32, 0.29, 0.26, 1.0)
            _pb.inputs["Metallic"].default_value = 0.0
            _pb.inputs["Roughness"].default_value = 0.85
        _podlaha_obj.data.materials.append(_podlaha_mat)
        print("PODLAHA OBRYS: zapnuta - %d bodu, K-075 prototyp." % len(_pts_xz))
    except Exception as _e:
        print("PODLAHA OBRYS: neocekavana chyba (%s), pokracuji BEZ ni." % _e)
        _podlaha_obj = None
        _podlaha_zapnuta = False
elif JOB.get("karoserie_podlaha") and not _podlaha_data.get("ok"):
    print("PODLAHA OBRYS: JOB['karoserie_podlaha'] zadano, ale data pro tuhle "
          "sestavu NEJSOU K DISPOZICI (%s) - FALLBACK bez ni."
          % _podlaha_data.get("reason", "neznamy duvod"))
else:
    print("PODLAHA OBRYS: JOB['karoserie_podlaha'] nezadano, vypnuto (vychozi stav)")

# ⭐ PAST c. 4 (nalezeno 2026-09-11, davka 334, elevace -40) - oprava NIZE
# v hlavni smycce renderu (_nastav_viditelnost_podlahy), NE tady: tady jeste
# neexistuje zadne konkretni `el`, tenhle blok bezi JEDNOU pred smyckou pres
# vsechny elevace. Duvod a mereni viz komentar u _nastav_viditelnost_podlahy.

# --------------------------------------------------------------- svetlo
if not has_template_light and not JOB.get("svetla"):
    # Fallback osvetleni odpovidajici render passu prohlizece
    # (scene.html TT_KEY_DIR / TT_LIGHTS) - jen kdyz sablona zadne nema.
    kd = JOB["key_dir"]
    key = bpy.data.lights.new("TT_KEY", type="SUN")
    key.energy = 3.0
    key.angle = math.radians(3.0)
    key_obj = bpy.data.objects.new("TT_KEY", key)
    sc.collection.objects.link(key_obj)
    key_dir_b = (C @ Vector((kd[0], kd[1], kd[2]))).normalized()
    key_obj.rotation_euler = (-key_dir_b).to_track_quat("-Z", "Y").to_euler()
    print("SVETLO: sablona zadne nemela, pouzito vestavene (SUN podle TT_KEY_DIR)")

# jen_hdri (2026-09-20, Robert: "odstranit svetla, staci hdri", vanDrawee) -
# AZ TADY, PO fallback bloku vyse, aby se odstranilo VSECHNO (sablonova i
# pripadne prave pridane vestavene) - osvetleni pak jde vyhradne z World/HDRI.
# Netyka se karoserie/normalni katalogove rendery (opt-in flag, vychozi
# chovani beze zmeny).
if JOB.get("jen_hdri"):
    odstraneno = 0
    for o in list(sc.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
            odstraneno += 1
    print("JEN_HDRI: odstraneno %d svetel, osvetleni vyhradne z World/HDRI" % odstraneno)

# hdri_sila (2026-09-20, Robert: "porad prilis svetla") - jednorazovy
# nasobek World Background Strength teto davky, nemeni sablonu na disku.
if JOB.get("hdri_sila") is not None and sc.world is not None and sc.world.use_nodes:
    bg = sc.world.node_tree.nodes.get("Background")
    if bg is not None:
        puvodni = bg.inputs["Strength"].default_value
        bg.inputs["Strength"].default_value = puvodni * float(JOB["hdri_sila"])
        print("HDRI_SILA: Background Strength %.3f -> %.3f (nasobek %.3f)"
              % (puvodni, bg.inputs["Strength"].default_value, JOB["hdri_sila"]))
    else:
        print("HDRI_SILA: sablona nema uzel 'Background' ve World - ignorovano")

# hdri_azimut_pomer (opt-in, VYCHOZI 0.0 = beze zmeny): Robert 2026-09-27
# "HDRI tocime lehce mensim krokem jako azimuty" - HDRI prostredi se otaci
# SPOLU S KAMEROU po jednotlivych snimcich otocky (ne jednou staticky pro
# celou davku jako driv, viz priprav_sablonu.py), ale o mensi uhel nez
# kamera - pomer 1.0 by znamenal stejny krok jako kamera (HDRI by se
# vzhledem ke kamere vubec nehybalo), pomer 0.0 = HDRI staticke (dnesni
# chovani). Zaklad = uhel, ktery uz sablona ma (priprav_sablonu.py), a
# PREDNI azimut sestavy (JOB["front_azimuth_deg"]) - pri prednim pohledu
# se tedy nic nemeni, jen na ostatnich snimcich se HDRI pootoci o
# hdri_azimut_pomer * (az - predni_azimut) stupnu. Aktualizuje se v
# _place_camera (viz nize), stejny hook jako u kliceho svetla.
HDRI_AZIMUT_POMER = float(JOB.get("hdri_azimut_pomer") or 0.0)
_hdri_mapping_uzel = None
_hdri_zakladni_rotace_z = 0.0
FRONT_AZIMUTH_DEG = float(JOB.get("front_azimuth_deg") or 0.0)
if HDRI_AZIMUT_POMER != 0.0 and sc.world is not None and sc.world.use_nodes:
    _bg = sc.world.node_tree.nodes.get("Background")
    if _bg is not None and _bg.inputs["Color"].links:
        _uzel = _bg.inputs["Color"].links[0].from_node
        _navstiveno = set()
        while _uzel is not None and _uzel.name not in _navstiveno:
            _navstiveno.add(_uzel.name)
            if _uzel.bl_idname == "ShaderNodeMapping":
                _hdri_mapping_uzel = _uzel
                break
            _dalsi = None
            for _sock in _uzel.inputs:
                if _sock.links:
                    _dalsi = _sock.links[0].from_node
                    break
            _uzel = _dalsi
    if _hdri_mapping_uzel is not None:
        _hdri_zakladni_rotace_z = _hdri_mapping_uzel.inputs["Rotation"].default_value[2]
        print("HDRI AZIMUT POMER: %.2f, zakladni rotace %.1f st., predni azimut %.0f st."
              % (HDRI_AZIMUT_POMER, math.degrees(_hdri_zakladni_rotace_z), FRONT_AZIMUTH_DEG))
    else:
        print("HDRI AZIMUT POMER: zadan, ale Mapping uzel HDRI se nenasel - ignorovano")

# ⭐ ODRAZNA DESKA (Robert 2026-09-11, pres bot3, DRUHE KOLO po prvnim
# testu): "nad regál umístíme vodorovně jakoby ocelový různě zvlněný plech
# který bude mít povrch velmi hladký a bude odrážet svetlo na naše regály".
#
# PRVNI VERZE (vodorovna, pevna, bez vlastniho svitu) skoro nic neudelala -
# bot3 zmereno primo v renderu: "jen mirne projasneni hornich vodorovnych
# profilu... na svislych nohach, na euroboxech ani na razitkach se
# nezmenilo nic". Duvod: vodorovna plocha nad sestavou zrcadli jen do
# ploch mirenych VZHURU - svisla noha odrazi to, co je PRED ni, ne nad ni.
# Fotoatelierovy odrazovy stit se proto nedava vodorovne, ale SIKMO NAD
# predmet, na stranu kamery, sklonem dolu k regalu.
#
# ⭐⭐ DESKA MUSI ROTOVAT S KAMEROU (bot3: "nejdulezitejsi vec z cele teto
# zpravy") - otocny nahled jezdi po prstenci; kdyby deska zustala na
# jednom miste, mela by odlesk jen na casti snimku otocky a jinde ne -
# viditelne poskakovani pri prehravani. Proto se POZICE/ROTACE deska
# NEPOCITA TADY (jednou pred smyckou), ale v `_umisti_odraznou_desku()`
# nize, volane KAZDY snimek se stejnym azimutem jako kamera (presne stejny
# vzor jako u _nastav_viditelnost_podlahy - jedna funkce, volana v obou
# smyckach s aktualnim uhlem).
#
# ZAMERNE VYPNUTO VE VYCHOZIM STAVU (JOB["odrazna_deska"] musi byt
# truthy) - je to POKUS, ne trvala zmena vzhledu. Tri dalsi parametry
# (sklon, vzdalenost, sila vlastniho svitu) jsou CISLA v JOB, ne
# konstanty v kodu - presne to bude Robert ladit.
#
# Neviditelna pro kameru (_nastav_viditelnost_podlahy - stejny mechanismus,
# cycles_visibility.camera), NAVIC nesmi vrhat stin (cycles_visibility.
# shadow=False). World/HDRI (canary_wharf) se NEDOTYKA - deska SVITI
# VLASTNIM emisnim vykonem (Principled BSDF Emission Strength), aby mela
# co odrazet ("Zrcadlo odráží jen to, co na něj dopadne... dnes na ni
# svítí jen prostředí" - bot3), ale sila je parametr prave proto, aby
# slo doladit tak, aby HDRI nepresvitila, jen ho doplnila.
_deska_zapnuta = bool(JOB.get("odrazna_deska"))
_deska_sklon_el_deg = float(JOB.get("odrazna_deska_sklon_el", 55.0))
_deska_vzdalenost_mm = MAX_DIM * float(JOB.get("odrazna_deska_vzdalenost_faktor", 1.3))
_deska_svit = float(JOB.get("odrazna_deska_svit", 3.0))
_deska_obj = None
_deska_bsdf = None
if _deska_zapnuta:
    _deska_size = MAX_DIM * 1.6
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=48, y_subdivisions=48,
        size=_deska_size, location=_to_blender_point(BOX_CENTER),
    )
    _deska_obj = bpy.context.active_object
    _deska_obj.name = "TT_ODRAZNA_DESKA"
    # Pocatecni rotace neni dulezita - _umisti_odraznou_desku() ji nastavi
    # pred KAZDYM snimkem podle aktualniho azimutu kamery (viz nize).

    _deska_mat = bpy.data.materials.new("TT_ODRAZNA_DESKA_MAT")
    _deska_mat.use_nodes = True
    _deska_bsdf = _deska_mat.node_tree.nodes.get("Principled BSDF")
    if _deska_bsdf:
        _deska_bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
        _deska_bsdf.inputs["Metallic"].default_value = 1.0
        _deska_bsdf.inputs["Roughness"].default_value = 0.04
        # Vlastni svit - "ať sama svítí... bude se chovat jako měkký
        # reflektor" (bot3). Principled BSDF ma Emission Color/Strength
        # vestavene (Blender 4.x+), zadny samostatny Emission uzel treba.
        if "Emission Color" in _deska_bsdf.inputs:
            _deska_bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        if "Emission Strength" in _deska_bsdf.inputs:
            _deska_bsdf.inputs["Emission Strength"].default_value = _deska_svit
    _deska_obj.data.materials.append(_deska_mat)

    # Jemne, nizkofrekvencni zvlneni - beze zmeny z prvniho kola (bot3:
    # "nemáme zatím důkaz, že je špatně, jen ho nebylo na čem vidět").
    _deska_disp_tex = bpy.data.textures.new("TT_ODRAZNA_DESKA_NOISE", type="CLOUDS")
    _deska_disp_tex.noise_scale = MAX_DIM * 0.6
    _deska_disp_tex.noise_depth = 1
    _deska_mod = _deska_obj.modifiers.new("TT_zvlneni", type="DISPLACE")
    _deska_mod.texture = _deska_disp_tex
    _deska_mod.strength = MAX_DIM * 0.03
    _deska_mod.mid_level = 0.5

    try:
        _deska_obj.cycles_visibility.camera = False
        _deska_obj.cycles_visibility.shadow = False
    except AttributeError:
        try:
            _deska_obj.visible_camera = False
            _deska_obj.visible_shadow = False
        except AttributeError:
            pass
    print("ODRAZNA DESKA: zapnuta (pokus, 2. kolo) - sklon_el=%.1f° vzdalenost=%.0fmm svit=%.1f"
          % (_deska_sklon_el_deg, _deska_vzdalenost_mm, _deska_svit))
else:
    print("ODRAZNA DESKA: JOB['odrazna_deska'] nezadano, vypnuta (vychozi stav)")


def _umisti_odraznou_desku(az_deg):
    """Prepocita pozici/rotaci desky pro AKTUALNI azimut kamery - musi se
    volat kazdy snimek (viz komentar u vzniku desky vyse). Deska sedi ve
    stejnem azimutu jako kamera (tedy na jeji strane), nad sestavou, ve
    sklonu `_deska_sklon_el_deg` (55° = vysoko, ale ne primo nad hlavou -
    fotoatelierovy uhel "shora napred"), a jeji normala (lokalni +Z, grid
    lezi vodorovne) miri na BOX_CENTER - presne stejna "to_track_quat"
    technika jako u kamery v _place_camera, jen s +Z misto -Z (kamera se
    diva po sve -Z, plocha "sviti"/odrazi po sve +Z)."""
    if not _deska_zapnuta or _deska_obj is None:
        return
    pos_tri = BOX_CENTER + _cam_dir(_deska_sklon_el_deg, az_deg) * _deska_vzdalenost_mm
    _deska_obj.location = _to_blender_point(pos_tri)
    tgt_b = _to_blender_point(BOX_CENTER)
    _deska_obj.rotation_euler = (tgt_b - _deska_obj.location).to_track_quat("Z", "Y").to_euler()


def _hex_linear(h):
    """#RRGGBB (sRGB) -> linearni RGBA pro shader."""
    h = (h or "#000000").lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (lin[0], lin[1], lin[2], 1.0)


def _bg_linear():
    """JOB["bg_color"] (#RRGGBB, sRGB) -> linearni RGBA pro shader."""
    return _hex_linear(JOB["bg_color"])


def _pozadi_node(nt):
    """Background uzel s pozadim, ktere vidi kamera.

    Robert 2026-09-10: "pozadi renderu chci prechod z sede do cerne smerem
    dolu". Kdyz uloha nese `bg_color_bottom`, postavi se svisly prechod;
    jinak zustava ploche `bg_color` jako driv.

    Gradient je SCREEN-SPACE (Texture Coordinate -> Window), ne smerovy.
    Prstence se renderuji ve trech elevacich a smerovy gradient by se mezi
    nimi posouval - v ramu obrazu ma vypadat pokazde stejne.
    """
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    spodni = JOB.get("bg_color_bottom")
    if not spodni:
        bg.inputs["Color"].default_value = _bg_linear()
        return bg, None

    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(sep.inputs[0], tc.outputs["Window"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    # Window: Y=0 dole, Y=1 nahore -> dolni zarazka je ta cerna.
    #
    # Robert, sestym upresnenim na tohle misto (predchozi kola v git
    # historii teto funkce - a3dd48e6/2128cd4c/e93357e7/d3f1fdb9/49b91e18) -
    # tentokrat podle referencniho obrazku (cisty gradient bez sestavy),
    # ktery potvrdil "toto chceme": svetla plocha nahore (0-15 % vysky
    # skoro beze zmeny), plynule tmavnouci stred (15-70 %), blizko cerne
    # (70-85 %), solidni plocha cerna dole (85-100 %).
    #
    # EASE (viz uz overeno v 2128cd4c) + zastavka posunuta z 0.2 na 0.15:
    # EASE ma nulovou derivaci na OBOU koncich sveho rozsahu, tedy
    # "pomaly start" nahore (blizko horni zastavky Y=1.0) STEJNE jako
    # hladke zploststeni dole (blizko dolni zastavky Y=0.15, pred
    # clampnutim na plnou cernou pod ni) - presne dva efekty, ktere
    # obrazek ukazuje soucasne. Overeno primo v Blenderu pred nasazenim
    # (cr.evaluate() na Y=0/0.05/0.1/0.15/0.2/0.3/.../1.0, prevedeno na
    # % vysky snimku odshora): slope v prvnich 15 % vysky citelne mensi
    # nez ve stredu (0.2-0.9 %/% vs 1.6-1.75 %/% v poloviny), 85-100 %
    # presne plocha nula - tvar odpovida popisu.
    ramp.color_ramp.interpolation = 'EASE'
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = _hex_linear(spodni)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = _bg_linear()
    nt.links.new(ramp.inputs["Fac"], sep.outputs["Y"])
    nt.links.new(bg.inputs["Color"], ramp.outputs["Color"])
    return bg, spodni


if not has_template_world:
    world = bpy.data.worlds.new("TT_W")
    sc.world = world
    world.use_nodes = True
    _nt = world.node_tree
    _stary = _nt.nodes.get("Background")
    if _stary:
        _nt.nodes.remove(_stary)
    _bg, _spodni = _pozadi_node(_nt)
    _out = next((n for n in _nt.nodes if n.type == "OUTPUT_WORLD"), None)
    if _out:
        _nt.links.new(_out.inputs["Surface"], _bg.outputs["Background"])
    print("PROSTREDI: sablona zadne nemela, pouzito %s"
          % ("prechod %s -> %s" % (JOB["bg_color"], _spodni) if _spodni
             else "ploche %s" % JOB["bg_color"]))
else:
    # PRAVIDLO 11 (PRODUKTOVE_RENDERY.md, Robert 2026-09-09: "nechceme to
    # samotne pozadi hdri videt, slouzi pouze pro odlesky").
    #
    # Sablona ma vlastni World - typicky s HDRI mapou, kvuli ktere tam je:
    # sviti sestavu a zrcadli se v hliniku. Fotka te mapy ale NESMI byt
    # videt za sestavou; kontrakt otocneho nahledu ma pozadi ploche
    # JOB["bg_color"] (#f2f3f5) a e-shop s nim pocita.
    #
    # Resi se Light Path trikem, ne pruhlednosti: MixShader prepnuty na
    # "Is Camera Ray" posle KAMERE plochou barvu, zatimco odrazy, lomy a
    # osvetleni dal berou puvodni world sablony. Alfa proto neni potreba
    # vubec a snimky mohou zustat JPEG (Robert: "otočný náhled proč nemůže
    # být jpg?" - muze, prave timhle zpusobem).
    #
    # Puvodni zapojeni Worldu se NEROZEBIRA, jen se pred vystup vlozi mix -
    # sablona je Robertuv soubor (pravidlo 2).
    _wnt = sc.world.node_tree
    _wout = next((n for n in _wnt.nodes if n.type == "OUTPUT_WORLD"), None)
    _puvodni = (_wout.inputs["Surface"].links[0].from_socket
                if _wout and _wout.inputs["Surface"].links else None)
    if _puvodni is None:
        print("PROSTREDI: sablona ma World bez zapojeneho vystupu - "
              "pozadi necham, jak je (neni co skryvat pred kamerou)")
    else:
        _plain, _spodni = _pozadi_node(_wnt)
        _lp = _wnt.nodes.new("ShaderNodeLightPath")
        _mix = _wnt.nodes.new("ShaderNodeMixShader")
        # Fac=0 -> vstup 1 (puvodni world: odrazy a osvetleni),
        # Fac=1 -> vstup 2 (plocha barva pro kameru).
        _wnt.links.new(_mix.inputs[0], _lp.outputs["Is Camera Ray"])
        _wnt.links.new(_mix.inputs[1], _puvodni)
        _wnt.links.new(_mix.inputs[2], _plain.outputs["Background"])
        _wnt.links.new(_wout.inputs["Surface"], _mix.outputs["Shader"])
        # Robert mel v X30-1 vypnutou World > Ray Visibility > Camera
        # ("cerne je ok protoze je vypnute hdri pro obraz, jen pro odraz").
        # Zamer je spravny, ale TENHLE prepinac ho plni spatne: kamerovy
        # paprsek world shader vubec nevyhodnoti, takze pozadi vyjde PLOSNE
        # CERNE - a spolu s nim zmizi i pozadovany gradient ("chci gradient
        # v pozadi", "preferujeme gradient seda az cerna"), protoze Light
        # Path trik vyse se ke slovu nedostane. Trik skryva HDRI pred
        # kamerou sam a lepe: umi pozadi obarvit, ne jen zhasnout. Proto se
        # viditelnost v NACTENE KOPII zase zapina; Robertuv soubor na
        # Sdilenem disku to nemeni (mereno 2026-09-10: s camera=False vysly
        # vsechny tri kontrolni pixely 0.0, se zapnutou 0.18/0.64/0.75).
        _vis_ok = False
        try:
            sc.world.cycles_visibility.camera = True
            _vis_ok = True
        except AttributeError:
            try:
                sc.world.visible_camera = True
                _vis_ok = True
            except AttributeError:
                pass
        if _vis_ok:
            print("PROSTREDI: World > Ray Visibility > Camera zapnuto v nactene "
                  "kopii (jinak by pozadi vyslo plosne cerne misto gradientu)")
        print("PROSTREDI: world ze sablony (odrazy/osvetleni), kamera vidi %s"
              " - pravidlo 11"
              % ("prechod %s -> %s" % (JOB["bg_color"], _spodni) if _spodni
                 else "ploche %s" % JOB["bg_color"]))

# --------------------------------------------------------------- kamera
cam_data = bpy.data.cameras.new("TT_CAM")
cam_data.sensor_fit = "VERTICAL"   # TT_FOV je SVISLY zorny uhel
cam_data.lens = (cam_data.sensor_height / 2.0) / math.tan(math.radians(FOV) / 2.0)
# past c. 1
cam_data.clip_start = max(0.001, MAX_DIM * 0.001)
cam_data.clip_end = MAX_DIM * 100
cam = bpy.data.objects.new("TT_CAM", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam


# SVETLA Z .BLEND SOUBORU (Robert 2026-09-29: "v renderovaci tabulce chci pridat
# nastaveni svetel, podle nejakeho souboru", X1_SCENA.blend). JOB["svetla"] je
# vysledek extrahuj_svetla.py (poloha/natoceni/vykon/barva/typ kazdeho svetla,
# v metrech souboru). Soubor ma jako "sestavu" 8 koulí o polomeru 1 kolem
# pocatku, proto: 1 jednotka souboru = KEY_R (polomer nasi sestavy), pocatek
# souboru = stred sestavy. Poloha a velikost zdroje se nasobi meritkem s,
# vykon s^2 (stejne ozareni pri jine vzdalenosti - stejna logika jako
# key_svetlo vyse); SUN se neskaluje (vykon je ozareni, ne zdroj v prostoru).
# Svetla se otaceji kolem svisle osy spolu s kamerou (uhel vuci kamere
# souboru zustava) - stejne jako key_svetlo a HDRI, takze kazdy snimek otocky
# vypada jako pohled z kamery X1 sceny. Sablonova svetla (v metrech, v mm
# scene bez ucinku) se odstrani - svetla ze souboru jsou JEDINA svetla.
_svetla_objs = []
_svetla_ref_az = None
_SV = JOB.get("svetla")
if _SV and _SV.get("svetla"):
    _sv_s = (MAX_DIM / 2.0) * float(JOB.get("svetla_meritko") if JOB.get("svetla_meritko") is not None else 1.0)
    _sv_sila = float(JOB.get("svetla_sila") if JOB.get("svetla_sila") is not None else 1.0)
    _odstr = 0
    for _o in list(sc.objects):
        if _o.type == "LIGHT":
            bpy.data.objects.remove(_o, do_unlink=True)
            _odstr += 1
    if _SV.get("kamera_azimut_deg") is not None:
        _svetla_ref_az = math.radians(float(_SV["kamera_azimut_deg"]))
    for _d in _SV["svetla"]:
        _typ = _d["typ"]
        _ld = bpy.data.lights.new("TT_SV_" + _d["jmeno"], type=_typ)
        _ld.color = _d["barva"]
        _ld.energy = _d["vykon"] * _sv_sila * (1.0 if _typ == "SUN" else _sv_s * _sv_s)
        _ld.diffuse_factor = _d.get("diffuse", 1.0)
        _ld.specular_factor = _d.get("specular", 1.0)
        _ld.use_shadow = bool(_d.get("stiny", True))
        if _d.get("teplota") is not None:
            _ld.use_temperature = True
            _ld.temperature = _d["teplota"]
        _zdroj = _d.get("meritko", 1.0) * _sv_s
        if _typ in ("POINT", "SPOT"):
            _ld.shadow_soft_size = _d.get("polomer", 0.0) * _zdroj
        if _typ == "SPOT":
            _ld.spot_size = _d["spot_uhel"]
            _ld.spot_blend = _d["spot_blend"]
        if _typ == "AREA":
            _ld.shape = _d["tvar"]
            _ld.size = _d["velikost"] * _zdroj
            _ld.size_y = _d["velikost_y"] * _zdroj
        if _typ == "SUN":
            _ld.angle = _d["uhel"]
        _lo = bpy.data.objects.new("TT_SV_" + _d["jmeno"], _ld)
        sc.collection.objects.link(_lo)
        _svetla_objs.append((_lo, Vector(_d["poloha"]) * _sv_s, Matrix(_d["rot"])))
    print("SVETLA ZE SOUBORU %s: %d svetel (sablonovych odstraneno %d), meritko %.1f mm/jednotku, "
          "nasobek vykonu %.2f, otaceji se s kamerou (kamera souboru %s st.)"
          % (JOB.get("svetla_soubor", "?"), len(_svetla_objs), _odstr, _sv_s, _sv_sila,
             "?" if _svetla_ref_az is None else "%.0f" % math.degrees(_svetla_ref_az)))
    for _d in _SV["svetla"]:
        print("  SVETLO %s: %s, vykon soubor %.4g W, barva (%.2f, %.2f, %.2f)%s"
              % (_d["jmeno"], _d["typ"], _d["vykon"], _d["barva"][0], _d["barva"][1], _d["barva"][2],
                 "  POZOR: slozity uzel svetla, vykon/barva nemusi sedet" if _d.get("uzly") == "slozite" else ""))
    for _p in _SV.get("preskoceno") or []:
        print("  SVETLO %s: PRESKOCENO (%s)" % (_p["jmeno"], _p["duvod"]))
    if _SV.get("kamera_azimut_deg") is None:
        print("  POZOR: soubor nema kameru - svetla se neotaceji s kamerou")


# KLICOVE BODOVE SVETLO (opt-in, VYCHOZI VYPNUTO; Robert 2026-09-26, hlinik
# "malo kovovy"): v Robertove zkusebni scene (koule s materialem) svieti
# bodove svetlo 1000 W, polomer 0.1, ~7.2x polomer koule daleko, 57 st.
# vedle kamery a 55 st. nad cilem - to dela ostry jasny odlesk na kovu. V
# nasem renderu zadne takove svetlo neni (sablonove 'Bod' 10 W je v metrech
# a v mm scene je u pocatku bez ucinku). key_svetlo = nasobek vykonu
# (1.0 = ekvivalent Robertovy scene). Geometrie i vykon se skaluji podle
# velikosti sestavy: stejna ozarenost pri polomeru R => vykon ~ R^2.
KEY_SVETLO = float(JOB.get("key_svetlo") or 0.0)
# key_svetlo_polomer (opt-in, VYCHOZI 1.0 = beze zmeny): nasobek velikosti
# svetelneho zdroje. Mensi cislo = ostrejsi, mensi jasna skvrna (vyssi
# kontrast lokalne, mensi dopad na celkovy jas snimku); vetsi = mekci,
# rozlity odlesk. Energie (vykon) se timhle NEMENI, jen jak je "rozetreny".
KEY_SVETLO_POLOMER = float(JOB.get("key_svetlo_polomer") or 1.0)
# key_svetlo_elevace/key_svetlo_azimut_posun (opt-in, VYCHOZI 55.0/-57.0 =
# puvodni hodnoty beze zmeny): uhel svetla vuci kamere. Robert 2026-09-27:
# "bila deska a bile drazky nejsou akceptovatelne" - puvodni elevace 55 st.
# (skoro shora) sviti primo na VODOROVNE plochy (desky, drazky) a prepaluje
# je; nizsi elevace sviti vic ZE STRANY na SVISLE plochy (predni steny
# profilu), ktere maji vypadat kovove, a min na vodorovne.
KEY_SVETLO_ELEVACE = float(JOB.get("key_svetlo_elevace") if JOB.get("key_svetlo_elevace") is not None else 55.0)
KEY_SVETLO_AZ_POSUN = float(JOB.get("key_svetlo_azimut_posun") if JOB.get("key_svetlo_azimut_posun") is not None else -57.0)
_key_svetlo_obj = None
KEY_R = MAX_DIM / 2.0
if KEY_SVETLO > 0.0:
    _ld = bpy.data.lights.new("TT_KEY_BOD", type="POINT")
    _ld.energy = 1000.0 * KEY_SVETLO * (KEY_R * KEY_R)
    _ld.shadow_soft_size = 0.1 * KEY_R * KEY_SVETLO_POLOMER
    _key_svetlo_obj = bpy.data.objects.new("TT_KEY_BOD", _ld)
    sc.collection.objects.link(_key_svetlo_obj)
    print("KEY SVETLO: bodove, vykon %.3g W (nasobek %.2f), polomer sestavy %.1f, vzdalenost %.1f, velikost x%.2f" %
          (_ld.energy, KEY_SVETLO, KEY_R, 7.2 * KEY_R, KEY_SVETLO_POLOMER))
    # Omezit svetlo JEN na hlinikove dily (Blender "Light Linking", Robert
    # 2026-09-27: "bila deska a bile drazky nejsou akceptovatelne" - stejne
    # svetlo, ktere dela hezky odlesk na hliniku, prepaluje desky/boxy z
    # jinych materialu. receiver_collection na svetle omezi, KTERE objekty
    # tohle svetlo osvetluje - ostatni dal sviti jen sablonovy svet/HDRI,
    # beze zmeny. VYCHOZI (bez omezeni) = svetlo sviti na vsechno jako
    # driv - key_svetlo_jen_alu musi byt vyslovne zapnuty (JOB flag), radeji
    # nove chovani neprepisovat automaticky pod stejnym prepinacem.
    if JOB.get("key_svetlo_jen_alu") and TEMPLATE_MATS.get("alu") is not None:
        _alu_jmeno = TEMPLATE_MATS["alu"].name
        _alu_prijem = bpy.data.collections.new("TT_ALU_PRIJEM")
        _n_prijem = 0
        for _o in imported:
            if _o.type == "MESH" and any(s.material is not None and s.material.name.startswith(_alu_jmeno)
                                         for s in _o.material_slots):
                _alu_prijem.objects.link(_o)
                _n_prijem += 1
        if _n_prijem > 0:
            _key_svetlo_obj.light_linking.receiver_collection = _alu_prijem
            print("KEY SVETLO: omezeno jen na hlinik (%d dilu), ostatni (desky/boxy) tímhle svetlem nesviceny" % _n_prijem)
        else:
            print("KEY SVETLO: key_svetlo_jen_alu zadano, ale 0 hlinikovych dilu nalezeno - svetlo sviti na vsechno")


# PLOSNA SVETLA V NAHODNEM SMERU (opt-in, VYCHOZI VYPNUTO; Robert
# 2026-09-26: "dej do sceny 2 plosna svetla v nahodilem smeru, spise slabsi
# sila"). plosna_svetla = pocet (napr. 2), plosna_sila = nasobek (vychozi
# 0.3 = slabsi; 1.0 ~ ekvivalent bodoveho svetla z Robertovy zkusebni
# sceny), plosna_seed = seminko nahody (vychozi 7, at je render
# opakovatelny). Smer je NAHODNY (elevace 25-70 st., azimut 0-360 st.) a
# PEVNY VE SVETE - u otocky se pri obehu kamery osvetleni prirozene meni.
# Svetla miri na stred sestavy, vykon se skaluje s R^2 stejne jako u
# key_svetlo (mm scena).
PLOSNA_N = int(JOB.get("plosna_svetla") or 0)
if PLOSNA_N > 0:
    import random as _rnd_mod
    _rnd = _rnd_mod.Random(int(JOB.get("plosna_seed") or 7))
    _psila = float(JOB.get("plosna_sila") or 0.3)
    _pD = 4.0 * KEY_R
    for _i in range(PLOSNA_N):
        _pel = _rnd.uniform(25.0, 70.0)
        _paz = _rnd.uniform(0.0, 360.0)
        _pl = bpy.data.lights.new("TT_PLOSNE_%d" % _i, type="AREA")
        _pl.shape = "SQUARE"
        _pl.size = KEY_R
        _pl.energy = _psila * 1000.0 * (_pD * _pD) / 51.84
        _po = bpy.data.objects.new("TT_PLOSNE_%d" % _i, _pl)
        sc.collection.objects.link(_po)
        _po.location = _to_blender_point(BOX_CENTER + _cam_dir(_pel, _paz) * _pD)
        _po.rotation_euler = (_to_blender_point(BOX_CENTER) - _po.location).to_track_quat("-Z", "Y").to_euler()
        print("PLOSNE SVETLO %d: elevace %.0f st., azimut %.0f st., vykon %.3g W (nasobek %.2f), velikost %.0f, vzdalenost %.0f"
              % (_i, _pel, _paz, _pl.energy, _psila, _pl.size, _pD))


def _place_camera(target_three, distance, el_deg, az_deg):
    pos_three = target_three + _cam_dir(el_deg, az_deg) * distance
    cam.location = _to_blender_point(pos_three)
    tgt_b = _to_blender_point(target_three)
    cam.rotation_euler = (tgt_b - cam.location).to_track_quat("-Z", "Y").to_euler()
    if _svetla_objs:
        _dv = cam.location - tgt_b
        _daz = (math.atan2(_dv.y, _dv.x) - _svetla_ref_az) if _svetla_ref_az is not None else 0.0
        _Rz = Matrix.Rotation(_daz, 3, "Z")
        for _lo, _lp0, _lr0 in _svetla_objs:
            _lo.rotation_euler = (_Rz @ _lr0).to_euler()
            _lo.location = tgt_b + _Rz @ _lp0
    if _key_svetlo_obj is not None:
        _lp = target_three + _cam_dir(KEY_SVETLO_ELEVACE, az_deg + KEY_SVETLO_AZ_POSUN) * (7.2 * KEY_R)
        _key_svetlo_obj.location = _to_blender_point(_lp)
    if _hdri_mapping_uzel is not None:
        # zabaleny rozdil na (-180, 180] - prosty rozdil by pro azimuty
        # "za rohem" 0/360 (napr. front=270, az=0 je ve skutecnosti +90,
        # ne -270) dal spatny smer i velikost otoceni.
        _delta_az = ((az_deg - FRONT_AZIMUTH_DEG + 180.0) % 360.0) - 180.0
        _hdri_mapping_uzel.inputs["Rotation"].default_value[2] = (
            _hdri_zakladni_rotace_z + math.radians(_delta_az * HDRI_AZIMUT_POMER))


# ⭐ PAST c. 4 (nalezeno 2026-09-11, davka 334, elevace -40): shadow catcher
# je neviditelny jen ze strany, na kterou by normalne padal stin (shora/ze
# strany) - z podhledu ho nic neosvetluje, vykresli se proto ciste barvou
# pozadi, ALE PORAD FYZICKY BLOKUJE KAMERE VYHLED za sebe. Pro zaporne
# elevace (kamera POD podlahou, divajici se vzhuru) tenhle disk sedel presne
# v ceste paprsku ke spodku sestavy - ostry vodorovny rez + dily cnici ven
# z disku vypadaly jako "odtrzene", protoze diskem blokovane nebyly.
#
# Zmereno (bot4, davka 334): pro VSECH 27 azimutu elevace -40 prochazi
# paprsek kamera->cil rovinou podlahy 727,9 mm od jejiho stredu - hluboko
# uvnitr 902mm disku, ne na jeho okraji. Nezavisly raytracer nad stejnou
# GLB geometrii BEZ podlahy vratil cistou sestavu bez naklonu a bez
# odtrzenych dilu - vada je v render pipeline, ne v datech sestavy.
#
# OPRAVA JE FYZIKALNI, NE KOSMETICKA: pri pohledu zdola vzhuru neni co
# simulovat - nikdo v realne fotce z podhledu nevidi zem, divá se do nebe.
# Podlaha tam proto nema co delat. Skryva se JEN kamere a JEN pro tenhle
# jeden snimek (volat KAZDY snimek, ne jednou pred smyckou!) - pro elevace
# >=0 (divak se divá shora/ze strany, stin davá smysl) zustava viditelna,
# presne jako driv.
#
# NEDOTYKAT SE u opravy: BOX_CENTER/ring_distance/kamerova matematika (bot4
# je overil bit presne, problem tam neni), film_transparent (Robertuv
# prechod seda->cerna pozadi), ani Robertova sablona (chybejici TT_FLOOR se
# DOPLNUJE tady v kodu, ne v .blend souboru - ten je jeho a bez svoleni se
# nemeni). Schvaleno Robertem pres bot3, 2026-09-11.
def _nastav_viditelnost_podlahy(el_deg):
    # Dve ruzne Blender API na totez podle verze - stejny osetreny vzor
    # jako u sc.world.cycles_visibility/visible_camera vyse (World Sunset,
    # HDRI pred kamerou). `hasattr` samo o sobe nestaci: na novejsim
    # Blenderu `cycles_visibility` na Objektu vubec neexistuje, spravna
    # cesta je primo `template_floor.visible_camera`.
    vidi = el_deg >= 0
    try:
        template_floor.cycles_visibility.camera = vidi
    except AttributeError:
        try:
            template_floor.visible_camera = vidi
        except AttributeError:
            pass


# ---------------------------------------------------------------- render
# --- Vypocetni zarizeni (CPU / GPU) -------------------------------------
# Robert 2026-09-09 ("v blenderu je nastaveno cpu to je divne") - a mel
# pravdu: tenhle skript zarizeni NENASTAVOVAL VUBEC, takze prebral CPU
# ze sablony (dilna na VPS zadne GPU nema) a VSECHNY dosavadni rendery
# bezely na PROCESORU jeho GPU stanice, ne na RTX 3060. Odtud casy
# 400-1000 s na jeden snimek.
#
# Backend hlasi agent promennou KONF_GPU_BACKEND (OPTIX / CUDA / HIP /
# ONEAPI). Stejny postup jako blender_render_scene.py - vcetne toho, ze
# se zapina JEN zvoleny backend: kdyz se pusti i CPU nebo se tataz karta
# zapne dvakrat (CUDA + OptiX), Cycles scenu mezi ne rozdeli a render je
# POMALEJSI, ne rychlejsi.
_gpu_backend = (os.environ.get("KONF_GPU_BACKEND") or "NONE").upper()
if _gpu_backend != "NONE":
    _cprefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        _cprefs.compute_device_type = _gpu_backend
    except TypeError:
        print("GPU backend %s neni k dispozici, renderuji na CPU" % _gpu_backend)
    else:
        _cprefs.get_devices()
        _on = [d.name for d in _cprefs.devices if (setattr(d, "use", d.type == _gpu_backend) or d.use)]
        if _on:
            sc.cycles.device = "GPU"
        print("GPU backend %s, zarizeni: %s" % (_gpu_backend, ", ".join(_on) or "zadne"))
else:
    print("KONF_GPU_BACKEND nenastaveno - renderuji na CPU")

sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = int(JOB.get("jpeg_quality", 92))
if not HAS_TEMPLATE:
    # Bez sablony: Cycles s rozumnymi vychozimi hodnotami. SE sablonou se
    # engine NEPREPISUJE - to je prave to, co si Robert nastavuje ve svem
    # .blend. Vzorky jsou od 2026-09-11 vyjimka, viz nize.
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(JOB.get("samples", 128))
    sc.cycles.use_denoising = True
elif sc.render.engine != "CYCLES":
    print("VAROVANI: sablona ma engine %s - shadow catcher podlahy je "
          "vlastnost Cycles a v jinem enginu se vykresli jako obycejna rovina."
          % sc.render.engine)

# Vzorky: VYSLOVNE zadana hodnota prebiji i sablonu (Robert 2026-09-11:
# "vzorky pro render dejme 500"). Duvod je cas, ne vzhled - X30-1 ma 924
# vzorku, coz je pri 360 snimcich na davku radove den na jednu variantu;
# se zapnutym OpenImageDenoise je rozdil proti ~500 opticky zanedbatelny.
# Robertuv .blend se pritom NEMENI - prepis se deje az tady, na kopii
# nactene v pameti. Kdyz uloha vzorky nenese, sablona si sve cislo drzi.
_vzorky = JOB.get("samples")
if HAS_TEMPLATE and _vzorky:
    try:
        _stare = sc.cycles.samples
        sc.cycles.samples = int(_vzorky)
        print("VZORKY: sablona mela %s, uloha rika %s - pouzito %s"
              % (_stare, int(_vzorky), int(_vzorky)))
    except Exception as e:
        print("VZORKY: nelze prepsat (%r), zustava hodnota ze sablony" % e)

# Nastaveni Cycles dle Roberta (opt-in cycles_robert; 2026-09-26, ukazal
# Light Paths ze sveho Blenderu): sablona X30-02 uz nese skoro vse stejne
# (vzorky 555 adaptivne 0.01, odsumeni, Light Tree, odrazy 12/4/-/12/0,
# transparent 8, clamp direct 0, caustics, subdivision). Lisi se JEN glossy
# odrazy (sablona 5, Robert 4) a clamp indirect (sablona 0, Robert 10).
if HAS_TEMPLATE and JOB.get("cycles_robert"):
    _g0, _c0 = sc.cycles.glossy_bounces, sc.cycles.sample_clamp_indirect
    sc.cycles.glossy_bounces = 4
    sc.cycles.sample_clamp_indirect = 10.0
    print("CYCLES (Robert): glossy odrazy %s -> 4, clamp indirect %s -> 10.0" % (_g0, _c0))


def _render_to(path, w, h):
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def _downscale(src, dst, w, h):
    """1024 tier: zmenseni uz vyrenderovaneho 2048 snimku (stejne jako
    prohlizec, ktery tier kresli z masteru - ne druhy render)."""
    img = bpy.data.images.load(src)
    img.scale(w, h)
    img.filepath_raw = dst
    img.file_format = "JPEG"
    img.save()
    bpy.data.images.remove(img)


elevations = JOB["elevations"]
azimuths = JOB["azimuths"]
tiers = {int(k): v for k, v in JOB["tiers"].items()}
master_tier = max(tiers)
mw, mh = tiers[master_tier]
ring_dirs = [(el, az) for el in elevations for az in azimuths]
if ring_dirs:
    ring_distance = tt_compute_distance(mw / mh, float(JOB["margin"]), ring_dirs)
    print("PRSTENCE: jedna vzdalenost %.0f mm pro %d smeru" % (ring_distance, len(ring_dirs)))
else:
    # Robert 2026-09-09 ("chceme ted testovat scenu takze chci jen 1
    # render") - rezim --test posle ulohu bez prstencu, jen s jednim
    # stillem. Vzdalenost prstencu se pak nepocita (nebylo by z ceho,
    # dirs je prazdne) a do manifestu jde 0.
    ring_distance = 0.0
    print("PRSTENCE: zadne (rezim jednoho snimku)")

manifest = {"frames": [], "stills": [], "camera": {
    "fov_deg": FOV, "center": list(BOX_CENTER), "distance": ring_distance,
    "front_azimuth_deg": JOB["front_azimuth_deg"],
    "box_min": list(BOX_MIN), "box_max": list(BOX_MAX), "stills": {},
},
    # Robert 2026-09-11: "upozornit pri zobrazeni ze je to on" - priznak v
    # datech ulohy, ne jen ve zprave/logu, aby bylo pozdeji (i za tyden)
    # poznat, ktery snimek vznikl s pokusnou odraznou deskou a ktery bez ni.
    "odrazna_deska": _deska_zapnuta,
    # Stejny duvod, pro skutecnou karoserii jako odrazovou plochu.
    "karoserie_odrazy": _karoserie_zapnuta,
    "karoserie_odrazy_base": (_karoserie_data.get("k_code") or _karoserie_data.get("base")) if _karoserie_zapnuta else None,
    "karoserie_odrazy_drsnost": _karoserie_drsnost if _karoserie_zapnuta else None,
    # Stejny duvod, pro podlahu jako obrysovou linku (prototyp K-075).
    "karoserie_podlaha": _podlaha_zapnuta,
}

n = 0
total = len(ring_dirs) + len(JOB["stills"])
for el, az in ring_dirs:
    _place_camera(BOX_CENTER, ring_distance, el, az)
    _nastav_viditelnost_podlahy(el)
    _umisti_odraznou_desku(az)
    master = os.path.join(OUT_DIR, "frame_e%02d_a%03d_t%d.jpg" % (el, az, master_tier))
    _render_to(master, mw, mh)
    entry = {"el": el, "az": az, "files": {str(master_tier): os.path.basename(master)}}
    for tier, (tw, th) in tiers.items():
        if tier == master_tier:
            continue
        small = os.path.join(OUT_DIR, "frame_e%02d_a%03d_t%d.jpg" % (el, az, tier))
        _downscale(master, small, tw, th)
        entry["files"][str(tier)] = os.path.basename(small)
    manifest["frames"].append(entry)
    n += 1
    print("SNIMEK %d/%d  e%+d a%03d" % (n, total, el, az), flush=True)
    # Strojove citelny radek pro agenta (Robert pres bot3, 2026-09-11:
    # "musime videt rendery prubezne" / "hotove rendery se musi ukladat na
    # sdileny disk okamzite po vytvoreni") - agent tohle cte ze stdout a
    # posle master snimek na server HNED, ne az na konci cele davky. JSON
    # na JEDNOM radku, aby ho slo parsovat regexem beze slozite logiky.
    print("PREVIEW " + json.dumps({"el": el, "az": az, "tier": master_tier, "path": master}),
         flush=True)

for s in JOB["stills"]:
    target, dist = tt_fit_still(s["el"], s["az"], s["w"] / s["h"], float(JOB["still_margin"]))
    _place_camera(target, dist, s["el"], s["az"])
    _nastav_viditelnost_podlahy(s["el"])
    _umisti_odraznou_desku(s["az"])
    path = os.path.join(OUT_DIR, "still_%s.jpg" % s["key"])
    _render_to(path, s["w"], s["h"])
    manifest["stills"].append({"key": s["key"], "el": s["el"], "az": s["az"],
                               "w": s["w"], "h": s["h"], "file": os.path.basename(path)})
    manifest["camera"]["stills"][s["key"]] = {
        "el": s["el"], "az": s["az"], "distance": dist, "center": list(target)}
    n += 1
    print("SNIMEK %d/%d  still %s" % (n, total, s["key"]), flush=True)

with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, ensure_ascii=False, indent=1)

print("TURNTABLE_OK %s snimku=%d stills=%d" % (OUT_DIR, len(manifest["frames"]), len(manifest["stills"])))
