#!/usr/bin/env python3
"""Jazykova UPLNOST mini-shopu napric vrstvami (bot16, 2026-10-07; JEN CTENI): cilovy jazyk proti referencnimu (vychozi sk).

Vrstvy (kazda kontrola = radek tabulky; MEZERA = neco chybi; exit 1, kdyz je aspon jedna mezera):
  server   serverove texty (docs/jazyky/README.md): polozky z kodu (stul_shop ...) vs sada api/jazyky/<jazyk>.json (cs / en / sk jsou v kodu)
  i18n     webapp/miniweb/i18n/<jazyk>.json vs <ref>.json: klice a placeholdery {x}
  seo      api/miniweb_seo_sablony.json sekce <jazyk> vs <ref> (rekurzivne klice) + PATHS[<jazyk>] v api/miniweb_seo.py
  db       DB (jen SELECT): texty kategorii a produktu (name, summary, description, delivery, url_slug), dokumenty (druh / stav), storefront + radek shopu pro jazyk
  pripni   webapp/pripni-cokoli/texty.json: jazyk v `_aktivni`, vsechny klice jako cestina

Pouziti (z korene repa):
  api/venv/bin/python3 scripts/miniweb_jazyk_parita.py --lang en --ref sk
  api/venv/bin/python3 scripts/miniweb_jazyk_parita.py --lang de --json
  --bez-db  preskoci vrstvu db;  --bez-kodu  preskoci import aplikace (vrstva server pak porovna jen sadu s kodem uz nacteným ze souboru zdroje - nepouzivat bez nutnosti)
"""
import argparse
import ast
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _jazyky_zdroj as Z  # noqa: E402

PLACEHOLDER_RE = re.compile(r"\{[A-Za-z0-9_.]+\}")
IGNOROVANE_KLICE_SEO = {"poznamka", "_zdroj"}
SEO_JEDNOTLIVE_JAZYKU = {"host", "brand", "locale", "lang"}        # hodnoty specificke pro shop (jazyk i domenu); klic musi existovat, text se nesrovnava


def radek(vrstva, kontrola, stav, detail=""):
    return {"vrstva": vrstva, "kontrola": kontrola, "stav": stav, "detail": detail}


def _seznam(polozky, n=6):
    polozky = list(polozky)
    return ", ".join(str(p) for p in polozky[:n]) + (f" … (+{len(polozky) - n})" if len(polozky) > n else "")


# ------------------------------------------------------------------ server
def vrstva_server(lang, ref, mods, jz):
    out = []
    kod = Z.polozky_z_kodu(mods)
    ids = {p["id"]: p for p in kod}

    def hodnoty(l):
        if l in jz.VESTAVENE:
            return {i: p[l] for i, p in ids.items() if (p[l] if isinstance(p[l], str) else any(p[l].values()))}
        sada = jz.nacti(l)
        if sada is None:
            return None
        return {i: v for i, v in Z.ploche_z_sady(sada).items() if (v if isinstance(v, str) else any(v.values()))}
    h_lang, h_ref = hodnoty(lang), hodnoty(ref)
    if h_lang is None:
        out.append(radek("server", f"sada api/jazyky/{lang}.json", "MEZERA", f"neexistuje (nebo je vadná); položek v kódu: {len(ids)}; referenční {ref}: {len(h_ref or {})}"))
        return out
    chybi = [i for i in (h_ref or {}) if i not in h_lang and not (isinstance(ids[i]["en"], str) and i.startswith("potvrzeni."))]
    out.append(radek("server", f"položky vůči {ref} ({len(h_ref or {})})", "OK" if not chybi else "MEZERA", f"vyplněno {len(h_lang)}" + (f"; chybí {len(chybi)}: {_seznam(chybi)}" if chybi else "")))
    navic = [i for i in h_lang if i not in ids]
    out.append(radek("server", "položky mimo kód (zastaralé)", "OK" if not navic else "MEZERA", _seznam(navic)))
    return out


