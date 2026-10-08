#!/opt/konfigurator/api/venv/bin/python
"""Cena a kusovnik hotovych valeckovych dopravniku Dogus (kat. 161, 90 karet) Z KOMPONENT (bot5, 2026-10-07; Robert: "recept z komponent", parametry k jeho potvrzeni).

Recept: docs/dopravniky_recept.json (pravidla, parametry, vychozi volby). Cena = ceil( soucet(Dogus List Price USD x mnozstvi) x kurz Fio USD prodej x koeficient kategorie x (1 + prirazka) ) - jako pravidlo 9
(zaokrouhleni nahoru). Ceny slozek: shop_products.dogus_list_price_usd (nocni prepocet), jinak z prihlaseneho cteni backups/2026-10-07_dogus_dopravniky_ceny_jednotky.json (nove slozky do 1. nocniho behu).
Faze: --ukazka = jen vypocet 3 dopravniku (nejkratsi, stredni, nejdelsi) a variant voleb, NIC se nezapisuje; zapis na vsech 90 az po schvaleni ukazky Robertem.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/dopravniky_cena_z_komponent.py --ukazka"""
import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RECEPT = os.path.join(REPO, "docs", "dopravniky_recept.json")
CENY_JSON = os.path.join(REPO, "backups", "2026-10-07_dogus_dopravniky_ceny_jednotky.json")


def nacti_recept(cesta=RECEPT):
    return json.load(open(cesta, encoding="utf-8"))


class ChybiValecek(Exception):
    """pro danou sirku neexistuje SKUTECNY valecek (vroubkovane 1000, ocel 1200) - dopravnik se necenit"""


def rozloz_kod(kod, recept):
    """'16.10.01.051.0600.3000.0' -> (rada, sirka_seg, delka_mm, skutecna_delka_valecku_mm); ChybiValecek, kdyz skutecny valecek neexistuje"""
    p = kod.split(".")
    rada = ".".join(p[:4])
    if rada not in recept["rady"] or len(p) != 7:
        raise ValueError(f"neznama rada / tvar kodu: {kod}")
    W = recept["skutecne_valecky_mm"][rada].get(p[4])
    if W is None:
        raise ChybiValecek(f"{kod}: skutecny valecek pro sirku {p[4]} neexistuje")
    return rada, p[4], int(p[5]), W


def pocet_noh(delka_mm, volba):
    m = delka_mm / 1000.0
    if volba == "vzdy4":
        return 4
    if volba == "2_4_6":
        return 4 if m <= 2 else (6 if m <= 4 else 8)
    return 4 if m <= 3 else 6                                  # 3m_6m


def usd_valecku(usd, prefix, delka_valecku):
    """(cena USD, odhad: bool). Chybi-li valecek dane delky (nejsiroke rady), cena se odhadne linearne z dvou nejdelsich dostupnych (odhad se v kusovniku oznaci)."""
    sku = f"{prefix}{delka_valecku}"
    if sku in usd:
        return usd[sku], False
    dostupne = sorted((int(k[len(prefix):]), v) for k, v in usd.items() if k.startswith(prefix) and k[len(prefix):].isdigit())
    if len(dostupne) < 2:
        raise KeyError(f"zadny valecek rady {prefix} v cenach")
    (l1, p1), (l2, p2) = dostupne[-2], dostupne[-1]
    return round(p2 + (p2 - p1) / (l2 - l1) * (delka_valecku - l2), 2), True


