# -*- coding: utf-8 -*-
"""Razitkovac profilu - automaticke umisteni ochranneho 3D loga LOGIMAN.CZ.

ZADANI (Robert, 2026-09-10, doslova):
  * "logem musi byt pokryto 10% profilu z celni / pohledove strany regalu"
    -> tzn. KAZDY DESATY profil, ktery ma viditelnou stenu na celni strane
    regalu. NENI to 10 % plochy - to bylo moje prvni, chybne cteni.
  * "kazdy desaty profil ma logo nahodne umistene nekde po jeho delce"
  * "loga musi byt v ruznych mistech podelne, nahodne"
  * "pri pohledu na obrazek musi byt dojem ze jsou rovnomerne rozmistena"
  * "pod razitkem chceme zaroven vyplneni prostoru drazky (slotu)",
    "vypln licuje se stenou profilu, stejne jako logo"
  * "dnes budeme razit jen profily 30x30"

PROC VYPLN: profil 30x30 ma ve stredu kazde steny otevrenou sterbinu
8,2 mm sirokou a 10 mm hlubokou (zmereno na Object_7.glb: povrch +-15,
dno +-5). Logo je 28 mm vysoke, takze lezi pres celou sirku steny a
prostrednich 8,2 mm mu visi nad prazdnem - pismena se v tom pasu lamou.
Vypln ten prostor zaplni az do roviny steny, takze razitko ma na cem
sedet.

KDE TO BEZI: razitka jsou OCHRANA RENDERU (viz pravidlo o 3 stupnich
duvery), ne prvek 3D sceny - proto Python vedle turntable_job.py a ne
scene-geometry-shared.js. Do sceny se nic nepridava.
"""
import hashlib
import math
import os
import re

# --- geometrie profilu 30x30 (zmereno na Object_7.glb) -------------------
PROFIL_SIRKA_MM = 30.0          # prurez 30 x 30
PROFIL_POLOMER_MM = 15.0        # povrch steny = 15 mm od osy
PROFIL_DELKA_ZAKLAD_MM = 1000.0  # zakladni delka .glb, scale ji nataha
DRAZKA_HLOUBKA_MM = 10.0        # povrch 15 -> dno 5

# --- role razitkovych dilu -----------------------------------------------
# ⭐ JEDEN PREFIX PRO OBA DILY RAZITKA. Nemenit bez precteni duvodu:
#
# Do 2026-09-11 se logo jmenovalo `logo-ochrana-N`, ale vypln drazky
# `vypln-drazky-N` - tedy JINY prefix. To bylo spatne ze dvou duvodu:
#  1. Kazdy filtr "tohle neni dil k vyrobe" (kusovnik, cena, pocitani spoju,
#     kolize) musel znat dve jmena. Jedno se vzdycky zapomnelo - a zapomnelo
#     se prave na vypln, tedy na dil, ktery v katalogu NENI (hlasi mezeru)
#     a je v drazce ZAMERNE zanoreny (hlasi falesnou kolizi).
#  2. Prefix `vypln-` uz patri generatoru hornich bloku
#     (2026-09-05_horni_ram.js: vypln-zada, vypln-dno, vypln-police,
#     vypln-celo, vypln-bok-prepazka). Razitkova vypln na nej squatovala,
#     takze `2026-09-11_smazat_stare_horni_bloky.py`, ktery maze podle
#     `role.startswith("vypln-")`, by VYPLNE SMAZAL A LOGA NECHAL - loga by
#     visela nad otevrenymi drazkami, presne ta vada, kvuli ktere vypln
#     existuje ("pismena se v tom pasu lamou").
#
# Role dilu jsou SDILENY jmenny prostor, do ktereho saha vic generatoru.
# Novy prefix si over proti ostatnim, nez ho zavedes.
ROLE_PREFIX = "logo-ochrana"
ROLE_LOGO = ROLE_PREFIX + "-logo-%d"
ROLE_VYPLN = ROLE_PREFIX + "-vypln-%d"


def je_razitko(role):
    """Je tenhle dil soucasti ochranneho razitka (logo nebo vypln drazky)?

    Razitko NENI dil k vyrobe: nesmi do kusovniku, do ceny, do poctu spoju
    ani do koliznich kontrol. JS protejsek: `isStampPart` ve
    webapp/js/scene-geometry-shared.js - meni se OBA najednou.

    Bere i stare `logo-ochrana-N` (sestava 134 z rucniho dema 2026-09-08),
    protoze prefix sedi i na nej.
    """
    return str(role or "").startswith(ROLE_PREFIX)


# --- logo ----------------------------------------------------------------
LOGO_PART_ID = "logo_logiman_cz"
# Robert 2026-09-10: "ve 3D logu potrebujeme zmenit velke I na male i" ->
# LOGiMAN.CZ. Male `i` je uzsi, takze logo se zkratilo z 223,217 na 222,204;
# vyska zustava 28 mm (tu urcuji velka pismena) a odsazeni pivotu 0,696
# take, takze umisteni razitek se nemeni.
LOGO_DELKA_MM = 222.204
LOGO_VYSKA_MM = 28.0
# Vzdalenost pivotu loga od jeho strany prilehajici k profilu. Plati pro
# puvodni relief 1,392 mm i pro zesileny na 3,0 mm - novy .glb je posunuty
# tak, aby prilehajici strana zustala na miste (viz export_loga.py).
LOGO_ODSAZENI_PIVOTU_MM = 0.696

