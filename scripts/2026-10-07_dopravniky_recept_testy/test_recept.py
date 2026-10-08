#!/opt/konfigurator/api/venv/bin/python
"""Recept ceny valeckovych dopravniku z komponent (bot5, 2026-10-07): scripts/dopravniky_cena_z_komponent.py (kusovnik, cena_czk, zapis_dopravniky) nad DOCASNOU kopii 90 skutecnych karet
(shop_products; ostre se nemeni, kontrola samostatnym spojenim) s cenami slozek z ostre DB/JSON. Spusteni:
 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dopravniky_recept_testy/test_recept.py"""
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.dont_write_bytecode = True
from _env import get_conn  # noqa: E402
import product_slug  # noqa: E402
spec = importlib.util.spec_from_file_location("rec", os.path.join(REPO, "scripts", "dopravniky_cena_z_komponent.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def stav():
    c = get_conn()
    try:
        cu = c.cursor()
        cu.execute("SELECT COUNT(*) n, COALESCE(SUM(price_czk_placeholder),0) s, MD5(GROUP_CONCAT(name ORDER BY id)) h FROM shop_products WHERE category_id=324")
        r = cu.fetchone()
        return (r["n"], str(r["s"]), r["h"])
    finally:
        c.close()


pred = stav()
recept = R.nacti_recept()
conn = get_conn()
cur = conn.cursor()
usd = R.nacti_usd(cur, recept, [])
cur.execute("CREATE TEMPORARY TABLE _src AS SELECT * FROM shop_products WHERE category_id=324")
cur.execute("CREATE TEMPORARY TABLE _tpl_shop_products LIKE shop_products")
cur.execute("CREATE TEMPORARY TABLE shop_products LIKE _tpl_shop_products")
cur.execute("INSERT INTO shop_products SELECT * FROM _src")
# vrat puvodni stav (ostre karty uz mohou mit zapsane ceny): bez ceny, puvodni nazvy ze zalohy neexistuji -> test pracuje s tim, co v DB je; nulovani ceny a Kusovniku
cur.execute("UPDATE shop_products SET price_czk_placeholder=NULL, dogus_list_price_usd=NULL, dogus_price_rate_used=NULL, active=0")      # ZIVE karty jsou po Robertove aktivaci aktivni a prejmenovane; test simuluje vychozi stav pred zapisem receptu
cur.execute("SELECT id, sku, name, description, product_specs_json FROM shop_products WHERE sku LIKE '16.12.01.050.%'")
_ZPET = {"290": "300", "440": "450", "590": "600", "790": "800"}
for r_ in cur.fetchall():                     # vroubkovane: vrat puvodni (Dogus) delky 300/450/600/800 v nazvu, popisu a parametru Roller length
    sp_ = json.loads(r_["product_specs_json"])
    skut = sp_.get("Roller length")
    if skut in _ZPET:
        n_, d_ = R.uprav_nazev_valecku(r_["name"], r_["description"], skut, _ZPET[skut])
        sp_["Roller length"] = _ZPET[skut]
        cur.execute("UPDATE shop_products SET name=%s, description=%s, product_specs_json=%s WHERE id=%s", (n_, d_, json.dumps(sp_, ensure_ascii=False), r_["id"]))
conn.commit()
cur.execute("SELECT id, sku, name, slug, description, product_specs_json FROM shop_products")
PUV = {r["sku"]: r for r in cur.fetchall()}
over("0 pracuji s 90 kartami dopravniku", len(PUV) == 90, len(PUV))
KURZ = 22.38391
zal = []
vys = R.zapis_dopravniky(cur, recept, usd, KURZ, True, lambda rows: zal.extend(rows), slug_for_name=product_slug.slug_for_name)
conn.commit()
ok = {z["sku"]: z for z in vys["zapsano"]}
over("S1 zapsano 78 dopravniku se SKUTECNYM valeckem, 12 preskoceno (vroubkovane sirka 1000 a ocel 1200)", len(vys["zapsano"]) == 78 and len(vys["preskoceno"]) == 12
     and all(("1000.0" in s or ".1000." in s) or "051.1200" in s for s, _ in vys["preskoceno"]) and sum(1 for s, _ in vys["preskoceno"] if s.startswith("16.12.01.050.1000")) == 6 and sum(1 for s, _ in vys["preskoceno"] if s.startswith("16.10.01.051.1200")) == 6,
     (len(vys["zapsano"]), vys["preskoceno"][:3]))
cur.execute("SELECT sku, name, slug, description, product_specs_json, price_czk_placeholder, dogus_list_price_usd, dogus_price_rate_used, active, dogus_url FROM shop_products")
NOV = {r["sku"]: r for r in cur.fetchall()}
nes = [s for s in NOV if s not in ok]
over("S2 preskocenych 12 se NEZMENILO (nazev, cena zustala NULL, popis, specifikace)", all(NOV[s]["name"] == PUV[s]["name"] and NOV[s]["price_czk_placeholder"] is None and NOV[s]["description"] == PUV[s]["description"] and NOV[s]["product_specs_json"] == PUV[s]["product_specs_json"] for s in nes) and len(nes) == 12, len(nes))
kn = [s for s in ok if s.startswith("16.12.01.050.") and not s.startswith("16.12.01.050.1000")]
def _chyby_s3(s):
    rl = json.loads(NOV[s]["product_specs_json"])["Roller length"]
    n, d = NOV[s]["name"], NOV[s]["description"]
    return [] if (f"×{rl} mm" in n and rl in ("290", "440", "590", "790") and "×300 mm" not in n and "×450 mm" not in n and f"délka válečku {rl} mm" in d) else [(s, rl, n[:60], d[:130])]
chyby3 = [c for s in kn for c in _chyby_s3(s)]
over("S3 vroubkovane (24): nazev, popis i parametr 'Roller length' maji SKUTECNOU delku valecku (290/440/590/790), ne 300/450/600/800", len(kn) == 24 and not chyby3, (len(kn), chyby3[:2]))
over("S4 hlinikove a ocelove (54) maji nazev beze zmeny (uz mely skutecne delky), kusovnik a cenu", all(NOV[s]["name"] == PUV[s]["name"] for s in ok if not s.startswith("16.12.01.050")) and sum(1 for s in ok if not s.startswith("16.12.01.050")) == 54, None)
over("S5 slug u zmenenych nazvu odpovida novemu nazvu a je unikatni", len({r["slug"] for r in NOV.values()}) == 90 and all("50290" in NOV[s]["slug"] or "50440" in NOV[s]["slug"] or "50590" in NOV[s]["slug"] or "50790" in NOV[s]["slug"] for s in kn), [NOV[s]["slug"] for s in kn[:2]])
s0 = "16.10.01.050.0600.3000.0"
radky, soucet = R.kusovnik(s0, recept, usd)
# nezavisly vypocet (USD za 1 METR profilu, oprava 2026-10-07): 20 valecku + 6 m profilu 23x75 + 4 nohy + 4 patky + H-ram (2 pricky po 0,59 m, podelna 2,8 m, 8 uchytu)
ocek_usd = round(20 * usd["3.009.01.50.590"] + 6 * usd["1.2.00.023075.00"] + 4 * usd["3.004.03.01"] + 4 * usd["2.3.002.1050"]
                 + (2 * 0.59 + 2.8) * usd["1.1.10.040040.02"] + 8 * usd["3.006.240.021.180"], 2)
over("S6 cena = ceil(soucet USD x 1,10 x kurz x 1,2) a soucet USD z NEZAVISLEHO vypoctu (profil za 1 m): stredni vzorek", NOV[s0]["price_czk_placeholder"] == R.cena_czk(soucet, KURZ, 1.2, 10) and soucet == ocek_usd
     and NOV[s0]["price_czk_placeholder"] == math.ceil(ocek_usd * 1.10 * KURZ * 1.2 - 1e-9) and float(NOV[s0]["dogus_list_price_usd"]) == soucet, (NOV[s0]["price_czk_placeholder"], soucet, ocek_usd))
sp = json.loads(NOV[s0]["product_specs_json"])
over("S7 specifikace obsahuje Kusovnik (valecky, profily, nohy, patky, H-ram) a puvodni parametry zustaly; bez nazvu dodavatele", "Kusovník" in sp and "Hliníkový váleček Ø50 délky 590 mm" in sp["Kusovník"] and "Dopravníkový profil 23x75" in sp["Kusovník"] and "Kovová noha 23x75" in sp["Kusovník"]
     and sp.get("Conveyor Length") == "3000" and sp.get("Stock Code") == s0 and "dogus" not in sp["Kusovník"].lower(), {k: v for k, v in sp.items() if k != "Kusovník"})
over("S8 karty zustaly NEAKTIVNI a bez navazani na Dogus (nocni prepocet je nezasahne)", all(r["active"] == 0 and r["dogus_url"] is None for r in NOV.values()), None)
vys2 = R.zapis_dopravniky(cur, recept, usd, KURZ, True, None, slug_for_name=product_slug.slug_for_name)
conn.commit()
cur.execute("SELECT sku, name, price_czk_placeholder FROM shop_products")
N2 = {r["sku"]: r for r in cur.fetchall()}
over("S9 opakovany zapis je idempotentni (stejne ceny a nazvy)", all(N2[s]["name"] == NOV[s]["name"] and N2[s]["price_czk_placeholder"] == NOV[s]["price_czk_placeholder"] for s in N2), None)
cur.execute("UPDATE shop_products SET active=1 WHERE sku=%s", (s0,))
vys3 = R.zapis_dopravniky(cur, recept, usd, KURZ, False, None)
over("S10 aktivni karta se preskoci (recept se nikdy nezapise na aktivni kartu)", any(s == s0 and "aktivni" in d for s, d in vys3["preskoceno"]), vys3["preskoceno"][:2])
over("S11 zaloha puvodnich radku predana (78)", len(zal) == 78 and all("name" in z for z in zal), len(zal))
# porovnani voleb: vzdy4 je levnejsi nez 3m_6m u 6m dopravniku
rA, sA = R.kusovnik("16.10.01.051.1000.6000.0", recept, usd, {"nohy": "3m_6m"})
rB, sB = R.kusovnik("16.10.01.051.1000.6000.0", recept, usd, {"nohy": "vzdy4"})
over("S12 volby receptu funguji (6m dopravnik: 6 noh dráž než 4 nohy)", sA > sB and sum(x["mnozstvi"] for x in rA if "noha" in x["nazev"].lower()) == 6, (sA, sB))
conn.rollback()
po = stav()
over("Z ostre karty dopravniku (kat. 324) beze zmeny (pocet, soucet cen, nazvy)", po == pred, (pred, po))
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
