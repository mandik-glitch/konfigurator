"""Doplneni HDRI do vzhledu online nabidek ZE SDILENEHO DISKU (bot10, 2026-10-07; Robert: "moznost pridat dalsi hdri ze sdileneho disku").

Knihovna HDRI vieweru (webapp/js/v3d/viewer3d.js HDRI_LIBRARY: crossfit, tv_studio, berg_inner, teufelsberg) je pevna v kodu. Tenhle modul pridava dalsi HDRI za behu:
admin v okne "Vzhled nabidek" (webapp/kontrola.html) vybere .hdr soubor ze Sdileneho disku, server ho PREVEDE (api/v3d_env_prevod.py v podprocesu s limitem pameti a casu) na dve
male verze (<klic>_1024.hdr 1024x512, <klic>_256.hdr 256x128 jako rychly nahled) a zapise do PRIVATE_FILES_DIR/v3d-env/ (mimo nginx docroot a mimo git; da se kdykoli znovu vyrobit ze
Sdileneho disku). Seznam doplnenych HDRI je v app_settings `v3d_env_extra` (JSON seznam {key, label, mul0, rot0_deg, w, h, source_id, source_name, created, by}). Verejny
GET /api/public/v3d-vzhled (api/v3d_vzhled.py) ho vraci jako `hdri_extra` [{key, label, mul0, rot0_deg, url, lo}] a viewer ho zaradi pres V3D.addEnvLibrary; soubory se servíruji z
GET /api/public/v3d-env/<klic>_<1024|256>.hdr (jen klice z evidence). Uložený vzhled (env.hdri) smi pouzit i doplnene klice (v3d_vzhled.over_env).

  GET    /api/admin/v3d-env/zdroje      admin (nastaveni/upravit): .hdr na Sdilenem disku, ktere jde pridat (+ uz doplnena HDRI)
  POST   /api/admin/v3d-env/import      telo {file_id, label?}: prevede a prida; 400/403/404/409 s ceskou vetou
  DELETE /api/admin/v3d-env/<klic>      smaze doplnene HDRI (409, kdyz je ulozene ve vzhledu nabidek)
  GET    /api/public/v3d-env/<soubor>   verejne, jen <klic>_1024.hdr / <klic>_256.hdr z evidence

Hlidano: opravneni nastaveni/upravit + pristup ke slozce Sdileneho disku (drive._user_can_access_folder); zdroj JEN podle id souboru (nikdy cesta od klienta, realpath v DRIVE_FILES_DIR);
jen .hdr, <= 150 MB, hlavicka #?RADIANCE; zakazana HDRI (modern_buildings - Robert 2026-09-28, stejny seznam jako api/render_hdri.py ZAKAZANE_HDRI); klic se generuje na serveru
([a-z][a-z0-9_]{2,39}, bez kolize s vestavenymi ani doplnenymi); nejvyse 12 doplnenych; jeden import naraz (flock); atomicky zapis (tmp + os.replace, nejdriv soubory, pak evidence);
vstup siroky nejvyse 8192 px (pamet); audit. Docs: docs/KONTRAKT_NABIDKA_3D.md (5k)."""
import fcntl
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

from flask import abort, jsonify, request, send_file

from app import app, get_conn, require_permission, current_user, log_audit
from quotes import PRIVATE_FILES_DIR
from drive import DRIVE_FILES_DIR, _user_can_access_folder

