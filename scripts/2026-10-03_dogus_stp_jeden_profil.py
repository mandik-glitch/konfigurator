#!/opt/konfigurator/api/venv/bin/python
"""Stazeni STP JEDNOHO produktu z Dogus (bot10, 2026-10-03, Robert: "1.1.10.040040.03 tento profil... jen mu stahni stp z Dogus kalip").

Ucel: realny 3D profil 40x40 pro animovanou ukazku "stavebnice" (matice zasunuta do dragky). Robert vyslovne povolil STP profilu
(jinak plati stare pravidlo "profily STP se nestahuji", viz scripts/2026-08-08_dogus_stp_download.py).

Rozdil proti hromadnemu stahovani: ZADNY zapis do DB (shop_products se nemeni, zadna karta ani glb_file), soubor jde do
PRIVATNIHO adresare (neni servirovan webem): private-files/dogus-stp/<sku>.step. Prihlaseni a nalezeni prvniho CAD souboru
pouziva funkce z puvodniho skriptu (login = DOGUS_LOGIN_EMAIL/PASSWORD z api/.env, nikdy se nevypisuji).

  api/venv/bin/python scripts/2026-10-03_dogus_stp_jeden_profil.py --sku 1.1.10.040040.03            # jen zjisti odkaz (nic nestahuje)
  api/venv/bin/python scripts/2026-10-03_dogus_stp_jeden_profil.py --sku 1.1.10.040040.03 --apply    # stahne
"""
import argparse
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("dogus_stp", os.path.join(HERE, "2026-08-08_dogus_stp_download.py"))
D = importlib.util.module_from_spec(spec)
spec.loader.exec_module(D)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sku", required=True)
    ap.add_argument("--apply", action="store_true", help="skutecne stahnout (bez toho jen zjisti odkaz na CAD soubor)")
    ap.add_argument("--out-dir", default=os.path.join(REPO, "private-files", "dogus-stp"))
    a = ap.parse_args()
    if not re.fullmatch(r"[0-9A-Za-z._-]{3,40}", a.sku):
        sys.exit("neplatne SKU")

    conn = D.get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, sku, name, dogus_url FROM shop_products WHERE sku=%s", (a.sku,))
            rows = cur.fetchall()
    finally:
        conn.close()
    if len(rows) != 1 or not rows[0]["dogus_url"]:
        sys.exit("produkt s timto SKU nenalezen / nema dogus_url (nalezeno %d)" % len(rows))
    p = rows[0]
    print("produkt #%s %s (%s)" % (p["id"], p["sku"], p["name"]))

    env = D.load_env()
    opener = D.make_session(env["DOGUS_LOGIN_EMAIL"], env["DOGUS_LOGIN_PASSWORD"])
    print("prihlaseni na doguskalip OK")
    html = D.fetch(opener, p["dogus_url"])
    cad = D.find_first_cad(html)
    if not cad:
        sys.exit("na strance produktu neni zadny CAD soubor (po prihlaseni)")
    name, url = cad
    print("prvni CAD soubor: %r -> %s" % (name, url.split("?")[0]))
    if not a.apply:
        print("(bez --apply nic nestazeno)")
        return
    data, ctype = D.download_file(opener, url)
    head = data[:200].decode("latin-1", errors="replace")
    if not data.startswith(b"ISO-10303-21"):
        sys.exit("stazeny soubor neni STEP (Content-Type=%s, zacatek=%r)" % (ctype, head[:60]))
    os.makedirs(a.out_dir, mode=0o750, exist_ok=True)
    out = os.path.join(a.out_dir, "%s.step" % a.sku)
    with open(out, "wb") as f:
        f.write(data)
    os.chmod(out, 0o640)
    print("ulozeno: %s (%d B, Content-Type=%s)" % (out, len(data), ctype))
    m = re.search(r"FILE_NAME\s*\(\s*'([^']*)'", data[:4000].decode("latin-1", errors="replace"))
    print("STEP FILE_NAME:", m.group(1) if m else "?")


if __name__ == "__main__":
    main()
