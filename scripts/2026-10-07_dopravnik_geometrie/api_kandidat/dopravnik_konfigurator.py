# -*- coding: utf-8 -*-
"""Konfigurator valeckoveho dopravniku: CISTA pravidla sestavy (bot8 = geometr, 2026-10-07; zaklad a prvni verzi pravidel napsal John 2026-10-07, prevzato beze zmeny chovani).

Zadna DB, sit, zapis ani prihlaseni. Vstup = vyber zakaznika (`rtype`, `width`, `len`, `pitch`, `h`, `legs`, `frame`, ...), vystup = EFEKTIVNI vyber po normalizaci, kusovnik (cenove radky),
POLOHY jednotlivych dilu (instance CAD dilu ve svete, mm) a rozmery sestavy. Geometrii dilu (obalky, pivoty, posuvna telesa nohy) dodava `dopravnik_data/geometrie.json`
(zmereno z oficialnich STEP dodavatele), ceny a kurz dodava volajici (shop bere USD a kurz z karet dilu v DB; snimek pro testy je `dopravnik_data/cenik_snapshot.json`).

Dve rozhrani nad stejnym vypoctem:
  * `sestav_dopravnik(**p)`  - kontrakt pro `api/dopravnik_shop.py` (bot5): {"parametry": efektivni vyber, "dily": [{sku, nazev, mnozstvi, jednotka "ks"|"m", kusy?, delka_mm?}], "upozorneni": [{id, slot, hodnota}], ...}
    + navic "polohy_dilu", "valid_geometry", "geometry_errors", "issues", "manufacturing_ready", "dimensions", "geometry" (pro `dopravnik_glb` a nabidku). Geometrie se nacte ze souboru (cache).
  * `resolve(selection, cenik, geometrie)` - plny vysledek vcetne ceny (stejny vstup a vystup jako preview `generator.js`; slouzi testum shody JS / Python a bezne jen jako referencni vypocet).

Osy: X = delka dopravniku (stred v 0), Y = vyska (podlaha 0), Z = sirka (stred v 0). Jednotky mm; quaternion [x, y, z, w].
`manufacturing_ready` je VZDY False, dokud nejsou potvrzena konstrukcni rozhodnuti z `issues` (patka, spoj spodniho ramu, ulozeni os valecku, zajisteni teleskopu); `valid` je jen kontrola rozmeru, ne schvaleni vyroby.
"""
import json
import math
import os

VERZE_PRAVIDEL = "dopravnik-john-2026-10-07.1"

VYCHOZI = {"rtype": "alu", "width": 590, "len": 2000, "pitch": 150, "h": 800, "legs": "auto", "frame": "full", "guide": "none", "guidetype": "40"}
SIRKY_PODLE_TYPU = {"alu": (290, 440, 590, 790), "knurl": (290, 440, 590, 790), "steel": (290, 440, 590, 790, 990)}
TYPY = tuple(SIRKY_PODLE_TYPU)
RAMY = ("full", "cross", "none")
ROZSAH = {"len": (1000, 6000, 100), "pitch": (75, 300, 25), "h": (570, 870, 10)}          # (min, max, krok) mm
PREFIX_VALECKU = {"alu": "3.009.01.50.", "knurl": "3.009.03.50.", "steel": "3.009.02.51."}
PROFIL_BOCNICE = {"alu": "1.2.00.023075.00", "knurl": "1.2.00.023075.00", "steel": "1.2.00.023127.00"}
NOHA = {"alu": "3.004.03.01", "knurl": "3.004.03.01", "steel": "3.004.02.01"}
PATKA = "2.3.002.1050"
PROFIL_RAMU = "1.1.10.040040.02"
UCHYT_RAMU = "3.006.240.021.180"
NAZEV_VALECKU = {"alu": "Hliníkový váleček Ø50×%d mm", "knurl": "Vroubkovaný hliníkový váleček Ø50×%d mm", "steel": "Ocelový váleček Ø51×%d mm"}

_ID = [0, 0, 0, 1]
_OTOCENI_180 = [0, 1, 0, 0]                                  # rotace o 180 st. kolem Y (leva strana)
_OTOCENI_90 = [0, math.sqrt(.5), 0, math.sqrt(.5)]           # rotace o 90 st. kolem Y (pricky)

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dopravnik_data")
_CACHE = {}


