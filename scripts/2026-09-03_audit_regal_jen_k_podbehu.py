#!/opt/konfigurator/api/venv/bin/python
"""Kontrola "regal jen k podbehu" nad vsemi verejnymi product_assemblies (bot16, 2026-09-03).

Robert 2026-09-03: "porad je spousta regalu jen k podbehu, udelej kontrolni skript,
ktery ti to odhali". Skript READ-ONLY vydumpuje is_public=1 sestavy + car_bodies do
docasneho adresare a pusti nad nimi geometrickou analyzu
scripts/2026-09-03_audit_regal_jen_k_podbehu.js (realne GLB karoserie, stejny
collidesWithWalls jako stavebni pipeline). Vypise tabulku problemovych sestav.

    scripts/2026-09-03_audit_regal_jen_k_podbehu.py              # jen problemove radky
    scripts/2026-09-03_audit_regal_jen_k_podbehu.py --all        # vsechny radky
    scripts/2026-09-03_audit_regal_jen_k_podbehu.py --ids 103,104 --json /tmp/x.json

Verdikty: JEN_K_PODBEHU (regal konci pred podbehem a za nim je >= 460mm),
NEDOTAZENO (uz nad podbehem, ale za nim porad >= 460mm), VOLNO_ZA_PREKAZKOU,
PRESAH_ZA_KONEC (regal konci za modelovanou karoserii), OK. Detaily v hlavicce .js.
Nic v DB nemeni.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, "api")
JS = os.path.join(ROOT, "scripts", "2026-09-03_audit_regal_jen_k_podbehu.js")


def load_env():
    with open(os.path.join(API, ".env")) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def dump(dirpath, ids):
    load_env()
    sys.path.insert(0, API)
    cwd = os.getcwd(); os.chdir(API)
    import app as A  # noqa: E402
    conn = A.get_conn()
    try:
        cur = conn.cursor()
        os.makedirs(os.path.join(dirpath, "rows"))
        q = "SELECT id, name, category_id, car_model_id, shop_product_id, data FROM product_assemblies WHERE is_public=1"
        args = ()
        if ids:
            q += " AND id IN (%s)" % ",".join(["%s"] * len(ids)); args = tuple(ids)
        cur.execute(q + " ORDER BY id", args)
        n = 0
        with open(os.path.join(dirpath, "all_public_rows.tsv"), "w") as f:
            for row in cur.fetchall():
                rid, name, cat, model, shop, data = row[:6] if not isinstance(row, dict) else (row["id"], row["name"], row["category_id"], row["car_model_id"], row["shop_product_id"], row["data"])
                f.write("%s\t%s\t%s\t%s\t%s\n" % (rid, cat, model, shop, (name or "").replace("\t", " ").replace("\n", " ")))
                d = json.loads(data) if isinstance(data, (str, bytes)) else (data or {})
                with open(os.path.join(dirpath, "rows", "%s.json" % rid), "w") as g:
                    json.dump(d, g)
                n += 1
        cur.execute("SELECT cb.id, cb.name, cb.glb_file, cb.model_id, m.name AS model_name FROM car_bodies cb LEFT JOIN car_models m ON m.id = cb.model_id ORDER BY cb.id")
        with open(os.path.join(dirpath, "car_bodies.tsv"), "w") as f:
            for row in cur.fetchall():
                vals = row[:5] if not isinstance(row, dict) else (row["id"], row["name"], row["glb_file"], row["model_id"], row["model_name"])
                f.write("\t".join("" if v is None else str(v).replace("\t", " ") for v in vals) + "\n")
        # oficialni rozmery ložné plochy (Robert 2026-09-03: u "nekonecneho" podbehu se ridit ložnou délkou)
        cur.execute("SELECT legacy_vendor_code, cargo_length_mm, cargo_width_mm, cargo_height_mm, real_name FROM karoserie_model_reference")
        with open(os.path.join(dirpath, "karoserie_model_reference.tsv"), "w") as f:
            for row in cur.fetchall():
                vals = row[:5] if not isinstance(row, dict) else (row["legacy_vendor_code"], row["cargo_length_mm"], row["cargo_width_mm"], row["cargo_height_mm"], row["real_name"])
                f.write("\t".join("" if v is None else str(v).replace("\t", " ") for v in vals) + "\n")
        return n
    finally:
        conn.close(); os.chdir(cwd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", help="jen tyto id (carkou)")
    ap.add_argument("--all", action="store_true", help="vypsat i OK radky")
    ap.add_argument("--json", help="ulozit plny JSON report (vc. profilu za regalem)")
    ap.add_argument("--keep", action="store_true", help="nemazat docasny dump")
    a = ap.parse_args()
    ids = [int(x) for x in a.ids.split(",")] if a.ids else None
    tmp = tempfile.mkdtemp(prefix="podbeh_audit_")
    try:
        n = dump(tmp, ids)
        print("dump: %d verejnych sestav -> %s" % (n, tmp), file=sys.stderr)
        env = dict(os.environ, NODE_PATH=os.path.join(ROOT, "node_modules"))
        p = subprocess.run(["node", JS, tmp] + ([a.ids] if a.ids else []), env=env, capture_output=True, text=True)
        if p.returncode != 0:
            sys.stderr.write(p.stderr); sys.exit(p.returncode)
        report = json.loads(p.stdout)
    finally:
        if a.keep:
            print("dump ponechan v", tmp, file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    order = {"JEN_K_PODBEHU": 0, "NEDOTAZENO": 1, "VOLNO_ZA_PREKAZKOU": 2, "PRESAH_ZA_KONEC": 3, "PRESAH_ZA_GLB": 4, "OK": 9}
    rows = [r for r in report if r.get("error") or a.all or r.get("verdict") != "OK"]
    rows.sort(key=lambda r: (order.get(r.get("verdict"), 5), r["id"]))
    hdr = "%-4s %-16s %7s %7s %7s %7s %6s %6s %5s %6s %5s  %s" % ("id", "verdikt", "regalZ", "podbehZ", "konecGLB", "konecOf", "lozna", "GLB-of", "pod∞", "volno", "zdvih", "nazev")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        if r.get("error"):
            print("%-4s %-16s %s  %s" % (r["id"], "CHYBA", r["error"], r.get("name", ""))); continue
        arch = r.get("arch") or {}
        b = r["behind"]
        o = r.get("official") or {}
        fmt = lambda v: "-" if v is None else "%.0f" % v
        print("%-4s %-16s %7.0f %7s %7.0f %7s %6s %6s %5s %6.0f %5.0f  %s" % (
            r["id"], r["verdict"], r["rack"]["rearZ"],
            fmt(arch.get("startZ")) if arch else "-", r["body"]["endZ"], fmt(o.get("endZ")),
            fmt(o.get("cargoLength")) if o.get("cargoLength") else "?", fmt(o.get("glbMinusOfficial")),
            "ANO" if arch.get("infinite") else "", b["usableLen"] if b["usableLen"] else b["bestRun"], b["maxFloorRise"], r["name"]))
    counts = {}
    for r in report:
        counts[r.get("verdict") or "CHYBA"] = counts.get(r.get("verdict") or "CHYBA", 0) + 1
    print("\ncelkem %d sestav: %s" % (len(report), ", ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    print("sloupce: regalZ=zadni konec regalu, podbehZ=zacatek podbehu u steny, konecGLB=konec modelovane karoserie, konecOf=predni hrana L steny+oficialni ložná délka, lozna=oficialni ložná délka (? = chybi v karoserie_model_reference), GLB-of=o kolik je GLB delsi(+)/kratsi(-) nez oficialni, pod∞=podbeh nekonecny (za nim uz zadna rovna podlaha az k zadni hranici), volno=vyuzitelna delka za regalem po blizsi z hranic [mm] (u VOLNO_ZA_PREKAZKOU nejdelsi usek), zdvih=max. vrsek podbehu v tom useku")


if __name__ == "__main__":
    main()
