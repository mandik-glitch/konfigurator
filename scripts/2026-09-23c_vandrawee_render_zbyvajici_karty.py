#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Robert: "Okamzite vsechno vyrenderovat" - 8 Vandr karet, ktere uz maji
GLB (fbx_exported_at nastaveno, prevod hotovy dnes v noci), ale jeste
nebyly renderovany/aktivovany. Plna produkcni kvalita (500 vzorku, cela
162snimkova otocka), s prave finalizovanym nastavenim sceny (HDRI
crossfit_gym_2k, rotace 120 - oboje jiz TRVALE v app_settings, zadny
--hdri/--hdri-rotace-deg override tu neni potreba).

Vyuziva --shop-product-id (bot4, dnes) - Vandr karta bez product_
assemblies radku (tj.build_job_vandr()).
"""
import json, os, re, subprocess, time

REPO = "/opt/konfigurator"
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
RENDER_SCRIPT = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT_DIR = os.path.join(REPO, "private-files", "blender-renders")

SHOP_PRODUCT_IDS = [4600, 4601, 4604, 4904, 4596, 4582, 4587, 4591]


def dispatch(shop_product_id):
    cmd = [PY, RENDER_SCRIPT, "--shop-product-id", str(shop_product_id)]
    child_env = dict(os.environ)
    child_env["KONFIGURATOR_RENDER_KLIC_SOUBOR"] = "/root/.konfigurator_render_klic"
    child_env.setdefault("BOT_ID", "bot10")
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=90, env=child_env)
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RuntimeError("dispatch selhal (rc=%d):\n%s" % (proc.returncode, out))
    m = re.search(r"Uloha ([0-9a-f]{16,40}) pripravena", out)
    if not m:
        raise RuntimeError("nenasel jsem job id ve vystupu:\n%s" % out)
    return m.group(1)


def wait_done(job_id, timeout_s=2400):
    status_path = os.path.join(RENDER_OUT_DIR, "%s.status.json" % job_id)
    t0 = time.time()
    last_state = None
    while time.time() - t0 < timeout_s:
        if os.path.exists(status_path):
            try:
                st = json.load(open(status_path, encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                st = None
            if st:
                if st.get("state") != last_state:
                    last_state = st.get("state")
                    print("    stav: %s" % last_state, flush=True)
                if st.get("state") in ("done", "error"):
                    return st
        time.sleep(10)
    raise TimeoutError("uloha %s nedobehla do %ds" % (job_id, timeout_s))


def main():
    celkem = len(SHOP_PRODUCT_IDS)
    hotovo, chyby = 0, 0
    for i, pid in enumerate(SHOP_PRODUCT_IDS, 1):
        print("[%d/%d] shop_product_id=%d" % (i, celkem, pid), flush=True)
        pokusy = 0
        while True:
            try:
                job_id = dispatch(pid)
                break
            except RuntimeError as e:
                if "ODMITNUTO" in str(e) and "uz ceka" in str(e) and pokusy < 5:
                    pokusy += 1
                    print("    fronta obsazena, cekam 20s...", flush=True)
                    time.sleep(20)
                    continue
                print("    CHYBA DISPATCH: %s" % e, flush=True)
                chyby += 1
                job_id = None
                break
        if job_id is None:
            continue
        print("    uloha %s zarazena, cekam na dokonceni (plna kvalita, muze trvat ~20-30 min)..." % job_id, flush=True)
        try:
            st = wait_done(job_id)
        except TimeoutError as e:
            print("    CASOVY LIMIT: %s" % e, flush=True)
            chyby += 1
            continue
        if st.get("state") != "done":
            print("    CHYBA RENDER: %s" % st.get("error"), flush=True)
            chyby += 1
            continue
        hotovo += 1
        print("    OK (job %s, %.1fs, aktivováno=%s)"
              % (job_id, st.get("render_seconds") or 0, not st.get("commit_pending")), flush=True)
    print("\nHOTOVO. %d/%d OK, %d chyb." % (hotovo, celkem, chyby), flush=True)


if __name__ == "__main__":
    main()