KLIC_EXTRA = "v3d_env_extra"
KLIC_VZHLED = "v3d_nabidka_vzhled"
ENV_DIR = os.path.join(PRIVATE_FILES_DIR, "v3d-env")
os.makedirs(ENV_DIR, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
PREVOD_PY = os.path.join(HERE, "v3d_env_prevod.py")
REF_HDRI = os.path.join(os.path.dirname(HERE), "webapp", "js", "v3d", "env", "crossfit_1024.hdr")      # referencni jas (mul0)
MAX_EXTRA = 12                                  # nejvyse tolik doplnenych HDRI
ZDROJ_MAX_B = 150 * 1024 * 1024                 # nejvetsi zdrojovy soubor
TIMEOUT_S = 50                                  # prevod (8k ~10 s v klidu, ~40 s pri velke zatezi); gunicorn ma timeout 60 s, takze davame vlastni mensi limit
MEM_B = 3 * 1024 ** 3                           # RLIMIT_AS podprocesu (8k vstup ~1,2 GB)
KEY_RE = re.compile(r"[a-z][a-z0-9_]{2,39}")
SOUBOR_RE = re.compile(r"([a-z][a-z0-9_]{2,39})_(1024|256)\.hdr")
BUILTIN = ("crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost")     # = v3d_vzhled.ENV_HDRI (shodu hlida test)
ZAKAZANE = ("modern_buildings",)                # = api/render_hdri.py ZAKAZANE_HDRI (shodu hlida test)
CHYBA_ZAKAZANA = "HDRI modern_buildings je zakázaná, nepoužívat."
MUL0_MEZE = (0.05, 20.0)
TTL_S = 5.0
_cache = {"t": 0.0, "v": None}


def _zakazana(filename):
    return any(z in (filename or "").lower() for z in ZAKAZANE)


def _cislo(v):
    return not isinstance(v, bool) and isinstance(v, (int, float)) and v == v and v not in (float("inf"), float("-inf"))


def _zaznam_ok(z):
    return (isinstance(z, dict) and isinstance(z.get("key"), str) and KEY_RE.fullmatch(z["key"]) is not None and z["key"] not in BUILTIN
            and isinstance(z.get("label"), str) and 0 < len(z["label"]) <= 60 and _cislo(z.get("mul0")) and MUL0_MEZE[0] <= z["mul0"] <= MUL0_MEZE[1])


def nacti_extra(force=False):
    """Seznam doplnenych HDRI (platne zaznamy z app_settings); nikdy nevyhodi (chyba / poskozena hodnota = prazdny seznam)."""
    ted = time.time()
    if not force and _cache["v"] is not None and ted - _cache["t"] < TTL_S:
        return list(_cache["v"])
    v = []
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC_EXTRA,))
                r = cur.fetchone()
        finally:
            conn.close()
        if r and r.get("setting_value"):
            data = json.loads(r["setting_value"])
            if isinstance(data, list):
                videno = set()
                for z in data:
                    if _zaznam_ok(z) and z["key"] not in videno:
                        videno.add(z["key"])
                        v.append(z)
    except Exception as e:                                      # noqa: BLE001
        app.logger.warning("v3d env extra: seznam nejde nacist, plati jen vestavena HDRI: %s", e)
        v = []
    _cache["t"], _cache["v"] = ted, v
    return list(v)


def extra_klice(force=False):
    return tuple(z["key"] for z in nacti_extra(force))


def public_extra():
    """Pro verejny GET vzhledu: [{key, label, mul0, rot0_deg, url, lo}] (zadne ID Sdileneho disku ani nazvy zdrojovych souboru)."""
    return [{"key": z["key"], "label": z["label"], "mul0": z["mul0"], "rot0_deg": float(z.get("rot0_deg") or 0.0),
             "url": "/api/public/v3d-env/%s_1024.hdr" % z["key"], "lo": "/api/public/v3d-env/%s_256.hdr" % z["key"]} for z in nacti_extra()]


def _zapis_extra(seznam):
    if seznam:
        val = json.dumps(seznam, sort_keys=True, ensure_ascii=False)
        sql, args = "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (KLIC_EXTRA, val, val)
    else:
        sql, args = "DELETE FROM app_settings WHERE setting_key=%s", (KLIC_EXTRA,)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        conn.commit()
    finally:
        conn.close()
    _cache["t"], _cache["v"] = time.time(), list(seznam)


def _cesta_slozky(cur, folder_id):
    casti, videno = [], set()
    while folder_id is not None and folder_id not in videno:
        videno.add(folder_id)
        cur.execute("SELECT name, parent_folder_id FROM shared_drive_folders WHERE id=%s", (folder_id,))
        row = cur.fetchone()
        if not row:
            break
        casti.append(row["name"])
        folder_id = row["parent_folder_id"]
    return " / ".join(reversed(casti)) if casti else "Kořen disku"


