"""JADRO generatoru OCHRANNY KRYT A OPLOCENI z profilu 40x40 (bot8, 2026-10-08; Robert: "udelej mezitim generator na ochranneho oploceni a krytovani stroju z profilu 40x40", fotka klece kolem
piskovaciho stroje). FAZE 1 = jen jadro (geometrie, kusovnik, entries pro cenu); GLB je v oploceni_glb.py, shop vrstva (verejne API, registr, stranka, karty) je fazi 2 (viz README.md).

CO TO JE: jeden generator s OBDELNIKOVYM pudorysem (sirka X, hloubka Z, vyska Y); kazda ze 4 stran (celo, prava, zadni, leva) je `stena` (ram z profilu + vyplne), `dvere` (krizdlove dvere
v jednom poli steny) nebo `otevreno` (bez steny: z jednoho generatoru jde udelat i prosté OPLOCENI - jedna strana = rada poli, L, U); strecha `zadna` / `ram` / `vyplne`; vyplne cira / kourova
polykarbonat, plexisklo, sit, plna (pro celek, kazdou stranu a strechu zvlast). Profil = SuperLight S10 40x40 (karta #3468, SKU 1.1.10.040040.03, dil `Object_11`, slot 10 mm).

SOURADNICE: x = sirka (zleva doprava pri pohledu na CELO zvenku), y = nahoru (podlaha 0), z = hloubka; CELO je v rovine z = D (pohled zvenku: x roste doprava), ZADNI z = 0, LEVA x = 0, PRAVA x = W.
`u` = poloha podel steny meřena zleva pri pohledu na stenu ZVENKU (celo u = x, prava u = D - z, zadni u = W - x, leva u = z) - v ni se zadava poloha dveri a strana zavesu.

KONSTRUKCE (rozhodnuti navrhu, vse NAVRH k potvrzeni Robertem):
 * ROHOVE sloupky jdou od podlahy / patky az po vrch, MEZILEHLE sloupky konci pod SOUVISLOU horni prickou (dosednou na jeji spodni plochu): strechou tak prochazeji jen rohove sloupky a strechni
   pricky / vyplne nikdy nenaraziji na sloupek, at lezi kde lezi. Dolni pricky, mezipricky a nadpraz dveri jsou kusy MEZI sloupky. Vsechny spoje drzi rohove spojky 40x40
   (karta #3176) v ucelu: jedna spojka v kazdem vnitrnim uhlu spoje (L-roh 1 ks, T-spoj 2 ks). Poloha spojky je ODVOZENA ze sablony stolu systemu 40 (stejny dil, stejny tvar): spojka lezi v UHLU mezi
   dosedajicim profilem B a plochou nosneho profilu, jeji dve nozky (3,43 mm) zasahuji do dražek obou profilu a blok 37 x 37 mm lezi v rovine drazek (viz _spojka a testy proti sablone).
 * VYPLN je vsazena do DRAZKY profilu (drazka lezi ve stredove rovine profilu = vyplne ve stredove rovine steny, jak je to na fotce): okraj vyplne zasahuje do kazde drazky o INS = 9 mm, tenke tabule
   (polykarbonat, plexi) sedi v tesneni na sklo (karta #3218, delka = obvod otvoru). Protoze spojky lezi v ROVINE vyplne (blok 37 x 37 mm v kazdem rohu pole), ma vyplň v kazdem rohu VYREZ
   (tvar kriz: 3 kvadry): to je obvyklý zpusob u tabuli v drazce a ve 3D se tim zadne dily nezanori.
 * Dolni pricka je jen u poli (u dveri zadny prah). Dvere: ram krídla ze 4 profilu 40x40 (+ mezipricka, kdyz svetla vyska krídla > MID_MAX), vyplne, 3 zavesy "Pant 40x40" (leva #3645 / prava #3644)
   na VNEJSI strane (osa cepu v mezere 3 mm mezi sloupkem a stojkou krídla), otevírani ven, zavreni zapadkou (#3298) nebo bezpecnostnim zamkem (#3423): dil lezi PLOSNE na vnejsi plose volne stojky
   krídla (ORIENTACNE - nemame vyrobni vykres montaze); nad dvermi vzdy nadpraz (prícka + pole s vyplni), aby spojky nelezely v otvoru dveri.
 * Strecha `vyplne` = vyplne v rovine horniho ramu (stredova rovina horních profilu), pri sirsim nez POLE_MAX se pridaji strechni pricky (mrizka).
 * Patky (volitelne): stavitelna patka M10 (#3283) pod kazdym sloupkem, sloupky o vysku patky kratsi (celkova vyska vyska zustava).
 * Zaslepka 40x40 (#3091) na volnych koncich sloupku a stojek dveri.

MEZE (pravidla rozpeti): max svetla sirka pole POLE_MAX = 1200 mm, max svetla vyska pole MID_MAX = 1100 mm (jinak mezilehly sloupek / mezipricka), sirka 600-6000, hloubka 600-6000, vyska 1000-3000,
dvere 600-1200 x 1500-2400 (nadpraz svetlosti aspon 150 mm => dvere vyzaduji vysku aspon 1750 mm + vyska patek); ochranne oplocení musi splnit ČSN EN ISO 14120 / 13857 - generator resi KONSTRUKCI, ne
posouzeni bezpecnosti stroje (upozorneni).

VYSTUP `sestav_oploceni(**p)`: {parametry, dily (umistene katalogove dily + metadata), vyplne (kazde pole: otvor + kusy kvadru), spoje, entries (pro configurator_price.price_entries), kusovnik,
extra_prace (tesneni), rozmery, upozorneni}. Chyba vstupu / neproveditelna kombinace = OploceniChyba (kod, text).
"""
import hashlib
import json
import math
import os
import struct
from collections import OrderedDict

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KATALOG_DIR = os.environ.get("OPLOCENI_KATALOG") or os.path.join(REPO, "webapp", "katalog")
VERZE_PRAVIDEL = "2026-10-08.1"

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# konstanty
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
PROFIL = 40.0                      # prurez profilu (mm); GLB `Object_11`: X x Z = 40 x 40, delka podel lokalni Y (1000 mm, delka = scale[1])
PROFIL_PART = "Object_11"          # SuperLight S10 40x40 (karta #3468, SKU 1.1.10.040040.03)
PROFIL_KARTA = 3468
SPOJKA = "product_3176"            # "40x40 Rohova spojka" (SKU 2.2.001.10.4040.33)
ZASLEPKA = "product_3091"          # "Zaslepka 40x40 S10"
PANT_PRAVY, PANT_LEVY = "product_3644", "product_3645"          # "Pant 40x40 (pravy / levy)"
PATKA = "product_3283"             # "Vyrovnavaci sroubovaci patka M10"
ZAPADKA, ZAMEK = "product_3298", "product_3423"                   # kulickova zapadka / bezpecnostni zamek (maly)
TESNENI_SKLO, TESNENI_MEKKE = "product_3218", "product_3199"      # tesneni na sklo (drazka 10, pruhledna) / mekke tesneni drazky (cerne)

