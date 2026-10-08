#!/usr/bin/env python3
"""Zalozeni produktove karty konfigurovatelneho OCHRANNEHO KRYTU A OPLOCENI a registrace v app_settings.configurator_products (bot8, 2026-10-08, faze 2; vzor
scripts/2026-10-07_system45/zaloz_kartu_system45.py).

Robert 2026-10-08: "nahrat vsechno hned". Kontrakt konfiguratoru (api/stul_shop.py -> api/konfigurator_registr.py -> api/oploceni_shop.py) potrebuje JEDNO shop_products.id konfigurovatelneho produktu;
stranka Generator 06 (webapp/oploceni-konfigurator.html) si ho najde sama (GET /api/shop/configurator/recepty/oploceni_kryt, jen zamestnanci). Skript zalozi kartu OPLOCENI.KRYT.KONF:
NEAKTIVNI (active=0, pravidlo 54 - aktivni ruce nepřepinat), jednotka ks, bez kategorie a bez ceny (cena se bere z resolve), s popisem a meta texty; do `configurator_products` jen PRIDA zaznam
{"<id>": "oploceni_kryt"} (read-modify-write v transakci: radek se zamkne FOR UPDATE a zapis plati jen kdyz se hodnota od cteni nezmenila).

JAK SE NEAKTIVNI KARTA CHOVA (overeno cteni kodu a u neaktivnich karet stolu 41 / 45): routy schema / resolve / model / glb (api/stul_shop.py) kontroluji JEN zaznam v configurator_products, ne `active`
- generator tedy funguje pro zamestnance (stranka Generator 06) i pro kohokoli, kdo zna id karty (stejne jako generatory stolu u neaktivnich karet; v odpovedi neni nic tajneho: dily, cena, model).
KOSIK a OBJEDNAVKA (api/konfigurace_kosik.py pridat_do_kosiku) vyzaduji active=1 a neni archivovana = neaktivni kartu nikdo nekoupi; produktove stranky obchodu neaktivni karty neukazuji.
Zverejneni = aktivace karty Robertem (pravidlo 54) + stranka produktu / mini-shop (mimo tuto fazi).

  api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_kartu_oploceni.py            (nahled, nic nezapise)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-10-08_oploceni/zaloz_kartu_oploceni.py --apply          (zapis; pouze po nasazeni kodu faze 2 - viz README_FAZE2.md)

Idempotentni: existuje-li uz karta se SKU `OPLOCENI.KRYT.KONF`, pouzije se (nepise se nic jineho nez chybejici zaznam v configurator_products). Zapis se overuje rowcountem a po commitu se potvrzena data znovu precte z DB.
Logika zapisu (`nacti_stav`, `zapis`, `over_zapis`) je v funkcich bez vlastniho pripojeni - test_oploceni_karty.py ji zkousi proti FALESNE DB (zadny dotaz na produkcni DB).
POZOR: zaznam v `configurator_products` zapne routy pro recept oploceni_kryt AZ PO NASAZENI kodu (api/*.py nasazuje plánovana sluzba 0:00 / 12:30); do te doby stary kod zaznam neznameho receptu
ignoruje (konfigurovatelny(id) = False -> 404), nic se tim nerozbije."""
import json
import os
import sys
import threading

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
SKU = "OPLOCENI.KRYT.KONF"
NAZEV = "Ochranný kryt a oplocení – konfigurovatelný"
RECEPT = "oploceni_kryt"
KLIC = "configurator_products"
POPIS = ("Ochranný kryt nebo oplocení stroje z hliníkových profilů 40×40 s drážkou 10 mm. Stěny, dveře a střecha s výplní z polykarbonátu (čirého nebo kouřového), plexiskla, svařované sítě "
         "nebo plného panelu; rozměry, strany, dveře a výplň si zvolíte v konfigurátoru, cena se počítá podle skutečného složení. Vyrábí se na zakázku. Konstrukce řeší kryt a oplocení, "
         "bezpečnostní vzdálenosti a otvory výplní (ČSN EN ISO 14120, ČSN EN ISO 13857) posuzuje projektant stroje.")
META_T = "Ochranný kryt a oplocení strojů z profilů 40×40 – konfigurátor na míru"
META_D = "Konfigurátor ochranného krytu a oplocení stroje z hliníkových profilů 40×40: rozměry, strany, dveře, střecha a výplň (polykarbonát, plexisklo, síť). Cena podle skutečného složení."


def nacti_stav(cur):
    """(karta | None, mapa configurator_products, {id: recept} jinych karet stejneho receptu): jen cte."""
    cur.execute("SELECT id, sku, name, slug, active, is_archived FROM shop_products WHERE sku=%s", (SKU,))
    karta = cur.fetchone()
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
    row = cur.fetchone()
    mapa = json.loads(row["setting_value"]) if row and row["setting_value"] else {}
    ostatni = {k: v for k, v in mapa.items() if v == RECEPT and (karta is None or str(karta["id"]) != k)}
    return karta, mapa, ostatni


