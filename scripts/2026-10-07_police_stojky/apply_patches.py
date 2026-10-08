#!/usr/bin/env python3
"""KOTVENE zaplaty pro horni police mezi zadnimi stojkami (bot8, 2026-10-07): z ZIVYCH souboru v <src_api> udela upravene soubory v <dst_api> (a nainstaluje novy modul stul_hpolice.py).
Kazda nahrada je kotvena: puvodni text se musi v souboru vyskytovat PRAVE JEDNOU (assert), jinak se nic nezapise (soubor se zmenil pod zaplatou -> rucne resit).

  apply_patches.py <src_api> <dst_api> [--lam12-id N]      src = dst  => nasazeni primo do zivych souboru (apply.sh, uvnitr zamku);  jinak kandidat pro testy
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def nahrad(s, a, b, label):
    n = s.count(a)
    assert n == 1, f"kotva '{label}': {n} vyskytu (ocekavan 1)"
    return s.replace(a, b)


def vloz_pred_radek(s, prefix, text, label):
    """Vlozi `text` PRED jediny radek, ktery zacina `prefix` (cely radek se zachova)."""
    m = list(re.finditer(r"^" + re.escape(prefix) + r".*$", s, re.M))
    assert len(m) == 1, f"kotva '{label}': {len(m)} radku s prefixem (ocekavan 1)"
    i = m[0].start()
    return s[:i] + text + s[i:]


# ---------------------------------------------------------------------------------------------------------------------
# stul_konfigurator.py
# ---------------------------------------------------------------------------------------------------------------------
def patch_konfigurator(s):
    s = nahrad(s, '''def _bbox_ze_souboru(part_id):
    path = os.path.join(KATALOG_DIR, part_id + ".glb")
''', '''# GLB dilu, jejichz soubor se nejmenuje `<part_id>.glb` (karta ma jiny `glb_file`): horni police pouziva desky MDF 8 mm (#3939), PR10 (#3539) a Uhelnikovou spojku 30x30 (#3045)
GLB_SOUBORY = {"product_3939": "deska_mdf_seda_8.glb", "product_3539": "pr10.glb", "product_3045": "product_2895.glb"}


def glb_cesta(part_id):
    """Cesta k souboru GLB dilu v katalogu (vetsinou `<part_id>.glb`, vyjimky viz GLB_SOUBORY)."""
    return os.path.join(KATALOG_DIR, GLB_SOUBORY.get(part_id, part_id + ".glb"))


def _bbox_ze_souboru(part_id):
    path = glb_cesta(part_id)
''', "glb_cesta")

    s = nahrad(s, '''def _sse():
    """Modul SSE stolu (system 41); import az pri pouziti (stul_sse importuje tenhle modul)."""
    import stul_sse
    return stul_sse
''', '''def _sse():
    """Modul SSE stolu (system 41); import az pri pouziti (stul_sse importuje tenhle modul)."""
    import stul_sse
    return stul_sse


def _hpol():
    """Modul horni police mezi zadnimi stojkami (api/stul_hpolice.py); import az pri pouziti (modul importuje tenhle)."""
    import stul_hpolice
    return stul_hpolice
''', "_hpol")

    s = nahrad(s, '''    "vzpera_delka": 300,
    **_vyrezy_vychozi(),''', '''    "vzpera_delka": 300,
    # HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): vychozi = BEZ police (hashe, kody a ceny stavajicich stolu beze zmeny)
    "hpolice": False, "hpolice_typ": "rovna", "hpolice_deska": "lam18", "hpolice_vyska": None, "hpolice_hloubka": 300.0,
    **_vyrezy_vychozi(),''', "VYCHOZI")

    s = nahrad(s, 'PREPINACE = ("stojky", "kolecka", "panely", "led", "suplik", "elektrozlab", "drzak_pet", "patky", "navlek")',
               'PREPINACE = ("stojky", "kolecka", "panely", "led", "suplik", "elektrozlab", "drzak_pet", "patky", "navlek", "hpolice")', "PREPINACE")

    s = nahrad(s, '''    if sys_ == SYSTEM_SSE:
        out = _sse().over_parametry(out, p)                          # SSE: zuzene rozsahy, nepodporovane volby vypnute (explicitni zapnuti = StulChyba)
    return out
''', '''    if sys_ == SYSTEM_SSE:
        out = _sse().over_parametry(out, p)                          # SSE: zuzene rozsahy, nepodporovane volby vypnute (explicitni zapnuti = StulChyba)
    else:
        out = _hpol().over_parametry(out, sys_)                      # horni police mezi zadnimi stojkami (Robert 2026-10-07): typ, deska, vyska, hloubka; vypnuta = kanonicka podoba
    return out
''', "_norm_parametry")

    # --- pomocna funkce otoceni spojky kolem uzlu
    s = nahrad(s, 'def _kvat_nasob(a, b):', '''def _otoc_spojku(odsazeni, q, osa, stupne):
    """Otoci spojku (jeji odsazeni od uzlu a kvaternion) o `stupne` (nasobek 90) kolem osy 'x' | 'y' | 'z' prochazejici uzlem: tentyz spoj ve ctyrech rozich (horni police)."""
    t = math.radians(stupne)
    c, sn = round(math.cos(t), 12), round(math.sin(t), 12)
    R = {"x": [[1, 0, 0], [0, c, -sn], [0, sn, c]], "y": [[c, 0, sn], [0, 1, 0], [-sn, 0, c]], "z": [[c, -sn, 0], [sn, c, 0], [0, 0, 1]]}[osa]
    qr = tuple(math.sin(t / 2.0) if i == "xyz".index(osa) else 0.0 for i in range(3)) + (math.cos(t / 2.0),)
    return np.round(np.array(R, float) @ np.asarray(odsazeni, float), 9), _kvat_nasob(qr, q)


def _kvat_nasob(a, b):''', "_otoc_spojku")

    s = nahrad(s, '''        pos_spojky = u1 + odsazeni
        if _zanori_do_desky(clenove, cc["part_id"], q, cc["scale"], pos_spojky):
            continue
        att = None
        if not rot and "ry90" not in priznaky:''', '''        rotace = spec[3] if len(spec) > 3 else ()              # (osa, stupne) ...: dalsi otoceni kolem uzlu (horni police: stejny spoj v jinem rohu)
        for osa_r, st_r in rotace:
            odsazeni, q = _otoc_spojku(odsazeni, q, osa_r, st_r)
        pos_spojky = u1 + odsazeni
        if _zanori_do_desky(clenove, cc["part_id"], q, cc["scale"], pos_spojky):
            continue
        att = None
        if not rot and "ry90" not in priznaky and not rotace:''', "odvozene_spojky rotace")

    # --- stavba police (pred konci noh)
    s = vloz_pred_radek(s, "    # 2b-) konce noh bez kole", '''    # ----- 2b++) HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): ram z profilu mezi stojkami, deska / prepazky s uhelniky; vypnuta = beze zmeny -----
    hpolice_info = None
    hpolice_spojky = []                                          # spojky police se pridaji AZ NA KONEC odvozenych spojek: cislovani ostatnich se police nemeni
    if p["hpolice"] and p["stojky"]:
        hpolice_info = _hpol().postav({"p": p, "sab": sab, "clenove": clenove, "odvozene": hpolice_spojky, "zl": zl, "zr": zr, "zm": zm, "rezim": rezim, "xr": xr, "xf": xf,
                                       "y_deska": horni_pred + DESKA_TLOUSTKA, "y_vrch": horni_pred + (nast if ext else 0.0)})

''', "stavba police")

    s = nahrad(s, '''    for k, c in clenove.items():
        if c["druh"] != "deska":
            continue
        lo, hi = _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
        strana = 0 if (zm is None''', '''    for k, c in clenove.items():
        if c["druh"] != "deska" or c.get("deska_id"):          # deska horni police ma deska_id uz od vzniku (api/stul_hpolice.py)
            continue
        lo, hi = _aabb({"part_id": c["part_id"], "quaternion": c["quaternion"], "scale": c["scale"], "position": c["pos"]})
        strana = 0 if (zm is None''', "_oznac_desky")

    s = nahrad(s, '''        src = c["src"]
        if _je_vz(klic):
''', '''        src = c["src"]
        if c.get("konce") is not None:
            konce_ocek[klic] = tuple(c["konce"])                           # horni police: konce podle role profilu (api/stul_hpolice.py)
        elif _je_vz(klic):
''', "konce_ocek")

    s = nahrad(s, '''    for n, spec in enumerate(odvozene_spojky):
        c_src, mapa = spec[0], spec[1]
''', '''    odvozene_spojky += hpolice_spojky                          # spojky horni police az na konec: cislovani ostatnich odvozenych spojek se police nemeni
    for n, spec in enumerate(odvozene_spojky):
        c_src, mapa = spec[0], spec[1]
''', "odvozene spojky police na konec")

    s = nahrad(s, '''        "panely_info": panely_info,
''', '''        "panely_info": panely_info,
        "hpolice_info": hpolice_info,
''', "hpolice_info ve vysledku")

    s = vloz_pred_radek(s, '    if panely_info.get("elzlab_bez_opory") and ("t", ELZLAB) in clenove:', '''    if hpolice_info and hpolice_info.get("problem") == "misto":
        problemy.append({"kod": "hpolice_nevejde", "dily": [],
                         "text": "Police mezi zadními stojkami se sem nevejde – mezi panely (nebo deskou) a ramenem LED není dost místa (zvyšte zadní stojky, snižte počet panelů, nebo ji vypněte)."})
    elif hpolice_info and hpolice_info.get("problem") == "sirka":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Police mezi zadními stojkami se sem nevejde – mezi zadní stojky potřebuje stůl širší."})
    elif hpolice_info and hpolice_info.get("problem") == "hloubka":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Police mezi zadními stojkami se sem nevejde – stůl je málo hluboký pro tento typ police (vyberte jiný typ, nebo ji vypněte)."})
''', "problem hpolice_nevejde")

    s = nahrad(s, '''    if not p["stojky"] and (p["panely"] or p["led"] or p["elektrozlab"]):
        problemy.append({"kod": "stojky_potreba", "dily": [],
                         "text": "Perforované panely, LED osvětlení a elektrožlab se montují na zadní stojky – bez nich je nelze zapnout."})
''', '''    if not p["stojky"] and (p["panely"] or p["led"] or p["elektrozlab"]):
        problemy.append({"kod": "stojky_potreba", "dily": [],
                         "text": "Perforované panely, LED osvětlení a elektrožlab se montují na zadní stojky – bez nich je nelze zapnout."})
    elif not p["stojky"] and p["hpolice"]:
        problemy.append({"kod": "stojky_potreba", "dily": [], "text": "Police mezi zadními stojkami se montuje na zadní stojky – bez nich ji nelze zapnout."})
''', "stojky_potreba police")

    # --- automaticke odebirani
    s = nahrad(s, '''        if kod == "stojky_potreba":
            for k in ("panely", "led", "elektrozlab"):''', '''        if kod == "hpolice_nevejde":
            if p["hpolice"]:
                kandidati.setdefault("hpolice", pr["text"])
            continue
        if kod == "stojky_potreba":
            for k in ("panely", "led", "elektrozlab", "hpolice"):''', "co_odebrat stojky")
    s = nahrad(s, '''            if isinstance(kl_i, list) and kl_i and kl_i[0] == "panrail":
                tg = "panely"                                   # profily nad/pod panelem stoji a padaji s panely
''', '''            if isinstance(kl_i, list) and kl_i and kl_i[0] == "panrail":
                tg = "panely"                                   # profily nad/pod panelem stoji a padaji s panely
            if isinstance(kl_i, (list, tuple)) and kl_i and kl_i[0] == "hpol":
                tg = "hpolice"                                  # vsechny dily horni police stoji a padaji s ni
''', "co_odebrat klic hpol")
    s = nahrad(s, 'PORADI_ODEBRANI = ("vzpery", "drzak_pet", "elektrozlab", "suplik", "led", "panely", "patky", "kolecka", "navlek")',
               'PORADI_ODEBRANI = ("vzpery", "hpolice", "drzak_pet", "elektrozlab", "suplik", "led", "panely", "patky", "kolecka", "navlek")', "PORADI_ODEBRANI")
    s = nahrad(s, '''"drzak_pet": "Držák PET lahve", "kolecka": "Kolečka", "vzpery": "Šikmé vzpěry ramen LED", "navlek": "Návlek nohou"}''',
               '''"drzak_pet": "Držák PET lahve", "kolecka": "Kolečka", "vzpery": "Šikmé vzpěry ramen LED", "navlek": "Návlek nohou", "hpolice": "Police mezi zadními stojkami"}''', "NAZVY_PREPINACU")

    s = nahrad(s, '''    if (p["suplik_posun"] == 0 and p["stredni_noha"] is None and not p["suplik_vlevo"] and p["pet_posun"] == 0 and p["pet_noha"] == "PL" and p["pet_strana"] == "vpravo"
            and p["panely_posun"] == 0 and p["panely_z"] == 0 and p["elzlab_y"] == 0 and p["elzlab_z"] == 0):''',
               '''    if (p["suplik_posun"] == 0 and p["stredni_noha"] is None and not p["suplik_vlevo"] and p["pet_posun"] == 0 and p["pet_noha"] == "PL" and p["pet_strana"] == "vpravo"
            and p["panely_posun"] == 0 and p["panely_z"] == 0 and p["elzlab_y"] == 0 and p["elzlab_z"] == 0 and p["hpolice_vyska"] is None):''', "kolizi posun podm.")
    s = nahrad(s, '''    ref["suplik_posun"] = 0.0
    ref["suplik_vlevo"] = False''', '''    ref["suplik_posun"] = 0.0
    ref["hpolice_vyska"] = None                                         # vysku horni police si zvolil zakaznik: kolize se NABIDNE odebrat, police se sama neodebere
    ref["suplik_vlevo"] = False''', "kolizi posun ref")

    # --- query string
    s = nahrad(s, ') + VYREZY_CISLA\n', ', "hpolice_hloubka") + VYREZY_CISLA\n', "_CISLA")                                      # (kotva nezavisla na tom, co je v n-tici pred ni: vetve LED delky, spodni police...)
    s = nahrad(s, '_DESETINNA = ("suplik_posun", "stredni_noha", "pet_posun", "panely_posun", "panely_z", "elzlab_y", "elzlab_z")',
               '_DESETINNA = ("suplik_posun", "stredni_noha", "pet_posun", "panely_posun", "panely_z", "elzlab_y", "elzlab_z", "hpolice_vyska")', "_DESETINNA")
    s = nahrad(s, 'if (k == "stredni_noha" or k.startswith("police_h")) and str(v)', 'if (k == "stredni_noha" or k.startswith("police_h") or k == "hpolice_vyska") and str(v)', "query None")
    s = nahrad(s, '        elif k in ("pet_noha", "pet_strana", "stredni_opora"):', '        elif k in ("pet_noha", "pet_strana", "stredni_opora", "hpolice_typ", "hpolice_deska"):', "query str")

    # --- nabidka roztazeni: horni police, ktera se nevejde, se zachrani vyssimi zadnimi stojkami (stejne jako panely)
    s = nahrad(s, '        if not nab and k == "panely":                                              # panel se nevejde na nizke zadni stojky: nabidka je zvysit stojky',
               '        if not nab and k in ("panely", "hpolice"):                                 # panel / horni police se nevejde na nizke zadni stojky: nabidka je zvysit stojky', "nabidky_roztazeni stojky")

    # --- cena, kusovnik, nazvy
    s = nahrad(s, '        elif d["part_id"] == "product_4933":\n            if d.get("deska_kus"):', '        elif d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY:\n            if d.get("deska_kus"):', "entries_pro_cenu")
    s = nahrad(s, '''    "product_3220": [(None, 2, "Šroub imbus se zápustnou hlavou M6 (délka včetně hlavy – určí Robert)"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")],
}''', '''    "product_3220": [(None, 2, "Šroub imbus se zápustnou hlavou M6 (délka včetně hlavy – určí Robert)"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")],
    # HORNI POLICE (Robert 2026-10-07): Uhelnikova spojka 30x30 (#3045, drazka 8) / 40x40 (#3207, drazka 10) kotvi prepazku / lem k profilu: 1 sroub M6 + 1 otocna matice do drazky (NAVRH, Robert upresni)
    "product_3045": [("2.1.21.0612", 1, "Šroub imbus s válcovou hlavou M6×12"), ("2.1.001.08.06", 1, "Otočná matice M6 (drážka 8)")],
    "product_3207": [("2.1.21.0616", 1, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 1, "Otočná matice M6 (drážka 10)")],
}''', "SPOJOVACI_MATERIAL")
    s = nahrad(s, '''_NAZVY.update({"product_4956": "šuplíkový box (1 šuplík)", "product_4957": "šuplíkový box (3 šuplíky)"})''',
               '''_NAZVY.update({"product_4956": "šuplíkový box (1 šuplík)", "product_4957": "šuplíkový box (3 šuplíky)"})
_NAZVY.update({"product_3939": "MDF deska 8 mm (police)", "product_3539": "překližka PR10 10 mm (police)", "product_3045": "úhelníková spojka 30×30", "product_3207": "úhelníková spojka 40×40",
               "product_5360": "laminovaná dřevotříska 12 mm (police)"})                            # horní police (Robert 2026-10-07); 5360 = karta desky 12 mm (cislo doplni nasazeni)''', "_NAZVY")

    # --- vyrobni vypis
    s = nahrad(s, '''    if t == "panrail":
        return "pricka", f"profil pod / nad perforovaným panelem (úroveň {klic[2] + 1})"''', '''    if t == "hpol":
        return _hpol().role(klic)
    if t == "panrail":
        return "pricka", f"profil pod / nad perforovaným panelem (úroveň {klic[2] + 1})"''', "role_dilu")
    s = nahrad(s, '''    """Cislo kroku montazniho postupu pro dil (viz MONTAZNI_KROKY)."""
''', '''    """Cislo kroku montazniho postupu pro dil (viz MONTAZNI_KROKY)."""
    if "horní police" in popis:
        return 7
''', "_krok_montaze")
    s = vloz_pred_radek(s, '    kroky[1]["dily"] = [x["id"] for x in profily]', '''    hpi_ = r.get("hpolice_info")
    if hpi_ and not hpi_.get("problem"):                                # horni police: veta v kroku 7 JEN u zapnute police (vychozi vypis zustava bitove stejny)
        kroky[7]["text"] += (" Horní police mezi zadními stojkami: rám z profilů mezi stojkami (zadní a přední příčka, boční a střední profily), deska shora na rámu nebo v drážce profilů; "
                             "rám s přepážkami má podlahu v drážce a svislé přepážky z překližky na úhelnících, police s lemem pás z překližky na úhelnících.")
''', "montazni krok 7 police")
    s = nahrad(s, '''    zaklad, _, strana = deska_id.rpartition("_") if not deska_id.startswith("polvyr") else (deska_id, "", "0")''',
               '''    if deska_id.startswith("hpol"):
        return _hpol().popis_desky(deska_id)
    zaklad, _, strana = deska_id.rpartition("_") if not deska_id.startswith("polvyr") else (deska_id, "", "0")''', "_popis_desky")
    s = nahrad(s, '        if d["part_id"] == "product_4933" and d.get("deska_id"):\n            skup_d.setdefault', '        if (d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY) and d.get("deska_id"):\n            skup_d.setdefault', "vypis skup_d")
    s = nahrad(s, '    rozdelena = any(k.endswith("_1") for k in skup_d if not k.startswith("polvyr"))', '    rozdelena = any(k.endswith("_1") for k in skup_d if not k.startswith(("polvyr", "hpol")))', "vypis rozdelena")
    s = nahrad(s, '        if d.get("deska_id") and d["part_id"] == "product_4933":\n            role[i] = ', '        if d.get("deska_id") and (d["part_id"] == "product_4933" or d["part_id"] in _hpol().DESKA_PARTY):\n            role[i] = ', "vypis role desek")
    s = nahrad(s, '"tloustka_mm": 18.0, "sirka_mm"', '"tloustka_mm": _hpol().tloustka_dilu(dily[prvni]["part_id"]), "sirka_mm"', "vypis tloustka")
    s = nahrad(s, '''        did = q["deska_id"]
        if did.startswith("prac_"):
            return (0, 0, int(did[-1]))''', '''        did = q["deska_id"]
        if did.startswith("hpol"):
            return (3, 0, 0)                                               # desky horni police az za policemi pod vyrezy (porad vzniku zustava)
        if did.startswith("prac_"):
            return (0, 0, int(did[-1]))''', "vypis poradi desek")
    s = nahrad(s, '        if d["part_id"] in PROFIL_PARTS + ("product_4933",) + SPOJKY_PARTS + (LOZ_PART,) + NAVLEK_PARTS + SSE_PARTS:',
               '        if d["part_id"] in PROFIL_PARTS + ("product_4933",) + _hpol().DESKA_PARTY + SPOJKY_PARTS + (LOZ_PART,) + NAVLEK_PARTS + SSE_PARTS:', "vypis prisl skip")

    # --- kontrola: deska zasazena do drazky profilu
    s = nahrad(s, '    # vektorove: prunik vsech dvojic (n x n x 3); dotyk (< TOL_PRUNIK_MM) se nepocita\n', '''    for k_, c_ in clenove.items():              # deska zasazena do DRAZKY profilu (horni police): jeji obalka zasahuje do profilu o sirku drazky - to je zamer, ne zanoreni
        for kk_ in c_.get("zasazeno_do") or ():
            if k_ in idx and kk_ in idx:
                vyrez.add((min(idx[k_], idx[kk_]), max(idx[k_], idx[kk_])))
    # vektorove: prunik vsech dvojic (n x n x 3); dotyk (< TOL_PRUNIK_MM) se nepocita
''', "zkontroluj zasazeni")

    # --- 3D menu: skupina horni police
    s = nahrad(s, '''    pi_ = r.get("panely_info") or {}
    n_pan = int(p["panely_pocet"])
''', '''    hp_ = r.get("hpolice_info")
    if hp_ and not hp_.get("problem"):
        skupina("hpolice", "Police mezi stojkami", lambda k, rl, d: k[0] == "hpol", ["hpolice", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka"], _hpol().menu(r, pol))
    pi_ = r.get("panely_info") or {}
    n_pan = int(p["panely_pocet"])
''', "ovladani police")
    return s


# ---------------------------------------------------------------------------------------------------------------------
# stul_glb.py
# ---------------------------------------------------------------------------------------------------------------------
def patch_glb(s):
    s = nahrad(s, '    kanon = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in sorted(p.items())}\n',
               '    p = S._hpol().kanon_hash(p)                            # horni police (Robert 2026-10-07): klice se do hashe nepocitaji, dokud neni zapnuta (hashe stolu bez police zustavaji)\n'
               '    kanon = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in sorted(p.items())}\n', "kanonicky_hash")
    s = nahrad(s, 'POREDI_MATERIALU = ["alu", "lamino", "ocel", "seda", "cerna", "led", "chrom", "ral7016"]',
               'POREDI_MATERIALU = ["alu", "lamino", "ocel", "seda", "cerna", "led", "chrom", "mdf", "preklizka", "ral7016"]', "POREDI_MATERIALU")       # mdf / preklizka pred ral7016 (ten zustava posledni); prazdne materialy se do GLB nedostanou, takze stoly bez nich zustavaji beze zmeny
    s = nahrad(s, 'MATERIAL_DILU.update({pid_: "ocel" for pid_ in S.PANEL_PARTY})', '''MATERIALY["mdf"] = {"baseColorFactor": [0.34, 0.36, 0.39, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.6}                 # MDF Steel Grey 8 mm (police): tmave seda
MATERIALY["preklizka"] = {"baseColorFactor": [0.72, 0.56, 0.36, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.65}          # topolova foliovana prekliska PR10 (police): svetle drevo
MATERIAL_DILU.update(S._hpol().MATERIAL_DILU)                                                                                    # dily horni police (desky, uhelniky)
MATERIAL_DILU.update({pid_: "ocel" for pid_ in S.PANEL_PARTY})''', "materialy police")
    s = nahrad(s, '    path = os.path.join(S.KATALOG_DIR, part_id + ".glb")\n    if not os.path.isfile(path):\n        raise GlbChyba(f"chybi GLB dilu {part_id}")',
               '    path = S.glb_cesta(part_id)\n    if not os.path.isfile(path):\n        raise GlbChyba(f"chybi GLB dilu {part_id}")', "nacti_mesh cesta")
    return s


# ---------------------------------------------------------------------------------------------------------------------
# stul_sse.py
# ---------------------------------------------------------------------------------------------------------------------
def patch_sse(s):
    s = nahrad(s, 'NEPODPOROVANE = ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "navlek", "vzpery", "loz")',
               'NEPODPOROVANE = ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "navlek", "vzpery", "loz", "hpolice")', "SSE NEPODPOROVANE")
    s = nahrad(s, '"loz_rozteca", "loz_okraj", "vzpera_delka") + tuple(f"police_h{j}" for j in range(1, 11))',
               '"loz_rozteca", "loz_okraj", "vzpera_delka", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka") + tuple(f"police_h{j}" for j in range(1, 11))', "SSE IGNOROVANE")
    return s


# ---------------------------------------------------------------------------------------------------------------------
# stul_ovladani_verejne.py (verejna podoba 3D menu: nazvy slotu a preklady)
# ---------------------------------------------------------------------------------------------------------------------
def patch_ovladani_verejne(s):
    s = nahrad(s, '"stojky_vyska": "posth", "elzlab_y": "socketup", "elzlab_z": "socketside"}\nfor _n in range(1, S.MAX_VYREZU + 1):',
               '"stojky_vyska": "posth", "elzlab_y": "socketup", "elzlab_z": "socketside",\n                 "hpolice": "upshelf", "hpolice_typ": "upshelftype", "hpolice_deska": "upshelfboard", "hpolice_vyska": "upshelfpos", "hpolice_hloubka": "upshelfdepth"}\nfor _n in range(1, S.MAX_VYREZU + 1):', "PARAM_NA_SLOT")
    s = nahrad(s, '"vzpery": "braces", "ram": "frame"}', '"vzpery": "braces", "ram": "frame", "hpolice": "upshelf"}', "ID_CASTI")
    s = nahrad(s, '        if k == "panely_delka":\n            out[slot] = str(int(round(float(v))))', '        if k == "hpolice_typ":\n            out[slot] = S._hpol().TYP_VEREJNE[v]                                  # verejne id typu police (flat | frame | groove | lip | dividers)\n        if k == "panely_delka":\n            out[slot] = str(int(round(float(v))))', "_nastav_na_sloty")
    s = nahrad(s, "]\n\n\ndef _tabulka():", "] + S._hpol().PREKLADY                                       # horni police mezi zadnimi stojkami (Robert 2026-10-07)\n\n\ndef _tabulka():", "_PREKLADY")
    return s


def patch_shop_obal(s):
    sys.path.insert(0, HERE)
    from patch_shop import patch_shop
    return patch_shop(s, nahrad, vloz_pred_radek)


PATCHE = {"stul_konfigurator.py": patch_konfigurator, "stul_glb.py": patch_glb, "stul_sse.py": patch_sse, "stul_ovladani_verejne.py": patch_ovladani_verejne, "stul_shop.py": patch_shop_obal}


def aplikuj(src_api, dst_api, lam12_id=None):
    """Aplikuje vsechny zaplaty; vraci seznam zapsanych souboru. Vsechno se nejdriv spocita v pameti (chyba kotvy = nic se nezapise)."""
    vysl = {}
    for jmeno, fn in PATCHE.items():
        with open(os.path.join(src_api, jmeno), encoding="utf-8") as f:
            vysl[jmeno] = fn(f.read())
    modul = open(os.path.join(HERE, "stul_hpolice.py"), encoding="utf-8").read()
    if lam12_id:
        modul = nahrad(modul, 'LAM12_PART = "product_5360"', f'LAM12_PART = "product_{int(lam12_id)}"', "LAM12_PART")
        vysl["stul_konfigurator.py"] = vysl["stul_konfigurator.py"].replace('"product_5360": "laminovaná dřevotříska 12 mm (police)"', f'"product_{int(lam12_id)}": "laminovaná dřevotříska 12 mm (police)"')
    vysl["stul_hpolice.py"] = modul
    for jmeno, text in vysl.items():
        cil = os.path.join(dst_api, jmeno)
        if os.path.islink(cil):
            os.remove(cil)
        with open(cil, "w", encoding="utf-8") as f:
            f.write(text)
    return sorted(vysl)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lam = None
    if "--lam12-id" in sys.argv:
        lam = sys.argv[sys.argv.index("--lam12-id") + 1]
        args = [a for a in args if a != lam]
    if len(args) != 2:
        sys.exit(__doc__)
    print("zapsano:", ", ".join(aplikuj(args[0], args[1], lam)))