BLOK = 37.0                        # blok rohove spojky (lokalni x 0..37, y -37..0, z 0..37), nozky 3,43 mm do drazek (lokalni x -3,43..0, y -40,43..-37)
TAB = 3.43
INS = 9.0                          # zasunuti vyplne do drazky (mm)
VYREZ = INS + BLOK + 1.0           # strana vyrezu v rohu vyplne (mm, od rohu tabule): zasunuti + blok spojky + 1 mm vule
POLE_MAX = 1200.0                  # nejvetsi svetla sirka pole (mm)
MID_MAX = 1100.0                   # nejvetsi svetla vyska pole mezi pricky (mm)
POLE_MIN = 150.0                   # nejmensi svetly rozmer pole (mm) - uzsi vyplne by mela po vyrezech nulovy stred
MEZERA_DVERE = 3.0                 # vule dveri k sloupku a k nadprazi (mm); stejna na obou svislych stranach
DVERE_NAD_PODLAHOU = 5.0           # spodek kridla nad podlahou / patkou (mm)
NADPRAZ_MIN = 150.0                # nejmensi svetla vyska pole nad dvermi (mm)
PATKA_VYSKA = 79.0                 # vyska patky M10 (GLB: y -79..0)
ZAVESY_Y = 150.0                   # horni a dolni zaves: stred 150 mm od okraje kridla
DVERE_SIRKA_VYCHOZI = 800.0
STRANY = ("celo", "prava", "zadni", "leva")
TYPY_STRANY = ("stena", "dvere", "otevreno")
STRECHY = ("zadna", "ram", "vyplne")
POLOHY = ("vlevo", "stred", "vpravo")
ZAMKY = ("zapadka", "zamek", "zadny")

# vyplne: id -> {nazev, tloustka (mm), material (GLB), sku (NAVRH nove karty - zadna karta desky v katalogu zatim neni), cena_m2 (ORIENTACNI Kc/m2 bez DPH), tesneni}
VYPLNE = OrderedDict([
    ("pc_cira", {"nazev": "Polykarbonát čirý 4 mm", "tloustka": 4.0, "material": "pc_cira", "sku": "OPL-PC-CIRY-04", "cena_m2": 1150.0, "tesneni": TESNENI_SKLO}),
    ("pc_koura", {"nazev": "Polykarbonát kouřový 4 mm", "tloustka": 4.0, "material": "pc_koura", "sku": "OPL-PC-KOURA-04", "cena_m2": 1350.0, "tesneni": TESNENI_SKLO}),
    ("plexi", {"nazev": "Plexisklo čiré 5 mm", "tloustka": 5.0, "material": "plexi", "sku": "OPL-PLEXI-CIRE-05", "cena_m2": 1550.0, "tesneni": TESNENI_SKLO}),
    ("sit", {"nazev": "Svařovaná síť, pozinkovaná (výplň)", "tloustka": 3.0, "material": "sit", "sku": "OPL-SIT-03", "cena_m2": 900.0, "tesneni": TESNENI_MEKKE}),
    ("plna", {"nazev": "Plná výplň – hliníkový kompozit 3 mm", "tloustka": 3.0, "material": "plna", "sku": "OPL-AL-KOMPOZIT-03", "cena_m2": 1400.0, "tesneni": TESNENI_MEKKE}),
])
TESNENI_KARTY = {TESNENI_SKLO: {"sku": "2.3.006.10.02", "nazev": "Těsnění na sklo – drážka 10, průhledná", "cena_m": 32.0},
                 TESNENI_MEKKE: {"sku": "2.3.005.10.01.01", "nazev": "Měkké těsnění drážky – drážka 10, černá", "cena_m": 25.0}}

VYCHOZI = OrderedDict([
    ("sirka", 1500.0), ("hloubka", 1500.0), ("vyska", 2200.0),
    ("celo", "dvere"), ("prava", "stena"), ("zadni", "stena"), ("leva", "stena"),
    ("strecha", "vyplne"), ("vyplne", "pc_cira"),
    ("vyplne_celo", None), ("vyplne_prava", None), ("vyplne_zadni", None), ("vyplne_leva", None), ("vyplne_strecha", None),
    ("dvere_sirka", DVERE_SIRKA_VYCHOZI), ("dvere_vyska", None), ("dvere_poloha", "vpravo"), ("dvere_zavesy", "vpravo"), ("zamek", "zapadka"),
    ("patky", False),
])
ROZSAH = {"sirka": (600.0, 6000.0), "hloubka": (600.0, 6000.0), "vyska": (1000.0, 3000.0), "dvere_sirka": (600.0, 1200.0), "dvere_vyska": (1500.0, 2400.0)}
CISLA = ("sirka", "hloubka", "vyska", "dvere_sirka", "dvere_vyska")


class OploceniChyba(ValueError):
    """Neplatny vstup nebo neproveditelna kombinace (`kod` strojove cteny, text cesky pro clovjeka)."""

    def __init__(self, zprava, kod="neplatny_vstup"):
        super().__init__(zprava)
        self.kod = kod


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# pomocne funkce: GLB obalky, matice <-> kvaternion
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_BBOX = {}


def glb_bbox(part_id):
    """Lokalni obalka (lo, hi) dilu z accessor.min/max POSITION v katalogovem GLB (stejne jako generator stolu)."""
    if part_id in _BBOX:
        return _BBOX[part_id]
    cesta = os.path.join(KATALOG_DIR, part_id + ".glb")
    with open(cesta, "rb") as f:
        buf = f.read()
    off, js = 12, None
    while off < len(buf):
        ln, typ = struct.unpack("<II", buf[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(buf[off + 8:off + 8 + ln].decode("utf-8"))
            break
        off += 8 + ln
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for m in js.get("meshes", []):
        for p in m.get("primitives", []):
            a = js["accessors"][p["attributes"]["POSITION"]]
            lo, hi = np.minimum(lo, a["min"]), np.maximum(hi, a["max"])
    _BBOX[part_id] = (lo, hi)
    return _BBOX[part_id]


def kvat_na_matici(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]], float)


