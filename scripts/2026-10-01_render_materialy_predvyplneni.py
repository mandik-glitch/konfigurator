#!/opt/konfigurator/api/venv/bin/python
"""Predvyplneni ucinne prirazovaci tabulky renderovacich materialu (bot10, 2026-10-01).

Cte navrh z analyzy (2026-10-01_render_materialy_predvyplneni_data/navrh.csv + souhrn.md) a podle nej:
  * zapise `render_material_key` JEN u radku se stavem OK (115 ks, jen kdyz je sloupec dosud NULL),
  * radky ROZHODNE ROBERT (sporne) a VYNECHANO NECHA NULL,
  * ulozi cely navrh (181 radku vc. stavu a navrhu po castech pro vicetelesove dily) do render_material_navrh,
    aby admin umel ukazat "sporne cerveně" a "pouzit navrh" (render to NEOVLIVNUJE).
Nic jineho nemeni (zadne app_settings, zadne karty mimo sloupec render_material_key, zadny render).

VYCHOZI = DRY-RUN (jen SELECT, nic se nezapise). Zapis jen s --apply, a jen kdyz uz existuje DDL
sql/2026-10-01_render_materialy.sql (tabulky + sloupce). Pred zapisem se do backups/ ulozi puvodni hodnoty
(JSON); po zapisu se kontroluje rowcount KAZDEHO UPDATE a pak CERSTVY SELECT, ktery musi souhlasit.
Nikdy neprepise hodnotu, kterou uz nekdo nastavil jinak (vypise ji jako konflikt).

Spusteni (server; db pristupy z api/.env, heslo se nevypisuje):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator api/venv/bin/python3 -u scripts/2026-10-01_render_materialy_predvyplneni.py            # dry-run
  ... scripts/2026-10-01_render_materialy_predvyplneni.py --apply                                                                # zapis
Navratovy kod: 0 = v poradku, 2 = chybi DDL (tabulky/sloupce), 3 = konflikty/neshoda po zapisu, 1 = jina chyba.
"""
import argparse
import csv
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(os.path.dirname(HERE), "scripts"))   # kandidat mimo repo: _env.py z ostreho repa
sys.path.append("/opt/konfigurator/scripts")
import _env  # noqa: E402

DATA_DIR = os.path.join(HERE, "2026-10-01_render_materialy_predvyplneni_data")
REPO = os.path.dirname(HERE)
STAV_MAP = {"OK": "OK", "ROZHODNE ROBERT": "SPORNE", "VYNECHANO": "VYNECHANO"}
TABULKY = ("render_materialy", "render_material_casti", "render_material_navrh")
SLOUPCE = (("shop_products", "render_material_key"), ("cfg_dily", "render_material_key"),
           ("content_categories", "render_material_key"))


def nacti_csv(cesta):
    with open(cesta, encoding="utf-8", newline="") as f:
        radky = list(csv.DictReader(f))
    povinne = {"zdroj", "id", "navrzeny_klic", "pravidlo", "stav"}
    if not radky or not povinne <= set(radky[0]):
        raise SystemExit("CSV %s nema ocekavane sloupce %s" % (cesta, sorted(povinne)))
    videno = set()
    for r in radky:
        if r["zdroj"] not in ("product", "cfg"):
            raise SystemExit("CSV: neznamy zdroj %r" % r["zdroj"])
        if r["stav"] not in STAV_MAP:
            raise SystemExit("CSV: neznamy stav %r (%s %s)" % (r["stav"], r["zdroj"], r["id"]))
        k = (r["zdroj"], r["id"])
        if k in videno:
            raise SystemExit("CSV: duplicitni radek %s" % (k,))
        videno.add(k)
        r["navrzeny_klic"] = (r["navrzeny_klic"] or "").strip() or None
        if r["stav"] == "OK" and not r["navrzeny_klic"]:
            raise SystemExit("CSV: radek OK bez klice (%s %s)" % k)
    return radky


