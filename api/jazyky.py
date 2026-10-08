"""Jazykove sady dalsich jazyku mini-shopu (bot16, 2026-10-07).

Robert 2026-10-07: "dodelat mini shop anglicky jedna ku jedne se slovenskym, dale vytvorit dalsi kopii shopu v nemcine" (+ madarstina). Zakaznicke texty, ktere vydava SERVER (verejne API
konfiguratoru stolu /api/shop/configurator/*, dopravni stitky mini-shopu, sablona potvrzeni), jsou pro jazyky cs / en / sk natvrdo v kodu (api/stul_shop.py, stul_shop_sse.py,
stul_ovladani_verejne.py, miniweb_objednavky.py, miniweb.py) a ZUSTAVAJI tam beze zmeny. Dalsi jazyk (de, hu, pl ...) se pridava DATY, bez zasahu do kodu:

    api/jazyky/<jazyk>.json        jedna sada na jazyk (dvoupismenny kod); env JAZYKY_DIR prepise adresar (testy)

Moduly na KONCI sveho souboru zavolaji pripoj_* z tohoto modulu; ten do jejich slovniku (TEXTY[<jazyk>], DUVODY[<jazyk>] ...) doplni jazyky ze sad. Pravidla:
  * jazyk, ktery NENI cs / en / sk, se bere jen ze sady; sada s vadnym JSON / neodpovidajicim `lang` / spatnymi typy se IGNORUJE (varovani do logu, nikdy pad aplikace);
  * chybejici klic v sade = zaloha z anglictiny + varovani do logu pri startu (zakaznik nikdy nedostane 500 ani KeyError); UPLNOST hlida scripts/miniweb_jazyk_parita.py a
    scripts/miniweb_jazyk_sestav.py (chybejici/neplatna polozka sadu vubec nevyda), takze zaloha je jen pojistka;
  * texty s gramatikou (informacni vety s poctem kusu) jsou SABLONY s placeholdery a plural kategoriemi (one / few / many / other podle pravidla jazyka); zadna jina logika v textech.
Postup pridani jazyka: docs/jazyky/README.md (zdroj -> vyplnit bot7 -> sestav -> parita).

Tento modul ma zamerne jen standardni knihovnu (importuje se z aplikace i ze skriptu). Zdrojove retezce z kodu vytahuje scripts/_jazyky_zdroj.py (introspekce modulu), ne tenhle soubor.
"""
import json
import logging
import os
import re
import string

LOG = logging.getLogger("jazyky")

VESTAVENE = ("cs", "en", "sk")                         # jazyky, jejichz texty jsou v kodu modulu (sada se pro ne nikdy nepouzije)
DIR_VYCHOZI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jazyky")
KOD_RE = re.compile(r"^[a-z]{2}$")
SLOVNIKY_DICT = ("TEXTY", "DUVODY", "NAZVY_SLOTU", "TEXTY_AKCI")        # stul_shop: slovnik {jazyk: {klic: text}}
VYCHOZI_KLIC = "_default"                              # v sade nahrazuje klic None ve slovniku DUVODY (JSON nezna None jako klic)

# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# ABECEDY - JEDNO misto: jake znaky smi mit text daneho jazyka. Pouziva scripts/miniweb_jazyk_sestav.py (kazdy znak mimo abecedu jazyka je CHYBA, typicky cesko-slovenska
# diakritika v nemcine / madarstine); novy jazyk = jeden radek. Kazdy jazyk smi navic ASCII a OBECNE_ZNAKY (typografie).
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
ASCII = "".join(chr(c) for c in range(0x20, 0x7F)) + "\n\t"
OBECNE_ZNAKY = "   ×–—−…“”„‚‘’«»°€·±½²³µ§®′″"
ABECEDY = {
    "cs": "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ",
    "sk": "áäčďéíĺľňóôŕšťúýžÁÄČĎÉÍĹĽŇÓÔŔŠŤÚÝŽ",
    "en": "",
    "de": "äöüÄÖÜß",
    "hu": "áéíóöőúüűÁÉÍÓÖŐÚÜŰ",
    "pl": "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "ro": "ăâîșțşţĂÂÎȘȚŞŢ",
    "hr": "čćđšžČĆĐŠŽ",
    "sl": "čšžČŠŽ",
    "it": "àèéìòùÀÈÉÌÒÙ",
    "fr": "àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ",
    "es": "áéíñóúü¿¡ÁÉÍÑÓÚÜ",
    "nl": "áéíóúëïüÁÉÍÓÚËÏÜ",
}
NAZVY_JAZYKU = {"cs": "čeština", "sk": "slovenština", "en": "angličtina", "de": "němčina", "hu": "maďarština", "pl": "polština", "ro": "rumunština", "hr": "chorvatština",
                "sl": "slovinština", "it": "italština", "fr": "francouzština", "es": "španělština", "nl": "nizozemština"}