def plan_text(karta):
    return ("pouzit existujici kartu #%s" % karta["id"] if karta else "INSERT neaktivni karty '%s' (SKU %s, unit ks, active 0, bez kategorie a ceny, popis + meta)" % (NAZEV, SKU)) \
        + "; configurator_products += {\"<id>\": \"%s\"} (compare-and-set, audit_log)" % RECEPT


def zapis(conn, cur, slug_fn, karta):
    """Zapis v JEDNE transakci (commit na konci, pri jakekoli chybe rollback a vyjimka RuntimeError): -> id karty. `karta` = vysledek nacti_stav (existujici karta, nebo None)."""
    try:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s FOR UPDATE", (KLIC,))
        row = cur.fetchone()
        puvodni = row["setting_value"] if row else None
        mapa = json.loads(puvodni) if puvodni else {}
        if karta is None:
            cur.execute("INSERT INTO shop_products (sku, name, slug, description, unit, active, meta_title, meta_description) VALUES (%s,%s,%s,%s,%s,0,%s,%s)",
                        (SKU, NAZEV, slug_fn(cur, NAZEV), POPIS, "ks", META_T, META_D))
            if cur.rowcount != 1:
                raise RuntimeError(f"INSERT karty rowcount={cur.rowcount}")
            pid = cur.lastrowid
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (None, "create", "shop_product", pid, f"bot8: neaktivni karta konfigurovatelneho ochranneho krytu a oploceni ({SKU}), generator 06 (Robert 2026-10-08)"))
        else:
            pid = karta["id"]
        if mapa.get(str(pid)) != RECEPT:
            mapa[str(pid)] = RECEPT
            nova = json.dumps(mapa, sort_keys=True)
            if puvodni is None:
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)", (KLIC, nova))
            else:
                cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s AND setting_value=%s", (nova, KLIC, puvodni))
            if cur.rowcount != 1:
                raise RuntimeError(f"zapis configurator_products rowcount={cur.rowcount} (hodnota se mezitim zmenila?)")
            cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (%s,%s,%s,%s,%s)",
                        (None, "update", "app_settings", None, f"bot8: configurator_products += {{\"{pid}\": \"{RECEPT}\"}} (puvodne: {puvodni})"))
        conn.commit()
        return pid
    except Exception as e:                                              # noqa: BLE001 - nic se nezapise napul
        conn.rollback()
        raise RuntimeError(f"{e} - ROLLBACK, nic se nezapsalo") from e


def over_zapis(cur2, pid):
    """Overeni po commitu (`cur2`; get_conn() vraci sdilene spojeni threadu, cte se ale potvrzena data): karta neaktivni a recept v configurator_products. -> (karta, hodnota nastaveni)."""
    cur2.execute("SELECT id, sku, name, slug, active FROM shop_products WHERE id=%s", (pid,))
    k2 = cur2.fetchone()
    cur2.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
    v2 = cur2.fetchone()["setting_value"]
    assert k2 and k2["sku"] == SKU and k2["active"] == 0 and json.loads(v2).get(str(pid)) == RECEPT, (k2, v2)
    return k2, v2


def pripoj():
    """(get_conn, slug_fn): v systemd-run s DB_* z .env pres app.py, jinak (nahled) pres scripts/_env.py."""
    if not os.environ.get("DB_HOST"):
        from _env import get_conn  # noqa: E402  (nahled bez systemd-run, jen cte)
        return get_conn, None
    _o = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
    import app as appmod  # noqa: E402
    threading.Thread.start = _o
    return appmod.get_conn, appmod._product_slug_for_name


def main(argv):
    apply = "--apply" in argv
    get_conn, slug_fn = pripoj()
    conn = get_conn()
    cur = conn.cursor()
    karta, mapa, ostatni = nacti_stav(cur)
    print("karta se SKU", SKU, ":", karta or "NEEXISTUJE", "| configurator_products:", mapa or "nenastaveno")
    if ostatni:
        print("POZOR: recept", RECEPT, "uz maji jine karty:", ostatni, "- stranka generatoru pouzije kartu s nejnizsim id")
    if not apply:
        print("\nplan (--apply): " + plan_text(karta))
        print("\n(nahled, nic nezapsano - zapis: --apply pres systemd-run, viz hlavicka)")
        return 0
    if slug_fn is None:
        print("CHYBA: --apply jen pres systemd-run s DB_* z api/.env (viz hlavicka)")
        return 2
    try:
        pid = zapis(conn, cur, slug_fn, karta)
    except RuntimeError as e:
        print(f"CHYBA: {e}")
        return 1
    k2, v2 = over_zapis(get_conn().cursor(), pid)
    print(f"zapsano a overeno po commitu (cteni z DB): karta #{pid} {k2['sku']} (active=0, slug {k2['slug']}), configurator_products = {v2}")
    print("OPLOCENI_KARTA_ID", pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