# ------------------------------------------------------------------ i18n
def vrstva_i18n(lang, ref, jz):
    out = []
    cesta = lambda l: os.path.join(Z.REPO, "webapp", "miniweb", "i18n", f"{l}.json")  # noqa: E731
    if not os.path.exists(cesta(lang)):
        n = len(json.load(open(cesta(ref), encoding="utf-8"))) if os.path.exists(cesta(ref)) else 0
        return [radek("i18n", f"webapp/miniweb/i18n/{lang}.json", "MEZERA", f"soubor neexistuje ({ref}.json má {n} klíčů)")]
    a = json.load(open(cesta(lang), encoding="utf-8"))
    b = json.load(open(cesta(ref), encoding="utf-8"))
    chybi = sorted(set(b) - set(a))
    navic = sorted(set(a) - set(b))
    out.append(radek("i18n", f"klíče vůči {ref} ({len(b)})", "OK" if not chybi else "MEZERA", f"{lang}: {len(a)} klíčů" + (f"; chybí {len(chybi)}: {_seznam(chybi)}" if chybi else "")))
    out.append(radek("i18n", f"klíče navíc oproti {ref}", "OK" if not navic else "INFO", _seznam(navic)))
    ph = [k for k in set(a) & set(b) if isinstance(a[k], str) and isinstance(b[k], str) and set(PLACEHOLDER_RE.findall(a[k])) != set(PLACEHOLDER_RE.findall(b[k]))]
    out.append(radek("i18n", "placeholdery {x} shodné s referencí", "OK" if not ph else "MEZERA", _seznam(sorted(ph))))
    prazdne = [k for k, v in a.items() if isinstance(v, str) and not v.strip() and isinstance(b.get(k), str) and b[k].strip()]
    out.append(radek("i18n", f"žádný prázdný text tam, kde {ref} text má", "OK" if not prazdne else "MEZERA", _seznam(sorted(prazdne))))
    znaky, znacka = {}, []
    for k, v in a.items():
        if not isinstance(v, str):
            continue
        if lang in jz.ABECEDY:
            for ch in jz.nepovolene_znaky(lang, v):
                znaky.setdefault(ch, []).append(k)
        if jz.ZAKAZANA_SLOVA_RE.search(v):
            znacka.append(k)
    if lang in jz.ABECEDY:
        out.append(radek("i18n", f"jen znaky abecedy jazyka {lang} (ASCII + typografie + {jz.ABECEDY[lang] or 'žádná písmena navíc'})", "OK" if not znaky else "MEZERA",
                         "; ".join(f"{ch!r} (U+{ord(ch):04X}) v {len(ks)} klíčích: {_seznam(ks, 3)}" for ch, ks in znaky.items())))
    else:
        out.append(radek("i18n", "abeceda jazyka", "INFO", f"jazyk {lang} nemá řádek v ABECEDY (api/jazyky.py) - znaky se nekontrolují"))
    out.append(radek("i18n", "žádná značka ani interní slova (Logiman, konfigurátor, vandrawee)", "OK" if not znacka else "MEZERA", _seznam(sorted(znacka))))
    return out


