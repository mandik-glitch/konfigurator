"""HORNI POLICE MEZI ZADNIMI STOJKAMI generatoru stolu (bot8, 2026-10-07; zdroj: scripts/2026-10-07_police_stojky/stul_hpolice.py, nasazuje se do api/).

Robert 2026-10-07: „pridat do generatoru ruzne typy polic mezi zadni stojky“ - a na otazku, ktere typy: rovna z laminodesky, ramova bez desky, sikma na boxy, s lemem + „a take ram s prekliskou v drazce
u 40/45 a u 30/35 krome laminodesky 18 mm i 12 mm, take do drazky MDF 8 mm“ + „plus police jako ram s prepazkami z prekliky 10 mm kotvena uhelniky viz stul SSE“.

VYCHOZI = BEZ HORNI POLICE (parametr `hpolice` False): vsechny stavajici konfigurace, ceny, kod konfigurace a hashe jsou BEZE ZMENY (zlaty test golden_head.json). Policejni klice se do hashe pocitaji
jen pri zapnute police (S.kanonicky_hash -> kanon_hash tady).

KONSTRUKCE (jedna jednotka na USEK mezi zadnimi stojkami = S._pole_panelu: s prostrednimi zadnimi nohami dva useky, jinak jeden; kazda jednotka je nezavisla)
  * ZADNI PRICKA (profil podel Z) v rovine stojek mezi jejich vnitrnimi lici (stejne jako profily panelu, spoje 42 / 45 se z analogie panelu OTOCI POD prickou), PREDNI PRICKA stejne dlouha v hloubce
    `hpolice_hloubka` (vnejsi hloubka ramu od zadniho lice zadni pricky po predni lico predni pricky), mezi nimi 2 BOCNI profily (podel X) na vnitrnich lících stojek, pri rozponu nad ROZPON
    (podle desky) dalsi MEZIPROFILY. T-spoje profilu: konec bocniho profilu dosedá celem na stenu pricky, rohove spojky (3158 / 3176) se odvozuji z analogie sablony (36 / 37) a otaci kolem uzlu.
  * DESKA (pocet kusu podle rozponu a tabule laminodesky): ROVNA / S LEMEM lezi shora na rame (laminodeska 18 mm vsechny systemy, 12 mm jen 30 / 35), V DRAZCE (MDF 8 mm u 30 / 35, prekliska PR10 10 mm
    u 40 / 45) je po jednotlivych polich mezi bocnimi / strednimi profily a zasahuje do jejich drazek (SSE: deska 10 mm zasahuje 10 mm do drazky); podel X konci o rameno rohove
    spojky + 1 mm pred pricnymi profily (v rozich ramu sedi spojky, jako ve vzoru SSE, kde je deska o 59 mm kratsi nez profily); RAMOVA nema desku.
  * S PREPAZKAMI (SSE.vzor.01, custom_shapes #561): podlaha z desky v drazce + svisle PREPAZKY z PR10 10 mm vysky 240 mm, hloubka rámu - 4 mm, stoji na horních plochach zadni a predni pricky,
    kazda na 2 UHELNICICH (Uhelnikova spojka 30x30 #3045 / 40x40 #3207): jeden u predni pricky na jedne strane prepazky, druhy u zadni na druhe (stridave jako ve vzoru), pocet podle rozteče 260 mm.
  * S LEMEM: predni lem = pas PR10 10 mm vysky 40 mm stoji na predni pricce (cela predni hrana), kotveny uhelniky ZA nim; deska konci za uhelniky.
  * SIKMA NA BOXY (2. kolo): RAM jako u lemu, ale NAKLONENY TUHE o `hpolice_sklon` (5-30 st., vychozi 15) kolem osy zadni pricky (vpredu nizsi): cely ram (pricky, boky, mezilisty, rohove spojky, zaslepky,
    deska, lem s uhelniky) se postavi PLOCHY a pri vystupu do `dily` se otoci kolem osy Z pres osu zadni pricky (T-spoje zustavaji 90 st., rohove spojky 3158 / 3176 jako jinde). Zadni pricka lezi v rovine
    stojek (osa na stojkach), predni je nize. Ram drzi 2 NAKLAPECI KONZOLE na sekci (Uhlova naklapeci konzole #3323 pro drazku 8 = systemy 30 / 35, #3324 pro drazku 10 = 40 / 45): list P1 lezi na PREDNIM licu
    stojky (dve oválne drazky na sroub), pulkruhova deska P2 s kloubem (otvor) a obloukovou drazkou lezi na VNEJSIM (stojce privracenem) licu bocniho profilu; bocni profil se otaci kolem klubu, jeho osa
    prochazi osou kloubu (GLB je tuhy tvar, sklon zadava poloha profilu, ne tvar konzoly). Vyska = vyska HORNI PLOCHY DESKY NA ZADNIM OKRAJI. Jen u stolu s JEDNIM usekem mezi zadnimi stojkami (u stredni
    zadni nohy by se dve konzole na jedno lice stojky nevesly - otevreny bod). Kolize naklonenych dilu: AABB kontrola generatoru se pro ne vypina a nahrazuje ji presny test OBB x AABB (`zkontroluj`).
  Vsechny rozmery desek, uhelniku a profilu se berou z GLB / sablony (nic neni zadratovane krome tlouštěk karet).

VYSKA: `hpolice_vyska` = vyska HORNI PLOCHY police (u desky horni plocha desky, jinak horni lico profilu) nad horni plochou pracovni desky; None = automaticky (spodek ramu 60 mm nad horni lištou panelu, bez
panelu 150 mm nad deskou). HLOUBKA: `hpolice_hloubka` = vnejsi hloubka ramu (150 az 600 mm, nejvic hloubka stolu).
"""
import math

import numpy as np

import stul_konfigurator as S

StulChyba = S.StulChyba

