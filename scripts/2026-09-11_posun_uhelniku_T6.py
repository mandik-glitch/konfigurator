#!/usr/bin/env python3
"""Posune 6 koliznich uhelniku u T6 o -29 mm po ose Z. VYCHOZI STAV: NEDELA NIC.

    api/venv/bin/python3 scripts/2026-09-11_posun_uhelniku_T6.py            # nahled
    api/venv/bin/python3 scripts/2026-09-11_posun_uhelniku_T6.py --provest  # zapise

=== ⚠️ CO TO VE SKUTECNOSTI DELA (precti, nez to pustis) ===
NENI to srovnani rozhozeneho dilu o par milimetru. Zmereno na skutecne
siti: uhelnik po posunu DOSEDA NA JINE DILY nez ted.

    ted:      sloupek-pred-podbehem + pricka-uzavreni-vyrezu   (a KOLIDUJE)
    po posunu: spojnice-dolni + spojnice-sloupec1-patro0       (a nekoliduje)

Uhelnik tedy PRESEDNE NA JINY SPOJ. Je to platna poloha - cilove misto je
volne (nejblizsi jiny uhelnik je az ten kolizni sam), dosedy jsou dva a
rade a kolize zmizi uplne. Ale je to ROZHODNUTI, ktery spoj ma byt
vyztuzeny, ne mechanicka oprava. Druha moznost je uhelnik proste smazat,
jako u zbylych 30 koliznich kusu.

Proto se tenhle skript bez `--provest` jen diva a proto to musi odsouhlasit
clovek.

=== PROC SKRIPTEM A NE RUCNE ===
Robert 2026-09-11: "nerazitkujeme botem rucne" - plati obecne, ne jen na
razitka. Rucni zasah do geometrie neni dohledatelny, nejde zopakovat a
nejde zkontrolovat. Skript ano.

=== CO SE NEMENI ===
`bom` ani `price_summary` se NEVYPRAZDNUJI - na rozdil od mazani dilu se
tady pocet ani druh dilu nemeni, jen poloha. Kusovnik i cena zustavaji
platne.
"""
import argparse
import json
import os
import sys
from datetime import datetime

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402

os.environ.update(_env.load_env())
import app  # noqa: E402,F401 - driv nez product_assemblies (kruhovy import)
import product_assemblies  # noqa: E402
import kolize_priznak  # noqa: E402

ZALOHA = os.path.join(REPO, "backups", "2026-09-11_posun_uhelniku_T6_pred_zmenou.json")
POSUN = (0.0, 0.0, -29.0)
TOLERANCE_MM = 0.6

# Odsouhlaseny rozsah. Zapsany natvrdo z mereni, ne dopocitavany za behu -
# mezi nahledem a spustenim muze nekdo se sestavami hnout a tise jiny
# rozsah je presne to, cemu se chceme vyhnout. Kazdy kus se pred zapisem
# OVERI (role i poloha musi sedet), jinak se nemeni NIC.
SEZNAM = {
    116: [("uhelnik-noha2", -617.0, 329.2, -693.8)],
    250: [("uhelnik-noha2", -617.0, 329.2, -693.8)],
    320: [("uhelnik-noha2", -617.0, 329.2, -693.8)],
    117: [("uhelnik-noha2", -617.0, 316.7, -733.5)],
    251: [("uhelnik-noha2", -617.0, 316.7, -733.5)],
    321: [("uhelnik-noha2", -617.0, 316.7, -733.5)],
}


def sedi(part, ocekavano):
    role, x, y, z = ocekavano
    if (part.get("role") or "") != role:
        return False
    p = part.get("position") or []
    return len(p) == 3 and all(abs(p[i] - v) <= TOLERANCE_MM for i, v in enumerate((x, y, z)))