# ------------------------------------------------------------------ seo
def _seo_paths(lang):
    """PATHS z api/miniweb_seo.py bez importu aplikace (AST), stejne jako gen_miniweb_vhost.py."""
    src = open(os.path.join(Z.API, "miniweb_seo.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PATHS" for t in node.targets):
            return ast.literal_eval(node.value).get(lang)
    return None


def _rozdil_klicu(a, b, cesta=""):
    """Klice v b (reference), ktere chybi v a; rekurzivne."""
    chybi = []
    for k, v in b.items():
        if k in IGNOROVANE_KLICE_SEO:
            continue
        if k not in a:
            chybi.append(f"{cesta}{k}")
        elif isinstance(v, dict) and isinstance(a[k], dict):
            chybi.extend(_rozdil_klicu(a[k], v, f"{cesta}{k}."))
    return chybi


def vrstva_seo(lang, ref):
    s = json.load(open(os.path.join(Z.API, "miniweb_seo_sablony.json"), encoding="utf-8"))
    out = []
    if lang not in s:
        out.append(radek("seo", f"sekce {lang} v miniweb_seo_sablony.json", "MEZERA", f"neexistuje (referenční {ref}: {len(s.get(ref, {}))} sekcí)"))
    else:
        chybi = _rozdil_klicu(s[lang], s.get(ref, {}))
        out.append(radek("seo", f"klíče šablon vůči {ref}", "OK" if not chybi else "MEZERA", (f"chybí {len(chybi)}: {_seznam(chybi, 12)}" if chybi else f"{len(s[lang])} sekcí")))
        prazdne = [k for k, v in s[lang].items() if isinstance(v, str) and not v.strip()]
        out.append(radek("seo", "žádná prázdná hodnota na nejvyšší úrovni", "OK" if not prazdne else "MEZERA", _seznam(prazdne)))
    p = _seo_paths(lang)
    out.append(radek("seo", f"PATHS[{lang}] (hezké adresy) v api/miniweb_seo.py", "OK" if p else "MEZERA", "" if p else f"chybí - doplnit /kategorie/ /produkt/ /kontakt … (reference {ref}: {_seo_paths(ref)})"))
    return out


# ------------------------------------------------------------------ db
def vrstva_db(lang, ref):
    try:
        import _env
        conn = _env.get_conn(env=_env.load_env(Z.najdi_env()))
    except Exception as e:                      # noqa: BLE001
        return [radek("db", "spojení s DB", "INFO", f"nedostupné ({type(e).__name__}) - vrstva přeskočena")]
    out = []
    try:
        cur = conn.cursor()

        def pocet(tabulka, l, kde=""):
            cur.execute(f"SELECT status, COUNT(*) n FROM {tabulka} WHERE lang=%s {kde} GROUP BY status", (l,))
            return {r["status"]: r["n"] for r in cur.fetchall()}
        for tabulka, polozky, povinna in (("miniweb_category_texts", "kategorie", ("name", "url_slug")),
                                          ("miniweb_product_texts", "produkty", ("name", "summary", "description", "delivery", "url_slug"))):
            a, b = pocet(tabulka, lang), pocet(tabulka, ref)
            sc_a, sc_b = a.get("approved", 0), b.get("approved", 0)
            stav = "OK" if sc_a >= sc_b else "MEZERA"
            out.append(radek("db", f"{polozky}: schválené texty vůči {ref} ({sc_b})", stav, f"{lang}: schváleno {sc_a}, ostatní stavy {({k: v for k, v in a.items() if k != 'approved'} or '-')}"))
            cur.execute("SELECT COUNT(*) n, " + ", ".join(f"SUM({c} IS NULL OR {c}='') AS `{c}`" for c in povinna) + f" FROM {tabulka} WHERE lang=%s", (lang,))
            r = cur.fetchone()
            prazdne = {c: int(r[c] or 0) for c in povinna if int(r[c] or 0)}
            out.append(radek("db", f"{polozky}: povinná pole ({', '.join(povinna)}) vyplněná", "OK" if not prazdne else "MEZERA",
                             "" if not prazdne else "prázdné z %d řádků: %s" % (r["n"], ", ".join(f"{c} ×{n}" for c, n in prazdne.items()))
                             + ("; prázdný url_slug = adresa se vezme ze základního slugu (není v jazyce shopu)" if "url_slug" in prazdne else "")))
        cur.execute("SELECT kind, status FROM miniweb_documents WHERE lang=%s", (lang,))
        d_l = {(r["kind"], r["status"]) for r in cur.fetchall()}
        cur.execute("SELECT kind, status FROM miniweb_documents WHERE lang=%s", (ref,))
        d_r = {r["kind"] for r in cur.fetchall() if r["status"] == "approved"}
        schvalene = {k for k, s in d_l if s == "approved"}
        chybi = sorted(d_r - schvalene)
        out.append(radek("db", f"právní dokumenty (schválené druhy vůči {ref}: {', '.join(sorted(d_r)) or '-'})", "OK" if not chybi else "MEZERA",
                         f"{lang}: schváleno {', '.join(sorted(schvalene)) or '-'}" + (f"; chybí {', '.join(chybi)}" if chybi else "") + (f"; v návrhu: {', '.join(sorted(k for k, s in d_l if s != 'approved'))}" if any(s != 'approved' for k, s in d_l) else "")))
        cur.execute("SELECT id, slug, primary_domain, status FROM car_storefronts WHERE kind='miniweb' AND lang=%s", (lang,))
        sf = cur.fetchall()
        if not sf:
            out.append(radek("db", f"storefront shopu pro jazyk {lang}", "MEZERA", "neexistuje (zakládá bot5: scripts/miniweb_shop.py)"))
        for r in sf:
            cur.execute("SELECT orders_enabled, price_mode, countries FROM miniweb_shops WHERE storefront_id=%s", (r["id"],))
            sh = cur.fetchone()
            out.append(radek("db", f"storefront #{r['id']} {r['slug']} ({r['primary_domain']})", "OK" if sh else "MEZERA",
                             f"stav {r['status']}" + (f"; shop: země {sh['countries']}, ceny {sh['price_mode']}, objednávky {'zapnuty' if sh['orders_enabled'] else 'vypnuty'}" if sh else "; chybí řádek v miniweb_shops")))
    finally:
        conn.rollback()
        conn.close()
    return out


# ------------------------------------------------------------------ pripni cokoli
def _povinne_klice(sekce):
    """Klice sekce, ktere nesou text (prazdny retezec = zamerne prazdny klic, ne povinny preklad)."""
    return {k for k, v in sekce.items() if not k.startswith("_") and not (isinstance(v, str) and not v.strip())}


def vrstva_pripni(lang, ref):
    cesta = os.path.join(Z.REPO, "webapp", "pripni-cokoli", "texty.json")
    if not os.path.exists(cesta):
        return [radek("pripni", "webapp/pripni-cokoli/texty.json", "INFO", "soubor neexistuje")]
    t = json.load(open(cesta, encoding="utf-8"))
    out = []
    if lang not in t:
        return [radek("pripni", f"sekce {lang} v texty.json", "MEZERA", f"není (referenční {ref}: {len(t.get(ref, {}))} klíčů)")]
    for zdroj in dict.fromkeys((ref, "cs")):
        chybi = sorted(_povinne_klice(t.get(zdroj, {})) - set(t[lang]))
        out.append(radek("pripni", f"klíče textů vůči {zdroj}" + (" (zdrojový jazyk)" if zdroj == "cs" and zdroj != ref else ""), "OK" if not chybi else "MEZERA", _seznam(chybi)))
    aktivni = t.get("_aktivni") or []
    out.append(radek("pripni", "jazyk v `_aktivni` (volba jazyka na stránce)", "OK" if lang in aktivni else "MEZERA", f"_aktivni = {aktivni}; zapíná se až po ověření terminologie (bot7)"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jazykova uplnost mini-shopu napric vrstvami (jen cteni).")
    ap.add_argument("--lang", required=True)
    ap.add_argument("--ref", default="sk")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--bez-db", action="store_true")
    ap.add_argument("--api", help="kopie API ke cteni kodu (vychozi zive repo)")
    a = ap.parse_args(argv)
    for l in (a.lang, a.ref):
        if not re.match(r"^[a-z]{2}$", l):
            print(f"CHYBA: jazyk {l!r} musi byt dvoupismenny kod", file=sys.stderr)
            return 2
    mods = Z.importuj_api(a.api)
    jz = mods["jazyky"]
    radky = []
    radky += vrstva_server(a.lang, a.ref, mods, jz)
    radky += vrstva_i18n(a.lang, a.ref, jz)
    radky += vrstva_seo(a.lang, a.ref)
    if not a.bez_db:
        radky += vrstva_db(a.lang, a.ref)
    radky += vrstva_pripni(a.lang, a.ref)
    mezery = [r for r in radky if r["stav"] == "MEZERA"]
    if a.json:
        print(json.dumps({"lang": a.lang, "ref": a.ref, "mezer": len(mezery), "kontroly": radky}, ensure_ascii=False, indent=1))
    else:
        print(f"Jazyková úplnost: {a.lang} ({jz.NAZVY_JAZYKU.get(a.lang, a.lang)}) vůči {a.ref} ({jz.NAZVY_JAZYKU.get(a.ref, a.ref)})")
        print(f"{'vrstva':8s} {'stav':7s} kontrola | detail")
        for r in radky:
            print(f"{r['vrstva']:8s} {r['stav']:7s} {r['kontrola']}" + (f" | {r['detail']}" if r["detail"] else ""))
        print(f"\nMezer: {len(mezery)} z {len(radky)} kontrol" + ("" if mezery else " - jazyk je úplný"))
    return 1 if mezery else 0


if __name__ == "__main__":
    sys.exit(main())