TYPY = ("rovna", "ram", "drazka", "lem", "prepazky", "sikma")
TYP_VYCHOZI = "rovna"
DESKA_VYCHOZI = "lam18"
HLOUBKA_VYCHOZI, HLOUBKA_MIN, HLOUBKA_MAX = 300.0, 150.0, 600.0       # vnejsi hloubka ramu police (od zadniho lice zadni pricky po predni lico predni pricky), mm
VYSKA_MIN, VYSKA_MAX = 100.0, 1500.0                                  # horni plocha police nad horni plochou pracovni desky, mm
SKLON_VYCHOZI, SKLON_MIN, SKLON_MAX, SKLON_KROK = 15.0, 5.0, 30.0, 5.0   # sklon sikme police (stupne; vpredu nizsi) - jen u typu `sikma`
KLICE = ("hpolice", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka", "hpolice_sklon")
LAM12_PART = "product_5360"                                           # karta laminovane drevotriky 12 mm (Laminodeska.SEDA.12) - cislo karty doplni nasazeni (apply.sh --lam12-id)
# desky police: id -> karta katalogu (part_id), tloustka (mm; z GLB), zda jde do DRAZKY profilu. GLB: osy X, Y = rozmer (1000 x 1000), Z = tloustka (jako pracovni deska).
DESKY = {
    "lam18": {"part": "product_4933", "tl": 18.0, "drazka": False},       # Laminovana dreviotriska 18 mm (karta 4933, dnesni deska generatoru), 1300 Kc/m2
    "lam12": {"part": LAM12_PART, "tl": 12.0, "drazka": False},           # 12 mm (jen 30 / 35; karta se zaklada neaktivni, viz zaloz_kartu_lam12.py)
    "mdf8": {"part": "product_3939", "tl": 8.0, "drazka": True},          # MDF Steel Grey 8 mm (karta 3939, GLB deska_mdf_seda_8.glb) - do drazky 8 mm (30 / 35)
    "pr10": {"part": "product_3539", "tl": 10.0, "drazka": True},         # topolova foliovana prekliska 10 mm (karta 3539, PR10, GLB pr10.glb) - do drazky 10 mm (40 / 45)
}
DESKY_SYSTEMU = {30: ("lam18", "lam12", "mdf8"), 35: ("lam18", "lam12", "mdf8"), 40: ("lam18", "pr10"), 45: ("lam18", "pr10")}
DRAZKA_DESKA = {30: "mdf8", 35: "mdf8", 40: "pr10", 45: "pr10"}       # deska do drazky podle systemu (drazka 8 / 10 mm)
ROZPON = {None: 800.0, "lam18": 800.0, "lam12": 600.0, "mdf8": 400.0, "pr10": 500.0}      # nejvetsi volny rozpon desky mezi bocnimi a mezi profily (mm) - PREDPOKLAD (Robert upresni)
SKUPINA_DESKY = {k: v["part"] for k, v in DESKY.items()}
DESKA_PARTY = tuple(dict.fromkeys(v["part"] for v in DESKY.values()))       # dily katalogu pouzivane jako desky (cena podle plochy)
PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, PREPAZKA_ODSAZENI = "product_3539", 10.0, 240.0, 2.0       # SSE.vzor.01: 10 x 240 x 306 (hloubka ramu 310 - 2 x 2 mm)
ROZTEC_PREPAZEK = 260.0            # PREDPOKLAD: pocet prepazek podle rozteče (SSE vzor 249 - 293 mm)
LEM_VYSKA = 40.0                   # vyska predniho lemu nad horni plochou pricky (mm) - PREDPOKLAD
LEM_MAX_DELKA = 2500.0            # nejdelsi kus lemu (PR10: tabule 1250 x 2500 mm, karta #3539); delsi lem se deli na stejne kusy
UHELNIK = {30: "product_3045", 35: "product_3045", 40: "product_3207", 45: "product_3207"}     # Uhelnikova spojka 30x30 (#3045, GLB product_2895.glb) / 40x40 (#3207)
UHELNIK_VZDALENOST_MAX = 450.0     # uhelniky lemu: nejvetsi rozteč (mm)
MEZERA_NAD_PANELY = 60.0           # automaticka vyska: spodek ramu police nad horni listou panelu (spojky listy panelu sahaji 27 mm nad ni, spojky police 27 mm pod ramem)
VYSKA_BEZ_PANELU = 150.0           # automaticka vyska bez panelu: spodek ramu police nad horni plochou desky
MEZERA_POD_RAMENEM = 15.0          # nejmene mm volne mezi nejvyssim dilem police a spodkem ramene LED
SIRKA_MIN_PLUS = 120.0             # nejuzsi usek mezi stojkami: 2 x profil + 120 mm
DELKA_DESKY_MIN = 100.0           # deska v drazce: nejmensi delka (podel X) mezi rohovymi spojkami; mensi hloubka police se u drazkovych typu neda
DRAZKA_ZASAH = {30: 8.0, 35: 8.0, 40: 10.0, 45: 10.0}                  # o kolik deska zasahuje do drazky profilu (= sirka drazky; SSE vzor: deska 10 mm zasahuje 10 mm)
SIKMA_MIN_NAD_DESKOU = 50.0        # sikma police: nejnizsi bod (predni pricka, konzole) aspon tolik mm nad horni plochou pracovni desky - PREDPOKLAD (Robert upresni)
# NAKLAPECI KONZOLE (karty #3323 / #3324; GLB = TUHY tvar L: list P1 120 x 30 na lici stojky + pulkruhova deska P2 s otvorem kloubu a obloukovou drazkou). Rozmery MERENE z GLB (viz test_hpolice.py, sekce S):
# y_zad = zadni plocha listu P1 (lezi na PREDNIM licu stojky), z_b = rovina desky P2, na ktere lezi vnejsi lico sikmeho profilu, pivot_y = osa otvoru kloubu (x = 0), pul_x = polovina delky konzoly.
KONZOLE = {30: "product_3323", 35: "product_3323", 40: "product_3324", 45: "product_3324"}
KONZOLE_GEO = {"product_3323": {"y_zad": -3.0, "z_b": 20.02, "pivot_y": 20.98, "pul_x": 60.0},
               "product_3324": {"y_zad": -19.0, "z_b": -3.0, "pivot_y": 0.0, "pul_x": 60.0}}
NAZVY_TYPU = {"rovna": "rovná police s deskou", "ram": "rámová police bez desky", "drazka": "rám s deskou v drážce", "lem": "police s lemem", "prepazky": "rám s přepážkami z překližky",
              "sikma": "šikmá police na boxy (s lemem)"}


def _je_cislo(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v)


def potrebuje_drazku(typ):
    return typ in ("drazka", "prepazky")


def deska_na_vrchu(typ):
    return typ in ("rovna", "lem", "sikma")


def deska_pro(typ, deska, system):
    """Efektivni deska police pro typ a system: rámová bez desky = None, drazkove typy = deska do drazky systemu, jinak vybrana (kanonicka podoba pro hash)."""
    if typ == "ram":
        return None
    if potrebuje_drazku(typ):
        return DRAZKA_DESKA[system]
    return deska


def nabidka_desek(system, typ):
    """Desky, ktere lze k typu police v systemu zvolit (pro schema): ramova = zadne, drazkove = jedna (deska do drazky), jinak laminodesky systemu."""
    if typ == "ram":
        return []
    if potrebuje_drazku(typ):
        return [DRAZKA_DESKA[system]]
    return [d for d in DESKY_SYSTEMU[system] if not DESKY[d]["drazka"]]


def potrebne_party(typ, system):
    """Dily katalogu (part_id), ktere typ police potrebuje bez ohledu na volbu desky shora: deska do drazky, PR10 na prepazky / lem a uhelniky, naklapeci konzole u sikme police. Verejnost smi typ dostat
    jen s jejich aktivnimi kartami."""
    out = set()
    if potrebuje_drazku(typ):
        out.add(DESKY[DRAZKA_DESKA[system]]["part"])
    if typ in ("lem", "prepazky", "sikma"):
        out.update((PREPAZKA_PART, UHELNIK[system]))
    if typ == "sikma":
        out.add(KONZOLE[system])
    return out


def vsechny_party():
    """Vsechny dily katalogu, na kterych horni police v nejakem systemu zavisi (desky, PR10, uhelniky, naklapeci konzole): jejich karty se pro verejnost kontroluji (aktivni, neni archivovana)."""
    out = set(DESKA_PARTY) | {PREPAZKA_PART} | set(UHELNIK.values()) | set(KONZOLE.values())
    return out


def nabidka(system, karty=None):
    """(desky, typy): desky police (id) a typy v nabidce pro `system`, kdyz jsou v nabidce jen karty `karty` (mnozina part_id; None = vsechny - zamestnanec, testy). Typ je v nabidce, kdyz
    jsou v nabidce vsechny jeho potrebne dily (potrebne_party) a - u typu s deskou shora (rovna, lem, sikma) - aspon jedna laminodeska systemu."""
    if system not in DESKY_SYSTEMU:                                                # SSE (system 41) a jine systemy bez horni police: prazdna nabidka
        return (), ()
    vse = karty is None
    desky = tuple(d for d in DESKY_SYSTEMU[system] if vse or DESKY[d]["part"] in karty)
    lamin = [d for d in desky if not DESKY[d]["drazka"]]
    typy = tuple(t for t in TYPY if (vse or potrebne_party(t, system) <= karty) and (not deska_na_vrchu(t) or lamin))
    return desky, typy


def over_parametry(out, sys_):
    """Dokonci normalizaci parametru horni police v `out` (volano z S._norm_parametry): typy, rozsahy, kanonicka podoba (vypnuta police = vychozi ostatni klice, deska podle typu, sklon jen u sikme)."""
    out["hpolice"] = bool(out["hpolice"])
    typ, deska = out["hpolice_typ"], out["hpolice_deska"]
    if typ not in TYPY:
        raise StulChyba(f"hpolice_typ: '{typ}' neni jedna z {', '.join(TYPY)}", "mimo_rozsah")
    if deska not in DESKY:
        raise StulChyba(f"hpolice_deska: '{deska}' neni jedna z {', '.join(DESKY)}", "mimo_rozsah")
    v, h, sk = out["hpolice_vyska"], out["hpolice_hloubka"], out.get("hpolice_sklon", SKLON_VYCHOZI)
    if v is not None:
        if not _je_cislo(v):
            raise StulChyba("hpolice_vyska: neni cislo", "mimo_rozsah")
        if not VYSKA_MIN <= v <= VYSKA_MAX:
            raise StulChyba(f"hpolice_vyska {v} mm je mimo rozsah {VYSKA_MIN:g}-{VYSKA_MAX:g} mm", "mimo_rozsah")
        out["hpolice_vyska"] = float(v)
    if not _je_cislo(h):
        raise StulChyba("hpolice_hloubka: neni cislo", "mimo_rozsah")
    if not HLOUBKA_MIN <= h <= HLOUBKA_MAX:
        raise StulChyba(f"hpolice_hloubka {h} mm je mimo rozsah {HLOUBKA_MIN:g}-{HLOUBKA_MAX:g} mm", "mimo_rozsah")
    out["hpolice_hloubka"] = float(h)
    if not _je_cislo(sk):
        raise StulChyba("hpolice_sklon: neni cislo", "mimo_rozsah")
    if not SKLON_MIN <= sk <= SKLON_MAX:
        raise StulChyba(f"hpolice_sklon {sk} st. je mimo rozsah {SKLON_MIN:g}-{SKLON_MAX:g} st.", "mimo_rozsah")
    out["hpolice_sklon"] = float(sk)
    if out["hpolice"]:
        if typ == "ram" or potrebuje_drazku(typ):
            out["hpolice_deska"] = deska_pro(typ, deska, sys_) or DESKA_VYCHOZI         # nepouzita / pevna deska: jedna kanonicka podoba
        elif deska not in DESKY_SYSTEMU.get(sys_, ()) or DESKY[deska]["drazka"]:
            raise StulChyba(f"hpolice_deska: '{deska}' se u typu police '{typ}' v systemu {sys_} nepouziva (mozne: {', '.join(nabidka_desek(sys_, typ))})", "mimo_rozsah")
        if typ != "sikma":
            out["hpolice_sklon"] = SKLON_VYCHOZI                                         # sklon se pouziva jen u sikme police: jedna kanonicka podoba
    else:
        out["hpolice_typ"], out["hpolice_deska"] = TYP_VYCHOZI, DESKA_VYCHOZI
        out["hpolice_vyska"], out["hpolice_hloubka"], out["hpolice_sklon"] = None, HLOUBKA_VYCHOZI, SKLON_VYCHOZI
    return out


def kanon_hash(p):
    """Zahodi klice horni police, ktere se do hashe nepocitaji (vypnuta / bez stojek = vsechny; nezadana vyska; nepouzita deska; sklon jinde nez u sikme) - hashe stolu bez police zustavaji."""
    if not (p["hpolice"] and p["stojky"]):
        for k in KLICE:
            p.pop(k, None)
        return p
    if p.get("hpolice_vyska") is None:
        p.pop("hpolice_vyska", None)
    if p["hpolice_typ"] == "ram":
        p.pop("hpolice_deska", None)
    if p["hpolice_typ"] != "sikma":
        p.pop("hpolice_sklon", None)
    return p


# ---------------------------------------------------------------------------------------------------------------------
# geometrie
# ---------------------------------------------------------------------------------------------------------------------
def _kvat_z_matice(R):
    """Kvaternion (x, y, z, w) z rotacni matice 3x3."""
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        return ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s)
    if R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        return (0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s, (R[2][1] - R[1][2]) / s)
    if R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        return ((R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s, (R[0][2] - R[2][0]) / s)
    s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
    return ((R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s, (R[1][0] - R[0][1]) / s)


Q_DESKA = (-0.7071067811865476, 0.0, 0.0, 0.7071067811865476)      # deska 1000 x 1000 x T lezi: X = hloubka, Y -> -Z (sirka), tloustka nahoru (jako pracovni deska)
Q_PRI_Z = (0.0, 0.0, 0.0, 1.0)                                          # svisla deska s normalou Z: X = hloubka, Y = vyska, Z = tloustka (prepazka)
Q_PRI_X = (0.0, 0.7071067811865476, 0.0, 0.7071067811865476)            # svisla deska s normalou X (lem): lokalni X -> -Z (delka), Y = vyska, Z -> +X (tloustka)


def _deska(part_id, q, rozmer, stred):
    """Clen desky (druh `deska`): GLB 1000 x 1000 x T se meritkem [x/1000, y/1000, 1], jeho STRED v bode `stred` (svet, mm); `rozmer` = (delka lokalni X, delka lokalni Y) v mm."""
    lo, hi = S.glb_bbox(part_id)
    lc = (lo + hi) / 2.0
    Rm = S.kvat_na_matici(q)
    s = np.array([rozmer[0] / 1000.0, rozmer[1] / 1000.0, 1.0])
    return S._clen(part_id, q, s.tolist(), np.array(stred, float) - Rm @ (s * lc), "deska", src=None)


def _uhelnik(part_id, e_n, bod_dotyku):
    """Clen uhelniku (Uhelnikova spojka): L profil, jehoz VNEJSI ROH lezi v `bod_dotyku` (svet): jedno rameno lezi na vodorovne plose (vnejsi plocha dole), druhe stoji svisle PROTI desce
    (vnejsi plocha u desky) a RAMENO NA PLOSE miri od desky ve smeru `e_n` (jednotkovy vektor, osa X nebo Z). Lokalne: x = rameno na plose (od desky), y = sirka, z = -nahoru."""
    lo, hi = S.glb_bbox(part_id)
    en = np.array(e_n, float)
    nahoru = np.array([0.0, 1.0, 0.0])
    ez = -nahoru
    ey = np.cross(ez, en)
    R = np.array([en, ey, ez]).T                                        # sloupce = obrazy lokalnich os x, y, z
    lokalni_roh = np.array([lo[0], (lo[1] + hi[1]) / 2.0, hi[2]])      # vnejsi roh (x = 0 plocha u desky, z = 0 plocha na podlozce) uprostred sirky
    pos = np.array(bod_dotyku, float) - R @ lokalni_roh
    return S._clen(part_id, _kvat_z_matice(R), [1.0, 1.0, 1.0], pos, "prisl", src=None), {"ramena": float(hi[0] - lo[0]), "sirka": float(hi[1] - lo[1]), "vyska": float(hi[2] - lo[2])}


def _vyska_nad_panely(clenove):
    """Horni lico nejvyssi liste panelu (klic ("panrail", ...)) nebo None bez panelu."""
    y = [float(S._aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})[1][1])
         for k, c in clenove.items() if isinstance(k, tuple) and k and k[0] == "panrail"]
    return max(y) if y else None