class DopravnikChyba(ValueError):
    """Chybi cena / CAD dilu nebo je vstup nepouzitelny; shop to hlasi jako 'cena neni k dispozici', nikdy ne jako cenu 0."""


def nacti_geometrii():
    """Geometrie dilu (obalky, pivoty, posuvna telesa) z `dopravnik_data/geometrie.json`; nemenne, cachuje se."""
    if "geometrie" not in _CACHE:
        with open(os.path.join(_DATA, "geometrie.json"), encoding="utf-8") as f:
            _CACHE["geometrie"] = json.load(f)
    return _CACHE["geometrie"]


def nacti_cenik_snapshot():
    """Snimek cen pro testy a preview (USD, kurz, karta) - provoz bere ceny z karet dilu v DB (dopravnik_shop)."""
    if "cenik" not in _CACHE:
        with open(os.path.join(_DATA, "cenik_snapshot.json"), encoding="utf-8") as f:
            _CACHE["cenik"] = json.load(f)
    return _CACHE["cenik"]


def _cele(value, fallback):
    """Cele cislo z libovolneho vstupu; nesmysl (bool, seznam, None, NaN, text) = fallback."""
    if isinstance(value, (bool, list, dict)) or value is None:
        return fallback
    try:
        value = float(value)
    except (ValueError, TypeError):
        return fallback
    return round(value) if math.isfinite(value) else fallback


def _otoc(v, q):
    """Vektor v otoceny quaternionem q [x, y, z, w]."""
    x, y, z = v
    qx, qy, qz, qw = q
    tx = 2 * (qy * z - qz * y)
    ty = 2 * (qz * x - qx * z)
    tz = 2 * (qx * y - qy * x)
    return [x + qw * tx + qy * tz - qz * ty, y + qw * ty + qz * tx - qx * tz, z + qw * tz + qx * ty - qy * tx]


def obalka_sestavy(parts, geometrie):
    """Obalka (min, max) vsech umistenych dilu ve svete, vcetne posunu teleskopu a vysunuti cepu; dily bez polohy (poloha_mm None) se nepocitaji."""
    mn = [math.inf] * 3
    mx = [-math.inf] * 3
    for p in parts:
        if p["poloha_mm"] is None:
            continue
        g = geometrie[p["sku"]]
        for m in g["meshes"]:
            posun = p.get("posun_teleskopu_mm", 0) if m["teleso"] in g.get("posuvna_telesa", []) else 0
            cep = p.get("vysunuti_cepu_mm", 0) if m["teleso"] in p.get("vysunuta_telesa", []) else 0
            for x in (m["bbox_mm"][0][0], m["bbox_mm"][1][0]):
                for y in (m["bbox_mm"][0][1], m["bbox_mm"][1][1]):
                    for z in (m["bbox_mm"][0][2], m["bbox_mm"][1][2]):
                        a = _otoc([x * p["scale"][0], y * p["scale"][1] + posun, z * p["scale"][2] + cep], p["quaternion"])
                        for i in range(3):
                            mn[i] = min(mn[i], a[i] + p["poloha_mm"][i])
                            mx[i] = max(mx[i], a[i] + p["poloha_mm"][i])
    return [mn, mx]


def normalizuj(selection):
    """(efektivni parametry, vyber s 'auto' u poctu noh, upozorneni). Upozorneni: [{"id", "slot", "kod", "hodnota", "message"}] - id a hodnota pro shop (sablony cs / en / sk), slot / kod / message jako v preview."""
    s = selection if isinstance(selection, dict) else {}
    p = dict(VYCHOZI)
    upoz = []
    if isinstance(s.get("rtype"), str) and s["rtype"] in SIRKY_PODLE_TYPU:
        p["rtype"] = s["rtype"]
    if s.get("frame") in RAMY:
        p["frame"] = s["frame"]
    for klic, mn, mx, krok in (("len", 1000, 6000, 100), ("pitch", 75, 300, 25), ("h", 570, 870, 10)):
        n = _cele(s.get(klic), VYCHOZI[klic])
        p[klic] = int(mn + round((min(mx, max(mn, n)) - mn) / krok) * krok)
        if p[klic] != n:
            upoz.append({"id": {"len": "len_upravena", "pitch": "pitch_upraven", "h": "h_upravena"}[klic], "slot": klic, "kod": "upraveno", "hodnota": p[klic], "message": "Hodnota byla upravena na %d mm." % p[klic]})
    w = _cele(s.get("width"), VYCHOZI["width"])
    p["width"] = min(SIRKY_PODLE_TYPU[p["rtype"]], key=lambda x: (abs(x - w), x))
    if w != p["width"]:
        upoz.append({"id": "sirka_upravena", "slot": "width", "kod": "upraveno", "hodnota": p["width"], "message": "Pro tento typ je dostupná šířka %d mm." % p["width"]})
    chce = "auto" if s.get("legs", "auto") == "auto" else _cele(s.get("legs"), 0)
    if chce not in ("auto", 4, 6, 8):
        chce = "auto"
    minimum = 4 if p["len"] <= 3000 else 6
    p["legs"] = minimum if chce == "auto" else max(minimum, chce)
    if chce != "auto" and p["legs"] != chce:
        upoz.append({"id": "nohy_zvyseny", "slot": "legs", "kod": "upraveno", "hodnota": p["legs"], "message": "Dopravník delší než 3 m potřebuje nejméně 6 noh."})
    vybrano = {**p, "legs": "auto" if chce == "auto" else p["legs"]}
    return p, vybrano, upoz