# pravidlo plurálu jazyka (kategorie CLDR): "one_other" (de, en, nl ...), "other" (hu: po cislovce jednotne cislo, staci kategorie other), "cs_sk" (one, few, other), "pl" (one, few, many, other)
PLURAL_PRO_JAZYK = {"de": "one_other", "hu": "other", "en": "one_other", "cs": "cs_sk", "sk": "cs_sk", "pl": "pl", "nl": "one_other", "it": "one_other", "es": "one_other",
                    "fr": "one_other", "ro": "one_other", "hr": "pl", "sl": "pl"}
KATEGORIE_PRO_PRAVIDLO = {"other": ("other",), "one_other": ("one", "other"), "cs_sk": ("one", "few", "other"), "pl": ("one", "few", "many", "other")}
# slova, ktera se ve verejnych textech mini-shopu NESMI objevit (znacka a interni nazvy; stejny regex jako scripts/miniweb_domena.py BRAND_RE a test_en_mini_shop.js)
ZAKAZANA_SLOVA_RE = re.compile(r"logiman|konfigur[aá]tor|vandrawee|logi\s*(?:<[^>]*>\s*)*man\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_]+\}")


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# plural
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
def _plural_other(n):
    return "other"


def _plural_one_other(n):
    return "one" if n == 1 else "other"


def _plural_cs_sk(n):
    return "one" if n == 1 else ("few" if 2 <= n <= 4 else "other")


def _plural_pl(n):
    if n == 1:
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return "many"


_PLURAL = {"other": _plural_other, "one_other": _plural_one_other, "cs_sk": _plural_cs_sk, "pl": _plural_pl}


def plural_kategorie(pravidlo, n):
    """Kategorie plurálu pro cele cislo n podle pravidla jazyka (neznamé pravidlo = one_other)."""
    return _PLURAL.get(pravidlo, _plural_one_other)(int(n))


def vyber_tvar(sablona, kategorie):
    """Sablona = retezec (platí pro vsechny kategorie) nebo {kategorie: retezec}. Kdyz kategorie chybi: other -> many -> few -> one -> prvni dostupny (jazyk smi mit `one` i `other` stejne)."""
    if isinstance(sablona, str):
        return sablona
    for k in (kategorie, "other", "many", "few", "one"):
        if isinstance(sablona.get(k), str):
            return sablona[k]
    for v in sablona.values():
        if isinstance(v, str):
            return v
    raise KeyError("sablona bez textu")


def pravidlo_jazyka(lang, sada=None):
    """Pravidlo plurálu: z sady (`plural`), jinak z tabulky PLURAL_PRO_JAZYK, jinak one_other."""
    p = (sada or {}).get("plural") if isinstance(sada, dict) else None
    return p if p in _PLURAL else PLURAL_PRO_JAZYK.get(lang, "one_other")


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# kontrola textu (pouziva sestav / parita / testy)
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
def placeholdery(text):
    """Mnozina placeholderu {x} v textu (retezec nebo objekt kategorii = sjednoceni)."""
    if isinstance(text, dict):
        out = set()
        for v in text.values():
            out |= placeholdery(v)
        return out
    return set(PLACEHOLDER_RE.findall(text or ""))