# Robert 2026-09-11 ("na razitka musime pridat barvu, lehce oranzovou"):
# do te doby melo logo STEJNY material jako profil (Robert 2026-09-10:
# "logo i vypln drazky nech maji material hlinik jako profily") - to uz
# neplati JEN pro logo, vypln drazky zustava hliníková beze zmeny (viz
# duvod u VYPLN_BARVU_MENIT nize).
#
# Barva je "eloxovana oranz" - hlinik se realne eloxuje do barevnych
# odstinu (stejny vyrobni proces jako u profilu, jen jina lazen), takze
# se drzi rodiny materialu produktu, ne nahodna barva zvenku. Metalness
# mirne NAD hodnotou raw hliniku (0.6 u "alu" v PART_MATERIAL_METALNESS,
# scripts/2026-09-09_turntable_job.py), roughness mirne POD (hladsi,
# "znackova destka" misto pískovaneho povrchu).
#
# hex NESMI kolidovat s PALETTE_BY_HEX (api/blender_render_turntable.py) -
# kdyby sedel na existujici radek (#c9cdd1/#242424/#b7bcc0/#1c1c1e/#666c73),
# _material_for() by tise sáhla po sablonovem TT_* materialu misto teto
# barvy. Zadny z kandidatu níže mu neni ani blizko.
LOGO_BARVA_HEX = "#EB8E23"    # kandidat D, "vyraznejsi oranzova" - Robert
# 2026-09-12 pres bot3/bot4, po overovacim renderu sestavy 333 s
# kandidatem C: "hliník profilů už vypadá dobře... barvu loga více
# oranžovou ne do červena". Historie: A (#C97A3D) -> "vyraznejsi"
# (duvod merlitelny: bot8 zmeril, ze logo ma na masteru 37 px vysky, ale
# na zmensenem nahledu produktove stranky jen 18 px, kde hlinik na
# hliniku zanikal uplne) -> C (#D4863F, "jasnejsi ambra", hue ~28.6°) ->
# TOHLE (D, hue ~32° - vyssi hue + vyssi saturace nez C, at to po
# vyrenderovani (sklo, transmission=1 - viz LOGO_TRANSMISSION nize, mate
# tendenci posouvat vnimany odstin k teplejsi/cervenejsi strane) porad
# ctelo jako oranzova, ne jako spalena/do cervena).
#
# Dalsi kandidati pro rychlou vymenu, kdyby D porad nebyl dost "cisty
# oranz" (jen prepsat tenhle radek + bumpnout OTISK_VERZE, presny postup
# jako A->C vyse):
#   kandidat E: "#E09016" - jeste vic saturovana/sytejsi (hue ~36°)
#   kandidat F: "#E6A82E" - mekci/zlatava oranzova (hue ~40°, nizsi sat)
# ⭐ EXPERIMENTALNI - "skutecne barevne sklo" (Robert 2026-09-11: "logo s
# barevnym sklem", doslova, ne glazura), testuje se na sestave 333 pro
# Robertovo porovnani na GPU snimku (jeste NEROZHODNUTO - viz zprava bota3).
# Historie hodnot: 0.65/0.30 ("dnesni" kov) -> 0.25/0.08 (kandidat B,
# "lakovany bonbon") -> tohle (sklo, transmission=1).
#
# ⭐⭐ POZOR, past kterou nahlasil bot3: tyhle konstanty NEJEDOU pres data
# sestavy. `_JEN_PRO_RENDER` je z ulozenych razitkovych dilu SCHVALNE
# odstranuje (spravne - material se ma vzdy odvodit znovu z katalogu, viz
# PRODUKTOVE_RENDERY.md "Barva loga"), takze zapis do `product_assemblies.
# data.parts` NEMENI, jaky material se pri renderu pouzije. Skutecny zdroj
# pravdy pri renderu je `HEX_TO_METALNESS`/`HEX_TO_ROUGHNESS`/
# `HEX_TO_TRANSMISSION`/`HEX_TO_IOR` v `scripts/2026-09-09_turntable_job.py`,
# ktere se naplni z TĚCHTO konstant AZ PRI IMPORTU (cte
# `razitkovac.LOGO_METALNESS`/... ze zdrojoveho souboru na disku, ne z
# nejakeho monkeypatch v jinem procesu). Zmena kandidata proto znamena
# zmenit CISLA TADY, ne jen prepsat data sestavy - jinak render pouzije
# stare hodnoty, i kdyz sestava ma novou geometrii.
#
# Metallic=0: sklo je dielektrikum - michat kovovost s pruhlednosti by
# bylo fyzikalne nekonzistentni (Principled BSDF by vysledek nedokazal
# citelne zobrazit). Transmission=1/IOR=1.5: plne pruhledne, bezne sklo/
# kristal - ne poloviceta pruhlednost (ta uz je vyuzita jinde, viz
# VYPLN_ALFA nize).
LOGO_METALNESS = 0.0
LOGO_ROUGHNESS = 0.04
LOGO_TRANSMISSION = 1.0
LOGO_IOR = 1.5

# Robert 2026-09-15, pres bot8: obousmerna sipka (posuvne celo - oznacuje,
# ze se da posouvat) - "material jako logo, jen v zelene". STEJNE barevne-
# sklo vlastnosti jako LOGO_METALNESS/ROUGHNESS/TRANSMISSION/IOR vyse
# (kopie hodnot, ne odkaz), jen jiny hex a VLASTNI konstanta - zmena barvy
# loga v budoucnu tak tuhle sipku necekane nepribarvi (a naopak).
POSUVNE_CELO_SIPKA_HEX = "#2ECC71"
POSUVNE_CELO_SIPKA_METALNESS = 0.0
POSUVNE_CELO_SIPKA_ROUGHNESS = 0.04
POSUVNE_CELO_SIPKA_TRANSMISSION = 1.0
POSUVNE_CELO_SIPKA_IOR = 1.5


def _hex_na_linearni_base_color(hexcode):
    """#RRGGBB (sRGB) -> [r,g,b] LINEARNI, presne stejny vzorec jako
    _hex_linear() v api/blender_render_turntable.py - `base_color` tam
    jde primo do Principled BSDF, ktery ceka linearni hodnoty, ne sRGB.
    Vlastni kopie vzorce (ne import): razitkovac.py se pouziva i mimo
    Blender (napr. api/product_assemblies.py pri zarazeni do stromu),
    tam se `api.blender_render_turntable` (zavisi na `bpy`) neda naimportovat.
    """
    h = hexcode.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 4)
           for c in srgb]


LOGO_BASE_COLOR = _hex_na_linearni_base_color(LOGO_BARVA_HEX)
POSUVNE_CELO_SIPKA_BASE_COLOR = _hex_na_linearni_base_color(POSUVNE_CELO_SIPKA_HEX)
# Vypln drazky barvu NEMENI (bot3 2026-09-11, souhlasim): jeji ukol je
# splyvat s profilem, aby razitko melo na cem "sedet" - vlastni barva by
# pod poloprusvitnym (50 %) povrchem udelala oranzovy odlesk KOLEM loga,
# tedy presny opak zameru ("ma pusobit jako znacka vyrobce, ne jako
# nalepka"). Meni se proto jen `logo`, `vypln` dal kopiruje material
# hostitelskeho profilu jako driv.

# --- vypln drazky --------------------------------------------------------
VYPLN_PART_ID = "vypln_drazky_30"
VYPLN_DELKA_ZAKLAD_MM = 1000.0
# Robert 2026-09-10: "vypln pod logo znamena ze nebude delsi nez logo".
# Zadny presah - vypln konci presne tam, kde konci razitko.
VYPLN_DELKA_MM = LOGO_DELKA_MM
# Robert 2026-09-10: "pruhlednost vyplne drazky 50%". Puvodni duvod: logo
# bylo NEPRUHLEDNY kov, takze poloprusvitna vypln byla jediny napovezeni,
# ze pod razitkem neco je.
#
# ⭐ ZMENENO na 1.0 (neprusvitna) 2026-09-11 SPOLU se sklenenym logem
# (LOGO_TRANSMISSION vyse), NE globalne - je to VYSLOVNE SVAZANE s tim, ze
# logo je ted sklo (bot3, souhlas s odduvodnenim): skrz sklo se skutecne
# kouka dovnitr, takze poloprusvitna vypln + pruhledne sklo + hlinik pod
# tim by byly TRI vrstvy pruhlednosti pres sebe - citelnost tim trpi
# ("kase"), ne pridava. Neprusvitna vypln za tonovanym sklem je ctivejsi
# ("sklo zasazene do kovu").
#
# ⭐⭐ KDYBY SE NEKDY LOGO VRATILO NA NEPRUHLEDNY KOV, VRATIT I TOHLE NA 0.5
# - jinak nikdo za mesic nebude vedet, proc je vypln neprusvitna, a puvodni
# duvod (napovezeni drazky pod neprulednym logem) zase prestane platit.
VYPLN_ALFA = 1.0

# --- pravidla razitkovani ------------------------------------------------
# Robert 2026-09-10: puvodne "kazdy desaty", po videni poctu ("kazdy desaty
# predni bude asi malo") zmeneno na KAZDY TRETI. Na Doblu C to dela 4 razitka
# z 11 profilu, ktere se kvalifikuji, na Doblu A 5 ze 14.
KAZDY_NTY = 3
OKRAJ_MM = 40.0                 # razitko nesmi az na konec profilu (spoje)
MIN_DELKA_MM = LOGO_DELKA_MM + 2 * OKRAJ_MM   # kratsi profil se nerazitkuje
# Robert 2026-09-17 (pres bot3, PLAN_TVORBY_SESTAV.md "Pravidla razitka"): na
# JEDNOM profilu se dve loga nesmi potkat blize nez 500 mm od sebe - NAPRIC
# stenami (jiná stena téhož profilu se počítá stejně). Meri se VOLNA MEZERA
# mezi konci log podel osy profilu (ne vzdalenost stredu): stredy musi byt
# od sebe aspon LOGO_DELKA_MM + MIN_ROZESTUP_LOG_MM.
MIN_ROZESTUP_LOG_MM = 500.0

