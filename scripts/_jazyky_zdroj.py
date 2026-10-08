"""Spolecny kod nastroju jazykovych sad mini-shopu (bot16, 2026-10-07): scripts/miniweb_jazyk_zdroj.py, miniweb_jazyk_sestav.py, miniweb_jazyk_parita.py.

  * zdrojove retezce serveru (cs / en / sk) se tahaji z KODU introspekci modulu (stul_shop, stul_shop_sse, stul_ovladani_verejne, miniweb_objednavky, miniweb) - jedina pravda je kod;
  * `polozky_z_kodu()` vraci seznam polozek {id, sekce, typ, cs, en, sk, placeholdery}; typ "plural" = sablona s tvary (one / few / many / other), hodnoty jsou objekty kategorii;
  * `sestav_sadu()` obraci identifikatory zpet na strukturu api/jazyky/<jazyk>.json;
  * informacni vety s gramatikou (podpery, podpery_desky, desky_deleny) se rozkladaji na SABLONY tak, ze se skutecne funkce modulu zavolaji se zastupnymi cisly a cisla se v
    vysledku nahradi placeholdery - sablona ze zdroje tedy vzdy presne odpovida kodu (hlida test_jazyky.py).
"""
import atexit
import json
import os
import re
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(REPO, "api")
DOCS = os.path.join(REPO, "docs", "jazyky")

SOUBORY_SEKCI = {                                    # sekce -> nazev souboru ve slozce docs/jazyky/<jazyk>/
    "stul_texty": "01_stul_texty.json",
    "stul_zpravy": "02_stul_zpravy.json",
    "stul_info": "03_stul_info_sablony.json",
    "ovladani": "04_ovladani.json",
    "objednavky": "05_objednavky.json",
}
POPIS_SEKCI = {
    "stul_texty": "Štítky a nápověda voleb konfigurátoru stolu (schéma voleb, to co zákazník vidí u posuvníků a přepínačů) + texty SSE stolu.",
    "stul_zpravy": "Hlášky konfigurátoru stolu: důvody, proč volba nejde, upozornění, nabídky „Odebrat …“, názvy dílů ve větách, ano/ne v souhrnu voleb.",
    "stul_info": "Informační věty s počtem kusů (podpěrné profily, dělení desky). Jsou to ŠABLONY: vyplň tvary podle počtu (one = 1 kus, other = jinak; u jazyků s víc tvary i few/many). "
                 "Začátek šablony s mezerou nebo středníkem (navazuje na `zaklad`) je záměrný - zachovej ho.",
    "ovladani": "Popisky ovládání ve 3D náhledu (tahy myší: „Výška desky“, „Přidat výřez sem“, „Odebrat šuplíky“ …). Klíč je česká šablona; {n} = číslo výřezu nebo police.",
    "objednavky": "Štítky dopravy v košíku mini-shopu a (volitelně) šablona potvrzení poptávky.",
}


def najdi_env():
    """Cesta k api/.env: v teto kopii repa, jinak v zivem repu (izolovana kopie / worktree .env nema)."""
    for cesta in (os.path.join(REPO, "api", ".env"), "/opt/konfigurator/api/.env"):
        if os.path.exists(cesta):
            return cesta
    return None