def format_chyba(text, povolene, presne=False, volitelne=()):
    """None, kdyz je `text` PLATNA sablona str.format, ktera pouziva jen pojmenovana pole z `povolene` (nazvy bez zavorek, napr. {"n", "h"}); jinak popis chyby.
    Zachyti to, co `.format()` za behu shodi: osamocenou { nebo }, neznamy / ciselny / atributovy placeholder ({x}, {}, {0}, {n.real}), format {n:05d} a konverzi {n!r}.
    presne=True navic vyzaduje VSECHNA povolena pole (krome `volitelne`) - tvrdsi pravidlo nastroje sestav; za behu stačí "jen povolena" (chybejici pole nic neshodi)."""
    if not isinstance(text, str):
        return "neni retezec"
    pole = set()
    try:
        for _lit, nazev, spec, konv in string.Formatter().parse(text):
            if nazev is None:
                continue
            if spec or konv:
                return f"placeholder {{{nazev}}} ma format / konverzi ({spec or ''}{'!' + konv if konv else ''}), povolena jsou jen holá pole"
            if nazev not in povolene:
                return f"neznamy placeholder {{{nazev}}} (povolene: {', '.join('{' + x + '}' for x in sorted(povolene)) or 'zadne'})"
            pole.add(nazev)
    except ValueError as e:
        return f"neplatna sablona ({e})"
    if presne:
        chybi = set(povolene) - pole - set(volitelne)
        if chybi:
            return "chybi placeholder " + ", ".join("{" + x + "}" for x in sorted(chybi))
    return None


def nepovolene_znaky(lang, text):
    """Seznam znaku textu, ktere nepatri do abecedy jazyka (ASCII + OBECNE_ZNAKY + pismena jazyka); prazdny seznam = v poradku. Jazyk bez radku v ABECEDY -> ValueError."""
    if lang not in ABECEDY:
        raise ValueError(f"jazyk {lang!r} nema abecedu v api/jazyky.py (ABECEDY) - doplnte radek")
    povolene = ASCII + OBECNE_ZNAKY + ABECEDY[lang]
    out = []
    for ch in text if isinstance(text, str) else "".join(text.values()) if isinstance(text, dict) else "":
        if ch not in povolene and ch not in out:
            out.append(ch)
    return out


def popis_znaku(znaky):
    return ", ".join(f"{z!r} (U+{ord(z):04X})" for z in znaky)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# nacteni sad
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
_CACHE = {}
_VAROVANO = set()


def adresar():
    return os.environ.get("JAZYKY_DIR") or DIR_VYCHOZI


def _varuj(klic, zprava):
    if klic not in _VAROVANO:
        _VAROVANO.add(klic)
        LOG.warning("%s", zprava)