def kusovnik(kod, recept, usd, volby=None):
    """-> (radky, soucet_usd). radek = {nazev, sku, mnozstvi, jednotka, usd_jedn, usd, poznamka}"""
    v = dict(recept["vychozi"])
    v.update(volby or {})
    rada, sirka, L, W = rozloz_kod(kod, recept)
    r = recept["rady"][rada]
    prof = recept["profily"][r["profil"]]
    radky = []

    def pridej(nazev, sku, mnozstvi, jednotka, usd_jedn, poznamka=""):
        radky.append({"nazev": nazev, "sku": sku, "mnozstvi": round(mnozstvi, 3), "jednotka": jednotka, "usd_jedn": round(usd_jedn, 4), "usd": round(usd_jedn * mnozstvi, 2), "poznamka": poznamka})

    n_val = int(L // recept["rozteč_valecku_mm"])
    sku_val = f"{r['valecek_prefix']}{W}"
    if sku_val not in usd:
        raise ChybiValecek(f"{kod}: valecek {sku_val} nema cenu")
    pridej(f"{r['nazev_valecku']} délky {W} mm", sku_val, n_val, "ks", usd[sku_val])
    pridej(f"{prof['nazev']} (2 boční profily)", prof["sku"], 2 * L / 1000.0, "m", usd[prof["sku"]])        # Dogus List Price profilu je USD za 1 METR (Robert 2026-08-10); delit delkou tyce NE (chyba v1 2026-10-07: profil a H-ram vychazely 3x levneji)
    nohy = pocet_noh(L, v["nohy"])
    pridej(prof["noha_nazev"], prof["noha_sku"], nohy, "ks", usd[prof["noha_sku"]])
    pridej(recept["patka"]["nazev"], recept["patka"]["sku"], nohy * recept["patka"]["na_nohu"], "ks", usd[recept["patka"]["sku"]])
    if v["h_ram"] != "zadny":
        h = recept["h_ram"]
        pary = nohy // 2
        cena_m = usd[h["profil_sku"]]                                    # USD za 1 metr (viz vyse)
        pridej(f"{h['profil_nazev']} – příčky H-rámu (šířka {W} mm)", h["profil_sku"], pary * W / 1000.0, "m", cena_m)
        if v["h_ram"] == "pricka_podelna":
            pridej(f"{h['profil_nazev']} – podélná příčka", h["profil_sku"], max(L / 1000.0 - 0.2, 0.0), "m", cena_m)
        pridej(h["konektor_nazev"], h["konektor_sku"], pary * h["konektoru_na_par"], "ks", usd[h["konektor_sku"]])
    return radky, round(sum(x["usd"] for x in radky), 2)


def cena_czk(soucet_usd, kurz, koef, prirazka_pct):
    return math.ceil(soucet_usd * (1 + prirazka_pct / 100.0) * kurz * koef - 1e-9)


def nacti_usd(cur, recept, kody):
    """USD slozek: DB (dogus_list_price_usd) prednostne, jinak prihlasene cteni (nove slozky). -> {sku: usd}"""
    ceny = json.load(open(CENY_JSON, encoding="utf-8"))
    usd = {k: v["cena_usd"] for k, v in ceny.items() if v.get("cena_usd")}
    skus = {p["sku"] for p in recept["profily"].values()} | {p["noha_sku"] for p in recept["profily"].values()} | {recept["patka"]["sku"], recept["h_ram"]["profil_sku"], recept["h_ram"]["konektor_sku"]}
    cur.execute("SELECT sku, dogus_list_price_usd FROM shop_products WHERE sku IN (" + ",".join(["%s"] * len(skus)) + ") AND dogus_list_price_usd IS NOT NULL", sorted(skus))
    for r in cur.fetchall():
        usd[r["sku"]] = float(r["dogus_list_price_usd"])
    for p in recept["profily"].values():
        for s in (p["sku"], p["noha_sku"]):
            if s not in usd:
                raise KeyError(f"chybi cena slozky {s}")
    return usd


def text_kusovniku(radky):
    """Kusovnik jako text pro product_specs_json (bez nazvu dodavatele): '20× Hliníkový váleček Ø50 délky 590 mm; 6 m Dopravníkový profil ...'"""
    casti = []
    for x in radky:
        mn = f"{x['mnozstvi']:.2f}".rstrip("0").rstrip(".").replace(".", ",") if x["jednotka"] == "m" else str(int(round(x["mnozstvi"])))
        casti.append(f"{mn}{' m' if x['jednotka'] == 'm' else '×'} {x['nazev']}")
    return "; ".join(casti)


def uprav_nazev_valecku(name, description, stary, novy):
    """Vroubkovane dopravniky: Dogus uvadi sirku valecku 300/450/600/800, skutecny valecek je 290/440/590/790 -> nazev i popis se skutecnou delkou."""
    if stary == novy:
        return name, description
    n = name.replace(f"×{stary} mm", f"×{novy} mm")
    d = description.replace(f"×{stary} mm", f"×{novy} mm").replace(f"délka válečku {stary} mm", f"délka válečku {novy} mm")
    return n, d


def zapis_dopravniky(cur, recept, usd, kurz, apply, zalohuj=None, volby=None, slug_for_name=None):
    """Cena + Kusovnik + skutecna delka valecku u 78 dopravniku s existujicim valeckem; zbytek (12) se nemeni. Nekomituje. -> {'zapsano': [...], 'preskoceno': [...]}"""
    cur.execute("SELECT id, sku, name, slug, description, product_specs_json, price_czk_placeholder, active, dogus_url FROM shop_products WHERE sku REGEXP '^16\\.1[02]\\.01\\.05[01]\\.[0-9]{4}\\.[0-9]{4}\\.0$' ORDER BY id")
    karty = cur.fetchall()
    koef = recept["koeficient_kategorie"]
    prirazka = (volby or {}).get("prirazka_pct", recept["vychozi"]["prirazka_pct"])
    zapsano, preskoceno, zaloha = [], [], []
    for k in karty:
        if k["active"] or k["dogus_url"] is not None:
            preskoceno.append((k["sku"], "karta je aktivni nebo navazana na Dogus"))
            continue
        try:
            rada, sirka, L, W = rozloz_kod(k["sku"], recept)
            radky, soucet = kusovnik(k["sku"], recept, usd, volby)
        except ChybiValecek as e:
            preskoceno.append((k["sku"], str(e)))
            continue
        specs = json.loads(k["product_specs_json"] or "{}")
        # pravda je KOD (sirka a delka dopravniku z kodu; tabulka Dogusu ma u nekterych SKU zkopirovane udaje sousedniho radku - nalez bot7); nominalni sirka = segment kodu (0600 -> 600), skutecny valecek W
        stary = str(int(sirka))
        nazev, popis = uprav_nazev_valecku(k["name"], k["description"], stary, str(W))
        specs["Roller length"] = str(W)
        specs["Conveyor Length"] = str(L)
        specs["Kusovník"] = text_kusovniku(radky)
        cena = cena_czk(soucet, kurz, koef, prirazka)
        slug = k["slug"]
        if nazev != k["name"] and slug_for_name:
            slug = slug_for_name(cur, nazev, k["id"])
        zaloha.append({kk: (str(vv) if vv is not None else None) for kk, vv in k.items()})
        zapsano.append({"id": k["id"], "sku": k["sku"], "cena_czk": cena, "soucet_usd": soucet, "nazev": nazev, "zmena_nazvu": nazev != k["name"], "slug": slug})
        if apply:
            n = cur.execute("UPDATE shop_products SET name=%s, slug=%s, description=%s, product_specs_json=%s, price_czk_placeholder=%s, dogus_list_price_usd=%s, dogus_price_rate_used=%s WHERE id=%s AND active=0 AND dogus_url IS NULL",
                            (nazev, slug, popis, json.dumps(specs, ensure_ascii=False), cena, soucet, kurz, k["id"]))
            cur.execute("SELECT name, price_czk_placeholder FROM shop_products WHERE id=%s AND active=0 AND dogus_url IS NULL", (k["id"],))
            kontrola = cur.fetchone()          # rowcount UPDATE je 0, kdyz jsou hodnoty uz shodne (opakovany zapis) - overuje se vysledek
            if n > 1 or not kontrola or kontrola["name"] != nazev or float(kontrola["price_czk_placeholder"] or -1) != float(cena):
                raise RuntimeError(f"UPDATE {k['sku']} nezapsal ocekavane hodnoty (rowcount {n})")
    if apply and zalohuj:
        zalohuj(zaloha)
    return {"zapsano": zapsano, "preskoceno": preskoceno}


def ukazka():
    recept = nacti_recept()
    spec = importlib.util.spec_from_file_location("dpr", os.path.join(HERE, "2026-08-09_dogus_price_recompute.py"))
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)
    sys.path.insert(0, HERE)
    from _env import get_conn
    conn = get_conn()
    cur = conn.cursor()
    usd = nacti_usd(cur, recept, [])
    conn.rollback()
    conn.close()
    kurz = float(D.fetch_fio_usd_czk_sell_rate())
    koef = recept["koeficient_kategorie"]
    vzorky = [("nejkratší", "16.12.01.050.0300.1000.0"), ("střední", "16.10.01.050.0600.3000.0"), ("nejdelší", "16.10.01.051.1000.6000.0")]
    out = {"kurz_usd_czk": kurz, "koeficient": koef, "vychozi": recept["vychozi"], "vzorky": []}
    for popis, kod in vzorky:
        radky, soucet = kusovnik(kod, recept, usd)
        var = {"nohy": {}, "h_ram": {}, "prirazka": {}}
        for k in recept["volby"]["nohy"]:
            rr, ss = kusovnik(kod, recept, usd, {"nohy": k})
            var["nohy"][k] = {"nohy": pocet_noh(rozloz_kod(kod, recept)[2], k), "cena_czk": cena_czk(ss, kurz, koef, recept["vychozi"]["prirazka_pct"])}
        for k in recept["volby"]["h_ram"]:
            rr, ss = kusovnik(kod, recept, usd, {"h_ram": k})
            var["h_ram"][k] = {"cena_czk": cena_czk(ss, kurz, koef, recept["vychozi"]["prirazka_pct"])}
        for p in recept["volby"]["prirazka_pct"]:
            var["prirazka"][str(p)] = {"cena_czk": cena_czk(soucet, kurz, koef, p)}
        out["vzorky"].append({"popis": popis, "kod": kod, "radky": radky, "soucet_usd": soucet, "cena_czk": cena_czk(soucet, kurz, koef, recept["vychozi"]["prirazka_pct"]), "varianty": var})
    json.dump(out, open(os.path.join(REPO, "backups", "2026-10-07_dopravniky_ukazka_receptu.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"kurz Fio USD prodej {kurz}, koeficient {koef}, výchozí volby {recept['vychozi']}")
    for v in out["vzorky"]:
        print(f"\n== {v['popis']}: {v['kod']}  -> {v['soucet_usd']} USD, cena {v['cena_czk']} Kč (přirážka {recept['vychozi']['prirazka_pct']} %)")
        for x in v["radky"]:
            print(f"   {x['nazev'][:58]:58} {x['mnozstvi']:>7} {x['jednotka']:2} x {x['usd_jedn']:>7} = {x['usd']:>8} USD {('(' + x['poznamka'] + ')') if x['poznamka'] else ''}")
        print("   varianty:", json.dumps(v["varianty"], ensure_ascii=False))


def zapis_cli(apply):
    recept = nacti_recept()
    spec = importlib.util.spec_from_file_location("dpr", os.path.join(HERE, "2026-08-09_dogus_price_recompute.py"))
    D = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(D)
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(REPO, "api"))
    from _env import get_conn
    import product_slug
    conn = get_conn()
    cur = conn.cursor()
    usd = nacti_usd(cur, recept, [])
    kurz = float(D.fetch_fio_usd_czk_sell_rate())
    zaloha_cesta = os.path.join(REPO, "backups", "2026-10-07_dopravniky_pred_zapisem_receptu.json")
    if apply and os.path.exists(zaloha_cesta):
        raise SystemExit(f"ZASTAVENO: zaloha {zaloha_cesta} uz existuje - recept se uz zapisoval")

    def zalohuj(rows):
        json.dump(rows, open(zaloha_cesta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    vys = zapis_dopravniky(cur, recept, usd, kurz, apply, zalohuj, slug_for_name=product_slug.slug_for_name)
    print(f"kurz {kurz}; k zapisu {len(vys['zapsano'])} dopravniku, preskoceno {len(vys['preskoceno'])}")
    for s in vys["preskoceno"][:14]:
        print("  preskoceno:", s)
    zm = [z for z in vys["zapsano"] if z["zmena_nazvu"]]
    print(f"  zmena nazvu (skutecna delka valecku) u {len(zm)}: napr. {zm[0]['nazev'] if zm else '-'}")
    for z in vys["zapsano"][:3] + vys["zapsano"][-2:]:
        print(f"  {z['sku']} -> {z['cena_czk']} Kč ({z['soucet_usd']} USD)")
    if not apply:
        conn.rollback()
        print("(nahled: nic nezapsano; --apply)")
        return
    cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'update','shop_product',NULL,%s)",
                (f"cena + kusovnik z komponent u {len(vys['zapsano'])} valeckovych dopravniku (Robert 2026-10-07: volby potvrzeny, jen dopravniky se skutecnym valeckem); nazvy vroubkovanych se skutecnou delkou valecku",))
    conn.commit()
    print("ZAPSANO a commitnuto")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ukazka", action="store_true")
    ap.add_argument("--zapis", action="store_true", help="nahled zapisu cen/kusovniku/nazvu (78 dopravniku se skutecnym valeckem), bez --apply nic nezapise")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.ukazka:
        return ukazka()
    if a.zapis:
        return zapis_cli(a.apply)
    sys.exit("pouzij --ukazka nebo --zapis [--apply]")


if __name__ == "__main__":
    main()
