#!/usr/bin/env python3
"""Sestavi ctx.json pro scripts/v3d/vandr_offer_build.py (bot10, 2026-10-01,
Robert: 3D scena online nabidky). JEN CTE - konfigurator DB (shop_products,
app_settings) a Vandr data pres artisan prikaz `vandr:offer-data <uuid>
--v3d` (VandrOfferData.php ve vandrawee repu), nic nezapisuje.

PRISTUPOVE UDAJE (nalez 6 kontroly 2026-10-01): proces konfiguratoru NECTE
/opt/vandrawee/web/.env a NEPRIPOJUJE se k Vandr DB. Vandr data (komponenty,
kusovnik components_parts -> parts, stored_model_parts.data) vraci artisan
prikaz, ktery bezi pod vlastnim Laravel pripojenim v SAMOSTATNEM procesu s
uzkym env (_clean_subprocess_env: jen PATH - stejne jako
api/vandr_scene_offers.py; jinak by DB_HOST/DB_PASSWORD konfiguratoru z
EnvironmentFile prepsaly Laravel .env). konfigurator_app nema GRANT na
vandrawee_work a mit ho nema.

Obsah ctx.json (verze 1):
  shop_product_id, glb_file, glb (absolutni cesta), glb_sha12
  vandr_predni_azimut_deg       shop_products (smer cela pro renderery)
  strany                        {"left": id stored_model_parts, ...}
  komponenty                    typy komponent karty (unikatni unity_id):
      {unity_id, klic, category_id, kategorie, is_universal, is_top,
       pocet, strany[], dily: [{unity_id, pocet}] (kusovnik components_parts
       -> vandrawee.parts), rozsireni: [{unity_id, pocet, dily[]}]}
  instance                      kazda komponenta ze stored_model_parts.data
      {unity_id, klic, strana, nohy, pozice [m, Unity], rotace, rozsireni[]}
  prirazeni_materialu           snimek app_settings.render_prirazeni_materialu
  kryci_listy_skryt             z tehoz snimku (nebo samostatneho klice)
  pohyby_vychozi                obsah pohyby-vychozi.json (nebo null)
  vandr_ok                      artisan vandr:offer-data --v3d vratil data
  warnings                      co se nepodarilo nacist
(komponenty/instance/strany jsou vystupem prikazu vandr:offer-data --v3d -
stejne dotazy jako drive primo z Vandr DB; ctx i ctx_sha8 jsou proto shodne
s drivejsimi snimky, overeno na 7 kartach)

Pouziti (server, jen cteni):
    api/venv/bin/python3 scripts/v3d/build_ctx.py <shop_product_id> [-o ctx.json]
                         [--pohyby pohyby-vychozi.json] [--strict]
Z API: sestav_ctx(shop_product_id, konf_conn=get_conn()) - na PREDANEM
spojeni se jen ctou SELECTy (zadne SET SESSION - pooled spojeni workeru
by si READ ONLY odneslo do dalsich pozadavku); spojeni, ktere si modul
otevre sam (CLI), je READ ONLY a po pouziti se zavre (rollback).
strict=True: selhani artisan prikazu = vyjimka (VandrDataError); jinak
varovani a ctx bez komponent (staticky model) jako drive.

Prihlasovaci udaje se nikam nevypisuji: konfigurator DB z prostredi
(DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME, EnvironmentFile sluzby), jinak
z /opt/konfigurator/api/.env (jen CLI). Vandr: zadne udaje v tomto procesu.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# koren repa: env KONFIGURATOR_REPO, jinak podle umisteni tohoto souboru (scripts/v3d -> koren; na serveru
# /opt/konfigurator) - stejne jako dosud, jen jde stavebni strom (testy) postavit i mimo /opt/konfigurator
KONF_REPO = os.environ.get("KONFIGURATOR_REPO") or os.path.dirname(os.path.dirname(SCRIPT_DIR))
KONF_ENV_PATH = os.path.join(KONF_REPO, "api", ".env")
KATALOG_DIR = os.path.join(KONF_REPO, "webapp", "katalog")
VANDRAWEE_WEB_DIR = "/opt/vandrawee/web"
PHP_BIN = "/usr/bin/php"
ARTISAN_TIMEOUT_S = 30
CTX_VERZE = 1


class VandrDataError(RuntimeError):
    """artisan vandr:offer-data --v3d selhal nebo vratil neplatna data."""


def _najdi_lib():
    for d in (os.environ.get("V3D_LIB_DIR") or "", os.path.dirname(SCRIPT_DIR), os.path.join(KONF_REPO, "scripts")):
        if d and os.path.isfile(os.path.join(d, "_render_prirazeni_lib.py")):
            return d
    return None


_lib = _najdi_lib()
sys.dont_write_bytecode = True   # zadny __pycache__ do scripts/ repa
if _lib:
    sys.path.insert(0, _lib)
    import _render_prirazeni_lib as PL  # noqa: E402
else:
    PL = None


def _cti_env(cesta):
    vals = {}
    try:
        with open(cesta, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        return None
    return vals


def _ro(conn):
    with conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        cur.execute("START TRANSACTION READ ONLY")
    return conn


def konf_conn_ro():
    """Vlastni READ ONLY spojeni do konfigurator DB (jen CLI; API predava
    get_conn()). pymysql se importuje az tady - modul jde nacist i bez nej."""
    import pymysql
    env = {k: os.environ[k] for k in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME") if k in os.environ}
    if len(env) < 5:
        env = _cti_env(KONF_ENV_PATH) or {}
    if not env.get("DB_USER"):
        raise RuntimeError("konfigurator DB: chybi prihlasovaci udaje (prostredi ani api/.env)")
    return _ro(pymysql.connect(
        host=env.get("DB_HOST") or "localhost", port=int(env.get("DB_PORT") or 3306), user=env["DB_USER"],
        password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=10, read_timeout=25))


def _clean_subprocess_env():
    """Stejne jako api/vandr_scene_offers._clean_subprocess_env (bug
    2026-09-28): podproces bez `env=` dedi CELE prostredi konfiguratoru vcetne
    DB_HOST/DB_PASSWORD z EnvironmentFile - Laravel by je vzal prednostne pred
    svym .env. Proto explicitne jen PATH."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def _fetch_vandr_v3d(uuid):
    """`php artisan vandr:offer-data <uuid> --v3d` (VandrOfferData.php ve
    vandrawee repu) - bezi pod Laravel vlastnim DB pripojenim v samostatnem
    procesu. Vraci dict celeho JSON vystupu (car_name, parts, v3d)."""
    env = _clean_subprocess_env()
    assert not any(k.startswith("DB_") for k in env)   # pojistka nalezu 6
    try:
        proc = subprocess.run([PHP_BIN, "artisan", "vandr:offer-data", uuid, "--v3d"], cwd=VANDRAWEE_WEB_DIR,
                              capture_output=True, text=True, timeout=ARTISAN_TIMEOUT_S, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VandrDataError("vandr:offer-data --v3d nespusteno/prekroceny cas (%s)" % type(e).__name__)
    if proc.returncode != 0:
        raise VandrDataError(("vandr:offer-data --v3d selhalo (rc=%d): %s"
                              % (proc.returncode, proc.stdout + proc.stderr))[-1000:])
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise VandrDataError(("vandr:offer-data --v3d nevratilo JSON: %s" % proc.stdout)[-500:])


def _v3d_z_vystupu(vystup):
    """Kontrola tvaru klice v3d (verze 1) z artisan vystupu."""
    v = vystup.get("v3d") if isinstance(vystup, dict) else None
    if not isinstance(v, dict):
        raise VandrDataError("vandr:offer-data nevratil klic v3d (na Vandr strane nasazena stara verze prikazu?)")
    if v.get("v") != 1 or not isinstance(v.get("strany"), dict) or not isinstance(v.get("komponenty"), list) \
            or not isinstance(v.get("rozsireni"), list):
        raise VandrDataError("vandr:offer-data: neznamy tvar v3d (v=%r)" % v.get("v"))
    return v


def klic_unity_id(unity_id):
    """unity_id -> klic, ktery odpovida jmenu uzlu v GLB: three.js
    PropertyBinding.sanitizeNodeName (mezery -> '_', znaky [ ] . : / pryc),
    diakritika -> '?' (FBXLoader ji rozbije), mala pismena. Stejny tvar
    vraci vandr_offer_build._klic_jmena pro jmeno uzlu."""
    n = re.sub(r"\s", "_", unity_id or "")
    n = re.sub(r"[\[\]\.:/]", "", n)
    n = "".join(c if ord(c) < 128 else "?" for c in unicodedata.normalize("NFC", n))
    return re.sub(r"[^0-9a-z_?]", "", n.lower())


def _vec(d):
    if isinstance(d, dict):
        return [round(float(d.get(k) or 0.0), 6) for k in ("x", "y", "z")]
    return None


def _najdi_pohyby(cesta=None):
    koren = os.path.dirname(os.path.dirname(SCRIPT_DIR))   # scripts/v3d -> koren (repo nebo kandidat)
    kandidati = [cesta, os.environ.get("V3D_POHYBY"),
                 os.path.join(SCRIPT_DIR, "pohyby-vychozi.json"),     # scripts/v3d/pohyby-vychozi.json (umisteni v repu)
                 os.path.join(koren, "pohyby-vychozi.json"),
                 os.path.join(koren, "webapp", "js", "v3d", "pohyby-vychozi.json"),
                 os.path.join(KONF_REPO, "webapp", "js", "v3d", "pohyby-vychozi.json")]
    for k in kandidati:
        if k and os.path.isfile(k):
            return k
    return None


def _sha12(cesta):
    h = hashlib.sha256()
    with open(cesta, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()[:12]


def _nacti_panel(cur, warnings):
    if PL is not None:
        n = PL.nacti_ulozene_nastaveni(cur)   # sdilena funkce, nikdy nevyhazuje
    else:
        warnings.append("scripts/_render_prirazeni_lib.py nenalezen - panel cten primo")
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", ("render_prirazeni_materialu",))
        row = cur.fetchone()
        try:
            n = json.loads(row["setting_value"]) if row and row.get("setting_value") else {}
        except ValueError:
            n = {}
    if not n:
        warnings.append("app_settings.render_prirazeni_materialu prazdne nebo necitelne")
    kryci = n.get("kryci_listy_skryt") if isinstance(n, dict) else None
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", ("kryci_listy_skryt",))
    row = cur.fetchone()
    if row and row.get("setting_value") not in (None, ""):
        kryci = str(row["setting_value"]).strip().lower() in ("1", "true", "ano", "yes")
    return n if isinstance(n, dict) else {}, bool(kryci) if kryci is not None else True


def _komponenty_z_dat(data, strana):
    """stored_model_parts.data = [{unity_id (nohy), position, components:
    [{unity_id, position, rotation, extensions}], left_leg, right_leg}]."""
    out = []
    for nohy in data if isinstance(data, list) else []:
        if not isinstance(nohy, dict):
            continue
        for k in nohy.get("components") or []:
            if not isinstance(k, dict) or not k.get("unity_id"):
                continue
            rozs = []
            for e in k.get("extensions") or []:
                if isinstance(e, dict) and e.get("unity_id"):
                    rozs.append(e["unity_id"])
                elif isinstance(e, str):
                    rozs.append(e)
            out.append({"unity_id": k["unity_id"], "klic": klic_unity_id(k["unity_id"]), "strana": strana,
                        "nohy": nohy.get("unity_id"), "pozice": _vec(k.get("position")),
                        "rotace": _vec(k.get("rotation")), "rozsireni": rozs})
    return out


RAZITKOVE_DILY = ("vypln_placka", "logo_logiman_cz")


def _konst_razitkovace():
    """LOGO_BARVA_HEX / LOGO_METALNESS / LOGO_ROUGHNESS ze scripts/razitkovac.py (zdroj pravdy; cteno ze zdroje, ne importem -
    modul tahne dalsi zavislosti). Chybi-li, None."""
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "razitkovac.py"), encoding="utf-8") as f:
            zdroj = f.read()
        hexc = re.search(r'^LOGO_BARVA_HEX\s*=\s*"(#[0-9A-Fa-f]{6})"', zdroj, re.M)
        met = re.search(r"^LOGO_METALNESS\s*=\s*([0-9.]+)", zdroj, re.M)
        rough = re.search(r"^LOGO_ROUGHNESS\s*=\s*([0-9.]+)", zdroj, re.M)
        return {"hex": hexc.group(1), "met": float(met.group(1)), "rough": float(rough.group(1))} if (hexc and met and rough) else None
    except (OSError, ValueError, AttributeError):
        return None


