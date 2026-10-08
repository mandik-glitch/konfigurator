"""render_materialy.py - ucinna prirazovaci tabulka renderovacich materialu KATALOGU (bot10, 2026-10-01).

Robert: "vsechny polozky katalogu mimo karoserie -> material z knihovny Vandr materialu" (hlinik vsude alumi2,
laminodesky cub_seda, elektrozlab bila, perfopanely grey). Admin panel (webapp/admin/js/render-materialy-katalogu.js)
tady cte seznam polozek s UCINNYM klicem materialu (a odkud se vzal) a uklada prirazeni.

DATA (sql/2026-10-01_render_materialy.sql): render_materialy (knihovna 11 materialu), render_material_casti (material po
castech vicetelesoveho dilu), render_material_navrh (podklad z analyzy: stav OK/SPORNE/VYNECHANO), sloupec
render_material_key na shop_products / cfg_dily / content_categories (NULL = dedit). Poradi hledani klice je v
scripts/_render_prirazeni_lib.py (vyres_klic, PORADI_ODKUD): cast -> karta -> cfg -> kategorie -> mapa barev -> beze zmeny.

TENTO MODUL RENDER NIJAK NEOVLIVNUJE. Do renderu se material dostane az zapojenim render_material_key() do
resolve_parts() (zvlast, s bot4) a jen pri zapnutem app_settings.render_materialy_katalogu_aktivni - ten tu jen CTEME
(pravidlo 50: zadny bot nezapisuje do app_settings; zapnuti je vec Roberta/bot4 mimo tenhle modul).

Ochrana: @admin_required jako ostatni render endpointy (api/render_hdri.py). Kazdy zapis jde do audit_log
(log_audit). Chybi-li tabulky/sloupce (DDL jeste nebezelo) -> HTTP 503 {"code": "tabulky_nejsou"}, ne vyjimka.
"""
import functools
import json
import os
import re
import struct
import sys
import time

import pymysql
from flask import jsonify, request

from app import app, get_conn, admin_required, log_audit, current_user, KATALOG_GLB_DIR

_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import _render_prirazeni_lib as _lib  # noqa: E402

ZDROJE = ("product", "cfg")
_RE_CFG_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_RE_MESH = re.compile(r"^[A-Za-z0-9_.\- ]{1,120}$")
_RE_KLIC = re.compile(r"^[a-z0-9_]{1,40}$")
MAX_HROMADNE = 500
_MAX_GLB_JSON = 32 * 1024 * 1024
_TABULKY = ("render_materialy", "render_material_casti", "render_material_navrh")
_SLOUPCE = (("shop_products", "render_material_key"), ("cfg_dily", "render_material_key"),
            ("content_categories", "render_material_key"))
FLAG_KLIC = _lib.RENDER_MATERIALY_FLAG
CHYBA_DDL = ("Tabulky nejsou založeny - nejdřív se musí spustit sql/2026-10-01_render_materialy.sql "
             "(Robert přes ! příkaz, viz NAVOD.md).")


# ---------------------------------------------------------------------------------------------------------------
# pomocne
# ---------------------------------------------------------------------------------------------------------------
def _chybi_ddl(cur):
    """Seznam chybejicich tabulek/sloupcu (prazdny = DDL probehlo)."""
    chybi = []
    for t in _TABULKY:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (t,))
        if not cur.fetchone()["n"]:
            chybi.append("tabulka " + t)
    for t, c in _SLOUPCE:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND COLUMN_NAME=%s", (t, c))
        if not cur.fetchone()["n"]:
            chybi.append("sloupec %s.%s" % (t, c))
    return chybi


def _odpoved_ddl(chybi):
    return jsonify({"error": CHYBA_DDL, "code": "tabulky_nejsou", "chybi": chybi}), 503


_ddl_ok_do = [0.0]       # kladny vysledek kontroly DDL se pamatuje 30 s (zaporny nikdy)