def _cena(bom, cenik):
    """Cena podle receptu: ceil(soucet(USD x mnozstvi, po radcich) x 1,10 x kurz x 1,20); kurz = nejvyssi z pouzitych dilu. Bez ceny (nebo bez kurzu) dilu vyhodi DopravnikChyba."""
    for r in bom:
        c = cenik.get(r["sku"])
        if not c or not isinstance(c.get("usd"), (int, float)) or not math.isfinite(c["usd"]) or c["usd"] <= 0:
            raise DopravnikChyba("Chybí cena dílu " + r["sku"])
    usd = round(sum(round(cenik[r["sku"]]["usd"] * round(r["mnozstvi"], 3), 2) for r in bom), 2)
    kurz = max(cenik[r["sku"]]["kurz"] for r in bom)
    net = math.ceil(usd * 1.1 * kurz * 1.2 - 1e-9)
    return {"net": net, "gross": round(net * 1.21), "vat_rate": 21, "currency": "CZK", "kurz": kurz}


def _vypocti(selection, geometrie, cenik=None):
    """Spolecne jadro: normalizace, kusovnik, polohy dilu, kontroly, rozmery. S `cenik` navic cena (a kontrola, ze maji ceny vsechny dily)."""
    p, vybrano, upoz = normalizuj(selection)
    dvojic = p["legs"] // 2
    n = p["len"] // p["pitch"]
    valecek = PREFIX_VALECKU[p["rtype"]] + str(p["width"])
    bocnice = PROFIL_BOCNICE[p["rtype"]]
    noha = NOHA[p["rtype"]]
    bom = []

    def radek(sku, nazev, mnozstvi, jednotka, **navic):
        bom.append(dict(sku=sku, nazev=nazev, mnozstvi=mnozstvi, jednotka=jednotka, **navic))

    radek(valecek, (cenik[valecek]["nazev"] if cenik is not None and valecek in cenik else NAZEV_VALECKU[p["rtype"]] % p["width"]), n, "ks")
    radek(bocnice, "Boční profil " + ("23 × 127" if p["rtype"] == "steel" else "23 × 75"), 2 * p["len"] / 1000, "m", kusy=2, delka_mm=p["len"])
    radek(noha, "Teleskopická noha s montážní deskou", p["legs"], "ks")
    radek(PATKA, "Vyrovnávací patka M10", p["legs"], "ks")
    if p["frame"] != "none":
        radek(PROFIL_RAMU, "Profil 40 × 40 – příčky", dvojic * p["width"] / 1000, "m", kusy=dvojic, delka_mm=p["width"])
        if p["frame"] == "full":
            radek(PROFIL_RAMU, "Profil 40 × 40 – podélník", (p["len"] - 200) / 1000, "m", kusy=1, delka_mm=p["len"] - 200)
        radek(UCHYT_RAMU, "Spodní úchyt rámu", 4 * dvojic, "ks")
    cena = _cena(bom, cenik) if cenik is not None else None
    parts = []
    errors = []
    issues = [{"kod": "ulozeni_osy", "text": "Uložení os válečků a vrtání bočnic vyžaduje potvrzení. Náhled osy opírá o horní hranu profilu."},
              {"kod": "patka_material", "text": "Cenový recept obsahuje plastovou patku s kovovým šroubem. Kovovou patku je potřeba vybrat a přecenit."},
              {"kod": "zajištění_nohy", "text": "Zajišťovací čepy jsou vysunuté vedle noh. Otvory po 50 mm neodpovídají výškám po 10 mm; způsob zajištění je potřeba potvrdit."},
              {"kod": "zavit_patky", "text": "Záslepka nohy má v původním CAD předvrtání Ø8,5 mm. Náhled zobrazuje jmenovitý obrys závitu M10; provedení závitu je potřeba potvrdit."}]

    def pridej(nazev, sku, poloha, q=_ID, scale=(1, 1, 1), **navic):
        if sku not in geometrie:
            raise DopravnikChyba("Chybí CAD dílu " + sku)
        parts.append(dict(id=nazev, sku=sku, nazev_uzlu=nazev, poloha_mm=list(poloha), quaternion=list(q), scale=list(scale), **navic))

    ocel = p["rtype"] == "steel"
    mezera = p["width"] + (10 if ocel else 30)                 # vnitrni mezera bocnic G = W + 30 (hlinik) / W + 10 (ocel)
    prumer = 51 if ocel else 50
    polomer_bocnice = 10 if ocel else 6                        # vyska osy nad horni hranou bocnice
    osa_y = p["h"] - prumer / 2
    horni_hrana = osa_y - polomer_bocnice
    zakladni_horni_noha = horni_hrana - (4.5 if ocel else 1)
    vnejsi = mezera / 2 + 23
    lg = geometrie[noha]
    vyska_bocnice = -min(m["bbox_mm"][0][1] for m in geometrie[bocnice]["meshes"])
    pevne_prvky = [m for m in lg["meshes"] if m["bbox_mm"][0][2] < 0 and m["teleso"] not in lg["posuvna_telesa"]]
    horni_noha = min(zakladni_horni_noha, horni_hrana - vyska_bocnice - max(m["bbox_mm"][1][1] for m in pevne_prvky))
    for i in range(n):
        pridej("roll_%03d" % (i + 1), valecek, [-(n - 1) * p["pitch"] / 2 + i * p["pitch"], osa_y, 0])
    delka_vzoru = geometrie[bocnice]["delka_vzoru_mm"]
    pridej("rail_left", bocnice, [0, horni_hrana, -mezera / 2 - 11.5], _OTOCENI_180, [p["len"] / delka_vzoru, 1, 1])
    pridej("rail_right", bocnice, [0, horni_hrana, mezera / 2 + 11.5], _ID, [p["len"] / delka_vzoru, 1, 1])
    vicko = next(m for m in lg["meshes"] if m["teleso"] == lg["posuvna_telesa"][1])
    rameno = 52                                                  # horni plocha pojistne matice patky nad podlahou
    posun = rameno - horni_noha - vicko["bbox_mm"][0][1]
    cepy = [5, 6, 10, 11] if ocel else [3, 4, 8, 9]
    cep_min = min(m["bbox_mm"][0][2] for m in lg["meshes"] if m["teleso"] in cepy)
    pevne_max = max(m["bbox_mm"][1][2] for m in lg["meshes"] if m["teleso"] not in cepy)
    vysunuti = pevne_max - cep_min + 1.5
    spodek_pevne = horni_noha + min(m["bbox_mm"][0][1] for m in lg["meshes"] if m["teleso"] not in lg["posuvna_telesa"])
    if spodek_pevne < rameno - 1e-4:
        errors.append({"kod": "vyska_nohy", "text": "Při této výšce je pevná část nohy níže než matice patky. Sestavení vyžaduje ověření."})
    xs = []
    for i in range(dvojic):
        x = -(p["len"] - 200) / 2 + i * (p["len"] - 200) / (dvojic - 1)
        xs.append(x)
        for strana in (-1, 1):
            pripona = "%02d_" % (i + 1) + ("L" if strana < 0 else "R")
            pridej("leg_" + pripona, noha, [x, horni_noha, strana * vnejsi], _OTOCENI_180 if strana < 0 else _ID, posun_teleskopu_mm=posun, vysunuta_telesa=list(cepy), vysunuti_cepu_mm=vysunuti)
            pridej("foot_" + pripona, PATKA, [x, 0, strana * (vnejsi + 20.75)])
    if p["frame"] != "none":
        issues.append({"kod": "ram_spoj", "text": "Spodní úchyt má kruhové sedlo Ø48,3 mm; profil 40 × 40 do něj nevejde. Příčky z receptu navíc nedosáhnou k nohám. Rám je zobrazen oranžově jako návrh."})
        for i, x in enumerate(xs):
            pridej("frame_cross_" + str(i + 1), PROFIL_RAMU, [x, rameno + 50, 0], _OTOCENI_90, [p["width"] / geometrie[PROFIL_RAMU]["delka_vzoru_mm"], 1, 1], navrh=True)
        if p["frame"] == "full":
            pridej("frame_long", PROFIL_RAMU, [0, rameno + 50 + 40, 0], _ID, [(p["len"] - 200) / geometrie[PROFIL_RAMU]["delka_vzoru_mm"], 1, 1], navrh=True)
        for i in range(4 * dvojic):
            parts.append(dict(id="frame_mount_" + str(i + 1), sku=UCHYT_RAMU, nazev_uzlu=None, poloha_mm=None, quaternion=None, scale=None, stav="neumisteno_nekompatibilni"))
    if ocel:
        issues.append({"kod": "noha_vykres", "text": "Rozsah ocelové nohy se v katalogové tabulce a výkresu liší. Nosnost ani použitelný rozsah tímto náhledem nepotvrzujeme."})
    if zakladni_horni_noha - horni_noha > .001:
        issues.append({"kod": "deska_posun", "text": "Ocelová noha je svisle posunutá o %.3f mm, aby přítlačný díl nezasahoval do bočnice. Polohu upevňovacích šroubů je potřeba potvrdit." % (zakladni_horni_noha - horni_noha)})
    vysledek = {
        "rules_version": VERZE_PRAVIDEL, "selection": vybrano, "parametry": p, "dily": parts, "bom": bom, "notices": upoz, "errors": errors, "issues": issues, "valid": not errors, "manufacturing_ready": False,
        "dimensions": {"length_mm": p["len"], "width_mm": mezera + 46, "height_mm": p["h"], "assembly_bbox_mm": obalka_sestavy(parts, geometrie), "nominal_roller_mm": p["width"], "inner_gap_mm": mezera},
        "geometry": {"roller_count": n, "edge_mm": (p["len"] - (n - 1) * p["pitch"]) / 2, "roller_clearance_mm": p["pitch"] - prumer, "rail_top_mm": horni_hrana, "leg_top_mm": horni_noha,
                     "mount_adjustment_mm": zakladni_horni_noha - horni_noha, "telescopic_shift_mm": posun, "leg_pairs_x_mm": xs}}
    if cena is not None:
        vysledek["price"] = cena
    return vysledek


