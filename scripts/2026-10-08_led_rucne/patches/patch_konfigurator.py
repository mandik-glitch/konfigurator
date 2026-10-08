#!/usr/bin/env python3
"""Zaplata api/stul_konfigurator.py: RUCNI pocet svitidel LED (`led_pocet`) a RUCNI poloha kazdeho svitidla (`led_z1..led_z<LED_MAX>`) - bot8, 2026-10-08.

Robert: "svitidla v generatoru se pridavaji automaticky za sebe podle delky, ale chceme aby se pridavali jen rucne a mohli se posouvat podel profilu".
Pocet svitidel uz neurcuje sirka stolu (drive max(1, floor((sirka + 47) / telo)) vedle sebe), vychozi je JEDNO svitidlo; zakaznik je pridava / odebira a posouva po prici nad LED.
Kotvene nahrady (assert count == 1). Pouziti: patch_konfigurator.py <vstup stul_konfigurator.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


def nahrad_radek(s, zacatek, fn, label):
    """Najde PRAVE JEDEN radek, jehoz obsah (po odsazeni) zacina `zacatek`, a nahradi ho vysledkem fn(radek)."""
    radky = s.split("\n")
    nalezy = [i for i, r in enumerate(radky) if r.lstrip().startswith(zacatek)]
    assert len(nalezy) == 1, "radek %s: %d vyskytu" % (label, len(nalezy))
    radky[nalezy[0]] = fn(radky[nalezy[0]])
    return "\n".join(radky)


def nahrad_rozsah(s, zacatek, konec, nove, label):
    """Radky od (vcetne) radku zacinajiciho `zacatek` do (vcetne) radku zacinajiciho `konec` se nahradi textem `nove`."""
    radky = s.split("\n")
    z = [i for i, r in enumerate(radky) if r.startswith(zacatek)]
    assert len(z) == 1, "zacatek rozsahu %s: %d vyskytu" % (label, len(z))
    k = [i for i in range(z[0], len(radky)) if radky[i].startswith(konec)]
    assert k, "konec rozsahu %s nenalezen" % label
    return "\n".join(radky[:z[0]] + nove.rstrip("\n").split("\n") + radky[k[0] + 1:])


# 1) konstanty + pomocne funkce -------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, "LED_PARTY = frozenset(LED_TYPY.values())", lambda r: r + '''
LED_MAX = 4                         # nejvic svitidel LED na stole (nejsirsi stul 3000 mm: 4 x 600 mm); od 2026-10-08 je POCET svitidel RUCNI volba (`led_pocet`, vychozi 1), polohu kazdeho urcuje `led_z1..led_z<LED_MAX>`
LED_PARAMETRY_Z = tuple(f"led_z{_k}" for _k in range(1, LED_MAX + 1))''', "LED_MAX")

s = nahrad(s, '''def kvat_na_matici(q):''', '''def led_max_pocet(sirka, telo):
    """Nejvic svitidel, ktera se na stul vejdou: soucet delek teles <= sirka stolu + LED_PREVIS (pravidlo jako dosud: max(1, floor((sirka + LED_PREVIS) / telo))), nejvic LED_MAX."""
    return max(1, min(LED_MAX, int((sirka + LED_PREVIS) // telo)))


def led_polohy(n, telo, c0, p0, p1, zadane, rozpeti_max):
    """Efektivni polohy STREDU teles `n` svitidel (absolutni z, zleva doprava), jejich AUTOMATICKE polohy a meze stredu jednoho svitidla.
    Automaticka poloha = svitidla tesne vedle sebe, skupina vystredena kolem `c0` (stred JEDNOHO svitidla ve vychozi / sablonove poloze: u 1 svitidla beze zmeny proti dosavadnimu stavu).
    `zadane` = n hodnot (absolutni z stredu, nebo None = automaticka poloha). Pravidla: poradi se nemeni (index = poradi zleva doprava), svitidla se neprekryvaji (nejmene tesne vedle sebe; kdo by se
    prekryl, je odsunut), aspon 90 % delky kazdeho svitidla lezi nad pricnym profilem <p0, p1> (MIN_PODIL_PROFILU_LED) a rozpeti cele skupiny nepresahne `rozpeti_max` (sirka stolu + LED_PREVIS,
    stejne pravidlo jako kontrola `mimo_obrys`). Vraci (polohy, automaticke, (nejmensi stred, nejvetsi stred))."""
    s_ = float(telo)
    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    auto = [c0 + (k - (n - 1) / 2.0) * s_ for k in range(n)]
    v, zbyva = [], max(0.0, rozpeti_max - n * s_)
    for k in range(n):
        chce = zadane[k] if zadane[k] is not None else auto[k]
        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax - (n - 1 - k) * s_
        if k:
            hi = min(hi, v[k - 1] + s_ + zbyva)
        x = min(max(chce, lo), hi) if lo <= hi else lo
        if k:
            zbyva -= x - v[k - 1] - s_
        v.append(x)
    return v, auto, (cmin, cmax)


def led_meze(v, telo, p0, p1, rozpeti_max):
    """Meze stredu kazdeho svitidla (absolutni z) pri dane poloze ostatnich: [(nejmene, nejvic), ...]. Sousedi se nesmi prekryt, aspon 90 % delky nad profilem, rozpeti skupiny <= `rozpeti_max`."""
    s_ = float(telo)
    q = MIN_PODIL_PROFILU_LED * s_
    cmin, cmax = p0 + q - s_ / 2.0, p1 - q + s_ / 2.0
    n = len(v)
    out = []
    for k in range(n):
        lo = cmin if k == 0 else v[k - 1] + s_
        hi = cmax if k == n - 1 else v[k + 1] - s_
        if n > 1 and k == 0:
            lo = max(lo, v[-1] + s_ - rozpeti_max)
        if n > 1 and k == n - 1:
            hi = min(hi, v[0] - s_ + rozpeti_max)
        out.append((lo, hi))
    return out


def _led_param_patch(pol, aut, zc):
    """Parametry generatoru pro svitidla v polohach `pol` (absolutni z stredu): `led_pocet` a `led_z1..`; poloha shodna s automatickou (`aut`) = None; zbyle az do LED_MAX = None."""
    out = {"led_pocet": len(pol)}
    for k in range(LED_MAX):
        out[f"led_z{k + 1}"] = (None if abs(pol[k] - aut[k]) < 0.05 else round(pol[k] - zc, 1)) if k < len(pol) else None
    return out


def led_pridat(st):
    """Parametry po PRIDANI dalsiho svitidla (nebo None, kdyz se uz zadne nevejde): nove svitidlo tesne vpravo od posledniho, jinak tesne vlevo od prvniho, jinak do mezery mezi dvema (kde je misto),
    a kdyz se nevejde ani tak (ostatni by se musela posunout), vsechna svitidla znovu tesne vedle sebe a vystredena (automaticke polohy); polohy ostatnich svitidel zustavaji, kdyz to jde."""
    n = st["n"]
    if n >= st["n_max"]:
        return None
    s_, v = st["telo"], list(st["v"])
    kandidati = [v + [v[-1] + s_], [v[0] - s_] + v]
    for k in range(n - 1):
        if v[k + 1] - v[k] >= 2 * s_ - 1e-9:
            kandidati.append(v[:k + 1] + [v[k] + s_] + v[k + 1:])
    for c in kandidati:
        pol, aut, _m = led_polohy(n + 1, s_, st["c0"], st["z_lo"], st["z_hi"], c, st["rozpeti"])
        if all(abs(pol[i] - c[i]) < 0.05 for i in range(n + 1)):
            return _led_param_patch(pol, aut, st["zc"])
    pol, aut, _m = led_polohy(n + 1, s_, st["c0"], st["z_lo"], st["z_hi"], [None] * (n + 1), st["rozpeti"])
    return _led_param_patch(pol, aut, st["zc"])


def led_odebrat(st, k):
    """Parametry po ODEBRANI svitidla cislo `k` (0 = nejlevejsi): ostatni zustanou na svych mistech (polohy se zapisou vyslovne, pokud nejsou shodne s automatickymi pro mensi pocet)."""
    v = [x for i, x in enumerate(st["v"]) if i != k]
    n = len(v)
    aut = [st["c0"] + (j - (n - 1) / 2.0) * st["telo"] for j in range(n)]
    return _led_param_patch(v, aut, st["zc"])


def kvat_na_matici(q):''', "led_polohy")

# 2) vychozi parametry ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, '"led_delka": float(LED_DELKA_VYCHOZI),', lambda r: r + '''
    "led_pocet": 1,               # Robert 2026-10-08: POCET svitidel LED RUCNE (1..LED_MAX; drive automaticky podle sirky stolu); relevantni jen kdyz led, stojky a svitidlo
    **{f"led_z{_k}": None for _k in range(1, LED_MAX + 1)},   # poloha STREDU _k-teho svitidla v mm od OSY STOLU (kladne = doprava); None = automaticka (svitidla tesne vedle sebe, skupina vystredena jako dosud)''', "VYCHOZI")

# 3) normalizace ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, 'out["led_delka"] = float(int(round(ld_)))', lambda r: r + '''
    lp_ = out["led_pocet"]
    if isinstance(lp_, bool) or not isinstance(lp_, (int, float)) or not math.isfinite(lp_) or lp_ != int(lp_):
        raise StulChyba(f"led_pocet: pocet svitidel musi byt cele cislo, je {lp_!r}", "mimo_rozsah")
    if not 1 <= int(lp_) <= LED_MAX:
        raise StulChyba(f"led_pocet: pocet svitidel {int(lp_)} je mimo rozsah 1-{LED_MAX}", "mimo_rozsah")
    out["led_pocet"] = int(lp_)
    for k_ in LED_PARAMETRY_Z:
        v_ = out[k_]
        if v_ is None:
            continue
        if isinstance(v_, bool) or not isinstance(v_, (int, float)) or not math.isfinite(v_):
            raise StulChyba(f"{k_}: poloha svitidla neni cislo", "mimo_rozsah")
        out[k_] = round(float(v_), 1)''', "norm")

# 4) skupina svitidel (2a) ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
NOVA_2A = '''    # 2a) svitidla LED: POCET i POLOHA jsou RUCNI volba (Robert 2026-10-08: "svitidla se maji pridavat jen rucne a mohla se posouvat podel profilu"); vychozi = jedno svitidlo, polohy None = svitidla
    #     tesne vedle sebe, skupina vystredena jako dosud. PANELY se stavi az po strednich nohach (viz 2b+)
    led_stav = None
    if (p["led"] and p["stojky"] and p["led_svetlo"]):
        d_led = _led_delka_int(p["led_delka"])                       # delka svitidel (vsechna stejna): dil katalogu zvolene delky, rozteč = delka jeho tělesa z GLB (1200: 1247, 600: 647 mm)
        s_led = led_telo_dilu(LED_TYPY[d_led])
        n_max_led = led_max_pocet(p["sirka"], s_led)                 # nejvic svitidel, ktera se vejdou (soucet delek <= sirka + LED_PREVIS)
        n_l = min(int(p["led_pocet"]), n_max_led)
        zakl = clenove[("t", LED)]
        zakl["part_id"] = LED_TYPY[d_led]                            # clen sablony nese dil 1200; jina delka = jiny dil se STEJNYM otocenim a polohou (stejny stred bboxu)
        zakl["pos"][0] += x_led
        b_lo_l, b_hi_l = _aabb({"part_id": zakl["part_id"], "quaternion": zakl["quaternion"], "scale": zakl["scale"], "position": zakl["pos"]})
        c0_led = float((b_lo_l[2] + b_hi_l[2]) / 2.0)                # stred JEDNOHO svitidla ve vychozi poloze (sablona; neni presne ve stredu stolu)
        z_lo_led, z_hi_led = float(zl - _H()), float(zr + _H())      # vnejsi okraje stolu = rozsah pricneho profilu nad LED
        zc_led = (z_lo_led + z_hi_led) / 2.0                         # osa stolu (referencni nula poloh led_z<k>)
        rozpeti_led = (z_hi_led - z_lo_led) + LED_PREVIS
        proveditelne = bool(n_l * s_led <= rozpeti_led + 1e-9 and (z_hi_led - z_lo_led) >= MIN_PODIL_PROFILU_LED * s_led)          # stul uzky pro svitidlo: dosavadni chovani (auto poloha, kontroly ohlasi problem)
        zad_led = [(zc_led + float(p[f"led_z{_k + 1}"])) if (proveditelne and p[f"led_z{_k + 1}"] is not None) else None for _k in range(n_l)]
        v_led, auto_led, mez_stred = led_polohy(n_l, s_led, c0_led, z_lo_led, z_hi_led, zad_led, rozpeti_led)
        if not proveditelne:
            v_led = list(auto_led)
        rel_led = []                                                 # efektivni poloha kazdeho svitidla v mm od osy stolu na mrizce 0,1 mm (stejna hodnota se pouzije pro geometrii i pro parametry)
        for k_led in range(n_l):
            if abs(v_led[k_led] - auto_led[k_led]) < 0.05:
                v_led[k_led] = auto_led[k_led]
                rel_led.append(None)
            else:
                rel_led.append(round(v_led[k_led] - zc_led, 1))
                v_led[k_led] = zc_led + rel_led[-1]
        z_base_led = float(zakl["pos"][2])
        zakl["pos"][2] = z_base_led + (v_led[0] - c0_led)
        for k in range(1, n_l):
            kl = _klon(sab, LED, np.array([zakl["pos"][0], zakl["pos"][1], z_base_led + (v_led[k] - c0_led)]))
            kl["part_id"] = LED_TYPY[d_led]
            clenove[("led", k)] = kl
        p["led_pocet"] = n_l                                         # efektivni hodnoty (pozadovany pocet / poloha se mohly orezat): jedna konfigurace = jedna kanonicka podoba = jeden hash
        for k_led in range(LED_MAX):
            p[f"led_z{k_led + 1}"] = rel_led[k_led] if k_led < n_l else None
        led_stav = {"n": n_l, "n_max": n_max_led, "telo": s_led, "c0": c0_led, "zc": zc_led, "z_lo": z_lo_led, "z_hi": z_hi_led, "rozpeti": rozpeti_led, "proveditelne": proveditelne,
                    "v": [float(x) for x in v_led], "auto": [float(x) for x in auto_led], "rel": rel_led, "stred_meze": (float(mez_stred[0]), float(mez_stred[1]))}
    else:
        p["led_delka"] = float(LED_DELKA_VYCHOZI)                    # bez svitidla (vypnute LED / stojky / svitidlo, nebo odebrane, protoze se nevejde) delka, pocet ani poloha nic nedelaji
        p["led_pocet"] = 1
        for k_led in LED_PARAMETRY_Z:
            p[k_led] = None
'''
s = nahrad_rozsah(s, "    # 2a) skupina LED podle sirky", '        p["led_delka"] = float(LED_DELKA_VYCHOZI)', NOVA_2A, "2a")

# 5) led_info -----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
NOVA_INFO = '''    led_info = {"delka": int(round(float(p["led_delka"]))), "typy": [], "pocet": 1, "max": 1, "polohy": [], "auto": [], "meze": [], "pridat": None, "odebrat": []}          # delky svitidel LED, pocet, polohy a meze (vztazene k OSE STOLU, mm)
    if p["led"] and p["stojky"] and p["led_svetlo"] and led_stav:
        wout = float(zr - zl + 2 * _H())
        dp_led = 1000.0 * clenove[("t", ZRAIL_TOP)]["scale"][1] if ("t", ZRAIL_TOP) in clenove else None
        n_led = led_stav["n"]
        for d_led in LED_DELKY:
            try:
                telo_l, presne_l = led_telo_dilu(LED_TYPY[d_led]), _led_telo_presne(LED_TYPY[d_led])
            except StulChyba:
                continue                                                           # GLB teto delky v katalogu chybi: delka se nenabizi
            n_t = led_max_pocet(p["sirka"], telo_l)
            presah_t = (n_t - 1) * telo_l + presne_l - wout                        # nejvyssi pocet svitidel teto delky tesne vedle sebe: vejde se, kdyz soucet delek nepresahne sirku + LED_PREVIS (jako dosud)
            led_info["typy"].append({"delka": d_led, "telo": telo_l, "pocet": n_t, "min_sirka": int(math.ceil(telo_l - LED_PREVIS)),
                                     "vejde": bool(presah_t <= LED_PREVIS + 1.0 and (dp_led is None or dp_led >= MIN_PODIL_PROFILU_LED * n_t * telo_l - 0.01))})
        zc_l, s_l = led_stav["zc"], led_stav["telo"]
        meze_abs = led_meze(led_stav["v"], s_l, led_stav["z_lo"], led_stav["z_hi"], led_stav["rozpeti"]) if led_stav["proveditelne"] else [(v_ - 1e6, v_ + 1e6) for v_ in led_stav["v"]]
        led_info.update({"pocet": n_led, "max": led_stav["n_max"], "telo": s_l, "osa": round(zc_l, 1),
                         "polohy": [round(v_ - zc_l, 1) for v_ in led_stav["v"]], "auto": [round(a_ - zc_l, 1) for a_ in led_stav["auto"]],
                         "meze": [[round(lo_ - zc_l, 1), round(hi_ - zc_l, 1)] for lo_, hi_ in meze_abs], "okraj": [round(led_stav["z_lo"] - zc_l, 1), round(led_stav["z_hi"] - zc_l, 1)],
                         "stred": [round(led_stav["stred_meze"][0] - zc_l, 1), round(led_stav["stred_meze"][1] - zc_l, 1)],
                         "pridat": led_pridat(led_stav) if led_stav["proveditelne"] else None,
                         "odebrat": [led_odebrat(led_stav, k_) for k_ in range(n_led)] if (led_stav["proveditelne"] and n_led > 1) else []})
'''
s = nahrad_rozsah(s, '    led_info = {"delka": int(round(float(p["led_delka"]))), "typy": []}', '                                     "vejde": bool(presah_t <= LED_PREVIS + 1.0', NOVA_INFO, "led_info")

# 6) kontrola profil_led_kratky: rozpeti skupiny ---------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, "delka_svetla = sum(led_telo_dilu(c[", lambda r: r[:len(r) - len(r.lstrip())] + '''led_z_ = [float(c["pos"][2]) for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED]
        delka_svetla = (max(led_z_) - min(led_z_)) + led_telo_dilu(next(c["part_id"] for c in clenove.values() if c["druh"] == "prisl" and c["src"] == LED))          # ROZPETI skupiny svitidel (od nejlevejsiho kraje po nejpravejsi; u svitidel tesne vedle sebe soucet delek)''', "profil_led_kratky")

# 7) vstup z dotazu (staff API) -----------------------------------------------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, '_CISLA = ("sirka"', lambda r: r.replace('"led_delka", ', '"led_delka", "led_pocet", ', 1) if '"led_delka", ' in r else (_ for _ in ()).throw(AssertionError("_CISLA bez led_delka")), "_CISLA")
s = nahrad_radek(s, '_DESETINNA = ("suplik_posun"', lambda r: r + " + LED_PARAMETRY_Z", "_DESETINNA")
s = nahrad_radek(s, 'if (k == "stredni_noha" or k.startswith("police_h")', lambda r: r.replace('or k == "hpolice_vyska")', 'or k == "hpolice_vyska" or k.startswith("led_z"))', 1) if 'or k == "hpolice_vyska")' in r else (_ for _ in ()).throw(AssertionError("None u hpolice_vyska")), "None v dotazu")

# 8) 3D ovladani: nabidka pridat, skupiny a tahy jednotlivych svitidel -------------------------------------------------------------------------------------------------------------------------
s = nahrad_radek(s, 'led_ids = skupina("led", "LED osvětlení"', lambda r: '''    li_led = r.get("led_info") or {}
    if p["led"] and p["stojky"] and p["led_svetlo"] and li_led.get("polohy"):
        pr_led = li_led.get("pridat")                                                              # Robert 2026-10-08: svitidla se pridavaji RUCNE (vychozi 1) a posouvaji se podel profilu
        menu_led_delky.append(pol("Přidat svítidlo LED", pr_led, None if pr_led else "Další svítidlo LED se sem nevejde (jejich délky dohromady by přesáhly šířku stolu)."))
''' + r, "menu led pridat")
s = nahrad(s, '''    if p["vzpery"]:
        dl_v = p["vzpera_delka"]
''', '''    if led_ids and li_led.get("polohy") and p["led"] and p["stojky"] and p["led_svetlo"]:                 # kazde svitidlo zvlast: nabidka (odebrat / vratit na vychozi misto) a tah podel profilu (osa Z)
        n_led_ = len(li_led["polohy"])
        pol_led = [float(x) for x in li_led["polohy"]]
        tel_led = float(li_led.get("telo") or LED_SIRKA)
        pul_led = (float(li_led["okraj"][1]) - float(li_led["okraj"][0])) / 2.0                     # polovina vnejsi sirky stolu (profil nad LED)
        for k_led in range(n_led_):
            klic_led = ("t", LED) if k_led == 0 else ("led", k_led)
            ids_led = idx(lambda kk, rl, d, kl=klic_led: kk == kl)
            if not ids_led:
                continue
            popis_led = f"Svítidlo LED {k_led + 1}" if n_led_ > 1 else "Svítidlo LED"
            odeb_led = (li_led.get("odebrat") or [None] * n_led_)[k_led] if n_led_ > 1 else {"led_svetlo": False}
            je_auto_led = abs(pol_led[k_led] - float((li_led.get("auto") or pol_led)[k_led])) < 0.05
            skupina(f"led_{k_led + 1}", popis_led, lambda kk, rl, d, kl=klic_led: kk == kl, ["led_pocet", f"led_z{k_led + 1}"],
                    [pol("Odebrat toto svítidlo", odeb_led), pol("Vrátit svítidlo na výchozí místo", {f"led_z{k_led + 1}": None}, "Už je na výchozím místě." if je_auto_led else None)], priorita=3)
            lo_led, hi_led = li_led["meze"][k_led]
            if float(hi_led) - float(lo_led) >= 0.5:
                alo_led, ahi_led = aabb(ids_led)
                mer_led = [{"label": "od levého okraje stolu", "param": f"led_z{k_led + 1}", "mul": 1.0, "add": round(pul_led - tel_led / 2.0, 1)},
                           {"label": "od pravého okraje stolu", "param": f"led_z{k_led + 1}", "mul": -1.0, "add": round(pul_led - tel_led / 2.0, 1)}]
                if k_led > 0:
                    mer_led.append({"label": "od levého svítidla", "param": f"led_z{k_led + 1}", "mul": 1.0, "add": round(-(pol_led[k_led - 1] + tel_led), 1)})
                if k_led < n_led_ - 1:
                    mer_led.append({"label": "od pravého svítidla", "param": f"led_z{k_led + 1}", "mul": -1.0, "add": round(pol_led[k_led + 1] - tel_led, 1)})
                tahy.append({"id": f"led_z{k_led + 1}", "label": f"Posun svítidla LED {k_led + 1}" if n_led_ > 1 else "Posun svítidla LED", "typ": "osa", "ikona": "sipka_z",
                             "bod": [round((alo_led[0] + ahi_led[0]) / 2, 1), round(alo_led[1], 1), round((alo_led[2] + ahi_led[2]) / 2, 1)], "osa": [0.0, 0.0, 1.0], "param": f"led_z{k_led + 1}",
                             "faktor": 1.0, "hodnota": round(pol_led[k_led], 1), "min": float(lo_led), "max": float(hi_led), "krok": 1.0, "casti": [f"led_{k_led + 1}"], "mereni": mer_led})
    if p["vzpery"]:
        dl_v = p["vzpera_delka"]
''', "led skupiny")

# 9) zive tazeni: svitidlo jede samo podel profilu (osa Z), nic jineho se nehybe -> PRESNA operace "posun" (vycentrovani GLB klient nedela, jako u ramene LED) --------------------------------------------
s = nahrad(s, '''    def dej(tid, ops):
        t = next((x for x in tahy if x["id"] == tid), None)
        ops = [o for o in ops if o]
        if t is not None and ops:
            t["zive"] = ops
''', '''    def dej(tid, ops):
        t = next((x for x in tahy if x["id"] == tid), None)
        ops = [o for o in ops if o]
        if t is not None and ops:
            t["zive"] = ops

    for k_led in range(1, LED_MAX + 1):                                   # svitidla LED (Robert 2026-10-08): svitidlo cislo k jede samo podel profilu (osa Z); jeho poloha je primo parametr led_z<k>, ostatni dily stoji
        i_led = ind_klic.get(("t", LED) if k_led == 1 else ("led", k_led - 1))
        if i_led is not None:
            dej(f"led_z{k_led}", [op_posun([i_led], 1.0)])
''', "zive led")

open(dst, "w", encoding="utf-8").write(s)
print("OK (kompletni) ->", dst)