def navrh_klice(filename, obsazene):
    """Klic z nazvu souboru: male pismena / cisla / podtrzitka, bez pripony a bez rozliseni (_4k), 3-40 znaku, unikatni (pripadne _2, _3, ...)."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0].lower()
    stem = re.sub(r"[\s_\-]*\d{1,2}k$", "", stem)
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
    if not stem or not stem[0].isalpha():
        stem = "hdri_" + stem
    stem = stem[:34].rstrip("_")
    if len(stem) < 3:
        stem = (stem + "_hdri")[:34]
    key, n = stem, 2
    while key in obsazene:
        key = "%s_%d" % (stem, n)
        n += 1
    return key


def navrh_labelu(klic):
    return klic.replace("_", " ").strip().capitalize()[:60]


def _admin_zaznam(z):
    return {"key": z["key"], "label": z["label"], "mul0": z["mul0"], "w": z.get("w"), "h": z.get("h"), "source_name": z.get("source_name"), "created": z.get("created")}


@app.get("/api/admin/v3d-env/zdroje")
@require_permission("nastaveni", "upravit")
def v3d_env_zdroje():
    """Soubory .hdr na Sdilenem disku, ktere jde pridat (nezakazane, ke kterym ma uzivatel pristup, jeste nedoplnene) + uz doplnena HDRI."""
    user = current_user()
    extra = nacti_extra(force=True)
    pouzita = {z.get("source_id") for z in extra}
    obsazene = set(BUILTIN) | {z["key"] for z in extra}
    zdroje = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, folder_id, size_bytes FROM shared_drive_files ORDER BY filename")
            for r in cur.fetchall():
                if os.path.splitext(r["filename"])[1].lower() != ".hdr" or _zakazana(r["filename"]) or r["id"] in pouzita:
                    continue
                if not _user_can_access_folder(cur, user, r["folder_id"]):
                    continue
                k = navrh_klice(r["filename"], obsazene)
                zdroje.append({"id": r["id"], "filename": r["filename"], "size_bytes": r["size_bytes"], "folder": _cesta_slozky(cur, r["folder_id"]),
                               "moc_velke": bool(r["size_bytes"] and r["size_bytes"] > ZDROJ_MAX_B), "navrh_label": navrh_labelu(k)})
    finally:
        conn.close()
    return jsonify({"max": MAX_EXTRA, "pocet": len(extra), "zdroje": zdroje, "extra": [_admin_zaznam(z) for z in extra], "max_zdroj_mb": ZDROJ_MAX_B // (1024 * 1024)})


def _limity():                                  # v podprocesu pred spustenim: strop pameti (priorita zustava: import je vzacny a ma stihnout limit)
    resource.setrlimit(resource.RLIMIT_AS, (MEM_B, MEM_B))


def _spust_prevod(src, out_dir, key):
    """Spusti prevod v podprocesu; vraci slovnik se statistikou, nebo vyhodi ValueError s ceskym duvodem."""
    cmd = [sys.executable, "-B", PREVOD_PY, "--src", src, "--out", out_dir, "--key", key, "--ref", REF_HDRI]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S, preexec_fn=_limity)
    except subprocess.TimeoutExpired:
        raise ValueError("Převod HDRI trval déle než %d s a byl zrušen. Zkus menší soubor (např. 4k) nebo to zopakuj, až server nebude zatížený." % TIMEOUT_S)
    if p.returncode != 0:
        msg = (p.stderr or "").strip().splitlines()
        raise ValueError(("Převod HDRI selhal: " + msg[-1]) if msg and p.returncode == 2 else "Převod HDRI selhal (kód %s)." % p.returncode)
    try:
        return json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception:                                           # noqa: BLE001
        raise ValueError("Převod HDRI nevrátil výsledek.")


@app.post("/api/admin/v3d-env/import")
@require_permission("nastaveni", "upravit")
def v3d_env_import():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) - {"file_id", "label"}:
        return jsonify({"error": "telo musi byt JSON objekt {file_id, label?}"}), 400
    fid = body.get("file_id")
    if isinstance(fid, bool) or not isinstance(fid, int):
        return jsonify({"error": "file_id musi byt cele cislo (id souboru na Sdilenem disku)"}), 400
    label = body.get("label")
    if label is not None:
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 60:
            return jsonify({"error": "label musi byt text 1 az 60 znaku"}), 400
        label = " ".join(label.split())
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, filename, stored_filename, folder_id, size_bytes FROM shared_drive_files WHERE id=%s", (fid,))
            r = cur.fetchone()
            if not r:
                return jsonify({"error": "Soubor na Sdíleném disku nenalezen."}), 404
            if not _user_can_access_folder(cur, user, r["folder_id"]):
                return jsonify({"error": "Nemáš přístup do složky, kde ten soubor leží."}), 403
    finally:
        conn.close()
    if os.path.splitext(r["filename"])[1].lower() != ".hdr":
        return jsonify({"error": "Vybraný soubor není HDRI ve formátu .hdr (EXR zatím nejde)."}), 400
    if _zakazana(r["filename"]):
        return jsonify({"error": CHYBA_ZAKAZANA}), 400
    koren = os.path.realpath(DRIVE_FILES_DIR)
    cesta = os.path.realpath(os.path.join(koren, str(r["stored_filename"] or "")))
    if not cesta.startswith(koren + os.sep) or not os.path.isfile(cesta):
        return jsonify({"error": "Soubor na disku chybí nebo má neplatnou cestu."}), 404 if not os.path.isfile(cesta) else 400
    velikost = os.path.getsize(cesta)
    if velikost > ZDROJ_MAX_B:
        return jsonify({"error": "Soubor je moc velký (%d MB, nejvíc %d MB) – zmenši ho a zkus znovu." % (velikost // (1024 * 1024), ZDROJ_MAX_B // (1024 * 1024))}), 400
    with open(cesta, "rb") as f:
        if not f.read(16).startswith((b"#?RADIANCE", b"#?RGBE")):
            return jsonify({"error": "Soubor není Radiance .hdr (chybí hlavička #?RADIANCE)."}), 400
    zamek = open(os.path.join(ENV_DIR, ".import.lock"), "a+")
    try:
        try:
            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return jsonify({"error": "Právě běží jiný import HDRI – počkej chvíli a zopakuj to."}), 409
        extra = nacti_extra(force=True)
        if len(extra) >= MAX_EXTRA:
            return jsonify({"error": "Je doplněno už %d HDRI (maximum). Nějaké nejdřív smaž." % MAX_EXTRA}), 409
        if any(z.get("source_id") == fid for z in extra):
            return jsonify({"error": "Tohle HDRI už je doplněné."}), 409
        klic = navrh_klice(r["filename"], set(BUILTIN) | {z["key"] for z in extra})
        tmp = tempfile.mkdtemp(prefix=".tmp-", dir=ENV_DIR)
        try:
            try:
                stat = _spust_prevod(cesta, tmp, klic)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            nove = ["%s_1024.hdr" % klic, "%s_256.hdr" % klic]
            for n in nove:
                if not os.path.isfile(os.path.join(tmp, n)):
                    return jsonify({"error": "Převod HDRI nevytvořil očekávané soubory."}), 400
            for n in nove:
                os.replace(os.path.join(tmp, n), os.path.join(ENV_DIR, n))
            zaznam = {"key": klic, "label": label or navrh_labelu(klic), "mul0": stat["mul0"], "rot0_deg": 0.0, "w": stat.get("w"), "h": stat.get("h"),
                      "source_id": fid, "source_name": r["filename"], "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "by": user["id"] if user else None}
            try:
                _zapis_extra(extra + [zaznam])
            except Exception:                                   # noqa: BLE001 - evidence se nezapsala: nenechat sirotky
                for n in nove:
                    try:
                        os.remove(os.path.join(ENV_DIR, n))
                    except OSError:
                        pass
                raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        try:
            fcntl.flock(zamek, fcntl.LOCK_UN)
        finally:
            zamek.close()
    log_audit(user["id"] if user else None, "create", "v3d_env", None, {"key": klic, "source": r["filename"], "mul0": stat["mul0"]})
    return jsonify({"ok": True, "polozka": {"key": klic, "label": zaznam["label"], "mul0": zaznam["mul0"], "rot0_deg": 0.0,
                                            "url": "/api/public/v3d-env/%s_1024.hdr" % klic, "lo": "/api/public/v3d-env/%s_256.hdr" % klic}})


def _vzhled_pouziva(klic):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC_VZHLED,))
            r = cur.fetchone()
    finally:
        conn.close()
    try:
        v = json.loads(r["setting_value"]) if r and r.get("setting_value") else None
    except Exception:                                           # noqa: BLE001
        return False
    return bool(isinstance(v, dict) and isinstance(v.get("env"), dict) and v["env"].get("hdri") == klic)


@app.delete("/api/admin/v3d-env/<klic>")
@require_permission("nastaveni", "upravit")
def v3d_env_smaz(klic):
    if not KEY_RE.fullmatch(klic or ""):
        return jsonify({"error": "neplatny klic"}), 400
    zamek = open(os.path.join(ENV_DIR, ".import.lock"), "a+")
    try:
        try:
            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return jsonify({"error": "Právě běží import HDRI – počkej chvíli a zopakuj to."}), 409
        extra = nacti_extra(force=True)
        if klic not in [z["key"] for z in extra]:
            return jsonify({"error": "Takové doplněné HDRI není."}), 404
        if _vzhled_pouziva(klic):
            return jsonify({"error": "Tohle HDRI je uložené ve vzhledu nabídek – nejdřív ulož jiné HDRI (nebo vrať výchozí vzhled)."}), 409
        _zapis_extra([z for z in extra if z["key"] != klic])
        for n in ("%s_1024.hdr" % klic, "%s_256.hdr" % klic):
            try:
                os.remove(os.path.join(ENV_DIR, n))
            except OSError:
                pass
    finally:
        try:
            fcntl.flock(zamek, fcntl.LOCK_UN)
        finally:
            zamek.close()
    user = current_user()
    log_audit(user["id"] if user else None, "delete", "v3d_env", None, {"key": klic})
    return jsonify({"ok": True})


@app.get("/api/public/v3d-env/<fname>")
def v3d_env_soubor(fname):
    """Verejne: male HDRI doplnene ze Sdileneho disku (jen klice z evidence; zadna cesta od klienta)."""
    m = SOUBOR_RE.fullmatch(fname or "")
    if not m or m.group(1) not in extra_klice():
        abort(404)
    cesta = os.path.join(ENV_DIR, fname)
    if not os.path.isfile(cesta):
        abort(404)
    resp = send_file(cesta, mimetype="application/octet-stream", conditional=True, max_age=3600)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