def matice_na_kvat(R):
    """Kvaternion (x, y, z, w) z rotacni matice (Shepperd)."""
    t = R[0, 0] + R[1, 1] + R[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = ((R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s)
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        q = (0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s, (R[2, 1] - R[1, 2]) / s)
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        q = ((R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s, (R[0, 2] - R[2, 0]) / s)
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        q = ((R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s, (R[1, 0] - R[0, 1]) / s)
    q = np.array(q, float)
    q /= np.linalg.norm(q)
    return tuple(round(float(v), 9) for v in q)


def _rot_y_na(d):
    """Rotace, ktera lokalni +Y otoci na smer d (jednotkovy vektor); otoceni kolem osy profilu je pro ctvercovy profil nepodstatne."""
    y = np.array([0.0, 1.0, 0.0])
    d = np.asarray(d, float)
    v = np.cross(y, d)
    c = float(y @ d)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1.0 / (1.0 + c))


def _zaokr(v, nd=6):
    return np.round(np.asarray(v, float), nd)


def aabb(dil):
    """Svetova obalka (lo, hi) dilu {part_id, quaternion, scale, position}."""
    lo, hi = glb_bbox(dil["part_id"])
    R = kvat_na_matici(dil["quaternion"])
    s = np.array(dil["scale"], float)
    rohy = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    w = (rohy * s) @ R.T + np.array(dil["position"], float)
    return w.min(axis=0), w.max(axis=0)


def hash_konfigurace(p):
    """Kanonicky hash NORMALIZOVANYCH parametru (16 hex)."""
    return hashlib.sha1(json.dumps(p, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()[:16]


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# normalizace a pravidla
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _cislo(k, v):
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise OploceniChyba(f"{k}: musi byt cislo", "neplatny_vstup")
    try:
        x = float(v)
    except ValueError:
        raise OploceniChyba(f"{k}: '{v}' neni cislo", "neplatny_vstup")
    if not math.isfinite(x):
        raise OploceniChyba(f"{k}: musi byt konecne cislo", "neplatny_vstup")
    lo, hi = ROZSAH[k]
    if x < lo - 1e-9 or x > hi + 1e-9:
        raise OploceniChyba(f"{k}: {x:g} je mimo rozsah {lo:g}-{hi:g} mm", "mimo_rozsah")
    return round(x, 1)


def normalizuj(**vstup):
    """Normalizovane parametry (uplny slovnik VYCHOZI, platne hodnoty); neznamy klic / hodnota mimo seznam / cislo mimo rozsah = OploceniChyba."""
    for k in vstup:
        if k not in VYCHOZI:
            raise OploceniChyba(f"neznamy parametr '{k}'", "neznamy_parametr")
    p = OrderedDict((k, vstup.get(k, v)) for k, v in VYCHOZI.items())
    for k in CISLA:
        if p[k] is None:
            if k != "dvere_vyska":
                raise OploceniChyba(f"{k}: chybi hodnota", "neplatny_vstup")
        else:
            p[k] = _cislo(k, p[k])
    for k in STRANY:
        if p[k] not in TYPY_STRANY:
            raise OploceniChyba(f"{k}: '{p[k]}' neni jedna z {', '.join(TYPY_STRANY)}", "mimo_rozsah")
    if p["strecha"] not in STRECHY:
        raise OploceniChyba(f"strecha: '{p['strecha']}' neni jedna z {', '.join(STRECHY)}", "mimo_rozsah")
    if p["vyplne"] not in VYPLNE:
        raise OploceniChyba(f"vyplne: '{p['vyplne']}' neni jedna z {', '.join(VYPLNE)}", "mimo_rozsah")
    for k in ("vyplne_celo", "vyplne_prava", "vyplne_zadni", "vyplne_leva", "vyplne_strecha"):
        if p[k] in ("", "auto"):
            p[k] = None
        if p[k] is not None and p[k] not in VYPLNE:
            raise OploceniChyba(f"{k}: '{p[k]}' neni jedna z {', '.join(VYPLNE)}", "mimo_rozsah")
    if p["dvere_poloha"] not in POLOHY:
        raise OploceniChyba(f"dvere_poloha: '{p['dvere_poloha']}' neni jedna z {', '.join(POLOHY)}", "mimo_rozsah")
    if p["dvere_zavesy"] not in ("vlevo", "vpravo"):
        raise OploceniChyba(f"dvere_zavesy: '{p['dvere_zavesy']}' neni vlevo / vpravo", "mimo_rozsah")
    if p["zamek"] not in ZAMKY:
        raise OploceniChyba(f"zamek: '{p['zamek']}' neni jedna z {', '.join(ZAMKY)}", "mimo_rozsah")
    if not isinstance(p["patky"], bool):
        raise OploceniChyba("patky: musi byt ano/ne", "neplatny_vstup")
    if all(p[k] == "otevreno" for k in STRANY) and p["strecha"] == "zadna":
        raise OploceniChyba("Všechny strany jsou otevřené a bez střechy – není co vyrobit (zapněte aspoň jednu stranu nebo střechu).", "prazdne")
    if not any(p[k] == "dvere" for k in STRANY):             # dvere nejsou: jejich parametry nemaji vliv (jedna kanonicka podoba = jeden hash)
        p["dvere_sirka"], p["dvere_vyska"], p["dvere_poloha"], p["dvere_zavesy"], p["zamek"] = (VYCHOZI["dvere_sirka"], None, VYCHOZI["dvere_poloha"], VYCHOZI["dvere_zavesy"], VYCHOZI["zamek"])
    for k in ("vyplne_celo", "vyplne_prava", "vyplne_zadni", "vyplne_leva"):
        if p[k.replace("vyplne_", "")] == "otevreno":
            p[k] = None                                       # strana bez steny: volba vyplne nema vliv
    if p["strecha"] != "vyplne":
        p["vyplne_strecha"] = None
    if p["strecha"] == "zadna":                              # jedna rovna strana bez strechy (oploceni): rozmer KOLMY na ni nema vliv na dily
        existuji = {k for k in STRANY if p[k] != "otevreno"}
        if existuji <= {"celo"} or existuji <= {"zadni"}:
            p["hloubka"] = VYCHOZI["hloubka"]
        elif existuji <= {"prava"} or existuji <= {"leva"}:
            p["sirka"] = VYCHOZI["sirka"]
    return p


def _deleni(span, nmax=POLE_MAX):
    """Rozdeleni svetle sirky `span` na pole oddelena sloupky 40 mm: nejmensi pocet poli n, aby (span - 40 (n-1)) / n <= nmax; vraci sirku pole (rovna pole)."""
    n = 1
    while (span - PROFIL * (n - 1)) / n > nmax + 1e-9:
        n += 1
    return n, (span - PROFIL * (n - 1)) / n


def _vyska_dveri(p, y0):
    """(vyska kridla, spodek kridla) - dle parametru a meze nadprazi; chyba, kdyz se dvere nevejdou."""
    spodek = y0 + DVERE_NAD_PODLAHOU
    dh_max = p["vyska"] - PROFIL - (MEZERA_DVERE + PROFIL) - NADPRAZ_MIN - spodek          # horni pricka (40) + nadpraz: mezera + pricka (40) + svetlost nad dvermi
    if dh_max < ROZSAH["dvere_vyska"][0] - 1e-9:
        raise OploceniChyba(f"Dveře se při výšce {p['vyska']:g} mm nevejdou: nad dveřmi musí zůstat nadpraží aspoň {NADPRAZ_MIN:g} mm (potřebují výšku aspoň {ROZSAH['dvere_vyska'][0] + p['vyska'] - dh_max:g} mm).", "dvere_nevejdou")
    if p["dvere_vyska"] is None:
        return min(2000.0, dh_max), spodek
    if p["dvere_vyska"] > dh_max + 1e-9:
        raise OploceniChyba(f"dvere_vyska: {p['dvere_vyska']:g} mm je víc než největší možná {dh_max:g} mm při výšce {p['vyska']:g} mm (nad dveřmi musí zůstat nadpraží aspoň {NADPRAZ_MIN:g} mm).", "dvere_nevejdou")
    return p["dvere_vyska"], spodek


def _sloupce(Lw, typ, p):
    """Rozlozeni steny delky Lw: seznam [(druh, u0, u1)] (svetle otvory mezi sloupky, u meřeno od leveho konce steny zvenku; rohove sloupky zabiraji 0-40 a Lw-40..Lw)."""
    S0 = Lw - 2 * PROFIL
    if typ == "stena":
        n, w = _deleni(S0)
        out, u = [], PROFIL
        for _ in range(n):
            out.append(("pole", u, u + w))
            u += w + PROFIL
        return out
    OW = p["dvere_sirka"] + 2 * MEZERA_DVERE
    if OW > S0 + 1e-9:
        raise OploceniChyba(f"Dveře ({p['dvere_sirka']:g} mm) se nevejdou do strany délky {Lw:g} mm (světlost mezi rohovými sloupky {S0:g} mm).", "dvere_nevejdou")
    zbytek = S0 - OW
    if zbytek < 1.0:
        return [("dvere", PROFIL, PROFIL + OW)]
    strana_uzka = lambda sirka: sirka < POLE_MIN - 1e-9
    if p["dvere_poloha"] == "stred":
        po_strane = (zbytek - 2 * PROFIL) / 2.0               # na kazde strane od dveri: sloupek 40 + pole
        if strana_uzka(po_strane):
            raise OploceniChyba(f"U dveří by na každé straně zbylo pole široké jen {po_strane:g} mm (minimum {POLE_MIN:g} mm): zúžte dveře nebo změňte jejich polohu.", "stena_uzka")
        n, w = _deleni(po_strane)
        out, u = [], PROFIL
        for _ in range(n):
            out.append(("pole", u, u + w))
            u += w + PROFIL
        out.append(("dvere", u, u + OW))
        u += OW + PROFIL
        for _ in range(n):
            out.append(("pole", u, u + w))
            u += w + PROFIL
        return out
    pole_sirka = zbytek - PROFIL                               # jedno souvisle pole (nebo vice) na jedne strane dveri
    if strana_uzka(pole_sirka):
        raise OploceniChyba(f"U dveří by zbylo pole široké jen {pole_sirka:g} mm (minimum {POLE_MIN:g} mm): zúžte dveře nebo je dejte doprostřed.", "stena_uzka")
    n, w = _deleni(pole_sirka)
    polo = []
    u = PROFIL
    for _ in range(n):
        polo.append(("pole", u, u + w))
        u += w + PROFIL
    if p["dvere_poloha"] == "vpravo":                        # dvere u praveho konce: pole vlevo, pak sloupek, dvere
        return polo + [("dvere", u, u + OW)]
    out = [("dvere", PROFIL, PROFIL + OW)]                    # vlevo: dvere na zacatku, pak sloupek a pole
    u = PROFIL + OW + PROFIL
    for _ in range(n):
        out.append(("pole", u, u + w))
        u += w + PROFIL
    return out


def _radky(vyska_otvoru):
    """(pocet mezipricek, svetla vyska pole mezi pricky) pro svetlou vysku otvoru (kdyz vetsi nez MID_MAX pribyvaji mezipricky po 40 mm)."""
    nm = 0
    while (vyska_otvoru - PROFIL * nm) / (nm + 1) > MID_MAX + 1e-9:
        nm += 1
    return nm, (vyska_otvoru - PROFIL * nm) / (nm + 1)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# sestaveni
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _zaklad_strany(s, W, D):
    """Zakladna strany: o = bod u = 0, y = 0 na stredove care steny; eu = smer rostouciho u; n = vnejsi normala; L = delka steny."""
    if s == "celo":
        return {"o": np.array([0.0, 0.0, D - 20.0]), "eu": np.array([1.0, 0.0, 0.0]), "n": np.array([0.0, 0.0, 1.0]), "L": W}
    if s == "prava":
        return {"o": np.array([W - 20.0, 0.0, D]), "eu": np.array([0.0, 0.0, -1.0]), "n": np.array([1.0, 0.0, 0.0]), "L": D}
    if s == "zadni":
        return {"o": np.array([W, 0.0, 20.0]), "eu": np.array([-1.0, 0.0, 0.0]), "n": np.array([0.0, 0.0, -1.0]), "L": W}
    return {"o": np.array([20.0, 0.0, 0.0]), "eu": np.array([0.0, 0.0, 1.0]), "n": np.array([-1.0, 0.0, 0.0]), "L": D}


UP = np.array([0.0, 1.0, 0.0])
OSA = {"x": 0, "y": 1, "z": 2}
# montaz zamku / zapadky PLOSNE na vnejsi plochu stojky: (osa dilu, ktera lezi svisle = nejdelsi rozmer, osa dilu, ktera miri z profilu ven; dosedaci plocha dilu je jeho minimum podel ni).
# Orientace je ORIENTACNI (nemame vyrobni vykres montaze): zapadka 42 x 10,5 x 8 mm = plochy plech s dvema otvory (pohled na dil), zamek 83 x 32 x 100 mm.
ZAMEK_MONTAZ = {ZAPADKA: ("x", "y"), ZAMEK: ("z", "y")}
_BLOK_ROHY = np.array([[lx, ly, lz] for lx in (0.0, BLOK) for ly in (-BLOK, 0.0) for lz in (0.0, BLOK)])        # osm rohu bloku spojky v lokalnich souradnicich


class _Sestava:
    def __init__(self, p):
        self.p = p
        self.dily = []
        self.vyplne = []                       # pole (bunky) vyplne
        self.spoje = []                        # kazdy spoj: {typ, role, souradnice}
        self.bloky = []                        # (lo, hi) bloku spojek v rovine vyplni (pro vyrezy)
        self.upozorneni = []
        self.dvere = []                        # informace o dverich (osa zavesu, smer ven) pro 3D (otevreni kridla)
        self.W, self.D, self.H = p["sirka"], p["hloubka"], p["vyska"]
        self.y0 = PATKA_VYSKA if p["patky"] else 0.0

    # ---- dily -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def profil(self, p0, p1, role, strana=None, **dalsi):
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1.0:
            raise OploceniChyba(f"profil '{role}' by měl nulovou délku", "neproveditelne")
        d = d / L
        q = matice_na_kvat(_rot_y_na(d))
        dil = {"part_id": PROFIL_PART, "quaternion": q, "scale": [1.0, round(L / 1000.0, 9), 1.0], "position": _zaokr((p0 + p1) / 2.0), "druh": "profil", "role": role, "strana": strana,
               "delka": round(L, 3), "osa": _zaokr(d, 9)}
        dil.update(dalsi)
        self.dily.append(dil)
        return dil

    def _dil(self, part_id, R, pos, druh, role, **dalsi):
        dil = {"part_id": part_id, "quaternion": matice_na_kvat(R), "scale": [1.0, 1.0, 1.0], "position": _zaokr(pos), "druh": druh, "role": role}
        dil.update(dalsi)
        self.dily.append(dil)
        return dil

    def spojka(self, Q, b, a, role, strana=None, **dalsi):
        """Rohova spojka v uhlu mezi dosedajicim profilem B (osa od spoje smerem `b`, stred cela v bode Q) a plochou nosneho profilu (smer `a` podel nosneho profilu); pravidlo odvozene ze
        sablony stolu: R = [b, a, b x a], poloha = Q + 57 a - 18,5 (b x a)."""
        b, a = np.asarray(b, float), np.asarray(a, float)
        c = np.cross(b, a)
        R = np.column_stack([b, a, c])
        pos = np.asarray(Q, float) + (PROFIL / 2.0 + BLOK) * a - (BLOK / 2.0) * c
        dil = self._dil(SPOJKA, R, pos, "spojka", role, strana=strana, b=_zaokr(b, 9), a=_zaokr(a, 9), Q=_zaokr(Q), **dalsi)
        rohy = pos + _BLOK_ROHY @ R.T                          # blok: lokalni x 0..37 -> b, y -37..0 -> a (od Q + 20 a do Q + 57 a), z 0..37 -> c
        self.bloky.append((rohy.min(axis=0), rohy.max(axis=0)))
        self.spoje.append({"role": role, "Q": _zaokr(Q), "b": _zaokr(b, 9), "a": _zaokr(a, 9)})
        return dil

    def zaslepka(self, stred_cela, dovnitr, role, **dalsi):
        """Zaslepka 40x40 na konci profilu: lokalni +Z do profilu (`dovnitr` = smer od cela dovnitr profilu)."""
        z = np.asarray(dovnitr, float)
        x = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 0.0, 1.0])
        y = np.cross(z, x)
        R = np.column_stack([x, y, z])
        self._dil(ZASLEPKA, R, stred_cela, "zaslepka", role, **dalsi)

    def patka(self, x, z):
        self._dil(PATKA, np.eye(3), np.array([x, self.y0, z]), "patka", "stavitelná patka")

    # ---- sloupky, pricky, spoje ----------------------------------------------------------------------------------------------------------------------------------------------------
    def sloupek(self, x, z, role, vrch=None, eu=None, strana=None):
        """Sloupek od podlahy / patky: ROHOVY (`vrch` None) jde az po vrch H se zaslepkou; MEZILEHLY (`vrch` = H - 40) konci POD souvislou hornipricku (dosedne na jeji spodni plochu, T-spoj =
        2 spojky podel pricky `eu`) - dik tomu prochazi strechou jen rohove sloupky a strechni vyplne / pricky nikdy nenaraziji na sloupek."""
        y_dol, y_hor = self.y0, (self.H if vrch is None else vrch)
        d = self.profil(np.array([x, y_dol, z]), np.array([x, y_hor, z]), role, strana)
        d["sloupek"] = True
        if vrch is None:
            self.zaslepka(np.array([x, y_hor, z]), -UP, "zaslepka sloupku (nahoře)")
        else:
            for sm in (1.0, -1.0):
                self.spojka(np.array([x, y_hor, z]), -UP, sm * np.asarray(eu, float), role, strana)
        if self.p["patky"]:
            self.patka(x, z)
        else:
            self.zaslepka(np.array([x, y_dol, z]), UP, "zaslepka sloupku (dole)")
        return d

    def pricka(self, bod0, bod1, role, strana, a_spoje, spojky=True, **dalsi):
        """Vodorovny profil mezi dvema sloupky: konce lezi na bocnich plochach sloupku; `a_spoje` = seznam smeru `a` (podel sloupku) pro spojky na kazdem konci (L-roh 1, T-spoj 2)."""
        bod0, bod1 = np.asarray(bod0, float), np.asarray(bod1, float)
        d = self.profil(bod0, bod1, role, strana, **dalsi)
        sm = (bod1 - bod0) / np.linalg.norm(bod1 - bod0)
        if spojky:
            for a in a_spoje:
                self.spojka(bod0, sm, a, role, strana, **({"kridlo": True} if dalsi.get("kridlo") else {}))                  # konec 0: b smerem od sloupku k prícce
                self.spojka(bod1, -sm, a, role, strana, **({"kridlo": True} if dalsi.get("kridlo") else {}))
        return d

    # ---- vyplne --------------------------------------------------------------------------------------------------------------------------------------------------------------------
    def vypln(self, typ, stred, e1, e2, n, w, h, role, strana, male_rohy=()):
        """Pole vyplne: otvor w x h (mm) ve stredove rovine (stred, osy e1/e2, normala n). `male_rohy` = rohy (s1, s2) = (+-1, +-1) sousedici s ROHOVYM SLOUPKEM (strecha): tabule tam ma maly
        vyrez INS x INS, jinak by se okraj zasunuty do drazky zanořil do sloupku."""
        self.vyplne.append({"typ": typ, "stred": _zaokr(stred), "e1": _zaokr(e1, 9), "e2": _zaokr(e2, 9), "n": _zaokr(n, 9), "w": round(float(w), 3), "h": round(float(h), 3), "role": role,
                            "strana": strana, "male_rohy": [tuple(r) for r in male_rohy]})

    def _kusy_vyplni(self):
        """Pro kazde pole spocte kusy kvadru: obdelnik otvoru + INS do drazek; v rozich s blokem spojky vyrez VYREZ, u rohoveho sloupku (strecha) maly vyrez INS (+ 0,5 mm vule). Tvar po vyrezech
        se rozlozi na nejmene kvadru (kriz = 3)."""
        B_lo = np.array([b[0] for b in self.bloky]).reshape(-1, 3)
        B_hi = np.array([b[1] for b in self.bloky]).reshape(-1, 3)
        for v in self.vyplne:
            e1, e2 = np.array(v["e1"]), np.array(v["e2"])
            w2, h2 = v["w"] / 2.0 + INS, v["h"] / 2.0 + INS
            N = {}
            for s1 in (-1, 1):
                for s2 in (-1, 1):
                    sonda = np.array(v["stred"]) + e1 * s1 * (v["w"] / 2.0 - 1.0) + e2 * s2 * (v["h"] / 2.0 - 1.0)
                    if np.any(np.all((sonda >= B_lo - 0.5) & (sonda <= B_hi + 0.5), axis=1)):
                        N[(s1, s2)] = VYREZ
                    elif (s1, s2) in v["male_rohy"]:
                        N[(s1, s2)] = INS + 0.5
                    else:
                        N[(s1, s2)] = 0.0
            v["vyrezy"] = sum(1 for x in N.values() if x == VYREZ)
            v["vyrezy_vsechny"] = sum(1 for x in N.values() if x > 0)
            body = {-h2, h2}
            for (s1, s2), n_ in N.items():
                if n_ > 0:
                    body.add(-h2 + n_ if s2 < 0 else h2 - n_)
            osy = sorted(body)
            pasy = []
            for ya, yb in zip(osy[:-1], osy[1:]):
                if yb - ya < 1e-6:
                    continue
                ym = (ya + yb) / 2.0
                lo_x = -w2 + max([N[(-1, -1)] if ym < -h2 + N[(-1, -1)] else 0.0, N[(-1, 1)] if ym > h2 - N[(-1, 1)] else 0.0])
                hi_x = w2 - max([N[(1, -1)] if ym < -h2 + N[(1, -1)] else 0.0, N[(1, 1)] if ym > h2 - N[(1, 1)] else 0.0])
                pasy.append([ya, yb, lo_x, hi_x])
            slite = []
            for pas in pasy:
                if slite and abs(slite[-1][2] - pas[2]) < 1e-6 and abs(slite[-1][3] - pas[3]) < 1e-6 and abs(slite[-1][1] - pas[0]) < 1e-6:
                    slite[-1][1] = pas[1]
                else:
                    slite.append(list(pas))
            kusy = []
            for ya, yb, lo_x, hi_x in slite:
                stred = np.array(v["stred"]) + e1 * (lo_x + hi_x) / 2.0 + e2 * (ya + yb) / 2.0
                kusy.append({"stred": _zaokr(stred), "e1": round(hi_x - lo_x, 6), "e2": round(yb - ya, 6)})
            v["kusy"] = kusy
            v["rozmer_tabule"] = (round(2 * w2, 3), round(2 * h2, 3))


def _rot_zamku(dlouha, normala, n_out):
    """Rotace dilu: osa `normala` -> ven z profilu (n_out), osa `dlouha` -> nahoru; treti osa doplni pravotocivou soustavu."""
    c = [None, None, None]
    c[OSA[normala]], c[OSA[dlouha]] = n_out, UP
    i = [k for k in range(3) if c[k] is None][0]
    c[i] = np.cross(c[(i + 1) % 3], c[(i + 2) % 3])
    return np.column_stack(c)


def sestav_oploceni(**vstup):
    """Viz hlavicka modulu."""
    p = normalizuj(**vstup)
    S = _Sestava(p)
    W, D, H, y0 = S.W, S.D, S.H, S.y0
    typy = {s: p[s] for s in STRANY}
    strecha = p["strecha"] != "zadna"
    if H - y0 < 1000.0 - 1e-9:
        raise OploceniChyba(f"Vyska {H:g} mm s patkami ({y0:g} mm) nechává na konstrukci jen {H - y0:g} mm (minimum 1000 mm).", "mimo_rozsah")
    # ---- rohove sloupky ----
    rohy = {"celo_leva": (20.0, D - 20.0, ("celo", "leva")), "celo_prava": (W - 20.0, D - 20.0, ("celo", "prava")), "zadni_prava": (W - 20.0, 20.0, ("zadni", "prava")),
            "zadni_leva": (20.0, 20.0, ("zadni", "leva"))}
    for nazev, (x, z, sousedi) in rohy.items():
        if strecha or any(typy[s] != "otevreno" for s in sousedi):
            S.sloupek(x, z, f"rohový sloupek ({nazev})")
    # ---- steny ----
    for s in STRANY:
        z = _zaklad_strany(s, W, D)
        pt = lambda u, y, z=z: z["o"] + z["eu"] * u + UP * y
        if typy[s] == "otevreno":
            if strecha:
                S.pricka(pt(PROFIL, H - 20.0), pt(z["L"] - PROFIL, H - 20.0), f"horní příčka ({s}, otevřená strana)", s, [-UP])
            continue
        vyp = p["vyplne_" + s] or p["vyplne"]
        sloupce = _sloupce(z["L"], typy[s], p)
        for k in range(len(sloupce) - 1):                     # mezilehle sloupky mezi sloupci (konci pod souvislou hornipricku)
            uc = (sloupce[k][2] + sloupce[k + 1][1]) / 2.0
            c = pt(uc, 0.0)
            S.sloupek(c[0], c[2], f"mezilehlý sloupek ({s})", vrch=H - PROFIL, eu=z["eu"], strana=s)
        S.pricka(pt(PROFIL, H - 20.0), pt(z["L"] - PROFIL, H - 20.0), f"horní příčka ({s})", s, [-UP])      # souvisla pres vsechna pole i dvere (nese strechu)
        y_dolni_horni = y0 + PROFIL                            # horni hrana dolni pricky
        y_horni_dolni = H - PROFIL                             # dolni hrana horni pricky
        for druh, u0, u1 in sloupce:
            w = u1 - u0
            uc = (u0 + u1) / 2.0
            if druh == "pole":
                S.pricka(pt(u0, y0 + 20.0), pt(u1, y0 + 20.0), f"dolní příčka ({s})", s, [UP])
                ho = y_horni_dolni - y_dolni_horni
                nm, oh = _radky(ho)
                for kk in range(nm):
                    yc = y_dolni_horni + (kk + 1) * oh + PROFIL * kk + PROFIL / 2.0
                    S.pricka(pt(u0, yc), pt(u1, yc), f"mezipříčka ({s})", s, [UP, -UP])
                yb = y_dolni_horni
                for kk in range(nm + 1):
                    S.vypln(vyp, pt(uc, yb + oh / 2.0), z["eu"], UP, z["n"], w, oh, f"výplň pole ({s})", s)
                    yb += oh + PROFIL
                continue
            # ---- dvere: kridlo, nadpraz ----
            dh, spodek = _vyska_dveri(p, y0)
            vrch = spodek + dh
            y_nadpraz = vrch + MEZERA_DVERE + PROFIL / 2.0
            S.pricka(pt(u0, y_nadpraz), pt(u1, y_nadpraz), f"nadpraží dveří ({s})", s, [UP], nadpraz=True)           # jen spojky nahoru (dolni ruh kridla by lezel v otvoru)
            y_nad_dol = vrch + MEZERA_DVERE + PROFIL                       # horni hrana nadprazi
            nm_n, oh_n = _radky(y_horni_dolni - y_nad_dol)                  # nizke dvere ve vysoke stene: pole nad nimi se deli mezipricky jako kazde jine
            for kk in range(nm_n):
                yc = y_nad_dol + (kk + 1) * oh_n + PROFIL * kk + PROFIL / 2.0
                S.pricka(pt(u0, yc), pt(u1, yc), f"mezipříčka nadpraží ({s})", s, [UP, -UP])
            yb = y_nad_dol
            for kk in range(nm_n + 1):
                S.vypln(vyp, pt(uc, yb + oh_n / 2.0), z["eu"], UP, z["n"], w, oh_n, f"výplň nadpraží ({s})", s)
                yb += oh_n + PROFIL
            ul, ur = u0 + MEZERA_DVERE, u1 - MEZERA_DVERE
            for uu, role in ((ul + 20.0, "stojka křídla (levá)"), (ur - 20.0, "stojka křídla (pravá)")):
                c = pt(uu, 0.0)
                S.profil(np.array([c[0], spodek, c[2]]), np.array([c[0], vrch, c[2]]), f"{role} ({s})", s, kridlo=True)
                S.zaslepka(np.array([c[0], vrch, c[2]]), -UP, f"zaslepka stojky křídla ({s})", kridlo=True)
                S.zaslepka(np.array([c[0], spodek, c[2]]), UP, f"zaslepka stojky křídla ({s})", kridlo=True)
            S.pricka(pt(ul + PROFIL, vrch - 20.0), pt(ur - PROFIL, vrch - 20.0), f"horní příčka křídla ({s})", s, [-UP], kridlo=True)
            S.pricka(pt(ul + PROFIL, spodek + 20.0), pt(ur - PROFIL, spodek + 20.0), f"dolní příčka křídla ({s})", s, [UP], kridlo=True)
            ho = (vrch - PROFIL) - (spodek + PROFIL)
            nm, oh = _radky(ho)
            yb = spodek + PROFIL
            for kk in range(nm):
                yc = yb + (kk + 1) * oh + PROFIL * kk + PROFIL / 2.0
                S.pricka(pt(ul + PROFIL, yc), pt(ur - PROFIL, yc), f"mezipříčka křídla ({s})", s, [UP, -UP], kridlo=True)
            for kk in range(nm + 1):
                S.vypln(vyp, pt((ul + ur) / 2.0, yb + oh / 2.0), z["eu"], UP, z["n"], ur - ul - 2 * PROFIL, oh, f"výplň křídla ({s})", s)
                yb += oh + PROFIL
            # zavesy: na vnejsi strane, osa v mezere mezi sloupkem a stojkou
            u_zav = u0 + MEZERA_DVERE / 2.0 if p["dvere_zavesy"] == "vlevo" else u1 - MEZERA_DVERE / 2.0
            n_out = z["n"]
            ys = [spodek + ZAVESY_Y, (spodek + vrch) / 2.0, vrch - ZAVESY_Y]
            R = np.column_stack([n_out, UP, np.cross(n_out, UP)])
            for yz in ys:
                stred = pt(u_zav, yz) + n_out * (PROFIL / 2.0 + 6.15)
                S._dil(PANT_PRAVY if p["dvere_zavesy"] == "vpravo" else PANT_LEVY, R, stred - R @ np.array([0.0, 26.0, 0.0]), "pant", f"závěs ({s})", strana=s)
            S.dvere.append({"strana": s, "zavesy": p["dvere_zavesy"], "osa_bod": _zaokr(pt(u_zav, 0.0) + n_out * (PROFIL / 2.0 + 6.15)), "n": _zaokr(n_out, 9), "eu": _zaokr(z["eu"], 9),
                            "vyska_kridla": round(dh, 1), "spodek": round(spodek, 1), "sirka_kridla": p["dvere_sirka"], "u0": round(u0, 3), "u1": round(u1, 3)})
            # zamek / zapadka na druhe stojce
            if p["zamek"] != "zadny":
                u_st = (ur - 20.0) if p["dvere_zavesy"] == "vlevo" else (ul + 20.0)
                dil_id = ZAPADKA if p["zamek"] == "zapadka" else ZAMEK
                lo_, hi_ = glb_bbox(dil_id)
                dlouha, normala = ZAMEK_MONTAZ[dil_id]
                Rz = _rot_zamku(dlouha, normala, n_out)
                stred_lic = (lo_ + hi_) / 2.0
                stred_lic[OSA[normala]] = lo_[OSA[normala]]                          # dosedaci plocha dilu = minimum podel normaly (lezi na povrchu profilu)
                lic = pt(u_st, spodek + min(1000.0, dh / 2.0)) + n_out * (PROFIL / 2.0)       # stred vnejsi plochy stojky
                S._dil(dil_id, Rz, lic - Rz @ stred_lic, "zamek", f"{'západka' if p['zamek'] == 'zapadka' else 'bezpečnostní zámek'} ({s})", strana=s, kridlo=True)
    # ---- strecha ----
    if p["strecha"] == "vyplne":
        vyp = p["vyplne_strecha"] or p["vyplne"]
        ix, iz = W - 2 * PROFIL, D - 2 * PROFIL
        nx, wx = _deleni(ix)
        nz, wz = _deleni(iz)
        yc = H - 20.0
        # pricky podel Z (delici sirku) a podel X (delici hloubku): mrizka s T-spoji
        xs = [PROFIL + k * (wx + PROFIL) for k in range(nx)]                    # levy okraj sloupce
        zs = [PROFIL + k * (wz + PROFIL) for k in range(nz)]
        for k in range(nx - 1):
            xc = xs[k] + wx + PROFIL / 2.0
            S.pricka(np.array([xc, yc, PROFIL]), np.array([xc, yc, D - PROFIL]), "střešní příčka (podél hloubky)", "strecha", [np.array([1.0, 0, 0]), np.array([-1.0, 0, 0])], stresni=True)
        for k in range(nz - 1):
            zc = zs[k] + wz + PROFIL / 2.0
            for i in range(nx):
                S.pricka(np.array([xs[i], yc, zc]), np.array([xs[i] + wx, yc, zc]), "střešní příčka (podél šířky)", "strecha", [np.array([0, 0, 1.0]), np.array([0, 0, -1.0])], stresni=True)
        for i in range(nx):
            for j in range(nz):
                male = [(sx, sz) for sx, krajni_x in ((-1, i == 0), (1, i == nx - 1)) for sz, krajni_z in ((-1, j == 0), (1, j == nz - 1)) if krajni_x and krajni_z]       # rohy u rohovych sloupku
                S.vypln(vyp, np.array([xs[i] + wx / 2.0, yc, zs[j] + wz / 2.0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), np.array([0, 1.0, 0]), wx, wz, "střešní výplň", "strecha", male)
    S._kusy_vyplni()
    return _vysledek(S)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# vysledek: kusovnik, entries, upozorneni, rozmery
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _vysledek(S):
    p, dily = S.p, S.dily
    upozorneni = [{"id": "norma", "text": "Generátor řeší KONSTRUKCI krytu / oplocení. Bezpečnostní vzdálenosti, otvory výplní a zajištění dveří (ČSN EN ISO 14120, ČSN EN ISO 13857) posuzuje projektant stroje."}]
    if p["vyska"] > 2500 or max(p["sirka"], p["hloubka"]) > 4000:
        upozorneni.append({"id": "kotveni", "text": "Vysoká nebo dlouhá konstrukce: doporučujeme ji ukotvit k podlaze nebo ke zdi (patky/úhelníky se do ceny nepočítají)."})
    if any(p[s] == "dvere" for s in STRANY) and p["dvere_sirka"] > 1000:
        upozorneni.append({"id": "dvere_siroke", "text": "Křídlo širší než 1000 mm je těžké: zvolte plnou 4 mm výplň jen tam, kde je to nutné, a zkontrolujte únosnost závěsů."})
    if any(v["typ"] == "sit" for v in S.vyplne):                                    # sit je skutecne pouzita v nejakem poli (ne jen jako prebita celkova volba)
        upozorneni.append({"id": "sit", "text": "Síťová výplň: velikost ok a vzdálenost od nebezpečného místa musí vyhovovat ČSN EN ISO 13857."})
    profily = [d for d in dily if d["druh"] == "profil"]
    skupiny = OrderedDict()
    for d in profily:
        k = (round(d["delka"], 1), d["role"].split(" (")[0])
        skupiny[k] = skupiny.get(k, 0) + 1
    kus_profily = [{"delka_mm": k[0], "role": k[1], "ks": n} for k, n in sorted(skupiny.items(), key=lambda kv: (-kv[0][0], kv[0][1]))]
    soucet_mm = sum(d["delka"] for d in profily)
    poctys = OrderedDict()
    for d in dily:
        if d["druh"] == "profil":
            continue
        poctys[d["part_id"]] = poctys.get(d["part_id"], 0) + 1
    NAZVY = {SPOJKA: ("2.2.001.10.4040.33", "Rohová spojka 40×40"), ZASLEPKA: ("2.3.001.4040.01", "Záslepka 40×40 S10"), PANT_PRAVY: ("2.2.003.4040.05", "Pant 40×40 (pravý)"),
             PANT_LEVY: ("2.2.003.4040.06", "Pant 40×40 (levý)"), PATKA: ("2.3.002.1050", "Vyrovnávací šroubovací patka M10"), ZAPADKA: ("2.2.004.10.000", "Kuličková západka s napínáním 45-40-35"),
             ZAMEK: ("2.2.014.01.000", "Bezpečnostní zámek (malý)")}
    kus_dily = [{"part_id": pid, "sku": NAZVY[pid][0], "nazev": NAZVY[pid][1], "mnozstvi": n, "jednotka": "ks"} for pid, n in poctys.items()]
    vypln_kus = OrderedDict()
    tesneni = OrderedDict()
    for v in S.vyplne:
        info = VYPLNE[v["typ"]]
        w, h = v["rozmer_tabule"]
        k = (v["typ"], w, h, v["vyrezy"])
        vypln_kus[k] = vypln_kus.get(k, 0) + 1
        tesneni[info["tesneni"]] = tesneni.get(info["tesneni"], 0.0) + 2.0 * (v["w"] + v["h"]) / 1000.0
    kus_vyplne = [{"typ": k[0], "nazev": VYPLNE[k[0]]["nazev"], "sku": VYPLNE[k[0]]["sku"], "sirka_mm": k[1], "vyska_mm": k[2], "vyrezy_rohu": k[3], "ks": n, "plocha_m2": round(k[1] * k[2] / 1e6 * n, 4)}
                  for k, n in vypln_kus.items()]
    kus_tesneni = [{"part_id": pid, "sku": TESNENI_KARTY[pid]["sku"], "nazev": TESNENI_KARTY[pid]["nazev"], "mnozstvi": round(m, 3), "jednotka": "m", "cena_m": TESNENI_KARTY[pid]["cena_m"]} for pid, m in tesneni.items()]
    # entries pro configurator_price.price_entries: profily (delka), kazdy spoj (1 spoj = 1 spojka... na dosedajici profil), ostatni dily po kuse, vyplne jako desky (m2) podle obdelnikove tabule
    entries = []
    pocet_spoju = _pocet_spoju(S)
    prvni = True
    for d in profily:
        e = {"product_id": d["part_id"], "length_mm": d["delka"]}
        if prvni:
            e["joint_count"] = pocet_spoju                    # cena spoje se pocita CELKEM (price_entries scita joint_count vsech radku): vsechny spoje na prvni profil
            prvni = False
        entries.append(e)
    for d in dily:
        if d["druh"] != "profil":
            entries.append({"product_id": d["part_id"]})
    for v in S.vyplne:
        w, h = v["rozmer_tabule"]
        entries.append({"product_id": "navrh:" + v["typ"], "width_mm": w, "height_mm": h})
    extra = [{"name": f"{t['nazev']} [{t['sku']}]", "qty": t["mnozstvi"], "unit_czk": t["cena_m"]} for t in kus_tesneni]
    obal = [aabb(d) for d in profily]
    ext = np.max([b[1] for b in obal], axis=0) - np.min([b[0] for b in obal], axis=0)
    uzavreny = sum(1 for d in profily if d["role"].startswith("rohový sloupek")) == 4          # vsechny 4 rohy = uzavreny pudorys (svetlost uvnitr dava smysl)
    rozmery = {"sirka_mm": round(float(ext[0]), 1), "hloubka_mm": round(float(ext[2]), 1), "vyska_mm": p["vyska"],                       # celkova vcetne patek
               "svetla_sirka_mm": p["sirka"] - 2 * PROFIL if uzavreny else None, "svetla_hloubka_mm": p["hloubka"] - 2 * PROFIL if uzavreny else None,
               "svetla_vyska_mm": p["vyska"] - S.y0 - PROFIL if p["strecha"] != "zadna" else p["vyska"] - S.y0, "pudorys_m2": round(p["sirka"] * p["hloubka"] / 1e6, 3) if uzavreny else None}
    return {"parametry": p, "hash": hash_konfigurace(p), "verze_pravidel": VERZE_PRAVIDEL, "dily": dily, "vyplne": S.vyplne, "spoje": S.spoje, "entries": entries, "extra_prace": extra,
            "kusovnik": {"profily": kus_profily, "profily_celkem_mm": round(soucet_mm, 1), "profily_ks": len(profily), "dily": kus_dily, "vyplne": kus_vyplne, "tesneni": kus_tesneni,
                         "spojovaci_material": _spojovaci_material(poctys)},
            "pocet_spoju": pocet_spoju, "rozmery": rozmery, "upozorneni": upozorneni, "problemy": [], "dvere": S.dvere}


def _pocet_spoju(S):
    """Pocet SPOJU profilu (ne spojek): L-roh = 1 spoj (1 spojka), T-spoj = 1 spoj (2 spojky se stejnym koncem pricky): podle (dosedajici konec = bod Q)."""
    return len({tuple(np.round(sp["Q"], 1)) + tuple(np.round(sp["b"], 3)) for sp in S.spoje})


# spojovaci material ke spojce: jako u generatoru stolu (system 40: 2 sroubky M6x16 + 2 otocne matice do drazky 10 na spojku)
SPOJOVACI_MATERIAL = {SPOJKA: [("2.1.21.0616", 2, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")]}


def _spojovaci_material(poctys):
    out = OrderedDict()
    for pid, n in poctys.items():
        for sku, ks, nazev in SPOJOVACI_MATERIAL.get(pid, []):
            q = out.setdefault(sku, {"sku": sku, "nazev": nazev, "mnozstvi": 0})
            q["mnozstvi"] += ks * n
    return list(out.values())