def _rozpony(a, b, rozpon, P):
    """Osy mezilist (profil sirky P) uvnitr volneho useku [a, b] mezi bocnimi profily: nejmensi pocet n, pri kterem jsou VOLNA POLE mezi profily (stejna) nejvyse `rozpon`;
    volne pole g = ((b - a) - n x P) / (n + 1), osa j-teho mezilisty = a + (j + 1) x g + j x P + P / 2."""
    n = 0
    while ((b - a) - n * P) / (n + 1) > rozpon + 1e-9 and n < 50:
        n += 1
    g = ((b - a) - n * P) / (n + 1)
    return [a + (j + 1) * g + j * P + P / 2.0 for j in range(n)]


# ---------------------------------------------------------------------------------------------------------------------
# SIKMA POLICE: geometrie vuci ose zadni pricky O (stred prurezu) PO naklonu; x dopredu je zaporne, nahoru kladne. Nakloneni o th kolem osy Z pres O (vpredu dolu).
# ---------------------------------------------------------------------------------------------------------------------
def sikma_rel(P, tl, dout, th, system):
    """Charakteristicke body naklonene police (mm vuci osa O zadni pricky, po naklonu o th [rad]): horni zadni roh desky (`rear_top`; to je vyska police), nejnizsi roh zadni pricky, nejnizsi roh predni pricky,
    horni zadni roh lemu, vyska stredu konzoly `y_c` (osa sikmeho profilu prochazi osou kloubu), nejvyssi (`high`) a nejnizsi (`low`) bod police vcetne konzoly."""
    H = P / 2.0
    c, s = math.cos(th), math.sin(th)
    g = KONZOLE_GEO[KONZOLE[system]]
    dpiv = g["pivot_y"] - g["y_zad"]                                          # osa kloubu je o tolik pred predním licem stojky
    y_c = -(H + dpiv) * math.tan(th)
    rear_top = H * s + (H + tl) * c
    rear_low = -H * (c + s)
    front_low = -(dout - P) * s - H * (c + s)
    lip_top = (-(dout - P) - H + PREPAZKA_TL) * s + (H + LEM_VYSKA) * c
    lo_c, hi_c = S.glb_bbox(S.SYSTEMY[system]["spojka"])
    extra_konz = max(0.0, float(max(hi_c - lo_c)) + 5.0 - MEZERA_POD_RAMENEM)        # pod ramenem LED visi u zadnich stojek rohova spojka (rameno 29 / 40 mm): konzola (na lici stojky) musi pod ni + 5 mm
    high = max(rear_top, lip_top, y_c + g["pul_x"] + extra_konz, H * (s + c))
    low = min(front_low, y_c - g["pul_x"], rear_low)
    return {"y_c": y_c, "dpiv": dpiv, "rear_top": rear_top, "rear_low": rear_low, "front_low": front_low, "lip_top": lip_top, "high": high, "low": low}