def nacti_casti_ze_souhrnu(cesta):
    """souhrn.md -> {product_id(str): {mesh_klic: {klic, proc, rozmer_mm}}}. Sekce '### 3381 Nazev - ...' s tabulkou
    '| Solid_0 | 92.2 x 152.3 x 45.0 | grey | hlavni/ostatni |'."""
    vysl, aktualni = {}, None
    with open(cesta, encoding="utf-8") as f:
        for radek in f:
            m = re.match(r"^### (\d+) ", radek)
            if m:
                aktualni = m.group(1)
                vysl[aktualni] = {}
                continue
            if radek.startswith("## "):
                aktualni = None
            if aktualni:
                t = re.match(r"^\|\s*(Solid_\d+)\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|\s*([^|]*?)\s*\|\s*$", radek)
                if t:
                    vysl[aktualni][t.group(1)] = {"klic": t.group(3), "proc": t.group(4), "rozmer_mm": t.group(2)}
    return {k: v for k, v in vysl.items() if v}


def over_ddl(cur):
    chybi = []
    for t in TABULKY:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (t,))
        if not cur.fetchone()["n"]:
            chybi.append("tabulka " + t)
    for t, c in SLOUPCE:
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
                    "AND TABLE_NAME=%s AND COLUMN_NAME=%s", (t, c))
        if not cur.fetchone()["n"]:
            chybi.append("sloupec %s.%s" % (t, c))
    return chybi


def stav_db(cur, radky):
    """{(zdroj,id): {existuje, klic}} + mnozina platnych (aktivnich) klicu materialu."""
    cur.execute("SELECT klic FROM render_materialy WHERE aktivni=1")
    platne = {r["klic"].lower() for r in cur.fetchall()}
    vysl = {}
    for r in radky:
        if r["zdroj"] == "product":
            cur.execute("SELECT render_material_key AS k FROM shop_products WHERE id=%s", (r["id"],))
        else:
            cur.execute("SELECT render_material_key AS k FROM cfg_dily WHERE id=%s", (r["id"],))
        row = cur.fetchone()
        vysl[(r["zdroj"], r["id"])] = {"existuje": row is not None, "klic": (row or {}).get("k")}
    return vysl, platne


def planuj(radky, stav, platne):
    plan = {"zapsat": [], "uz_nastaveno": [], "konflikt": [], "chybi_dil": [], "neplatny_klic": [],
            "sporne": [], "vynechano": []}
    for r in radky:
        k = (r["zdroj"], r["id"])
        s = stav[k]
        if r["stav"] == "SPORNE" or r["stav"] == "ROZHODNE ROBERT":
            plan["sporne"].append(r)
            continue
        if r["stav"] == "VYNECHANO":
            plan["vynechano"].append(r)
            continue
        if not s["existuje"]:
            plan["chybi_dil"].append(r)
        elif r["navrzeny_klic"].lower() not in platne:
            plan["neplatny_klic"].append(r)
        elif s["klic"] is None:
            plan["zapsat"].append(r)
        elif s["klic"].lower() == r["navrzeny_klic"].lower():
            plan["uz_nastaveno"].append(r)
        else:
            plan["konflikt"].append((r, s["klic"]))
    return plan


def vypis_plan(plan, radky):
    print("Radku v navrhu: %d (cfg %d, product %d)" % (
        len(radky), sum(r["zdroj"] == "cfg" for r in radky), sum(r["zdroj"] == "product" for r in radky)))
    print("  ZAPSAT render_material_key (OK, dosud NULL) : %d" % len(plan["zapsat"]))
    print("  uz nastaveno na navrzenou hodnotu          : %d" % len(plan["uz_nastaveno"]))
    print("  KONFLIKT (v DB je jina hodnota, NEPREPISUJI): %d" % len(plan["konflikt"]))
    print("  chybi dil v DB                              : %d" % len(plan["chybi_dil"]))
    print("  navrzeny klic neni platny material          : %d" % len(plan["neplatny_klic"]))
    print("  SPORNE (nechano NULL, rozhodne Robert)      : %d" % len(plan["sporne"]))
    print("  VYNECHANO (nechano NULL)                    : %d" % len(plan["vynechano"]))
    pocty = {}
    for r in plan["zapsat"]:
        pocty[r["navrzeny_klic"]] = pocty.get(r["navrzeny_klic"], 0) + 1
    print("  zapsat podle klice: " + ", ".join("%s=%d" % kv for kv in sorted(pocty.items())))
    for r, jina in plan["konflikt"]:
        print("    KONFLIKT %s %s: v DB '%s', navrh '%s'" % (r["zdroj"], r["id"], jina, r["navrzeny_klic"]))
    for r in plan["chybi_dil"] + plan["neplatny_klic"]:
        print("    PROBLEM %s %s (%s)" % (r["zdroj"], r["id"], r["navrzeny_klic"]))


