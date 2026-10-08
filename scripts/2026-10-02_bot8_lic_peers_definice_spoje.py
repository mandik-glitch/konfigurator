"""Oprava ulozenych lic_peers vlastnich tvaru podle DEFINICE SPOJE (bot8, 2026-10-02).

Nalez bot10: stul #577 hlasi po nacteni 32 spoju, geometrie 26; stejne #572,
"Regal 40A01 Doblo" #524 (53 vs 35). Definice spoje (Robert 2026-08-31,
PRAVIDLA_SPOJU.md): spoj jen kdyz se CELA plocha cela jednoho profilu dotyka
cela/steny druheho - dotyk hranou/rohem spoj neni. scene.html po nacteni tvaru
zapocita KAZDY par z lic_peers bez kontroly geometrie (insertCustomShape), takze
nadbytecne pary zvysuji pocet spoju a cenu v souhrnu sceny (110 Kc/spoj).

Co skript dela: u vybranych vlastnich tvaru odebere z parts[i].lic_peers dvojice,
ktere definici NEsplnuji (qa_checks.lic_peers_bad_pairs - stejna logika jako QA
kontrola lic_peers_neni_spoj), na OBOU stranach; prazdne pole lic_peers odstrani.
Nic jineho (pozice, last_joint, join_groups...) se nemeni. Custom_shapes nemaji
ulozenou cenu - zmeni se jen pocet spoju ve scene po nacteni.

NEMENI product_assemblies (#374, #503 - cena tam sedi s geometrii, viz navrh).

Spusteni v /opt/konfigurator:
    api/venv/bin/python3 scripts/2026-10-02_bot8_lic_peers_definice_spoje.py          (nahled #572, #577)
    api/venv/bin/python3 scripts/2026-10-02_bot8_lic_peers_definice_spoje.py --apply  (zapis - schvaleno bot3 2026-10-02)
    ... --shapes=524                                                                  (jen nahled/zapis jineho tvaru)
"""
import json
import os
import sys

REPO = "/opt/konfigurator"
API = os.path.join(REPO, "api")
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, API)
from _env import get_conn  # noqa: E402
import qa_checks  # noqa: E402

# Vychozi: jen tvary vytvorene IMPORTEM (#572, #577 - ulozene lic_peers presne = vystup stareho
# _profiles_touch, schvaleno bot3 2026-10-02). #524 "Regal 40A01 Doblo" postavil Robert RUCNE ve scene
# (AGENTS_LOG 2026-08-23) - neprepisovat bez jeho rozhodnuti (--shapes=...,524).
SHAPES = (572, 577)
for _a in sys.argv:
    if _a.startswith("--shapes="):
        SHAPES = tuple(int(x) for x in _a.split("=", 1)[1].split(",") if x.strip())
ZAL_DIR = os.path.join(REPO, "backups", "2026-10-02_lic_peers_definice_spoje")
ZAL = os.path.join(ZAL_DIR, "pred_zapisem.json")


def plan_for(parts, bad):
    """{index dilu: novy seznam lic_peers (None = odstranit klic)}"""
    drop = {}
    for i, j in bad:
        drop.setdefault(i, set()).add(j)
        drop.setdefault(j, set()).add(i)
    ops = {}
    for i, rm in drop.items():
        left = [x for x in (parts[i].get("lic_peers") or []) if x not in rm]
        ops[i] = left or None
    return ops


def build_expr(ops):
    """SQL vyraz nad sloupcem data (JSON_SET / JSON_REMOVE jen lic_peers danych dilu) + parametry."""
    expr, params = "data", []
    for i, left in sorted(ops.items()):
        if left is None:
            expr = f"JSON_REMOVE({expr}, '$.parts[{i}].lic_peers')"
        else:
            expr = f"JSON_SET({expr}, '$.parts[{i}].lic_peers', CAST(%s AS JSON))"
            params.append(json.dumps(left))
    return expr, params


def main():
    apply = "--apply" in sys.argv
    conn = get_conn()
    cur = conn.cursor()
    profil_glb = qa_checks._lic_peers_profile_glb(cur)
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='joint_price_czk'")
    joint_price = float(cur.fetchone()["setting_value"])
    cache = {}
    plans = []
    for sid in SHAPES:
        cur.execute("SELECT id, name, data FROM custom_shapes WHERE id=%s", (sid,))
        r = cur.fetchone()
        if not r:
            print(f"#{sid}: neexistuje - preskoceno")
            continue
        raw = r["data"]
        parts = json.loads(raw)["parts"]
        pairs, bad = qa_checks.lic_peers_bad_pairs(parts, profil_glb, cache)
        ops = plan_for(parts, bad)
        plans.append({"id": sid, "name": r["name"], "raw": raw, "pairs": pairs, "bad": bad, "ops": ops})
        print(f"#{sid} {r['name']}: {len(pairs)} paru, odebrat {len(bad)} -> {len(pairs) - len(bad)} paru "
              f"(scena po nacteni -{len(bad)} spoju = -{round(len(bad) * joint_price)} Kc v souhrnu)")
        print("   " + ", ".join(f"#{i}↔#{j}" for i, j in bad))
    if not apply:
        print("\n(nahled, nic nezapsano - zapis: --apply az po schvaleni)")
        return

    os.makedirs(ZAL_DIR, exist_ok=True)
    if os.path.exists(ZAL):
        raise SystemExit(f"CHYBA: zaloha {ZAL} uz existuje - neprepisuji")
    with open(ZAL, "w", encoding="utf-8") as f:
        json.dump([{"id": p["id"], "name": p["name"], "data": json.loads(p["raw"])} for p in plans], f,
                  ensure_ascii=False, indent=1)
    print(f"\nzaloha: {ZAL}")
    for p in plans:
        if not p["bad"]:
            continue
        cur.execute("SELECT data FROM custom_shapes WHERE id=%s", (p["id"],))
        if cur.fetchone()["data"] != p["raw"]:
            conn.rollback()
            raise SystemExit(f"CHYBA: tvar #{p['id']} se mezitim zmenil - ROLLBACK, nic nezapsano")
        expr, params = build_expr(p["ops"])
        cur.execute(f"UPDATE custom_shapes SET data = {expr} WHERE id=%s", params + [p["id"]])
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: UPDATE #{p['id']} rowcount={cur.rowcount} - ROLLBACK")
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                    (None, "update", "custom_shape_lic_peers", p["id"],
                     f"bot8: odebrano {len(p['bad'])} paru lic_peers nesplnujicich definici spoje (nahrazuje dotyk hranou)"))
    conn.commit()
    c2 = get_conn().cursor()
    for p in plans:
        c2.execute("SELECT data FROM custom_shapes WHERE id=%s", (p["id"],))
        parts2 = json.loads(c2.fetchone()["data"])["parts"]
        pairs2, bad2 = qa_checks.lic_peers_bad_pairs(parts2, profil_glb, cache)
        if bad2 or len(pairs2) != len(p["pairs"]) - len(p["bad"]):
            raise SystemExit(f"CHYBA: tvar #{p['id']} po zapisu: {len(pairs2)} paru, nevyhovujicich {len(bad2)}")
    print("zapsano a overeno z noveho spojeni:", ", ".join(f"#{p['id']}" for p in plans))


if __name__ == "__main__":
    main()