def nacti_env():
    """Nacte api/.env do os.environ (setdefault) - import aplikace potrebuje DB prihlaseni; nic se nevypisuje."""
    cesta = najdi_env()
    if cesta:
        for line in open(cesta, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def importuj_api(api_dir=None):
    """Import aplikace z dane kopie API (vychozi zive repo): vraci slovnik modulu. Soubory se zapisuji do docasnych adresaru (PRIVATE_FILES_DIR, CONTENT_UPLOAD_DIR).
    POZOR: `import app` spousti vlakno render-dozorce (api/render_worker.py), ktere po 60 s kontroluje ZIVOU frontu renderu; proces, ktery ziji dele, by mohl prebrat cizi ulohu.
    Proto se obe cesty VZDY prepisuji na docasny adresar (ne setdefault), i kdyz je nekdo nastavi v prostredi."""
    api_dir = os.path.abspath(api_dir or API)
    nacti_env()
    tmp = tempfile.mkdtemp(prefix="jazyky_")
    atexit.register(shutil.rmtree, tmp, True)
    os.environ["PRIVATE_FILES_DIR"] = os.path.join(tmp, "private")
    os.environ["CONTENT_UPLOAD_DIR"] = os.path.join(tmp, "content")
    for d in (os.environ["PRIVATE_FILES_DIR"], os.environ["CONTENT_UPLOAD_DIR"]):
        os.makedirs(d, exist_ok=True)
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    import app  # noqa: F401
    import jazyky
    import miniweb
    import miniweb_objednavky
    import stul_ovladani_verejne
    import stul_shop
    import stul_shop_sse
    return {"jazyky": jazyky, "miniweb": miniweb, "miniweb_objednavky": miniweb_objednavky, "stul_ovladani_verejne": stul_ovladani_verejne, "stul_shop": stul_shop, "stul_shop_sse": stul_shop_sse}


def jazyky_modul(api_dir=None):
    """Jen lehky modul api/jazyky.py (bez importu aplikace) - pro sestav a cast parity."""
    api_dir = os.path.abspath(api_dir or API)
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    import jazyky
    return jazyky


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# rozklad informacnich vet na sablony
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
_H, _K, _M = 90001, 90002, 90003                     # zastupna cisla (v textu se nahradi placeholdery)
_N_PRO_KATEGORII = {"one": 1, "few": 2, "many": 5, "other": 5}


def _nahrad_cisla(text, n, ph_n="{n}"):
    text = re.sub(rf"(?<![0-9]){_H}(?![0-9])", "{h}", text)
    text = re.sub(rf"(?<![0-9]){_K}(?![0-9])", "{k}", text)
    text = re.sub(rf"(?<![0-9]){_M}(?![0-9])", "{mezera}", text)
    if n:
        text = re.sub(rf"(?<![0-9]){n}(?![0-9])", ph_n, text)
    return text


def _spolecny_prefix(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[:i]


def sablony_info(SH, jazyky, lg):
    """Sablony informacnich vet pro vestaveny jazyk lg (cs / en / sk) odvozene z funkci modulu stul_shop. Vraci {nazev_sablony: str | {kategorie: str}} ve tvaru sady jazyka
    (klice: podpery.zaklad|s_u1|s_um|bez, podpery_desky.zaklad|konec|konec_suplik, desky_deleny.noha|ram|ram_navic). Kategorie plurálu podle pravidla jazyka lg."""
    pravidlo = jazyky.PLURAL_PRO_JAZYK[lg]
    kategorie = jazyky.KATEGORIE_PRO_PRAVIDLO[pravidlo]
    f_pod, f_deska, f_del = SH.text_podpery, SH.text_podpery_desky, SH.text_desky_deleny

    def pod(n, u):
        return f_pod(lg, {"kraceni_mm": _K, "podpery": n, "urovni": u, "hloubka_mm": _H})
    bez = pod(0, 1)
    prvni = pod(1, 1)
    zaklad = _spolecny_prefix(bez, prvni)
    assert bez.startswith(zaklad) and prvni.startswith(zaklad) and zaklad.endswith(")"), (lg, zaklad)
    out = {"podpery": {"zaklad": _nahrad_cisla(zaklad, 0), "bez": _nahrad_cisla(bez[len(zaklad):], 0), "s_u1": {}, "s_um": {}}}
    for kat in kategorie:
        n = _N_PRO_KATEGORII[kat]
        for klic, u in (("s_u1", 1), ("s_um", 2)):
            t = pod(n, u)
            assert t.startswith(zaklad), (lg, kat, t)
            out["podpery"][klic][kat] = _nahrad_cisla(t[len(zaklad):], n)
    out["podpery_desky"] = {"zaklad": {}}
    konce = set()
    for kat in kategorie:
        n = _N_PRO_KATEGORII[kat]
        bez_sup = f_deska(lg, {"podpery": n, "suplik": False, "hloubka_mm": _H})
        se_sup = f_deska(lg, {"podpery": n, "suplik": True, "hloubka_mm": _H})
        assert bez_sup.endswith(".") and se_sup.startswith(bez_sup[:-1]), (lg, kat)
        out["podpery_desky"]["zaklad"][kat] = _nahrad_cisla(bez_sup[:-1], n)
        konce.add(se_sup[len(bez_sup) - 1:])
    assert len(konce) == 1, (lg, konce)
    out["podpery_desky"]["konec"] = "."
    out["podpery_desky"]["konec_suplik"] = next(iter(konce))
    noha = f_del(lg, "noha", _M, (_H, _K))
    ram = f_del(lg, "ram", _M, (_H, _K))
    i = ram.find("mm).")
    assert i > 0, (lg, ram)
    out["desky_deleny"] = {"noha": noha, "ram": ram[:i + 4], "ram_navic": ram[i + 4:]}
    for k in ("noha", "ram", "ram_navic"):
        t = out["desky_deleny"][k]
        for cislo, ph in ((_H, "{t1}"), (_K, "{t2}"), (_M, "{mezera}")):
            t = re.sub(rf"(?<![0-9]){cislo}(?![0-9])", ph, t)
        out["desky_deleny"][k] = t
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# polozky z kodu
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def _pol(sekce, id_, cs, en, sk, typ="text", poznamka=None, volitelne=False):
    pol = {"id": id_, "sekce": sekce, "typ": typ, "cs": cs, "en": en, "sk": sk}
    if poznamka:
        pol["poznamka"] = poznamka
    if volitelne:
        pol["volitelne"] = True
    return pol


def polozky_z_kodu(mods):
    """Vsechny zdrojove retezce serveru jako seznam polozek (poradi = poradi v souborech sady). `mods` = importuj_api()."""
    SH, SSE, OV, MO, MW, jz = mods["stul_shop"], mods["stul_shop_sse"], mods["stul_ovladani_verejne"], mods["miniweb_objednavky"], mods["miniweb"], mods["jazyky"]
    out = []
    # --- 01 stitky voleb
    for k in SH.TEXTY["en"]:
        out.append(_pol("stul_texty", f"stul_shop.TEXTY.{k}", SH.TEXTY["cs"][k], SH.TEXTY["en"][k], SH.TEXTY["sk"].get(k, "")))
    for k in SSE.TEXTY["en"]:
        out.append(_pol("stul_texty", f"stul_shop_sse.TEXTY.{k}", SSE.TEXTY["cs"][k], SSE.TEXTY["en"][k], SSE.TEXTY["sk"].get(k, ""), poznamka="SSE stůl (ergonomický stůl s nohami SSE)"))
    # --- 02 hlasky
    for k in SH.DUVODY["en"]:
        kk = jz.VYCHOZI_KLIC if k is None else k
        out.append(_pol("stul_zpravy", f"stul_shop.DUVODY.{kk}", SH.DUVODY["cs"].get(k, ""), SH.DUVODY["en"][k], SH.DUVODY["sk"].get(k, ""),
                        poznamka="obecná věta, když pro volbu není konkrétní důvod" if k is None else "důvod, proč volbu nelze zapnout / proč se sama odebrala (slot = " + str(k) + ")"))
    for nazev in jz.slovniky_zprav(vars(SH)):
        d = getattr(SH, nazev)
        out.append(_pol("stul_zpravy", f"stul_shop.zpravy.{nazev}", d.get("cs", ""), d["en"], d.get("sk", ""), poznamka="hláška konfigurátoru"))
    for k in SH.NAZVY_SLOTU["en"]:
        out.append(_pol("stul_zpravy", f"stul_shop.NAZVY_SLOTU.{k}", SH.NAZVY_SLOTU["cs"][k], SH.NAZVY_SLOTU["en"][k], SH.NAZVY_SLOTU["sk"][k],
                        poznamka="název dílu ve větě („Automaticky odebráno: <název> - důvod“; v angličtině s členem the)"))
    for k in SH.TEXTY_AKCI["en"]:
        out.append(_pol("stul_zpravy", f"stul_shop.TEXTY_AKCI.{k}", SH.TEXTY_AKCI["cs"][k], SH.TEXTY_AKCI["en"][k], SH.TEXTY_AKCI["sk"][k], poznamka="text tlačítka / předpona nabídky"))
    out.append(_pol("stul_zpravy", "stul_shop_sse.DUVOD_SUPLIKY", SSE.DUVOD_SUPLIKY["cs"], SSE.DUVOD_SUPLIKY["en"], SSE.DUVOD_SUPLIKY["sk"], poznamka="SSE stůl"))
    out.append(_pol("stul_zpravy", "ano_ne.ano", "ano", "yes", "yes", poznamka="hodnota zapnutého přepínače v souhrnu voleb (slovenský kód dnes používá yes/no)"))
    out.append(_pol("stul_zpravy", "ano_ne.ne", "ne", "no", "no", poznamka="hodnota vypnutého přepínače v souhrnu voleb"))
    # --- 03 informacni sablony
    sab = {lg: sablony_info(SH, jz, lg) for lg in ("cs", "en", "sk")}
    popis = {"podpery.zaklad": "úvod věty: zkrácení desky spodní police; {h} = hloubka stolu v mm, {k} = zkrácení z každé strany v mm",
             "podpery.s_u1": "pokračování, když je jedna police: {n} = počet podpěrných profilů",
             "podpery.s_um": "pokračování, když je polic víc („pod každou polici“): {n} = počet podpěrných profilů",
             "podpery.bez": "pokračování, když žádné podpěry nejsou potřeba",
             "podpery_desky.zaklad": "věta o podpěrách pod pracovní deskou: {h} = hloubka stolu, {n} = počet podpěrných profilů (bez tečky na konci)",
             "podpery_desky.konec": "konec věty bez šuplíků",
             "podpery_desky.konec_suplik": "konec věty, když desku podpírají i příčky šuplíků",
             "desky_deleny.noha": "věta, když se deska a police dělí u střední nohy: {t1} × {t2} = rozměr tabule desky v mm",
             "desky_deleny.ram": "věta, když se deska a police dělí u vestavěného rámu",
             "desky_deleny.ram_navic": "doplňující věta u rámu: {mezera} = o kolik mm jsou spodní police kratší"}
    for nazev in ("podpery", "podpery_desky", "desky_deleny"):
        for var in sab["en"][nazev]:
            hodnoty = {lg: sab[lg][nazev][var] for lg in ("cs", "en", "sk")}
            typ = "plural" if isinstance(hodnoty["en"], dict) else "text"
            out.append(_pol("stul_info", f"stul_shop.info.{nazev}.{var}", hodnoty["cs"], hodnoty["en"], hodnoty["sk"], typ=typ, poznamka=popis.get(f"{nazev}.{var}")))
    # --- 04 ovladani (klic = ceska sablona)
    videno = set()
    for cs, en, sk in OV._PREKLADY:
        if cs in videno:
            raise AssertionError(f"duplicitni ceska sablona ve _PREKLADY: {cs!r}")
        videno.add(cs)
        out.append(_pol("ovladani", f"ovladani.{cs}", cs, en, sk))
    # --- 05 objednavky
    for k in ("toptrans", "quote", "pickup"):
        out.append(_pol("objednavky", f"objednavky.{k}", MO.LABELS["cs"][k], MO.LABELS["en"][k], MO.LABELS["sk"][k], poznamka="štítek způsobu dopravy v košíku"))
    en_pot = MW.CONFIRMATION.get("en")
    if en_pot:
        out.append(_pol("objednavky", "potvrzeni.predmet", "", en_pot[0], "", volitelne=True, poznamka="VOLITELNÉ (potvrzení poptávky je zatím vypnuté; vyplň předmět i tělo společně, nebo obojí nech prázdné): předmět e-mailu"))
        out.append(_pol("objednavky", "potvrzeni.telo", "", en_pot[1], "", volitelne=True, poznamka="VOLITELNÉ (společně s předmětem): tělo e-mailu; {name} = jméno zákazníka, {site} = název webu"))
    for p in out:
        p["placeholdery"] = sorted(_placeholdery(p["en"]))
    return out


def _placeholdery(hodnota):
    if isinstance(hodnota, dict):
        out = set()
        for v in hodnota.values():
            out |= _placeholdery(v)
        return out
    return set(re.findall(r"\{[A-Za-z0-9_]+\}", hodnota or ""))


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# soubory k vyplneni (docs/jazyky/<jazyk>/NN_*.json)
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def navod(lang, jz):
    nazev = jz.NAZVY_JAZYKU.get(lang, lang)
    pravidlo = jz.PLURAL_PRO_JAZYK.get(lang, "one_other")
    kat = jz.KATEGORIE_PRO_PRAVIDLO[pravidlo]
    abeceda = jz.ABECEDY.get(lang)
    return (f"Vyplň pole \"{lang}\" ({nazev}) u každé položky v `polozky`. Zdroj = cs / en / sk (en je referenční, sk je vzor pro odbornou terminologii). Pravidla: "
            "(1) placeholdery ve složených závorkách ({n} {d} {w} {h} {u} {k} {v} {t1} {t2} {prah} {mezera} {name} {site}) zachovej PŘESNĚ jako v poli `placeholdery` (pořadí ve větě smíš změnit); "
            "(2) žádná značka ani interní slova: Logiman, konfigurátor / konfigurator (i německy „Konfigurator“), vandrawee; "
            "(3) prodej jen firmám (B2B), neutrální věcný tón, bez značky; "
            "(4) povolená písmena jazyka: ASCII + " + (abeceda if abeceda else "(žádná další)") + " - jakýkoli jiný znak (např. česká písmena ě š č ř ž ý ů ť ď ň ľ) vyřadí `miniweb_jazyk_sestav.py`; "
            "(5) mezeru / středník / tečku na začátku nebo konci u šablon (navazují na `zaklad`) ZACHOVEJ stejně jako v en; "
            "(6) terminologie jednotně v celém shopu (i18n, SEO, katalog): drážka profilu = v angličtině „slot“ -> ekvivalent v jazyce určí bot7; "
            f"(7) plurálové položky (`typ`: plural): `{lang}` je objekt, vyplň tvary " + ", ".join(kat) + (" (`one` je volitelné, stačí `other`)" if pravidlo == "other" else "") +
            "; (8) hotové soubory ověř příkazem `scripts/miniweb_jazyk_sestav.py --lang " + lang + "` (bez --apply jen kontrola) a pak jazyk zapíše `--apply`.")


def prazdne_pole(pol, lang, jz):
    """Prazdna hodnota cilového jazyka pro polozku: retezec, nebo objekt kategorii podle pravidla jazyka."""
    if pol["typ"] == "plural":
        pravidlo = jz.PLURAL_PRO_JAZYK.get(lang, "one_other")
        return {k: "" for k in jz.KATEGORIE_PRO_PRAVIDLO[pravidlo]}
    return ""


def cesta_k_souboru(slozka, sekce):
    return os.path.join(slozka, SOUBORY_SEKCI[sekce])


def nacti_vyplnene(slozka):
    """Uz vyplnene hodnoty z existujicich souboru {id: hodnota} (pro znovuspusteni zdroje)."""
    out = {}
    for sekce, nazev in SOUBORY_SEKCI.items():
        cesta = os.path.join(slozka, nazev)
        if not os.path.exists(cesta):
            continue
        try:
            data = json.load(open(cesta, encoding="utf-8"))
        except ValueError:
            continue
        for p in data.get("polozky", []):
            if isinstance(p, dict) and "id" in p:
                out[p["id"]] = p
    return out


def zapis_zdroj(polozky, lang, slozka, jz, existujici=None, sada=None):
    """Zapise soubory docs/jazyky/<jazyk>/NN_*.json. Uz vyplnene `<jazyk>` (z existujicich souboru nebo z hotove sady) se zachova, nove polozky dostanou prazdne pole, polozky, ktere uz v kodu
    nejsou, se vypisou do reportu. Vraci {sekce: pocet}, [zastarale id]."""
    os.makedirs(slozka, exist_ok=True)
    existujici = existujici if existujici is not None else nacti_vyplnene(slozka)
    z_sady = ploche_z_sady(sada) if sada else {}
    pocty, zastarale = {}, []
    ted = {p["id"] for p in polozky}
    zastarale = sorted(i for i in existujici if i not in ted)
    for sekce, nazev in SOUBORY_SEKCI.items():
        radky = []
        for p in polozky:
            if p["sekce"] != sekce:
                continue
            hodnota = prazdne_pole(p, lang, jz)
            stara = existujici.get(p["id"], {}).get(lang)
            if stara is None and p["id"] in z_sady:
                stara = z_sady[p["id"]]
            if stara is not None:
                hodnota = _sjednot(stara, hodnota)
            r = {"id": p["id"]}
            if p.get("poznamka"):
                r["poznamka"] = p["poznamka"]
            if p.get("volitelne"):
                r["volitelne"] = True
            r.update({"typ": p["typ"], "placeholdery": p["placeholdery"], "cs": p["cs"], "en": p["en"], "sk": p["sk"], lang: hodnota})
            radky.append(r)
        pocty[sekce] = len(radky)
        doc = {"_navod": navod(lang, jz), "_sekce": POPIS_SEKCI[sekce], "lang": lang, "sekce": sekce, "polozky": radky}
        with open(os.path.join(slozka, nazev), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return pocty, zastarale


def _sjednot(stara, prazdna):
    """Drivejsi hodnota (retezec / objekt) -> tvar prazdneho pole (zmena pravidla plurálu pridava chybejici kategorie jako '')."""
    if isinstance(prazdna, dict):
        out = dict(prazdna)
        if isinstance(stara, dict):
            for k, v in stara.items():
                if k in out or isinstance(v, str):
                    out[k] = v
        elif isinstance(stara, str) and stara:
            out["other"] = stara
        return out
    return stara if isinstance(stara, str) else (stara.get("other", "") if isinstance(stara, dict) else "")


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
# sada <-> ploche id
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def ploche_z_sady(sada):
    """Sada jazyka (api/jazyky/<jazyk>.json) -> {id: hodnota} se stejnymi id jako polozky_z_kodu."""
    out = {}
    sh = sada.get("stul_shop") or {}
    for nazev in ("TEXTY", "DUVODY", "NAZVY_SLOTU", "TEXTY_AKCI"):
        for k, v in (sh.get(nazev) or {}).items():
            out[f"stul_shop.{nazev}.{k}"] = v
    for k, v in (sh.get("zpravy") or {}).items():
        out[f"stul_shop.zpravy.{k}"] = v
    for nazev, varianty in (sh.get("info") or {}).items():
        for var, v in varianty.items():
            out[f"stul_shop.info.{nazev}.{var}"] = v
    sse = sada.get("stul_shop_sse") or {}
    for k, v in (sse.get("TEXTY") or {}).items():
        out[f"stul_shop_sse.TEXTY.{k}"] = v
    if "DUVOD_SUPLIKY" in sse:
        out["stul_shop_sse.DUVOD_SUPLIKY"] = sse["DUVOD_SUPLIKY"]
    for k, v in (sada.get("ovladani") or {}).items():
        out[f"ovladani.{k}"] = v
    for k, v in (sada.get("objednavky") or {}).items():
        out[f"objednavky.{k}"] = v
    for k, v in (sada.get("potvrzeni") or {}).items():
        out[f"potvrzeni.{k}"] = v
    an = sada.get("ano_ne")
    if isinstance(an, (list, tuple)) and len(an) == 2:
        out["ano_ne.ano"], out["ano_ne.ne"] = an
    return out


def sestav_sadu(lang, hodnoty, pravidlo, jz):
    """{id: hodnota} -> struktura sady jazyka (api/jazyky/<jazyk>.json). Neznamy tvar identifikatoru = ValueError."""
    sada = {"lang": lang, "verze": 1, "plural": pravidlo, "zdroj": f"docs/jazyky/{lang}/", "ano_ne": [None, None],
            "stul_shop": {"TEXTY": {}, "DUVODY": {}, "NAZVY_SLOTU": {}, "TEXTY_AKCI": {}, "zpravy": {}, "info": {}},
            "stul_shop_sse": {"TEXTY": {}}, "ovladani": {}, "objednavky": {}, "potvrzeni": {}}
    for id_, v in hodnoty.items():
        d = id_.split(".")
        if id_.startswith("ovladani."):
            sada["ovladani"][id_[len("ovladani."):]] = v
        elif d[0] == "stul_shop" and d[1] in ("TEXTY", "DUVODY", "NAZVY_SLOTU", "TEXTY_AKCI") and len(d) == 3:
            sada["stul_shop"][d[1]][d[2]] = v
        elif d[0] == "stul_shop" and d[1] == "zpravy" and len(d) == 3:
            sada["stul_shop"]["zpravy"][d[2]] = v
        elif d[0] == "stul_shop" and d[1] == "info" and len(d) == 4:
            sada["stul_shop"]["info"].setdefault(d[2], {})[d[3]] = v
        elif d[0] == "stul_shop_sse" and d[1] == "TEXTY" and len(d) == 3:
            sada["stul_shop_sse"]["TEXTY"][d[2]] = v
        elif id_ == "stul_shop_sse.DUVOD_SUPLIKY":
            sada["stul_shop_sse"]["DUVOD_SUPLIKY"] = v
        elif d[0] == "objednavky" and len(d) == 2:
            sada["objednavky"][d[1]] = v
        elif d[0] == "potvrzeni" and len(d) == 2:
            sada["potvrzeni"][d[1]] = v
        elif id_ == "ano_ne.ano":
            sada["ano_ne"][0] = v
        elif id_ == "ano_ne.ne":
            sada["ano_ne"][1] = v
        else:
            raise ValueError(f"neznamy identifikator polozky: {id_!r}")
    if not sada["potvrzeni"]:
        del sada["potvrzeni"]
    return sada