# Do 2026-09-11 tu byly dve konstanty (MAX_SOUBEZNOST_S_POHLEDEM,
# MIN_NATOCENI_STENY), ktere vyrazovaly profily/steny podle uhlu k JEDNOMU
# smeru pohledu kamery. Robert pres bot3: "razitka 3D budou ze vsech stran
# regalu tzn i shora a zezadu" - vyber steny se ted rozhoduje VYHRADNE podle
# GEOMETRIE profilu (ma ta stena volne misto a je exponovana ven), nikoli
# podle toho, odkud se zrovna kouka kamera. Obe konstanty proto NEMAJI
# smysluplnou nahradu - nejde o to je nahradit jinym prahem, jejich cely
# duvod existence (kompenzovat, ze se stenu vybirala jen jedna, ta k
# aktualnimu pohledu) zmizel spolu s pohledem samotnym. Viz
# vyber_profily_k_razitkovani() a PRAVIDLA_SPOJU.md.
#
# 4 lokalni normaly sten ctvercoveho prurezu profilu (30x30), STABILNI
# POŘADÍ napric profily - pouziva se jako klic "kazdy N-ty" hustoty
# NEZAVISLE PRO KAZDOU STENU (drive tuhle roli hral kazdy pohled zvlast).
KANDIDATNI_STENY_LOK = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, 0.0, -1.0))


# ---------------------------------------------------------------- vektory
def _rotuj(q, v):
    """Otoci vektor v kvaternionem q=[x,y,z,w] (stejna konvence jako
    THREE.Quaternion i data sestav)."""
    qx, qy, qz, qw = q
    vx, vy, vz = v
    # t = 2 * (q_vec x v)
    tx = 2.0 * (qy * vz - qz * vy)
    ty = 2.0 * (qz * vx - qx * vz)
    tz = 2.0 * (qx * vy - qy * vx)
    return (vx + qw * tx + (qy * tz - qz * ty),
            vy + qw * ty + (qz * tx - qx * tz),
            vz + qw * tz + (qx * ty - qy * tx))


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    d = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / d, a[1] / d, a[2] / d)


def _neg(a):
    return (-a[0], -a[1], -a[2])


def _kvaternion_z_baze(x_osa, y_osa, z_osa):
    """Rotace, ktera posle lokalni X/Y/Z na zadane svetove osy.

    POZOR (pravidlo z VLASTNOSTI_PROFILU.md): tri nezavisle zvolene osy by
    mohly dat zrcadleni. Volajici proto MUSI tretí osu dopocitat krizovym
    soucinem - tahle funkce uz jen prevadi ortonormalni bazi na kvaternion.
    """
    m00, m10, m20 = x_osa
    m01, m11, m21 = y_osa
    m02, m12, m22 = z_osa
    stopa = m00 + m11 + m22
    if stopa > 0.0:
        s = math.sqrt(stopa + 1.0) * 2.0
        return [(m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25 * s]
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        return [0.25 * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s]
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        return [(m01 + m10) / s, 0.25 * s, (m12 + m21) / s, (m02 - m20) / s]
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
    return [(m02 + m20) / s, (m12 + m21) / s, 0.25 * s, (m10 - m01) / s]


def smer_ke_kamere(azimut_deg, elevace_deg=0.0):
    """Doslovny port _cam_dir() z blender_render_turntable.py - jednotkovy
    smer STRED -> KAMERA v souradnicich prohlizece. Pro az=90 vychazi
    (1,0,0), tedy celni strana je ta s normalou +X."""
    el = math.radians(elevace_deg)
    az = math.radians(azimut_deg)
    return (math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az))


# ------------------------------------------------------------- vyber dilu
def _je_profil_30(part, profil_ids):
    return part.get("part_id") in profil_ids


def _delka_profilu(part):
    """Profil .glb je 1000 mm dlouhy podel LOKALNI osy Y, scale ho nataha."""
    return PROFIL_DELKA_ZAKLAD_MM * float((part.get("scale") or [1, 1, 1])[1])


def _nahodne_0_1(*klice):
    """Deterministicke 'nahodne' cislo z klicu. Stejna sestava musi dat
    stejne rozmisteni - jinak by kazdy render vysel jinak a dva snimky
    otocky by nesly porovnat."""
    h = hashlib.sha256("|".join(str(k) for k in klice).encode("utf-8")).hexdigest()
    return int(h[:12], 16) / float(0x1000000000000)


def vyber_profily_k_razitkovani(parts, assembly_id, profil_ids,
                                kazdy_nty=KAZDY_NTY, rozmery=None):
    """Vrati seznam (index, part, osa, normala_steny, lok_idx) pro KAZDOU
    STENU kazdeho profilu, ktera ma dostat razitko.

    Od 2026-09-11 (Robert pres bot3: razitka na vsechny strany regalu vcetne
    shora a zezadu) se NEROZHODUJE podle smeru pohledu kamery - kazda ze 4
    lokalnich sten kazdeho profilu (KANDIDATNI_STENY_LOK) se posuzuje
    NEZAVISLE, cistě geometricky:
      1. ma podel delky profilu souvisly volny usek na cely logo
         (_blokovane_useky/_volne_useky - uz drive pocitane PER STENA, ne
         per pohled, tak zustavaji beze zmeny);
      2. je EXPONOVANA VEN - z bodu na stene vede paprsek podel VLASTNI
         normaly steny ven ze sestavy, aniz by narazil na jiny dil
         (_je_videt, driv volany se smerem ke kamere, ted se smerem ven ze
         steny - stejna funkce, jiny smer paprsku).
    """
    if rozmery is None:
        rozmery = ROZMERY_DILU
    kandidati_dilu = []
    for i, p in enumerate(parts):
        if not _je_profil_30(p, profil_ids):
            continue
        if _delka_profilu(p) < MIN_DELKA_MM:
            continue
        q = p.get("quaternion") or [0, 0, 0, 1]
        osa = _norm(_rotuj(q, (0.0, 1.0, 0.0)))
        volnost = _delka_profilu(p) - 2.0 * OKRAJ_MM - LOGO_DELKA_MM
        ostatni_bez_razitek = [x for j, x in enumerate(parts) if j != i and not je_razitko(x.get("role"))]
        for lok_idx, lok in enumerate(KANDIDATNI_STENY_LOK):
            normala = _norm(_rotuj(q, lok))
            # Useky, kde na teto stene uz neco sedi (nosnik dosedajici celem,
            # spojka, uhelnik...). Bez toho by razitko padlo DO nej.
            volne = _volne_useky((volnost + LOGO_DELKA_MM) / 2.0,
                                 _blokovane_useky(p, osa, normala, ostatni_bez_razitek, rozmery))
            if not any((do - od) >= LOGO_DELKA_MM for od, do in volne):
                # Na teto stene neni souvisle misto pro cele logo. Vyradit
                # UZ TADY, tedy PRED pravidlem "kazdy treti" - kdyby se
                # vyradilo az pri vyrobe razitka, obsadilo by nepouzitelne
                # misto jeden ze slotu a razitko by se proste ztratilo.
                continue
            kandidati_dilu.append({"index": i, "part": p, "osa": osa, "normala": normala,
                                   "lok_idx": lok_idx, "volne_useky": volne})

    if not kandidati_dilu:
        return []

    # Zakryte steny pryc - paprsek VEN podel VLASTNI normaly steny (viz
    # docstring). Nahrazuje puvodni "paprsek ke kamere" (do 2026-09-11) i
    # jeste starsi heuristiku medianu hloubky - obe byly vazane na jeden
    # smer pohledu, ktery uz v tomhle vyberu neexistuje.
    exponovane = []
    for v in kandidati_dilu:
        p = v["part"]
        stred = p.get("position") or [0.0, 0.0, 0.0]
        # Bod, kde razitko realne lezi: stred steny, kousek nad povrchem.
        bod = tuple(stred[k] + v["normala"][k] * (PROFIL_POLOMER_MM + 1.0) for k in range(3))
        ostatni = [x for j, x in enumerate(parts) if j != v["index"]]
        if _je_videt(bod, v["normala"], ostatni, rozmery):
            exponovane.append(v)

    if not exponovane:
        return []

    # "Kazdy N-ty" hustota, NEZAVISLE PRO KAZDOU ze 4 lokalnich sten (drive
    # tuhle roli hral kazdy pohled zvlast - profil viditelny ze dvou pohledu
    # mohl dostat razitko na kazdou zvlast). Razeni je ted podle POZICE VE
    # STRUKTURE (vyska, pak X, pak Z), ne podle vodorovne souradnice obrazu -
    # ta bez jedne kamery neexistuje. Rovnomerny FYZICKY rozestup napric
    # regalem nahrazuje drivejsi rovnomerny rozestup na jednom snimku.
    vybrane = []
    for lok_idx in range(len(KANDIDATNI_STENY_LOK)):
        skupina = [v for v in exponovane if v["lok_idx"] == lok_idx]
        if not skupina:
            continue
        skupina.sort(key=lambda v: (round((v["part"].get("position") or [0, 0, 0])[1], 1),
                                    round((v["part"].get("position") or [0, 0, 0])[0], 1),
                                    round((v["part"].get("position") or [0, 0, 0])[2], 1),
                                    v["index"]))
        # Posun odvozeny ze sestavy A z lok_idx - aby razitka nezacinala u
        # vsech sestav (a u vsech 4 sten) na stejnem miste.
        posun = int(_nahodne_0_1("posun", assembly_id, lok_idx) * kazdy_nty)
        vybrane.extend(v for k, v in enumerate(skupina) if k % kazdy_nty == posun)
    return vybrane