def _strop(k):
    ramena = [c for kk, c in k["clenove"].items() if kk in (("t", S.XRAIL_TOP_L), ("t", S.XRAIL_TOP_P))]
    return (min(float(c["pos"][1]) for c in ramena) - S._H()) if ramena else float(k["y_vrch"])          # spodek ramene LED, jinak vrch zadnich stojek


def _meze_sikma(k):
    """meze_uvod() pro sikmou polici: vyska = horni plocha desky na ZADNIM okraji; spodek zadni pricky nad panely (+ MEZERA_NAD_PANELY), nejnizsi bod nad deskou stolu, nejvyssi bod pod ramenem LED."""
    p, clenove = k["p"], k["clenove"]
    P, H = S._P(), S._H()
    system = int(p["system"])
    deska = deska_pro("sikma", p["hpolice_deska"], system)
    tl = DESKY[deska]["tl"]
    th = math.radians(float(p["hpolice_sklon"]))
    y_deska_hor = float(k["y_deska"])
    y_strop = _strop(k)
    xr, xf = float(k["xr"]), float(k["xf"])
    h_min, h_max = HLOUBKA_MIN, min(HLOUBKA_MAX, (xr - xf) + P)
    dout = min(max(float(p["hpolice_hloubka"]), h_min), max(h_max, h_min))
    rel = sikma_rel(P, tl, dout, th, system)
    y_pan = _vyska_nad_panely(clenove)
    hv_max = (y_strop - MEZERA_POD_RAMENEM) - y_deska_hor + rel["rear_top"] - rel["high"]
    hv_desk = SIKMA_MIN_NAD_DESKOU - rel["low"] + rel["rear_top"]
    hv_pan = (y_pan + MEZERA_NAD_PANELY - y_deska_hor + rel["rear_top"] - rel["rear_low"]) if y_pan is not None else None
    min_raw = max(VYSKA_MIN, hv_desk, hv_pan if hv_pan is not None else VYSKA_MIN)
    auto_raw = hv_pan if hv_pan is not None else (VYSKA_BEZ_PANELU - rel["low"] + rel["rear_top"])
    hv_min = math.ceil(min_raw / 10.0 - 1e-9) * 10.0
    hv_auto = math.ceil(max(auto_raw, min_raw) / 10.0 - 1e-9) * 10.0
    zadana = p["hpolice_vyska"]
    hv = hv_auto if zadana is None else min(max(float(zadana), hv_min), max(hv_max, hv_min))
    return {"P": P, "H": H, "typ": "sikma", "deska": deska, "tl_vrch": tl, "extra": 0.0, "y_deska_hor": y_deska_hor, "hv": hv, "hv_min": hv_min, "hv_max": hv_max, "hv_auto": hv_auto,
            "auto": zadana is None, "dout": dout, "h_min": h_min, "h_max": h_max, "gap_c": 0.0, "y_pan": y_pan, "y_strop": y_strop, "rel": rel, "th": th,
            "sekci_n": len(S._pole_panelu(k["zl"], k["zr"], k["zm"], k["rezim"]))}


def meze_uvod(k):
    """Spolecne vypocty (vyska, hloubka, meze) pro postav() i pro dotazy; vraci dict."""
    p, clenove = k["p"], k["clenove"]
    typ = p["hpolice_typ"]
    if typ == "sikma":
        return _meze_sikma(k)
    P, H = S._P(), S._H()
    deska = deska_pro(typ, p["hpolice_deska"], int(p["system"]))
    tl_vrch = DESKY[deska]["tl"] if (deska and deska_na_vrchu(typ)) else 0.0           # deska lezi na rame: horni plocha police = horni lico ramu + tloustka
    extra = PREPAZKA_VYSKA if typ == "prepazky" else (LEM_VYSKA if typ == "lem" else 0.0)       # co jeste cnici nad horni plochu (prepazky, lem)
    y_deska_hor = float(k["y_deska"])
    y_strop = _strop(k)
    hv_max = (y_strop - MEZERA_POD_RAMENEM) - extra - y_deska_hor
    y_pan = _vyska_nad_panely(clenove)
    y_dolni_auto = (y_pan + MEZERA_NAD_PANELY) if y_pan is not None else (y_deska_hor + VYSKA_BEZ_PANELU)
    hv_auto = math.ceil((y_dolni_auto + P + tl_vrch - y_deska_hor) / 10.0 - 1e-9) * 10.0      # automaticka vyska zaokrouhlena NAHORU na 10 mm (posuvnik v UI jde po 10 mm)
    hv_min = max(VYSKA_MIN, hv_auto) if y_pan is not None else VYSKA_MIN               # s panely nejnize na automatickou vysku (rám police sedí mezi stejnymi stojkami jako panely: pod ne nejde)
    zadana = p["hpolice_vyska"]
    hv = hv_auto if zadana is None else min(max(float(zadana), hv_min), max(hv_max, hv_min))
    xr, xf = float(k["xr"]), float(k["xf"])
    h_max = min(HLOUBKA_MAX, (xr - xf) + P)
    gap_c = 0.0
    h_min = HLOUBKA_MIN
    if potrebuje_drazku(typ):                                                          # deska v drazce nesmi do rohu ramu, kde sedi rohove spojky: konci o rameno spojky + 1 mm pred pricnymi profily
        lo_c, hi_c = S.glb_bbox(S.SYSTEMY[int(p["system"])]["spojka"])
        gap_c = round(float(max(hi_c - lo_c)) + 1.0, 2)
        h_min = max(HLOUBKA_MIN, math.ceil((2.0 * P + 2.0 * gap_c + DELKA_DESKY_MIN) / 10.0) * 10.0)
    dout = min(max(float(p["hpolice_hloubka"]), h_min), max(h_max, h_min))
    return {"P": P, "H": H, "typ": typ, "deska": deska, "tl_vrch": tl_vrch, "extra": extra, "y_deska_hor": y_deska_hor, "hv": hv, "hv_min": hv_min, "hv_max": hv_max, "hv_auto": hv_auto,
            "auto": zadana is None, "dout": dout, "h_min": h_min, "h_max": h_max, "gap_c": gap_c, "y_pan": y_pan, "y_strop": y_strop}


def _typy(k):
    """Pro KAZDY typ police: vejde se do dane konstrukce (aspon jedna vyska: automaticka vyska ani minimum nepresahne strop; sikma jen u stolu s jednim usekem mezi stojkami) a jeho meze vysky;
    `duvod` (misto | hloubka | sekce | None); nezavisi na zvolene vysce ani typu (nabidka typu v UI)."""
    p = k["p"]
    out = []
    for t in TYPY:
        m = meze_uvod({**k, "p": {**p, **nastav_typ(p, t), "hpolice_vyska": None}})
        mista = bool(m["hv_min"] <= m["hv_max"] + 1e-6 and m["hv_auto"] <= m["hv_max"] + 1e-6)
        hloubka_ok = bool(m["h_min"] <= m["h_max"] + 1e-6)
        sekce_ok = (m.get("sekci_n", 1) <= 1) if t == "sikma" else True
        duvod = None if (mista and hloubka_ok and sekce_ok) else ("sekce" if not sekce_ok else ("misto" if not mista else "hloubka"))
        out.append({"typ": t, "vejde": duvod is None, "duvod": duvod, "min": round(m["hv_min"], 1), "max": round(m["hv_max"], 1)})
    return out