def zaloha(cur, radky, plan, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    cur.execute("SELECT zdroj, dil_id, navrzeny_klic, stav, pravidlo, navrh_casti_json FROM render_material_navrh")
    navrh_pred = cur.fetchall()
    obsah = {
        "vytvoreno": datetime.datetime.now().isoformat(timespec="seconds"),
        "popis": "stav PRED zapisem scripts/2026-10-01_render_materialy_predvyplneni.py --apply",
        "render_material_key_pred": [
            {"zdroj": r["zdroj"], "id": r["id"], "klic_pred": None} for r in plan["zapsat"]],
        "render_material_navrh_pred": [
            {k: (v if not isinstance(v, (bytes, datetime.datetime)) else str(v)) for k, v in row.items()}
            for row in navrh_pred],
    }
    # cas v nazvu + "x" (nikdy neprepsat drivejsi zalohu - ta z prvniho behu nese skutecny stav PRED zapisem)
    cesta = os.path.join(backup_dir, "%s_render_materialy_pred_zapisem.json"
                         % datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    with open(cesta, "x", encoding="utf-8") as f:
        json.dump(obsah, f, ensure_ascii=False, indent=1, default=str)
    return cesta


def zapis(conn, cur, radky, plan, casti):
    """Jedna transakce: UPDATE render_material_key (jen kde je NULL) + upsert render_material_navrh. rowcount se kontroluje."""
    nezapsano = []
    for r in plan["zapsat"]:
        tab = "shop_products" if r["zdroj"] == "product" else "cfg_dily"
        n = cur.execute("UPDATE " + tab + " SET render_material_key=%s WHERE id=%s AND render_material_key IS NULL",
                        (r["navrzeny_klic"], r["id"]))
        if n != 1:
            nezapsano.append(r)      # nekdo mezitim nastavil jinak / radek zmizel - jen oznamit, neprepisovat
    for r in radky:
        stav = STAV_MAP[r["stav"]]
        casti_json = None
        if r["zdroj"] == "product" and r["id"] in casti:
            casti_json = json.dumps(casti[r["id"]], ensure_ascii=False)
        cur.execute(
            "INSERT INTO render_material_navrh (zdroj, dil_id, navrzeny_klic, stav, pravidlo, navrh_casti_json) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE navrzeny_klic=VALUES(navrzeny_klic), stav=VALUES(stav), "
            "pravidlo=VALUES(pravidlo), navrh_casti_json=VALUES(navrh_casti_json)",
            (r["zdroj"], r["id"], r["navrzeny_klic"], stav, (r.get("pravidlo") or "")[:600], casti_json))
    conn.commit()
    return nezapsano


def over_po_zapisu(cur, radky, plan, nezapsano):
    """CERSTVY SELECT po commitu: kazdy zapsany radek ma navrzeny klic, sporne/vynechane zustaly NULL, navrh ma vsechny radky."""
    chyby = []
    zapsane = {(r["zdroj"], r["id"]) for r in plan["zapsat"]} - {(r["zdroj"], r["id"]) for r in nezapsano}
    for r in plan["zapsat"]:
        k = (r["zdroj"], r["id"])
        tab = "shop_products" if r["zdroj"] == "product" else "cfg_dily"
        cur.execute("SELECT render_material_key AS k FROM " + tab + " WHERE id=%s", (r["id"],))
        row = cur.fetchone()
        if k in zapsane and (row or {}).get("k") != r["navrzeny_klic"]:
            chyby.append("po zapisu %s %s ma '%s', ocekavano '%s'" % (r["zdroj"], r["id"], (row or {}).get("k"), r["navrzeny_klic"]))
    for r in plan["sporne"] + plan["vynechano"]:
        tab = "shop_products" if r["zdroj"] == "product" else "cfg_dily"
        cur.execute("SELECT render_material_key AS k FROM " + tab + " WHERE id=%s", (r["id"],))
        row = cur.fetchone()
        if row and row["k"] is not None:
            # nastavil to nekdo jiny (Robert v adminu) - neni to chyba skriptu, jen informace
            print("  info: %s %s (%s) ma klic '%s' nastaveny jinak nez skriptem" % (r["zdroj"], r["id"], r["stav"], row["k"]))
    cur.execute("SELECT COUNT(*) AS n FROM render_material_navrh")
    n = cur.fetchone()["n"]
    if n < len(radky):
        chyby.append("render_material_navrh ma %d radku, ocekavano aspon %d" % (n, len(radky)))
    cur.execute("SELECT stav, COUNT(*) AS n FROM render_material_navrh GROUP BY stav")
    print("  render_material_navrh po zapisu: " + ", ".join("%s=%d" % (x["stav"], x["n"]) for x in cur.fetchall()))
    return chyby


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="ZAPSAT (bez toho jen dry-run)")
    ap.add_argument("--navrh", default=os.path.join(DATA_DIR, "navrh.csv"))
    ap.add_argument("--souhrn", default=os.path.join(DATA_DIR, "souhrn.md"))
    ap.add_argument("--backup-dir", default=os.path.join(REPO, "backups"))
    a = ap.parse_args()

    radky = nacti_csv(a.navrh)
    casti = nacti_casti_ze_souhrnu(a.souhrn) if os.path.exists(a.souhrn) else {}
    env = _env.load_env()
    print("CIL: DB %s@%s:%s/%s  (%s)" % (env.get("DB_USER"), env.get("DB_HOST"), env.get("DB_PORT", "3306"), env.get("DB_NAME"),
                                          "ZAPIS (--apply)" if a.apply else "DRY-RUN, nic se nezapise"))
    conn = _env.get_conn(env=env, autocommit=False)
    try:
        with conn.cursor() as cur:
            chybi = over_ddl(cur)
            if chybi:
                print("CHYBI DDL: " + ", ".join(chybi))
                print("Nejdriv spust sql/2026-10-01_render_materialy.sql (Robert pres '!', viz NAVOD.md). Nic nezapsano.")
                return 2
            stav, platne = stav_db(cur, radky)
            plan = planuj(radky, stav, platne)
            print("Navrh po castech (vicetelesove dily ze souhrn.md): %d dilu, %d teles" % (
                len(casti), sum(len(v) for v in casti.values())))
            vypis_plan(plan, radky)
            if not a.apply:
                print("\nDRY-RUN: nic se nezapsalo. Pro zapis pridej --apply.")
                return 3 if (plan["konflikt"] or plan["chybi_dil"] or plan["neplatny_klic"]) else 0
            if plan["chybi_dil"] or plan["neplatny_klic"]:
                print("\nPROBLEM v datech (chybi dil / neplatny klic) - nezapisuji nic, nejdriv opravit.")
                return 3
            cesta = zaloha(cur, radky, plan, a.backup_dir)
            print("\nZaloha pred zapisem: %s" % cesta)
            nezapsano = zapis(conn, cur, radky, plan, casti)
            print("Zapsano UPDATE: %d z %d" % (len(plan["zapsat"]) - len(nezapsano), len(plan["zapsat"])))
            for r in nezapsano:
                print("  NEZAPSANO (rowcount != 1, nekdo mezitim zmenil): %s %s" % (r["zdroj"], r["id"]))
            chyby = over_po_zapisu(cur, radky, plan, nezapsano)
            for c in chyby:
                print("  CHYBA: " + c)
            return 3 if (chyby or nezapsano or plan["konflikt"]) else 0
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print("CHYBA: %s: %s" % (type(e).__name__, e))
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