def _cisla(v, n):
    return isinstance(v, (list, tuple)) and len(v) == n and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) < 1e7 for x in v)


def _razitka_pro_ctx(cur, shop_product_id, warnings):
    """Ochranna razitka LOGIMAN.CZ pro 3D model nabidky (bot4 2026-10-06, Robertovo pravidlo 2026-09-06: razitkovani = stupen 2 =
    model v nabidce): shop_products.vandr_razitka_json (logo + vypln drazky, pozice v mm a quaternion v glTF ramu katalogoveho GLB)
    + cesty a otisky katalogovych GLB loga a vypne + barva loga. None = zadna razitka (build bezi jako driv, jen varovani).
    Vse ostatni, co by melo vliv na vysledek, jde do ctx_hash -> klic cache (zmena razitek/loga = novy model)."""
    try:
        cur.execute("SELECT vandr_razitka_json, vandr_razitka_glb_otisk FROM shop_products WHERE id=%s", (shop_product_id,))
        r = cur.fetchone() or {}
        if not r.get("vandr_razitka_json"):
            return None
        data = json.loads(r["vandr_razitka_json"])
        if not isinstance(data, list):
            raise ValueError("vandr_razitka_json neni seznam")
        dily = []
        for d in data:
            if not isinstance(d, dict) or d.get("part_id") not in RAZITKOVE_DILY:
                continue
            if not (_cisla(d.get("position"), 3) and _cisla(d.get("quaternion"), 4) and _cisla(d.get("scale", [1, 1, 1]), 3)):
                raise ValueError("razitko %s ma neplatnou pozici/otoceni/meritko" % d.get("part_id"))
            item = {"part_id": d["part_id"], "position": list(d["position"]), "quaternion": list(d["quaternion"]),
                    "scale": list(d.get("scale", [1, 1, 1]))}
            if d["part_id"] == "vypln_placka":
                for k, n in (("base_color", 3),):
                    if _cisla(d.get(k), n):
                        item[k] = list(d[k])
                for k in ("metalness", "roughness"):
                    if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool):
                        item[k] = float(d[k])
            dily.append(item)
        if not dily:
            return None
        cur.execute("SELECT id, glb_file FROM cfg_dily WHERE id IN (%s, %s)", RAZITKOVE_DILY)
        glb = {}
        for row in cur.fetchall():
            cesta = os.path.join(KATALOG_DIR, row["glb_file"]) if row.get("glb_file") else None
            if cesta and os.path.isfile(cesta):
                glb[row["id"]] = {"cesta": cesta, "sha12": _sha12(cesta)}
        chybi = [k for k in RAZITKOVE_DILY if k not in glb]
        if chybi:
            raise ValueError("katalogove GLB razitek chybi: %s" % ", ".join(chybi))
        logo = _konst_razitkovace()
        if not logo:
            raise ValueError("konstanty loga v razitkovac.py nenalezeny")
        return {"dily": dily, "otisk": r.get("vandr_razitka_glb_otisk"), "glb": glb, "logo": logo}
    except (ValueError, KeyError, TypeError) as e:
        warnings.append("razitka do modelu nebyla pridana (%s)" % str(e)[:200])
        return None
    except Exception as e:  # noqa: BLE001 - razitka nesmi shodit model nabidky
        warnings.append("razitka do modelu nebyla pridana (%s: %s)" % (type(e).__name__, str(e)[:160]))
        return None


