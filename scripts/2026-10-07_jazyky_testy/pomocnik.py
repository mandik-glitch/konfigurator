#!/usr/bin/env python3
"""Pomocnik testu jazykovych sad (bot16, 2026-10-07): spousti se jako PODPROCES s cerstvym importem aplikace a nastavenym JAZYKY_DIR (sady se pripojuji pri importu modulu).
Rezimy (argv[1]): kontrola | snimek | fallback | poskozena | seznam. Vystup = jeden JSON na stdout (posledni radek); log varovani jazyka se zachytava do pole "log".
Zadne zapisy do DB, soubory jdou do docasnych adresaru (PRIVATE_FILES_DIR, CONTENT_UPLOAD_DIR).
"""
import hashlib
import json
import logging
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import _jazyky_zdroj as Z  # noqa: E402

LOG = []


class _Zachyt(logging.Handler):
    def emit(self, record):
        LOG.append(record.getMessage())


logging.getLogger("jazyky").addHandler(_Zachyt())
logging.getLogger("jazyky").setLevel(logging.WARNING)
mods = Z.importuj_api(os.path.join(REPO, "api"))
SH, SSE, OV, MO, MW, jz = (mods[k] for k in ("stul_shop", "stul_shop_sse", "stul_ovladani_verejne", "miniweb_objednavky", "miniweb", "jazyky"))
import app as A  # noqa: E402

TED = 1750000000
CHYBY = []


def over(podminka, zprava):
    if not podminka:
        CHYBY.append(zprava)


def vyber(system, **kw):
    d = SH.vychozi_vyber(system)
    d.update(kw)
    return d


def tag(id_):
    return "[xx:" + re.sub(r"[^A-Za-z0-9_.{}]", "_", id_) + "]"


