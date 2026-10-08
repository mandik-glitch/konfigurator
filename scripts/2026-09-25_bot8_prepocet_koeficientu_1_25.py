"""Prepocet cen sestav (vetev 1, nase) na novy `app_settings.scene_price_
coefficient` = 1,25 (dnes zmeneno bot3/Robertem z 1,4).

Zadani (bot3 -> bot8, 2026-09-25), doslova shrnuto:
  - NEPRENASOBOVAT ulozene total_czk pomerem 1,25/1,4 (naivni prepocet) -
    riziko, ze se marze/rucni ceny prepocitaji spatne (uz jednou se stalo,
    ze marze byla zapocitana 2x, viz komentar u JOINT_RULE_VERSION v
    webapp/scene.html a api/product_assemblies.py:1160-1198).
  - Prepocitat ZNOVU z zivych katalogovych cen (stejny vzorec jako
    computeAssemblyBomAndPrice() v scene.html), na ulozene geometrii
    (data.parts), ne jen prenasobit vysledek.
  - Nejdriv DRY-RUN tabulka: sestava | cena dnes | cena po prepoctu |
    rozdil Kc | rozdil % | ma kartu | aktivni. Ostry zapis az po
    Robertove souhlasu (pres bot3).
  - Nesahat na aktivni/neaktivni (pravidlo 54) a na VD-% (Vandr, bot5).

OPRAVA (bot3, 2026-09-25, po overeni v kodu - PUVODNI verze tohohle
skriptu mela dve chyby, obe potvrzene primo v `api/products.py` a
`api/product_assemblies.py`, ne jen tvrzenim):
  1) `api/products.py` (verejne API e-shopu) cte cenu karty VYHRADNE
     z `shop_products.price_czk_placeholder` - `price_summary.total_czk`
     se tam necte nikde. Prepsat jen `price_summary` uvnitr JSONu sestavy
     tedy NA WEBU NIC NEZMENI.
  2) `price_czk_placeholder` NENI Robertovo rucni cislo, ktereho se
     nesmi sahnout - je to KOPIE master-varianty `price_summary.total_czk`
     z okamziku, kdy se master naposledy nastavoval (viz
     api/product_assemblies.py:1024-1058, `⭐ AUTO-SYNC ceny karty s
     novym zastupcem`). Prave proto se rozesla se scenou - a prave tady
     se ma oprava udelat: kdyz PREPOCITAM masterovu price_summary.total_czk,
     musim STEJNYM vyrazem (`round(total)`) prepsat i
     shop_products.price_czk_placeholder te karty, jinak zustane
     nesynchronizovana znovu.
  3) 55 radku v puvodni tabulce viselo jen na 12 RUZNYCH kartach (kazda
     karta ma prave 1 master, 0 vyjimek - overeno COUNT(DISTINCT
     shop_product_id)/SUM(is_master)) - soucet pres vsech 55 tedy
     kazdou kartu pocital az 5x. Spravny soucet cen 1. vetve je soucet
     PRES 12 KARET (masterovy total_czk po prepoctu), ne pres 55 sestav.
     Hlavni tabulka pro Roberta je proto 12 radku = 12 karet; rozpad po
     vsech 55 sestavach (variantach) je jen vedlejsi/informativni - jejich
     price_summary se pocita a zapisuje take (pouzivaji ho jina mista),
     ale NEURCUJE cenu karty.

VZOREC (overeno rucne na sestave #552 pred psanim skriptu - material_czk,
accessory_czk, packaging_czk, montaz_czk i total_czk sedi presne):
  Kazdy dil v `data.parts` (mimo razitka/kontrolni pomucky/karoserii -
  isStampPart/isKontrolniPart/isCarBodyPart, stejne role-prefixy jako
  webapp/js/scene-geometry-shared.js):
    - profil (cfg_dily radek s length_mm+cross_section_mm, viz
      isProfilePart): cena = zakladni_cena_1m(NOVY koef) * scale[1]
      (scale.y = pomer aktualni/referencni delky, referencni delka je u
      VSECH profilu pouzitych v techto sestavach presne 1000 mm - overeno
      primo v cfg_dily).
    - deska (shop_products.is_board_material=1): cena = zakladni_cena_m2
      (NOVY koef) * scale[0] * scale[1] (obe osy v rovine desky, tretí
      osa = tloustka, scale=1) - overeno na sestave #343 (68 Kc pri
      koef 1,4 presne sedi na scale [0.233, 0.2075]).
    - ostatni (prislusenstvi-produkt, ploche kusove ceny): cena =
      zakladni_cena_ks(NOVY koef) primo, scale se ignoruje (presne jako
      currentWeightPrice() v scene.html pro ne-profil/ne-desku).
  material_czk = round(soucet cen profilu+desek)
  accessory_czk = round(soucet cen ostatnich dilu) - `cfg_accessories`
  (samostatny poplatek za spoj) je PRAZDNA tabulka (0 aktivnich radku,
  overeno), takze accessory_czk = accessoryParts, zadna skryta slozka.
  cut_czk, profile_flat_fee_czk, joint_czk, joint_count - NEMENI SE
  koeficientem (cut_czk a joint_czk jsou nezavisle admin sazby * pocet,
  profile_flat_fee_czk take) - PREBIRAJI SE beze zmeny z ulozeneho
  price_summary (a zaroven se pouziji k REPRODUKCI stare ceny jako
  kontrole, ze rozklad na dily sedi).
  subtotal = material_czk + cut_czk + profile_flat_fee_czk + joint_czk + accessory_czk
  packaging_czk = round(subtotal * packaging_pct/100)
  total_czk = subtotal + packaging_czk
  montaz_czk = round(total_czk * montaz_pct/100)  (INFORMATIVNI, NENI v total_czk)

Bezpecnostni vzor stejny jako scripts/2026-09-11_robert_joint_count_
prepocet_269.py: zaloha pred zapisem, fresh-read-pred-zapisem, JSON_SET
jen na konkretni klice v `price_summary` (NIKDY cele `data` prepsat),
per-radek rowcount kontrola, over-z-noveho-spojeni po zapisu.

Spusteni NA SERVERU, v /opt/konfigurator:
    api/venv/bin/python3 scripts/2026-09-25_bot8_prepocet_koeficientu_1_25.py
        (dry-run, nic nezapisuje)
    api/venv/bin/python3 scripts/2026-09-25_bot8_prepocet_koeficientu_1_25.py --apply
        (ostry zapis - AZ PO Robertove souhlasu)
"""
import json
import os
import sys

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
from _env import get_conn

