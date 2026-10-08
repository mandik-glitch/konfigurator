#!/usr/bin/env python3
"""DRUHE KOLO horni police (sikma police na boxy; bot8 fork 3, 2026-10-08): KOTVENE zaplaty NAD v1 (stav po commitu 110b03d3) + vymena modulu stul_hpolice.py za v2 (cely soubor).
Z ZIVYCH souboru v <src_api> udela upravene soubory v <dst_api>; kazda kotva se musi v souboru vyskytovat PRAVE JEDNOU (assert), jinak se nic nezapise. src = dst => nasazeni primo do zivych souboru.
  apply_patches_v2.py <src_api> <dst_api>"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LENIENT = []


def nahrad(s, a, b, label):
    n = s.count(a)
    if n != 1:
        if LENIENT is not None and "--lenient" in sys.argv:
            LENIENT.append((label, n))
            return s
        raise AssertionError(f"kotva '{label}': {n} vyskytu (ocekavan 1)")
    return s.replace(a, b)


def vloz_pred_radek(s, prefix, text, label):
    m = list(re.finditer(r"^" + re.escape(prefix) + r".*$", s, re.M))
    if len(m) != 1:
        if "--lenient" in sys.argv:
            LENIENT.append((label, len(m)))
            return s
        raise AssertionError(f"kotva '{label}': {len(m)} radku s prefixem (ocekavan 1)")
    i = m[0].start()
    return s[:i] + text + s[i:]


def vloz_pred_radek_s(s, podretezec, text, label):
    """Vlozi `text` PRED jediny radek, ktery OBSAHUJE `podretezec`."""
    radky = s.split("\n")
    nalez = [i for i, r in enumerate(radky) if podretezec in r]
    if len(nalez) != 1:
        if "--lenient" in sys.argv:
            LENIENT.append((label, len(nalez)))
            return s
        raise AssertionError(f"kotva '{label}': {len(nalez)} radku s podretezcem (ocekavan 1)")
    radky.insert(nalez[0], text.rstrip("\n"))
    return "\n".join(radky)


def patch_konfigurator(s):
    s = nahrad(s, '"hpolice_vyska": None, "hpolice_hloubka": 300.0,', '"hpolice_vyska": None, "hpolice_hloubka": 300.0, "hpolice_sklon": 15.0,', "VYCHOZI sklon")
    s = nahrad(s, '''    for k in poradi:
        c = clenove.get(k) or spojky[k]
        dily.append({"part_id": c["part_id"], "position": [round(float(v), 4) for v in c["pos"]],
                     "quaternion": [round(float(v), 6) for v in c["quaternion"]],
                     "scale": [round(float(v), 6) for v in c["scale"]]})
''', '''    for k in poradi:
        c = clenove.get(k) or spojky[k]
        pos_c, q_c = c["pos"], c["quaternion"]
        if hpolice_info and hpolice_info.get("rotace") and _hpol().v_rotaci(k, c, clenove):
            pos_c, q_c = _hpol().rotuj(hpolice_info["rotace"], pos_c, q_c)          # sikma horni police: ram se postavil PLOCHY, tady se tuhe otoci kolem osy zadni pricky
        dily.append({"part_id": c["part_id"], "position": [round(float(v), 4) for v in pos_c],
                     "quaternion": [round(float(v), 6) for v in q_c],
                     "scale": [round(float(v), 6) for v in c["scale"]]})
''', "dily: rotace sikme police")
    s = vloz_pred_radek(s, '    _oznac_desky(clenove, zm)', '    _hpol().pridej_konzoly(hpolice_info, clenove)                  # sikma horni police: naklapeci konzole az po zaslepkach volnych koncu (jinak by se dotykaly koncu profilu v plochem stavu)\n', "pridej_konzoly")
    s = nahrad(s, 'and not _je_vz(k)]      # sikma vzpera nema celni dotyk (AABB sikmeho profilu je velka)', 'and not _je_vz(k) and not c.get("hp_rot")]      # sikma vzpera a naklonena horni police nemaji celni dotyk (AABB sikmeho profilu je velka)', "prof_zakl")
    s = vloz_pred_radek_s(s, '# vzpera drzi na stojce a na rameni pres sikme spojky', '''    for ka_, kb_ in ((hpolice_info or {}).get("pary") or ()):      # sikma horni police: spoje profil - profil (AABB naklonenych profilu spoj nepozna)
        if ka_ in idx and kb_ in idx:
            peers[min(idx[ka_], idx[kb_])].add(max(idx[ka_], idx[kb_]))
''', "lic_peers pary police")
    s = nahrad(s, '''    vz_vse = {idx[k] for k in list(clenove) + list(spojky) if _je_vz(k)}          # sikme vzpery se kontroluji presne v _zkontroluj_vzpery
''', '''    vz_vse = {idx[k] for k in list(clenove) + list(spojky) if _je_vz(k)}          # sikme vzpery se kontroluji presne v _zkontroluj_vzpery
    sk_vse = {idx[k] for k, c in list(clenove.items()) + list(spojky.items()) if _hpol().v_skupine(k, c, clenove)}          # sikma horni police: presna kontrola OBB x AABB (stul_hpolice.zkontroluj)
''', "sk_vse")
    s = nahrad(s, 'd["part_id"] not in SPOJKY_PARTS + KONCE_PARTS + NAVLEK_PARTS and i not in vz_vse]', 'd["part_id"] not in SPOJKY_PARTS + KONCE_PARTS + NAVLEK_PARTS and i not in vz_vse and i not in sk_vse]', "nep")
    s = nahrad(s, '    spoj_i = [i for i, d in enumerate(dily) if d["part_id"] in SPOJKY_PARTS]', '    spoj_i = [i for i, d in enumerate(dily) if d["part_id"] in SPOJKY_PARTS and i not in sk_vse]', "spoj_i")
    s = nahrad(s, 'komp_i = [idx[k] for k, c in clenove.items() if c["druh"] in ("prisl", "deska") and not _je_zasl(k)]', 'komp_i = [idx[k] for k, c in clenove.items() if c["druh"] in ("prisl", "deska") and not _je_zasl(k) and idx[k] not in sk_vse]', "komp_i")
    s = nahrad(s, '    problemy = _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, (xf, xr, zl, zr))\n', '    problemy = _zkontroluj(dily, bb, clenove, spojky, idx, konce_ocek, (xf, xr, zl, zr))\n    problemy += _hpol().zkontroluj(hpolice_info, dily, bb, idx, clenove, spojky)          # sikma horni police: presna kontrola kolizi naklonenych dilu\n', "zkontroluj sikmou")
    s = nahrad(s, '''"text": "Police mezi zadními stojkami se sem nevejde – stůl je málo hluboký pro tento typ police (vyberte jiný typ, nebo ji vypněte)."})
''', '''"text": "Police mezi zadními stojkami se sem nevejde – stůl je málo hluboký pro tento typ police (vyberte jiný typ, nebo ji vypněte)."})
    elif hpolice_info and hpolice_info.get("problem") == "sekce":
        problemy.append({"kod": "hpolice_nevejde", "dily": [], "text": "Šikmá police mezi zadními stojkami zatím nejde u stolu se střední zadní nohou (na jednu stojku by se nevešly dvě konzole) – zvolte vestavěný rám, nebo jiný typ police."})
''', "problem sekce")
    s = nahrad(s, ', "hpolice_hloubka") + VYREZY_CISLA\n', ', "hpolice_hloubka", "hpolice_sklon") + VYREZY_CISLA\n', "_CISLA sklon")
    s = nahrad(s, '''        bb_vse = np.array([_bb_clenu(clenove[k]) if k in clenove else _bb_clenu(spojky[k]) for k in kl_vse], float)
''', '''        bb_vse = np.array([_bb_clenu(clenove[k]) if k in clenove else _bb_clenu(spojky[k]) for k in kl_vse], float)
        kl_vse, bb_vse = _hpol().pro_vzpery(hpolice_info, kl_vse, bb_vse, clenove, spojky)          # sikma horni police: obalky naklonenych dilu a konzol v definitivni poloze (vzpera se jim prizpusobi)
''', "vzpery: obalky sikme police")
    s = nahrad(s, '''    "product_3207": [("2.1.21.0616", 1, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 1, "Otočná matice M6 (drážka 10)")],
''', '''    "product_3207": [("2.1.21.0616", 1, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 1, "Otočná matice M6 (drážka 10)")],
    # NAKLAPECI KONZOLE sikme police (2. kolo; NAVRH, Robert upresni): 2 sroubky + 2 matice do drazky na list P1 (stojka) a 2 + 2 na desku P2 (kloub + obloukova drazka v sikmem profilu) = 4 + 4 na konzolu
    "product_3323": [("2.1.21.0612", 4, "Šroub imbus s válcovou hlavou M6×12"), ("2.1.001.08.06", 4, "Otočná matice M6 (drážka 8)")],
    "product_3324": [("2.1.21.0616", 4, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 4, "Otočná matice M6 (drážka 10)")],
''', "SPOJOVACI_MATERIAL konzoly")
    s = vloz_pred_radek(s, '_NAZVY.update({"product_3939"', '_NAZVY.update({"product_3323": "úhlová naklápěcí konzola (drážka 8)", "product_3324": "úhlová naklápěcí konzola (drážka 10)"})             # sikma horni police (2. kolo)\n', "_NAZVY konzoly")
    return s


def patch_sse(s):
    return nahrad(s, '"hpolice_vyska", "hpolice_hloubka")', '"hpolice_vyska", "hpolice_hloubka", "hpolice_sklon")', "SSE IGNOROVANE sklon")


def patch_ovladani_verejne(s):
    return nahrad(s, '"hpolice_vyska": "upshelfpos", "hpolice_hloubka": "upshelfdepth"', '"hpolice_vyska": "upshelfpos", "hpolice_hloubka": "upshelfdepth", "hpolice_sklon": "upshelftilt"', "PARAM_NA_SLOT sklon")


def patch_shop(s):
    s = nahrad(s, '"upshelfdepth": int(HP.HLOUBKA_VYCHOZI)}', '"upshelfdepth": int(HP.HLOUBKA_VYCHOZI), "upshelftilt": int(HP.SKLON_VYCHOZI)}', "VYCHOZI_VYBER tilt")
    s = nahrad(s, 'slider("upshelfdepth", "g_extras", int(HP.HLOUBKA_MIN), int(HP.HLOUBKA_MAX), 10, "mm"),', 'slider("upshelfdepth", "g_extras", int(HP.HLOUBKA_MIN), int(HP.HLOUBKA_MAX), 10, "mm"), slider("upshelftilt", "g_extras", int(HP.SKLON_MIN), int(HP.SKLON_MAX), int(HP.SKLON_KROK), "°"),', "schema tilt")
    s = nahrad(s, 'for k_ in ("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth")})', 'for k_ in ("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt")})', "zavisi_na tilt")
    s = nahrad(s, '''    p["hpolice_hloubka"] = _cislo(sel["upshelfdepth"], HP.HLOUBKA_MIN, HP.HLOUBKA_MAX, HP.HLOUBKA_VYCHOZI, 10) if p["hpolice"] else float(HP.HLOUBKA_VYCHOZI)
''', '''    p["hpolice_hloubka"] = _cislo(sel["upshelfdepth"], HP.HLOUBKA_MIN, HP.HLOUBKA_MAX, HP.HLOUBKA_VYCHOZI, 10) if p["hpolice"] else float(HP.HLOUBKA_VYCHOZI)
    p["hpolice_sklon"] = _cislo(sel["upshelftilt"], HP.SKLON_MIN, HP.SKLON_MAX, HP.SKLON_VYCHOZI, HP.SKLON_KROK) if (p["hpolice"] and p["hpolice_typ"] == "sikma") else float(HP.SKLON_VYCHOZI)       # sklon jen u sikme police
''', "normalizuj sklon")
    s = nahrad(s, 'norm["upshelfpos"], norm["upshelfdepth"] = _cele_nebo_none(p["hpolice_vyska"]), int(round(p["hpolice_hloubka"]))\n', 'norm["upshelfpos"], norm["upshelfdepth"] = _cele_nebo_none(p["hpolice_vyska"]), int(round(p["hpolice_hloubka"]))\n    norm["upshelftilt"] = int(round(p["hpolice_sklon"]))\n', "norm tilt")
    s = nahrad(s, '    norm["upshelfdepth"] = int(round(p["hpolice_hloubka"]))\n', '    norm["upshelfdepth"] = int(round(p["hpolice_hloubka"]))\n    norm["upshelftilt"] = int(round(p["hpolice_sklon"])) if (p["hpolice"] and p["hpolice_typ"] == "sikma") else int(HP.SKLON_VYCHOZI)\n', "_spocti norm tilt")
    s = nahrad(s, 'round(float(p["hpolice_hloubka"]), 1)]', 'round(float(p["hpolice_hloubka"]), 1)] + ([round(float(p["hpolice_sklon"]), 1)] if p["hpolice_typ"] == "sikma" else [])', "_zabal sklon")
    s = nahrad(s, '        p["hpolice_hloubka"] = float(o["R"][3])', '        p["hpolice_hloubka"] = float(o["R"][3])\n        if len(o["R"]) > 4:\n            p["hpolice_sklon"] = float(o["R"][4])', "_rozbal sklon")
    s = nahrad(s, 'skryt.update(("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth"))', 'skryt.update(("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"))', "souhrn off tilt")
    s = nahrad(s, '''        if sel.get("upshelftype") == "frame":
            skryt.add("upshelfboard")
''', '''        if sel.get("upshelftype") == "frame":
            skryt.add("upshelfboard")
        if sel.get("upshelftype") != "slope":
            skryt.add("upshelftilt")
''', "souhrn tilt")
    s = nahrad(s, 'and not (k == "hpolice" and not v)', 'and not (k == "hpolice" and not v) and not (k == "hpolice_sklon" and p.get("hpolice_typ") != "sikma")', "staff blok sklon")
    s = nahrad(s, '"reason": dz["upshelf_typ_nevejde"]}', '"reason": dz["upshelf_typ_sekce"] if x_.get("duvod") == "sekce" else dz["upshelf_typ_nevejde"]}', "options typ duvod")
    s = nahrad(s, '    dz = DUVODY[lang]\n    options["upshelftype"]', '''    if p["hpolice"] and p["stojky"] and hp_inf and not hp_inf.get("problem") and p["hpolice_typ"] == "sikma":          # sklon sikme police (jen u typu sikma; jinak posuvnik zamceny)
        options["upshelftilt"] = {"min": int(HP.SKLON_MIN), "max": int(HP.SKLON_MAX), "value": int(round(p["hpolice_sklon"]))}
    else:
        options["upshelftilt"] = {"min": int(HP.SKLON_VYCHOZI), "max": int(HP.SKLON_VYCHOZI)}
    dz = DUVODY[lang]
    options["upshelftype"]''', "options tilt")
    s = vloz_pred_radek(s, "def _spocti(", '''# SIKMA POLICE NA BOXY (2. kolo, bot8 2026-10-08): slot sklonu `upshelftilt` (5-30 st. po 5, vychozi 15; jen u typu `slope`), texty cs / en / sk
TEXTY["cs"].update({"upshelftilt": "Sklon police (vpředu níž)", "upshelftype_slope": "Šikmá, na boxy (s lemem vpředu)"})
TEXTY["en"].update({"upshelftilt": "Shelf slope (lower at the front)", "upshelftype_slope": "Sloped, for boxes (with a front lip)"})
TEXTY["sk"].update({"upshelftilt": "Sklon police (vpredu nižšie)", "upshelftype_slope": "Šikmá, na boxy (s lemom vpredu)"})
TEXTY["cs"]["help_upshelf"] += " Šikmá police na boxy je skloněná dopředu dolů (výchozí sklon 15°), vpředu má lem proti sjetí boxů a drží ji dvě naklápěcí konzole na zadních stojkách; výška je výška zadního okraje desky."
TEXTY["en"]["help_upshelf"] += " The sloped shelf for boxes slopes down towards the front (default 15°), has a front lip so that boxes cannot slide off and is held by two tilting brackets on the rear uprights; the height is the height of the rear edge of the board."
TEXTY["sk"]["help_upshelf"] += " Šikmá polica na boxy je naklonená dopredu nadol (predvolený sklon 15°), vpredu má lem proti zošmyknutiu boxov a drží ju dve naklápacie konzoly na zadných stojkách; výška je výška zadnej hrany dosky."
DUVODY["cs"]["upshelf_typ_sekce"] = "Šikmá police zatím nejde u stolu se střední zadní nohou (na jednu stojku by se nevešly dvě konzole) – zvolte vestavěný rám, nebo jiný typ police."
DUVODY["en"]["upshelf_typ_sekce"] = "The sloped shelf is not available yet for a table with a rear centre leg (two brackets would not fit on one upright) – choose the built-in frame or another shelf type."
DUVODY["sk"]["upshelf_typ_sekce"] = "Šikmá polica zatiaľ nejde pri stole so strednou zadnou nohou (na jednu stojku by sa nezmestili dve konzoly) – zvoľte vstavaný rám, alebo iný typ police."


''', "texty tilt")
    return s


PATCHE = {"stul_konfigurator.py": patch_konfigurator, "stul_sse.py": patch_sse, "stul_ovladani_verejne.py": patch_ovladani_verejne, "stul_shop.py": patch_shop}


def aplikuj(src_api, dst_api):
    vysl = {}
    for jmeno, fn in PATCHE.items():
        with open(os.path.join(src_api, jmeno), encoding="utf-8") as f:
            vysl[jmeno] = fn(f.read())
    vysl["stul_hpolice.py"] = open(os.path.join(HERE, "stul_hpolice.py"), encoding="utf-8").read()
    if LENIENT:
        return vysl
    for jmeno, text in vysl.items():
        cil = os.path.join(dst_api, jmeno)
        if os.path.islink(cil):
            os.remove(cil)
        with open(cil, "w", encoding="utf-8") as f:
            f.write(text)
    return sorted(vysl)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)
    r = aplikuj(args[0], args[1])
    if LENIENT:
        print("SELHALE KOTVY:", LENIENT)
        sys.exit(1)
    print("zapsano:", ", ".join(r))
