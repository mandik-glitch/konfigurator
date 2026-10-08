#!/usr/bin/env python3
"""2026-09-23_vandr_razitka_spocitat.py - spocita a zapise 3D razitka
LOGIMAN.CZ pro Vandr/vanDrawee monoliticke importy (Robert 2026-09-23:
"3D razitka dodelat zpetne a dopredu").

⭐ PREPSANO 2026-09-23 (Robert, po mnoha kolech samostatnych oprav: "Upravte
ten generator razítek podle vzoru na větvi jedna, píšu to dnes už po
desáté."): tenhle skript uz NENI sbirka vlastnich heuristik (AABB kolize,
vlastni "kazdy treti", bbox-hack na karoserii) - je to PRIMY PORT
`scripts/razitkovac.py::vyber_profily_k_razitkovani()` +
`orazitkuj()`/`_razitko_pro_profil()` (branch 1), krok za krokem:

  1. Pro KAZDOU ze 4 LOKALNICH sten KAZDEHO kvalifikovaneho profilu
     NEZAVISLE (port KANDIDATNI_STENY_LOK - u Vandr nejde pouzit stejne
     PEVNE svetove smery jako u nativni katalogove 30x30, protoze
     jednotlive Vandr profily nemaji jednotnou lokalni orientaci; misto
     toho ctyri smery = ±(prvni prurezova osa), ±(druha prurezova osa)):
       a) ma podel delky profilu souvisly volny usek na cele logo
          (`_blokovane_useky_vandr`/`razitkovac._volne_useky` - port
          `_blokovane_useky`, jen mista analytickych katalogovych rozmeru
          (ROZMERY_DILU) pouziva SKUTECNOU mesh AABB ostatnich objektu,
          protoze Vandr zadny katalog rozmeru pro monoliticky import
          nema);
       b) je stena EXPONOVANA VEN (`_je_videt_vandr` - port `_je_videt`,
          mista analytickeho box-testu (`_paprsek_protne_kvadr`) pouziva
          SKUTECNY Object.ray_cast proti kazdemu ostatnimu mesh objektu -
          presnejsi nez katalogovy box, a POSTIHUJE i ztraceně
          pojmenovanou karoserii/"SomeName*" objekty automaticky, bez
          potreby zvlastniho jmenoveho/bbox rozpoznavani).
  2. Vyber NENI zavisly na smeru kamery/predni strany - cisté
     geometricke, presne jako branch 1 od 2026-09-11.
  3. Hustota "kazdy N-ty" (`razitkovac.KAZDY_NTY`, sdileno s branch 1) se
     pocita SAMOSTATNE pro kazdou ze 4 stenovych skupin: kandidati se
     seradi podle POZICE VE STRUKTURE, pak kazdy N-ty s POSUNEM
     odvozenym deterministicky ze (jmeno GLB, index steny) pres
     `razitkovac._nahodne_0_1` - ruzne sestavy/strany nezacinaji razitka
     na stejnem miste, vysledek je pri stejnem vstupu vzdy stejny.
  4. Presna pozice v ramci volneho useku + rozestup vice log na TEMZE
     profilu (MIN_ROZESTUP_LOG_MM) - `razitkovac._povolene_useky` prevzato
     PRIMO (cista intervalova matematika, zadna geometrie specificka pro
     data model).

POZOR (Robert at vi, kdyby se zeptal): i tenhle presny algoritmus
NEGARANTUJE razitko na "predni" strane pri pohledu z vychozi kamery - je
to cisté geometricke rozhodnuti, ne view-dependent. Branch 1 tohle
taky negarantuje. Pokud by Robert chtel zarucit "aspon 1 razitko videt z
hlavniho uhlu", je to DALSI pravidlo, ktere nema ani branch 1, a
potrebuje samostatne probrat - ne predpokladat.

POVINNY KROK pro KAZDOU novou Vandr sestavu (shop_products s hotovym
glb_file) - viz VANDR_RENDER_HOWTO.md "Poradi kroku shrnute". Bez tohohle
nema render zadnou ochranu (razitkovac.py na monoliticky import nedosahne,
hleda jen mezi katalogovymi Object_7/8/9 profily).

PROC JEDNORAZOVE MIMO RENDER (ne za behu Blenderu jako
razitkovac.py::orazitkuj): geometrie profilu existuje az po importu GLB,
ale jednou spoctena se NEMENI (pozice v ramci jedne karty jsou fixni) -
proto se spocita JEDNOU tady a zapise jako obycejne dily s
part_id="logo_logiman_cz", presne jako u nativnich Logiman sestav. Render
kod (api/blender_render_turntable.py) se timhle VUBEC nemeni - stamp dily
projdou stejnym _material_for() sklenym materialem jako kazde jine
razitko.

POUZITI (spustit primo blenderem, ne pres python3 - potrebuje bpy):
    /opt/blender-5.2/blender -b -P scripts/2026-09-23_vandr_razitka_spocitat.py \
        -- <glb_soubor> --shop-product-id <id>
    (stary rezim, jen pro 671/672: -- <glb_soubor> --assembly-id <id>)

Idempotentni - stare "logo-ochrana-vandr-*" dily se pred zapisem smazou,
takze opakovane spusteni na tez karte jen prepocita znovu, nezdvojuje.
"""
import sys
import os
import re
import json
import math
import hashlib
import importlib.util

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# Cely geometricky/vyberovy algoritmus PRIMO z razitkovac.py (Robert
# 2026-09-23, durazne, opakovane: "prevezmi generator razitkovani z prvni
# vetve", nakonec "pisu to dnes uz po desate") - vlastni reimplementace
# (nejdriv jen orientace, pak cela kolizni logika) vysla spatne/preplacane
# vickrat, nez se prestalo hadat a zacalo doslovne kopirovat. Zbyva
# vlastni jen to, co razitkovac.py vubec neresi, protoze pracuje s JINYM
# datovym modelem (katalogove "parts" s ulozenymi rozmery z ROZMERY_DILU
# vs. Vandr realna mesh geometrie bez katalogu) - viz CLAUDE.md bod 6
# (vanDrawee/nase logika se nemichaji v JEDNOM SOUBORU - tohle je import
# cisté geometricke matematiky ze sdileneho souboru, ne kopie cizi
# domenove logiky sem).
_rc_spec = importlib.util.spec_from_file_location(
    "razitkovac", os.path.join(REPO, "scripts", "razitkovac.py"))
razitkovac = importlib.util.module_from_spec(_rc_spec)
_rc_spec.loader.exec_module(razitkovac)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
# --dry-run (bot10 2026-09-24): spocitat a vypsat SOUHRN_JSON + razitka, NIC nezapsat
# do DB - pro nahledy navrhu Robertovi bez toho, aby vandr-render-dispatch timer
# (reaguje na zmenu vandr_razitka_json) pustil ostry render neschvaleneho navrhu.
DRY_RUN = "--dry-run" in argv
argv = [a for a in argv if a != "--dry-run"]
# Dva rezimy zapisu (Robert/bot3 2026-09-23: "2. vetev se vepisuje do
# tabulky pro 1. vetev, to nelze" - Vandr karty NEMAJI product_assemblies,
# viz 2026-09-22_vandr_fbx_watcher.py hlavicka). --assembly-id je PUVODNI
# rezim, zachovany JEN pro dve uz existujici testovaci sestavy (671/672,
# vznikly pred timhle pravidlem) - pro KAZDOU dalsi/realnou Vandr kartu
# se pouziva vyhradne --shop-product-id (zapis do shop_products, viz
# scripts/2026-09-23_vandr_razitka_auto_dispatch.py).
GLB_PATH = None
ASSEMBLY_ID = None
SHOP_PRODUCT_ID = None
if len(argv) == 3 and argv[1] == "--assembly-id":
    GLB_PATH, ASSEMBLY_ID = argv[0], int(argv[2])
elif len(argv) == 3 and argv[1] == "--shop-product-id":
    GLB_PATH, SHOP_PRODUCT_ID = argv[0], int(argv[2])
elif len(argv) == 2:
    # Zpetna kompatibilita se stary volanim bez priznaku (assembly-id).
    GLB_PATH, ASSEMBLY_ID = argv[0], int(argv[1])
else:
    raise SystemExit(
        "Pouziti: blender -b -P %s -- <glb_soubor> --shop-product-id <id>\n"
        "     (stary rezim, jen pro 671/672: -- <glb_soubor> --assembly-id <id>)"
        % __file__)

C = Matrix.Rotation(math.radians(90.0), 4, "X")
C_INV = C.inverted()