def resolve(selection, cenik, geometrie):
    """Plny vysledek vcetne ceny (referencni vypocet, shodny s preview `generator.js`). Vyhodi DopravnikChyba, kdyz chybi cena nebo CAD dilu."""
    r = _vypocti(selection, geometrie, cenik)
    # poradi klicu jako v preview (JSON se porovnava jako objekt, poradi nehraje roli; price navic za bom)
    return {"rules_version": r["rules_version"], "selection": r["selection"], "parametry": r["parametry"], "dily": r["dily"], "bom": r["bom"], "price": r["price"], "notices": [{"slot": u["slot"], "kod": u["kod"], "message": u["message"]} for u in r["notices"]],
            "errors": r["errors"], "issues": r["issues"], "valid": r["valid"], "manufacturing_ready": r["manufacturing_ready"], "dimensions": r["dimensions"], "geometry": r["geometry"]}


def sestav_dopravnik(**selection):
    """Kontrakt pro dopravnik_shop (bot5): vyber -> {"parametry", "dily" (kusovnik), "upozorneni", + polohy_dilu, valid_geometry, geometry_errors, issues, manufacturing_ready, dimensions, geometry}.
    Cena se zde NEPOCITA (bere ji shop z karet dilu v DB); chybi-li CAD dilu, vyhodi DopravnikChyba."""
    r = _vypocti(selection, nacti_geometrii(), None)
    return {"parametry": r["parametry"], "dily": r["bom"], "upozorneni": [{k: u[k] for k in ("id", "slot", "hodnota")} for u in r["notices"]], "polohy_dilu": r["dily"],
            "valid_geometry": r["valid"], "geometry_errors": r["errors"], "issues": r["issues"], "manufacturing_ready": False, "dimensions": r["dimensions"], "geometry": r["geometry"],
            "rules_version": r["rules_version"]}