def _konzoly(system, P, xr, y_s, th, sekce):
    """Naklapeci konzoly sikme police: [{s, j, part_id, pos, quat}] - na kazdou sekci 2 (j = 0 levy, 1 pravy bocni profil). List P1 lezi na PREDNIM licu stojky (x = xr - P / 2), kolmo k ose Z,
    deska P2 s kloubem na vnejsim (stojce privracenem) licu bocniho profilu (z = a_ / b_); osa sikmeho profilu prochazi osou kloubu (stred konzoly ve vysce y_c vuci ose zadni pricky)."""
    H = P / 2.0
    part = KONZOLE[system]
    g = KONZOLE_GEO[part]
    y_c = y_s - (H + g["pivot_y"] - g["y_zad"]) * math.tan(th)
    Q = np.array([0.0, g["y_zad"], g["z_b"]])
    M_levy = np.array([[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])         # lokalni x -> -y, y -> -x (dopredu), z -> -z (do stojky nalevo)
    M_pravy = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])          # lokalni x -> +y, y -> -x (dopredu), z -> +z (do stojky napravo)
    out = []
    for s_, a_, b_ in sekce:
        for j, (z_lico, M) in enumerate(((a_, M_levy), (b_, M_pravy))):
            T = np.array([xr - H, y_c, z_lico])
            out.append({"s": s_, "j": j, "part_id": part, "pos": T - M @ Q, "quat": _kvat_z_matice(M)})
    return out


def postav(k):
    """Postavi horni polici do `k["clenove"]` (+ spojky do `k["odvozene"]`); vraci `hpolice_info` (dict) nebo None, neni-li zapnuta. Nic nemaze, jen pridava clenu s klici ("hpol", ...).
    SIKMA: ram se postavi PLOCHY (jako lem) a oznaci `hp_rot`; otoci se az pri vystupu do `dily` (rotuj); konzoly pridava pridej_konzoly (az po zaslepkach volnych koncu)."""
    p, sab, clenove, odvozene = k["p"], k["sab"], k["clenove"], k["odvozene"]
    if not (p["hpolice"] and p["stojky"]):
        return None
    system = int(p["system"])
    m = meze_uvod(k)
    P, H, typ, deska = m["P"], m["H"], m["typ"], m["deska"]
    sikma = typ == "sikma"
    tg = "lem" if sikma else typ                                                       # geometricky typ desky / lemu / uhelniku (sikma = lem + naklon)
    info = {"typ": typ, "deska": deska, "tl": DESKY[deska]["tl"] if deska else 0.0, "sekci": 0, "preskoceno": 0, "problem": None, "nazev": NAZVY_TYPU[typ],
            "vyska": {"hodnota": round(m["hv"], 1), "min": m["hv_min"], "max": round(m["hv_max"], 1), "auto": m["auto"], "auto_hodnota": round(m["hv_auto"], 1)},
            "hloubka": {"hodnota": round(m["dout"], 1), "min": m["h_min"], "max": round(m["h_max"], 1)},
            "desky_nabidka": nabidka_desek(system, typ), "typy": _typy(k), "prepazek": 0, "uhelniku": 0, "rotace": None, "konzoly": [], "pary": []}
    if sikma:
        info["sklon"] = {"hodnota": round(float(p["hpolice_sklon"]), 1), "min": SKLON_MIN, "max": SKLON_MAX}
    if m["hv_max"] < m["hv_min"] or (m["auto"] and m["hv_auto"] > m["hv_max"] + 1e-6):
        info["problem"] = "misto"                                                     # mezi panely / deskou a ramenem LED (stojkami) neni pro polici misto
        return info
    if m["h_max"] < m["h_min"] - 1e-6:
        info["problem"] = "hloubka"                                                   # stul je mensi (mene hluboky), nez vyzaduje nejmensi hloubka tohoto typu police
        return info
    if sikma and m["sekci_n"] > 1:
        info["problem"] = "sekce"                                                     # sikma police: jen jeden usek mezi zadnimi stojkami (dve konzole na jednu stredni stojku se nevejdou)
        return info
    p["hpolice_vyska"] = None if m["auto"] else round(float(m["hv"]), 1)
    p["hpolice_hloubka"] = round(float(m["dout"]), 1)
    xr = float(k["xr"])
    dout = m["dout"]
    xf_c = xr + P - dout                                                              # osa predni pricky (vnejsi hloubka ramu = od zadniho lice zadni pricky po predni lico predni)
    x_st = (xr + xf_c) / 2.0                                                          # stred bocnich profilu (mezi licem zadni a predni pricky)
    delka_b = dout - 2.0 * P                                                          # delka bocniho profilu mezi pricky
    if sikma:
        y_s = m["y_deska_hor"] + m["hv"] - m["rel"]["rear_top"]                       # osa zadni pricky (stred otaceni): po naklonu je horni zadni roh desky ve vysce `hv`
    else:
        y_s = m["y_deska_hor"] + m["hv"] - H - m["tl_vrch"]                           # osa ramu (vsechny profily police ve stejne vysce)
    y_rt = y_s + H                                                                    # horni lico ramu
    zasah = DRAZKA_ZASAH[system]
    rozpon = ROZPON[deska]
    sirka_min = 2.0 * P + SIRKA_MIN_PLUS
    uh_part = UHELNIK[system]
    dl_tabule = float(S.max_delka_desky())
    klice_sekci = []
    sekce_geo = []
    for s_, (a_, b_, kl, kr) in enumerate(S._pole_panelu(k["zl"], k["zr"], k["zm"], k["rezim"])):
        G = b_ - a_
        if G < sirka_min - 1e-6:
            info["preskoceno"] += 1
            continue
        zc = (a_ + b_) / 2.0
        kz, kp = ("hpol", s_, "zad"), ("hpol", s_, "pred")
        clenove[kz] = S._klon(sab, S.ZRAIL_PANEL, [float(k["xr"]), y_s, zc], delka=G)
        clenove[kp] = S._klon(sab, S.ZRAIL_TOP, [xf_c, y_s, zc], delka=G)
        clenove[kz]["konce"], clenove[kp]["konce"] = ((False, False) if sikma else (True, True)), (False, False)
        boky = []
        for j, zb in enumerate((a_ + H, b_ - H)):
            kb = ("hpol", s_, "bok", j)
            clenove[kb] = S._klon(sab, S.XRAIL_PRAC_L, [x_st, y_s, zb], delka=delka_b)
            clenove[kb]["konce"] = (False, False) if sikma else (True, True)
            boky.append(kb)
        mezi = []
        for j, zmj in enumerate(_rozpony(a_ + P, b_ - P, rozpon, P)):
            kb = ("hpol", s_, "mezi", j)
            clenove[kb] = S._klon(sab, S.XRAIL_PRAC_L, [x_st, y_s, zmj], delka=delka_b)
            clenove[kb]["konce"] = (False, False) if sikma else (True, True)
            mezi.append((kb, zmj))
        # spoje: zadni pricka na stojky (analogie panelu 42 / 45, spojka otocena POD pricku; u sikme ne - ram drzi konzoly), bocni a mezilisty na pricky (analogie 36 / 37)
        if not sikma:
            odvozene.append((42, {12: kl, 14: kz}, (), [("x", 90)]))
            odvozene.append((45, {13: kr, 14: kz}, (), [("x", -90)]))
        for j, kb in enumerate(boky):
            vnitrni = (37 if j == 0 else 36)                                          # leva lista: vnitrni strana je +z (37: nohy +x, -z -> po otoceni o 180 st. kolem Y +z), prava opacne
            odvozene.append((36 if j == 0 else 37, {5: kp, 6: kb}))                   # predni konec: lista za pricku (+x), vnitrni strana
            odvozene.append((vnitrni, {5: kz, 6: kb}, (), [("y", 180)]))               # zadni konec: lista pred pricku (-x), vnitrni strana
        for kb, _z in mezi:
            for c_ in (36, 37):
                odvozene.append((c_, {5: kp, 6: kb}))
                odvozene.append((c_, {5: kz, 6: kb}, (), [("y", 180)]))
        if sikma:                                                                     # profil - profil: boky / mezilisty na obe pricky (pary pro lic_peers: AABB naklonenych profilu spoj nepozna)
            for kb in boky + [kk for kk, _z in mezi]:
                info["pary"] += [(kz, kb), (kp, kb)]
            info["pary"] += [(kl, boky[0]), (kr, boky[1])]                            # naklapeci konzola = spoj stojka - bocni profil (jako sikma vzpera: spoj pres spojku se pocita jako spoj profilu - prace za spoj v cene)
        # desky
        osy_z = [a_ + P] + [c for _, c in mezi] + [b_ - P]                                # vnitrni lice leveho boku, stredy mezilist, vnitrni lice praveho boku
        if deska and deska_na_vrchu(tg):
            tl = DESKY[deska]["tl"]
            x_od = (xf_c - H) if tg != "lem" else None
            if tg == "lem":
                uh_lo, uh_hi = S.glb_bbox(uh_part)
                x_od = xf_c - H + PREPAZKA_TL + float(uh_hi[0] - uh_lo[0]) + 1.0     # deska konci za rameny uhelniku lemu
            x_do = float(k["xr"]) + H
            hranice = [a_]
            z_mezi = sorted(z for _, z in mezi)
            while b_ - hranice[-1] > dl_tabule + 1e-6:                                # siroka deska se deli v osach mezilist: kazdy kus nejdelsi, jaky se jeste vejde do tabule
                kand = [z for z in z_mezi if hranice[-1] + 1e-6 < z <= hranice[-1] + dl_tabule + 1e-6]
                if not kand:
                    break                                                             # mezilisty jsou dal nez delka tabule: deli se nema cim, kontrola `deska_mimo_tabuli` to ohlasi
                hranice.append(max(kand))
            hranice.append(b_)
            for q_, (z0, z1) in enumerate(zip(hranice, hranice[1:])):
                kd = ("hpol", s_, "deska", q_)
                clenove[kd] = _deska(DESKY[deska]["part"], Q_DESKA, (x_do - x_od, z1 - z0), ((x_od + x_do) / 2.0, y_rt + tl / 2.0, (z0 + z1) / 2.0))
                clenove[kd]["deska_id"] = f"hpol{s_}d{q_}"
        elif deska and potrebuje_drazku(tg):
            tl = DESKY[deska]["tl"]
            x_od, x_do = (xf_c + H) + m["gap_c"], (float(k["xr"]) - H) - m["gap_c"]          # podel X mezi rohovymi spojkami (v hornim / dolnim okraji drazky bocnich profilu)
            for q_, (z0, z1) in enumerate(zip(osy_z, osy_z[1:])):
                # pole mezi profily: vnitrni lice leveho profilu .. vnitrni lice praveho; mezilista maji sirku P (stred osy_z[q]), kraj ma uz vnitrni lice
                z_l = z0 if q_ == 0 else z0 + H
                z_p = z1 if q_ == len(osy_z) - 2 else z1 - H
                kd = ("hpol", s_, "deska", q_)
                clenove[kd] = _deska(DESKY[deska]["part"], Q_DESKA, (x_do - x_od, (z_p - z_l) + 2.0 * zasah), ((x_od + x_do) / 2.0, y_s, (z_l + z_p) / 2.0))
                clenove[kd]["deska_id"] = f"hpol{s_}d{q_}"
                clenove[kd]["zasazeno_do"] = boky + [kk for kk, _z in mezi]                    # zasahuje jen do drazek bocnich a strednich profilu (podel X konci pred rohovymi spojkami)
        # prepazky + uhelniky (SSE): stoji na horních plochach zadni a predni pricky
        if tg == "prepazky":
            pocet = max(0, int(round(G / ROZTEC_PREPAZEK)) - 1)
            dx = dout - 4.0 * PREPAZKA_ODSAZENI
            for j in range(pocet):
                zj = a_ + (j + 1) * G / (pocet + 1)
                kd = ("hpol", s_, "prep", j)
                clenove[kd] = _deska(PREPAZKA_PART, Q_PRI_Z, (dx, PREPAZKA_VYSKA), (x_st, y_rt + PREPAZKA_VYSKA / 2.0, zj))
                clenove[kd]["deska_id"] = f"hpol{s_}p{j}"
                sA = 1.0 if j % 2 == 0 else -1.0                                       # stridave: na predni pricce strana +z a na zadni -z (a naopak), jako v SSE.vzor.01
                for n_, (x_pric, znak) in enumerate(((xf_c, sA), (float(k["xr"]), -sA))):
                    uh, rozm = _uhelnik(uh_part, (0.0, 0.0, znak), (x_pric, y_rt, zj + znak * PREPAZKA_TL / 2.0))
                    clenove[("hpol", s_, "uhel", j, n_)] = uh
                info["prepazek"] += 1
                info["uhelniku"] += 2
        if tg == "lem":
            n_l = max(1, int(math.ceil(G / LEM_MAX_DELKA - 1e-9)))
            for q_ in range(n_l):                                                     # lem je jeden pas; delsi nez tabule PR10 se deli na stejne kusy
                z0, z1 = a_ + q_ * G / n_l, a_ + (q_ + 1) * G / n_l
                kd = ("hpol", s_, "lem", q_)
                clenove[kd] = _deska(PREPAZKA_PART, Q_PRI_X, (z1 - z0, LEM_VYSKA), (xf_c - H + PREPAZKA_TL / 2.0, y_rt + LEM_VYSKA / 2.0, (z0 + z1) / 2.0))
                clenove[kd]["deska_id"] = f"hpol{s_}l{q_}"
            n_b = max(2, int(math.ceil(G / UHELNIK_VZDALENOST_MAX)))
            for j in range(n_b):
                zb = a_ + 60.0 + j * (G - 120.0) / (n_b - 1)
                uh, rozm = _uhelnik(uh_part, (1.0, 0.0, 0.0), (xf_c - H + PREPAZKA_TL, y_rt, zb))
                clenove[("hpol", s_, "uhel", 0, j)] = uh
                info["uhelniku"] += 1
        klice_sekci.append(s_)
        sekce_geo.append((s_, a_, b_))
        info["sekci"] += 1
    if not klice_sekci:
        info["problem"] = "sirka"
        return info
    if sikma:                                                                         # ram se otoci az pri vystupu do dily (viz rotuj / v_rotaci); konzoly pridava pridej_konzoly
        for kk, cc in clenove.items():
            if isinstance(kk, tuple) and kk and kk[0] == "hpol":
                cc["hp_rot"] = True
        info["rotace"] = {"O": (xr, y_s), "phi": m["th"]}
        info["konzoly"] = _konzoly(system, P, xr, y_s, m["th"], sekce_geo)
    return info