LOGO_ODSAZENI_PIVOTU_MM = 0.696
# Zmereno raycastem napric sirkou steny (BVH, 2026-09-23) na Ducatu
# (45x45, priruba 22.5mm/dno 7.5mm = hloubka 15mm) i Trafic (40x40,
# priruba 20.0mm/dno 6.668mm = hloubka 13.3mm) - OBA maji uprostred steny
# skutecnou T-drazku SIROKOU PRESNE 10,2mm (Robert 2026-09-23: "na Vandr
# sestavach jsou drazky 10mm", nativni `vypln_drazky_30` ma jinou sirku,
# 8,2mm - nelze prevzit 1:1). Katalogovy dil `vypln_placka` je proto UZKY
# ZAPUSTENY CEP presne do sirky drazky (222.204×16×10mm - vnejsi celo
# licuje s prirubou, cep saha 16mm dovnitr, bezpecne za skutecne dno
# drazky na obou profilech). TOHLE je Vandr-specificka geometrie drazky,
# NENI cast razitkovaciho VYBEROVEHO algoritmu, ktery se odsud portuje -
# zustava vlastni.
VYPLN_DRAZKY_HLOUBKA_MM = 16.0
# ⭐ Ruzne prurezy MAJI ruznou drazku - NEODVOZOVAT vzorcem z rozmeru
# profilu, vzdy zmerit primo (VANDR_RENDER_HOWTO.md bod 4) pred pridanim
# noveho klice sem. Klic = min(prurez) - oba dosavadni Vandr profily jsou
# ctvercove (min==max), kdyby nekdy pribyl obdelnikovy, klic se musi
# predefinovat na dvojici, ne hadat, ktery rozmer je "ten spravny".
#
# 30: bot10 2026-09-25, karta #4586 (VW Transporter T6 L1, VD-f3007b39) -
#     priruba 15,000mm/dno 5,000mm/sirka drazky 8,200mm (metoda overena
#     PRED merenim na Ducatu/Traficu proti tehle tabulce, presna shoda na
#     3 des. mista - viz AGENTS_LOG.md). Existujici vypln_placka NESEDI
#     ani sirkou (10mm > 8,2mm drazka) ani hloubkou (16mm > priruba
#     15mm - spicka by presla stred profilu) - novy dil vypln_placka_30
#     (222.204×11×8.2mm, cfg_dily zapsano 2026-09-25).
# 40/45: bot10 2026-09-23, Trafic/Ducato (viz komentar u
#     VYPLN_DRAZKY_HLOUBKA_MM vyse) - puvodni vypln_placka sedi na oba,
#     ponechano jako sdileny dil (stejna sirka 10,2mm namerena na obou).
VYPLN_PODLE_PRUREZU_MM = {
    30: {"part_id": "vypln_placka_30", "hloubka_mm": 11.0},
    40: {"part_id": "vypln_placka", "hloubka_mm": VYPLN_DRAZKY_HLOUBKA_MM},
    45: {"part_id": "vypln_placka", "hloubka_mm": VYPLN_DRAZKY_HLOUBKA_MM},
}
# ⭐ Robert 2026-09-24 (AskUserQuestion, po zavedeni vyvazenosti svisle/
# vodorovne): na sestavach systemu 40x40 jsou JEDINE vodorovne hlavni profily
# hloubkove pricky ~270 mm; s nativnim okrajem 40 mm (MIN_DELKA 302,2) se na
# ne logo 222,2 mm nevejde a cela sestava vyjde 100 % svisle. Robert zvolil
# "okraj 40 -> 20 mm na 270mm prickach" (pravidlo "jen hlavni profily"
# zustava; alternativy - vedlejsi 20x40/20x80/30x30 profily - odmitl).
# Plati jen pro Vandr export, nativni razitkovac.py (OKRAJ_MM=40) se nemeni.
VANDR_OKRAJ_MM = float(os.environ.get("RAZITKA_OKRAJ_MM", "20"))   # ladeni/varianty: RAZITKA_OKRAJ_MM=40 = puvodni okraj
VANDR_MIN_DELKA_MM = 2.0 * VANDR_OKRAJ_MM + 222.204   # = razitkovac.LOGO_DELKA_MM; 270mm pricka: okraj ~24 mm
# Robert 2026-09-23: "Proč je logo jenom na svislých nohách, musí to být
# náhodné různě, vzor je přece první větev" - kandidati = JAKYKOLI profil
# se jmenem zacinajicim rozmerem "NNxNNxLLL" (Ducato i Trafic konvence:
# "45x45x1330_noha", "45x45x369_Zx2", "20x40x1258"...), ne jen ty s "noha"
# v nazvu - vertikalni i horizontalni podelniky/pricky rovnocenne, presne
# jako branch 1 stampuje NAHODNE napric VSEMI profily daneho prurezu.
# ⭐ bot10 2026-09-24 (Robert nad 4904: "vidis tu nejake vodorovne razitko?"):
# vodorovne pricky 40x40 na cele i zadech 40x40 sestav se jmenuji s PREDPONOU
# "SL" (SL40x40x1267_Zx2, svetove 447 mm, na kazdem patre) - puvodni vzor
# ^CxCxC je vynechaval, proto 40x40 sestavy "nemely" vodorovne hlavni profily.
# Volitelna pismenna predpona (bez cislic - CUB1_/PR10_ maji jen 2 rozmery a
# nematchnou ani tak).
KANDIDATNI_VZOR_RE = re.compile(r"^[A-Za-z_]*(\d+)x(\d+)x(\d+)", re.IGNORECASE)
# Jak daleko od razitka se jeste hleda zakryvajici dil pri testu
# exponovanosti - port razitkovac.DOHLED_MM (4000mm, "radove metrove,
# bezpecne pokryje i nejdelsi pruhled skrz celou sestavu").
DOHLED_MM = 4000.0


def _je_kandidat(name):
    return bool(KANDIDATNI_VZOR_RE.match(name or ""))


def _stred_world(o):
    bbox_local = [Vector(c) for c in o.bound_box]
    return o.matrix_world @ Vector(
        [(max(v[i] for v in bbox_local) + min(v[i] for v in bbox_local)) / 2.0 for i in range(3)])


def _world_aabb_rohy(o):
    """8 rohu SKUTECNE mesh bounding boxu ve svetovych souradnicich - port
    razitkovac.py::_obb_rohy, mista analytickych katalogovych rozmeru
    (ROZMERY_DILU, kazdy dil ma pevny (dx,dy,dz) podle part_id) pouziva
    skutecnou mesh geometrii (Vandr monoliticky import zadny katalog
    rozmeru pro sve stovky vnitrnich objektu nema)."""
    bbox_local = [Vector(c) for c in o.bound_box]
    return [o.matrix_world @ c for c in bbox_local]


def _ctyri_steny_world(M3, cross_idx):
    """Port razitkovac.KANDIDATNI_STENY_LOK (4 PEVNE lokalni smery steny,
    stabilni poradi napric vsemi profily stejneho katalogoveho dilu).

    Vandr NEMA jednotnou katalogovou lokalni konvenci jako nativni 30x30
    (kazdy Vandr profil muze byt v puvodnich datech natoceny/autorsky
    zalozeny jinak) - stabilni je jen "index vlastni prurezove osy +
    znamenko", ne konkretni pevny svetovy smer jako u branch 1. Poradi
    (+prvni, +druha, -prvni, -druha) odpovida stejnemu strukturalnimu
    vzoru jako KANDIDATNI_STENY_LOK=((1,0,0),(0,0,1),(-1,0,0),(0,0,-1))."""
    a, b = cross_idx
    lok = (
        Vector([1.0 if i == a else 0.0 for i in range(3)]),
        Vector([1.0 if i == b else 0.0 for i in range(3)]),
        Vector([-1.0 if i == a else 0.0 for i in range(3)]),
        Vector([-1.0 if i == b else 0.0 for i in range(3)]),
    )
    return [(M3 @ v).normalized() for v in lok]


def _blokovane_useky_vandr(stred_world, osa_world, normala, half_width, aabb_rohy_ostatnich):
    """Port razitkovac.py::_blokovane_useky - useky podel osy hostitele, kde
    na stene uz neco sedi. Mista analytickych katalogovych OBB rohu
    (_obb_rohy) pouziva SKUTECNE mesh AABB rohy ostatnich objektu
    (_world_aabb_rohy) - jina geometrie vstupu, STEJNA logika (w/v/u
    projekce do mistni baze (osa, bok, normala), stejne prahy z
    razitkovac.py: LOGO_RELIEF_MM, LOGO_VYSKA_MM, BLOK_REZERVA_MM)."""
    bok = osa_world.cross(normala).normalized()
    w_min = half_width + 0.5
    w_max = half_width + razitkovac.LOGO_RELIEF_MM + 2.0
    v_mez = razitkovac.LOGO_VYSKA_MM / 2.0 + 2.0
    useky = []
    for rohy in aabb_rohy_ostatnich:
        us, vs, ws = [], [], []
        for r in rohy:
            d = r - stred_world
            us.append(d.dot(osa_world))
            vs.append(d.dot(bok))
            ws.append(d.dot(normala))
        if max(ws) < w_min or min(ws) > w_max:
            continue                            # neni u teto steny
        if max(vs) < -v_mez or min(vs) > v_mez:
            continue                            # mimo sirku razitka
        useky.append((min(us) - razitkovac.BLOK_REZERVA_MM, max(us) + razitkovac.BLOK_REZERVA_MM))
    return useky


def _je_videt_vandr(bod_world, smer_world, vsechny_objekty, sam, inverze_matic, dohled_mm=DOHLED_MM):
    """Port razitkovac.py::_je_videt - je bod na stene videt zvenku, nebo ho
    neco zakryva? Mista analytickeho box-testu (_paprsek_protne_kvadr
    proti katalogovym rozmerum) pouziva SKUTECNY Object.ray_cast proti
    kazdemu ostatnimu mesh objektu - presnejsi nez katalogovy box A
    (dulezite pro Vandr) automaticky zachyti i geometrii, ktera ztratila
    sve jmeno pri exportu (napr. karoserie/kabina vozidla dosazena appkou
    genericky jako "SomeName_Mesh_NNNN") - zadne zvlastni jmenove ani
    bbox-podilove rozpoznavani takove geometrie neni potreba, protoze
    _je_videt ji uvidi jako KAZDOU jinou prekazku."""
    for obj in vsechny_objekty:
        if obj is sam or obj.type != "MESH":
            continue
        inv = inverze_matic[obj.name]
        lok_origin = inv @ bod_world
        lok_smer = (inv.to_3x3() @ smer_world).normalized()
        hit, loc, _nrm, _idx = obj.ray_cast(lok_origin, lok_smer, distance=dohled_mm * 10.0)
        if hit:
            hit_world = obj.matrix_world @ loc
            if (hit_world - bod_world).length <= dohled_mm:
                return False
    return True


