#!/usr/bin/env python3
"""Smaze 24 ODSOUHLASENYCH koliznich uhelniku ve 12 sestavach.

=== POZOR: PRAVIDLO SE MEZITIM ZMENILO (v2 -> v3) ===
Tenhle skript vznikl podle pravidla v2 ("kolizni uhelniky DOLE V NOHACH
smazat"), kde bylo misto na sestave soucasti podminky. Robert 2026-09-11
misto jako podminku ZRUSIL: "Je jasne ze ruzne auta maji ruzne tvary takze
pokud se vyskytne kolizni uhelnik tak nemusi mit stejnou pozici jako v
doublu." Platne je ted pravidlo v3 (PRISLUSENSTVI_PRIPOJENI.md +
shape_geometry_methods.id=7 verze 3): kriterium je ciste prunik hmoty.

CO TO ZNAMENA PRO TENHLE SKRIPT: jeho ROZSAH zustava presne stejny a je dal
platny - techhle 24 kusu koliduje i podle v3 a Robert je odsouhlasil.
Skript ale UZ NENI uplna implementace pravidla: podle v3 je koliznich
uhelniku v katalogu 60, ne 24. Zbylych 36 se sem NEPRIDAVA, protoze Robert
k nim rekl "Napred mi je ukazat" - vypis k posouzeni dela
scripts/2026-09-11_report_kolizni_uhelniky.cjs. Nerozsiruj SEZNAM nize bez
jeho rozhodnuti.

Rozsah odsouhlasil bot8 2026-09-11 na zaklade dry-runu.

CO SE MAZE: vyhradne uhelniky vyjmenovane nize v SEZNAM - ten NENI
dopocitavany za behu, ale zapsany natvrdo z odsouhlaseneho dry-runu
(`scripts/2026-09-11_sweep_kolizni_uhelniky.cjs`, commit ec348066).
Duvod: mezi odsouhlasenim a spustenim muze nekdo se sestavami hnout a
tise jiny rozsah, nez co bot8 videl, je presne to, cemu se chceme vyhnout.
Skript proto kazdy kus pred smazanim OVERI (pozice i role musi sedet) a
kdyz nesedi, NEMAZE NIC a skonci chybou.

JAK VZNIKLA DEFINICE (podrobne v hlavicce sweep skriptu a v AGENTS_LOG.md
2026-09-11): vyska jako kriterium NEFUNGUJE - ve vzoru Dobla C byly
ponechane uhelniky NIZ (Y=31.5) nez smazane (Y=53.5) a jeden ponechany byl
dokonce ve STEJNE vysce. Rozhoduje skutecny PRUNIK realne GLB geometrie:
smazane pronikaly do `spojnice-dolni` o 7.00mm, vsechny ostatni mely 0.00mm
(flush dosed = jejich ucel).

NEMAZE se zbylych 36 koliznich uhelniku. NE proto, ze by na ne pravidlo
neplatilo (od v3 plati vsude), ale proto, ze je Robert jeste nevidel.
Z nich 24 kusu (sestavy 182, 189, 219, 289) koliduje vyhradne s dily
starych hornich bloku a po jejich uklidu zaniknou samy.

POJISTKY:
  --dry-run              nahled bez zapisu
  zaloha do backups/     jako DOKONCENY krok pred mazanim (fsync + velikost)
  overeni kazdeho kusu   pozice + role musi sedet, jinak se nemaze NIC
  kontrola po zapisu     cerstvym spojenim
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402

os.environ.update(_env.load_env())

import app  # noqa: E402,F401 - drive nez product_assemblies (kruhovy import)
import product_assemblies  # noqa: E402

ZALOHA = "/opt/konfigurator/backups/2026-09-11_kolizni_uhelniky_pred_smazanim.json"

# Odsouhlaseny rozsah (bot8, 2026-09-11). Klic = id sestavy, hodnota = seznam
# (role, X, Y, Z) kusu ke smazani. Pozice zaokrouhlene na 0.1mm, stejne jako
# je vypisuje sweep.
SEZNAM = {
    79: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    83: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    134: [("uhelnik-noha2", -402.5, 53.5, -48.5), ("uhelnik-noha2", -557.5, 53.5, -48.5)],
    135: [("uhelnik-noha2", -402.5, 55.5, -49.5), ("uhelnik-noha2", -557.5, 55.5, -49.5)],
    151: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    152: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    173: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    209: [("uhelnik-noha2", -402.5, 53.5, -48.5), ("uhelnik-noha2", -557.5, 53.5, -48.5)],
    210: [("uhelnik-noha2", -402.5, 55.5, -49.5), ("uhelnik-noha2", -557.5, 55.5, -49.5)],
    224: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
    280: [("uhelnik-noha2", -402.5, 55.5, -49.5), ("uhelnik-noha2", -557.5, 55.5, -49.5)],
    294: [("uhelnik-noha1", -483.5, 42, -1150), ("uhelnik-noha1", -598.5, 42, -1150)],
}
TOLERANCE_MM = 0.2


def _conn():
    return app.get_conn()


def sedi(part, ocekavano):
    role, x, y, z = ocekavano
    if (part.get("role") or "") != role:
        return False
    p = part.get("position") or []
    if len(p) != 3:
        return False
    return all(abs(p[i] - v) <= TOLERANCE_MM for i, v in enumerate((x, y, z)))


def main():
    dry = "--dry-run" in sys.argv
    ted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ids = sorted(SEZNAM)

    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, name, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            radky = cur.fetchall()
    finally:
        conn.close()

    if len(radky) != len(ids):
        print(f"CHYBA: ocekaval jsem {len(ids)} sestav, nasel {len(radky)} - NEMAZU NIC.",
              file=sys.stderr)
        return 1

    print(f"[{ted}] {'DRY-RUN' if dry else 'ZAPIS'} - kolizni uhelniky dole v nohach\n")
    plan, problemy = [], []
    for r in radky:
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        parts = d.get("parts", [])
        ocekavane = SEZNAM[r["id"]]
        indexy = []
        for oc in ocekavane:
            nalez = [i for i, p in enumerate(parts) if sedi(p, oc)]
            if len(nalez) != 1:
                problemy.append(f"#{r['id']}: {oc} -> nalezeno {len(nalez)}x (ocekavano prave 1)")
            else:
                indexy.append(nalez[0])
        if len(indexy) == len(ocekavane):
            print(f"#{r['id']} {r['name'][:52]}")
            for i in indexy:
                p = parts[i]
                print(f"   smazat {p['role']:14} poz={[round(v,1) for v in p['position']]} {p['part_id']}")
            plan.append((r, d, set(indexy)))

    if problemy:
        print("\nCHYBA: odsouhlaseny rozsah uz neodpovida datum - NEMAZU NIC:", file=sys.stderr)
        for x in problemy:
            print("   " + x, file=sys.stderr)
        print("\nSestavy se od dry-runu zmenily. Pust znovu sweep "
              "(scripts/2026-09-11_sweep_kolizni_uhelniky.cjs) a nech rozsah znovu odsouhlasit.",
              file=sys.stderr)
        return 1

    celkem = sum(len(i) for _r, _d, i in plan)
    print(f"\nCELKEM ke smazani: {celkem} uhelniku z {len(plan)} sestav")
    if celkem != 24:
        print(f"POZOR: ocekavano 24 kusu, vyslo {celkem} - zkontroluj, nez pustis naostro.",
              file=sys.stderr)

    if dry:
        print("\n--dry-run: nic se nezapisuje.")
        return 0

    # --- ZALOHA PRED MAZANIM, jako dokonceny krok ---
    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    zaloha = {
        "vytvoreno": datetime.now().isoformat(),
        "duvod": "smazani koliznich uhelniku dole v nohach (Robert 2026-09-11, rozsah odsouhlasil bot8)",
        "definice": "prunik hmoty overeny na skutecne GLB siti (pravidlo v3); tyto kusy "
                    "odsouhlasil bot8 jeste podle v2 jako skupinu dole v nohach",
        "sestavy": [{"id": r["id"], "name": r["name"], "data": d} for r, d, _i in plan],
    }
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump(zaloha, f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    velikost = os.path.getsize(ZALOHA)
    if velikost < 1000:
        print(f"CHYBA: zaloha {ZALOHA} je podezrele mala ({velikost} B) - NEMAZU NIC.",
              file=sys.stderr)
        return 1
    print(f"\nZaloha PRED mazanim: {ZALOHA} ({velikost} B, {len(plan)} sestav)")

    # --- ZAPIS ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            mapy = product_assemblies.nacti_mapy_znacek(cur)
            for r, d, indexy in plan:
                d["parts"] = [p for i, p in enumerate(d["parts"]) if i not in indexy]
                # bom/price_summary jsou snimky ze sceny - po odebrani dilu uz
                # nesedi. Uhelnik je polozka kusovniku, takze se to tyka i jich.
                if d.get("bom"):
                    d["bom"] = []
                if d.get("price_summary"):
                    d["price_summary"] = None
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                            (json.dumps(d, ensure_ascii=False), r["id"]))
                file_id = product_assemblies.zrcadli_sestavu_na_disk(
                    cur, r["id"], r["name"], d, None, mapy=mapy)
                print(f"   #{r['id']}: -{len(indexy)} uhelniku, zrcadlo file_id={file_id}")
        conn.commit()
    finally:
        conn.close()

    # --- KONTROLA CERSTVYM SPOJENIM ---
    conn = _conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT id, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            print("\nKontrola cerstvym spojenim:")
            zbylo_celkem = 0
            for r in cur.fetchall():
                d = json.loads(r["data"])
                zbylo = [p for p in d["parts"]
                         if any(sedi(p, oc) for oc in SEZNAM[r["id"]])]
                zbylo_celkem += len(zbylo)
                print(f"  #{r['id']}: dilu {len(d['parts'])}, zbytky ke smazani "
                      f"{len(zbylo) or 'zadne OK'}")
    finally:
        conn.close()
    return 0 if zbylo_celkem == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