# ---------------------------------------------------------------------------------------------------------------------
# SIKMA POLICE: otoceni ramu pri vystupu, konzoly, presna kontrola kolizi
# ---------------------------------------------------------------------------------------------------------------------
def v_rotaci(k, c, clenove):
    """Je dil (klic `k`, clen / spojka `c`) soucasti NAKLONENEHO ramu sikme police (rotuje se tuhe kolem osy zadni pricky)? Clen s `hp_rot`, spojka s vlastnikem z ramu, zaslepka konce jeho profilu."""
    if isinstance(k, tuple) and k and k[0] == "hpol":
        return bool(c.get("hp_rot"))
    vl = c.get("vlastnici")
    if vl:
        return any(isinstance(v, tuple) and v and v[0] == "hpol" and bool(clenove.get(v, {}).get("hp_rot")) for v in vl)
    if isinstance(k, tuple) and len(k) == 3 and k[0] == "zasl":
        o = k[1]
        return isinstance(o, tuple) and bool(o) and o[0] == "hpol" and bool(clenove.get(o, {}).get("hp_rot"))
    return False


def v_skupine(k, c, clenove):
    """Dil sikme police pro presnou kontrolu kolizi: naklonene dily + konzoly (osove rovnobezne, ale AABB kontrola generatoru se pro cele skupiny vypina)."""
    return v_rotaci(k, c, clenove) or bool(c.get("hp_skup"))


def rotuj(rotace, pos, quat):
    """Pozice a kvaternion dilu po otoceni o `phi` kolem osy rovnobezne s Z, ktera prochazi bodem O = (x, y) (osa zadni pricky); kladne phi = vpredu (mensi x) dolu."""
    ox, oy = rotace["O"]
    ph = float(rotace["phi"])
    c, s = math.cos(ph), math.sin(ph)
    dx, dy = float(pos[0]) - ox, float(pos[1]) - oy
    qz = (0.0, 0.0, math.sin(ph / 2.0), math.cos(ph / 2.0))
    return (ox + dx * c - dy * s, oy + dx * s + dy * c, float(pos[2])), S._kvat_nasob(qz, tuple(float(v) for v in quat))