def _stena_popis(normala, front_azimut_deg):
    """Popis steny CLOVEKU (predni/zadni/prava/leva/horni/dolni), relativne
    k PREDNIMU SMERU SESTAVY (`front_azimut_deg`).

    ⭐ Tohle NENI kriterium vyberu (ten je cely v vyber_profily_k_razitkovani,
    cistě geometricky, bez pojmu "predu"/"zadu") - je to jen CITELNY ZAPIS
    pokryti PO vyberu, aby se dalo z dat sestavy precist "ma tahle sestava
    razitka na vsech stranach", bez prepoctu geometrie (Robert pres bot3,
    2026-09-11: "zapsat razitkovane steny do receptu, do postupu, do DB").
    """
    if normala[1] >= 0.5:
        return "horni"
    if normala[1] <= -0.5:
        return "dolni"
    smer_predu = smer_ke_kamere(front_azimut_deg)
    smer_vpravo = _norm(_cross((0.0, 1.0, 0.0), smer_predu))
    kandidati = {"predni": smer_predu, "zadni": _neg(smer_predu),
                "prava": smer_vpravo, "leva": _neg(smer_vpravo)}
    return max(kandidati, key=lambda jmeno: _dot(normala, kandidati[jmeno]))


# --------------------------------------------------------------- razitko
# --- obsazenost steny (aby razitko nesedlo na misto, kde uz neco je) -----
# Robert: "zadne zanoreni" (⭐ nadrazene pravidlo ve VLASTNOSTI_PROFILU.md).
# Razitkovac hlidal jen KONCE profilu (OKRAJ_MM kvuli spojum), ale uz ne to,
# jestli na te stene neco NESEDI. Nezavisla revize (bot4, 2026-09-11) nasla,
# ze 9 ze 46 log na schvalenych sestavach je celou svou tloustkou (~2,9 mm)
# zanoreno do nosniku, ktery celem dosedá na tutez stenu svislice (T-spoj).
# Merene prekryvy 27,9 x 27-30 x 2,9 mm, tedy cele razitko uvnitr materialu.
LOGO_RELIEF_MM = 3.0            # o kolik logo vycniva nad rovinu steny
BLOK_REZERVA_MM = 3.0           # odstup razitka od ciziho dilu na stene
# Kdyz rozmer dilu neznáme (typicky prislusenstvi `product_*`, ktere v
# cfg_dily neni), odhadneme kvadr. Musi byt omezeny ve VSECH osach: puvodnich
# (80, 1000, 80) znamenalo metrovy kvadr kolem kazde zaslepky a uhelniku, coz
# zablokovalo skoro celou stenu a razitka mizela (namereno na 333: ze 46 log
# zbylo 29). Konzervativni != nekonecny.
ROZMER_NEZNAMY = (60.0, 60.0, 60.0)


# Zaklad tabulky rozmeru - profily, ktere se v sestavach vyskytuji nejcasteji
# (hodnoty z cfg_dily, dim_x x dim_y x dim_z; dim_y=1000 je referencni delka,
# skutecnou delku dela scale). Volajici, ktery ma pristup do DB, by mel poslat
# uplnou tabulku pres `rozmery_z_katalogu()` - tohle je zachranna sit, ne
# nahrada: neznamy dil se bere jako ROZMER_NEZNAMY, tedy radeji vetsi.
ROZMERY_DILU = {
    "Object_7": (30.0, 1000.0, 30.0),    # profil 30x30
    "Object_11": (40.0, 1000.0, 40.0),   # profil 40x40
    "Object_2": (45.0, 1000.0, 45.0),    # profil 45x45
    "Object_1": (30.0, 1000.0, 60.0),    # profil 30x60
    "Object_14": (40.0, 1000.0, 80.0),   # profil 40x80
}


def rozmery_z_katalogu(cur, katalog_dir):
    """{part_id: (dx, dy, dz)} pro VSECHNY katalogove dily, ktere se mohou
    objevit jako "ostatni" v _blokovane_useky/_je_videt (blokovaci/exponovani
    kontrola razitek).

    * `cfg_dily` (profily, spojky...) ma analyticke sloupce (dim_x/y/z_mm) -
      pouziji se primo.
    * `shop_products` (produkty, napr. eurobox) tyhle sloupce NEMA - rozmer
      se zmeri PRIMO Z .glb (trimesh, lokalni bounding box; stejna
      souradnicova konvence jako `position`/`quaternion` - overeno proti
      JS parseru `scripts/2026-08-19_glb_real_geometry.js`, shodne cislo na
      product_3788: [299,399,120] oběma cestami).

    ⭐ Bez tohohle VSECHNY produkty padaly na ROZMER_NEZNAMY=(60,60,60) mm -
    `rozmery_z_katalogu()` existovala, ale nikdy nebyla zapojena (zavedeno
    az 2026-09-11, bot16). Zmereno na rozsireni razitkovani na vsechny
    steny: eurobox `eurobox_400x300x120` (product_3788) tim vychazel 5-7x
    mensi nez skutecne je, blokovaci kontrola ho na sousedni stene profilu
    tise prehlizela a nove razitko s nim realne kolidovalo (odsun ~4mm,
    zmereno SAT+volumetric testem - viz AGENTS_LOG.md 2026-09-11).

    Dily bez rozmeru (chybejici/nenacitatelne .glb) se vynechavaji - padnou
    na ROZMER_NEZNAMY, coz je zamerne konzervativni.
    """
    out = dict(ROZMERY_DILU)

    cur.execute("SELECT id, dim_x_mm, dim_y_mm, dim_z_mm FROM cfg_dily "
                "WHERE dim_x_mm IS NOT NULL AND dim_y_mm IS NOT NULL AND dim_z_mm IS NOT NULL")
    for r in cur.fetchall():
        out[r["id"]] = (float(r["dim_x_mm"]), float(r["dim_y_mm"]), float(r["dim_z_mm"]))

    cur.execute("SELECT id, glb_file FROM shop_products WHERE glb_file IS NOT NULL AND glb_file != ''")
    produkty = cur.fetchall()
    if produkty:
        import warnings
        import trimesh
        warnings.filterwarnings("ignore")
        for r in produkty:
            pid = "product_%d" % r["id"]
            if pid in out:
                continue
            cesta = os.path.join(katalog_dir, r["glb_file"])
            if not os.path.exists(cesta):
                continue
            try:
                m = trimesh.load(cesta, force="scene").to_geometry()
                lo, hi = m.bounds
                out[pid] = (float(hi[0] - lo[0]), float(hi[1] - lo[1]), float(hi[2] - lo[2]))
            except Exception:
                continue   # nezmereno -> zustane ROZMER_NEZNAMY, konzervativni
    return out