def main():
    ap = argparse.ArgumentParser(description="Posun koliznich uhelniku u T6 o -29 mm po Z")
    ap.add_argument("--provest", action="store_true", help="ZAPSAT zmenu (bez toho jen nahled)")
    a = ap.parse_args()
    ids = sorted(SEZNAM)

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, name, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            radky = cur.fetchall()
    finally:
        conn.close()
    if len(radky) != len(ids):
        print(f"CHYBA: ocekaval jsem {len(ids)} sestav, nasel {len(radky)} - NEMENIM NIC.", file=sys.stderr)
        return 1

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {'ZAPIS' if a.provest else 'NAHLED'} - "
          f"posun o {POSUN[2]} mm po ose Z\n")
    plan, problemy = [], []
    for r in radky:
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        parts = d.get("parts", [])
        indexy = []
        for oc in SEZNAM[r["id"]]:
            nalez = [i for i, p in enumerate(parts) if sedi(p, oc)]
            if len(nalez) != 1:
                problemy.append(f"#{r['id']}: {oc} -> nalezeno {len(nalez)}x (ocekavano prave 1)")
            else:
                indexy.append(nalez[0])
        if len(indexy) == len(SEZNAM[r["id"]]):
            print(f"#{r['id']} {r['name'][:52]}")
            for i in indexy:
                p = parts[i]
                nova = [p["position"][k] + POSUN[k] for k in range(3)]
                print(f"   {p['role']:14} [{', '.join(f'{v:.1f}' for v in p['position'])}]"
                      f"  ->  [{', '.join(f'{v:.1f}' for v in nova)}]")
            plan.append((r, d, indexy))

    if problemy:
        print("\nCHYBA: rozsah uz neodpovida datum - NEMENIM NIC:", file=sys.stderr)
        for x in problemy:
            print("   " + x, file=sys.stderr)
        return 1

    celkem = sum(len(i) for _r, _d, i in plan)
    print(f"\nCELKEM k posunu: {celkem} uhelniku v {len(plan)} sestavach")
    if celkem != 6:
        print(f"POZOR: ocekavano 6 kusu, vyslo {celkem}.", file=sys.stderr)
        return 1
    if not a.provest:
        print("\nNAHLED - nic se nezapisuje. Zmenu provedes pridanim --provest.")
        return 0

    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump({"vytvoreno": datetime.now().isoformat(),
                   "duvod": "posun koliznich uhelniku u T6 o -29 mm po Z",
                   "pozor": "uhelnik timto DOSEDA NA JINE DILY nez pred posunem - viz hlavicka skriptu",
                   "posun": POSUN,
                   "sestavy": [{"id": r["id"], "name": r["name"], "data": d} for r, d, _i in plan]},
                  f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    vel = os.path.getsize(ZALOHA)
    if vel < 1000:
        print(f"CHYBA: zaloha {ZALOHA} je podezrele mala ({vel} B) - NEMENIM NIC.", file=sys.stderr)
        return 1
    print(f"\nZaloha pred zmenou: {ZALOHA} ({vel} B)")

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            mapy = product_assemblies.nacti_mapy_znacek(cur)
            for r, d, indexy in plan:
                for i in indexy:
                    p = d["parts"][i]
                    p["position"] = [p["position"][k] + POSUN[k] for k in range(3)]
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                            (json.dumps(d, ensure_ascii=False), r["id"]))
                fid = product_assemblies.zrcadli_sestavu_na_disk(cur, r["id"], r["name"], d, None, mapy=mapy)
                print(f"   #{r['id']}: posunuto {len(indexy)}, zrcadlo file_id={fid}")
            # Priznak kolizi po zmene geometrie - at cerveny nazev ve scene
            # nelze dal, nez casovac dobehne.
            v = kolize_priznak.prepocti(cur, ids)
            print(f"   priznak kolizi prepocten: {v}")
        conn.commit()
    finally:
        conn.close()

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, kolize_pocet FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            print("\nKontrola cerstvym spojenim (kolize po zmene):")
            zbylo = 0
            for r in cur.fetchall():
                zbylo += r["kolize_pocet"] or 0
                print(f"  #{r['id']}: koliznich uhelniku {r['kolize_pocet']}")
    finally:
        conn.close()
    print(f"\nkoliznich uhelniku v techhle sestavach celkem: {zbylo} (ocekavano 6 -> ty 'bez ustupu')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
