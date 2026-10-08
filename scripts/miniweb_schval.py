#!/usr/bin/env python3
"""Schvaleni textu mini-shopu stejnou cestou jako stranka /miniweb-schvaleni.html (miniweb_admin.apply_status_change, otisk obsahu rev, approved_by).
Pouziti: miniweb_schval.py --lang sk --items document:2,product:1 [--user-id 1] [--apply]   (bez --apply jen vypise; --apply POVINNE s --items, schvaluji se jen vyjmenovane polozky)
Pred zapisem zaloha dotcenych radku do backups/. Spoustet jen na PRIMY pokyn Roberta."""
import argparse, json, os, sys, time
sys.path.insert(0, "/opt/konfigurator/api")
import app
import miniweb
import miniweb_admin as ma

miniweb._price_from = lambda p, shop: None      # schvalovani cenu nepotrebuje (admin kontext shopu nema price_mode)

ap = argparse.ArgumentParser()
ap.add_argument("--lang", required=True)
ap.add_argument("--user-id", type=int, default=1)
ap.add_argument("--apply", action="store_true")
ap.add_argument("--items", help="POVINNE pro --apply: jen tyto polozky, ve tvaru kind:id[,kind:id] (napr. document:2,product:1); kind = category|product|document. Schvaluje se JEN to, co Robert videl a potvrdil, nikdy 'vse co je v draftu'.")
a = ap.parse_args()
conn = app.get_conn()
cur = conn.cursor()
data = ma.build_overview(cur, a.lang)
items = [i for i in data["items"] if i["lang"] == a.lang and i["status"] == "draft" and not i["blocking"]]
if a.items:
    want = {tuple(x.split(":", 1)) for x in a.items.split(",") if ":" in x}
    items = [i for i in items if (i["kind"], str(i["id"])) in want]
elif a.apply:
    sys.exit("--apply vyzaduje --items kind:id[,kind:id] (schvalovat jen konkretni polozky, ne vsechny drafty; 2026-10-05 se tak omylem schvalily cizi koncepty)")
for i in data["items"]:
    print(("-> " if i in items else "   ") + f"{i['kind']} #{i['id']} {i['lang']} {i['status']} blocking={bool(i['blocking'])} {str(i.get('name') or i.get('title') or '')[:60]}")
if not a.apply:
    print("NAHLED (nic se nezapsalo), schvalilo by se:", len(items)); sys.exit(0)
if not items:
    print("nic ke schvaleni"); sys.exit(0)
os.makedirs("/opt/konfigurator/backups", exist_ok=True)
bk = "/opt/konfigurator/backups/2026-10-03_miniweb_schvaleni_%s.json" % time.strftime("%H%M%S")
json.dump(items, open(bk, "w"), ensure_ascii=False, default=str, indent=1)
req = [{"kind": i["kind"], "id": i["id"], "lang": i["lang"], "rev": i["rev"]} for i in items]
done, skipped = ma.apply_status_change(cur, a.user_id, req, True)
conn.commit()
print("schvaleno (rowcount):", done, "preskoceno:", skipped, "zaloha:", bk)
sys.exit(0 if done == len(items) and not skipped else 1)