ZAL_DIR = os.path.join(REPO, "backups", "2026-09-25_prepocet_koeficientu")
ZAL = os.path.join(ZAL_DIR, "pred_zapisem.json")

STAMP_ROLE_PREFIX = "logo-ochrana"
KONTROLNI_ROLE_PREFIX = "kontrolni-pomucka"
CAR_BODY_ID_PREFIX = "car_body_"


def is_stamp(role):
    return str(role or "").startswith(STAMP_ROLE_PREFIX)


def is_kontrolni(role):
    return str(role or "").startswith(KONTROLNI_ROLE_PREFIX)


def is_car_body(part_id):
    return str(part_id or "").startswith(CAR_BODY_ID_PREFIX)


def nacti_katalog(cur, part_ids):
    """Zakladni (PRED koeficientem) ceny jen pro konkretni part_id, presne
    podle vzorce ve fetch_katalog_parts() (api/app.py)."""
    profile_ids = [p for p in part_ids if not str(p).startswith("product_") and not is_car_body(p)]
    product_ids = [int(p.replace("product_", "")) for p in part_ids if str(p).startswith("product_")]

    katalog = {}

    if profile_ids:
        fmt = ",".join(["%s"] * len(profile_ids))
        cur.execute(f"""
            SELECT d.id, d.dim_x_mm, d.dim_y_mm, d.dim_z_mm, d.price_czk_approx, d.price_per_cut_czk,
                   spm.shop_product_id, sp.price_czk_placeholder AS sp_price
            FROM cfg_dily d
            LEFT JOIN (
                SELECT cfg_dily_id, MIN(id) AS shop_product_id FROM shop_products
                WHERE active=1 AND is_archived=0 AND cfg_dily_id IS NOT NULL GROUP BY cfg_dily_id
            ) spm ON spm.cfg_dily_id = d.id
            LEFT JOIN shop_products sp ON sp.id = spm.shop_product_id
            WHERE d.id IN ({fmt})
        """, profile_ids)
        for r in cur.fetchall():
            dims = [r["dim_x_mm"], r["dim_y_mm"], r["dim_z_mm"]]
            is_profile = False
            if all(d is not None for d in dims):
                ds = sorted(float(x) for x in dims)
                is_profile = ds[0] is not None  # cross_section_mm[0] = ds[0], vzdy not-None kdyz vsechny 3 existuji
            if r["sp_price"] is not None:
                base = round(float(r["sp_price"]) / 3.0, 2)
            elif r["price_czk_approx"] is not None:
                base = float(r["price_czk_approx"])
            else:
                base = None
            katalog[r["id"]] = {
                "base_price": base,
                "is_profile": is_profile,
                "is_board": False,
                "price_per_cut_czk": float(r["price_per_cut_czk"]) if r.get("price_per_cut_czk") is not None else 0.0,
            }

    if product_ids:
        fmt = ",".join(["%s"] * len(product_ids))
        cur.execute(f"""
            SELECT id, price_czk_placeholder, unit, is_board_material,
                   board_sheet_width_mm, board_sheet_height_mm
            FROM shop_products WHERE id IN ({fmt})
        """, product_ids)
        for r in cur.fetchall():
            cena = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
            jednotka = (r.get("unit") or "").strip().lower() or None
            if r["is_board_material"] and cena is not None and jednotka != "m2":
                sirka, vyska = r.get("board_sheet_width_mm"), r.get("board_sheet_height_mm")
                plocha = (float(sirka) * float(vyska) / 1e6) if (sirka and vyska) else None
                if plocha and plocha > 0:
                    cena = round(cena / plocha, 4)
            katalog[f"product_{r['id']}"] = {
                "base_price": cena,
                "is_profile": False,
                "is_board": bool(r["is_board_material"]),
                "price_per_cut_czk": 0.0,
            }

    return katalog