def nacti(lang):
    """Sada jazyka (dict) nebo None (neexistuje / vadna / jazyk je vestaveny). Vysledek se drzi v pameti podle mtime souboru."""
    if lang in VESTAVENE or not isinstance(lang, str) or not KOD_RE.match(lang):
        return None
    cesta = os.path.join(adresar(), f"{lang}.json")
    try:
        st = os.stat(cesta)
    except OSError:
        return None
    klic = (cesta, st.st_mtime_ns, st.st_size)
    if klic in _CACHE:
        return _CACHE[klic]
    sada = None
    try:
        with open(cesta, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or data.get("lang") != lang:
            raise ValueError(f"pole lang ({data.get('lang') if isinstance(data, dict) else None!r}) neodpovida souboru")
        for sekce in ("stul_shop", "stul_shop_sse", "ovladani", "objednavky", "potvrzeni"):
            if sekce in data and not isinstance(data[sekce], (dict, list)):
                raise ValueError(f"sekce {sekce} ma spatny typ")
        sada = data
    except (OSError, ValueError) as e:
        _varuj(("vadna", cesta, klic[1]), f"jazyky: sada {cesta} se ignoruje: {e}")
        sada = None
    for k in [k for k in _CACHE if k[0] == cesta]:
        del _CACHE[k]
    _CACHE[klic] = sada
    return sada


def jazyky():
    """Kody jazyku, ktere maji platnou sadu (serazene)."""
    try:
        jmena = os.listdir(adresar())
    except OSError:
        return []
    out = []
    for j in sorted(jmena):
        m = re.match(r"^([a-z]{2})\.json$", j)
        if m and m.group(1) not in VESTAVENE and nacti(m.group(1)) is not None:
            out.append(m.group(1))
    return out


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# pripojeni do modulu (volaji na KONCI svych souboru)
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
def _pole_zalohy(ref):
    """Povolena pole sablony: placeholdery anglicke zalohy (retezec) bez slozenych zavorek."""
    return {x[1:-1] for x in placeholdery(ref)} if isinstance(ref, str) else set()


def _platna(lang, nazev, klic, v, ref):
    """Hodnota ze sady je pouzitelna, kdyz je neprazdny retezec a platna sablona s poli jako anglicka zaloha (.format za behu pak nic neshodi). Jinak jednorazove varovani a False."""
    if not (isinstance(v, str) and v.strip()):
        _varuj(("prazdna", lang, nazev, klic), f"jazyky: {lang}: {nazev}[{klic!r}] je prazdne / neni retezec - zaloha angličtina")
        return False
    ch = format_chyba(v, _pole_zalohy(ref))
    if ch:
        _varuj(("sablona", lang, nazev, klic), f"jazyky: {lang}: {nazev}[{klic!r}] ma vadnou sablonu ({ch}) - zaloha angličtina")
        return False
    return True


def _slij(lang, nazev, zaloha, hodnoty):
    """Slovnik jazyka = anglicka zaloha prepsana platnymi hodnotami sady; chybejici klice se hlasi jednou do logu."""
    out = dict(zaloha)
    if not isinstance(hodnoty, dict):
        hodnoty = {}
    chybi = [k for k in zaloha if k not in hodnoty]
    if chybi:
        _varuj(("chybi", lang, nazev), f"jazyky: {lang}: v {nazev} chybi {len(chybi)} polozek (zaloha angličtina): {', '.join(str(k) for k in chybi[:8])}{' ...' if len(chybi) > 8 else ''}")
    for k, v in hodnoty.items():
        if k in zaloha and _platna(lang, nazev, k, v, zaloha[k]):
            out[k] = v
    return out


def slovniky_zprav(ns):
    """Nazvy slovniku {jazyk: text} (14 hlasek v stul_shop.py): moduly-level dict, ktery ma cs a en jako retezce."""
    return sorted(n for n, v in ns.items() if isinstance(v, dict) and n not in SLOVNIKY_DICT and isinstance(v.get("en"), str) and isinstance(v.get("cs"), str))


def pripoj_stul_shop(ns):
    """Doplni jazyky ze sad do slovniku modulu api/stul_shop.py (ns = globals() modulu): TEXTY, DUVODY (klic None = `_default`), NAZVY_SLOTU, TEXTY_AKCI a hlasky {jazyk: text}.
    Jazyk se pripojuje ATOMICKY (vsechny slovniky, nebo zadny); neocekavana chyba jednoho jazyka ho vynecha (log), aplikace i cs / en / sk bezi dal."""
    zpravy = slovniky_zprav(ns)
    for lg in jazyky():
        try:
            sada = nacti(lg)
            sekce = sada.get("stul_shop") if isinstance(sada.get("stul_shop"), dict) else {}
            nove = {}
            for nazev in SLOVNIKY_DICT:
                if nazev not in ns or "en" not in ns[nazev]:
                    continue
                hodnoty = sekce.get(nazev) if isinstance(sekce.get(nazev), dict) else {}
                if nazev == "DUVODY":
                    hodnoty = {(None if k == VYCHOZI_KLIC else k): v for k, v in hodnoty.items()}
                nove[nazev] = _slij(lg, nazev, ns[nazev]["en"], hodnoty)
            z = sekce.get("zpravy") if isinstance(sekce.get("zpravy"), dict) else {}
            nove_zpravy = {}
            for nazev in zpravy:
                v = z.get(nazev)
                if v is not None and _platna(lg, "zpravy", nazev, v, ns[nazev]["en"]):
                    nove_zpravy[nazev] = v
                else:
                    if v is None:
                        _varuj(("chybi", lg, nazev), f"jazyky: {lg}: hlaska {nazev} chybi v sade (zaloha angličtina)")
                    nove_zpravy[nazev] = ns[nazev]["en"]
            for nazev, d in nove.items():
                ns[nazev][lg] = d
            for nazev, t in nove_zpravy.items():
                ns[nazev][lg] = t
        except Exception:                                                           # noqa: BLE001 - sada nikdy nesmi shodit import aplikace
            LOG.exception("jazyky: %s: pripojeni do stul_shop selhalo, jazyk se v tomto modulu vynecha", lg)


def pripoj_stul_shop_sse(ns):
    """Doplni jazyky do api/stul_shop_sse.py (TEXTY, DUVOD_SUPLIKY). Jazyk, ktery ma sadu, ale ne sekci SSE, dostane anglickou zalohu (verejne schema SSE stolu smi mit jen jazyky z TEXTY)."""
    for lg in jazyky():
        try:
            sada = nacti(lg)
            sekce = sada.get("stul_shop_sse") if isinstance(sada.get("stul_shop_sse"), dict) else {}
            texty = _slij(lg, "SSE TEXTY", ns["TEXTY"]["en"], sekce.get("TEXTY"))
            d = sekce.get("DUVOD_SUPLIKY")
            if d is not None and _platna(lg, "SSE", "DUVOD_SUPLIKY", d, ns["DUVOD_SUPLIKY"]["en"]):
                duvod = d
            else:
                if d is None:
                    _varuj(("chybi", lg, "DUVOD_SUPLIKY"), f"jazyky: {lg}: SSE DUVOD_SUPLIKY chybi v sade (zaloha angličtina)")
                duvod = ns["DUVOD_SUPLIKY"]["en"]
            ns["TEXTY"][lg] = texty
            ns["DUVOD_SUPLIKY"][lg] = duvod
        except Exception:                                                           # noqa: BLE001
            LOG.exception("jazyky: %s: pripojeni do stul_shop_sse selhalo, jazyk se v tomto modulu vynecha", lg)


def pripoj_ovladani(tab, preklady, max_polic):
    """Doplni jazyky do tabulky ovladani 3D (api/stul_ovladani_verejne.py: `_TAB` = {jazyk: {cesky text: preklad}}). Sada nese `ovladani` = {cesky text se {n}: preklad se {n}}, rozbaluje se stejne
    jako `_tabulka()` (cislo vyrezu / police 1..max_polic). Chybejici nebo vadny preklad (neplatna sablona, jine pole nez {n}) = anglicky text z `tab["en"]` (+ varovani)."""
    for lg in jazyky():
        try:
            sada = nacti(lg)
            zdroj = sada.get("ovladani") if isinstance(sada.get("ovladani"), dict) else {}
            out = {}
            chybi, vadne = [], []
            for cs, _en, _sk in preklady:
                t = zdroj.get(cs)
                povolene = {"n"} if "{n}" in cs else set()
                if not (isinstance(t, str) and t.strip()):
                    chybi.append(cs)
                    t = None
                elif format_chyba(t, povolene):
                    vadne.append(f"{cs!r}: {format_chyba(t, povolene)}")
                    t = None
                for n in (range(1, max_polic + 1) if "{n}" in cs else (0,)):
                    k = cs.format(n=n) if "{n}" in cs else cs
                    out[k] = (t.format(n=n) if "{n}" in t else t) if t is not None else tab["en"][k]
            if chybi:
                _varuj(("chybi", lg, "ovladani"), f"jazyky: {lg}: v ovladani chybi {len(chybi)} prekladu (zaloha angličtina): {', '.join(repr(c)[:40] for c in chybi[:5])}{' ...' if len(chybi) > 5 else ''}")
            if vadne:
                _varuj(("vadne", lg, "ovladani"), f"jazyky: {lg}: v ovladani je {len(vadne)} vadnych sablon (zaloha angličtina): {'; '.join(vadne[:3])}")
            tab[lg] = out
        except Exception:                                                           # noqa: BLE001
            LOG.exception("jazyky: %s: pripojeni do ovladani selhalo, jazyk se v tomto modulu vynecha", lg)


def pripoj_objednavky(labels):
    """Doplni dopravni stitky mini-shopu (api/miniweb_objednavky.py LABELS = {jazyk: {toptrans, quote, pickup}})."""
    for lg in jazyky():
        try:
            sada = nacti(lg)
            z = sada.get("objednavky") if isinstance(sada.get("objednavky"), dict) else {}
            labels[lg] = _slij(lg, "LABELS", labels["en"], z)
        except Exception:                                                           # noqa: BLE001
            LOG.exception("jazyky: %s: pripojeni stitku objednavek selhalo, jazyk se vynecha", lg)


def pripoj_potvrzeni(potvrzeni):
    """Doplni sablonu potvrzeni poptavky (api/miniweb.py CONFIRMATION = {jazyk: (predmet, telo)}); jen pro jazyky, ktere sekci `potvrzeni` ({predmet, telo}) v sade maji a ktera je platna
    sablona s poli {name} a {site}."""
    for lg in jazyky():
        try:
            z = nacti(lg).get("potvrzeni")
            if not isinstance(z, dict):
                continue
            ok = all(isinstance(z.get(k), str) and z[k].strip() and not format_chyba(z[k], {"name", "site"}) for k in ("predmet", "telo"))
            if ok:
                potvrzeni[lg] = (z["predmet"], z["telo"])
            else:
                _varuj(("vadna", lg, "potvrzeni"), f"jazyky: {lg}: sekce potvrzeni je neuplna nebo ma vadnou sablonu (povolena jen {{name}} a {{site}}) - potvrzeni se pro jazyk nepouzije")
        except Exception:                                                           # noqa: BLE001
            LOG.exception("jazyky: %s: pripojeni potvrzeni selhalo, jazyk se vynecha", lg)


# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
# za behu
# ----------------------------------------------------------------------------------------------------------------------------------------------------------------
def ano_ne(lang):
    """(ano, ne) pro souhrn voleb z sady jazyka, nebo None (jazyk cs / en / sk resi kod)."""
    sada = nacti(lang)
    v = sada.get("ano_ne") if sada else None
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, str) and x.strip() for x in v):
        return v[0], v[1]
    return None