def sestav_ctx(shop_product_id, konf_conn=None, pohyby_path=None, vandr_fetch=None, strict=False):
    """vandr_fetch(uuid) -> dict vystupu `vandr:offer-data --v3d` (vychozi
    _fetch_vandr_v3d; parametr je pro testy). strict: selhani Vandr dat =
    VandrDataError misto varovani."""
    warnings = []
    vlastni_konf = konf_conn is None
    conn = konf_conn or konf_conn_ro()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, glb_file, vandr_predni_azimut_deg FROM shop_products WHERE id=%s",
                        (shop_product_id,))
            karta = cur.fetchone()
            if not karta:
                raise LookupError("karta %s neexistuje" % shop_product_id)
            panel, kryci = _nacti_panel(cur, warnings)
            razitka = _razitka_pro_ctx(cur, shop_product_id, warnings)
    finally:
        if vlastni_konf:
            try:
                conn.rollback()
            finally:
                conn.close()

    sku = karta.get("sku") or ""
    if not sku.startswith("VD-"):
        raise ValueError("karta %s neni Vandr karta (SKU neni VD-<uuid>)" % shop_product_id)
    glb_abs = os.path.join(KATALOG_DIR, karta["glb_file"]) if karta.get("glb_file") else None
    ctx = {
        "v": CTX_VERZE,
        "vytvoreno": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "shop_product_id": int(karta["id"]),
        "glb_file": karta.get("glb_file"),
        "glb": glb_abs,
        "glb_sha12": _sha12(glb_abs) if glb_abs and os.path.isfile(glb_abs) else None,
        "vandr_predni_azimut_deg": karta.get("vandr_predni_azimut_deg"),
        "strany": {},
        "komponenty": [],
        "instance": [],
        "prirazeni_materialu": panel,
        "kryci_listy_skryt": kryci,
        "razitka": razitka,
        "pohyby_vychozi": None,
        "warnings": warnings,
    }
    if not glb_abs or not os.path.isfile(glb_abs):
        warnings.append("karta nema GLB na disku")

    # ---- Vandr: sestava -> strany -> komponenty -> kusovnik (artisan, jen cteni)
    v3d = None
    try:
        v3d = _v3d_z_vystupu((vandr_fetch or _fetch_vandr_v3d)(sku[3:]))
    except VandrDataError as e:
        if strict:
            raise
        warnings.append("Vandr data nedostupna (%s) - ctx bez komponent" % str(e)[:300])
    ctx["vandr_ok"] = v3d is not None
    if v3d is not None:
        for strana in ("left", "right", "bulkhead"):
            s = v3d["strany"].get(strana)
            if not isinstance(s, dict) or s.get("id") is None:
                continue
            ctx["strany"][strana] = int(s["id"])
            try:
                data = json.loads(s["data"]) if s.get("data") else []
            except (TypeError, ValueError):
                data = []
                warnings.append("stored_model_parts.data (%s) necitelne" % strana)
            ctx["instance"] += _komponenty_z_dat(data, strana)
        if not ctx["strany"]:
            warnings.append("sestava nema zadnou stranu (left/right/bulkhead)")
        typy = {}
        for r in v3d["komponenty"]:
            if isinstance(r, dict) and r.get("unity_id"):
                typy[r["unity_id"]] = r
        ext_podle_uid = {}
        for r in v3d["rozsireni"]:
            if isinstance(r, dict) and r.get("unity_id"):
                ext_podle_uid[r["unity_id"]] = r
        uids = sorted(set(i["unity_id"] for i in ctx["instance"]))
        chybi = [u for u in uids if u not in typy]
        if chybi:
            warnings.append("%d typu komponent neni v tabulce components" % len(chybi))
        if v3d.get("chybi_dily"):
            warnings.append("kusovnik: %d dilu (part_id) bez radku v parts - vynechany" % int(v3d["chybi_dily"]))
        if v3d.get("smazane_dily"):
            warnings.append("kusovnik obsahuje %d dilu smazanych ve Vandru (soft delete) - zapocteny"
                            % len(v3d["smazane_dily"]))

        def _dily(seznam):
            out = []
            for d in seznam or []:
                if isinstance(d, dict) and d.get("unity_id"):
                    out.append({"unity_id": str(d["unity_id"]), "pocet": int(d.get("pocet") or 0)})
            return sorted(out, key=lambda d: d["unity_id"])

        pocty, strany_typu, rozs_typu = {}, {}, {}
        for i in ctx["instance"]:
            pocty[i["unity_id"]] = pocty.get(i["unity_id"], 0) + 1
            strany_typu.setdefault(i["unity_id"], set()).add(i["strana"])
            for e in i["rozsireni"]:
                rozs_typu.setdefault(i["unity_id"], {})
                rozs_typu[i["unity_id"]][e] = rozs_typu[i["unity_id"]].get(e, 0) + 1
        for uid in sorted(pocty):
            t = typy.get(uid)
            ctx["komponenty"].append({
                "unity_id": uid, "klic": klic_unity_id(uid),
                "category_id": t.get("category_id") if t else None, "kategorie": t.get("kategorie") if t else None,
                "is_universal": bool(t.get("is_universal")) if t else None,
                "is_top": bool(t.get("is_top")) if t else None, "pocet": pocty[uid],
                "strany": sorted(strany_typu.get(uid, [])), "dily": _dily(t.get("dily") if t else []),
                "rozsireni": [{"unity_id": e, "pocet": n, "dily": _dily((ext_podle_uid.get(e) or {}).get("dily"))}
                              for e, n in sorted(rozs_typu.get(uid, {}).items())],
            })
        klice = {}
        for k in ctx["komponenty"]:
            klice.setdefault(k["klic"], []).append(k["unity_id"])
        kolize = [k for k, v in klice.items() if len(v) > 1]
        if kolize:
            warnings.append("%d klicu komponent je nejednoznacnych (ruzne unity_id po odstraneni tecek)" % len(kolize))

    # ---- vychozi hodnoty pohybu
    pp = _najdi_pohyby(pohyby_path)
    if pp:
        try:
            with open(pp, encoding="utf-8") as f:
                ctx["pohyby_vychozi"] = json.load(f)
            ctx["pohyby_vychozi_soubor"] = os.path.basename(pp)
        except (OSError, ValueError) as e:
            warnings.append("pohyby-vychozi.json necitelny (%s)" % type(e).__name__)
    else:
        warnings.append("pohyby-vychozi.json nenalezen - pohyby bez vychozich hodnot")
    return ctx