def spocitej_material_accessory(parts, katalog, coef):
    """Vraci (material_czk, accessory_czk, total_cut, total_profiles,
    nenalezeno) pro dany koeficient - presna replika computeAssemblyBom
    AndPrice() pro slozky, ktere se s koeficientem meni."""
    total_material = 0.0
    total_accessory = 0.0
    total_cut = 0.0
    total_profiles = 0
    nenalezeno = []
    for p in parts:
        pid = p.get("part_id")
        role = p.get("role")
        if is_stamp(role) or is_kontrolni(role) or is_car_body(pid):
            continue
        kat = katalog.get(pid)
        if kat is None:
            nenalezeno.append(pid)
            continue
        base = kat["base_price"]
        scale = p.get("scale") or [1, 1, 1]
        if kat["is_board"]:
            # isMaterialPart(p) = isProfilePart(p) || p.is_board_material -> deska
            # patri do totalMaterial, NE do totalAccessoryParts (scene.html).
            total_cut += kat["price_per_cut_czk"]
            if base is None:
                continue
            area = float(scale[0]) * float(scale[1])
            total_material += base * coef * area
        elif kat["is_profile"]:
            total_profiles += 1
            total_cut += kat["price_per_cut_czk"]
            if base is None:
                continue
            factor = float(scale[1])
            total_material += base * coef * factor
        else:
            if base is None:
                continue
            total_accessory += base * coef
    return total_material, total_accessory, total_cut, total_profiles, nenalezeno


BOARD_NAME_MARKERS = ("MDF deska", "Plastová deska")


