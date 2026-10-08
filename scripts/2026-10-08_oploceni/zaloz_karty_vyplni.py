#!/usr/bin/env python3
"""NAVRH KARET VYPLNI generatoru OCHRANNY KRYT A OPLOCENI - jen DRY-RUN (bot8, 2026-10-08, faze 1).

Generator pocita vyplne (polykarbonat cira / kourova, plexisklo, svarovana sit, plna vyplne z hlinikoveho kompozitu) jako VIRTUALNI desky `navrh:<typ>` s ORIENTACNI cenou za m2 (oploceni_konfigurator.VYPLNE).
V katalogu zadna karta takove desky zatim NENI (jsou jen drzaky plexiskla a tesneni na sklo). Skript jen CTE (DB se nemeni) a vypise navrh 5 NEAKTIVNICH karet desek (is_board_material=1, jednotka m2,
cena orientacni, bez DPH): SKU, nazev, popis, rozmer tabule, tloustku, GLB (1000 x 1000 x tloustka jako laminodesky), navrh kategorie a existujici karty se stejnym SKU. Zapis NENI implementovan
(`--apply` skonci chybou): po schvaleni Robertem (kategorie, ceny, rozmery tabuli, material pro render) ho doplni faze 2 podle vzoru scripts/2026-10-07_police_stojky/zaloz_kartu_lam12.py
(neaktivni karta, pravidlo 54; aktivuje Robert / bot9).

  api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_karty_vyplni.py                  (nahled; cte DB pres scripts/_env.py nebo systemd-run s EnvironmentFile)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "scripts"))
import oploceni_konfigurator as O  # noqa: E402

if "--apply" in sys.argv:
    sys.exit("CHYBA: zapis karet neni ve fazi 1 implementovan (jen dry-run). Po schvaleni Robertem ho doplni faze 2.")

# typ vyplne -> (nazev karty, tabule sirka x vyska mm, popis)
KARTY = {
    "pc_cira": ("Polykarbonátová deska čirá 4mm", (2050, 3050),
                "Polykarbonátová (PC) deska čirá, tloušťka 4 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo."),
    "pc_koura": ("Polykarbonátová deska kouřová 4mm", (2050, 3050),
                 "Polykarbonátová (PC) deska kouřově šedá, tloušťka 4 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo."),
    "plexi": ("Plexisklo čiré 5mm", (2050, 3050),
              "Plexisklo (akrylátové sklo) čiré, tloušťka 5 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj desky se zasouvá do drážky profilu v těsnění na sklo."),
    "sit": ("Svařovaná síť pozinkovaná – výplň do drážky", (1000, 2000),
            "Svařovaná pozinkovaná síť (drát 2–3 mm, oko 25 × 25 mm) ve formátu tabule, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj tabule se zasouvá do drážky profilu v měkkém těsnění."),
    "plna": ("Hliníkový kompozitní panel 3mm", (1500, 3050),
             "Plná výplň z hliníkového kompozitního panelu (2 × 0,3 mm hliník, plastové jádro), tloušťka 3 mm, prodej na m². Výplň krytů a oplocení z hliníkových profilů: okraj panelu se zasouvá do drážky profilu v měkkém těsnění."),
}
KATEGORIE_NAVRH = "nová podkategorie „Výplně krytů a oplocení“ pod kat. 149 (Hliníkové stavebnicové profily) nebo pod 150 (Příslušenství profilů, kde jsou Držáky plexiskla a Krycí lišty) - rozhodne Robert"

if not os.environ.get("DB_HOST"):
    from _env import get_conn  # noqa: E402  (nahled bez systemd-run, jen cte)
    conn = get_conn()
else:
    import threading
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    sys.path.insert(0, os.path.join(REPO, "api"))
    import app as appmod  # noqa: E402
    threading.Thread.start = _o
    conn = appmod.get_conn()
cur = conn.cursor()
cur.execute("SELECT AUTO_INCREMENT AS a FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
dalsi = int(cur.fetchone()["a"])
print("NAVRH 5 NEAKTIVNICH karet vyplni (is_board_material=1, jednotka m2, ceny ORIENTACNI bez DPH; DB se nemeni)\n")
print(f"{'typ':9s} {'SKU':22s} {'cena Kc/m2':>10s} {'tloustka':>8s} {'tabule mm':>12s}  nazev  [existuje?]")
for typ, (nazev, (tw, th), popis) in KARTY.items():
    info = O.VYPLNE[typ]
    cur.execute("SELECT id, sku, name, active FROM shop_products WHERE sku=%s OR name=%s", (info["sku"], nazev))
    ex = cur.fetchall()
    stav = "NE" if not ex else "ANO: " + ", ".join(f"#{r['id']} {r['sku']} (active={r['active']})" for r in ex)
    print(f"{typ:9s} {info['sku']:22s} {info['cena_m2']:10.0f} {info['tloustka']:6.0f}mm {tw:5d}x{th:<5d}  {nazev}  [{stav}]")
    print(f"          popis: {popis}")
print("\nspolecne: unit=m2, is_board_material=1, active=0 (pravidlo 54), visible_in_scene=1 + glb_file=product_<id>.glb (kvadr 1000 x 1000 x tloustka, glb_lam12.kvadr; cenovy kontext bere jen karty s GLB),")
print("          render_material_key=NULL (Blender material pro rendery nabidky urci Robert / bot10), kategorie: " + KATEGORIE_NAVRH)
print(f"dalsi volne ID karty = {dalsi} (karty by dostaly {dalsi}..{dalsi + len(KARTY) - 1}, pokud mezitim nikdo nezalozi jinou)")
print("po zalozeni: v oploceni_konfigurator.VYPLNE doplnit `karta` (id) a v entries misto `navrh:<typ>` pouzit `product_<id>`")
print("\n(nahled, nic nezapsano)")
