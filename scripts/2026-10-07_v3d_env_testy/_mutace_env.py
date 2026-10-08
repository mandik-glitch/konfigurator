#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mutacni kontrola test_env_import_api.py (bot10, 2026-10-07): do kopie api/v3d_env_import.py (nebo v3d_env_prevod.py) vlozi vzdy jednu chybu (hlavne bezpecnostni kontroly) a overi, ze test
SELZE. "!!!" = mutaci test nechytil (exit 1). Nic se nezapisuje do repa ani do DB.
  api/venv/bin/python scripts/2026-10-07_v3d_env_testy/_mutace_env.py [pocet paralelnich behu, vychozi 3]       (V3D_ENV_DIR = kandidat s v3d_env_import.py + v3d_env_prevod.py, vychozi repo api/)"""
import concurrent.futures as cf
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.environ.get("V3D_ENV_DIR") or os.path.join(REPO, "api")
TEST = os.path.join(HERE, "test_env_import_api.py")
PAR = int(sys.argv[1]) if len(sys.argv) > 1 else 3
IMP = open(os.path.join(SRC, "v3d_env_import.py"), encoding="utf-8").read()
PRE = open(os.path.join(SRC, "v3d_env_prevod.py"), encoding="utf-8").read()
PERM = '@require_permission("nastaveni", "upravit")\n'
# (nazev, soubor "i" | "p", kotva, nahrada)
MUT = [
    ("zdroje bez opravneni", "i", '@app.get("/api/admin/v3d-env/zdroje")\n' + PERM, '@app.get("/api/admin/v3d-env/zdroje")\n'),
    ("import bez opravneni", "i", '@app.post("/api/admin/v3d-env/import")\n' + PERM, '@app.post("/api/admin/v3d-env/import")\n'),
    ("smazani bez opravneni", "i", '@app.delete("/api/admin/v3d-env/<klic>")\n' + PERM, '@app.delete("/api/admin/v3d-env/<klic>")\n'),
    ("zakazana HDRI se importuje", "i", '    if _zakazana(r["filename"]):\n        return jsonify({"error": CHYBA_ZAKAZANA}), 400\n', ""),
    ("zakazana HDRI se nabizi", "i", 'or _zakazana(r["filename"]) or r["id"] in pouzita', 'or r["id"] in pouzita'),
    ("import ignoruje pristup ke slozce", "i", '            if not _user_can_access_folder(cur, user, r["folder_id"]):\n                return jsonify({"error": "Nemáš přístup do složky, kde ten soubor leží."}), 403\n', ""),
    ("zdroje ukazuji i zamcene slozky", "i", '                if not _user_can_access_folder(cur, user, r["folder_id"]):\n                    continue\n', ""),
    ("cesta mimo adresar Sdileneho disku", "i", 'if not cesta.startswith(koren + os.sep) or not os.path.isfile(cesta):', 'if not os.path.isfile(cesta):'),
    ("pripona se nekontroluje", "i", '    if os.path.splitext(r["filename"])[1].lower() != ".hdr":\n        return jsonify({"error": "Vybraný soubor není HDRI ve formátu .hdr (EXR zatím nejde)."}), 400\n', ""),
    ("velikost se nekontroluje", "i", '    if velikost > ZDROJ_MAX_B:', '    if False:'),
    ("hlavicka #?RADIANCE se nekontroluje", "i", 'if not f.read(16).startswith((b"#?RADIANCE", b"#?RGBE")):', 'if False:'),
    ("limit doplnenych HDRI zrusen", "i", '        if len(extra) >= MAX_EXTRA:', '        if False:'),
    ("stejny zdroj lze pridat znovu", "i", '        if any(z.get("source_id") == fid for z in extra):', '        if False:'),
    ("import bez zamku proti soubehu", "i", '        try:\n            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)\n        except OSError:\n            return jsonify({"error": "Právě běží jiný import HDRI – počkej chvíli a zopakuj to."}), 409\n', '        pass\n'),
    ("smazani bez zamku", "i", '        try:\n            fcntl.flock(zamek, fcntl.LOCK_EX | fcntl.LOCK_NB)\n        except OSError:\n            return jsonify({"error": "Právě běží import HDRI – počkej chvíli a zopakuj to."}), 409\n', '        pass\n'),
    ("docasna slozka se neuklizi", "i", '            shutil.rmtree(tmp, ignore_errors=True)\n', '            pass\n'),
    ("pri selhani evidence zustanou soubory", "i", '                for n in nove:\n                    try:\n                        os.remove(os.path.join(ENV_DIR, n))\n                    except OSError:\n                        pass\n                raise\n', '                raise\n'),
    ("prevod bez casoveho limitu", "i", 'timeout=TIMEOUT_S, preexec_fn=_limity', 'preexec_fn=_limity'),
    ("kolize klicu se neresi", "i", '    while key in obsazene:', '    while False:'),
    ("vestavene klice se muzou prepsat", "i", 'BUILTIN = ("crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost")', 'BUILTIN = ()'),
    ("verejny soubor bez kontroly evidence", "i", 'if not m or m.group(1) not in extra_klice():', 'if not m:'),
    ("verejny soubor: nazev se kontroluje jen zacatkem", "i", 'SOUBOR_RE.fullmatch(fname or "")', 'SOUBOR_RE.match(fname or "")'),
    ("verejny soubor bez nosniff", "i", '    resp.headers["X-Content-Type-Options"] = "nosniff"\n    return resp\n', '    return resp\n'),
    ("smazani HDRI pouziteho ve vzhledu", "i", '        if _vzhled_pouziva(klic):', '        if False:'),
    ("smazani nesmaze soubory", "i", '        for n in ("%s_1024.hdr" % klic, "%s_256.hdr" % klic):\n            try:\n                os.remove(os.path.join(ENV_DIR, n))\n            except OSError:\n                pass\n    finally:', '        pass\n    finally:'),
    ("import bez auditu", "i", '    log_audit(user["id"] if user else None, "create", "v3d_env", None, {"key": klic, "source": r["filename"], "mul0": stat["mul0"]})\n', ""),
    ("evidence bez kontroly zaznamu", "i", 'if _zaznam_ok(z) and z["key"] not in videno:', 'if True:'),
    ("verejny vypis prozrazuje nazev zdroje", "i", '    return [{"key": z["key"], "label": z["label"], "mul0": z["mul0"],', '    return [{"key": z["key"], "label": z["label"], "mul0": z["mul0"], "source_name": z.get("source_name"),'),
    ("klic z nazvu bez odstraneni rozliseni", "i", '    stem = re.sub(r"[\\s_\\-]*\\d{1,2}k$", "", stem)\n', ''),
    ("nazev se nesjednocuje", "i", '        label = " ".join(label.split())\n', ''),
    ("nazev bez limitu delky", "i", 'len(label.strip()) > 60', 'len(label.strip()) > 6000'),
    ("file_id bool se prijme", "i", 'if isinstance(fid, bool) or not isinstance(fid, int):', 'if not isinstance(fid, int):'),
    ("telo bez kontroly neznamych klicu", "i", 'if not isinstance(body, dict) or set(body) - {"file_id", "label"}:', 'if not isinstance(body, dict):'),
    # prevod
    ("prevod: sirka nad 8192 se prijme", "p", '    if W > w_max:', '    if False:'),
    ("prevod: ne 2:1 se prijme", "p", '    if W < 64 or H < 32 or W != 2 * H:', '    if W < 64 or H < 32:'),
    ("prevod: moc male HDRI se prijme", "p", '    if W < w_min:', '    if False:'),
    ("prevod: jiny format se prijme", "p", '        if not fmt_ok:', '        if False:'),
    ("prevod: mul0 podle medianu misto prumeru", "p", 'def mean_lum(rgb):\n    return float((0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]).mean())', 'def mean_lum(rgb):\n    return float(np.median(0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]))'),
    ("prevod: zmenseni vzorkovanim misto prumerovani", "p", '        return rgb.reshape(H, fy, W, fx, 3).mean(axis=(1, 3), dtype=np.float32)', '        return rgb[::fy, ::fx]'),
    ("prevod: Pillow BOX nahrazen NEAREST", "p", 'resize((W, H), Image.BOX)', 'resize((W, H), Image.NEAREST)'),
    ("prevod: cerna HDRI se prijme", "p", '    if lum <= 1e-9:', '    if False:'),
    ("prevod: useknuty radek se neosetri", "p", '                            if n == 0 or x + n > W or pos + n > len(data):\n                                raise Chyba("poskozeny radek v .hdr")\n', ''),
]


def beh(i):
    nazev, kde, a, b = MUT[i]
    zdroj = IMP if kde == "i" else PRE
    if zdroj.count(a) != 1:
        return (i, nazev, None, "KOTVA nalezena %d x" % zdroj.count(a))
    d = tempfile.mkdtemp(prefix="mutace_env_")
    try:
        open(os.path.join(d, "v3d_env_import.py"), "w", encoding="utf-8").write(zdroj.replace(a, b) if kde == "i" else IMP)
        open(os.path.join(d, "v3d_env_prevod.py"), "w", encoding="utf-8").write(zdroj.replace(a, b) if kde == "p" else PRE)
        r = subprocess.run([sys.executable, "-B", TEST], env=dict(os.environ, V3D_ENV_DIR=d, PYTHONDONTWRITEBYTECODE="1"), capture_output=True, text=True, timeout=600)
        prvni = [l for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))][:2]
        return (i, nazev, r.returncode != 0, "; ".join(x[:70] for x in prvni))
    finally:
        shutil.rmtree(d, ignore_errors=True)


if os.environ.get("MUT_DRY"):
    for i, (n, k, a, b) in enumerate(MUT):
        z = IMP if k == "i" else PRE
        print("%2d %-60s kotev: %d" % (i + 1, n, z.count(a)))
    sys.exit(0)
bad = 0
with cf.ThreadPoolExecutor(PAR) as ex:
    for i, nazev, ok, info in ex.map(beh, range(len(MUT))):
        bad += 0 if ok else 1
        print(("chyceno  " if ok else "!!! NECHYCENO ") + "| %2d %s | %s" % (i + 1, nazev, info), flush=True)
print("\n%d mutaci, chyceno %d, nechyceno/chyba pripravy %d" % (len(MUT), len(MUT) - bad, bad))
sys.exit(1 if bad else 0)