def pro_vzpery(info, kl_vse, bb_vse, clenove, spojky):
    """Sikma police a vzpery ramen LED: pole obalek `bb_vse` (kontrola delky vzper) ma u naklonenych dilu obalku PLOCHEHO ramu (otaci se az pri vystupu do `dily`) a konzoly jeste neexistuji.
    Vraci (kl_vse, bb_vse) s obalkami naklonenych dilu v definitivni poloze a s konzolami navic: vzpera se pak prizpusobi sikme police stejne jako ostatnim dilum (jako u rovnych typu police)."""
    if not info or not info.get("rotace"):
        return kl_vse, bb_vse
    bb = np.array(bb_vse, float)
    for n, k in enumerate(kl_vse):
        c = clenove[k] if k in clenove else spojky[k]
        if v_rotaci(k, c, clenove):
            pos, q = rotuj(info["rotace"], c["pos"], c["quaternion"])
            bb[n] = S._aabb({"part_id": c["part_id"], "quaternion": q, "scale": c["scale"], "position": pos})
    kz_ = info.get("konzoly") or ()
    if not kz_:
        return kl_vse, bb
    extra = np.array([S._aabb({"part_id": kz["part_id"], "quaternion": kz["quat"], "scale": [1.0, 1.0, 1.0], "position": kz["pos"]}) for kz in kz_], float)
    return list(kl_vse) + [("hpol", kz["s"], "konz", kz["j"]) for kz in kz_], np.concatenate([bb, extra])


def pridej_konzoly(info, clenove):
    """Prida do `clenove` naklapeci konzoly sikme police (az po zaslepkach volnych koncu: jinak by se dotykaly koncu profilu v PLOCHEM stavu). Klic ("hpol", usek, "konz", j)."""
    for kz in (info or {}).get("konzoly") or ():
        c = S._clen(kz["part_id"], kz["quat"], [1.0, 1.0, 1.0], np.array(kz["pos"], float), "prisl", src=None)
        c["hp_skup"] = True
        clenove[("hpol", kz["s"], "konz", kz["j"])] = c


def _obb(d):
    """(stred, osy po sloupcich, polorozmery) obalky dilu `d` (dict position / quaternion / scale) z GLB bbox."""
    lo, hi = S.glb_bbox(d["part_id"])
    R = S.kvat_na_matici(d["quaternion"])
    s = np.array(d["scale"], float)
    c_l = (np.array(lo, float) + np.array(hi, float)) / 2.0
    return np.array(d["position"], float) + R @ (s * c_l), R, np.abs(s) * (np.array(hi, float) - np.array(lo, float)) / 2.0


def _sat_obb_obb(c1, R1, h1, c2, R2, h2):
    """Hloubka pruniku dvou OBB (mm; <= 0 = bez pruniku): nejmensi presah pres 15 delicich os (SAT). R = osy po sloupcich, h = polorozmery."""
    A, B = R1.T, R2.T
    osy = list(A) + list(B) + [np.cross(a_, b_) for a_ in A for b_ in B]
    nej = None
    for o in osy:
        n = float(np.linalg.norm(o))
        if n < 1e-9:
            continue
        o = o / n
        pr = float(np.sum(np.abs(R1.T @ o) * h1)) + float(np.sum(np.abs(R2.T @ o) * h2)) - abs(float(np.dot(c2 - c1, o)))
        nej = pr if nej is None else min(nej, pr)
    return float(nej)


def _osove(R):
    """Jsou osy OBB rovnobezne se souradnymi osami (pak je AABB totez co OBB)?"""
    return bool(np.all(np.abs(R).max(axis=0) > 1.0 - 1e-6))


def zkontroluj(info, dily, bb, idx, clenove, spojky):
    """PRESNA kontrola kolizi sikme police (AABB kontrola generatoru se pro ni vypina): kazdy dil skupiny (naklonene dily + konzoly) jako OBB proti AABB vsech ostatnich dilu stolu (SAT);
    prunik hlubsi nez TOL_PRUNIK_MM = problem `hpolice_nevejde` (polici pak generator sam odebere)."""
    if not info or not info.get("rotace"):
        return []
    skup = {idx[kk] for kk, cc in list(clenove.items()) + list(spojky.items()) if kk in idx and v_skupine(kk, cc, clenove)}
    ostatni = [i for i in range(len(dily)) if i not in skup]
    if not skup or not ostatni:
        return []
    lo = np.array([bb[i][0] for i in ostatni])
    hi = np.array([bb[i][1] for i in ostatni])
    nalezeno = []
    sikme = {jj: _obb(dily[i_o]) for jj, i_o in enumerate(ostatni) if not _osove(_obb(dily[i_o])[1])}      # sikme dily stolu (profil vzpery): jejich AABB je velka a falesne se protina, proto OBB x OBB
    for i in sorted(skup):
        c_w, R, h = _obb(dily[i])
        dep = S._sat_obb_aabb_davka(c_w, R, h, lo, hi)
        for jj, (c2, R2, h2) in sikme.items():
            dep[jj] = _sat_obb_obb(c_w, R, h, c2, R2, h2)
        for jj in np.nonzero(dep > S.TOL_PRUNIK_MM)[0]:
            nalezeno.append((i, ostatni[int(jj)], float(dep[jj])))
    if not nalezeno:
        return []
    nalezeno.sort(key=lambda t: -t[2])
    i, j, dp = nalezeno[0]
    return [{"kod": "hpolice_nevejde", "dily": sorted({i, j} | {a for a, b, _ in nalezeno[1:6]} | {b for a, b, _ in nalezeno[1:6]}),
             "text": f"Šikmá police mezi zadními stojkami by narazila na {S._jmeno(dily[j], j)} (průnik {dp:.1f} mm) – zvyšte polici, zmenšete sklon nebo hloubku, nebo ji vypněte."}]


# ---------------------------------------------------------------------------------------------------------------------
# popisy a hacky pro generator / GLB / vyrobni vypis
# ---------------------------------------------------------------------------------------------------------------------
MATERIAL_DILU = {"product_4933": "lamino", LAM12_PART: "lamino", "product_3939": "mdf", "product_3539": "preklizka", "product_3045": "seda", "product_3207": "seda"}      # material dilu v GLB (stul_glb.MATERIAL_DILU)


def tloustka_dilu(part_id):
    """Tloustka desky (mm) dilu katalogu; pracovni deska a ostatni (laminodeska 18 mm) = 18."""
    for v in DESKY.values():
        if v["part"] == part_id:
            return float(v["tl"])
    return 18.0


def popis_desky(deska_id):
    """Citelny nazev desky horni police podle `deska_id` (hpol<usek>d<k> deska, hpol<usek>p<j> prepazka, hpol<usek>l lem)."""
    import re
    m = re.match(r"hpol(\d+)([dpl])(\d*)$", deska_id)
    if not m:
        return "deska horní police"
    usek = f" – úsek {int(m.group(1)) + 1}" if int(m.group(1)) else ""
    if m.group(2) == "p":
        return f"přepážka horní police č. {int(m.group(3)) + 1}{usek}"
    if m.group(2) == "l":
        return "lem horní police" + (f" (kus {int(m.group(3)) + 1})" if m.group(3) not in ("", "0") else "") + usek
    return "deska horní police" + (f" (pole {int(m.group(3)) + 1})" if m.group(3) not in ("", "0") else "") + usek


def role(klic):
    """(kategorie, citelny popis) dilu horni police podle klice ("hpol", usek, role, ...); popis vzdy obsahuje 'horní police' (montazni krok 7)."""
    s_, r_ = klic[1], klic[2]
    usek = f" (úsek {s_ + 1})" if s_ else ""
    if r_ == "zad":
        return "pricka", "zadní příčka horní police" + usek
    if r_ == "pred":
        return "pricka", "přední příčka horní police" + usek
    if r_ == "bok":
        return "pricka", ("levý" if klic[3] == 0 else "pravý") + " boční profil horní police" + usek
    if r_ == "mezi":
        return "pricka", f"střední profil horní police č. {klic[3] + 1}" + usek
    if r_ == "deska":
        return "deska", "deska horní police" + usek
    if r_ == "prep":
        return "deska", f"přepážka horní police č. {klic[3] + 1}" + usek
    if r_ == "lem":
        return "deska", "lem horní police" + (f" (kus {klic[3] + 1})" if len(klic) > 3 and klic[3] else "") + usek
    if r_ == "uhel":
        return "prislusenstvi", "úhelník horní police" + usek
    if r_ == "konz":
        return "prislusenstvi", ("levá" if klic[3] == 0 else "pravá") + " naklápěcí konzola horní police" + usek
    return "dil", "díl horní police"