def spocitej_razitka(glb_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    bpy.context.view_layer.update()

    vsichni_kandidati = [o for o in bpy.context.scene.objects if o.type == "MESH" and _je_kandidat(o.name)]
    if not vsichni_kandidati:
        return [], {"nedostatek": ["zadni kandidati"], "pozadovane": {}, "umistene": {}}
    # Robert 2026-09-23: "razitko patri pouze na hlavni profily" - ne na
    # KAZDY profil-like objekt (predchozi verze rozsirila na uplne vsechno
    # vc. vedlejsich/tenkych profilu jako 20x40 nebo 80x20). "Hlavni" =
    # dominantni prurez (W x H) podle poctu vyskytu v nazvu - u Ducata
    # 45x45 (vetsina), u Trafic 40x40 - zjisteno z dat, ne natvrdo napsane
    # cislo (jine vozidlo muze mit jiny hlavni profil). Analogie k
    # nativnimu `profil_ids` (mnozina konkretnich katalogovych part_id) -
    # Vandr nema katalog, dominantni prurez je nejlepsi dostupna nahrada.
    rozmer_re = re.compile(r"^[A-Za-z_]*(\d+)x(\d+)x\d+", re.IGNORECASE)   # vc. predpony SL (viz KANDIDATNI_VZOR_RE)
    pocty = {}
    for o in vsichni_kandidati:
        m = rozmer_re.match(o.name)
        if m:
            key = tuple(sorted((int(m.group(1)), int(m.group(2)))))
            pocty[key] = pocty.get(key, 0) + 1
    hlavni_prurez = max(pocty, key=pocty.get) if pocty else None
    kandidati = [o for o in vsichni_kandidati
                if hlavni_prurez is None
                or (lambda m: m and tuple(sorted((int(m.group(1)), int(m.group(2))))) == hlavni_prurez)
                (rozmer_re.match(o.name))]
    print("HLAVNI PRUREZ: %s (%d/%d kandidatu odpovida)"
          % (hlavni_prurez, len(kandidati), len(vsichni_kandidati)))
    if not kandidati:
        return [], {"nedostatek": ["zadni kandidati"], "pozadovane": {}, "umistene": {}}

    # Vsechny mesh objekty ve scene jsou mozni "ostatni" (blokatori pro
    # volne-usek test, prekazky pro exponovanost) - VCETNE objektu se
    # ztracenym jmenem ("SomeName*") a VCETNE ostatnich razitkovych
    # kandidatu navzajem, presne jako branch 1 bere "vsechny ostatni
    # dily sestavy" bez vyjimky (_je_videt/_blokovane_useky dostavaji
    # `ostatni` = VSE krome sebe sama, ne jen "znamou" podmnozinu).
    vsechny_mesh = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    aabb_rohy_podle_jmena = {o.name: _world_aabb_rohy(o) for o in vsechny_mesh}
    inverze_matic = {o.name: o.matrix_world.inverted() for o in vsechny_mesh}
    print("EXPONOVANOST/BLOKACE: %d mesh objektu v scene pripraveno" % len(vsechny_mesh))

    # ⭐ Vandr-specificka mez pro _blokovane_useky_vandr (Robert/bot3
    # 2026-09-23, nalezeno pri testovani tehle prepisu na Trafic 4904):
    # branch 1 pocita blokovane useky z ANALYTICKYCH katalogovych rozmeru
    # (ROZMERY_DILU) - kazdy dil je tam realisticky maly, srovnatelny s
    # profilem samotnym. Vandr monoliticky import navic obsahuje objekty
    # ztracenym jmenem obalujici CELOU sestavu (karoserie/kabina, viz
    # commit 00a8031e) - jejich AABB rohy jsou tak daleko od sebe, ze VZDY
    # "obkroci" i tu nejuzsi testovaci pasku u JAKEKOLI steny (kazdy roh
    # velkeho kvadru je bud hluboko pod, nebo hluboko nad w_min/w_max),
    # takze by orazitkovaci algoritmus (na rozdil od exponovanosti, ktera
    # pocita se SKUTECNOU geometrii pres raycast a tenhle problem nema)
    # oznacil VSECHNY profily jako "zablokovane po cele delce" - presne
    # to, co se stalo pri prvnim testu (0 razitek na cele karte). Objekty
    # vetsi nez cela sestava samotna proto do vypoctu VOLNYCH USEKU
    # nevstupuji (ale POCITAJI SE dal normalne v _je_videt_vandr, kde
    # skutecna geometrie funguje spravne).
    scena_min = Vector((min(r.x for rohy in aabb_rohy_podle_jmena.values() for r in rohy),
                        min(r.y for rohy in aabb_rohy_podle_jmena.values() for r in rohy),
                        min(r.z for rohy in aabb_rohy_podle_jmena.values() for r in rohy)))
    scena_max = Vector((max(r.x for rohy in aabb_rohy_podle_jmena.values() for r in rohy),
                        max(r.y for rohy in aabb_rohy_podle_jmena.values() for r in rohy),
                        max(r.z for rohy in aabb_rohy_podle_jmena.values() for r in rohy)))
    velikost_sceny = scena_max - scena_min
    aabb_rohy_pro_blokovani = {}
    prilis_velke = []
    obal_pudorys = []        # >= 60 % sceny v OBOU vodorovnych osach (karoserie NEBO jen podlaha vozu), pro urceni cela
    for jmeno, rohy in aabb_rohy_podle_jmena.items():
        mn = Vector((min(r.x for r in rohy), min(r.y for r in rohy), min(r.z for r in rohy)))
        mx = Vector((max(r.x for r in rohy), max(r.y for r in rohy), max(r.z for r in rohy)))
        velikost_o = mx - mn
        if all(velikost_sceny[i] <= 1e-6 or velikost_o[i] / velikost_sceny[i] >= 0.6 for i in (0, 1)):
            obal_pudorys.append(jmeno)
        if all(velikost_sceny[i] <= 1e-6 or velikost_o[i] / velikost_sceny[i] >= 0.6 for i in range(3)):
            prilis_velke.append(jmeno)
            continue
        aabb_rohy_pro_blokovani[jmeno] = rohy
    if prilis_velke:
        print("VYNECHANO z vypoctu volnych useku (pokryva >= 60%% cele sestavy ve vsech 3 osach, "
              "pravdepodobne karoserie/obal se ztracenym jmenem): %s" % prilis_velke)

    # ⭐ OPRAVENO 2026-09-24 (bot3, nalezeno pri testovani noveho pravidla
    # presnych poctu na sestave 4582): karoserie/obal vozidla OBEPINA celou
    # sestavu ze vsech stran, takze paprsek EXPONOVANOSTI (Krok 2 nize) v
    # predni/zadni ose skoro vzdy neco trefi - bud VELMI BLIZKO (skrin je
    # tesne u nohy, protoze regal stoji u steny vozidla) nebo AZ NA DRUHE
    # STRANE INTERIERU (paprsek preleti prazdny prostor vozidla a trefi
    # protejsi stenu skrine). Puvodni komentar u _je_videt_vandr tvrdil, ze
    # skutecna geometrie + raycast "tenhle problem nema" (na rozdil od
    # volnych-useku testu) - to plati pro NATIVNI otevrene ramy, NE pro
    # Vandr sestavu uzavrenou uvnitr karoserie vozidla. Overeno primo
    # (ray_cast debug): noha 40x40x305_Zx1_noha, smer +X zasahne
    # SomeName_Mesh_0057 (karoserie) uz na 70mm, smer -X tutez karoserii na
    # 1418mm - VYSLEDEK byl 0 exponovanych kandidatu na cele hloubkove ose
    # (predek+zadek) u cele sestavy 4582. Karoserie/obal (stejna mnozina
    # `prilis_velke` jako u volnych useku vyse) se proto ted vynecha i z
    # `vsechny_mesh` predavaneho do _je_videt_vandr - regal se hodnoti
    # exponovany vuci OSTATNIMU NABYTKU (police, prihradky), ne vuci
    # obalu vozidla, ve kterem stoji.
    vsechny_mesh_expo = [o for o in vsechny_mesh if o.name not in prilis_velke]
    if prilis_velke:
        print("EXPONOVANOST bude pocitana BEZ karoserie/obalu (%d objektu vynechano, %d zbyva jako "
              "mozne prekazky)" % (len(prilis_velke), len(vsechny_mesh_expo)))

    # --- Krok 1 (port vyber_profily_k_razitkovani, cast 1): pro kazdou ze
    # 4 sten kazdeho kvalifikovaneho profilu - ma volny usek na cele logo? ---
    preskoceno_kratke = []
    kandidati_sten = []
    for o in kandidati:
        bbox_local = [Vector(c) for c in o.bound_box]
        spans = [max(v[axis] for v in bbox_local) - min(v[axis] for v in bbox_local) for axis in range(3)]
        osa_idx = spans.index(max(spans))
        M3 = o.matrix_world.to_3x3()
        # ⭐ SVETOVE rozmery (bot10 2026-09-24, Robert v kontrolni scene:
        # "razitko ve vzduchu" na 4593): 48 ze ~470 kandidatu v 17 GLB je
        # SDILENA MESH INSTANCE se skalovanim v matrix_world (napr.
        # 45x45x1750_noha ma svetove jen 1003 mm = x0,573; 20x80x1258 na
        # Traficu 420 mm = x0,334; Connect 20x40x1258 naopak 1538 mm =
        # x1,222). Lokalni bbox (spans) je pro ne LEZ - delka, volne useky
        # i poloha `t` podel osy se musi pocitat ze skutecne svetove delky,
        # jinak razitko pristane za koncem dilu. Nazev ("...x1750") drzi
        # lokalni hodnotu, ne skutecnou.
        wspans = [(M3 @ Vector([spans[i] if k == i else 0 for k in range(3)])).length for i in range(3)]
        delka = wspans[osa_idx]
        # ⭐ Sanity kontrola JEDNOTEK (reference_gltf_meters_vs_project_mm,
        # Vandr-specificky problem, branch 1 s katalogovymi daty tohle
        # nepotrebuje - jejich "scale" vzdy nese jen delku, ne skryte
        # jednotky) - nalezeno 2026-09-23 na testovacim Transporteru:
        # LOKALNI bbox (spans, pouzite pro delka) je spravne v mm, ale
        # matrix_world muze nest skryte meritko (napr. 0.001 z puvodniho
        # metroveho FBX exportu) - stred_world/osa_world pak vychazi v
        # UPLNE JINEM meritku, coz by tise zapsalo nesmyslne (mikroskopicke)
        # souradnice misto chyby. POZOR #1: transformovat SAMOTNY lokalni
        # smerovy vektor (PRED normalizaci), jeho delka je nezavisla na
        # rotaci/zamene os (na rozdil od o.dimensions, coz je AABB
        # svetovych os, ne "svetova delka lokalni osy"). POZOR #2:
        # TOLERANCE musi byt SIROKA (radovy rozdil, ne procenta) - realne
        # Ducato/Trafic dily (napr. 45x45x1267_Zx2) maji legitimni
        # ne-1:1 pomer (~0,76x, zdilena/skalovana mesh instance).
        osa_world_nenormalizovana = M3 @ Vector([spans[osa_idx] if i == osa_idx else 0 for i in range(3)])
        world_delka = osa_world_nenormalizovana.length
        if world_delka < 1e-9 or not (0.1 <= world_delka / delka <= 10.0):
            raise SystemExit(
                "CHYBA JEDNOTEK: %s ma lokalni delku %.2f (bbox), ale po transformaci "
                "matrix_world vychazi %.6f - pomer %.4fx je radove mimo (>10x). matrix_world "
                "nejspis nese skryte meritko (typicky GLB puvodne v metrech misto mm, viz "
                "reference_gltf_meters_vs_project_mm pamet). NEPOKRACUJI - tise zapsat "
                "spatne souradnice by bylo horsi nez chybu ted zastavit." % (
                    o.name, delka, world_delka, (world_delka / delka) if delka else float("inf")))
        if delka < VANDR_MIN_DELKA_MM:
            preskoceno_kratke.append((o.name, round(delka, 0)))
            continue

        cross_idx = [i for i in range(3) if i != osa_idx]
        half_width = (wspans[cross_idx[0]] + wspans[cross_idx[1]]) / 4.0
        stred_world = _stred_world(o)
        osa_world = (M3 @ Vector([1 if i == osa_idx else 0 for i in range(3)])).normalized()
        aabb_rohy_ostatnich = [rohy for jmeno, rohy in aabb_rohy_pro_blokovani.items() if jmeno != o.name]

        volnost = delka - 2.0 * VANDR_OKRAJ_MM - razitkovac.LOGO_DELKA_MM
        for lok_idx, normala in enumerate(_ctyri_steny_world(M3, cross_idx)):
            blokovane = _blokovane_useky_vandr(stred_world, osa_world, normala, half_width, aabb_rohy_ostatnich)
            volne = razitkovac._volne_useky((volnost + razitkovac.LOGO_DELKA_MM) / 2.0, blokovane)
            if not any((do - od) >= razitkovac.LOGO_DELKA_MM for od, do in volne):
                continue                        # na teto stene neni souvisle misto pro cele logo
            kandidati_sten.append({"o": o, "lok_idx": lok_idx, "osa_world": osa_world,
                                   "normala": normala, "half_width": half_width,
                                   "stred_world": stred_world, "volne_useky": volne})

    if not kandidati_sten:
        print("KANDIDATU celkem: %d, orazitkovano: 0, preskoceno (kratsi nez %.0fmm): %d %s"
              % (len(kandidati), VANDR_MIN_DELKA_MM, len(preskoceno_kratke), preskoceno_kratke))
        return [], {"nedostatek": ["zadni kandidati"], "pozadovane": {}, "umistene": {}}

    # --- Krok 2 (port vyber_profily_k_razitkovani, cast 2): exponovanost -
    # paprsek VEN podel VLASTNI normaly steny nesmi narazit na jiny dil.
    # Hlavni oprava je vynechani karoserie z `vsechny_mesh_expo` viz vyse -
    # tenhle blok navic testuje ze STREDU NEJDELSIHO VOLNEHO USEKU (misto
    # stredu cele delky profilu), aby bod odpovidal mistu, kam razitko
    # doopravdy pujde (Krok 4 nize pouziva stejnou bazi u_mid).
    exponovane = []
    for v in kandidati_sten:
        nejdelsi = max(v["volne_useky"], key=lambda u: u[1] - u[0])
        u_mid = (nejdelsi[0] + nejdelsi[1]) / 2.0
        bod = v["stred_world"] + v["osa_world"] * u_mid + v["normala"] * (v["half_width"] + 1.0)
        if _je_videt_vandr(bod, v["normala"], vsechny_mesh_expo, v["o"], inverze_matic):
            exponovane.append(v)
    print("EXPONOVANOST: %d kandidatu-sten melo volne misto, %d z nich je i exponovanych ven"
          % (len(kandidati_sten), len(exponovane)))
    if not exponovane:
        return [], {"nedostatek": ["zadni kandidati"], "pozadovane": {}, "umistene": {}}

    # --- Krok 3 (⭐ PREPSANO 2026-09-24, bot10 - Robertovo PRESNE pravidlo
    # poctu podle poctu SLOUPCU; zaklad = bot3 fork research 2026-09-24
    # (exponovanost bez karoserie, klic rozestupu per stena, bucketing);
    # viz AGENTS_LOG 2026-09-24 "sloupec = pole mezi nohami" + "handoff").
    #
    # 3a) NOHY. Exporter pojmenovava nohy "...x..._noha" (Ducato 45x45 i
    # Trafic/Transporter 40x40 - overeno na vsech 9 GLB, shodne s cistym
    # geometrickym filtrem). Kdyz zadny "_noha" objekt neexistuje (ztracena
    # jmena), fallback = svisly rozsah >= 600 mm a prurez <= 60x60 mm - ale
    # HLASITE, nikdy tise "vsichni kandidati" (to by pocitalo i police).
    def _aabb_min_max(jmeno):
        rohy = aabb_rohy_podle_jmena[jmeno]
        return (Vector((min(r.x for r in rohy), min(r.y for r in rohy), min(r.z for r in rohy))),
                Vector((max(r.x for r in rohy), max(r.y for r in rohy), max(r.z for r in rohy))))

    noha_objekty = [o for o in vsichni_kandidati if "_noha" in o.name.lower()]
    metoda_noh = "nazev '_noha'"
    if not noha_objekty:
        for o in vsechny_mesh:
            if o.name in prilis_velke:
                continue
            mn, mx = _aabb_min_max(o.name)
            d = mx - mn
            if d.z >= 600.0 and d.x <= 60.0 and d.y <= 60.0:
                noha_objekty.append(o)
        metoda_noh = "GEOMETRICKY FALLBACK (zadny objekt s '_noha' v nazvu)"
        print("VAROVANI: %s - %d objektu prislo pres bbox filtr (vyska>=600, prurez<=60x60)"
              % (metoda_noh, len(noha_objekty)))
    if not noha_objekty:
        raise SystemExit("CHYBA: v GLB nejsou zadne nohy (ani podle nazvu, ani geometricky) - "
                         "nelze urcit pocet sloupcu, razitka se NEPOCITAJI.")

    # 3b) Slouceni kusu jedne nohy (stohovane segmenty 305/365/580 mm sdili
    # pudorys) -> pozice noh v pudorysu (X,Y; Z je vyska po glTF importu).
    nohy_pudorys = []                      # [ [x, y, [objekty]] ]
    for o in noha_objekty:
        s = _stred_world(o)
        for zaznam in nohy_pudorys:
            if abs(zaznam[0] - s.x) <= 30.0 and abs(zaznam[1] - s.y) <= 30.0:
                zaznam[2].append(o)
                break
        else:
            nohy_pudorys.append([s.x, s.y, [o]])

    # 3c) Sirkova osa = ta horizontalni osa, kde maji nohy VETSI rozptyl
    # (rada sloupcu podel steny vozidla); hloubkova osa = konstantni
    # ~300 mm rozestup predni/zadni nohy jednoho sloupce.
    rozptyl = [max(n[i] for n in nohy_pudorys) - min(n[i] for n in nohy_pudorys) for i in range(2)]
    SIRKA_IDX = 0 if rozptyl[0] >= rozptyl[1] else 1
    HLOUBKA_IDX = 1 - SIRKA_IDX

    def _shluky(hodnoty, mez):
        out = []
        for h in sorted(hodnoty):
            if out and h - out[-1][-1] <= mez:
                out[-1].append(h)
            else:
                out.append([h])
        return out

    SLOUPEC_SLUC_MM = 120.0
    shluky = _shluky([n[SIRKA_IDX] for n in nohy_pudorys], SLOUPEC_SLUC_MM)
    if len(shluky) == 1 and len(_shluky([n[HLOUBKA_IDX] for n in nohy_pudorys], SLOUPEC_SLUC_MM)) == 2:
        # jedina dvojice noh (2 nohy): "sirka" je degenerovana, osy prohodit
        SIRKA_IDX, HLOUBKA_IDX = HLOUBKA_IDX, SIRKA_IDX
        shluky = _shluky([n[SIRKA_IDX] for n in nohy_pudorys], SLOUPEC_SLUC_MM)
        print("VAROVANI: jen jedna dvojice noh - osy sirka/hloubka urceny z rozestupu dvojice")
    pocet_pozic_noh = len(shluky)
    # ⭐ Robert 2026-09-24: "sloupec" = POLE mezi dvema dvojicemi noh, NE
    # svislice -> pocet sloupcu = pocet pozic noh - 1 (min. 1).
    pocet_sloupcu = max(1, pocet_pozic_noh - 1)
    if pocet_sloupcu <= 1:
        pocty_stran = {"predni": 2, "zadni": 2, "leva": 2, "prava": 2}
    elif pocet_sloupcu == 2:
        pocty_stran = {"predni": 3, "zadni": 2, "leva": 2, "prava": 2}
    else:
        pocty_stran = {"predni": 4, "zadni": 3, "leva": 2, "prava": 2}
    print("NOHY: %d objektu (%s) -> %d noh v pudorysu -> %d pozic podel sirkove osy %s "
          "(sluc %.0f mm) -> %d POLI = pozadovane pocty %s"
          % (len(noha_objekty), metoda_noh, len(nohy_pudorys), pocet_pozic_noh, "XYZ"[SIRKA_IDX],
             SLOUPEC_SLUC_MM, pocet_sloupcu, pocty_stran))

    # 3d) CELO/ZADA. Primarne podle VOZIDLA: "obal v pudorysu" = objekty
    # pokryvajici >= 60 % sceny v OBOU vodorovnych osach - bud karoserie/
    # kabina (4582, 4587, 4591, 4904), nebo JEN PODLAHA vozu (Ducato/Connect
    # exporty 4596/4600/4601/4604/4903: deska 12 mm pres celou plochu, zadna
    # skorepina - nalezeno dry-runem 2026-09-24, kdy tyhle karty padaly na
    # remizu exponovanosti a u 4600/4601 by vysel predek OBRACENE). Stena
    # obalu na hloubkove ose BLIZ tezisti noh = zadni (regal stoji zady u
    # steny vozu). Krizova kontrola / fallback #2 = KOVANI: madla a panty
    # ('madlo', 'pant', 'klika') lezi na cele supliku/dvirek, jejich prumer
    # na hloubkove ose vuci tezisti noh ukazuje predek. Fallback #3 =
    # exponovanost (bot3): smer s VICE exponovanymi kandidaty je predek.
    teziste_hloubka = sum(n[HLOUBKA_IDX] for n in nohy_pudorys) / len(nohy_pudorys)
    osa_h = "XYZ"[HLOUBKA_IDX]
    predni_znamenko, celo_podle = None, None
    if obal_pudorys:
        obal_min = min(_aabb_min_max(j)[0][HLOUBKA_IDX] for j in obal_pudorys)
        obal_max = max(_aabb_min_max(j)[1][HLOUBKA_IDX] for j in obal_pudorys)
        k_minus, k_plus = teziste_hloubka - obal_min, obal_max - teziste_hloubka
        druh_obalu = "karoserie" if any(j in prilis_velke for j in obal_pudorys) else "podlaha"
        if k_minus > 0 and k_plus > 0 and abs(k_plus - k_minus) >= 150.0:
            predni_znamenko = 1 if k_plus > k_minus else -1
            celo_podle = "vozidlo/%s (stena %s%s je bliz: %.0f mm vs %.0f mm)" % (
                druh_obalu, "-" if k_minus < k_plus else "+", osa_h, min(k_minus, k_plus), max(k_minus, k_plus))
        else:
            print("VOZIDLO (%s: %s) nerozhodlo o cele (vzdalenosti %.0f / %.0f mm), zkousim kovani"
                  % (druh_obalu, obal_pudorys, k_minus, k_plus))
    else:
        print("VOZIDLO: v GLB neni karoserie ani podlaha (zadny objekt >= 60 %% sceny v obou vodorovnych osach)")

    kovani = [o for o in vsechny_mesh
              if any(k in o.name.lower() for k in ("madlo", "pant", "klika")) and o.name not in prilis_velke]
    kovani_znamenko = None
    if kovani:
        prum_kovani = sum(_stred_world(o)[HLOUBKA_IDX] for o in kovani) / len(kovani) - teziste_hloubka
        if abs(prum_kovani) >= 40.0:
            kovani_znamenko = 1 if prum_kovani > 0 else -1
        print("KOVANI: %d objektu (madlo/pant/klika), prumer %+.0f mm od teziste noh na ose %s -> %s"
              % (len(kovani), prum_kovani, osa_h,
                 ("predek %s%s" % ("+" if kovani_znamenko > 0 else "-", osa_h)) if kovani_znamenko else "nerozhodne (<40 mm)"))
    else:
        print("KOVANI: zadne madlo/pant/klika v GLB")
    if predni_znamenko is None and kovani_znamenko is not None:
        predni_znamenko = kovani_znamenko
        celo_podle = "kovani (madla/panty %+.0f mm od noh na ose %s)" % (prum_kovani, osa_h)
    elif predni_znamenko is not None and kovani_znamenko is not None and kovani_znamenko != predni_znamenko:
        print("VAROVANI: kovani ukazuje OPACNY predek (%s%s) nez obal vozidla - plati obal vozidla, OVERIT NAHLEDEM"
              % ("+" if kovani_znamenko > 0 else "-", osa_h))

    for v in exponovane:
        n = v["normala"]
        if abs(n[SIRKA_IDX]) >= abs(n[HLOUBKA_IDX]):
            v["osa_strany"], v["znamenko"] = "sirka", (1 if n[SIRKA_IDX] > 0 else -1)
        else:
            v["osa_strany"], v["znamenko"] = "hloubka", (1 if n[HLOUBKA_IDX] > 0 else -1)
    # ⭐ JEN VNEJSI OBRYS (bot10 2026-09-24, Robert nad 4904: "tato sestava
    # nema zadne vodorovne razitko" - 4 razitka byla na hloubkovych prickach
    # MEZI POLI, zvenku neviditelna; exponovanost je pustila, protoze paprsek
    # v dohledu nic nepotkal). Stena patri ke strane sestavy jen tehdy,
    # kdyz lezi na okraji sestavy: souradnice vnejsi steny na ose strany
    # do 60 mm od krajniho hlavniho profilu (min/max AABB vsech kandidatu).
    # Okraj sestavy = obalka NOH (sloupky definuji boky i celo regalu), NE
    # vsech kandidatu: na 4903 dva cepy 45x45x110 trci 111 mm za prave
    # sloupky a posunuly okraj tak, ze cela prava strana vypadla (0/2).
    kand_min = [min(min(r[i] for r in aabb_rohy_podle_jmena[o.name]) for o in noha_objekty) for i in range(3)]
    kand_max = [max(max(r[i] for r in aabb_rohy_podle_jmena[o.name]) for o in noha_objekty) for i in range(3)]
    OKRAJ_SESTAVY_TOL_MM = 60.0

    def _na_vnejsim_obrysu(v):
        ax = SIRKA_IDX if v["osa_strany"] == "sirka" else HLOUBKA_IDX
        stena = v["stred_world"][ax] + v["normala"][ax] * v["half_width"]
        kraj = kand_max[ax] if v["znamenko"] > 0 else kand_min[ax]
        return abs(stena - kraj) <= OKRAJ_SESTAVY_TOL_MM
    vnitrni = [v for v in exponovane if not _na_vnejsim_obrysu(v)]
    exponovane = [v for v in exponovane if _na_vnejsim_obrysu(v)]
    print("VNEJSI OBRYS: %d exponovanych sten je na okraji sestavy, %d VNITRNICH vyrazeno%s"
          % (len(exponovane), len(vnitrni),
             (" (" + ", ".join(sorted({v["o"].name for v in vnitrni})[:8]) + ("..." if len(vnitrni) > 8 else "") + ")") if vnitrni else ""))
    if not exponovane:
        return [], {"nedostatek": ["zadni kandidati na vnejsim obrysu"], "pozadovane": {}, "umistene": {}}

    hloubka_plus = sum(1 for v in exponovane if v["osa_strany"] == "hloubka" and v["znamenko"] > 0)
    hloubka_minus = sum(1 for v in exponovane if v["osa_strany"] == "hloubka" and v["znamenko"] < 0)
    if predni_znamenko is None:
        predni_znamenko = 1 if hloubka_plus >= hloubka_minus else -1
        celo_podle = "exponovanost (+%s: %d, -%s: %d)" % (osa_h, hloubka_plus, osa_h, hloubka_minus)
        if hloubka_plus == hloubka_minus:
            print("VAROVANI: exponovanost je remiza, celo zvoleno +%s - OVERIT NAHLEDEM" % osa_h)
    predni_normala_world = Vector([predni_znamenko if i == HLOUBKA_IDX else 0.0 for i in range(3)])
    n3 = C_INV.to_3x3() @ predni_normala_world
    predni_azimut_rig = int(round(math.degrees(math.atan2(n3.x, n3.z)) % 360.0 / 10.0) * 10) % 360
    print("CELO: predek = %s%s podle %s; azimut pro render rig ~%d (atan2(dx,dz) jako nativni predni_azimut)"
          % ("+" if predni_znamenko > 0 else "-", osa_h, celo_podle, predni_azimut_rig))

    skupiny = {
        "leva": [v for v in exponovane if v["osa_strany"] == "sirka" and v["znamenko"] < 0],
        "prava": [v for v in exponovane if v["osa_strany"] == "sirka" and v["znamenko"] > 0],
        "predni": [v for v in exponovane if v["osa_strany"] == "hloubka" and v["znamenko"] == predni_znamenko],
        "zadni": [v for v in exponovane if v["osa_strany"] == "hloubka" and v["znamenko"] == -predni_znamenko],
    }

    souhrn = {
        "pocet_sloupcu": pocet_sloupcu, "pocet_pozic_noh": pocet_pozic_noh,
        "metoda_noh": metoda_noh, "sirka_osa": "XYZ"[SIRKA_IDX], "hloubka_osa": "XYZ"[HLOUBKA_IDX],
        "celo_podle": celo_podle, "predni_znamenko": predni_znamenko, "predni_azimut_rig": predni_azimut_rig,
        "pozadovane": dict(pocty_stran), "exponovanych": {k: len(v) for k, v in skupiny.items()},
    }

    # --- Krok 3e + 4: ROZMISTENI PO STRANACH (bot10 2026-09-24, v4) ---
    # Robertova pravidla (chat + kontrolni scena 2026-09-24):
    #  (a) presne pocty na stranu podle poctu poli (viz pocty_stran vyse);
    #  (b) na JEDNOM FYZICKEM PROFILU mezera mezi logy >= MIN_ROZESTUP_LOG_MM
    #      (500 mm) BEZ OHLEDU NA STENU ("jsou sice na jine strane regalu,
    #      ale jsou na jednom profilu a proto jsou u sebe") - klic linie
    #      = (dominantni osa, pricna poloha/30 mm), stohovane segmenty nohy
    #      i vsechny 4 steny sloupku sdili jeden klic; souradnice ABSOLUTNE
    #      podel dominantni osy;
    #  (c) "razitka musi byt rovnomerne z hlediska poctu, vodorovne i
    #      svisle": na kazde strane se jeji rozsah (vodorovna osa strany x
    #      vyska) rozdeli na N bunek x N pasem, kazde razitko dostane JINOU
    #      bunku i JINE pasmo (permutace s nejvetsi minimalni vzdalenosti
    #      cilu), poloha na profilu se voli NEJBLIZ cili misto nahodne;
    #  (d) rozestup ma prednost pred poctem - nedostatek = chybovy stav.
    # Poradi stran: nejmene kandidatu prvni (boky 1poloveho regalu maji jen
    # 2 rohove sloupky, ktere celo/zada sdili - kdyz si je vezme celo driv,
    # bok uz nema kam). Uz pouzity profil dostava malou penalizaci, aby se
    # razitka drzela na ruznych profilech, kdyz je z ceho vybirat.
    # Exponovanost se v miste skutecneho umisteni OVERUJE ZNOVU (Krok 2 ji
    # testoval jen ve stredu nejdelsiho volneho useku).
    import itertools
    nove = []
    poradi = 0
    umistene = {k: 0 for k in pocty_stran}
    stredy_log = {}          # klic linie -> [absolutni souradnice stredu uz umistenych log]
    pouzite_profily = set()
    rozlozeni = []           # (strana, profil, h, z) pro vypis
    LOGO_PUL = razitkovac.LOGO_DELKA_MM / 2.0

    def _klic_linie(v):
        osa = v["osa_world"]
        dom = max(range(3), key=lambda i: abs(osa[i]))
        sgn = 1.0 if osa[dom] >= 0 else -1.0
        pricne = tuple(int(round(v["stred_world"][i] / 30.0)) for i in range(3) if i != dom)
        return (dom, pricne), dom, sgn

    def _stredove_useky(v):
        return [(od + LOGO_PUL, do - LOGO_PUL) for od, do in v["volne_useky"]
                if (do - od) >= razitkovac.LOGO_DELKA_MM]

    def _zapis_razitko(v, t, strana):
        nonlocal poradi
        o, normala, osa_world = v["o"], v["normala"], v["osa_world"]
        half_width, stred_world = v["half_width"], v["stred_world"]
        # Orientace PRIMO z razitkovac.py (Robert: "jedna ku jedne prevezmi
        # razitkovaci kod z prvni vetve") - prevod do three.js prostoru je
        # jen linearni cast (smery, ne pozice) - C_INV.to_3x3().
        osa_three = tuple(C_INV.to_3x3() @ osa_world)
        normala_three = tuple(C_INV.to_3x3() @ normala)
        x_osa, z_osa = osa_three, normala_three
        y_osa = razitkovac._norm(razitkovac._cross(z_osa, x_osa))
        if razitkovac._je_text_o_180_stupnu(normala_three, osa_three, y_osa):
            x_osa, y_osa = razitkovac._neg(x_osa), razitkovac._neg(y_osa)
        quat_list = razitkovac._kvaternion_z_baze(x_osa, y_osa, z_osa)  # [x,y,z,w]
        # Vypln drazky - Vandr-specificka geometrie, JINY dil/hloubka podle
        # PRUREZU (VYPLN_PODLE_PRUREZU_MM vyse) - nikdy nehadat, vzdy zmerit
        # pred pridanim noveho profilu (VANDR_RENDER_HOWTO.md bod 4).
        m_prurez = KANDIDATNI_VZOR_RE.match(o.name or "")
        prurez_min = min(int(m_prurez.group(1)), int(m_prurez.group(2))) if m_prurez else None
        vypln_spec = VYPLN_PODLE_PRUREZU_MM.get(prurez_min)
        if vypln_spec is None:
            raise SystemExit(
                "CEP NEZNAMY PRUREZ: %s (prurez klic=%s) neni ve VYPLN_PODLE_PRUREZU_MM - "
                "zmer skutecnou drazku (VANDR_RENDER_HOWTO.md bod 4) pred pridanim "
                "noveho profilu, nehadej existujici cislo z jineho prurezu." % (o.name, prurez_min))
        pozice_vypln = stred_world + osa_world * t + normala * (half_width - vypln_spec["hloubka_mm"] / 2.0)
        posv = C_INV.to_3x3() @ pozice_vypln
        nove.append({
            "part_id": vypln_spec["part_id"],
            "position": [round(posv.x, 3), round(posv.y, 3), round(posv.z, 3)],
            "quaternion": [round(c, 6) for c in quat_list],
            "scale": [1.0, 1.0, 1.0],
            "role": "logo-ochrana-vandr-vypln-%d" % poradi,
            "stena": strana,
            "layer": "alu",
            "metalness": 0.6,
            "roughness": 0.4,
            "base_color": [0.6, 0.6, 0.6],
        })
        pozice = stred_world + osa_world * t + normala * (half_width + LOGO_ODSAZENI_PIVOTU_MM)
        # Samokontrola "logo lezi na profilu" (nezavisla na ose/merítku -
        # pres svetovy AABB objektu): stred loga musi byt uvnitr AABB
        # rozsireneho o half_width+odsazeni+5 mm. Selhani = tvrda chyba,
        # ne varovani (presne tohle proslo 2026-09-24 az k Robertovi).
        rohy = aabb_rohy_podle_jmena[o.name]
        rez = half_width + LOGO_ODSAZENI_PIVOTU_MM + 5.0
        for i in range(3):
            lo, hi = min(r[i] for r in rohy) - rez, max(r[i] for r in rohy) + rez
            if not (lo <= pozice[i] <= hi):
                raise SystemExit("CHYBA GEOMETRIE: logo %d (%s) na %s lezi MIMO profil - osa %s: %.0f mimo [%.0f, %.0f]"
                                 % (poradi, strana, o.name, "XYZ"[i], pozice[i], lo, hi))
        pos = C_INV.to_3x3() @ pozice
        nove.append({
            "part_id": "logo_logiman_cz",
            "position": [round(pos.x, 3), round(pos.y, 3), round(pos.z, 3)],
            "quaternion": [round(c, 6) for c in quat_list],
            "scale": [1.0, 1.0, 1.0],
            "role": "logo-ochrana-vandr-logo-%d" % poradi,
            "stena": strana,
        })
        umistene[strana] = umistene.get(strana, 0) + 1
        pouzite_profily.add(o.name)
        poradi += 1

    STRANY_PORADI = ("leva", "prava", "predni", "zadni")
    poradi_stran = sorted(pocty_stran, key=lambda s: (len(skupiny[s]), STRANY_PORADI.index(s)))

    # 1) SLOTY: pro kazdou stranu N cilu (bunka x pasmo), viz (c) vyse.
    sloty = []
    for strana in poradi_stran:
        N, cands = pocty_stran[strana], skupiny[strana]
        if N <= 0 or not cands:
            continue
        H_IDX = SIRKA_IDX if strana in ("predni", "zadni") else HLOUBKA_IDX
        body = []
        for v in cands:
            for a, b in _stredove_useky(v):
                for tt in (a, b):
                    p = v["stred_world"] + v["osa_world"] * tt
                    body.append((p[H_IDX], p.z))
        if not body:
            continue
        h_min, h_max = min(b[0] for b in body), max(b[0] for b in body)
        z_min, z_max = min(b[1] for b in body), max(b[1] for b in body)
        span_h, span_z = max(h_max - h_min, 1.0), max(z_max - z_min, 1.0)
        cile_h = [h_min + (k + 0.5) * span_h / N for k in range(N)]
        cile_z = [z_min + (k + 0.5) * span_z / N for k in range(N)]

        def _skore(perm):
            pts = [((k + 0.5) / N, (perm[k] + 0.5) / N) for k in range(N)]
            return min((math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in itertools.combinations(pts, 2)),
                       default=1.0)
        permutace = list(itertools.permutations(range(N)))
        nej = max(_skore(p) for p in permutace)
        kandidatni_perm = [p for p in permutace if abs(_skore(p) - nej) < 1e-9]
        r_perm = razitkovac._nahodne_0_1("perm", os.path.basename(glb_path), strana)
        perm = kandidatni_perm[min(int(r_perm * len(kandidatni_perm)), len(kandidatni_perm) - 1)]
        for k in range(N):
            sloty.append({"strana": strana, "cil": (cile_h[k], cile_z[perm[k]]), "cands": cands,
                          "span_h": span_h, "span_z": span_z, "H_IDX": H_IDX})

    # 2) OMEZENY BACKTRACKING pres vsechny sloty sestavy (bot10 2026-09-24
    # v5): hladove "strana po strane" nechalo 8/17 karet v nedostatku,
    # protoze si bok vzal sdileny rohovy sloupek uprostred a celu uz na nem
    # nezbylo 722 mm. Ted se hleda UPLNE reseni: kazdy slot ma az M
    # nejblizsich moznosti (profil + poloha), prohledava se do hloubky s
    # rozpoctem uzlu; kdyz uplne reseni neexistuje, plati nejlepsi castecne
    # (nejvic razitek, pak nejmensi soucet odchylek od cilu) = nedostatek.
    # Exponovanost v miste umisteni se overuje pri generovani moznosti
    # (cache), ne az po vyberu.
    # Kapacita vodorovnych/svislych sten na obrysu (pro poradi vetveni a
    # pro souhrn: kdyz je vodorovnych kandidatu malo, je karta na fyzickem
    # stropu a "zhruba stejny pocet" nejde - Robert 2026-09-24, 4904: jen
    # 3 vodorovne hlavni profily 40x40 na obrysu proti 11 razitkum).
    def _orient(v):
        osa = v["osa_world"]
        return "V" if max(range(3), key=lambda i: abs(osa[i])) == 2 else "H"
    kapacita = {"H": 0, "V": 0}
    for v in exponovane:
        kapacita[_orient(v)] += 1
    vzacna = "H" if kapacita["H"] <= kapacita["V"] else "V"     # orientace, ktere je na obrysu min
    souhrn["kapacita_sten"] = {"vodorovne": kapacita["H"], "svisle": kapacita["V"]}
    M_MOZNOSTI = 6           # nejblizsi body k cili + KRAJE useku (aby sel sdileny sloupek vyuzit od kraju)
    ROZPOCET_UZLU = int(os.environ.get("RAZITKA_ROZPOCET_UZLU", "300000"))  # 4249 potreboval 86k, 4591 30k uzlu (~5 s); 20k nestacilo
    videt_cache = {}

    def _videt(v, t):
        klic = (v["o"].name, v["lok_idx"], int(round(t / 10.0)))
        if klic not in videt_cache:
            bod = v["stred_world"] + v["osa_world"] * t + v["normala"] * (v["half_width"] + 1.0)
            videt_cache[klic] = _je_videt_vandr(bod, v["normala"], vsechny_mesh_expo, v["o"], inverze_matic)
        return videt_cache[klic]

    def _moznosti(slot, stredy, pouzite, vetsina=None, potreba=None):
        """vetsina = orientace ("V"/"H"), ktere je uz ted vic (penalizace);
        potreba = orientace, ktera se ma zkouset PRVNI (ta, ktere je v
        rozpracovanem reseni zrovna min; pri rovnosti ta vzacnejsi na obrysu).
        Dynamicky, ne staticky z kapacity: 4904 ma 30 vodorovnych sten proti
        14 svislym, staticke "vzacna=V" hnalo DFS do sloupku a dalo 10/1."""
        cil, H_IDX = slot["cil"], slot["H_IDX"]
        out = []
        for v in slot["cands"]:
            klic, dom, sgn = _klic_linie(v)
            if dom not in (H_IDX, 2):
                continue                        # osa profilu miri od divaka - nemelo nastat u steny teto strany
            c0 = v["stred_world"][dom]
            useky_abs = [tuple(sorted((c0 + sgn * a, c0 + sgn * b))) for a, b in _stredove_useky(v)]
            for a, b in razitkovac._povolene_useky(useky_abs, stredy.get(klic, [])):
                if b - a < 0:
                    continue
                cil_dom = cil[0] if dom == H_IDX else cil[1]
                c_cil = min(max(cil_dom, a), b)
                # Body k vyzkouseni: nejblizsi k cili + oba kraje useku. Kraj je
                # dulezity u SDILENEHO sloupku (bok i celo): razitko u konce
                # necha druhe strane 722 mm na tomtez profilu, razitko uprostred ne.
                body_c = [c_cil] + [x for x in (a, b) if abs(x - c_cil) > 1.0]
                for c in body_c:
                    t = (c - c0) * sgn
                    if not _videt(v, t):
                        continue
                    p_h = c if dom == H_IDX else v["stred_world"][H_IDX]
                    p_z = c if dom == 2 else v["stred_world"].z
                    d = math.hypot((p_h - cil[0]) / slot["span_h"], (p_z - cil[1]) / slot["span_z"])
                    if v["o"].name in pouzite:
                        d += 0.15
                    orient = "V" if dom == 2 else "H"
                    if vetsina is not None and orient == vetsina:
                        d += 0.3
                    out.append((d, v, t, c, klic, p_h, p_z, orient))
        # Vzacna orientace VZDY prvni (ne jen +0.3 k odchylce): jinak DFS
        # vycerpa rozpocet na sloupcich blizko cilum a vodorovne pricky,
        # kterych je par, se k razitku nedostanou (4904: 9/2 misto 8/3).
        prvni = potreba or vzacna
        out.sort(key=lambda m: (0 if m[7] == prvni else 1, m[0], m[1]["o"].name, m[2]))
        return out[:M_MOZNOSTI]

    nejlepsi = {"pocet": -1, "strany": -1, "nevyv": 10**6, "soucet": 0.0, "volby": None}
    stav = {"uzly": 0, "hotovo": False}

    def _hledej(i, stredy, pouzite, volby, soucet):
        if stav["hotovo"]:
            return
        stav["uzly"] += 1
        pocet = sum(1 for x in volby if x is not None)
        # Hodnoceni: nejvic razitek -> co nejvic STRAN s aspon jednim (strana
        # uplne bez razitka je horsi nez dve strany po jednom chybejicim) ->
        # VYVAZENOST ORIENTACE (Robert 2026-09-24: "svisle/vodorovne pomerove
        # zhruba stejny pocet" = |na svislych - na vodorovnych| co nejmensi)
        # -> nejmensi odchylka od cilu. Hodnoti se jen UPLNE stavy (i == len),
        # castecne jen jako zaloha, kdyz uplne reseni neexistuje.
        strany_s = len({x[0]["strana"] for x in volby if x is not None})
        n_v = sum(1 for x in volby if x is not None and x[5] == "V")
        nevyv = abs(n_v - (pocet - n_v))
        if i == len(sloty) or pocet + (len(sloty) - i) < len(sloty):
            klic_hodn = (pocet, strany_s, -nevyv, -soucet)
            if klic_hodn > (nejlepsi["pocet"], nejlepsi["strany"], -nejlepsi["nevyv"], -nejlepsi["soucet"]):
                nejlepsi.update({"pocet": pocet, "strany": strany_s, "nevyv": nevyv, "soucet": soucet,
                                 "volby": list(volby)})
        if i == len(sloty):
            # uplne reseni s optimalni vyvazenosti (0, u licheho poctu 1) = konec
            if pocet == len(sloty) and nevyv <= pocet % 2:
                stav["hotovo"] = True
            return
        if stav["uzly"] > ROZPOCET_UZLU:
            return
        # horni odhad: i kdyby vsechny zbyle sloty vysly, prekona se nejlepsi?
        if pocet + (len(sloty) - i) < nejlepsi["pocet"]:
            return
        slot = sloty[i]
        n_h = pocet - n_v
        vetsina = "V" if n_v > n_h else ("H" if n_h > n_v else None)
        potreba = "H" if n_h < n_v else ("V" if n_v < n_h else vzacna)
        for d, v, t, c, klic, p_h, p_z, orient in _moznosti(slot, stredy, pouzite, vetsina, potreba):
            stredy2 = dict(stredy)
            stredy2[klic] = stredy.get(klic, []) + [c]
            pouzite2 = pouzite | {v["o"].name}
            volby.append((slot, v, t, p_h, p_z, orient))
            _hledej(i + 1, stredy2, pouzite2, volby, soucet + d)
            volby.pop()
            if stav["hotovo"]:
                return
        # slot vynechan (nedostatek) - az jako posledni vetev
        volby.append(None)
        _hledej(i + 1, stredy, pouzite, volby, soucet)
        volby.pop()

    _hledej(0, {}, set(), [], 0.0)
    volby = nejlepsi["volby"] or []
    for volba in volby:
        if volba is None:
            continue
        slot, v, t, p_h, p_z, orient = volba
        _zapis_razitko(v, t, slot["strana"])
        rozlozeni.append((slot["strana"], v["o"].name, p_h, p_z, orient))

    n_v = sum(1 for r in rozlozeni if r[4] == "V")
    uplne = nejlepsi["pocet"] == len(sloty)
    print("VYBER PODLE STRAN: exponovanych %s, poradi stran %s, slotu %d -> umisteno %d (prohledano %d uzlu, %s; "
          "svisle %d / vodorovne %d; sten na obrysu svisle %d / vodorovne %d)"
          % ({k: len(v) for k, v in skupiny.items()}, poradi_stran, len(sloty), poradi, stav["uzly"],
             ("UPLNE reseni" + (" s optimalni vyvazenosti" if stav["hotovo"] else " (vyvazenost %d)" % nejlepsi["nevyv"]))
             if uplne else "uplne reseni NENALEZENO", n_v, poradi - n_v, kapacita["V"], kapacita["H"]))
    souhrn["orientace"] = {"svisle": n_v, "vodorovne": poradi - n_v}
    for strana in STRANY_PORADI:
        radky = [r for r in rozlozeni if r[0] == strana]
        if radky:
            print("ROZLOZENI %-6s: %s" % (strana, "; ".join("%s%s (h %.0f, z %.0f)" % (r[1], "|" if r[4] == "V" else "—", r[2], r[3]) for r in radky)))
    print("KANDIDATU celkem: %d, preskoceno (kratsi nez %.0fmm): %d %s"
          % (len(kandidati), VANDR_MIN_DELKA_MM, len(preskoceno_kratke), preskoceno_kratke))
    print("VYSLEDEK: %d log umisteno" % poradi)
    # Robert 2026-09-24: rozestup ma prednost pred presnym poctem - nedostatek se
    # NEDOHANI mackanim razitek k sobe, hlasi se jako chybovy stav karty.
    souhrn["umistene"] = dict(umistene)
    souhrn["nedostatek"] = ["%s: %d/%d" % (k, umistene.get(k, 0), p)
                            for k, p in pocty_stran.items() if umistene.get(k, 0) < p]

    # ⭐ TVRDA KONTROLA "logo lezi CELOU DELKOU na skutecne plose" (bot3
    # 2026-09-24, po nalezu 4565 "logo presahuje do vzduchu" + obave "je to
    # systemova vada, ne jednorazovost" - rozhodnuto samostatne, "je to vec
    # robustnosti kodu, ne produktove rozhodnuti"). STEJNA definice "lezi na
    # plose" jako nezavisly audit (scripts/2026-09-24_vandr_logo_presah_
    # audit.py, BVHTree.find_nearest na OBA konce delkove osy) - jedno misto
    # pravdy, aby se kontrola a audit nikdy nerozesly (bot3 pozadavek #3).
    # Prekroceni = STEJNY kanal jako `nedostatek` (razitka se NEZAPISI,
    # zapise se jen chyba_otisk - viz zapis_do_shop_product) - NE tiche
    # varovani, presne jak bot3 zadal.
    PRESAH_TOLERANCE_MM = 15.0  # nameren na vsech 17 kartach: cisty pripad = 5.1mm (pivot odsazeni), rezerva 3x
    vsechny_mesh_pro_bvh = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    verts_bvh, tris_bvh = [], []
    for o in vsechny_mesh_pro_bvh:
        o_mat = o.matrix_world
        zaklad = len(verts_bvh)
        verts_bvh.extend(o_mat @ v.co for v in o.data.vertices)
        for poly in o.data.polygons:
            idx = [zaklad + i for i in poly.vertices]
            for k in range(1, len(idx) - 1):
                tris_bvh.append((idx[0], idx[k], idx[k + 1]))
    bvh_cela_scena = BVHTree.FromPolygons(verts_bvh, tris_bvh)
    presahy = []
    for zaznam in nove:
        if zaznam["part_id"] != "logo_logiman_cz":
            continue
        pos_three = Vector(zaznam["position"])
        x, y, z, w = zaznam["quaternion"]
        osa_three = Vector((1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w))).normalized()
        for znamenko in (1, -1):
            konec_blender = C.to_3x3() @ (pos_three + osa_three * (znamenko * razitkovac.LOGO_DELKA_MM / 2.0))
            zasah = bvh_cela_scena.find_nearest(konec_blender, PRESAH_TOLERANCE_MM)
            if zasah[3] is None:
                presahy.append("%s (%s konec): > %.0f mm od jakekoli plochy"
                               % (zaznam["role"], "+" if znamenko > 0 else "-", PRESAH_TOLERANCE_MM))
    if presahy:
        souhrn["nedostatek"] = souhrn["nedostatek"] + ["PRESAH DO PRAZDNA: %s" % p for p in presahy]
        print("CHYBA GEOMETRIE: %d konec/koncu loga dal nez %.0f mm od jakekoli plochy (presahuje do prazdna): %s"
              % (len(presahy), PRESAH_TOLERANCE_MM, presahy))

    print("POCTY PO STRANACH: pozadovane %s, umistene %s%s"
          % (pocty_stran, dict(umistene),
             (" - NEDOSTATEK: %s" % souhrn["nedostatek"]) if souhrn["nedostatek"] else " - OK"))
    return nove, souhrn


