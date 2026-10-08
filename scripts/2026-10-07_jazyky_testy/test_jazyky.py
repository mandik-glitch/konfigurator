#!/usr/bin/env python3
"""Testy jazykovych sad serveru (bot16, 2026-10-07): api/jazyky.py + nastroje scripts/miniweb_jazyk_{zdroj,sestav,parita}.py + napojeni v modulech API.

Co se overuje (zadne zapisy do ostre DB; DB jen cteni, soubory do docasnych adresaru):
  A  plural pravidla, vyber tvaru, abecedy (de / hu / pl / syntetický jazyk s diakritikou), placeholdery, vadne sady se ignoruji bez padu
  B  nastroje: zdroj (326 polozek, znovuspusteni zachova hodnoty), sestav (prazdne = chyba, placeholdery, abeceda: ceske pismeno v de / hu spadne, ő ű v hu projde, znacka, mezery,
     plural kategorie, hu staci `other`), zapis sady
  C  sada `xx` v kodu (podproces s cerstvym importem): slovniky, schema vsech systemu, resolve (hlasky, nabidky, duvody), informacni vety s pluralem, ovladani, SSE, LABELS,
     potvrzeni, ano / ne, skutecne trasy pres Flask test client
  D  chybejici polozky v sade = anglicka zaloha + varovani v logu, zadny pad
  E  cs / en / sk BEZE ZMENY: otisk vystupu s prazdnym adresarem sad = otisk se sadou xx
  F  parita: sk proti sk bez mezer, xx proti sk ukaze chybejici vrstvy, vrstva DB (jen SELECT), --json
  G  sablony z kodu slozene pres jazyky.info davaji presne stejne vety jako puvodni funkce (cs / en / sk, 210 pripadu)
Spusteni: api/venv/bin/python3 scripts/2026-10-07_jazyky_testy/test_jazyky.py   (z korene repa nebo z izolovane kopie HEAD)
"""
import contextlib
import copy
import importlib.util
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import _jazyky_zdroj as Z  # noqa: E402
import jazyky as jz  # noqa: E402