def _obb_rohy(part, rozmery):
    """8 rohu dilu ve svetovych souradnicich (kvadr z katalogovych rozmeru).

    Zamerne analyticky, ne z .glb: tatáž funkce musi fungovat i nad RAW dily
    sestavy, kde zadna cesta k .glb neni (razitkovani pri zarazeni do stromu).
    """
    dx, dy, dz = rozmery.get(part.get("part_id"), ROZMER_NEZNAMY)
    sc = part.get("scale") or [1.0, 1.0, 1.0]
    hx, hy, hz = dx * float(sc[0]) / 2.0, dy * float(sc[1]) / 2.0, dz * float(sc[2]) / 2.0
    q = part.get("quaternion") or [0, 0, 0, 1]
    stred = part.get("position") or [0.0, 0.0, 0.0]
    rohy = []
    for zx in (-hx, hx):
        for zy in (-hy, hy):
            for zz in (-hz, hz):
                r = _rotuj(q, (zx, zy, zz))
                rohy.append((stred[0] + r[0], stred[1] + r[1], stred[2] + r[2]))
    return rohy


def _konjugovat(q):
    return [-q[0], -q[1], -q[2], q[3]]


def _paprsek_protne_kvadr(pocatek, smer, dil, rozmery, delka_max):
    """Protne polopřímka (pocatek, smer) kvadr dilu drive nez `delka_max`?

    Slab test v LOKALNI soustave kvadru - paprsek se do ni prevede zpetnou
    rotaci, cimz se z orientovaneho kvadru stane osove zarovnany.
    """
    dx, dy, dz = rozmery.get(dil.get("part_id"), ROZMER_NEZNAMY)
    sc = dil.get("scale") or [1.0, 1.0, 1.0]
    pul = (dx * float(sc[0]) / 2.0, dy * float(sc[1]) / 2.0, dz * float(sc[2]) / 2.0)
    stred = dil.get("position") or [0.0, 0.0, 0.0]
    qc = _konjugovat(dil.get("quaternion") or [0, 0, 0, 1])
    o = _rotuj(qc, (pocatek[0] - stred[0], pocatek[1] - stred[1], pocatek[2] - stred[2]))
    d = _rotuj(qc, smer)
    t_od, t_do = 0.0, delka_max
    for k in range(3):
        if abs(d[k]) < 1e-9:
            if abs(o[k]) > pul[k]:
                return False
            continue
        t1 = (-pul[k] - o[k]) / d[k]
        t2 = (pul[k] - o[k]) / d[k]
        if t1 > t2:
            t1, t2 = t2, t1
        t_od = max(t_od, t1)
        t_do = min(t_do, t2)
        if t_od > t_do:
            return False
    return t_do > 0.0


# Jak daleko od razitka se jeste hleda zakryvajici dil. Regál je radove
# metrove, takze 4 m bezpecne pokryje i nejdelsi pruhled skrz celou sestavu.
DOHLED_MM = 4000.0


def _je_videt(bod, pohled, ostatni, rozmery):
    """Je bod na stene videt z daneho smeru, nebo ho neco zakryva?

    ⭐ Tohle nahrazuje puvodni heuristiku "median hloubky" (brala se prednejsi
    polovina sestavy). Ta NENI test zakryti a kod si to sam priznaval v
    komentari. Na CELE fungovala nahodou - predni rám je opravdu vpredu - ale
    na BOKU propoustela vnitrni svislice uprostred regalu, ktere zvenci
    zakryva krajni noha. Revize (bot4, 2026-09-11) to zmerila: na 333 bylo
    jedine bocni razitko vidět z uhlu 180-220 na 0-2 %, a 17 z 81 snimku
    otocky nemelo jedine citelne razitko.
    """
    for o in ostatni:
        if je_razitko(o.get("role")):
            continue
        if _paprsek_protne_kvadr(bod, pohled, o, rozmery, DOHLED_MM):
            return False
    return True


def _blokovane_useky(host, osa, normala, ostatni, rozmery):
    """Useky podel osy hostitele (v tomtez `t` jako razitko), kde na stene
    uz neco sedi. Vraci seznam (od, do), neserazeny."""
    stred = host.get("position") or [0.0, 0.0, 0.0]
    bok = _norm(_cross(normala, osa))           # treti osa lokalni baze
    # Blokator musi VYCNIVAT nad rovinu steny, ne se ji jen zevnitr dotykat.
    # Puvodnich `- 1.0` chytalo i nosniky pripojene k JINE stene hostitele:
    # jejich kvadr saha skrz cely prurez profilu, takze `max(w)` je presne
    # 15 a test je oznacil za blokujici. Nosnik, ktery opravdu dosedá celem
    # na TUHLE stenu, ma max(w) radove stovky mm, takze se chyta dal.
    w_min = PROFIL_POLOMER_MM + 0.5
    w_max = PROFIL_POLOMER_MM + LOGO_RELIEF_MM + 2.0
    v_mez = LOGO_VYSKA_MM / 2.0 + 2.0
    useky = []
    for o in ostatni:
        rohy = _obb_rohy(o, rozmery)
        us, vs, ws = [], [], []
        for r in rohy:
            d = (r[0] - stred[0], r[1] - stred[1], r[2] - stred[2])
            us.append(_dot(d, osa)); vs.append(_dot(d, bok)); ws.append(_dot(d, normala))
        if max(ws) < w_min or min(ws) > w_max:
            continue                            # neni u teto steny
        if max(vs) < -v_mez or min(vs) > v_mez:
            continue                            # mimo sirku razitka
        useky.append((min(us) - BLOK_REZERVA_MM, max(us) + BLOK_REZERVA_MM))
    return useky


def _volne_useky(polovina_volnosti, blokovane):
    """Z rozsahu <-polovina, +polovina> odecte blokovane useky."""
    volne = [(-polovina_volnosti, polovina_volnosti)]
    for b_od, b_do in blokovane:
        nove = []
        for od, do in volne:
            if b_do <= od or b_od >= do:
                nove.append((od, do)); continue
            if b_od > od:
                nove.append((od, b_od))
            if b_do < do:
                nove.append((b_do, do))
        volne = nove
    return [(od, do) for od, do in volne if do > od]