def info(lang, nazev, **kw):
    """Informacni veta s gramatikou ze sablon sady jazyka (`stul_shop.info`): nazev = podpery | podpery_desky | desky_deleny. kw = hodnoty placeholderu + (n, u, sup, ram) pro vyber tvaru.
    Vraci text, nebo None (jazyk bez sady / sablony chybi nebo je vadna) - volajici pak pouzije anglictinu."""
    sada = nacti(lang)
    if not sada:
        return None
    sekce = sada.get("stul_shop")
    sab = ((sekce or {}).get("info") or {}).get(nazev) if isinstance(sekce, dict) else None
    if not isinstance(sab, dict):
        _varuj(("chybi", lang, "info", nazev), f"jazyky: {lang}: sablony informace {nazev} chybi v sade (zaloha angličtina)")
        return None
    pr = pravidlo_jazyka(lang, sada)
    try:
        if nazev == "podpery":                        # kw: h, k, n (pocet podper na policu; 0 = zadne), u (pocet urovni polic)
            z = sab["zaklad"].format(**kw)
            if kw["n"]:
                tvary = sab["s_u1"] if kw["u"] == 1 else sab["s_um"]
                return z + vyber_tvar(tvary, plural_kategorie(pr, kw["n"])).format(**kw)
            return z + sab["bez"].format(**kw)
        if nazev == "podpery_desky":                  # kw: h, n, sup (suplik)
            z = vyber_tvar(sab["zaklad"], plural_kategorie(pr, kw["n"])).format(**kw)
            return z + (sab["konec_suplik"] if kw["sup"] else sab["konec"]).format(**kw)
        if nazev == "desky_deleny":                   # kw: t1, t2, mezera, ram
            if kw["ram"]:
                return sab["ram"].format(**kw) + sab["ram_navic"].format(**kw)
            return sab["noha"].format(**kw)
    except (KeyError, IndexError, ValueError, AttributeError, TypeError) as e:
        _varuj(("vadna", lang, "info", nazev), f"jazyky: {lang}: sablona informace {nazev} je vadna ({type(e).__name__}: {e}) - zaloha angličtina")
        return None
    return None