def _pymysql_a_env():
    import glob
    venv_site = glob.glob(os.path.join(REPO, "api", "venv", "lib", "python3.*", "site-packages"))
    if venv_site:
        sys.path.insert(0, venv_site[0])
    import pymysql
    env = {}
    for line in open(os.path.join(REPO, "api", ".env")):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return pymysql, env


def zapis_do_shop_product(shop_product_id, glb_path, stamps, nedostatek=None, predni_azimut_rig=None):
    """Zapise razitka PRIMO na shop_products - ZADNY product_assemblies
    radek (viz komentar u argv vyse). `vandr_razitka_glb_otisk` je
    sha256 GLB souboru v okamziku vypoctu - zmeni-li se GLB (novy
    export/oprava), otisk nesedi a dispatch skript kartu prepocita.

    `predni_azimut_rig` (WORKFLOW.md pravidlo 52, bot10 2026-09-24):
    geometricky vypocitany predni smer TETO konkretni sestavy (Krok 3d
    vyse - karoserie/podlaha proximita + kovani jako krizova kontrola),
    perzistovany do `vandr_predni_azimut_deg`, aby ho
    `scripts/2026-09-09_turntable_job.py::build_job_vandr()` mohl pouzit
    MISTO globalniho fallbacku 270 (ktery je spravny jen nahodou u
    LEVYCH regalu - bot3 2026-09-24: "55 karet je RP, vsechny by
    renderovaly se spatnou stranou")."""
    pymysql, env = _pymysql_a_env()
    # Otisk = sha256(GLB) + VERZE PRAVIDLA (scripts/_vandr_razitka_otisk.py,
    # sdileno s auto_dispatch - obe strany MUSI pocitat totez).
    _spec_o = importlib.util.spec_from_file_location(
        "_vandr_razitka_otisk", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vandr_razitka_otisk.py"))
    _otisk_mod = importlib.util.module_from_spec(_spec_o)
    _spec_o.loader.exec_module(_otisk_mod)
    glb_otisk = _otisk_mod.otisk_glb(glb_path)
    conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4")
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (shop_product_id,))
            if not cur.fetchone():
                raise SystemExit("shop_products id %s neexistuje." % shop_product_id)
            if nedostatek:
                # Rozestup ma prednost pred poctem (Robert 2026-09-24). Kartu s malo razitky
                # NEZAPISUJEME (vandr-render-dispatch reaguje na kazdou zmenu razitka_json a
                # pustil by ostry render vadne karty) - jen chyba_otisk, at ji razitka-dispatch
                # neopakuje donekonecna, a hlasity vystup pro cloveka.
                cur.execute("UPDATE shop_products SET vandr_razitka_chyba_otisk=%s WHERE id=%s",
                            (glb_otisk, shop_product_id))
                conn.commit()
                raise SystemExit("NEDOSTATEK RAZITEK (%s) - shop_product %s NEZAPSAN, oznacen chyba_otisk; "
                                 "potrebuje rucni posouzeni." % (nedostatek, shop_product_id))
            razitka_json = json.dumps(stamps, ensure_ascii=False)
            azimut_db = int(round(predni_azimut_rig)) % 360 if predni_azimut_rig is not None else None
            cur.execute(
                "UPDATE shop_products SET vandr_razitka_json=%s, vandr_razitka_glb_otisk=%s, "
                "vandr_razitka_hotovo_at=NOW(), vandr_razitka_chyba_otisk=NULL, "
                "vandr_predni_azimut_deg=%s WHERE id=%s",
                (razitka_json, glb_otisk, azimut_db, shop_product_id))
            cur.execute("SELECT vandr_razitka_json, vandr_razitka_glb_otisk, vandr_predni_azimut_deg "
                        "FROM shop_products WHERE id=%s", (shop_product_id,))
            zpet = cur.fetchone()
            if (zpet["vandr_razitka_json"] != razitka_json or zpet["vandr_razitka_glb_otisk"] != glb_otisk
                    or zpet["vandr_predni_azimut_deg"] != azimut_db):
                raise SystemExit("Zapis se neprojevil - data po SELECT nesedi (shop_product %s)" % shop_product_id)
        conn.commit()
    finally:
        conn.close()