def _je_text_o_180_stupnu(normala, osa, y_osa_pred_korekci):
    """Rozhoduje, jestli je potreba otocit bazi razitka o 180 stupnu kolem
    normaly, aby text LOGIMAN.CZ cetl spravne (ne pozpatku/vzhuru nohama).
    Nejde o zrcadleni - determinant baze je vzdy +1, zrcadleni touhle
    konstrukci nejde vyrobit (viz VLASTNOSTI_PROFILU.md).

    OBECNE PRAVIDLO (bot8, 2026-09-12, nahrazuje drivejsi cistou empiricku
    tabulku): kdyz je "nahoru pro pismena" (y_osa PRED pripadnou korekci)
    jednoznacne urcitelne gravitaci (ma vyraznou slozku podel svetove osy
    Y), musi mit KLADNOU Y slozku - jinak jsou pismena vzhuru nohama. Tenhle
    test je mechanicky overitelny (ne odhad) a funguje pro JAKOUKOLI stenu,
    ne jen pro rucne vyjmenovane kombinace.

    Duvod prechodu z puvodni tabulky (bot9, 2026-09-12): puvodni pravidlo
    tvrdilo "zadni stena + vodorovny profil (osa k Z) = SPRAVNA", ale primy
    vypocet na cerstve vygenerovanych razitkach (bot8, K-075 serie 341-347)
    ukazal y_osa=(0,-1,0) pro presne tenhle pripad - text vzhuru nohama,
    Robert to potvrdil vizualne ve scene ("zezadu obracene"). Puvodni
    tabulka byla odvozena empiricky jen z tehdy existujicich 87 razitek/9
    sestav - nova generace razitek trefila kombinaci mimo tenhle vzorek.

    Kdyz gravitace NEROZHODUJE (stena horni/dolni, NEBO je i profil svisly -
    y_osa lezi v rovine bez Y slozky), gravitaci zalozeny test nema co rict
    - pouzije se puvodni, renderem overena tabulka pro tyhle konkretni
    zbyle pripady:
      * "horni" stena (normala k svetovemu +Y): SPATNE pro kazdou osu
        profilu.
      * "zadni" stena (normala k -X) A soucasne svisly profil (osa k
        svetovemu +Y): SPATNE.
    Kdyby se objevil dalsi gravitacne-nerozhodny pripad mimo tyhle dva
    (napr. "dolni" stena, nebo svisly profil na "leva"/"prava" stene),
    over renderem znovu - tabulka pro ne dosud neexistuje.
    """
    dot_gravitace = y_osa_pred_korekci[1]
    if abs(dot_gravitace) > 0.5:
        return dot_gravitace < 0.0
    if _dot(normala, (0.0, 1.0, 0.0)) > 0.9:
        return True
    if _dot(normala, (-1.0, 0.0, 0.0)) > 0.9 and _dot(osa, (0.0, 1.0, 0.0)) > 0.9:
        return True
    return False


def _povolene_useky(useky, zakazane_stredy):
    """Z intervalu pripustnych STREDU loga [(od, do)] odecte zakazana okoli
    stredu log, ktera uz na TEMZ profilu lezi (MIN_ROZESTUP_LOG_MM, viz
    konstanta). Vraci seznam zbylych intervalu (muze byt prazdny)."""
    min_stredy = LOGO_DELKA_MM + MIN_ROZESTUP_LOG_MM
    vysledek = list(useky)
    for s in zakazane_stredy:
        zak_od, zak_do = s - min_stredy, s + min_stredy
        nove = []
        for od, do in vysledek:
            if do <= zak_od or od >= zak_do:
                nove.append((od, do))
                continue
            if od < zak_od:
                nove.append((od, zak_od))
            if do > zak_do:
                nove.append((zak_do, do))
        vysledek = nove
    return vysledek


def _razitko_pro_profil(v, assembly_id, logo_glb, vypln_glb, vzor_part,
                        poradi, stena_popis, stredy_na_profilu=()):
    """Vyrobi dvojici dilu (vypln drazky + logo) pro jeden profil.

    `stredy_na_profilu`: pozice `t` (podel osy) log, ktera uz na TEMZ profilu
    lezi z drivejsich sten. Nove logo musi byt od kazdeho z nich aspon
    MIN_ROZESTUP_LOG_MM (volna mezera); kdyz na stene takove misto neni,
    vraci [] (razitko se vynecha). Vysledne `t` vraci v klici "_t" loga."""
    p = v["part"]
    osa, normala = v["osa"], v["normala"]
    stred = p.get("position") or [0.0, 0.0, 0.0]
    delka = _delka_profilu(p)

    # Baze razitka: X = podel profilu, Z = ven ze steny, Y = dopocitano
    # krizovym soucinem (nikdy nevolit vsechny tri nezavisle).
    x_osa = osa
    z_osa = normala
    y_osa = _norm(_cross(z_osa, x_osa))
    x_osa = _norm(_cross(y_osa, z_osa))
    if _je_text_o_180_stupnu(normala, osa, y_osa):
        # Otoceni cele baze o 180 stupnu KOLEM normaly (ne zrcadleni -
        # determinant zustava +1): text pak cte spravne. Viz docstring
        # _je_text_o_180_stupnu.
        x_osa, y_osa = _neg(x_osa), _neg(y_osa)
    q = _kvaternion_z_baze(x_osa, y_osa, z_osa)

    # Nahodna pozice po delce, ale v ramci pouzitelneho useku (mimo okraje)
    # A MIMO MISTA, KDE UZ NA STENE NECO SEDI.
    #
    # Do 2026-09-11 se hlidaly jen KONCE profilu (OKRAJ_MM) a `t` se volilo
    # volne v celem zbytku. Revize (bot4) namerila, ze tim 9 ze 46 log padlo
    # CELOU SVOU TLOUSTKOU do nosniku, ktery celem dosedá na tutez stenu -
    # tedy porusenim nadrazeneho pravidla "zadne zanoreni", ne kosmetikou.
    volnost = delka - 2.0 * OKRAJ_MM - LOGO_DELKA_MM
    # lok_idx (index steny, 0-3) je v klici, aby stejny profil orazitkovany
    # na vice stenach nemel razitka na kazde ve stejne vysce - drive tu byl
    # `azimut` (index POHLEDU), ktery zanikl spolu s vyberem podle kamery.
    # Klic NAHODY je jinak GEOMETRICKY, ne poradove: drive tu byl v["index"],
    # tedy poradi dilu v `data.parts`. Preusporadani sestavy (cimz se
    # geometricky nic nemeni) tim razitka prehazovalo jinam. Determinismus
    # ma platit vuci OBSAHU sestavy, ne vuci poradi radku. (bot4, 2026-09-11)
    klic_dilu = tuple(round(float(c), 1) for c in (p.get("position") or [0, 0, 0]))
    r = _nahodne_0_1("pozice", assembly_id, klic_dilu, v["lok_idx"])
    volne = v.get("volne_useky")
    if volne is None:
        t = (r - 0.5) * volnost
        stredove_useky = [(-volnost / 2.0, volnost / 2.0)]
    else:
        # Razitko se vejde jen tam, kde je souvisly volny usek delsi nez logo.
        pouzitelne = [(od, do) for od, do in volne if (do - od) >= LOGO_DELKA_MM]
        if not pouzitelne:
            return []                      # na tehle stene neni kam - vynechat
        # Nejdelsi usek (deterministicky; pri shode rozhodne levejsi).
        od, do = max(pouzitelne, key=lambda u: (u[1] - u[0], -u[0]))
        stred_od = od + LOGO_DELKA_MM / 2.0
        stred_do = do - LOGO_DELKA_MM / 2.0
        t = stred_od + r * (stred_do - stred_od)
        stredove_useky = [(u_od + LOGO_DELKA_MM / 2.0, u_do - LOGO_DELKA_MM / 2.0)
                          for u_od, u_do in pouzitelne]

    # Rozestup log na temz profilu (Robert 2026-09-17, viz MIN_ROZESTUP_LOG_MM).
    # Puvodni `t` zustava, kdyz rozestup splnuje - pravidlo jen PRIDAVA
    # podminku, nemeni rozmisteni tam, kde nebylo porusene.
    min_stredy = LOGO_DELKA_MM + MIN_ROZESTUP_LOG_MM
    if any(abs(t - s) < min_stredy - 1e-6 for s in stredy_na_profilu):
        povolene = _povolene_useky(stredove_useky, stredy_na_profilu)
        povolene = [(u_od, u_do) for u_od, u_do in povolene if u_do - u_od >= 0.0]
        if not povolene:
            return []                      # na tehle stene uz neni misto dost daleko od jineho loga
        # Deterministicky: nejdelsi povoleny interval, v nem pozice podle stejneho `r`.
        u_od, u_do = max(povolene, key=lambda u: (u[1] - u[0], -u[0]))
        t = u_od + r * (u_do - u_od)

    def _bod(vzdalenost_od_osy):
        return [stred[k] + osa[k] * t + normala[k] * vzdalenost_od_osy
                for k in range(3)]

    # Robert 2026-09-10: "logo i vypln drazky nech maji material hlinik jako
    # profily". Material se proto NEVYRABI, ale KOPIRUJE z profilu, na kterem
    # razitko sedi - vcetne pripadneho TT_ALU ze sablony, kterou si Robert
    # naladil v Blenderu na VPS. Vlastni trojice cisel by se s ni casem
    # rozesla.
    spolecne = {
        "layer": vzor_part.get("layer"),
        "color_hex": vzor_part.get("color_hex"),
        "base_color": vzor_part.get("base_color"),
        "metalness": vzor_part.get("metalness"),
        "roughness": vzor_part.get("roughness"),
    }

    # Vypln: pivot uprostred hloubky -> stred lezi 10 mm od osy, cimz
    # horni plocha padne presne na povrch profilu (15 mm).
    vypln = dict(spolecne)
    vypln.update({
        "part_id": VYPLN_PART_ID,
        "glb": vypln_glb,
        "position": _bod(PROFIL_POLOMER_MM - DRAZKA_HLOUBKA_MM / 2.0),
        "quaternion": q,
        "scale": [VYPLN_DELKA_MM / VYPLN_DELKA_ZAKLAD_MM, 1.0, 1.0],
        "role": ROLE_VYPLN % poradi,
        "alpha": VYPLN_ALFA,
        "stena": stena_popis,
    })

    # Logo: prilehajici strana lici s povrchem profilu. Barva NENI
    # kopie z profilu (na rozdil od vypln vyse) - viz LOGO_BARVA_HEX.
    logo = dict(spolecne)
    logo.update({
        "part_id": LOGO_PART_ID,
        "glb": logo_glb,
        "position": _bod(PROFIL_POLOMER_MM + LOGO_ODSAZENI_PIVOTU_MM),
        "quaternion": q,
        "scale": [1.0, 1.0, 1.0],
        "role": ROLE_LOGO % poradi,
        "color_hex": LOGO_BARVA_HEX,
        "base_color": LOGO_BASE_COLOR,
        "metalness": LOGO_METALNESS,
        "roughness": LOGO_ROUGHNESS,
        "transmission": LOGO_TRANSMISSION,
        "ior": LOGO_IOR,
        "stena": stena_popis,
        "_t": t,
    })
    return [vypln, logo]