TYP_ID = {"flat": "rovna", "frame": "ram", "groove": "drazka", "lip": "lem", "dividers": "prepazky", "slope": "sikma"}       # verejna id slotu upshelftype <-> typ generatoru
TYP_VEREJNE = {v: k for k, v in TYP_ID.items()}
TYP_IDS = tuple(TYP_VEREJNE[t] for t in TYPY)                                                   # verejna id typu v poradi nabidky
DESKY_IDS = tuple(DESKY)                                                                         # verejna id desek (lam18 | lam12 | mdf8 | pr10)


def nastav_typ(p, typ):
    """Zmeny parametru pro prepnuti typu police na `typ` (3D menu, schema): typ + deska platna pro novy typ a system (zachova se, kdyz sedi; jinak vychozi laminodeska 18 mm)."""
    system = int(p["system"])
    nab = nabidka_desek(system, typ)
    deska = p["hpolice_deska"] if p["hpolice_deska"] in nab else (nab[0] if nab else DESKA_VYCHOZI)
    return {"hpolice_typ": typ, "hpolice_deska": deska}


# ---------------------------------------------------------------------------------------------------------------------
# 3D menu (pravym tlacitkem na police) a jeho preklady (verejna vrstva api/stul_ovladani_verejne.py)
# ---------------------------------------------------------------------------------------------------------------------
NAZVY_MENU = {"rovna": "rovná, deska na rámu", "ram": "rámová, bez desky", "drazka": "rám s deskou v drážce", "lem": "s lemem", "prepazky": "rám s přepážkami z překližky", "sikma": "šikmá na boxy"}
NAZVY_DESEK = {"lam18": "laminodeska 18 mm", "lam12": "laminodeska 12 mm", "mdf8": "MDF 8 mm", "pr10": "překližka 10 mm"}
KROK_MENU = 50.0
PREKLADY = [
    ("Police mezi stojkami", "Shelf between the uprights", "Polica medzi stojkami"),
    ("Odebrat polici mezi stojkami", "Remove the shelf between the uprights", "Odstrániť policu medzi stojkami"),
    ("Police: rovná, deska na rámu", "Shelf: flat, board on the frame", "Polica: rovná, doska na ráme"),
    ("Police: rámová, bez desky", "Shelf: frame only, no board", "Polica: rámová, bez dosky"),
    ("Police: rám s deskou v drážce", "Shelf: frame with a board in the slot", "Polica: rám s doskou v drážke"),
    ("Police: s lemem", "Shelf: with a front lip", "Polica: s lemom"),
    ("Police: rám s přepážkami z překližky", "Shelf: frame with plywood dividers", "Polica: rám s priehradkami z preglejky"),
    ("Police: šikmá na boxy", "Shelf: sloped, for boxes", "Polica: šikmá na boxy"),
    ("Deska police: laminodeska 18 mm", "Shelf board: laminated chipboard 18 mm", "Doska police: laminovaná drevotrieska 18 mm"),
    ("Deska police: laminodeska 12 mm", "Shelf board: laminated chipboard 12 mm", "Doska police: laminovaná drevotrieska 12 mm"),
    ("Deska police: MDF 8 mm", "Shelf board: MDF 8 mm", "Doska police: MDF 8 mm"),
    ("Deska police: překližka 10 mm", "Shelf board: plywood 10 mm", "Doska police: preglejka 10 mm"),
    ("Police o 50 mm výš", "Raise the shelf by 50 mm", "Polica o 50 mm vyššie"),
    ("Police o 50 mm níž", "Lower the shelf by 50 mm", "Polica o 50 mm nižšie"),
    ("Sem se nevejde (málo místa nad rámem).", "It does not fit here (not enough room above the frame).", "Sem sa nezmestí (málo miesta nad rámom)."),
    ("Sem se nevejde (stůl se střední zadní nohou).", "It does not fit here (table with a rear centre leg).", "Sem sa nezmestí (stôl so strednou zadnou nohou)."),
    ("Výš už police nejde.", "The shelf cannot go any higher.", "Vyššie už polica nejde."),
    ("Níž už police nejde.", "The shelf cannot go any lower.", "Nižšie už polica nejde."),
    ("Police hlouběji (+50 mm)", "Shelf deeper (+50 mm)", "Polica hlbšia (+50 mm)"),
    ("Police mělčí (−50 mm)", "Shelf shallower (−50 mm)", "Polica plytšia (−50 mm)"),
    ("Hlouběji už police nejde.", "The shelf cannot be any deeper.", "Hlbšie už polica nejde."),
    ("Mělčeji už police nejde.", "The shelf cannot be any shallower.", "Plytšie už polica nejde."),
    ("Sklon police o 5° větší", "Shelf slope 5° steeper", "Sklon police o 5° väčší"),
    ("Sklon police o 5° menší", "Shelf slope 5° shallower", "Sklon police o 5° menší"),
    ("Větší sklon už není možný.", "A steeper slope is not possible.", "Väčší sklon už nie je možný."),
    ("Menší sklon už není možný.", "A shallower slope is not possible.", "Menší sklon už nie je možný."),
]


def menu(r, pol):
    """Polozky 3D menu horni police (pravym tlacitkem): odebrat, jiny typ, jina deska, vyska a hloubka po 50 mm, u sikme i sklon po 5 st. `pol` = tovarna polozek z ovladani_3d."""
    p, hp = r["parametry"], r["hpolice_info"]
    system, typ = int(p["system"]), p["hpolice_typ"]
    out = [pol("Odebrat polici mezi stojkami", {"hpolice": False})]
    inf = {x["typ"]: x for x in hp.get("typy") or []}
    for t in TYPY:
        if t != typ:
            x = inf.get(t) or {}
            duvod = None if x.get("vejde", True) else ("Sem se nevejde (stůl se střední zadní nohou)." if x.get("duvod") == "sekce" else "Sem se nevejde (málo místa nad rámem).")
            out.append(pol(f"Police: {NAZVY_MENU[t]}", nastav_typ(p, t), duvod))
    for d in nabidka_desek(system, typ):
        if d != p["hpolice_deska"]:
            out.append(pol(f"Deska police: {NAZVY_DESEK[d]}", {"hpolice_deska": d}))
    v, h = hp["vyska"], hp["hloubka"]
    out.append(pol("Police o 50 mm výš", {"hpolice_vyska": round(min(v["max"], v["hodnota"] + KROK_MENU), 1)}, None if v["hodnota"] + 1e-6 < v["max"] else "Výš už police nejde."))
    out.append(pol("Police o 50 mm níž", {"hpolice_vyska": round(max(v["min"], v["hodnota"] - KROK_MENU), 1)}, None if v["hodnota"] - 1e-6 > v["min"] else "Níž už police nejde."))
    out.append(pol("Police hlouběji (+50 mm)", {"hpolice_hloubka": round(min(h["max"], h["hodnota"] + KROK_MENU), 1)}, None if h["hodnota"] + 1e-6 < h["max"] else "Hlouběji už police nejde."))
    out.append(pol("Police mělčí (−50 mm)", {"hpolice_hloubka": round(max(h["min"], h["hodnota"] - KROK_MENU), 1)}, None if h["hodnota"] - 1e-6 > h["min"] else "Mělčeji už police nejde."))
    if typ == "sikma" and hp.get("sklon"):
        sk = hp["sklon"]
        out.append(pol("Sklon police o 5° větší", {"hpolice_sklon": round(min(sk["max"], sk["hodnota"] + SKLON_KROK), 1)}, None if sk["hodnota"] + 1e-6 < sk["max"] else "Větší sklon už není možný."))
        out.append(pol("Sklon police o 5° menší", {"hpolice_sklon": round(max(sk["min"], sk["hodnota"] - SKLON_KROK), 1)}, None if sk["hodnota"] - 1e-6 > sk["min"] else "Menší sklon už není možný."))
    return out