PY = sys.executable
TMP = tempfile.mkdtemp(prefix="jazyky_test_")
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def nacti_nastroj(jmeno):
    spec = importlib.util.spec_from_file_location(jmeno, os.path.join(REPO, "scripts", jmeno + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def spust(fn, argv):
    """Zavola main(argv) nastroje, vrati (kod, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        kod = fn(argv)
    return kod, out.getvalue()


def san(id_):
    return re.sub(r"[^A-Za-z0-9_.{}]", "_", id_)


def okraje(t):
    return t[:len(t) - len(t.lstrip())], t[len(t.rstrip()):]


def vypln_hodnotu(p, lang):
    """Hodnota se znackou [xx:<id>] + placeholdery, se stejnymi okraji jako en (aby prosla kontrolou); plural: znacka s kategorii."""
    ph = " ".join(p["placeholdery"])
    if p["typ"] == "plural":
        pravidlo = jz.PLURAL_PRO_JAZYK.get(lang, "one_other")
        out = {}
        for kat in jz.KATEGORIE_PRO_PRAVIDLO[pravidlo]:
            en = p["en"].get(kat) or p["en"].get("other")
            z, k = okraje(en)
            out[kat] = f"{z}[xx:{san(p['id'])}:{kat}] {ph}".rstrip() + k
        return out
    z, k = okraje(p["en"])
    t = f"[xx:{san(p['id'])}]" + (f" {ph}" if ph else "")
    return z + t + k


def vypln_slozku(slozka, lang, upravy=None):
    """Vyplni vsechny soubory slozky tagovanymi hodnotami; upravy = {id: nova_hodnota | funkce(stara)}. Vraci pocet polozek."""
    upravy = upravy or {}
    n = 0
    for nazev in Z.SOUBORY_SEKCI.values():
        cesta = os.path.join(slozka, nazev)
        doc = json.load(open(cesta, encoding="utf-8"))
        for p in doc["polozky"]:
            p[lang] = vypln_hodnotu(p, lang)
            if p["id"] in upravy:
                u = upravy[p["id"]]
                p[lang] = u(p[lang]) if callable(u) else u
            n += 1
        json.dump(doc, open(cesta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return n


def uprav_polozku(slozka, id_, fn):
    for nazev in Z.SOUBORY_SEKCI.values():
        cesta = os.path.join(slozka, nazev)
        doc = json.load(open(cesta, encoding="utf-8"))
        zmeneno = False
        for p in doc["polozky"]:
            if p["id"] == id_:
                fn(p)
                zmeneno = True
        if zmeneno:
            json.dump(doc, open(cesta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return True
    raise KeyError(id_)


def kopie(slozka, nazev):
    cil = os.path.join(TMP, nazev)
    shutil.rmtree(cil, ignore_errors=True)
    shutil.copytree(slozka, cil)
    return cil


def podproces(rezim, jazyky_dir, extra_env=None):
    env = dict(os.environ)
    env["JAZYKY_DIR"] = jazyky_dir
    env.update(extra_env or {})
    r = subprocess.run([PY, os.path.join(HERE, "pomocnik.py"), rezim], capture_output=True, text=True, env=env, timeout=600)
    posledni = [x for x in r.stdout.strip().splitlines() if x.startswith("{")]
    if r.returncode != 0 or not posledni:
        return {"chyby": [f"podproces {rezim} skoncil kodem {r.returncode}: {(r.stderr or r.stdout)[-1500:]}"], "log": [], "extra": {}}
    return json.loads(posledni[-1])


def main():
    jz.LOG.addHandler(logging.NullHandler())                           # bez toho by varovani z testu G2 (zamerne neuplna sada hu) sla na stderr
    zdroj_n, sestav_n, parita_n = (nacti_nastroj(x) for x in ("miniweb_jazyk_zdroj", "miniweb_jazyk_sestav", "miniweb_jazyk_parita"))
    jz.ABECEDY["xx"] = "ěš"                                            # syntetický jazyk s diakritikou (jen v tomto procesu)
    jz.PLURAL_PRO_JAZYK["xx"] = "one_other"
    jz.NAZVY_JAZYKU["xx"] = "syntetická"

    print("== A) pravidla plurálu, abecedy, placeholdery, vadné sady")
    over("A1 plural one_other: 1 = one, 0 / 2 / 5 = other", [jz.plural_kategorie("one_other", n) for n in (1, 0, 2, 5)] == ["one", "other", "other", "other"])
    over("A2 plural other (hu): vždy other", {jz.plural_kategorie("other", n) for n in (0, 1, 2, 5, 21)} == {"other"})
    over("A3 plural cs_sk: 1 one, 2-4 few, 5+ other", [jz.plural_kategorie("cs_sk", n) for n in (1, 2, 4, 5, 0)] == ["one", "few", "few", "other", "other"])
    over("A4 plural pl: 1 one, 2-4 few, 5-21 many, 22 few, 12-14 many", [jz.plural_kategorie("pl", n) for n in (1, 2, 5, 12, 22, 24, 25)] == ["one", "few", "many", "many", "few", "few", "many"])
    over("A5 výběr tvaru: kategorie → other → … (hu může mít one i other stejně)", jz.vyber_tvar({"other": "O"}, "one") == "O" and jz.vyber_tvar({"one": "A", "other": "B"}, "one") == "A" and jz.vyber_tvar("S", "few") == "S")
    over("A6 abeceda de: ä ö ü ß ok, ě á é í ú š ř ž ů ý ľ flaguje", jz.nepovolene_znaky("de", "Größe äöüÄÖÜß Straße") == [] and set(jz.nepovolene_znaky("de", "ě á é í ú š ř ž ů ý ľ")) == set("ěáéíúšřžůýľ"))
    over("A7 abeceda hu: á é í ó ö ő ú ü ű (i velká) ok, ě š č ř ž ý ů ť ď ň ľ ĺ ŕ ä flaguje", jz.nepovolene_znaky("hu", "áéíóöőúüű ÁÉÍÓÖŐÚÜŰ Hőtároló") == [] and set(jz.nepovolene_znaky("hu", "ěščřžýůťďňľĺŕä")) == set("ěščřžýůťďňľĺŕä"))
    over("A8 abeceda cs / sk / en jako dnes (cs: ě ř ů ok, en: žádná diakritika)", jz.nepovolene_znaky("cs", "Příliš žluťoučký kůň ěščřžýáíéúůťďň") == [] and jz.nepovolene_znaky("sk", "Žltá ľadová ôsmy") == [] and set(jz.nepovolene_znaky("en", "ě é")) == set("ěé"))
    over("A9 typografie (– × − … „ “) je povolená v každém jazyce", all(jz.nepovolene_znaky(l, "10 × 20 mm – „text“ … −5 °C €") == [] for l in ("de", "hu", "cs", "en")))
    over("A10 syntetický jazyk xx s diakritikou: ě š ok, ř flaguje", jz.nepovolene_znaky("xx", "ěš") == [] and jz.nepovolene_znaky("xx", "ř") == ["ř"])
    try:
        jz.nepovolene_znaky("qq", "a")
        over("A11 jazyk bez abecedy = ValueError", False)
    except ValueError as e:
        over("A11 jazyk bez abecedy = ValueError (doplnit řádek do ABECEDY)", "ABECEDY" in str(e))
    over("A12 každý jazyk s pravidlem plurálu / názvem má i abecedu", all(l in jz.ABECEDY for l in list(jz.PLURAL_PRO_JAZYK) + list(jz.NAZVY_JAZYKU)) and all(jz.PLURAL_PRO_JAZYK[l] in jz.KATEGORIE_PRO_PRAVIDLO for l in jz.PLURAL_PRO_JAZYK))
    over("A13 placeholdery: {n} {h} se najdou, {} a { n } ne", jz.placeholdery("a {n} b {h} {} { n }") == {"{n}", "{h}"} and jz.placeholdery({"one": "{n}", "other": "{k}"}) == {"{n}", "{k}"})
    over("A14 zakázaná slova: Logiman, Konfigurator, konfigurátor, vandrawee, Logi<span>MAN", all(jz.ZAKAZANA_SLOVA_RE.search(x) for x in ("Logiman", "Konfigurator", "konfigurátor", "VanDrawee", "LOGi <b>MAN")) and not jz.ZAKAZANA_SLOVA_RE.search("Konfiguration"))

    fc = jz.format_chyba
    over("A14b format_chyba: platné šablony projdou ({n}, {{literal}}, bez polí)", fc("ok {n} mm", {"n"}) is None and fc("{{literal}} text", set()) is None and fc("bez poli", {"n"}) is None and fc("{n} {h}", {"n", "h"}, presne=True) is None)
    over("A14c format_chyba: osamocená { nebo }, {}, {0}, {x}, {n:05d}, {n!r}, {n.real}, {n[0]} jsou chyby",
         all(fc(t, {"n"}) for t in ("a { b", "a } b", "{}", "{0}", "{x}", "{n:05d}", "{n!r}", "{n.real}", "{n[0]}", "{n")), [t for t in ("a { b", "a } b", "{}", "{0}", "{x}", "{n:05d}", "{n!r}", "{n.real}", "{n[0]}", "{n") if not fc(t, {"n"})])
    over("A14d format_chyba presne: chybějící pole = chyba, `volitelne` smí chybět, {{n}} není placeholder", fc("jen {n}", {"n", "h"}, presne=True) and fc("jen {n}", {"n", "h"}, presne=True, volitelne={"h"}) is None and fc("{{n}}", {"n"}, presne=True) and fc(5, {"n"}))
    kod_pol = Z.polozky_z_kodu(Z.importuj_api())
    zdroj_spatne = []
    for pol in kod_pol:
        pov = {x[1:-1] for x in pol["placeholdery"]}
        for lg in ("cs", "en", "sk"):
            v = pol[lg]
            for kat, t in (v.items() if isinstance(v, dict) else [(None, v)]):
                if t and fc(t, pov, presne=(lg == "en" and kat != "one"), volitelne={"n"} if kat == "one" else ()):
                    zdroj_spatne.append((pol["id"], lg, kat))
    over(f"A14e všech {len(kod_pol)} zdrojových položek cs / en / sk je platná šablona (kontrola `sestav` není přísnější než vlastní texty)", not zdroj_spatne, zdroj_spatne[:3])

    # vadné sady
    vadne = os.path.join(TMP, "vadne_sady")
    os.makedirs(vadne)
    open(os.path.join(vadne, "yy.json"), "w").write("{ tohle neni json")
    json.dump({"lang": "zz2"}, open(os.path.join(vadne, "zz.json"), "w"))
    json.dump({"lang": "ww", "stul_shop": 5}, open(os.path.join(vadne, "ww.json"), "w"))
    json.dump({"lang": "cs", "stul_shop": {}}, open(os.path.join(vadne, "cs.json"), "w"))
    json.dump({"lang": "abc"}, open(os.path.join(vadne, "abc.json"), "w"))
    json.dump([1, 2], open(os.path.join(vadne, "vv.json"), "w"))
    json.dump({"lang": "oo", "plural": "one_other"}, open(os.path.join(vadne, "oo.json"), "w"))
    zachyt = []

    class H(logging.Handler):
        def emit(self, r):
            zachyt.append(r.getMessage())
    h = H()
    jz.LOG.addHandler(h)
    jz._VAROVANO.clear()
    os.environ["JAZYKY_DIR"] = vadne
    over("A15 vadné sady se ignorují: platná jen `oo` (bez sekcí), žádná výjimka", jz.jazyky() == ["oo"], jz.jazyky())
    over("A16 do logu přišlo varování k vadným sadám (json, lang, typ)", sum("ignoruje" in z for z in zachyt) >= 3, zachyt)
    over("A17 vestavěný jazyk (cs) se ze sady nikdy nenačte", jz.nacti("cs") is None and jz.nacti("en") is None)
    over("A18 info() bez sady / bez šablon vrací None (volající použije angličtinu)", jz.info("ww", "podpery", h=1, k=1, n=1, u=1) is None and jz.info("oo", "podpery", h=1, k=1, n=1, u=1) is None)
    # vadná šablona (neznámý placeholder, chybějící část) -> None + varování
    sab = os.path.join(TMP, "sab_vadne")
    os.makedirs(sab)
    json.dump({"lang": "oo", "plural": "one_other", "stul_shop": {"info": {"podpery": {"zaklad": "x {neznamy}", "bez": ".", "s_u1": {"one": " 1", "other": " n"}, "s_um": {"one": " 1", "other": " n"}}}}},
              open(os.path.join(sab, "oo.json"), "w"))
    os.environ["JAZYKY_DIR"] = sab
    over("A19 šablona s neznámým placeholderem = None + varování (ne výjimka)", jz.info("oo", "podpery", h=1, k=2, n=1, u=1) is None and any("vadna" in z or "vadná" in z for z in zachyt), zachyt[-2:])
    jz.LOG.removeHandler(h)
    del os.environ["JAZYKY_DIR"]

    print("== B) nástroje: zdroj, sestav")
    os.environ["JAZYKY_DIR"] = os.path.join(TMP, "sady_xx")                       # sestav zapisuje sem
    zdroj_xx = os.path.join(TMP, "zdroj_xx")
    kod, vystup = spust(zdroj_n.main, ["--lang", "xx", "--vystup", zdroj_xx])
    mods = Z.importuj_api()
    kod_polozky = Z.polozky_z_kodu(mods)
    over("B1 zdroj: soubory vznikly a obsahují všechny položky z kódu", kod == 0 and sum(len(json.load(open(os.path.join(zdroj_xx, n), encoding="utf-8"))["polozky"]) for n in Z.SOUBORY_SEKCI.values()) == len(kod_polozky) >= 300, (kod, vystup[-300:]))
    ids = [p["id"] for p in kod_polozky]
    over("B2 identifikátory jsou jedinečné a pokrývají všech 5 sekcí", len(set(ids)) == len(ids) and {p["sekce"] for p in kod_polozky} == set(Z.SOUBORY_SEKCI), len(set(ids)))
    pocty = {s: sum(1 for p in kod_polozky if p["sekce"] == s) for s in Z.SOUBORY_SEKCI}
    over("B3 sekce: texty 99+7, hlášky (28 důvodů, 14 zpráv, 15 názvů, 5 akcí, SSE, ano/ne), 10 šablon, 140 ovládání, 5 objednávky", pocty["stul_texty"] == 106 and pocty["stul_zpravy"] == 65 and pocty["stul_info"] == 10 and pocty["ovladani"] == 140 and pocty["objednavky"] == 5, pocty)
    doc0 = json.load(open(os.path.join(zdroj_xx, Z.SOUBORY_SEKCI["stul_info"]), encoding="utf-8"))
    pl = [p for p in doc0["polozky"] if p["typ"] == "plural"]
    over("B4 plurálové šablony mají u cílového jazyka objekt kategorií one/other a zdroj cs/en/sk jako objekty", len(pl) == 3 and all(set(p["xx"]) == {"one", "other"} for p in pl) and all(isinstance(p["cs"], dict) and "few" in p["cs"] for p in pl), [p["id"] for p in pl])
    over("B5 _navod: česky, zmiňuje abecedu jazyka, placeholdery, zakázaná slova a kategorie", "ASCII + ěš" in doc0["_navod"] and "{n}" in doc0["_navod"] and "Logiman" in doc0["_navod"] and "one, other" in doc0["_navod"])
    # znovuspuštění zachová vyplněné
    uprav_polozku(zdroj_xx, "stul_shop.TEXTY.w", lambda p: p.update({"xx": "RUCNE VYPLNENO"}))
    uprav_polozku(zdroj_xx, "stul_shop.TEXTY.help_mid", lambda p: p.update({"xx": "RUCNE {prah}"}))
    cesta_t = os.path.join(zdroj_xx, Z.SOUBORY_SEKCI["stul_texty"])
    doc_t = json.load(open(cesta_t, encoding="utf-8"))
    doc_t["polozky"] = [p for p in doc_t["polozky"] if p["id"] != "stul_shop.TEXTY.d"]                        # simulace nového řetězce v kódu (chybí v souboru)
    json.dump(doc_t, open(cesta_t, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    kod2, vystup2 = spust(zdroj_n.main, ["--lang", "xx", "--vystup", zdroj_xx])
    doc_t2 = json.load(open(cesta_t, encoding="utf-8"))
    by = {p["id"]: p for p in doc_t2["polozky"]}
    over("B6 znovuspuštění zachová vyplněné hodnoty a doplní nové řetězce (prázdné)", kod2 == 0 and by["stul_shop.TEXTY.w"]["xx"] == "RUCNE VYPLNENO" and by["stul_shop.TEXTY.help_mid"]["xx"] == "RUCNE {prah}" and by["stul_shop.TEXTY.d"]["xx"] == "", (kod2, by["stul_shop.TEXTY.d"]["xx"]))
    # prázdné = chyby
    kod3, vystup3 = spust(sestav_n.main, ["--lang", "xx", "--zdroj", zdroj_xx])
    over("B7 sestav: skoro vše prázdné → exit 1, sada se nezapíše", kod3 == 1 and not os.path.exists(os.path.join(os.environ["JAZYKY_DIR"], "xx.json")) and "NEZAPSALA" in vystup3 and "prázdné" in vystup3, vystup3[-300:])
    over("B8 sestav: zbývající nevyplněné položky jsou vypsané s id", "CHYBA    stul_shop.TEXTY.d" in vystup3 or "stul_shop.TEXTY.d:" in vystup3, vystup3[:400])
    # úplné vyplnění
    vypln_slozku(zdroj_xx, "xx", {"stul_shop.TEXTY.w": lambda v: v + " ěš"})
    kod4, vystup4 = spust(sestav_n.main, ["--lang", "xx", "--zdroj", zdroj_xx])
    over("B9 sestav: plně vyplněné soubory (včetně ě š v abecedě xx) projdou kontrolou bez zápisu", kod4 == 0 and "Kontrola prošla" in vystup4 and not os.path.exists(os.path.join(os.environ["JAZYKY_DIR"], "xx.json")), vystup4[-300:])
    kod5, vystup5 = spust(sestav_n.main, ["--lang", "xx", "--zdroj", zdroj_xx, "--apply"])
    cesta_sady = os.path.join(os.environ["JAZYKY_DIR"], "xx.json")
    sada = json.load(open(cesta_sady, encoding="utf-8")) if os.path.exists(cesta_sady) else {}
    over("B10 sestav --apply zapíše api/jazyky/xx.json se všemi sekcemi a pravidlem plurálu", kod5 == 0 and sada.get("lang") == "xx" and sada.get("plural") == "one_other" and len(sada["stul_shop"]["TEXTY"]) == 99 and len(sada["ovladani"]) == 140
         and sada["stul_shop"]["DUVODY"].get("_default") and set(sada["stul_shop"]["info"]) == {"podpery", "podpery_desky", "desky_deleny"} and sada["ano_ne"][0], (kod5, sada.get("lang")))
    over("B11 round-trip: ploché id sady = id položek z kódu", set(Z.ploche_z_sady(sada)) == {p["id"] for p in kod_polozky if not p["id"].startswith("potvrzeni.")} | {i for i in Z.ploche_z_sady(sada) if i.startswith("potvrzeni.")}, len(Z.ploche_z_sady(sada)))

    # mutace: kontrolní pravidla sestav
    def mutace(nazev, id_, fn, ocekavana_zprava, jazyk="xx", slozka=None):
        sl = kopie(slozka or zdroj_xx, "mut_" + re.sub(r"\W", "_", nazev))
        uprav_polozku(sl, id_, fn)
        k, v = spust(sestav_n.main, ["--lang", jazyk, "--zdroj", sl])
        over(f"B13 mutace: {nazev} → exit 1 a hláška „{ocekavana_zprava}“", k == 1 and ocekavana_zprava in v and id_ in v, v[-400:])
    mutace("chybí placeholder {prah}", "stul_shop.TEXTY.help_mid", lambda p: p.update({"xx": "[xx:help_mid] bez placeholderu"}), "placeholdery")
    mutace("změněný placeholder {prah} → {x}", "stul_shop.TEXTY.help_mid", lambda p: p.update({"xx": "[xx:help_mid] {x}"}), "placeholdery")
    mutace("navíc placeholder", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] {n}"}), "placeholdery")
    mutace("české ř v syntetickém jazyce (jen ě š)", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] ř"}), "znaky mimo abecedu")
    mutace("slovo Konfigurator", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] Konfigurator"}), "zakázané slovo")
    mutace("značka Logiman", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] Logiman"}), "zakázané slovo")
    mutace("chybí koncová mezera (TEXTY_AKCI.odebrano)", "stul_shop.TEXTY_AKCI.odebrano", lambda p: p.update({"xx": "[xx:odebrano]"}), "mezery")
    mutace("TODO v textu", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] TODO"}), "TODO")
    mutace("HTML značka", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] <b>"}), "HTML")
    mutace("příliš dlouhé", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] " + "x" * 400}), "podezřele dlouhé")
    mutace("plural: chybí kategorie other", "stul_shop.info.podpery.s_u1", lambda p: p.update({"xx": {"one": p["xx"]["one"], "other": ""}}), "prázdné")
    mutace("plural: nepovolená kategorie few (xx = one_other)", "stul_shop.info.podpery.s_u1", lambda p: p["xx"].update({"few": "[xx:few] {n}"}), "není pro jazyk")
    mutace("plural jako řetězec", "stul_shop.info.podpery.s_u1", lambda p: p.update({"xx": "[xx:x] {n}"}), "objekt s kategoriemi")
    mutace("zbytečný objekt u textu", "stul_shop.TEXTY.w", lambda p: p.update({"xx": {"other": "[xx:w]"}}), "řetězec, ne objekt")
    mutace("ovládání: zmizela {n}", "ovladani.Výřez {n}", lambda p: p.update({"xx": "[xx:vyrez]"}), "placeholdery")

    mutace("osamocená { v textu", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] a { b"}), "vadná šablona")
    mutace("osamocená } v textu", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] a } b"}), "vadná šablona")
    mutace("{{v}} místo {v} (regex ho vidí, .format ne)", "stul_shop.TEXTY_AKCI.roztahnout_h", lambda p: p.update({"xx": "[xx:roztahnout_h] {{v}}"}), "vadná šablona")
    mutace("placeholder s formátem {v:05d}", "stul_shop.TEXTY_AKCI.roztahnout_h", lambda p: p.update({"xx": "[xx:roztahnout_h] {v:05d}"}), "placeholdery")
    mutace("číselný placeholder {0}", "stul_shop.TEXTY.w", lambda p: p.update({"xx": "[xx:w] {0}"}), "placeholdery")

    # varování (nezastaví)
    sl = kopie(zdroj_xx, "var")
    uprav_polozku(sl, "stul_shop.DUVODY.panels", lambda p: p.update({"xx": p["en"]}))
    k, v = spust(sestav_n.main, ["--lang", "xx", "--zdroj", sl])
    over("B14 text shodný s angličtinou = varování, ne chyba", k == 0 and "varování" in v and "shodné s angličtinou" in v, v[-300:])

    print("== B2) reálné jazyky: de (one_other) a hu (jen other, maďarská písmena)")
    zdroj_de, zdroj_hu = os.path.join(TMP, "zdroj_de"), os.path.join(TMP, "zdroj_hu")
    kd, vd = spust(zdroj_n.main, ["--lang", "de", "--vystup", zdroj_de])
    kh, vh = spust(zdroj_n.main, ["--lang", "hu", "--vystup", zdroj_hu])
    over("B15 zdroj pro de a hu: 326 položek každý, de má u plurálu {one, other}, hu jen {other}", kd == 0 and kh == 0 and "Celkem %d položek" % len(kod_polozky) in vd and "Celkem %d položek" % len(kod_polozky) in vh, (vd[-200:], vh[-200:]))
    dd = json.load(open(os.path.join(zdroj_de, Z.SOUBORY_SEKCI["stul_info"]), encoding="utf-8"))["polozky"]
    dh = json.load(open(os.path.join(zdroj_hu, Z.SOUBORY_SEKCI["stul_info"]), encoding="utf-8"))["polozky"]
    over("B16 plurál: de {one, other}, hu {other}", all(set(p["de"]) == {"one", "other"} for p in dd if p["typ"] == "plural") and all(set(p["hu"]) == {"other"} for p in dh if p["typ"] == "plural"))
    nav_hu = json.load(open(os.path.join(zdroj_hu, Z.SOUBORY_SEKCI["stul_info"]), encoding="utf-8"))["_navod"]
    over("B17 _navod hu uvádí maďarská písmena a že `one` je volitelné; de uvádí äöüÄÖÜß", "áéíóöőúüű" in nav_hu and "volitelné" in nav_hu and "äöüÄÖÜß" in json.load(open(os.path.join(zdroj_de, Z.SOUBORY_SEKCI["stul_info"]), encoding="utf-8"))["_navod"])
    vypln_slozku(zdroj_de, "de")
    vypln_slozku(zdroj_hu, "hu")
    kd2, vd2 = spust(sestav_n.main, ["--lang", "de", "--zdroj", zdroj_de])
    kh2, vh2 = spust(sestav_n.main, ["--lang", "hu", "--zdroj", zdroj_hu])
    over("B18 tagované (ASCII) soubory de i hu projdou kontrolou", kd2 == 0 and kh2 == 0, (vd2[-200:], vh2[-200:]))

    def mut_jazyk(nazev, jazyk, slozka, id_, fn, ma_projit, znak=None):
        sl = kopie(slozka, f"mj_{jazyk}_" + re.sub(r"\W", "_", nazev))
        uprav_polozku(sl, id_, fn)
        k, v = spust(sestav_n.main, ["--lang", jazyk, "--zdroj", sl])
        if ma_projit:
            over(f"B19 {jazyk}: {nazev} → projde", k == 0, v[-300:])
        else:
            over(f"B19 {jazyk}: {nazev} → exit 1, znak {znak!r} nahlášen", k == 1 and "znaky mimo abecedu" in v and (znak is None or znak in v), v[-300:])
    for jazyk, slozka in (("de", zdroj_de), ("hu", zdroj_hu)):
        def nastav(text, jazyk=jazyk):
            return lambda p: p.update({jazyk: f"[xx:w] {text}"})
        id_ = "stul_shop.TEXTY.w"
        if jazyk == "de":
            mut_jazyk("ä ö ü ß Ä Ö Ü projdou", "de", slozka, id_, nastav("Größe äöüß ÄÖÜ Straße"), True)
            mut_jazyk("české ě", "de", slozka, id_, nastav("Breite ě"), False, "ě")
            mut_jazyk("české š ř ž", "de", slozka, id_, nastav("šířka"), False, "š")
            mut_jazyk("á í é ú (česko-slovenské i v němčině)", "de", slozka, id_, nastav("á"), False, "á")
            mut_jazyk("slovenské ľ ĺ ŕ ô", "de", slozka, id_, nastav("ľ"), False, "ľ")
            mut_jazyk("maďarské ő", "de", slozka, id_, nastav("ő"), False, "ő")
        else:
            mut_jazyk("á é í ó ö ő ú ü ű (a velká) projdou", "hu", slozka, id_, nastav("szélesség áéíóöőúüű ÁÉÍÓÖŐÚÜŰ"), True)
            mut_jazyk("ő ű samostatně projdou", "hu", slozka, id_, nastav("Hőtároló űrlap"), True)
            mut_jazyk("české ě", "hu", slozka, id_, nastav("ě"), False, "ě")
            mut_jazyk("české š č ř ž ý ů ť ď ň", "hu", slozka, id_, nastav("š"), False, "š")
            mut_jazyk("slovenské ľ ĺ ŕ ô ä", "hu", slozka, id_, nastav("ľ"), False, "ľ")
            mut_jazyk("německé ä a ß", "hu", slozka, id_, nastav("ä"), False, "ä")
            mut_jazyk("německé ß", "hu", slozka, id_, nastav("ß"), False, "ß")
    # hu: plural one je volitelné
    sl = kopie(zdroj_hu, "hu_one")
    uprav_polozku(sl, "stul_shop.info.podpery.s_u1", lambda p: p["hu"].update({"one": " [xx:hu:one] {n}"}))
    k, v = spust(sestav_n.main, ["--lang", "hu", "--zdroj", sl])
    over("B20 hu: kategorie `one` navíc (stejně jako other) projde", k == 0, v[-300:])
    sl = kopie(zdroj_hu, "hu_few")
    uprav_polozku(sl, "stul_shop.info.podpery.s_u1", lambda p: p["hu"].update({"few": " x {n}"}))
    k, v = spust(sestav_n.main, ["--lang", "hu", "--zdroj", sl])
    over("B21 hu: kategorie `few` není povolená", k == 1 and "není pro jazyk" in v, v[-300:])
    sl = kopie(zdroj_de, "de_bez_other")
    uprav_polozku(sl, "stul_shop.info.podpery.s_u1", lambda p: p["de"].update({"other": ""}))
    k, v = spust(sestav_n.main, ["--lang", "de", "--zdroj", sl])
    over("B22 de: prázdná kategorie other = chyba (one i other povinné)", k == 1 and "prázdné" in v, v[-300:])
    sl = kopie(zdroj_de, "de_one_bez_n")
    uprav_polozku(sl, "stul_shop.info.podpery.s_u1", lambda p: p["de"].update({"one": " ein Stützprofil wird ergänzt."}))
    k, v = spust(sestav_n.main, ["--lang", "de", "--zdroj", sl])
    over("B23 de: kategorie `one` smí vynechat {n} (ein …), `other` ne", k == 0, v[-300:])
    sl = kopie(zdroj_de, "de_other_bez_n")
    uprav_polozku(sl, "stul_shop.info.podpery.s_u1", lambda p: p["de"].update({"other": " Stützprofile werden ergänzt."}))
    k, v = spust(sestav_n.main, ["--lang", "de", "--zdroj", sl])
    over("B24 de: kategorie `other` bez {n} = chyba", k == 1 and "placeholdery" in v, v[-300:])
    sl = kopie(zdroj_de, "de_bez_potvrzeni")
    for id_ in ("potvrzeni.predmet", "potvrzeni.telo"):
        uprav_polozku(sl, id_, lambda p: p.update({"de": ""}))
    k, v = spust(sestav_n.main, ["--lang", "de", "--zdroj", sl, "--apply", "--vystup", os.path.join(TMP, "de_bez_potvrzeni.json")])
    sada_bez = json.load(open(os.path.join(TMP, "de_bez_potvrzeni.json"), encoding="utf-8")) if os.path.exists(os.path.join(TMP, "de_bez_potvrzeni.json")) else {}
    over("B27 volitelné potvrzení poptávky: obě položky prázdné = projde, sada nemá klíč `potvrzeni`", k == 0 and sada_bez and "potvrzeni" not in sada_bez and sada_bez["lang"] == "de", v[-300:])
    sl = kopie(zdroj_de, "de_potvrzeni_pul")
    uprav_polozku(sl, "potvrzeni.telo", lambda p: p.update({"de": ""}))
    k, v = spust(sestav_n.main, ["--lang", "de", "--zdroj", sl])
    over("B28 volitelné potvrzení: vyplněný předmět bez těla = chyba (vyplňují se společně)", k == 1 and "společně" in v, v[-300:])
    k, v = spust(sestav_n.main, ["--lang", "qq", "--zdroj", zdroj_de])
    over("B25 jazyk bez abecedy: srozumitelná chyba (exit 2)", k == 2 and "ABECEDY" in v, v)
    k, v = spust(sestav_n.main, ["--lang", "cs", "--zdroj", zdroj_de])
    over("B26 vestavěný jazyk (cs) nástroj odmítne (exit 2)", k == 2, v)

    print("== C) sada xx v kódu (podproces s čerstvým importem)")
    r = podproces("kontrola", os.environ["JAZYKY_DIR"])
    over("C1 sada xx: slovníky, schéma 30/35/40/41, resolve (12 scénářů), info věty, ovládání, SSE, LABELS, potvrzení, ano/ne, trasy – bez chyb", not r["chyby"], r["chyby"][:6])
    over("C2 trasa GET schema ?lang=xx proběhla na skutečném produktu", bool(r.get("extra", {}).get("produkt")), r.get("extra"))
    over("C3 načtení sady nic nevarovalo (úplná sada)", not [x for x in r["log"] if "chybi" in x or "prazdne" in x], r["log"][:3])

    print("== D) neúplná sada: anglická záloha + varování, žádný pád")
    neuplna = os.path.join(TMP, "sady_neuplna")
    os.makedirs(neuplna)
    s2 = copy.deepcopy(sada)
    del s2["stul_shop"]["TEXTY"]["w"]
    del s2["stul_shop"]["TEXTY"]["help_mid"]
    del s2["stul_shop"]["DUVODY"]["panels"]
    del s2["stul_shop"]["zpravy"]["PET_BEZ_STREDNI"]
    del s2["stul_shop"]["NAZVY_SLOTU"]["drawers"]
    del s2["ovladani"]["Pracovní deska"]
    del s2["objednavky"]["quote"]
    del s2["stul_shop_sse"]["DUVOD_SUPLIKY"]
    del s2["stul_shop"]["info"]
    del s2["ano_ne"]
    json.dump(s2, open(os.path.join(neuplna, "xx.json"), "w", encoding="utf-8"), ensure_ascii=False)
    r = podproces("fallback", neuplna)
    over("D1 chybějící klíče / šablony / ano-ne = angličtina, varování v logu, resolve funguje", not r["chyby"], r["chyby"][:6])
    zn = [pp["id"].split(".")[-1] for pp in kod_pol if pp["id"].startswith("stul_shop.zpravy.")]
    s4 = copy.deepcopy(sada)
    s4["stul_shop"]["TEXTY"]["w"] = "bad {nope}"
    s4["stul_shop"]["TEXTY"]["help_mid"] = "stray { brace {prah}"
    s4["stul_shop"]["DUVODY"]["sleeve_orezano"] = "orez {v"
    for nm in sorted(zn)[:2]:
        s4["stul_shop"]["zpravy"][nm] = "{{x}} { {zz}"
    s4["stul_shop"]["info"]["podpery"]["zaklad"] = "{h} {k} {"
    s4["stul_shop_sse"]["DUVOD_SUPLIKY"] = "{d} {q}"
    s4["ovladani"]["Výřez {n}"] = "Foo {n} {x}"
    s4["ovladani"]["Pracovní deska"] = "{"
    s4["objednavky"]["toptrans"] = "x {y}"
    s4["potvrzeni"] = {"predmet": "ok", "telo": "bad {foo}"}
    s4["ano_ne"] = ["", None]
    pos = os.path.join(TMP, "sady_poskozena")
    os.makedirs(pos)
    json.dump(s4, open(os.path.join(pos, "xx.json"), "w", encoding="utf-8"), ensure_ascii=False)
    r = podproces("poskozena", pos)
    over("D3 poškozené šablony (osamocená závorka, neznámé pole, formát): import nespadl, vadné hodnoty = angličtina, zbytek ze sady, resolve / schema bez výjimky", not r["chyby"], r["chyby"][:6])
    r = podproces("seznam", vadne)
    over("D2 adresář s vadnými sadami: import aplikace nespadl, platná jen oo", r.get("extra", {}).get("jazyky") == ["oo"] and not r["chyby"], r)

    print("== E) cs / en / sk beze změny")
    prazdny = os.path.join(TMP, "sady_prazdny")
    os.makedirs(prazdny)
    a = podproces("snimek", prazdny)
    b = podproces("snimek", os.environ["JAZYKY_DIR"])
    over("E1 otisk výstupů cs / en / sk (schema, resolve, věty, slovníky, LABELS, souhrn, ovládání) je STEJNÝ bez sad i se sadou xx", a.get("extra", {}).get("otisk") and a["extra"]["otisk"] == b.get("extra", {}).get("otisk"), (a.get("extra"), b.get("extra"), a["chyby"][:2], b["chyby"][:2]))
    over("E2 snímek pokrývá 200+ otisků (schémata, 3 systémy × 13 scénářů × 3 jazyky, věty, slovníky)", (a.get("extra") or {}).get("polozek", 0) >= 200, a.get("extra"))

    print("== F) parita")
    os.environ["JAZYKY_DIR"] = os.path.join(TMP, "sady_xx")
    k, v = spust(parita_n.main, ["--lang", "sk", "--ref", "sk", "--bez-db", "--json"])
    try:
        pj = json.loads(v[v.index("{"):])
    except ValueError:
        pj = {"mezer": -1, "kontroly": []}
    over("F1 sk proti sk: žádná mezera (parita nehlásí falešné poplachy; prázdné klíče ve zdroji nejsou mezera), exit 0", k == 0 and pj["mezer"] == 0, [r for r in pj.get("kontroly", []) if r["stav"] == "MEZERA"][:3])
    k, v = spust(parita_n.main, ["--lang", "en", "--ref", "sk", "--json"])
    pj_db = json.loads(v[v.index("{"):])
    db_radky = [r for r in pj_db["kontroly"] if r["vrstva"] == "db"]
    over("F5 vrstva DB (jen SELECT) vrací řádky pro texty, dokumenty a shop (nebo hlásí nedostupnost jako INFO)", len(db_radky) >= 5 or (len(db_radky) == 1 and db_radky[0]["stav"] == "INFO"), db_radky[:2])
    over("F6 výstup --json má lang, ref, mezer a kontroly se čtyřmi poli", all(set(r) == {"vrstva", "kontrola", "stav", "detail"} for r in pj_db["kontroly"]) and pj_db["lang"] == "en" and pj_db["ref"] == "sk" and pj_db["mezer"] == sum(r["stav"] == "MEZERA" for r in pj_db["kontroly"]))
    k, v = spust(parita_n.main, ["--lang", "xx", "--ref", "sk", "--bez-db", "--json"])
    pj = json.loads(v[v.index("{"):])
    server = [r for r in pj["kontroly"] if r["vrstva"] == "server"]
    over("F2 xx proti sk: vrstva server je v pořádku (úplná sada), vrstvy i18n a seo hlásí chybějící soubor / sekci, exit 1", k == 1 and server and all(r["stav"] == "OK" for r in server)
         and any(r["vrstva"] == "i18n" and r["stav"] == "MEZERA" for r in pj["kontroly"]) and any(r["vrstva"] == "seo" and r["stav"] == "MEZERA" for r in pj["kontroly"]), pj["kontroly"][:4])
    os.environ["JAZYKY_DIR"] = os.path.join(TMP, "sady_prazdny")
    k, v = spust(parita_n.main, ["--lang", "de", "--ref", "sk", "--bez-db"])
    over("F3 de bez sady: vrstva server hlásí chybějící sadu, tabulka čitelná (stav MEZERA), exit 1", k == 1 and "MEZERA" in v and "sada api/jazyky/de.json" in v and "neexistuje" in v, v[:500])
    os.environ["JAZYKY_DIR"] = os.path.join(TMP, "sady_xx")
    # úplná sada s jedním chybějícím klíčem
    s3 = copy.deepcopy(sada)
    del s3["stul_shop"]["TEXTY"]["d"]
    del s3["ovladani"]["Pracovní deska"]
    cil = os.path.join(TMP, "sady_chybi")
    os.makedirs(cil)
    json.dump(s3, open(os.path.join(cil, "xx.json"), "w", encoding="utf-8"), ensure_ascii=False)
    os.environ["JAZYKY_DIR"] = cil
    k, v = spust(parita_n.main, ["--lang", "xx", "--ref", "sk", "--bez-db", "--json"])
    pj = json.loads(v[v.index("{"):])
    srv = [r for r in pj["kontroly"] if r["vrstva"] == "server" and r["stav"] == "MEZERA"]
    over("F4 sada s chybějícími klíči: parita je vypíše (TEXTY.d, ovladani.Pracovní deska)", srv and "stul_shop.TEXTY.d" in srv[0]["detail"] and "ovladani.Pracovní deska" in srv[0]["detail"], srv[:1])

    print("== G) šablony z kódu složené přes jazyky.info = původní věty")
    os.environ["JAZYKY_DIR"] = os.path.join(TMP, "sady_g")
    os.makedirs(os.environ["JAZYKY_DIR"])
    SH = mods["stul_shop"]
    shody = rozdily = 0
    for lg, kod in (("cs", "xa"), ("en", "xb"), ("sk", "xc")):
        sab = Z.sablony_info(SH, jz, lg)
        json.dump({"lang": kod, "plural": jz.PLURAL_PRO_JAZYK[lg], "stul_shop": {"info": sab}}, open(os.path.join(os.environ["JAZYKY_DIR"], f"{kod}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        for n in range(0, 14):
            for u in (1, 2, 3):
                inf = {"kraceni_mm": 40, "podpery": n, "urovni": u, "hloubka_mm": 1000}
                if SH.text_podpery(lg, inf) == SH.text_podpery(kod, inf):
                    shody += 1
                else:
                    rozdily += 1
        for n in range(1, 14):
            for sup in (False, True):
                inf = {"podpery": n, "suplik": sup, "hloubka_mm": 1000}
                if SH.text_podpery_desky(lg, inf) == SH.text_podpery_desky(kod, inf):
                    shody += 1
                else:
                    rozdily += 1
        for rezim in ("ram", "noha"):
            if SH.text_desky_deleny(lg, rezim, 74.0, (2070.0, 2800.0)) == SH.text_desky_deleny(kod, rezim, 74.0, (2070.0, 2800.0)):
                shody += 1
            else:
                rozdily += 1
    over(f"G1 šablony ze zdroje dávají přesně stejné věty jako kód (cs / en / sk; {shody} případů)", shody == 210 and rozdily == 0, (shody, rozdily))
    # hu: pravidlo `other`, jednotné po číslovce; šablona se stejným tvarem one i other
    json.dump({"lang": "hu", "plural": "other", "stul_shop": {"info": {"podpery_desky": {"zaklad": {"other": "Mélység {h}: {n} db"}, "konec": ".", "konec_suplik": " (fiók)."}}}},
              open(os.path.join(os.environ["JAZYKY_DIR"], "hu.json"), "w", encoding="utf-8"), ensure_ascii=False)
    t1 = SH.text_podpery_desky("hu", {"podpery": 1, "suplik": False, "hloubka_mm": 1000})
    t5 = SH.text_podpery_desky("hu", {"podpery": 5, "suplik": True, "hloubka_mm": 1000})
    over("G2 hu (pravidlo other): n=1 i n=5 použijí tvar other; chybějící ostatní šablony = angličtina", t1 == "Mélység 1000: 1 db." and t5 == "Mélység 1000: 5 db (fiók)." and "supporting profile" in SH.text_podpery("hu", {"kraceni_mm": 4, "podpery": 1, "urovni": 1, "hloubka_mm": 900}), (t1, t5))

    ok = sum(vysl)
    print(f"\nVYSLEDEK jazykove sady serveru: {ok}/{len(vysl)} OK")
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if ok == len(vysl) else 1


if __name__ == "__main__":
    sys.exit(main())
