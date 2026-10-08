#!/opt/konfigurator/api/venv/bin/python
"""Import katalogu a textu mini-shopu (JSON) jako DRAFT (bot5, 2026-10-02, fáze 1b; logika je v api/miniweb_admin.py::import_catalog).

  scripts/miniweb_import.py SOUBOR.json                       NAHLED: zvaliduje a ukaze, co by se stalo, nic nezapise (vychozi)
  scripts/miniweb_import.py SOUBOR.json --apply               zapise jako DRAFT (nikdy approved), pred zapisem zazalohuje stavajici radky do backups/
  --revise-approved   schvaleny text, ktery se lisi od souboru, se prepise a VRATI do draftu (verejne zmizi do dalsiho schvaleni Robertem), jinak se schvaleny text nikdy neprepise
  --update-catalog    zmeni i katalogova data uz existujici polozky (rodic, poradi, kod, kategorie, konfigurator), jinak se rozdil jen ohlasi
  --backup-dir DIR    kam zalohovat (vychozi backups/ v repu)

Pri JEDINE chybe v souboru se nezapise nic. Schvaluje Robert v adminu (stranka miniweb-schvaleni.html), tenhle skript nic neschvaluje. Format souboru a pravidla: hlavicka api/miniweb_admin.py.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/miniweb_import.py SOUBOR.json
Navratovy kod: 0 v poradku, 2 chyba v souboru nebo v argumentech (nic se nezapsalo).
"""
import argparse
import datetime
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TABULKY = ("miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts")


def _vypis(report):
    for e in report["errors"]:
        print("CHYBA    " + e)
    for w in report["warnings"]:
        print("VAROVÁNÍ " + w)
    c, p, t = report["categories"], report["products"], report["texts"]
    print(f"kategorie: nové {c['created']}, beze změny {c['unchanged']}, změněné {c['updated']}, rozdíl nepřepsán {c['differs']}")
    print(f"produkty:  nové {p['created']}, beze změny {p['unchanged']}, změněné {p['updated']}, rozdíl nepřepsán {p['differs']}")
    print(f"texty:     nové {t['created']}, upravené návrhy {t['updated']}, beze změny {t['unchanged']}, schválené NEPŘEPSANÉ {t['skipped_approved']}, schválené vrácené do návrhu {t['revised']}")
    d = report.get("documents")
    if d and any(d.values()):
        print(f"dokumenty: nové {d['created']}, upravené návrhy {d['updated']}, beze změny {d['unchanged']}, schválené NEPŘEPSANÉ {d['skipped_approved']}, schválené vrácené do návrhu {d['revised']}")


def _zaloha(cur, adresar):
    """Zaloha stavajicich radku mini-shopu do JSON, jen kdyz v nich neco je. -> cesta nebo None."""
    data, pocet = {}, 0
    for t in TABULKY:
        cur.execute(f"SELECT * FROM `{t}` ORDER BY 1, 2")
        data[t] = cur.fetchall()
        pocet += len(data[t])
    if not pocet:
        return None
    os.makedirs(adresar, exist_ok=True)
    cesta = os.path.join(adresar, f"{datetime.date.today().isoformat()}_miniweb_pred_importem_{datetime.datetime.now().strftime('%H%M%S')}.json")
    with open(cesta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=str)
    return cesta


def main(argv=None, conn=None):
    ap = argparse.ArgumentParser(description="Import katalogu a textu mini-shopu jako DRAFT")
    ap.add_argument("soubor")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--revise-approved", action="store_true")
    ap.add_argument("--update-catalog", action="store_true")
    ap.add_argument("--backup-dir", default=os.path.join(REPO, "backups"))
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        with open(args.soubor, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"CHYBA    soubor {args.soubor} nejde načíst jako JSON: {e}")
        return 2
    if conn is None:
        sys.path.insert(0, os.path.join(REPO, "api"))
        import app  # noqa: E402
        conn = app.get_conn()
    try:
        import miniweb_admin
    except ImportError:
        print("CHYBA    modul api/miniweb_admin.py není nasazený (import a schvalování se nasazuje skriptem nasazeni/deploy_miniweb.sh)")
        return 2
    kw = {"revise_approved": args.revise_approved, "update_catalog": args.update_catalog}
    with conn.cursor() as cur:
        report = miniweb_admin.import_catalog(cur, data, apply=False, **kw)
    conn.rollback()
    if report["errors"] or not args.apply:
        print("== NÁHLED (nic se nezapsalo)" if not report["errors"] else "== SOUBOR MÁ CHYBY (nic se nezapsalo)")
        _vypis(report)
        return 2 if report["errors"] else 0
    with conn.cursor() as cur:
        zaloha = _zaloha(cur, args.backup_dir)
        report = miniweb_admin.import_catalog(cur, data, apply=True, **kw)
    if report["errors"]:
        conn.rollback()
        print("== CHYBA PŘI ZÁPISU (nic se nezapsalo)")
        _vypis(report)
        return 2
    conn.commit()
    print("== ZAPSÁNO jako DRAFT" + (f", záloha stávajících řádků: {zaloha}" if zaloha else ""))
    _vypis(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