def bom_material_accessory_split(bom):
    """Kontrola KLASIFIKACE (profil/deska = material, ostatni = accessory),
    NEZAVISLA na dnesni katalogove cene - pocita se z `bom[].total`, ktere
    je zamrazene na cenu/koeficient PLATNY V DOBE ULOZENI sestavy. Slouzi
    jako sanity check vzorce, ne jako presna shoda s price_summary (bom je
    zaokrouhleny PO RADCICH/skupinach, price_summary az na konci souctu -
    drobny rozdil v radu desetin procenta je OCEKAVANY, ne chyba)."""
    material = sum(b["total"] for b in bom if b["name"].startswith("Profil") or b["name"].startswith(BOARD_NAME_MARKERS))
    accessory = sum(b["total"] for b in bom if not (b["name"].startswith("Profil") or b["name"].startswith(BOARD_NAME_MARKERS)))
    return material, accessory


def main():
    apply = "--apply" in sys.argv
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='scene_price_coefficient'")
    novy_koef = float(cur.fetchone()["setting_value"])
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='profile_flat_fee_czk'")
    profile_flat_fee_setting = float(cur.fetchone()["setting_value"])
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='packaging_pct'")
    packaging_pct = float(cur.fetchone()["setting_value"])
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='montaz_pct'")
    montaz_pct = float(cur.fetchone()["setting_value"])

    print(f"Novy koeficient (live app_settings): {novy_koef}")
    print(f"profile_flat_fee_czk={profile_flat_fee_setting}  packaging_pct={packaging_pct}  montaz_pct={montaz_pct}\n")

    cur.execute("""
        SELECT pa.id, pa.data, pa.is_master, pa.shop_product_id,
               sp.sku, sp.name AS sp_name, sp.active, sp.price_czk_placeholder
        FROM product_assemblies pa
        JOIN shop_products sp ON sp.id = pa.shop_product_id
        WHERE sp.sku NOT LIKE 'VD-%%'
        ORDER BY pa.id
    """)
    radky = cur.fetchall()
    print(f"nase (ne-Vandr) sestavy s napojenou kartou: {len(radky)}\n")

    # katalog jen pro pouzite part_id (napric vsemi sestavami)
    vsechny_ds = [json.loads(r["data"]) if isinstance(r["data"], str) else r["data"] for r in radky]
    part_ids = set()
    for d in vsechny_ds:
        for p in d.get("parts", []):
            part_ids.add(p.get("part_id"))
    katalog = nacti_katalog(cur, part_ids)

    vysledky = []
    chyby_validace = []

    for r, d in zip(radky, vsechny_ds):
        ps = d.get("price_summary")
        if not ps or ps.get("total_czk") is None:
            continue  # "56 z 57 ma cenu" - tenhle jeden preskocit, nahlasit zvlast
        stary_koef = float(ps.get("scene_price_coefficient_applied") or 1.0)
        parts = d.get("parts", [])

        # 1) KLASIFIKACE - validace rozkladu na material/accessory NEZAVISLE
        # na dnesni katalogove cene, primo z ulozeneho `bom` (zamrazeno na
        # cenu z doby ulozeni). Tolerance 2 % pokryva ocekavane zaokrouhleni
        # bom-po-radcich vs. price_summary-po-souctu (u #552 overeno rucne
        # na 0,08 %/0,5 %) - vetsi odchylka by znamenala spatnou klasifikaci
        # (napr. deska omylem v accessory), ne jen zaokrouhleni.
        mat_bom, acc_bom = bom_material_accessory_split(d.get("bom", []))
        mat_ok = ps["material_czk"] == 0 or abs(mat_bom / ps["material_czk"] - 1) < 0.02
        acc_ok = ps["accessory_czk"] == 0 or abs(acc_bom / ps["accessory_czk"] - 1) < 0.02
        repro_ok = mat_ok and acc_ok

        # informativni: kolik se zakladni cena v katalogu posunula od ulozeni
        # (tydenni Dogus/FIO prepocet, WORKFLOW.md bod 9) - NEZAVISLE na
        # koeficientu, muj prepocet z "zivych cen" tohle nutne dozene take.
        mat_old_repro, acc_old_repro, _, _, chybi_old = spocitej_material_accessory(parts, katalog, stary_koef)
        posun_material_pct = round((mat_old_repro / ps["material_czk"] - 1) * 100, 1) if ps["material_czk"] else None

        # 2) NOVA cena pri novem koeficientu (stejne dily, jen jina zakladni cena)
        mat_new, acc_new, cut_new, prof_new, chybi_new = spocitej_material_accessory(parts, katalog, novy_koef)
        material_new = round(mat_new)
        accessory_new = round(acc_new)
        cut_czk = ps["cut_czk"]  # nezavisle na koeficientu, prebirame beze zmeny
        profile_flat_fee_czk = ps["profile_flat_fee_czk"]  # dtto
        joint_czk = ps["joint_czk"]  # dtto
        subtotal_new = material_new + cut_czk + profile_flat_fee_czk + joint_czk + accessory_new
        packaging_new = round(subtotal_new * packaging_pct / 100)
        total_new = subtotal_new + packaging_new
        montaz_new = round(total_new * montaz_pct / 100)

        # zobrazena cena DNES - u masteru je to skutecna cena karty
        # (shop_products.price_czk_placeholder, kterou vidi zakaznik na webu,
        # viz api/products.py); u ostatnich variant jen jejich vlastni
        # price_summary.total_czk (necenu karty, jen informativni).
        cena_dnes = float(r["price_czk_placeholder"]) if r["is_master"] and r["price_czk_placeholder"] is not None else ps["total_czk"]

        if not repro_ok or chybi_old or chybi_new:
            chyby_validace.append({
                "id": r["id"], "sku": r["sku"], "chybi_old": chybi_old, "chybi_new": chybi_new,
                "material_bom_vs_summary": (mat_bom, ps["material_czk"]), "accessory_bom_vs_summary": (acc_bom, ps["accessory_czk"]),
            })

        vysledky.append({
            "id": r["id"], "sku": r["sku"], "nazev": r["sp_name"], "active": bool(r["active"]),
            "is_master": bool(r["is_master"]), "shop_product_id": r["shop_product_id"],
            "cena_dnes": round(cena_dnes), "cena_po_prepoctu": total_new,
            "rozdil_kc": total_new - round(cena_dnes),
            "rozdil_pct": round((total_new / cena_dnes - 1) * 100, 1) if cena_dnes else None,
            "repro_ok": repro_ok, "posun_material_pct": posun_material_pct,
            "material_new": material_new, "accessory_new": accessory_new,
            "packaging_new": packaging_new, "montaz_new": montaz_new,
        })

    # HLAVNI TABULKA PRO ROBERTA: 12 karet (masterova price_summary.total_czk
    # = cena, kterou uvidi zakaznik na webu - viz oprava v hlavicce souboru).
    karty = [v for v in vysledky if v["is_master"]]
    print("=" * 100)
    print("CENA KARET (1. vetev, ne-Vandr) - tohle uvidi zakaznik na webu")
    print("=" * 100)
    print(f"{'shop_product_id':>15} {'sku':<20} {'dnes':>8} {'po prep.':>9} {'rozdil Kc':>10} {'rozdil %':>9} {'akt':>4}")
    print("-" * 100)
    for v in karty:
        print(f"{v['shop_product_id']:>15} {v['sku']:<20} {v['cena_dnes']:>8} {v['cena_po_prepoctu']:>9} {v['rozdil_kc']:>+10} "
              f"{(str(v['rozdil_pct'])+'%') if v['rozdil_pct'] is not None else '-':>9} {'ano' if v['active'] else 'ne':>4}")
    soucet_karty_dnes = sum(v["cena_dnes"] for v in karty)
    soucet_karty_novy = sum(v["cena_po_prepoctu"] for v in karty)
    print("-" * 100)
    print(f"POCET karet: {len(karty)}")
    print(f"SOUCET cena dnes:        {soucet_karty_dnes:>10,} Kc".replace(",", " "))
    print(f"SOUCET cena po prepoctu: {soucet_karty_novy:>10,} Kc".replace(",", " "))
    print(f"ROZDIL:                  {soucet_karty_novy - soucet_karty_dnes:>+10,} Kc  "
          f"({(soucet_karty_novy/soucet_karty_dnes-1)*100:+.1f} %)".replace(",", " "))
    print("\nPOZNAMKA: kladny 'posun mat. od ulozeni' ve vedlejsi tabulce nize = zakladni cena profilu/desky")
    print("v katalogu od ulozeni sestavy vzrostla (tydenni Dogus/FIO prepocet, WORKFLOW.md bod 9), NEZAVISLE")
    print("na zmene koeficientu 1,4->1,25. Prepocet 'ze zivych cen' tohle zaroven dohani, proto je pokles")
    print("mensi nez naivnich -10,7 % (jen koeficient) - cast se ztrati v mezidobem podrazenem materialu.")

    if chyby_validace:
        print(f"\n!!! KLASIFIKACE: {len(chyby_validace)} sestav ma bom-material/accessory soucet mimo "
              f"2% toleranci od ulozeneho price_summary (nebo nenalezeny part_id) - MOZNA CHYBA VZORCE,"
              f" nedoporucuji zapisovat bez rucni kontroly:")
        for c in chyby_validace:
            print(f"   #{c['id']} {c['sku']}  chybi_old={c['chybi_old']}  chybi_new={c['chybi_new']}  "
                  f"material(bom/summary)={c['material_bom_vs_summary']}  accessory(bom/summary)={c['accessory_bom_vs_summary']}")
    else:
        print(f"\nKLASIFIKACE OK - vsech {len(vysledky)} sestav ma bom-material/accessory soucet do 2% od "
              f"ulozeneho price_summary (rozklad dilu na material/prislusenstvi sedi).")

    print(f"\n--- VEDLEJSI/INFORMATIVNI: rozpad po vsech {len(vysledky)} variantach (12 karet, kazda 1-15 variant) ---")
    print("(price_summary se prepocita a zapise u KAZDE varianty - pouziva se jinde - ale cenu karty")
    print(" urcuje vyhradne master, viz tabulka vyse. Soucet pres tuhle tabulku NIC neznamena, nescitat.)")
    print(f"{'id':>5} {'sku':<20} {'master':>6} {'total_czk dnes':>15} {'total_czk po prep.':>19} {'posun mat. od ulozeni':>22}")
    for v in vysledky:
        posun = f"{v['posun_material_pct']:+.1f}%" if v["posun_material_pct"] is not None else "-"
        print(f"{v['id']:>5} {v['sku']:<20} {'ano' if v['is_master'] else '-':>6} {v['cena_dnes']:>15} "
              f"{v['cena_po_prepoctu']:>19} {posun:>22}")

    preskoceno = len(radky) - len(vysledky)
    if preskoceno:
        print(f"\nPRESKOCENO (chybi price_summary/total_czk): {preskoceno} sestav")

    if not apply:
        print("\n(dry-run, nic nezapsano - spust s --apply az po Robertove/bot3 souhlasu)")
        return

    if chyby_validace:
        raise SystemExit(f"\nCHYBA: {len(chyby_validace)} sestav nesedi na validaci - ZASTAVUJI, nic nezapisuji. "
                          f"Over rucne pred --apply.")

    os.makedirs(ZAL_DIR, exist_ok=True)
    zaloha = []
    for r, d in zip(radky, vsechny_ds):
        if d.get("price_summary") and d["price_summary"].get("total_czk") is not None:
            zaloha.append({
                "id": r["id"], "shop_product_id": r["shop_product_id"], "is_master": bool(r["is_master"]),
                "price_summary": d["price_summary"],
                "shop_products_price_czk_placeholder": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None,
            })
    with open(ZAL, "w", encoding="utf-8") as f:
        json.dump(zaloha, f, ensure_ascii=False, indent=1, default=str)
    print(f"\nzaloha: {ZAL} ({len(zaloha)} zaznamu)")

    zapsano = 0
    preskoceno_stejne = 0
    karty_zapsano = 0
    for v in vysledky:
        # fresh-read pred zapisem (jina session mohla mezitim sestavu upravit)
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (v["id"],))
        fresh = cur.fetchone()
        fresh_data = json.loads(fresh["data"]) if isinstance(fresh["data"], str) else fresh["data"]
        fresh_ps = fresh_data.get("price_summary")
        if not fresh_ps or fresh_ps.get("total_czk") is None:
            print(f"   PRESKOCENO #{v['id']}: price_summary mezitim zmizel/zmenen zpusobem, ktery nejde overit")
            continue
        if fresh_ps.get("scene_price_coefficient_applied") == novy_koef:
            preskoceno_stejne += 1
            continue  # uz prepocitano (idempotence)
        subtotal_new = v["material_new"] + fresh_ps["cut_czk"] + fresh_ps["profile_flat_fee_czk"] + fresh_ps["joint_czk"] + v["accessory_new"]
        packaging_new = round(subtotal_new * packaging_pct / 100)
        total_new = subtotal_new + packaging_new
        montaz_new = round(total_new * montaz_pct / 100)
        cur.execute("""
            UPDATE product_assemblies SET data = JSON_SET(data,
                '$.price_summary.material_czk', %s,
                '$.price_summary.accessory_czk', %s,
                '$.price_summary.scene_price_coefficient_applied', %s,
                '$.price_summary.packaging_czk', %s,
                '$.price_summary.total_czk', %s,
                '$.price_summary.montaz_czk', %s
            ) WHERE id=%s
        """, (v["material_new"], v["accessory_new"], novy_koef, packaging_new, total_new, montaz_new, v["id"]))
        if cur.rowcount != 1:
            conn.rollback()
            raise SystemExit(f"CHYBA: UPDATE #{v['id']} rowcount={cur.rowcount} - ROLLBACK, nic nezapsano dal")
        zapsano += 1

        # ⭐ stejny mechanismus jako api/product_assemblies.py:1052-1058
        # (AUTO-SYNC ceny karty s masterem) - bez tohohle by prepocet zmenil
        # jen price_summary v datech sestavy a e-shop by dal dal ukazoval
        # starou cenu (api/products.py cte VYHRADNE shop_products.
        # price_czk_placeholder, viz oprava v hlavicce souboru).
        if v["is_master"] and v["shop_product_id"]:
            nova_cena_karty = round(total_new)
            cur.execute("UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                        (nova_cena_karty, v["shop_product_id"]))
            if cur.rowcount != 1:
                conn.rollback()
                raise SystemExit(f"CHYBA: UPDATE shop_products id={v['shop_product_id']} "
                                  f"rowcount={cur.rowcount} - ROLLBACK, nic nezapsano dal")
            karty_zapsano += 1
    conn.commit()
    print(f"\nzapsano: {zapsano} sestav (preskoceno jiz-prepoctenych: {preskoceno_stejne}), "
          f"z toho {karty_zapsano} karet (shop_products.price_czk_placeholder)")

    # over z NOVEHO spojeni
    conn2 = get_conn()
    cur2 = conn2.cursor()
    soucet_over = 0
    chyby_over = 0
    for v in vysledky:
        cur2.execute("SELECT data FROM product_assemblies WHERE id=%s", (v["id"],))
        d2 = json.loads(cur2.fetchone()["data"])
        skutecny = d2["price_summary"]["total_czk"]
        if skutecny != v["cena_po_prepoctu"]:
            chyby_over += 1
            print(f"   NESEDI price_summary #{v['id']}: ocekavano {v['cena_po_prepoctu']}, v DB {skutecny}")
        if v["is_master"] and v["shop_product_id"]:
            cur2.execute("SELECT price_czk_placeholder FROM shop_products WHERE id=%s", (v["shop_product_id"],))
            karta_cena = float(cur2.fetchone()["price_czk_placeholder"])
            soucet_over += karta_cena
            if round(karta_cena) != v["cena_po_prepoctu"]:
                chyby_over += 1
                print(f"   NESEDI karta shop_product_id={v['shop_product_id']}: ocekavano {v['cena_po_prepoctu']}, "
                      f"v DB {karta_cena}")
    print(f"\nOvereno z noveho spojeni - soucet cen {len(karty)} karet v DB: {soucet_over:,.0f} Kc".replace(",", " "))
    if chyby_over:
        raise SystemExit(f"CHYBA: {chyby_over} nesedi na ocekavanou hodnotu")
    print("OK - vsechny prepocitane sestavy i ceny karet overeny z ciste DB")


if __name__ == "__main__":
    main()