def zapis_do_db(assembly_id, stamps):
    """PUVODNI rezim, jen pro 671/672 (pred pravidlem "Vandr karty
    product_assemblies nemaji") - zapisuje do product_assemblies.
    data.parts, stejne jako driv."""
    pymysql, env = _pymysql_a_env()
    conn = pymysql.connect(host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
                            user=env["DB_USER"], password=env["DB_PASSWORD"],
                            database=env["DB_NAME"], charset="utf8mb4")
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
            row = cur.fetchone()
            if not row:
                raise SystemExit("Sestava %s neexistuje." % assembly_id)
            data = json.loads(row["data"])
            parts = [p for p in (data.get("parts") or [])
                    if not str(p.get("role") or "").startswith("logo-ochrana-vandr-")]
            parts.extend(stamps)
            data["parts"] = parts
            data["razitka"] = {"otisk": razitkovac.otisk_sestavy(parts),
                               "pocet": len(stamps), "verze": razitkovac.OTISK_VERZE}
            novy_json = json.dumps(data, ensure_ascii=False)
            cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s", (novy_json, assembly_id))
            cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (assembly_id,))
            zpet = cur.fetchone()["data"]
            if zpet != novy_json:
                raise SystemExit("Zapis se neprojevil - data po SELECT nesedi (sestava %s)" % assembly_id)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    stamps, souhrn = spocitej_razitka(GLB_PATH)
    souhrn["pocet_razitek"] = sum(1 for s in stamps if str(s.get("role", "")).startswith("logo-ochrana-vandr-logo-"))
    print("SOUHRN_JSON: " + json.dumps(souhrn, ensure_ascii=False))
    if DRY_RUN:
        print("DRY_RUN: nic se nezapisuje. RAZITKA_JSON: " + json.dumps(stamps, ensure_ascii=False))
        raise SystemExit(2 if souhrn.get("nedostatek") else 0)
    if SHOP_PRODUCT_ID is not None:
        print("SPOCITANO %d razitek pro shop_product %s" % (len(stamps), SHOP_PRODUCT_ID))
        zapis_do_shop_product(SHOP_PRODUCT_ID, GLB_PATH, stamps, nedostatek=souhrn.get("nedostatek"),
                              predni_azimut_rig=souhrn.get("predni_azimut_rig"))
        print("ZAPSANO do shop_products.vandr_razitka_json (produkt %s)" % SHOP_PRODUCT_ID)
    else:
        print("SPOCITANO %d razitek pro sestavu %s" % (len(stamps), ASSEMBLY_ID))
        zapis_do_db(ASSEMBLY_ID, stamps)
        print("ZAPSANO do product_assemblies.data.parts (sestava %s)" % ASSEMBLY_ID)