def ctx_hash(ctx):
    """sha8 obsahu, ktery ovlivnuje vysledek buildu (pro klic cache)."""
    klic = {k: ctx.get(k) for k in ("v", "glb_sha12", "vandr_predni_azimut_deg", "komponenty", "instance",
                                     "prirazeni_materialu", "kryci_listy_skryt", "pohyby_vychozi", "razitka")}
    return hashlib.sha256(json.dumps(klic, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:8]


def main():
    ap = argparse.ArgumentParser(description="ctx.json pro vandr_offer_build.py (jen cteni DB + artisan)")
    ap.add_argument("shop_product_id", type=int)
    ap.add_argument("-o", "--out", help="vystupni ctx.json (bez = stdout)")
    ap.add_argument("--pohyby", help="cesta k pohyby-vychozi.json")
    ap.add_argument("--strict", action="store_true", help="selhani vandr:offer-data = chyba (jinak varovani)")
    a = ap.parse_args()
    ctx = sestav_ctx(a.shop_product_id, pohyby_path=a.pohyby, strict=a.strict)
    ctx["ctx_sha8"] = ctx_hash(ctx)
    txt = json.dumps(ctx, ensure_ascii=False, indent=1, default=str)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("CTX_OK %s komponent=%d instanci=%d varovani=%d" % (a.out, len(ctx["komponenty"]), len(ctx["instance"]),
                                                                  len(ctx["warnings"])))
    else:
        print(txt)


if __name__ == "__main__":
    main()
