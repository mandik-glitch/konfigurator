#!/usr/bin/env python3
"""Overeni a sestaveni jazykove sady serveru (bot16, 2026-10-07): vyplnene soubory docs/jazyky/<jazyk>/NN_*.json -> api/jazyky/<jazyk>.json.

Bez --apply JEN KONTROLA (nic se nezapise). Kazda polozka musi byt vyplnena a projit:
  * pole <jazyk> je vyplnene (retezec, u `typ: plural` objekt kategorii podle pravidla plurálu jazyka; u pravidla `other` je `one` volitelne); polozky s `volitelne: true`
    (sablona potvrzeni poptavky, zatim vypnuta) smi zustat prazdne - predmet a telo se ale vyplnuji SPOLECNE;
  * placeholdery {n} {d} {w} {h} {t1} ... presne jako v poli `placeholdery` (v kategorii `one` smi chybet jen {n}) a text musi byt platna sablona (zadna osamocena { nebo }, {{n}}, {n:05d}, {0});
  * ZNAKY: kazdy znak mimo abecedu jazyka (api/jazyky.py ABECEDY: ASCII + obecna typografie + pismena jazyka) je CHYBA - napr. cesko-slovenska diakritika v nemcine / madarstine;
    legitimni znaky jazyka (hu: ő ű á é í ó ö ú ü) projdou;
  * zadna znacka ani interni slova (Logiman, konfigurator / konfigurátor, vandrawee), zadne TODO / ???, zadne HTML;
  * mezery / strednik / tecka na zacatku a na konci stejne jako v anglictine (sablony navazuji na `zaklad`);
  * rozumna delka (do 3x anglicky text + 60 znaku). VAROVANI (nezastavi): shodne s anglictinou / s cestinou, dvojite mezery.
S --apply a bez chyb zapise api/jazyky/<jazyk>.json (adresar prepise env JAZYKY_DIR). Sada se projevi po nasazeni API (plánované 0:00 / 12:30).

Pouziti:
  api/venv/bin/python3 scripts/miniweb_jazyk_sestav.py --lang de                 # kontrola
  api/venv/bin/python3 scripts/miniweb_jazyk_sestav.py --lang hu --apply         # zapis sady
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _jazyky_zdroj as Z  # noqa: E402

MAX_DELKA_NASOBEK, MAX_DELKA_PRIDAT = 3, 60
_TODO_RE = re.compile(r"\b(?:TODO|FIXME|XXX)\b|\?\?\?")


def _okraje(t):
    z = t[:len(t) - len(t.lstrip())]
    k = t[len(t.rstrip()):]
    return z, k


def _kontrola_retezce(lang, jz, id_, t, ref_en, ref_cs, pozadovane, kategorie=None):
    """(chyby, varovani) pro jeden retezec. `pozadovane` = mnozina placeholderu z en; kategorie one smi vynechat {n}."""
    chyby, var = [], []
    nazev = id_ if kategorie is None else f"{id_} [{kategorie}]"
    if not isinstance(t, str) or not t.strip():
        return [(nazev, "prázdné / není řetězec")], var
    if _TODO_RE.search(t):
        chyby.append((nazev, "obsahuje TODO / ???"))
    if "<" in t and "<" not in (ref_en or ""):
        chyby.append((nazev, "obsahuje HTML značku (v angličtině žádná není)"))
    ph = jz.placeholdery(t)
    dovolene = [set(pozadovane)]
    if kategorie == "one":
        dovolene.append(set(pozadovane) - {"{n}"})
    if ph not in dovolene:
        chyby.append((nazev, f"placeholdery {sorted(ph)} ≠ požadované {sorted(pozadovane)}"))
    else:
        fc = jz.format_chyba(t, {x[1:-1] for x in pozadovane}, presne=True, volitelne={"n"} if kategorie == "one" else ())
        if fc:
            chyby.append((nazev, f"vadná šablona: {fc}"))          # osamocená { }, {{n}}, {n:05d}, {0} ... - server by za běhu spadl na .format()
    spatne = jz.nepovolene_znaky(lang, t)
    if spatne:
        chyby.append((nazev, f"znaky mimo abecedu jazyka {lang}: {jz.popis_znaku(spatne)}"))
    m = jz.ZAKAZANA_SLOVA_RE.search(t)
    if m:
        chyby.append((nazev, f"zakázané slovo (značka / interní název): {m.group(0)!r}"))
    if ref_en is not None:
        if _okraje(t) != _okraje(ref_en):
            chyby.append((nazev, f"mezery na začátku/konci {_okraje(t)!r} ≠ {_okraje(ref_en)!r} jako v angličtině (šablony navazují na `zaklad`)"))
        if len(t) > MAX_DELKA_NASOBEK * len(ref_en) + MAX_DELKA_PRIDAT:
            chyby.append((nazev, f"podezřele dlouhé ({len(t)} znaků, angličtina {len(ref_en)})"))
        if t == ref_en and len(t.strip()) > 20:
            var.append((nazev, "shodné s angličtinou (nepřeloženo?)"))
    if ref_cs and t == ref_cs and len(t.strip()) > 20:
        var.append((nazev, "shodné s češtinou (nepřeloženo?)"))
    if "  " in t:
        var.append((nazev, "dvojitá mezera"))
    return chyby, var


def _ref_kategorie(ref, kat):
    if isinstance(ref, dict):
        return ref.get(kat) or ref.get("other") or next((v for v in ref.values() if isinstance(v, str)), None)
    return ref


def validuj(lang, slozka, jz):
    """Vraci (hodnoty {id: hodnota}, chyby [(id, zprava)], varovani, pocty {sekce: [vyplneno, celkem]})."""
    chyby, varovani, hodnoty, pocty, videno, volitelne_prazdne = [], [], {}, {}, set(), set()
    pravidlo = jz.PLURAL_PRO_JAZYK.get(lang, "one_other")
    povinne = jz.KATEGORIE_PRO_PRAVIDLO[pravidlo]
    volitelne = ("one",) if pravidlo == "other" else ()
    for sekce, nazev in Z.SOUBORY_SEKCI.items():
        cesta = os.path.join(slozka, nazev)
        pocty[sekce] = [0, 0]
        if not os.path.exists(cesta):
            chyby.append((nazev, "soubor chybí (spusť miniweb_jazyk_zdroj.py)"))
            continue
        try:
            doc = json.load(open(cesta, encoding="utf-8"))
        except ValueError as e:
            chyby.append((nazev, f"neplatný JSON: {e}"))
            continue
        if doc.get("lang") != lang:
            chyby.append((nazev, f"pole lang je {doc.get('lang')!r}, očekáváno {lang!r}"))
            continue
        for p in doc.get("polozky", []):
            id_ = p.get("id")
            if not isinstance(id_, str) or id_ in videno:
                chyby.append((nazev, f"chybějící nebo duplicitní id {id_!r}"))
                continue
            videno.add(id_)
            pocty[sekce][1] += 1
            typ = p.get("typ", "text")
            h = p.get(lang)
            pozadovane = set(p.get("placeholdery") or jz.placeholdery(p.get("en")))
            en, cs = p.get("en"), p.get("cs")
            chyb0 = len(chyby)
            if p.get("volitelne") and (h is None or (isinstance(h, str) and not h.strip())):
                volitelne_prazdne.add(id_)                   # volitelna polozka (potvrzeni poptavky) nechana prazdna: preskoci se, sada ji nebude mit
                pocty[sekce][0] += 1
                continue
            if typ == "plural":
                if not isinstance(h, dict):
                    chyby.append((id_, f"`{lang}` musí být objekt s kategoriemi {', '.join(povinne)}"))
                    continue
                for kat in h:
                    if kat not in povinne and kat not in volitelne:
                        chyby.append((id_, f"kategorie {kat!r} není pro jazyk {lang} (pravidlo {pravidlo}) povolená"))
                kategorie_ok = {}
                for kat in povinne + volitelne:
                    t = h.get(kat)
                    if kat in volitelne and (t is None or (isinstance(t, str) and not t.strip())):
                        continue
                    c, v = _kontrola_retezce(lang, jz, id_, t, _ref_kategorie(en, kat), _ref_kategorie(cs, kat), pozadovane, kat)
                    chyby.extend(c)
                    varovani.extend(v)
                    kategorie_ok[kat] = t
                hodnoty[id_] = kategorie_ok
            else:
                if isinstance(h, dict):
                    chyby.append((id_, f"`{lang}` má být řetězec, ne objekt"))
                    continue
                c, v = _kontrola_retezce(lang, jz, id_, h, en if isinstance(en, str) else None, cs if isinstance(cs, str) else None, pozadovane)
                chyby.extend(c)
                varovani.extend(v)
                hodnoty[id_] = h
            if len(chyby) == chyb0:
                pocty[sekce][0] += 1
    pot = [i for i in ("potvrzeni.predmet", "potvrzeni.telo") if i in videno]
    if len(pot) == 2 and len(volitelne_prazdne & set(pot)) == 1:
        chyby.append(("potvrzeni", "předmět a tělo potvrzení poptávky se vyplňují společně (jedno je vyplněné, druhé prázdné)"))
    return hodnoty, chyby, varovani, pocty


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kontrola a sestaveni jazykove sady serveru.")
    ap.add_argument("--lang", required=True)
    ap.add_argument("--zdroj", help="slozka vyplnenych souboru (vychozi docs/jazyky/<jazyk>)")
    ap.add_argument("--vystup", help="cilovy soubor (vychozi <adresar sad>/<jazyk>.json)")
    ap.add_argument("--api", help="kopie API (vychozi zive repo)")
    ap.add_argument("--apply", action="store_true", help="zapsat sadu (jinak jen kontrola)")
    ap.add_argument("--json", action="store_true", help="vystup jako JSON")
    a = ap.parse_args(argv)
    jz = Z.jazyky_modul(a.api)
    if not jz.KOD_RE.match(a.lang) or a.lang in jz.VESTAVENE:
        print(f"CHYBA: jazyk {a.lang!r} musi byt dvoupismenny kod jiny nez {', '.join(jz.VESTAVENE)}.", file=sys.stderr)
        return 2
    if a.lang not in jz.ABECEDY:
        print(f"CHYBA: jazyk {a.lang!r} nema abecedu v api/jazyky.py (ABECEDY) - doplnte jeden radek.", file=sys.stderr)
        return 2
    slozka = os.path.abspath(a.zdroj or os.path.join(Z.DOCS, a.lang))
    hodnoty, chyby, varovani, pocty = validuj(a.lang, slozka, jz)
    celkem = sum(v[1] for v in pocty.values())
    ok = sum(v[0] for v in pocty.values())
    zapsano = None
    if not chyby and a.apply:
        sada = Z.sestav_sadu(a.lang, hodnoty, jz.PLURAL_PRO_JAZYK.get(a.lang, "one_other"), jz)
        cil = os.path.abspath(a.vystup or os.path.join(jz.adresar(), f"{a.lang}.json"))
        os.makedirs(os.path.dirname(cil), exist_ok=True)
        with open(cil, "w", encoding="utf-8") as f:
            json.dump(sada, f, ensure_ascii=False, indent=1)
            f.write("\n")
        zapsano = cil
    if a.json:
        print(json.dumps({"lang": a.lang, "polozek": celkem, "ok": ok, "chyby": chyby, "varovani": varovani, "pocty": pocty, "zapsano": zapsano}, ensure_ascii=False, indent=1))
    else:
        print(f"Jazyk {a.lang}: {ok}/{celkem} položek v pořádku, {len(chyby)} chyb, {len(varovani)} varování")
        for sekce, v in pocty.items():
            print(f"  {Z.SOUBORY_SEKCI[sekce]:30s} {v[0]:4d} / {v[1]:4d}")
        for id_, zprava in chyby[:200]:
            print(f"  CHYBA    {id_}: {zprava}")
        if len(chyby) > 200:
            print(f"  ... a dalších {len(chyby) - 200} chyb")
        for id_, zprava in varovani[:50]:
            print(f"  varování {id_}: {zprava}")
        if zapsano:
            print(f"ZAPSÁNO {zapsano}")
            print("  Dál: commit souboru; sada se načte při startu API (plánované nasazení 0:00 / 12:30 reaguje jen na commity do api/*.py - viz docs/jazyky/README.md, past 1);")
            print(f"  úplnost vrstev: scripts/miniweb_jazyk_parita.py --lang {a.lang}")
        elif chyby:
            print("Sada se NEZAPSALA - oprav chyby.")
        else:
            print("Kontrola prošla; zapíše se s --apply.")
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
