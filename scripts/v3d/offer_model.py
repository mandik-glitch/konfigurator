#!/usr/bin/env python3
"""3D model online nabidky z Vandr karty pro ziva volani z API (bot10,
2026-10-01, Robert: 3D scena online nabidky).

    build_offer_model(shop_product_id, conn_readonly, cache_dir=None)
        -> (offer_glb_bytes, geom)

Kroky:
 1) ctx: build_ctx.sestav_ctx(shop_product_id, konf_conn=conn_readonly,
    strict=True) - na predanem spojeni jen SELECT (shop_products,
    app_settings), nic se nezavira ani nerollbackuje (pooled spojeni);
    Vandr data jen pres `php artisan vandr:offer-data <uuid> --v3d`
    (podproces s env jen PATH - zadne Vandr udaje v tomto procesu)
 2) klic cache vd_<id>_<glb_sha12>_<verze buildu>_<ctx_sha8>; kdyz v cache
    je (.glb i .json), vrati se bez Blenderu
 3) Blender na pozadi, CPU (scripts/v3d/vandr_offer_build.py --ctx),
    limit BUILD_TIMEOUT_S = 50 s (a zbytek celkoveho limitu), env jen PATH
 4) v3d_glb.sanitize(clean_glb, geom["v3d"]) - serverova pojistka
 5) zapis do cache (atomicky: docasny soubor + os.replace, .json az po .glb)
CHYBY JSOU HLASITE: cokoli selze = V3DBuildError s textem pro admina
(posledni radky vystupu Blenderu); do cache se nic nezapise, nic se tise
nevrati. Soubeh dvou pozadavku na stejny klic hlida zamek souboru (druhy
pocka a vezme vysledek z cache).

Verze buildu = BUILD_VERZE + sha6 kodu (build, modul pohybu, knihovna roli,
sanitizer): zmena kterehokoli z nich sama zneplatni cache. Zmena dat (karta,
panel materialu, pohyby-vychozi.json, kusovnik ve Vandru) zmeni ctx_sha8.

geom = geom.json z buildu + "cache" (klic, verze, hit) + "ctx_warnings".
Varovani (geom["warnings"], geom["ctx_warnings"]) jsou jen pro admina - obsahuji
unity_id, do zakaznickeho GLB se nedostanou.

CLI (server, jen cteni DB): api/venv/bin/python3 scripts/v3d/offer_model.py
    <shop_product_id> [--cache DIR] [-o model.glb] [--geom geom.json]
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KOREN = os.path.dirname(os.path.dirname(SCRIPT_DIR))          # repo (nebo kandidat)
sys.dont_write_bytecode = True                                 # zadny __pycache__ do repa
for _d in (SCRIPT_DIR, os.path.join(KOREN, "api")):
    if _d not in sys.path:
        sys.path.insert(0, _d)
import build_ctx  # noqa: E402
import v3d_glb  # noqa: E402

KONF_REPO = os.environ.get("KONFIGURATOR_REPO") or KOREN        # na serveru /opt/konfigurator
BLENDER_BIN = "/opt/blender-5.2/blender"
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, "vandr_offer_build.py")
BUILD_TIMEOUT_S = 50
CELKOVY_LIMIT_S = 57          # gunicorn --timeout 60
BUILD_VERZE = "b3"            # zvysit, kdyz se meni vystup bez zmeny kodu (napr. jiny Blender)
VYCHOZI_CACHE = os.path.join(KONF_REPO, "private-files", "v3d-cache")


class V3DBuildError(RuntimeError):
    """3D model nabidky nevznikl - text je pro admina (hlasita chyba)."""


def _kod_soubory():
    out = [BUILD_SCRIPT, os.path.join(SCRIPT_DIR, "vandr_motions.py"), v3d_glb.__file__]
    lib = build_ctx._najdi_lib()
    if lib:
        out.append(os.path.join(lib, "_render_prirazeni_lib.py"))
    return out


def verze_buildu():
    h = hashlib.sha256()
    for p in _kod_soubory():
        h.update(os.path.basename(p).encode("utf-8") + b"\0")
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except OSError:
            h.update(b"(chybi)")
    return "%s-%s" % (BUILD_VERZE, h.hexdigest()[:6])


def klic_cache(shop_product_id, ctx, verze=None):
    return "vd_%d_%s_%s_%s" % (int(shop_product_id), ctx.get("glb_sha12") or "bezglb", verze or verze_buildu(),
                               build_ctx.ctx_hash(ctx))


@contextlib.contextmanager
def _zamek(cesta, do_casu):
    try:
        fh = open(cesta, "a+")
    except OSError as e:
        raise V3DBuildError("Zamek cache 3D modelu nejde otevrit (%s) - zkontrolujte vlastnika a prava adresare "
                            "private-files/v3d-cache (musi byt zapisovatelny uzivatelem sluzby)" % type(e).__name__)
    try:
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() > do_casu:
                    raise V3DBuildError("3D model teto karty prave sestavuje jiny pozadavek - zkuste to za chvili")
                time.sleep(0.2)
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()


def _z_cache(glb_p, json_p):
    if not (os.path.isfile(glb_p) and os.path.isfile(json_p)):
        return None
    try:
        with open(json_p, encoding="utf-8") as f:
            geom = json.load(f)
        with open(glb_p, "rb") as f:
            data = f.read()
    except (OSError, ValueError):
        return None
    if data[:4] != b"glTF" or not isinstance(geom, dict):
        return None
    return data, geom


def _zapis_atomicky(cesta, data):
    d = os.path.dirname(cesta)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, cesta)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def _konec(text, n=2000):
    return (text or "")[-n:]


def spust_build(glb_in, ctx, timeout_s, blender_bin=BLENDER_BIN):
    """Blender build v docasnem adresari -> (clean_glb_bytes, geom). Chyba =
    V3DBuildError (vcetne konce vystupu Blenderu)."""
    with tempfile.TemporaryDirectory(prefix="v3d_build_") as tmp:
        ctx_p, geom_p, clean_p = (os.path.join(tmp, n) for n in ("ctx.json", "geom.json", "clean.glb"))
        with open(ctx_p, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, default=str)
        try:
            proc = subprocess.run(
                [blender_bin, "-b", "--factory-startup", "-P", BUILD_SCRIPT, "--", glb_in, geom_p, clean_p,
                 "--ctx", ctx_p],
                capture_output=True, text=True, timeout=timeout_s, env=build_ctx._clean_subprocess_env(), cwd=tmp)
        except subprocess.TimeoutExpired as e:
            vystup = (e.stdout or b"") if isinstance(e.stdout, bytes) else (e.stdout or "")
            if isinstance(vystup, bytes):
                vystup = vystup.decode("utf-8", "replace")
            raise V3DBuildError("Sestaveni 3D modelu prekrocilo %d s (Blender ukoncen). %s"
                                % (timeout_s, _konec(vystup, 600)))
        except OSError as e:
            raise V3DBuildError("Blender nejde spustit (%s: %s)" % (type(e).__name__, e))
        if proc.returncode != 0 or "GEOM_OK" not in proc.stdout:
            raise V3DBuildError("Sestaveni 3D modelu selhalo (rc=%s): %s"
                                % (proc.returncode, _konec(proc.stdout + "\n" + proc.stderr)))
        try:
            with open(geom_p, encoding="utf-8") as f:
                geom = json.load(f)
            with open(clean_p, "rb") as f:
                clean = f.read()
        except (OSError, ValueError) as e:
            raise V3DBuildError("Build nahlasil GEOM_OK, ale vystup chybi/neni citelny (%s)" % type(e).__name__)
    if not isinstance(geom, dict) or not isinstance(geom.get("v3d"), dict):
        raise V3DBuildError("geom.json z buildu nema v3d")
    return clean, geom


def build_offer_model(shop_product_id, conn_readonly, cache_dir=None, *, vandr_fetch=None, blender_bin=BLENDER_BIN,
                      timeout_s=BUILD_TIMEOUT_S, celkovy_limit_s=CELKOVY_LIMIT_S, povolit_bez_vandr=False):
    """-> (offer_glb_bytes, geom). Chyba = V3DBuildError (hlasite), nic se
    nezapise. conn_readonly: spojeni do konfigurator DB (napr. get_conn()),
    pouzije se jen na SELECTy a NEzavira se. vandr_fetch: jen pro testy."""
    t0 = time.time()
    try:
        ctx = build_ctx.sestav_ctx(shop_product_id, konf_conn=conn_readonly, vandr_fetch=vandr_fetch,
                                   strict=not povolit_bez_vandr)
    except build_ctx.VandrDataError as e:
        raise V3DBuildError("Nacteni dat z Vandru selhalo: %s" % e)
    except (LookupError, ValueError) as e:
        raise V3DBuildError(str(e))
    glb_in = ctx.get("glb")
    if not glb_in or not os.path.isfile(glb_in):
        raise V3DBuildError("Karta nema 3D model (GLB) na disku: %s" % (ctx.get("glb_file") or "-"))
    verze = verze_buildu()
    klic = klic_cache(shop_product_id, ctx, verze)
    cache_dir = cache_dir or VYCHOZI_CACHE
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError as e:
        raise V3DBuildError("Adresar cache 3D modelu nejde vytvorit (%s)" % type(e).__name__)
    glb_p = os.path.join(cache_dir, klic + ".glb")
    json_p = os.path.join(cache_dir, klic + ".json")
    meta = {"klic": klic, "verze_buildu": verze, "ctx_sha8": build_ctx.ctx_hash(ctx), "glb_sha12": ctx.get("glb_sha12")}

    hit = _z_cache(glb_p, json_p)
    if hit:
        data, geom = hit
        geom["cache"] = dict(meta, hit=True)
        return data, geom
    with _zamek(os.path.join(cache_dir, klic + ".lock"), t0 + celkovy_limit_s):
        hit = _z_cache(glb_p, json_p)              # mezitim postavil jiny pozadavek
        if hit:
            data, geom = hit
            geom["cache"] = dict(meta, hit=True)
            return data, geom
        zbyva = celkovy_limit_s - (time.time() - t0)
        limit = int(min(timeout_s, zbyva))
        if limit < 5:
            raise V3DBuildError("Na sestaveni 3D modelu nezbyva cas (ctx trval %.0f s)" % (time.time() - t0))
        clean, geom = spust_build(glb_in, ctx, limit, blender_bin=blender_bin)
        try:
            offer = v3d_glb.sanitize(clean, geom["v3d"])
        except ValueError as e:                        # V3DError je ValueError
            raise V3DBuildError("3D model neprosel kontrolou (sanitize): %s" % e)
        geom["ctx_warnings"] = list(ctx.get("warnings") or [])
        geom["cache"] = dict(meta, hit=False, sekundy=round(time.time() - t0, 2))
        try:
            _zapis_atomicky(glb_p, offer)
            _zapis_atomicky(json_p, json.dumps(geom, ensure_ascii=False).encode("utf-8"))
        except OSError as e:
            # hotovy model se kvuli neukladne cache nezahazuje (14+ s prace); admin to uvidi ve varovanich
            geom["cache"]["zapis"] = "selhal"
            geom["ctx_warnings"].append("cache 3D modelu se nezapsala (%s) - dalsi pozadavek postavi model znovu"
                                        % type(e).__name__)
        return offer, geom


def main():
    ap = argparse.ArgumentParser(description="3D model online nabidky z Vandr karty (jen cteni DB)")
    ap.add_argument("shop_product_id", type=int)
    ap.add_argument("--cache", help="adresar cache (vychozi private-files/v3d-cache)")
    ap.add_argument("-o", "--out", help="kam ulozit offer GLB")
    ap.add_argument("--geom", help="kam ulozit geom.json")
    a = ap.parse_args()
    conn = build_ctx.konf_conn_ro()
    try:
        data, geom = build_offer_model(a.shop_product_id, conn, a.cache)
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()
    if a.out:
        with open(a.out, "wb") as f:
            f.write(data)
    if a.geom:
        with open(a.geom, "w", encoding="utf-8") as f:
            json.dump(geom, f, ensure_ascii=False)
    print("OFFER_OK %s %d B dc=%s varovani=%d" % (geom["cache"]["klic"], len(data), geom.get("stats", {}).get("draw_calls"),
                                                 len(geom.get("warnings") or []) + len(geom.get("ctx_warnings") or [])))


if __name__ == "__main__":
    try:
        main()
    except V3DBuildError as e:
        print("CHYBA: %s" % e, file=sys.stderr)
        sys.exit(2)
