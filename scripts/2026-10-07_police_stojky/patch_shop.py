"""Zaplata api/stul_shop.py pro horni polici mezi zadnimi stojkami (sloty upshelf*, texty cs / en / sk, normalizace, kod konfigurace, volby, shrnuti, nabidka karet pro verejnost).
Kotvene nahrady (viz apply_patches.nahrad): kazda kotva musi byt v souboru PRAVE JEDNOU."""


def patch_shop(s, nahrad, vloz_pred_radek):
    s = nahrad(s, "import stul_konfigurator as S\nimport stul_ovladani_verejne\n",
               "import stul_hpolice as HP                                    # horni police mezi zadnimi stojkami (Robert 2026-10-07)\nimport stul_konfigurator as S\nimport stul_ovladani_verejne\n", "shop import")

    # ---- nabidka karet police (pravidlo 54) ----
    s = vloz_pred_radek(s, "# id slotu -> parametr generatoru (neprusvitne ID pro UI; stabilni)", '''# KARTY HORNI POLICE V NABIDCE (Robert 2026-10-07; pravidlo 54 - kartu aktivuje jen Robert): VEREJNOST dostane jen desky, typy a dily, jejichz karta je AKTIVNI a neni archivovana (laminodeska 12 mm
# vznika jako neaktivni karta s orientacni cenou, takze je venku, az ji Robert potvrdi a aktivuje); ZAMESTNANEC (platna session) a kod mimo pozadavek (testy, skripty) vidi vsechno.
_KARTY_POLICE_CACHE = {"t": 0.0, "set": frozenset({"product_4933"})}


def karty_police_verejne():
    """Mnozina part_id karet horni police, ktere smi dostat verejnost (aktivni, neni archivovana); cache DELKY_TTL_S, chyba cteni DB = jen laminodeska 18 mm (stul nikdy nesmi spadnout kvuli volitelne polici)."""
    ted = time.time()
    if ted - _KARTY_POLICE_CACHE["t"] > DELKY_TTL_S:
        mnozina = {"product_4933"}
        try:
            ids = sorted({int(pid.split("_", 1)[1]) for pid in HP.vsechny_party()})
            cur = get_conn().cursor()
            cur.execute("SELECT id, active, is_archived FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(ids)) + ")", tuple(ids))
            for r in cur.fetchall():
                if r["active"] and not r["is_archived"]:
                    mnozina.add(f"product_{r['id']}")
        except Exception as e:                                       # noqa: BLE001 - nikdy nesmi shodit verejny resolve
            app.logger.warning("stul_shop: nacteni aktivnich karet horni police selhalo (nabidnuta jen laminodeska 18 mm): %s", e)
        _KARTY_POLICE_CACHE.update(t=ted, set=frozenset(mnozina))
    return _KARTY_POLICE_CACHE["set"]


def nabidka_police(system, karty="pozadavek"):
    """(desky, typy) horni police v nabidce pro `system`: `karty` = "pozadavek" (zamestnanec / kod mimo pozadavek vsechno, verejnost jen karty z karty_police_verejne), nebo mnozina part_id (testy)."""
    if isinstance(karty, str):
        karty = None if (not has_request_context() or _je_staff()) else karty_police_verejne()
    return HP.nabidka(system, karty)


def _cele_nebo_none(v):
    """Vyska police do echa vyberu: None = automaticka, cele cislo jako int (640, ne 640.0), jinak desetinne."""
    return None if v is None else (int(v) if float(v).is_integer() else round(float(v), 1))


def _upshelf_typ(v, nab):
    """Verejna volba typu police -> typ generatoru; neznamy nebo nenabizeny typ = vychozi (rovna), nebo prvni nabizeny."""
    t = HP.TYP_ID.get(v) if isinstance(v, str) else None                                        # (vstup od klienta: seznam / slovnik nesmi spadnout na hash)
    return t if t in nab[1] else (HP.TYP_VYCHOZI if HP.TYP_VYCHOZI in nab[1] else nab[1][0])


def _upshelf_deska(v, system, typ, nab):
    """Verejna volba desky police -> id desky generatoru: neznama / pro typ a system nepouzitelna / nenabizena deska = prvni pouzitelna (ramova police bez desky: vychozi laminodeska 18 mm)."""
    pouz = [d for d in HP.nabidka_desek(system, typ) if d in nab[0]]
    if typ == "ram" or not pouz:
        return HP.DESKA_VYCHOZI
    return v if v in pouz else pouz[0]


''', "shop nabidka police")

    s = nahrad(s, '"feet": "patky", "braces": "vzpery"', '"feet": "patky", "braces": "vzpery", "upshelf": "hpolice"', "shop PREPINACE")                      # (kotva bez ohledu na dalsi polozky mapy: shelfboard, ...)
    s = nahrad(s, '                 "braces": False, "bracelen": 300}\n',
               '                 "braces": False, "bracelen": 300,\n'
               '                 "upshelf": False, "upshelftype": "flat", "upshelfboard": "lam18", "upshelfpos": None, "upshelfdepth": int(HP.HLOUBKA_VYCHOZI)}      # horni police mezi zadnimi stojkami (pos None = automaticky)\n',
               "shop VYCHOZI_VYBER")

    # ---- texty cs / en / sk (pred _spocti, po vsech slovnicich) ----
    s = vloz_pred_radek(s, "def _spocti(p, norm, lang, h, gen, delky=None):", '''# HORNI POLICE MEZI ZADNIMI STOJKAMI (Robert 2026-10-07; api/stul_hpolice.py): texty cs / en / sk (dalsi jazyky z api/jazyky; chybejici klic = anglicky)
TEXTY["cs"].update({
    "upshelf": "Police mezi zadními stojkami", "upshelftype": "Typ police", "upshelfboard": "Deska police", "upshelfpos": "Výška police nad deskou stolu", "upshelfdepth": "Hloubka police",
    "upshelftype_flat": "Rovná, deska na rámu", "upshelftype_frame": "Rámová, bez desky", "upshelftype_groove": "Rám s deskou v drážce", "upshelftype_lip": "S lemem na přední hraně",
    "upshelftype_dividers": "Rám s přepážkami z překližky",
    "upshelfboard_lam18": "Laminodeska 18 mm", "upshelfboard_lam12": "Laminodeska 12 mm", "upshelfboard_mdf8": "MDF 8 mm (do drážky)", "upshelfboard_pr10": "Překližka 10 mm (do drážky)",
    "help_upshelf": "Police se montuje mezi zadní stojky: rám z profilů (zadní a přední příčka, boční profily a u širších polic střední) a deska shora na rámu, nebo v drážce profilů. Rám s přepážkami má "
                    "podlahu v drážce a svislé přepážky z překližky 10 mm na úhelnících; lem je pás z překližky na přední hraně. Výchozí výška je nad panely."})
TEXTY["en"].update({
    "upshelf": "Shelf between the rear uprights", "upshelftype": "Shelf type", "upshelfboard": "Shelf board", "upshelfpos": "Shelf height above the worktop", "upshelfdepth": "Shelf depth",
    "upshelftype_flat": "Flat, board on the frame", "upshelftype_frame": "Frame only, no board", "upshelftype_groove": "Frame with a board in the slot", "upshelftype_lip": "With a lip on the front edge",
    "upshelftype_dividers": "Frame with plywood dividers",
    "upshelfboard_lam18": "Laminated chipboard 18 mm", "upshelfboard_lam12": "Laminated chipboard 12 mm", "upshelfboard_mdf8": "MDF 8 mm (in the slot)", "upshelfboard_pr10": "Plywood 10 mm (in the slot)",
    "help_upshelf": "The shelf is mounted between the rear uprights: a frame of profiles (rear and front cross-member, side profiles and, for wider shelves, centre profiles) and a board on top of the frame "
                    "or in the slot of the profiles. The frame with dividers has the floor in the slot and vertical 10 mm plywood dividers on angle brackets; the lip is a plywood strip on the front edge. "
                    "The default height is above the panels."})
TEXTY["sk"].update({
    "upshelf": "Polica medzi zadnými stojkami", "upshelftype": "Typ police", "upshelfboard": "Doska police", "upshelfpos": "Výška police nad doskou stola", "upshelfdepth": "Hĺbka police",
    "upshelftype_flat": "Rovná, doska na ráme", "upshelftype_frame": "Rámová, bez dosky", "upshelftype_groove": "Rám s doskou v drážke", "upshelftype_lip": "S lemom na prednej hrane",
    "upshelftype_dividers": "Rám s priehradkami z preglejky",
    "upshelfboard_lam18": "Laminovaná drevotrieska 18 mm", "upshelfboard_lam12": "Laminovaná drevotrieska 12 mm", "upshelfboard_mdf8": "MDF 8 mm (do drážky)", "upshelfboard_pr10": "Preglejka 10 mm (do drážky)",
    "help_upshelf": "Polica sa montuje medzi zadné stojky: rám z profilov (zadná a predná priečka, bočné profily a pri širších policiach stredné) a doska zhora na ráme, alebo v drážke profilov. Rám "
                    "s priehradkami má podlahu v drážke a zvislé priehradky z preglejky 10 mm na uholníkoch; lem je pás z preglejky na prednej hrane. Predvolená výška je nad panelmi."})
DUVODY["cs"].update({"upshelf": "Police mezi zadními stojkami se sem nevejde – potřebuje zadní stojky a místo mezi panely (nebo deskou) a ramenem LED; zvyšte stojky, snižte počet panelů, nebo ji vypněte.",
                     "upshelf_deska_ram": "Rámová police nemá desku.", "upshelf_deska_drazka": "Do drážky jde jen deska {d}.", "upshelf_deska_shora": "Deska do drážky jde jen u rámu s deskou v drážce a s přepážkami.",
                     "upshelf_deska_nabidka": "Tahle deska teď není v nabídce.", "upshelf_typ_nabidka": "Tahle varianta police teď není v nabídce.",
                     "upshelf_typ_nevejde": "Tenhle typ police se sem nevejde – nad rámem potřebuje víc volného místa (zvyšte zadní stojky nebo snižte počet panelů)."})
DUVODY["en"].update({"upshelf": "The shelf between the rear uprights does not fit here – it needs the rear uprights and space between the panels (or the worktop) and the LED arm; raise the uprights, reduce the panels or switch it off.",
                     "upshelf_deska_ram": "A frame-only shelf has no board.", "upshelf_deska_drazka": "Only the {d} board goes into the slot.", "upshelf_deska_shora": "A board in the slot is only for the frame with a board in the slot and the frame with dividers.",
                     "upshelf_deska_nabidka": "This board is not available at the moment.", "upshelf_typ_nabidka": "This shelf variant is not available at the moment.",
                     "upshelf_typ_nevejde": "This shelf type does not fit here – it needs more free room above the frame (raise the rear uprights or reduce the panels)."})
DUVODY["sk"].update({"upshelf": "Polica medzi zadnými stojkami sa sem nezmestí – potrebuje zadné stojky a miesto medzi panelmi (alebo doskou) a ramenom LED; zvýšte stojky, znížte počet panelov, alebo ju vypnite.",
                     "upshelf_deska_ram": "Rámová polica nemá dosku.", "upshelf_deska_drazka": "Do drážky ide len doska {d}.", "upshelf_deska_shora": "Doska do drážky ide len pri ráme s doskou v drážke a s priehradkami.",
                     "upshelf_deska_nabidka": "Táto doska teraz nie je v ponuke.", "upshelf_typ_nabidka": "Táto varianta police teraz nie je v ponuke.",
                     "upshelf_typ_nevejde": "Tento typ police sa sem nezmestí – nad rámom potrebuje viac voľného miesta (zvýšte zadné stojky alebo znížte počet panelov)."})
VOLBA_NA_SLOT["hpolice"] = "upshelf"
NAZVY_SLOTU["cs"]["upshelf"], NAZVY_SLOTU["en"]["upshelf"], NAZVY_SLOTU["sk"]["upshelf"] = "polici mezi zadními stojkami", "the shelf between the rear uprights", "policu medzi zadnými stojkami"
UPSHELF_NAZVY_DESEK = {"lam18": "laminodeska 18 mm", "lam12": "laminodeska 12 mm", "mdf8": "MDF 8 mm", "pr10": "překližka 10 mm"}


''', "shop texty")

    # ---- schema: sloty, zavislosti, volby podle systemu a nabidky ----
    s = nahrad(s, '            toggle("braces", "g_extras"), slider("bracelen", "g_extras", S.ROZSAH["vzpera_delka"][0], S.ROZSAH["vzpera_delka"][1], 10, "mm", t["help_braces"]),\n',
               '            toggle("braces", "g_extras"), slider("bracelen", "g_extras", S.ROZSAH["vzpera_delka"][0], S.ROZSAH["vzpera_delka"][1], 10, "mm", t["help_braces"]),\n'
               '            toggle("upshelf", "g_extras"), select("upshelftype", "g_extras", HP.TYP_IDS, t["help_upshelf"]), select("upshelfboard", "g_extras", HP.DESKY_IDS),\n'
               '            slider("upshelfpos", "g_extras", int(HP.VYSKA_MIN), int(HP.VYSKA_MAX), 10, "mm"), slider("upshelfdepth", "g_extras", int(HP.HLOUBKA_MIN), int(HP.HLOUBKA_MAX), 10, "mm"),\n',
               "shop schema sloty")
    s = nahrad(s, '    z["sleevelen"] = ["sleeve"]                                      # delka navleku existuje jen se zapnutym navlekem\n',
               '    z["sleevelen"] = ["sleeve"]                                      # delka navleku existuje jen se zapnutym navlekem\n'
               '    z.update({k_: ["posts", "upshelf"] for k_ in ("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth")})        # horni police: volby existuji jen se zapnutou policí (a stojkami)\n',
               "shop zavisi_na")
    s = nahrad(s, '''    for sl in out["slots"]:
        if sl["id"] == "panellen":
            sl["options"] = [o for o in sl["options"] if int(o["id"]) in delky_]''', '''    nab_hp = nabidka_police(system)                              # horni police: desky a typy v nabidce (system; verejnost jen aktivni karty)
    for sl in out["slots"]:
        if sl["id"] == "upshelfboard":
            sl["options"] = [o for o in sl["options"] if o["id"] in nab_hp[0]]
        if sl["id"] == "upshelftype":
            sl["options"] = [o for o in sl["options"] if HP.TYP_ID[o["id"]] in nab_hp[1]]
        if sl["id"] == "panellen":
            sl["options"] = [o for o in sl["options"] if int(o["id"]) in delky_]''', "shop schema nabidka")

    # ---- normalizace ----
    s = nahrad(s, "def normalizuj(selection, system=30, delky=None):", "def normalizuj(selection, system=30, delky=None, nab_hp=None):", "shop normalizuj sig")
    s = vloz_pred_radek(s, '    p["stredni_opora"] = MIDSUPPORT_ID.get(sel.get("midsupport"), "auto")', '''    nab_hp = nabidka_police(system) if nab_hp is None else nab_hp                                                       # desky a typy horni police v nabidce (verejnost jen aktivni karty)
    p["hpolice_typ"] = _upshelf_typ(sel.get("upshelftype"), nab_hp) if p["hpolice"] else HP.TYP_VYCHOZI                  # horni police: typ, deska podle typu a systemu, vyska (None = automaticky), hloubka
    p["hpolice_deska"] = _upshelf_deska(sel.get("upshelfboard"), system, p["hpolice_typ"], nab_hp) if p["hpolice"] else HP.DESKA_VYCHOZI
    p["hpolice_vyska"] = (None if sel.get("upshelfpos") in (None, "") else round(_cislo(sel["upshelfpos"], HP.VYSKA_MIN, HP.VYSKA_MAX, HP.VYSKA_MIN), 1)) if p["hpolice"] else None
    p["hpolice_hloubka"] = _cislo(sel["upshelfdepth"], HP.HLOUBKA_MIN, HP.HLOUBKA_MAX, HP.HLOUBKA_VYCHOZI, 10) if p["hpolice"] else float(HP.HLOUBKA_VYCHOZI)
''', "shop normalizuj hpolice")
    s = nahrad(s, '''    norm["posth"], norm["socketup"], norm["socketside"] = round(float(p["stojky_vyska"]), 1), int(p["elzlab_y"]), int(p["elzlab_z"])
    return p, norm
''', '''    norm["posth"], norm["socketup"], norm["socketside"] = round(float(p["stojky_vyska"]), 1), int(p["elzlab_y"]), int(p["elzlab_z"])
    norm["upshelftype"], norm["upshelfboard"] = HP.TYP_VEREJNE[p["hpolice_typ"]], p["hpolice_deska"]
    norm["upshelfpos"], norm["upshelfdepth"] = _cele_nebo_none(p["hpolice_vyska"]), int(round(p["hpolice_hloubka"]))
    return p, norm
''', "shop normalizuj norm")

    # ---- kod konfigurace (token) ----
    s = nahrad(s, '"vzpery", "navlek"]      # bit 0 drive police', '"vzpery", "navlek", "hpolice"]      # bit 10 horni police mezi zadnimi stojkami; bit 0 drive police', "shop _BITY")
    s = nahrad(s, '''    if p.get("navlek"):
        out["a"] = int(round(float(p["navlek_delka"])))''', '''    if p.get("hpolice") and p.get("stojky", True):
        out["R"] = [p["hpolice_typ"], p["hpolice_deska"], None if p.get("hpolice_vyska") is None else round(float(p["hpolice_vyska"]), 1), round(float(p["hpolice_hloubka"]), 1)]      # horni police: typ, deska, vyska (None = auto), hloubka; zapnuti nese bit "hpolice" v "t"; klic R (K je delka LED)
    if p.get("navlek"):
        out["a"] = int(round(float(p["navlek_delka"])))''', "shop _zabal")
    s = nahrad(s, '''    if o.get("a"):
        p["navlek_delka"] = float(o["a"])''', '''    if o.get("a"):
        p["navlek_delka"] = float(o["a"])
    if o.get("R"):                                                           # (klic "K" patri delce svitidla LED - vetev led600)
        p["hpolice_typ"], p["hpolice_deska"] = str(o["R"][0]), str(o["R"][1])
        p["hpolice_vyska"] = None if o["R"][2] is None else float(o["R"][2])
        p["hpolice_hloubka"] = float(o["R"][3])''', "shop _rozbal")

    # ---- priradeni chyb ke slotum ----
    s = nahrad(s, '''    if problem.get("kod") == "panel_nevejde":
        return "panels"
''', '''    if problem.get("kod") == "panel_nevejde":
        return "panels"
    if problem.get("kod") == "hpolice_nevejde":
        return "upshelf"
''', "shop slot_pro_problem kod")
    s = nahrad(s, '''    for i in problem.get("dily") or []:
        if 0 <= i < len(dily) and dily[i]["part_id"] in DIL_NA_SLOT:''', '''    for i in problem.get("dily") or []:
        kl_ = gen["klice"][i] if (gen and 0 <= i < len(gen["klice"])) else None
        if isinstance(kl_, (list, tuple)) and kl_ and kl_[0] == "hpol":
            return "upshelf"                                    # dily horni police: chyba patri k jejimu slotu
    for i in problem.get("dily") or []:
        if 0 <= i < len(dily) and dily[i]["part_id"] in DIL_NA_SLOT:''', "shop slot_pro_problem klic")

    # ---- odkaz na vyrobni list (staff blok): parametry police jen u zapnute police (odkazy stolu bez police zustavaji beze zmeny) ----
    s = nahrad(s, 'and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI)', 'and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI) '
               'and not (k.startswith("hpolice") and k != "hpolice" and not p.get("hpolice")) and not (k == "hpolice" and not v)', "shop staff blok police")

    # ---- resolve: nabidka v klici cache ----
    s = nahrad(s, '''    delky = delky_pro_pozadavek()                                # delky panelu v nabidce tohoto pozadavku (verejnost jen s aktivni kartou)
    p, norm = normalizuj(selection, system, delky)''', '''    delky = delky_pro_pozadavek()                                # delky panelu v nabidce tohoto pozadavku (verejnost jen s aktivni kartou)
    nab_hp = nabidka_police(system)                              # desky a typy horni police v nabidce tohoto pozadavku (totez)
    p, norm = normalizuj(selection, system, delky, nab_hp)''', "shop resolve normalizuj")
    s = nahrad(s, 'norm.get("panellen"), tuple(sorted(delky))', 'norm.get("panellen"), tuple(sorted(delky)), nab_hp', "shop resolve klic")
    s = nahrad(s, "        r = _spocti(p, norm, lang, h, gen, delky)\n", "        r = _spocti(p, norm, lang, h, gen, delky, nab_hp)\n", "shop resolve spocti")

    # ---- shrnuti voleb ----
    s = nahrad(s, '''    if not sel["braces"]:
        skryt.add("bracelen")
    out = []''', '''    if not sel["braces"]:
        skryt.add("bracelen")
    if not (sel.get("upshelf") and sel["posts"]):                  # horni police: volby se ve shrnuti ukazi jen se zapnutou policí; automaticka vyska ani deska ramove police se neuvadi
        skryt.update(("upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth"))
    else:
        if sel.get("upshelfpos") is None:
            skryt.add("upshelfpos")
        if sel.get("upshelftype") == "frame":
            skryt.add("upshelfboard")
    out = []''', "shop souhrn")

    # ---- _spocti ----
    s = nahrad(s, "def _spocti(p, norm, lang, h, gen, delky=None):\n    delky = frozenset(S.PANEL_DELKY) if delky is None else delky",
               "def _spocti(p, norm, lang, h, gen, delky=None, nab_hp=None):\n"
               "    nab_hp = HP.nabidka(p[\"system\"], None) if nab_hp is None else nab_hp                     # desky a typy horni police v nabidce (verejnost jen s aktivni kartou)\n"
               "    delky = frozenset(S.PANEL_DELKY) if delky is None else delky", "shop _spocti sig")
    s = nahrad(s, '''    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    cur = cena["bez_dph"] if cena else None
    errors = []''', '''    hp_inf = gen.get("hpolice_info")                                                                              # efektivni horni police (typ, deska, vyska, hloubka po orezu na meze)
    norm["upshelftype"], norm["upshelfboard"] = HP.TYP_VEREJNE[p["hpolice_typ"]], p["hpolice_deska"]
    norm["upshelfpos"] = _cele_nebo_none(p["hpolice_vyska"]) if p["hpolice"] else None
    norm["upshelfdepth"] = int(round(p["hpolice_hloubka"]))
    cena = stul_api.cena_konfigurace(gen["dily"], p["system"])
    cur = cena["bez_dph"] if cena else None
    errors = []''', "shop _spocti norm")
    s = nahrad(s, '(POTREBUJE_STOJKY[lang] if (par in ("panely", "led", "elektrozlab") and not p["stojky"])', '(POTREBUJE_STOJKY[lang] if (par in ("panely", "led", "elektrozlab", "hpolice") and not p["stojky"])', "shop _spocti stojky")
    s = vloz_pred_radek(s, "    vat = float(stul_api.SAZBA_DPH)", '''    # horni police: vyska (posuvnik po 10 mm; automaticky = hodnota z generatoru), hloubka, typy a desky (zakazane, co se nevejde / nepatri k typu a systemu / neni v nabidce)
    if p["hpolice"] and p["stojky"] and hp_inf and not hp_inf.get("problem"):
        hv, hh = hp_inf["vyska"], hp_inf["hloubka"]
        options["upshelfpos"] = {"min": int(math.ceil(hv["min"] / 10.0)) * 10, "max": int(math.floor(hv["max"] / 10.0)) * 10, "value": round(float(hv["hodnota"]), 1), "auto": bool(hv["auto"]), "fits": True}
        options["upshelfdepth"] = {"min": int(hh["min"]), "max": int(math.floor(hh["max"] / 10.0)) * 10, "value": int(round(hh["hodnota"]))}
    else:
        options["upshelfpos"] = {"min": 0, "max": 0}
        options["upshelfdepth"] = {"min": 0, "max": 0}
    dz = DUVODY[lang]
    options["upshelftype"] = {HP.TYP_VEREJNE[t_]: {"disabled": True, "reason": dz["upshelf_typ_nabidka"]} for t_ in HP.TYPY if t_ not in nab_hp[1]}           # typy mimo nabidku (verejnost: neaktivni karta)
    if p["hpolice"] and p["stojky"] and hp_inf:                                                                     # typy, na ktere neni nad ramem dost mista (aktualni zustava volitelny)
        options["upshelftype"].update({HP.TYP_VEREJNE[x_["typ"]]: {"disabled": True, "reason": dz["upshelf_typ_nevejde"]}
                                       for x_ in hp_inf["typy"] if not x_["vejde"] and x_["typ"] != p["hpolice_typ"] and x_["typ"] in nab_hp[1]})
    options["upshelfboard"] = {}
    for d_ in HP.DESKY_SYSTEMU[p["system"]]:
        if p["hpolice_typ"] == "ram":
            duv = dz["upshelf_deska_ram"]
        elif HP.potrebuje_drazku(p["hpolice_typ"]) and d_ != HP.DRAZKA_DESKA[p["system"]]:
            duv = dz["upshelf_deska_drazka"].format(d=UPSHELF_NAZVY_DESEK[HP.DRAZKA_DESKA[p["system"]]])
        elif not HP.potrebuje_drazku(p["hpolice_typ"]) and HP.DESKY[d_]["drazka"]:
            duv = dz["upshelf_deska_shora"]
        elif d_ not in nab_hp[0]:
            duv = dz["upshelf_deska_nabidka"]
        else:
            duv = None
        if duv:
            options["upshelfboard"][d_] = {"disabled": True, "reason": duv}
''', "shop _spocti options")
    return s