def retezce(o, cesta=""):
    """Vsechny retezce zanorene struktury jako (cesta, text)."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from retezce(v, f"{cesta}/{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from retezce(v, f"{cesta}[{i}]")
    elif isinstance(o, str):
        yield cesta, o


SCENARE = [("vychozi", {}), ("uzky_suplik", {"w": 600, "drawers": True}), ("uzky_panely", {"w": 900, "panels": True, "posts": True}),
           ("siroky_panely_auto", {"w": 2600, "panels": True, "posts": True, "midsupport": "auto", "shelf": 1}), ("hluboky", {"d": 1100, "shelf": 1}),
           ("hluboky_suplik", {"d": 1100, "shelf": 2, "drawers": True}), ("pet_kolize", {"pet": True, "drawers": True, "drawleft": True, "petleg": "fl"}),
           ("pet_stredni_uzky", {"w": 900, "pet": True, "petleg": "fm"}), ("vyrezy_prekryv", {"cut1": True, "cut1w": 500, "cut1d": 400, "cut1x": 100, "cut1z": 100, "cut2": True,
                                                                                               "cut2w": 500, "cut2d": 400, "cut2x": 150, "cut2z": 150}),
           ("vzpery_dlouhe", {"led": True, "posts": True, "arm": 900, "braces": True}), ("siroky_deleny", {"w": 2800, "d": 800, "shelf": 1, "midsupport": "frame"}),
           ("suplik3_nizky", {"drawers": True, "drawercount": 3, "h": 700, "shelf": 2}), ("navlek", {"sleeve": True, "sleevelen": 400, "h": 700})]


def rezim_kontrola():
    """Sada `xx` (vyplnena znackami [xx:<id>] + placeholdery) je v kodu: slovniky, schema, resolve, informacni vety, ovladani, SSE, LABELS, ano/ne, trasy."""
    over("xx" in jz.jazyky(), "jazyky.jazyky() neobsahuje xx: %r" % jz.jazyky())
    over("xx" in SH.TEXTY and "xx" in SSE.TEXTY and "xx" in OV._TAB and "xx" in MO.LABELS, "xx chybi v nekterem slovniku")
    # TEXTY: stejne klice jako en, hodnota = znacka (+ placeholdery)
    over(set(SH.TEXTY["xx"]) == set(SH.TEXTY["en"]), "TEXTY[xx] ma jine klice nez en")
    spatne = [k for k in SH.TEXTY["en"] if not SH.TEXTY["xx"].get(k, "").startswith(tag(f"stul_shop.TEXTY.{k}"))]
    over(not spatne, "TEXTY[xx] bez znacky: %r" % spatne[:5])
    over(set(SH.DUVODY["xx"]) == set(SH.DUVODY["en"]) and SH.DUVODY["xx"][None].startswith(tag("stul_shop.DUVODY._default")), "DUVODY[xx]: klice nebo vychozi (None)")
    for nazev in jz.slovniky_zprav(vars(SH)):
        over(getattr(SH, nazev)["xx"].startswith(tag(f"stul_shop.zpravy.{nazev}")), f"zprava {nazev}[xx]")
    over(set(SH.NAZVY_SLOTU["xx"]) == set(SH.NAZVY_SLOTU["en"]) and set(SH.TEXTY_AKCI["xx"]) == set(SH.TEXTY_AKCI["en"]), "NAZVY_SLOTU / TEXTY_AKCI klice")
    over(SH.TEXTY_AKCI["xx"]["odebrano"].startswith(tag("stul_shop.TEXTY_AKCI.odebrano")) and SH.TEXTY_AKCI["xx"]["odebrano"].endswith(" "), "TEXTY_AKCI.odebrano: prefix a koncova mezera")
    over(set(SSE.TEXTY["xx"]) == set(SSE.TEXTY["en"]) and SSE.DUVOD_SUPLIKY["xx"].startswith(tag("stul_shop_sse.DUVOD_SUPLIKY")), "SSE texty")
    over(set(OV._TAB["xx"]) == set(OV._TAB["en"]), "ovladani: _TAB[xx] ma jine klice nez en")
    over(OV._TAB["xx"]["Pracovní deska"].startswith("[xx:ovladani.Pracovn"), "ovladani: preklad pracovni desky: %r" % OV._TAB["xx"]["Pracovní deska"])
    over(MO.LABELS["xx"]["toptrans"].startswith(tag("objednavky.toptrans")), "LABELS[xx]")
    over("xx" in MW.CONFIRMATION and MW.CONFIRMATION["xx"][0].startswith(tag("potvrzeni.predmet")), "CONFIRMATION[xx]")
    over(jz.ano_ne("xx") == (tag("ano_ne.ano"), tag("ano_ne.ne")), "ano_ne(xx) = %r" % (jz.ano_ne("xx"),))
    # schema + resolve pro vsechny systemy: kazdy stitek slotu = znacka jeho klice (SSE: vlastni TEXTY)
    for system in (30, 35, 40, 41):
        en = SH.schema("en", system)
        xx = SH.schema("xx", system)
        over([s["id"] for s in en["slots"]] == [s["id"] for s in xx["slots"]], f"schema {system}: jina sada slotu")
        for se, sx in zip(en["slots"], xx["slots"]):
            over(sx["label"].startswith("[xx:"), f"schema {system} slot {se['id']}: stitek {sx['label']!r}")
            if se.get("help"):
                over((sx.get("help") or "").startswith("[xx:"), f"schema {system} slot {se['id']}: napoveda {sx.get('help')!r}")
            for oe, ox in zip(se.get("options", []), sx.get("options", [])):
                over(ox["label"].startswith("[xx:") and oe["id"] == ox["id"], f"schema {system} slot {se['id']}: moznost {ox}")
        over(all(not re.search(r"\{prah\}", s.get("help") or "") for s in xx["slots"]), f"schema {system}: {{prah}} se nenahradil")
        for jm, kw in SCENARE:
            try:
                e = SH.resolve(vyber(system, **kw), "en", ted=TED, system=system)
                x = SH.resolve(vyber(system, **kw), "xx", ted=TED, system=system)
            except Exception as ex:                                  # noqa: BLE001
                CHYBY.append(f"resolve {system}/{jm}: vyjimka {type(ex).__name__}: {ex}")
                continue
            for pole in ("errors", "notices", "offers"):
                over(len(e[pole]) == len(x[pole]), f"resolve {system}/{jm}: pocet {pole} {len(e[pole])} vs {len(x[pole])}")
                for ze, zx in zip(e[pole], x[pole]):
                    over(zx["message" if "message" in zx else "label"].startswith("[xx:") or zx["message" if "message" in zx else "label"].startswith("{"), f"resolve {system}/{jm}: {pole} bez znacky: {zx}")
            for cesta, t in retezce(x.get("options")):
                if cesta.endswith("/reason") and t:
                    over(t.startswith("[xx:"), f"resolve {system}/{jm}: reason {cesta} = {t!r}")
            vod = (x.get("vodici") or {}).get("ovladani")
            if (e.get("vodici") or {}).get("ovladani"):
                over(bool(vod), f"resolve {system}/{jm}: ovladani chybi (ChybiPreklad?)")
            for cesta, t in retezce(vod):
                if cesta.endswith(("/label", "/name", "/title", "/popis")) and t:
                    over(t.startswith("[xx:ovladani."), f"resolve {system}/{jm}: ovladani text {cesta} = {t!r}")
    # informacni vety s pluralem: znacka podle sablony a kategorie
    for n in (0, 1, 2, 5):
        for u in (1, 2):
            t = SH.text_podpery("xx", {"kraceni_mm": 40, "podpery": n, "urovni": u, "hloubka_mm": 1000})
            if n == 0:
                over(t.startswith(tag("stul_shop.info.podpery.zaklad")) and "stul_shop.info.podpery.bez" in t, f"podpery n=0: {t!r}")
            else:
                var = "s_u1" if u == 1 else "s_um"
                kat = "one" if n == 1 else "other"
                over(f"stul_shop.info.podpery.{var}:{kat}" in t and f" {n}" in t and "1000" in t and "40" in t, f"podpery n={n} u={u}: {t!r}")
    for n, kat in ((1, "one"), (2, "other"), (5, "other")):
        for sup in (False, True):
            t = SH.text_podpery_desky("xx", {"podpery": n, "suplik": sup, "hloubka_mm": 1000})
            over(f"podpery_desky.zaklad:{kat}" in t and (("konec_suplik" in t) == sup), f"podpery_desky n={n} sup={sup}: {t!r}")
    over("desky_deleny.ram_navic" in SH.text_desky_deleny("xx", "ram", 74.0, (2070.0, 2800.0)) and "ram_navic" not in SH.text_desky_deleny("xx", "noha", 74.0, (2070.0, 2800.0)), "desky_deleny ram vs noha")
    sou = SH._souhrn_voleb(vyber(30, drawers=True, panels=False), "xx", 30)
    hodnoty = {s["value"] for s in sou if isinstance(s["value"], str)}
    over(tag("ano_ne.ano") in hodnoty and tag("ano_ne.ne") in hodnoty, f"souhrn voleb: ano/ne jazyka: {sorted(hodnoty)[:6]}")
    # shipping / potvrzeni
    lab = MO._shipping_options("xx", {"net": 10, "reason": None})
    over(lab[0]["label"].startswith(tag("objednavky.toptrans")) and lab[2]["label"].startswith(tag("objednavky.pickup")), "shipping_options(xx)")
    # _lang + trasy (jen cteni DB: app_settings configurator_products)
    with A.app.test_request_context("/x?lang=xx"):
        over(SH._lang("xx") == "xx" and SH._lang("zz") in ("cs", "en", "sk"), "_lang(xx) / _lang(zz)")
    produkty = SH._produkty()
    pid = next((p for p, r in produkty.items() if SH.RECEPTY.get(r) == 30), None) or next(iter(produkty), None)
    if pid:
        c = A.app.test_client()
        r = c.get(f"/api/shop/products/{pid}/configurator?lang=xx", headers={"X-Real-IP": "10.1.2.3"})
        over(r.status_code == 200 and r.get_json()["slots"][0]["label"].startswith("[xx:"), f"GET schema ?lang=xx: {r.status_code}")
        r2 = c.get(f"/api/shop/products/{pid}/configurator?lang=zz", headers={"X-Real-IP": "10.1.2.3"})
        over(r2.status_code == 200 and not r2.get_json()["slots"][0]["label"].startswith("[xx:"), "GET schema ?lang=zz (bez sady) ma spadnout na cs / en / sk")
        r3 = c.post("/api/shop/configurator/resolve", json={"product_id": int(pid), "selection": SH.vychozi_vyber(SH.system_pro_produkt(int(pid))), "lang": "xx"}, headers={"X-Real-IP": "10.1.2.4"})
        over(r3.status_code == 200 and isinstance(r3.get_json().get("selection"), dict), f"POST resolve lang=xx: {r3.status_code}")
    return {"produkt": pid}


def rezim_snimek():
    """Kompaktni otisk vystupu cs / en / sk (schema, resolve, info vety, slovniky): musi byt STEJNY s sadou xx i bez ni."""
    h = hashlib.sha256()
    pocet = 0

    def pridej(klic, hodnota):
        nonlocal pocet
        h.update(json.dumps([klic, hodnota], ensure_ascii=False, sort_keys=True, default=str).encode())
        pocet += 1
    for lg in ("cs", "en", "sk"):
        for system in (30, 40, 41):
            pridej(f"schema/{system}/{lg}", SH.schema(lg, system))
            for jm, kw in SCENARE:
                try:
                    pridej(f"resolve/{system}/{lg}/{jm}", SH.resolve(vyber(system, **kw), lg, ted=TED, system=system))
                except Exception as ex:                              # noqa: BLE001
                    pridej(f"resolve/{system}/{lg}/{jm}", f"vyjimka {type(ex).__name__}: {ex}")
        for n in range(0, 7):
            for u in (1, 2):
                pridej(f"podpery/{lg}/{n}/{u}", SH.text_podpery(lg, {"kraceni_mm": 40, "podpery": n, "urovni": u, "hloubka_mm": 1000}))
        pridej(f"deska/{lg}", [SH.text_podpery_desky(lg, {"podpery": n, "suplik": s, "hloubka_mm": 1000}) for n in (1, 2, 5) for s in (False, True)])
        pridej(f"deleny/{lg}", [SH.text_desky_deleny(lg, r, 74.0, (2070.0, 2800.0)) for r in ("ram", "noha")])
        pridej(f"souhrn/{lg}", SH._souhrn_voleb(vyber(30), lg, 30))
        pridej(f"ship/{lg}", MO._shipping_options(lg, {"net": 1, "reason": None}))
        for nazev in ("TEXTY", "DUVODY", "NAZVY_SLOTU", "TEXTY_AKCI") + tuple(jz.slovniky_zprav(vars(SH))):
            pridej(f"slovnik/{nazev}/{lg}", {str(k): v for k, v in getattr(SH, nazev)[lg].items()} if isinstance(getattr(SH, nazev)[lg], dict) else getattr(SH, nazev)[lg])
        pridej(f"sse/{lg}", [SSE.TEXTY[lg], SSE.DUVOD_SUPLIKY[lg]])
        pridej(f"tab/{lg}", OV._TAB.get(lg))
    pridej("conf", {k: v for k, v in MW.CONFIRMATION.items() if k in ("cs", "en", "sk")})
    pridej("klice", [sorted(k for k in SH.TEXTY if k in ("cs", "en", "sk"))])
    return {"otisk": h.hexdigest(), "polozek": pocet}


def rezim_fallback():
    """Sada `xx` s CHYBEJICIMI polozkami (klice vyhozene testem): zadna vyjimka, chybejici = anglicky text, varovani v logu."""
    over("xx" in SH.TEXTY, "xx neni v TEXTY")
    for k in ("w", "help_mid"):
        over(SH.TEXTY["xx"][k] == SH.TEXTY["en"][k], f"TEXTY[xx][{k}] ma byt anglicky (zaloha): {SH.TEXTY['xx'][k]!r}")
    over(SH.TEXTY["xx"]["d"].startswith("[xx:"), "ostatni TEXTY ze sady")
    over(SH.DUVODY["xx"]["panels"] == SH.DUVODY["en"]["panels"], "DUVODY[xx][panels] zaloha")
    over(SH.PET_BEZ_STREDNI["xx"] == SH.PET_BEZ_STREDNI["en"] and SH.KOLIZE_PET["xx"].startswith("[xx:"), "zprava PET_BEZ_STREDNI zaloha, ostatni ze sady")
    over(SH.NAZVY_SLOTU["xx"]["drawers"] == SH.NAZVY_SLOTU["en"]["drawers"], "NAZVY_SLOTU zaloha")
    over(OV._TAB["xx"]["Pracovní deska"] == OV._TAB["en"]["Pracovní deska"], "ovladani zaloha")
    over(OV._TAB["xx"]["Spodní police"].startswith("[xx:"), "ovladani: ostatni ze sady")
    over(MO.LABELS["xx"]["quote"] == MO.LABELS["en"]["quote"], "LABELS zaloha")
    over(SSE.DUVOD_SUPLIKY["xx"] == SSE.DUVOD_SUPLIKY["en"], "SSE DUVOD_SUPLIKY zaloha")
    # chybejici informacni sablona -> anglicky text
    over(SH.text_podpery("xx", {"kraceni_mm": 40, "podpery": 2, "urovni": 1, "hloubka_mm": 1000}) == SH.text_podpery("en", {"kraceni_mm": 40, "podpery": 2, "urovni": 1, "hloubka_mm": 1000}), "podpery bez sablony = anglicky")
    over(SH.text_desky_deleny("xx", "ram", 74.0, (2070.0, 2800.0)) == SH.text_desky_deleny("en", "ram", 74.0, (2070.0, 2800.0)), "deleny bez sablony = anglicky")
    over(jz.ano_ne("xx") is None, "ano_ne bez sady = None")
    try:
        r = SH.resolve(vyber(30, w=600, drawers=True), "xx", ted=TED, system=30)
        over(bool(r.get("notices")), "resolve funguje i s neuplnou sadou")
    except Exception as ex:                                      # noqa: BLE001
        CHYBY.append(f"resolve s neuplnou sadou spadl: {type(ex).__name__}: {ex}")
    over(any("chybi" in x for x in LOG), "do logu ma jit varovani o chybejicich polozkach: %r" % LOG[:3])
    return {}


def rezim_poskozena():
    """Sada `xx` s POSKOZENYMI sablonami (osamocena zavorka, neznamy placeholder, format {n:..}): import aplikace nespadl, vadne hodnoty = anglicka zaloha, zbytek ze sady, resolve / schema bez vyjimky."""
    over("xx" in SH.TEXTY and "xx" in SSE.TEXTY and "xx" in OV._TAB and "xx" in MO.LABELS, "jazyk xx se mel pripojit i s poskozenymi hodnotami")
    over(SH.TEXTY["xx"]["w"] == SH.TEXTY["en"]["w"], f"TEXTY.w s neznamym polem = anglicky: {SH.TEXTY['xx']['w']!r}")
    over(SH.TEXTY["xx"]["help_mid"] == SH.TEXTY["en"]["help_mid"], "TEXTY.help_mid s osamocenou zavorkou = anglicky")
    over(SH.TEXTY["xx"]["d"].startswith("[xx:"), "ostatni TEXTY ze sady")
    over(SH.DUVODY["xx"]["sleeve_orezano"] == SH.DUVODY["en"]["sleeve_orezano"], "DUVODY.sleeve_orezano s osamocenou zavorkou = anglicky")
    over(SH.DUVODY["xx"]["panels"].startswith("[xx:"), "ostatni DUVODY ze sady")
    for nazev in sorted(jz.slovniky_zprav(vars(SH)))[:2]:
        over(getattr(SH, nazev)["xx"] == getattr(SH, nazev)["en"], f"zprava {nazev} s vadnou sablonou = anglicky")
    over(SSE.DUVOD_SUPLIKY["xx"] == SSE.DUVOD_SUPLIKY["en"], "SSE DUVOD_SUPLIKY s neznamym polem = anglicky")
    over(OV._TAB["xx"]["Výřez 1"] == OV._TAB["en"]["Výřez 1"] and OV._TAB["xx"]["Výřez 3"] == OV._TAB["en"]["Výřez 3"], "ovladani Vyrez {n} s polem {x} = anglicky")
    over(OV._TAB["xx"]["Pracovní deska"] == OV._TAB["en"]["Pracovní deska"], "ovladani s osamocenou zavorkou = anglicky")
    over(OV._TAB["xx"]["Spodní police"].startswith("[xx:"), "ostatni ovladani ze sady")
    over(MO.LABELS["xx"]["toptrans"] == MO.LABELS["en"]["toptrans"] and MO.LABELS["xx"]["quote"].startswith("[xx:"), "LABELS: vadny stitek = anglicky, ostatni ze sady")
    over("xx" not in MW.CONFIRMATION, "potvrzeni s polem {foo} se nesmi pouzit")
    over(jz.ano_ne("xx") is None, "ano_ne s prazdnou hodnotou = None")
    over(SH.text_podpery("xx", {"kraceni_mm": 40, "podpery": 2, "urovni": 1, "hloubka_mm": 1000}) == SH.text_podpery("en", {"kraceni_mm": 40, "podpery": 2, "urovni": 1, "hloubka_mm": 1000}), "info sablona s osamocenou zavorkou = anglicky")
    for system in (30, 35, 40, 41):
        try:
            sch = SH.schema("xx", system)
            over(bool(sch["slots"]), f"schema {system}")
        except Exception as ex:                                  # noqa: BLE001
            CHYBY.append(f"schema {system}: {type(ex).__name__}: {ex}")
        for jm, kw in SCENARE:
            try:
                SH.resolve(vyber(system, **kw), "xx", ted=TED, system=system)
            except Exception as ex:                              # noqa: BLE001
                CHYBY.append(f"resolve {system}/{jm}: {type(ex).__name__}: {ex}")
    over(any("vadnou sablonu" in x for x in LOG) and any("vadnych sablon" in x for x in LOG), "varovani o vadnych sablonach maji byt v logu: %r" % LOG[:4])
    return {"varovani": len(LOG)}


def rezim_seznam():
    """Seznam platnych jazyku v JAZYKY_DIR (ostatni se ignoruji) a to, ze import aplikace nespadl."""
    return {"jazyky": jz.jazyky()}


if __name__ == "__main__":
    rezim = sys.argv[1]
    extra = {"kontrola": rezim_kontrola, "snimek": rezim_snimek, "fallback": rezim_fallback, "poskozena": rezim_poskozena, "seznam": rezim_seznam}[rezim]()
    print(json.dumps({"rezim": rezim, "chyby": CHYBY, "log": LOG, "extra": extra}, ensure_ascii=False))