def potrebuje_ddl(fn):
    """503 'tabulky nejsou zalozeny' misto vyjimky. Kontrola pred handlerem + zachyt MySQL 1146/1054 uvnitr."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if time.time() >= _ddl_ok_do[0]:
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    chybi = _chybi_ddl(cur)
            finally:
                conn.close()
            if chybi:
                return _odpoved_ddl(chybi)
            _ddl_ok_do[0] = time.time() + 30
        try:
            return fn(*args, **kwargs)
        except (pymysql.err.ProgrammingError, pymysql.err.OperationalError) as e:
            if e.args and e.args[0] in (1146, 1054):
                return _odpoved_ddl([str(e.args[-1])[:200]])
            raise
    return wrapper


def _text(v, max_delka=200):
    if v is None:
        return None
    v = str(v).strip()
    return v[:max_delka] if v else None


def _norm_id(zdroj, raw):
    """Platne id dilu jako text, nebo None. product = cele kladne cislo, cfg = [A-Za-z0-9_.-]{1,64}."""
    if zdroj not in ZDROJE or raw is None or isinstance(raw, (dict, list, bool)):
        return None
    s = str(raw).strip()
    if zdroj == "product":
        return str(int(s)) if s.isdigit() and 0 < int(s) < 2 ** 31 else None
    return s if _RE_CFG_ID.match(s) else None


def _parse_json(v):
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


def _over_klic(cur, hodnota):
    """(kanonicky_klic | None, chyba | None). None / '' = zrusit prirazeni. Klic musi existovat a byt aktivni."""
    k = _text(hodnota, 40)
    if k is None:
        return None, None
    k = k.lower()
    if not _RE_KLIC.match(k):
        return None, "Neplatný klíč materiálu '%s'." % k[:40]
    cur.execute("SELECT klic, aktivni FROM render_materialy WHERE klic=%s", (k,))
    row = cur.fetchone()
    if not row:
        return None, "Materiál '%s' v knihovně není." % k
    if not row["aktivni"]:
        return None, "Materiál '%s' je neaktivní." % k
    return row["klic"], None


def _flag_aktivni(cur):
    try:
        return bool(_lib.render_materialy_zapnuto(cur))
    except Exception:
        return False


# ---------------------------------------------------------------------------------------------------------------
# GLB: telesa (uzly s meshem) a nahled
# ---------------------------------------------------------------------------------------------------------------
_glb_cache = {}


def _cesta_glb(rel):
    if not rel:
        return None
    zaklad = os.path.realpath(KATALOG_GLB_DIR)
    cesta = os.path.realpath(os.path.join(zaklad, rel))
    if not cesta.startswith(zaklad + os.sep) or not os.path.isfile(cesta):
        return None
    return cesta


def _glb_json(cesta):
    with open(cesta, "rb") as f:
        hlavicka = f.read(12)
        if len(hlavicka) < 12 or hlavicka[:4] != b"glTF":
            return None
        delka, typ = struct.unpack("<I4s", f.read(8))
        if typ != b"JSON" or delka > _MAX_GLB_JSON:
            return None
        return json.loads(f.read(delka))


def telesa_glb(rel):
    """[{mesh_klic, rozmer: [x,y,z] v jednotkach GLB (u katalogu mm) | None}] z uzlu s meshem, nebo None (soubor nejde precist).
    Jmeno uzlu = to, co ve scene/Blenderu nese dil (Solid_0, Solid_1, ...). Vysledek se pamatuje podle mtime."""
    cesta = _cesta_glb(rel)
    if not cesta:
        return None
    try:
        st = os.stat(cesta)
        klic = (cesta, st.st_mtime_ns, st.st_size)
    except OSError:
        return None
    if klic in _glb_cache:
        return _glb_cache[klic]
    try:
        js = _glb_json(cesta)
    except (OSError, ValueError, struct.error):
        js = None
    if js is None:
        return None
    uzly, meshe, acc = js.get("nodes") or [], js.get("meshes") or [], js.get("accessors") or []
    vysl, pouzita = [], {}
    for i, u in enumerate(uzly):
        mi = u.get("mesh")
        if mi is None or not isinstance(mi, int) or mi >= len(meshe):
            continue
        jmeno = str(u.get("name") or "mesh_%d" % i)
        pouzita[jmeno] = pouzita.get(jmeno, 0) + 1
        if pouzita[jmeno] > 1:
            jmeno = "%s.%03d" % (jmeno, pouzita[jmeno] - 1)     # jako Blender: duplicitni jmeno -> .001
        lo, hi = [None] * 3, [None] * 3
        for p in meshe[mi].get("primitives") or []:
            ai = (p.get("attributes") or {}).get("POSITION")
            if ai is None or ai >= len(acc) or not acc[ai].get("min") or not acc[ai].get("max"):
                continue
            for k in range(3):
                lo[k] = acc[ai]["min"][k] if lo[k] is None else min(lo[k], acc[ai]["min"][k])
                hi[k] = acc[ai]["max"][k] if hi[k] is None else max(hi[k], acc[ai]["max"][k])
        rozmer = None
        if None not in lo and None not in hi:
            sc = u.get("scale") or [1, 1, 1]
            rozmer = [round(abs((hi[k] - lo[k]) * sc[k]), 1) for k in range(3)]
        vysl.append({"mesh_klic": jmeno, "rozmer": rozmer})
    if len(_glb_cache) > 1500:
        _glb_cache.clear()
    _glb_cache[klic] = vysl
    return vysl


def _nahled_url(thumbnail_file):
    if thumbnail_file and _cesta_glb(thumbnail_file):
        return "/katalog/" + thumbnail_file
    return None


# ---------------------------------------------------------------------------------------------------------------
# nacteni kontextu (knihovna, kategorie, navrh, casti) a sestaveni polozek
# ---------------------------------------------------------------------------------------------------------------
def _nacti_knihovnu(cur):
    cur.execute("SELECT klic, nazev, nazev_blender, knihovna_soubor, knihovna_file_id, three_json, poradi, aktivni, poznamka "
                "FROM render_materialy ORDER BY poradi, klic")
    radky = cur.fetchall()
    soubory = sorted({r["knihovna_soubor"] for r in radky if r["knihovna_soubor"]})
    existuje = set()
    if soubory:
        cur.execute("SELECT DISTINCT filename FROM shared_drive_files WHERE filename IN (%s)" % ",".join(["%s"] * len(soubory)), soubory)
        existuje = {r["filename"].lower() for r in cur.fetchall()}
    vysl = []
    for r in radky:
        vysl.append({
            "klic": r["klic"], "nazev": r["nazev"], "nazev_blender": r["nazev_blender"],
            "knihovna_soubor": r["knihovna_soubor"], "knihovna_file_id": r["knihovna_file_id"],
            # knihovna_ok: soubor s timhle jmenem je na Sdilenem disku (jinak render s timhle klicem nema co nacist)
            "knihovna_ok": bool(r["knihovna_soubor"]) and r["knihovna_soubor"].lower() in existuje,
            "three": _parse_json(r["three_json"]) or {}, "poradi": r["poradi"], "aktivni": bool(r["aktivni"]),
            "poznamka": r["poznamka"],
        })
    return vysl


def _nacti_kategorie(cur):
    cur.execute("SELECT id, parent_id, name, render_material_key FROM content_categories")
    return {r["id"]: r for r in cur.fetchall()}


def _cesta_kategorie(kat, cid):
    casti, videno = [], set()
    while cid is not None and cid in kat and cid not in videno:
        videno.add(cid)
        casti.append(kat[cid]["name"])
        cid = kat[cid]["parent_id"]
    return " › ".join(reversed(casti))


def _klic_kategorie(kat, cid):
    """(klic, nazev_kategorie_ktera_ho_nese) - nejblizsi nadrazena s klicem."""
    videno = set()
    while cid is not None and cid in kat and cid not in videno and len(videno) < 15:
        videno.add(cid)
        k = _lib._klic_text(kat[cid]["render_material_key"])
        if k:
            return k, kat[cid]["name"]
        cid = kat[cid]["parent_id"]
    return None, None


def _kontext(cur):
    ctx = {"knihovna": _nacti_knihovnu(cur), "kat": _nacti_kategorie(cur)}
    ctx["platne"] = {m["klic"].lower(): m["klic"] for m in ctx["knihovna"] if m["aktivni"]}
    cur.execute("SELECT zdroj, dil_id, navrzeny_klic, stav, pravidlo, navrh_casti_json FROM render_material_navrh")
    ctx["navrh"] = {(r["zdroj"], r["dil_id"]): r for r in cur.fetchall()}
    cur.execute("SELECT zdroj, dil_id, COUNT(*) AS n FROM render_material_casti GROUP BY zdroj, dil_id")
    ctx["casti_pocet"] = {(r["zdroj"], r["dil_id"]): r["n"] for r in cur.fetchall()}
    return ctx


def _dto(zdroj, r, ctx, cfg_podle_id):
    """Jedna polozka pro tabulku. r = radek shop_products / cfg_dily (viz _nacti_polozky)."""
    did = str(r["id"])
    if zdroj == "product":
        nazev, sku = r["name"], r["sku"]
        aktivni = bool(r["active"]) and not r["is_archived"]
        cesta = _cesta_kategorie(ctx["kat"], r["category_id"]) or (r.get("category_path") or "")
        karta, cid = _lib._klic_text(r["render_material_key"]), r["category_id"]
        cfg_r = cfg_podle_id.get(r["cfg_dily_id"]) if r.get("cfg_dily_id") else None
        kcfg = _lib._klic_text(cfg_r["render_material_key"]) if cfg_r else None
        layer = cfg_r["layer"] if cfg_r else None
        hexb = r["color_hex"] or (cfg_r["color_hex"] if cfg_r else None)
        nativni = bool(r.get("nativni_material"))
    else:
        nazev, sku = r["name"], r["id"]
        aktivni = bool(r["visible_in_scene"])
        cesta = "vrstva: %s" % (r["layer"] or "(prázdná)")
        karta, cid, kcfg = None, None, _lib._klic_text(r["render_material_key"])
        layer, hexb, nativni = r["layer"], r["color_hex"], False
    navrh = ctx["navrh"].get((zdroj, did))
    stav_navrhu = navrh["stav"] if navrh else None
    kkat, nazev_kat = (None, None)
    if cid is not None and not (karta or kcfg):
        kkat, nazev_kat = _klic_kategorie(ctx["kat"], cid)
    casti_n = ctx["casti_pocet"].get((zdroj, did), 0)
    klic, odkud = _lib.vyres_klic(None, karta, kcfg, kkat, hexb, layer, stav_navrhu)
    neplatny = None
    if klic is not None:
        kanon = ctx["platne"].get(klic.lower())
        if kanon is None:
            neplatny, klic, odkud = klic, None, "neplatny"
        else:
            klic = kanon
    if nativni:
        klic, odkud = None, "nativni"
    vlastni = karta if zdroj == "product" else kcfg
    # stav: VYNECHANO / SPORNE se zrusi, jakmile polozka dostane vlastni klic (karta/cfg), cast nebo klic z kategorie
    rozhodnuto = bool(vlastni or casti_n or kkat)
    if nativni:
        stav = "VYNECHANO"
    elif rozhodnuto:
        stav = "OK"
    elif stav_navrhu in ("SPORNE", "VYNECHANO"):
        stav = stav_navrhu
    elif klic is not None:
        stav = "OK"
    else:
        stav = "NOVE"
    t = telesa_glb(r.get("glb_file")) if r.get("glb_file") else None
    return {
        "zdroj": zdroj, "id": r["id"] if zdroj == "product" else did, "sku": sku, "nazev": nazev,
        "kategorie": cesta, "category_id": cid, "layer": layer, "barva_dnes": hexb,
        "aktivni": aktivni,
        "klic_vlastni": vlastni,
        "klic_efektivni": klic, "odkud": odkud, "odkud_nazev": nazev_kat if odkud == "kategorie" else None,
        "neplatny_klic": neplatny,
        "stav": stav, "stav_navrhu": stav_navrhu,
        "navrzeny_klic": navrh["navrzeny_klic"] if navrh else None,
        "pravidlo": navrh["pravidlo"] if navrh else None,
        "navrh_casti": bool(navrh and navrh["navrh_casti_json"]),
        "telesa": len(t) if t is not None else None,
        "casti_pocet": casti_n,
        "nahled": _nahled_url(r.get("thumbnail_file")),
    }


_SQL_PRODUCT = ("SELECT id, sku, name, category_id, category_path, color_hex, thumbnail_file, glb_file, active, is_archived, "
                "cfg_dily_id, nativni_material, render_material_key FROM shop_products "
                "WHERE visible_in_scene=1 AND glb_file IS NOT NULL")
_SQL_CFG = ("SELECT id, name, layer, color_hex, thumbnail_file, glb_file, visible_in_scene, render_material_key FROM cfg_dily")
# neaktivni dily SSE vzoru (sse_part_*): Robert "nechat" - v tabulce se nenabizi (parametr vse=1 je ukaze)
_SQL_BEZ_SSE = " AND NOT (active=0 AND sku LIKE 'SSE.%')"


def _nacti_polozky(cur, ctx, vse=False, jen=None):
    """jen = [(zdroj, id), ...] omezi vysledek (po zapisu); jinak vsechny polozky katalogu mimo karoserie."""
    cur.execute("SELECT id, render_material_key, layer, color_hex FROM cfg_dily")
    cfg_podle_id = {r["id"]: r for r in cur.fetchall()}
    polozky, skryto = [], 0
    if jen is None:
        cur.execute(_SQL_CFG + " ORDER BY layer, name")
        for r in cur.fetchall():
            polozky.append(_dto("cfg", r, ctx, cfg_podle_id))
        cur.execute(_SQL_PRODUCT + (_SQL_BEZ_SSE if not vse else "") + " ORDER BY name")
        for r in cur.fetchall():
            polozky.append(_dto("product", r, ctx, cfg_podle_id))
        if not vse:
            cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE visible_in_scene=1 AND glb_file IS NOT NULL "
                        "AND active=0 AND sku LIKE 'SSE.%'")
            skryto = cur.fetchone()["n"]
        return polozky, skryto
    for zdroj, did in jen:
        if zdroj == "product":
            cur.execute(_SQL_PRODUCT + " AND id=%s", (did,))
        else:
            cur.execute(_SQL_CFG + " WHERE id=%s", (did,))
        r = cur.fetchone()
        if r:
            polozky.append(_dto(zdroj, r, ctx, cfg_podle_id))
    return polozky, 0


def _souhrn(polozky, knihovna, skryto):
    s = {"celkem": len(polozky), "OK": 0, "SPORNE": 0, "VYNECHANO": 0, "NOVE": 0, "bez_efektivniho_klice": 0,
         "skryto_sse": skryto, "po_materialech": {m["klic"]: 0 for m in knihovna}}
    for p in polozky:
        s[p["stav"]] = s.get(p["stav"], 0) + 1
        if p["klic_efektivni"] is None:
            s["bez_efektivniho_klice"] += 1
        else:
            s["po_materialech"][p["klic_efektivni"]] = s["po_materialech"].get(p["klic_efektivni"], 0) + 1
    return s


def _kategorie_dto(ctx, polozky):
    """Kategorie, ktere maji polozky, vcetne predku + vsechny, co nesou vlastni klic."""
    kat = ctx["kat"]
    potreba = set()
    for p in polozky:
        cid = p["category_id"]
        videno = set()
        while cid is not None and cid in kat and cid not in videno:
            videno.add(cid)
            potreba.add(cid)
            cid = kat[cid]["parent_id"]
    potreba |= {cid for cid, r in kat.items() if _lib._klic_text(r["render_material_key"])}
    pocty = {}
    for p in polozky:
        if p["category_id"] is not None:
            pocty[p["category_id"]] = pocty.get(p["category_id"], 0) + 1
    vysl = []
    for cid in sorted(potreba):
        r = kat[cid]
        kd, nazev_nese = _klic_kategorie(kat, cid)
        vysl.append({"id": cid, "parent_id": r["parent_id"], "nazev": r["name"], "cesta": _cesta_kategorie(kat, cid),
                     "klic_vlastni": _lib._klic_text(r["render_material_key"]), "klic_zdedeny": kd,
                     "zdedeno_od": nazev_nese if kd and not _lib._klic_text(r["render_material_key"]) else None,
                     "polozek": pocty.get(cid, 0)})
    return vysl


# ---------------------------------------------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------------------------------------------
@app.get("/api/admin/render-materialy")
@admin_required
@potrebuje_ddl
def render_materialy_list():
    vse = request.args.get("vse") in ("1", "true", "ano")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _kontext(cur)
            polozky, skryto = _nacti_polozky(cur, ctx, vse=vse)
            flag = _flag_aktivni(cur)
    finally:
        conn.close()
    return jsonify({"tabulky_ok": True, "flag_aktivni": flag, "flag_klic": FLAG_KLIC,
                    "knihovna": ctx["knihovna"], "polozky": polozky,
                    "kategorie": _kategorie_dto(ctx, polozky),
                    "souhrn": _souhrn(polozky, ctx["knihovna"], skryto)})


@app.get("/api/admin/render-materialy/knihovna")
@admin_required
@potrebuje_ddl
def render_materialy_knihovna():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            knihovna = _nacti_knihovnu(cur)
    finally:
        conn.close()
    return jsonify({"knihovna": knihovna})


@app.get("/api/admin/render-materialy/dil/<zdroj>/<dil_id>")
@admin_required
@potrebuje_ddl
def render_materialy_dil(zdroj, dil_id):
    did = _norm_id(zdroj, dil_id)
    if did is None:
        return jsonify({"error": "Neplatný zdroj nebo id dílu."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _kontext(cur)
            polozky, _ = _nacti_polozky(cur, ctx, jen=[(zdroj, did)])
            if not polozky:
                return jsonify({"error": "Díl v katalogu není."}), 404
            p = polozky[0]
            if zdroj == "product":
                cur.execute("SELECT glb_file FROM shop_products WHERE id=%s", (did,))
            else:
                cur.execute("SELECT glb_file FROM cfg_dily WHERE id=%s", (did,))
            glb = (cur.fetchone() or {}).get("glb_file")
            cur.execute("SELECT mesh_klic, render_material_key FROM render_material_casti WHERE zdroj=%s AND dil_id=%s",
                        (zdroj, did))
            casti = {r["mesh_klic"]: r["render_material_key"] for r in cur.fetchall()}
    finally:
        conn.close()
    navrh = ctx["navrh"].get((zdroj, did))
    navrh_casti = _parse_json(navrh["navrh_casti_json"]) if navrh else None
    telesa = telesa_glb(glb)
    vysl = []
    for t in (telesa or []):
        m = t["mesh_klic"]
        vlastni = casti.get(m)
        # efektivni klic casti: vlastni klic casti, jinak to, co ma cely dil
        klic, odkud = (vlastni, "cast") if vlastni else (p["klic_efektivni"], p["odkud"])
        n = (navrh_casti or {}).get(m) or {}
        vysl.append({"mesh_klic": m, "rozmer": t["rozmer"], "klic_cast": vlastni, "klic_efektivni": klic,
                     "odkud": odkud, "navrh_klic": n.get("klic"), "navrh_proc": n.get("proc")})
    return jsonify({"polozka": p, "telesa": vysl if telesa is not None else None,
                    "chyba_glb": None if telesa is not None else "GLB soubor dílu nejde přečíst (chybí nebo je poškozený).",
                    "navrh_casti": bool(navrh_casti)})


# ---------------------------------------------------------------------------------------------------------------
# PUT / DELETE
# ---------------------------------------------------------------------------------------------------------------
def _audit(co, detail):
    user = current_user()
    log_audit(user["id"] if user else None, "update", "render_materialy", None,
              json.dumps({"co": co, **detail}, ensure_ascii=False))


def _tabulka_dilu(zdroj):
    return "shop_products" if zdroj == "product" else "cfg_dily"


def _precti_klic(cur, zdroj, did):
    """(existuje, aktualni_klic) cerstvym SELECTem."""
    cur.execute("SELECT render_material_key AS k FROM " + _tabulka_dilu(zdroj) + " WHERE id=%s", (did,))
    row = cur.fetchone()
    return (row is not None), (row or {}).get("k")


def _zapis_klice(cur, zdroj, did, klic):
    cur.execute("UPDATE " + _tabulka_dilu(zdroj) + " SET render_material_key=%s WHERE id=%s", (klic, did))
    existuje, po = _precti_klic(cur, zdroj, did)
    shoda = (po is None and klic is None) or (po is not None and klic is not None and po.lower() == klic.lower())
    return existuje and shoda, po


@app.put("/api/admin/render-materialy/polozka")
@admin_required
@potrebuje_ddl
def render_materialy_polozka_set():
    telo = request.get_json(silent=True) or {}
    zdroj = telo.get("zdroj")
    did = _norm_id(zdroj, telo.get("id"))
    if did is None:
        return jsonify({"error": "Neplatný zdroj nebo id položky."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            klic, chyba = _over_klic(cur, telo.get("klic"))
            if chyba:
                return jsonify({"error": chyba}), 400
            existuje, pred = _precti_klic(cur, zdroj, did)
            if not existuje:
                return jsonify({"error": "Položka v katalogu není."}), 404
            if "pred" in telo and (_text(telo["pred"], 40) or "").lower() != (pred or "").lower():
                return jsonify({"error": "Položku mezitím změnil někdo jiný - načti tabulku znovu.",
                                "code": "zmeneno", "aktualni": pred}), 409
            ok, po = _zapis_klice(cur, zdroj, did, klic)
            if not ok:
                conn.rollback()
                return jsonify({"error": "Uložení se nepotvrdilo (po zápisu je '%s')." % po}), 500
            conn.commit()
    finally:
        conn.close()
    _audit("polozka", {"zdroj": zdroj, "id": did, "pred": pred, "po": po})
    return jsonify({"status": "ok", "zdroj": zdroj, "id": did, "klic_vlastni": po})


@app.put("/api/admin/render-materialy/hromadne")
@admin_required
@potrebuje_ddl
def render_materialy_hromadne_set():
    """Dve podoby tela: {"polozky": [{zdroj,id}, ...], "klic": "grey"|null} (stejny klic vsem)
    nebo {"zmeny": [{zdroj,id,klic}, ...]}. Vse v jedne transakci (bud vsechno, nebo nic)."""
    telo = request.get_json(silent=True) or {}
    zmeny = []
    if isinstance(telo.get("polozky"), list):
        zmeny = [{"zdroj": p.get("zdroj"), "id": p.get("id"), "klic": telo.get("klic")} for p in telo["polozky"]
                 if isinstance(p, dict)]
    elif isinstance(telo.get("zmeny"), list):
        zmeny = [z for z in telo["zmeny"] if isinstance(z, dict)]
    if not zmeny:
        return jsonify({"error": "Chybí seznam položek."}), 400
    if len(zmeny) > MAX_HROMADNE:
        return jsonify({"error": "Najednou lze změnit nejvýš %d položek." % MAX_HROMADNE}), 400
    hotove, videno = [], set()
    for z in zmeny:
        did = _norm_id(z.get("zdroj"), z.get("id"))
        if did is None:
            return jsonify({"error": "Neplatná položka: %s %s" % (z.get("zdroj"), z.get("id"))}), 400
        if (z["zdroj"], did) in videno:
            continue
        videno.add((z["zdroj"], did))
        hotove.append((z["zdroj"], did, z.get("klic")))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cache_klicu, kroky = {}, []
            for zdroj, did, klic_raw in hotove:
                kk = _text(klic_raw, 40)
                if kk not in cache_klicu:
                    klic, chyba = _over_klic(cur, klic_raw)
                    if chyba:
                        return jsonify({"error": chyba}), 400
                    cache_klicu[kk] = klic
                existuje, pred = _precti_klic(cur, zdroj, did)
                if not existuje:
                    return jsonify({"error": "Položka %s %s v katalogu není - nic se neuložilo." % (zdroj, did)}), 404
                kroky.append((zdroj, did, cache_klicu[kk], pred))
            zapsano = []
            for zdroj, did, klic, pred in kroky:
                ok, po = _zapis_klice(cur, zdroj, did, klic)
                if not ok:
                    conn.rollback()
                    return jsonify({"error": "Uložení %s %s se nepotvrdilo - nic se neuložilo." % (zdroj, did)}), 500
                zapsano.append({"zdroj": zdroj, "id": did, "pred": pred, "po": po})
            conn.commit()
    finally:
        conn.close()
    _audit("hromadne", {"pocet": len(zapsano), "zmeny": zapsano[:200]})
    return jsonify({"status": "ok", "zmeneno": sum(1 for z in zapsano if (z["pred"] or None) != (z["po"] or None)),
                    "celkem": len(zapsano)})


@app.put("/api/admin/render-materialy/kategorie")
@admin_required
@potrebuje_ddl
def render_materialy_kategorie_set():
    telo = request.get_json(silent=True) or {}
    raw = telo.get("category_id")
    if isinstance(raw, bool) or not str(raw).strip().isdigit():
        return jsonify({"error": "Neplatné id kategorie."}), 400
    cid = int(str(raw).strip())
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            klic, chyba = _over_klic(cur, telo.get("klic"))
            if chyba:
                return jsonify({"error": chyba}), 400
            cur.execute("SELECT render_material_key AS k FROM content_categories WHERE id=%s", (cid,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Kategorie neexistuje."}), 404
            pred = row["k"]
            cur.execute("UPDATE content_categories SET render_material_key=%s WHERE id=%s", (klic, cid))
            cur.execute("SELECT render_material_key AS k FROM content_categories WHERE id=%s", (cid,))
            po = (cur.fetchone() or {}).get("k")
            if (po or None) != (klic or None):
                conn.rollback()
                return jsonify({"error": "Uložení se nepotvrdilo."}), 500
            conn.commit()
    finally:
        conn.close()
    _audit("kategorie", {"category_id": cid, "pred": pred, "po": po})
    return jsonify({"status": "ok", "category_id": cid, "klic_vlastni": po})


def _over_dil_a_mesh(cur, zdroj, dil_id, mesh_klice):
    """(did, chyba_odpoved|None): dil existuje a mesh_klice jsou mezi telesy jeho GLB."""
    did = _norm_id(zdroj, dil_id)
    if did is None:
        return None, (jsonify({"error": "Neplatný zdroj nebo id dílu."}), 400)
    cur.execute("SELECT glb_file FROM " + _tabulka_dilu(zdroj) + " WHERE id=%s", (did,))
    row = cur.fetchone()
    if not row:
        return None, (jsonify({"error": "Díl v katalogu není."}), 404)
    t = telesa_glb(row["glb_file"])
    if t is None:
        return None, (jsonify({"error": "GLB soubor dílu nejde přečíst, části nelze přiřadit."}), 422)
    znama = {x["mesh_klic"] for x in t}
    for m in mesh_klice:
        if not isinstance(m, str) or not _RE_MESH.match(m) or m not in znama:
            return None, (jsonify({"error": "Těleso '%s' v modelu dílu není." % str(m)[:60]}), 400)
    return did, None


def _zapis_casti(cur, zdroj, did, mapa):
    """mapa {mesh_klic: klic|None}; None = smazat. Vraci seznam zmen [{mesh,pred,po}]; po zapisu cerstvy SELECT kontroluje."""
    zmeny = []
    for mesh, klic in mapa.items():
        cur.execute("SELECT render_material_key AS k FROM render_material_casti WHERE zdroj=%s AND dil_id=%s AND mesh_klic=%s",
                    (zdroj, did, mesh))
        r = cur.fetchone()
        pred = r["k"] if r else None
        if klic is None:
            cur.execute("DELETE FROM render_material_casti WHERE zdroj=%s AND dil_id=%s AND mesh_klic=%s", (zdroj, did, mesh))
        else:
            cur.execute("INSERT INTO render_material_casti (zdroj, dil_id, mesh_klic, render_material_key) VALUES (%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE render_material_key=VALUES(render_material_key)", (zdroj, did, mesh, klic))
        cur.execute("SELECT render_material_key AS k FROM render_material_casti WHERE zdroj=%s AND dil_id=%s AND mesh_klic=%s",
                    (zdroj, did, mesh))
        r2 = cur.fetchone()
        po = r2["k"] if r2 else None
        if (po or None) != (klic or None):
            raise RuntimeError("zapis casti %s nepotvrzen" % mesh)
        zmeny.append({"mesh": mesh, "pred": pred, "po": po})
    return zmeny


@app.put("/api/admin/render-materialy/dil/<zdroj>/<dil_id>/cast")
@admin_required
@potrebuje_ddl
def render_materialy_cast_set(zdroj, dil_id):
    telo = request.get_json(silent=True) or {}
    mesh = telo.get("mesh_klic")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            did, chyba = _over_dil_a_mesh(cur, zdroj, dil_id, [mesh])
            if chyba:
                return chyba
            klic, ch = _over_klic(cur, telo.get("klic"))
            if ch:
                return jsonify({"error": ch}), 400
            try:
                zmeny = _zapis_casti(cur, zdroj, did, {mesh: klic})
            except RuntimeError as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            conn.commit()
    finally:
        conn.close()
    _audit("cast", {"zdroj": zdroj, "id": did, "zmeny": zmeny})
    return jsonify({"status": "ok", "zmeny": zmeny})


@app.delete("/api/admin/render-materialy/dil/<zdroj>/<dil_id>/cast")
@admin_required
@potrebuje_ddl
def render_materialy_cast_delete(zdroj, dil_id):
    mesh = request.args.get("mesh_klic")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            did, chyba = _over_dil_a_mesh(cur, zdroj, dil_id, [mesh])
            if chyba:
                return chyba
            try:
                zmeny = _zapis_casti(cur, zdroj, did, {mesh: None})
            except RuntimeError as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            conn.commit()
    finally:
        conn.close()
    _audit("cast_smazana", {"zdroj": zdroj, "id": did, "zmeny": zmeny})
    return jsonify({"status": "ok", "zmeny": zmeny})


@app.put("/api/admin/render-materialy/dil/<zdroj>/<dil_id>/casti")
@admin_required
@potrebuje_ddl
def render_materialy_casti_set(zdroj, dil_id):
    """Vice casti najednou (napr. 'pouzit navrh po castech'): {"casti": {"Solid_0": "grey", "Solid_8": "chrome", "Solid_3": null}}."""
    telo = request.get_json(silent=True) or {}
    casti = telo.get("casti")
    if not isinstance(casti, dict) or not casti or len(casti) > 200:
        return jsonify({"error": "Chybí seznam částí."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            did, chyba = _over_dil_a_mesh(cur, zdroj, dil_id, list(casti))
            if chyba:
                return chyba
            mapa = {}
            for mesh, k in casti.items():
                klic, ch = _over_klic(cur, k)
                if ch:
                    return jsonify({"error": ch}), 400
                mapa[mesh] = klic
            try:
                zmeny = _zapis_casti(cur, zdroj, did, mapa)
            except RuntimeError as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            conn.commit()
    finally:
        conn.close()
    _audit("casti", {"zdroj": zdroj, "id": did, "zmeny": zmeny})
    return jsonify({"status": "ok", "zmeny": zmeny})