def orazitkuj(parts, front_azimut_deg, assembly_id, katalog_dir,
              profil_ids=("Object_7", "Object_8", "Object_9"),
              kazdy_nty=KAZDY_NTY, rozmery=None):
    """Vrati NOVE dily k pridani do sestavy (vypln drazky + logo).

    `parts` uz musi byt resolvovane (maji `glb` a materialove klice).
    Puvodni seznam se nemeni.
    """
    logo_glb = os.path.join(katalog_dir, "logo_logiman_cz.glb")
    vypln_glb = os.path.join(katalog_dir, "vypln_drazky_30.glb")
    if not os.path.exists(logo_glb) or not os.path.exists(vypln_glb):
        return [], "chybi %s nebo %s" % (os.path.basename(logo_glb),
                                         os.path.basename(vypln_glb))

    # Robert 2026-09-10: "ze stran tzn zboku dejme take kazdy treti, z obou
    # stran, tzn na nohach". Robert 2026-09-11 (pres bot3), po prvni davce:
    # "razitka 3D budou ze vsech stran regálů tzn i shora a zezadu" -
    # razitkuje se ted na VSECHNY POUZITELNE STENY KAZDEHO PROFILU, vybirane
    # CISTE GEOMETRICKY (viz vyber_profily_k_razitkovani), ne podle smeru
    # pohledu kamery. `front_azimut_deg` uz neni smer vyberu - pouziva se jen
    # k CITELNEMU POPISU steny (predni/zadni/prava/leva/horni/dolni, viz
    # _stena_popis), ktery se zapisuje ke kazdemu razitku.
    kandidati = vyber_profily_k_razitkovani(parts, assembly_id, set(profil_ids), kazdy_nty,
                                            rozmery if rozmery is not None else ROZMERY_DILU)

    nove = []
    poradi = 0
    stredy_log = {}   # index profilu -> pozice `t` uz umistenych log (napric stenami)
    for v in kandidati:
        stena_popis = _stena_popis(v["normala"], front_azimut_deg)
        dvojice = _razitko_pro_profil(v, assembly_id, logo_glb, vypln_glb,
                                      v["part"], poradi, stena_popis,
                                      stredy_log.get(v["index"], ()))
        if not dvojice:
            continue      # na stene neni volne misto - poradi se nezvysuje
        stredy_log.setdefault(v["index"], []).append(dvojice[1].pop("_t"))
        nove.extend(dvojice)
        poradi += 1
    return nove, None


# ------------------------------------------------- otisk vstupu razitkovani
# Verze PRAVIDEL razitkovani. Zvedni ji, kdykoli se zmeni, KDE nebo KOLIK
# razitek vznika (KAZDY_NTY, vyber sten, rozmery loga...). Otisk se tim
# zneplatni u vsech sestav najednou a prerazitkuji se pri dalsim zarazeni -
# bez toho by stare sestavy navzdy drzely razitka podle starych pravidel a
# nikdo by to nepoznal.
# v2 (2026-09-11): zmenila se PRAVIDLA umisteni - pribyl test zakryti misto
# medianu hloubky, kontrola obsazenosti steny a razeni podle vodorovne osy
# obrazu. Stare otisky proto musi prestat platit, jinak by uz orazitkovane
# sestavy navzdy drzely razitka podle starych pravidel a nikdo by to nepoznal.
# v3 (2026-09-11): logo dostalo barvu (LOGO_BARVA_HEX, "lehce oranzovou" -
# Robert pres bot3) - stare otisky (bezbarve logo) proto musi prestat
# platit.
# v4 (2026-09-11): Robert po prvnim snimku rozhodl "vyraznejsi" - barva
# zmenena z kandidata A (#C97A3D) na kandidata C (#D4863F, "jasnejsi
# ambra"). Stare otisky (stara barva) musi prestat platit.
# v5 (2026-09-11): Robert: "razitka 3D budou ze vsech stran regálů tzn i
# shora a zezadu". Vyber steny se PRESTAL rozhodovat podle smeru pohledu
# kamery (zaniklo `pohledy`, `MAX_SOUBEZNOST_S_POHLEDEM`,
# `MIN_NATOCENI_STENY`) - kazda ze 4 sten kazdeho profilu se posuzuje
# nezavisle podle geometrie (viz vyber_profily_k_razitkovani). Kazde razitko
# navic nese `stena` (predni/zadni/prava/leva/horni/dolni), viz
# _stena_popis - zapis pokryti "do receptu, do postupu, do DB" (Robert pres
# bot3). Pocet razitek na sestavu roste cca 4x (byval z 1-3 sten, ted ze
# vsech pouzitelnych ~4). Stare otisky (jedna/tri steny, bez `stena` klice)
# proto musi prestat platit.
# v6 (2026-09-12): barva loga zmenena z kandidata C na kandidata D (viz
# LOGO_BARVA_HEX vyse, "vice oranzovou ne do cervena"). Stare otisky
# (stara barva) proto musi prestat platit.
# v7 (2026-09-17): Robert (pres bot3) - na jednom profilu nejmene
# MIN_ROZESTUP_LOG_MM (500 mm volne mezery) mezi logy napric stenami. Loga
# se tim posouvaji/vynechavaji - stare otisky proto musi prestat platit.
OTISK_VERZE = 7


def otisk_sestavy(parts, kazdy_nty=KAZDY_NTY):
    """Otisk VSTUPU razitkovani - `sha256` hex.

    K cemu: ulozi se vedle razitek do dat sestavy. Pri kazdem dalsim ulozeni
    / zarazeni se prepocita a porovna:
      * shodny  -> razitka jsou aktualni, NEDELA SE NIC (idempotence: opakovane
                   zarazeni ani preraceni mezi slozkami druhou sadu nevyrobi,
                   protoze slozka do otisku nevstupuje);
      * jiny    -> sestava se od orazitkovani ZMENILA, stara razitka pryc a
                   razitkuje se znovu (jinak by razitka sedela na profilech,
                   ktere uz neexistuji).

    ⭐ POCITA SE BEZ RAZITKOVYCH DILU. Tohle je jediná past celeho mechanismu:
    kdyby razitka do otisku vstupovala, pridani razitek by otisk zmenilo, pri
    dalsim pruchodu by nesedel, razitka by se vyhodila a udelala znovu - a tak
    porad dokola. Mechanismus by nikdy nezkonvergoval.

    Predni azimut se nezapocitava zvlast: odvozuje se z role-tagovanych dilu,
    ktere v otisku uz jsou. Zaokrouhluje se na 0,1 mm / 5 desetinnych mist,
    aby otisk neskakal kvuli sumu v plovouci carce.
    """
    polozky = []
    for p in parts:
        if je_razitko(p.get("role")):
            continue
        pos = [round(float(x), 1) for x in (p.get("position") or [0, 0, 0])]
        quat = [round(float(x), 5) for x in (p.get("quaternion") or [0, 0, 0, 1])]
        scale = [round(float(x), 5) for x in (p.get("scale") or [1, 1, 1])]
        polozky.append("%s|%s|%s|%s|%s" % (p.get("part_id"), p.get("role") or "",
                                           pos, quat, scale))
    polozky.sort()
    zaklad = "v%d|n%d|%s" % (OTISK_VERZE, kazdy_nty, "\n".join(polozky))
    return hashlib.sha256(zaklad.encode("utf-8")).hexdigest()


def stav_razitek(data, kazdy_nty=KAZDY_NTY):
    """Rozhodne, v jakem stavu jsou razitka sestavy. Vraci jeden z retezcu:

      "zadna"     - v datech nejsou zadne razitkove dily
      "aktualni"  - razitka jsou a otisk sedi na dnesni podobu sestavy
      "zastarala" - razitka jsou, ale sestava se od orazitkovani zmenila
                    (nebo otisk chybi uplne - tak vypada rucne vlozene
                    razitko, napr. sestava 134 ze dema 2026-09-08)

    `data` = rozparsovany obsah `product_assemblies.data`.
    Sdilena funkce zamerne: prehled vyroby v adminu i samotny spoustec
    potrebuji TOTEZ rozhodnuti, ne dve ruzna.
    """
    parts = (data or {}).get("parts") or []
    if not any(je_razitko(p.get("role")) for p in parts):
        return "zadna"
    ulozeny = ((data or {}).get("razitka") or {}).get("otisk")
    if not ulozeny:
        return "zastarala"
    return "aktualni" if ulozeny == otisk_sestavy(parts, kazdy_nty) else "zastarala"


# ------------------------------------------------- razitkovani DAT SESTAVY
def predni_azimut(parts, step_deg=10):
    """Predni smer sestavy z role-tagovanych dilu. None = nelze urcit.

    JEDINY zdroj tehle matematiky. `2026-09-09_turntable_job.py`
    (compute_front_azimuth_deg) i spoustec razitkovani v API ji volaji
    odsud - dve kopie by se casem rozesly a razitka by pak sedela na jine
    strane regalu, nez ke ktere se otaci kamera.
    JS protejsek: computeFrontAzimuthDeg ve webapp/scene.html.

    Role se porovnava BEZ pripony "-noha<i>" (konvence K-020 rebuildu
    2026-09-17, postup_stavby_regalu_krok_za_krokem_2026_09_17 krok 14) -
    presny match na "predni-svislice"/"cap" bez normalizace tise vracel
    None pro KAZDOU takhle pojmenovanou sestavu (nalezeno bot3/bot5 na
    sestave 538: razitkovac hlasil "nelze orientovat"). Stejna trida chyby
    jako u horni_ram.js/addDorazovaDeska driv dnes - normalizovat na OBOU
    stranach kazdeho srovnani role, ne jen pri vyberu kandidatu.
    """
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
    return int(round(az / step_deg) * step_deg) % 360


# Klice, ktere ma smysl mit na dilu RENDERU, ale ne v datech sestavy:
# absolutni cesta k .glb a materialove hodnoty. V datech sestavy se dil
# identifikuje `part_id` a material si scena vezme z katalogu sama - kdyby
# tu zustala zapecena kopie, rozesla by se s katalogem pri prvni zmene barvy.
_JEN_PRO_RENDER = ("glb", "layer", "color_hex", "base_color", "metalness", "roughness",
                   "transmission", "ior")


def orazitkuj_data_sestavy(parts, assembly_id, katalog_dir, kazdy_nty=KAZDY_NTY, rozmery=None):
    """Razitka ve tvaru, ktery patri do `product_assemblies.data.parts`.

    Vraci (nove_parts, chyba). Geometrie je TATAZ jako u renderu - pocita ji
    `orazitkuj` - jen se z vysledku odstrani klice, ktere v datech sestavy
    nemaji co delat (viz _JEN_PRO_RENDER).

    Vstupni `parts` jsou RAW dily sestavy (bez `glb`), coz `orazitkuj` zvlada:
    vybira podle `part_id`, delku bere ze `scale`.

    `rozmery`: {part_id: (dx,dy,dz)} pro blokovaci/exponovani kontrolu -
    volajici s pristupem do DB by mel poslat `rozmery_z_katalogu(cur,
    katalog_dir)` (presne merene rozmery vc. produktu jako eurobox), jinak
    se pouzije jen mala zachranna tabulka `ROZMERY_DILU` (viz tam - vede k
    nepresnostem u vsech `product_*` dilu).
    """
    front = predni_azimut(parts)
    if front is None:
        return [], ("sestavu nelze orientovat - chybi role-tagovane dily "
                    "(predni-svislice + cap/zadni-svislice), razitka by mohla "
                    "vyjit na spatne strane")
    nove, chyba = orazitkuj(parts, front, assembly_id, katalog_dir, kazdy_nty=kazdy_nty, rozmery=rozmery)
    if chyba:
        return [], chyba
    for d in nove:
        for k in _JEN_PRO_RENDER:
            d.pop(k, None)
    return nove, None


def prerazitkuj(data, assembly_id, katalog_dir, kazdy_nty=KAZDY_NTY, rozmery=None):
    """Razitkovani JAKO CELEK nad daty sestavy. Vraci (nova_data, zprava).

    * razitka uz jsou a otisk sedi -> vrati puvodni data beze zmeny
      (IDEMPOTENCE - opakovane zarazeni, preraceni mezi slozkami ani druhe
      ulozeni druhou sadu nevyrobi);
    * jinak -> stara razitka pryc, orazitkuje se znovu, ulozi novy otisk.

    Poradi je zamerne: NEJDRIV se stara razitka odstrani a teprve z ocisteneho
    seznamu se pocita otisk i nova razitka. Kdyby se razitkovalo "pres"
    stavajici, rostla by sada s kazdym pruchodem.

    `rozmery`: viz orazitkuj_data_sestavy - poslat `rozmery_z_katalogu(cur,
    katalog_dir)`, kdyz je `cur` po ruce.
    """
    data = dict(data or {})
    parts = list(data.get("parts") or [])
    stav = stav_razitek(data, kazdy_nty)
    if stav == "aktualni":
        return data, "razitka uz jsou aktualni (otisk sedi) - nic se nemeni"

    ciste = [p for p in parts if not je_razitko(p.get("role"))]
    odebrano = len(parts) - len(ciste)
    nove, chyba = orazitkuj_data_sestavy(ciste, assembly_id, katalog_dir, kazdy_nty, rozmery)
    if chyba:
        return None, chyba
    data["parts"] = ciste + nove
    data["razitka"] = {"otisk": otisk_sestavy(ciste, kazdy_nty),
                       "pocet": len(nove), "verze": OTISK_VERZE}
    return data, ("orazitkovano: %d dilu razitek (%d starych odebrano, stav pred: %s)"
                  % (len(nove), odebrano, stav))
