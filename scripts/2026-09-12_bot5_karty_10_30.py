#!/usr/bin/env python3
"""Nove skladove karty pro sestavy s koliznimi rezervami 10/30 mm.

Zadani (Robert pres bot3, 2026-09-12): nova generace sestav ma dostat
VLASTNI `shop_products` karty; stara karta 3942 se smi pouzit jen jako
KONTROLNI SEZNAM POLI - *"inspirujme se ve starych jen aby neco
nechybelo v novych, data neprebirat, musi se vsechno natahnout ze
sceny"*. Zadna hodnota se proto z 3942 nekopiruje.

Struktura schvalena bot3 (varianta A): JEDNA KARTA NA VOZIDLO, ne na
sestavu. Duvod je WORKFLOW.md pravidlo 26 ("karta se ma jmenovat po
vozidle", jedna karta nese vic sestav) a Robert 2026-09-11 pres bot8:
*"A/B/C prepinat DRUHYM posuvnikem na TEZE karte, ne samostatnymi
kartami."* Jedna karta na sestavu by ekvalizeru ve fazi 3 nenechala co
prepinat (`by-product/<id>` vraci `assemblies[]`).

Osy posuvniku se mezi kartami lisi a je to v poradku:
  * Doblo  - jedna verze (C), sedm provedeni horniho bloku (kod 0-6)
  * Jumpy  - tri verze (A/B/C = rozpis boxu), horni blok zatim jen "bez"

CO TENHLE SKRIPT ZAMERNE NEDELA
-------------------------------
`weight_g`, `length_mm`/`width_mm`/`height_mm` a `price_czk_placeholder`
zustavaji NULL. Nejsou to zapomenuta pole - jsou to prave ta pole, ktera
se podle zadani maji "natahnout ze sceny", a ta data dnes neexistuji:
vsech 14 sestav ma `bom = []` a `price_summary = NULL` (zapisovaci
skripty bot8 je tak nastavuji zamerne, viz WORKFLOW.md pravidlo 32).
Vyplnit je odhadem by bylo presne to "prebirani dat", ktere Robert
zakazal. Rozmery navic nesmi vzniknout z `position`/`scale` cisel -
pravidlo 10 zada realnou GLB geometrii (`THREE.Box3`). Doplni se, az
bot8 prepocita snimek ze sceny.

`is_master` se nemeni. U Dobla ho drzi sestava 343 (Robertova volba),
u Jumpy ho nema zadna - obe situace zustavaji, jak jsou.

AKTIVACE: nove karty vznikaji s `active=0`, stejne jako je zaklada
`product_assemblies_create()` ("navrh e-shopove polozky - neaktivni, bez
ceny, admin dodela zbytek"). Neni to opatrnost navic, ma to konkretni
ucinek: `api/car_storefronts.py` pousti sestavu na verejny storefront,
dokud ji nezastavi neaktivni/archivovana karta - a Doblo L1H1 (model 7)
JE pokryte dvema zivymi storefronty (11 `fiat-doblo`, 14
`fiat-doblo-vestavby`). Karta s `active=0` tedy 341-347 ze storefrontu
stahne; dnes tam jdou ven pres aktivni 3942.

Skript dela CTYRI veci, vsechny v jedne transakci:
  1. archivuje starou kartu 3942 (a uvolni jeji slug nastupkyni),
  2. zaklada tri nove karty,
  3. prepojuje na ne sestavy,
  4. doplnuje chybejici `car_model_id` u 342 (viz DOPLNIT_CAR_MODEL nize).

Idempotence (WORKFLOW.md pravidlo 28): karta se hleda podle SKU. Druhy
beh uz zalozenou kartu nezaklada znovu, jen dorovna vazby sestav.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-12_bot5_karty_10_30.py
    api/venv/bin/python3 scripts/2026-09-12_bot5_karty_10_30.py --apply
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

STARA_KARTA_ID = 3942
ESHOP_KATEGORIE_ID = 247  # "Regaly do auta"
DOSTUPNOST = "3 - 5 týdnů"

# Slug, ktery dnes drzi 3942. Karta se archivuje a jeji nastupkyne je pro
# TOTEZ vozidlo, takze slug prechazi na ni - jinak by zavedena adresa
# skoncila na 404 a nastupkyne dostala `...-2`. SKU se NEPREJMENOVAVA
# (bot3: "na 3942.sku nesahej"), jen slug.
SLUG_DOBLO = "regal-na-euroboxy-fiat-doblo-l1h1-do-2022"
SLUG_ARCHIV_3942 = "regal-na-euroboxy-fiat-doblo-l1h1-do-2022-archiv-rezervy-2-20"

KARTY = [
    {
        "klic": "doblo",
        "sku": "K-075-EB-30-1030",
        "name": "Regál na euroboxy – Fiat Doblò L1H1 (do 2022)",
        "slug": SLUG_DOBLO,
        "sestavy": [341, 342, 343, 344, 345, 346, 347],
        "short_description": (
            "Hliníkový regál na euroboxy na míru pro Fiat Doblò L1H1 (do 2022), "
            "profil 30×30 mm, osm boxů ve dvou výškových pásmech."
        ),
        "description": (
            "Hliníkový regálový systém do nákladového prostoru Fiat Doblò L1H1 "
            "(do 2022), postavený z profilů 30×30 mm. Základní skladba nese osm "
            "euroboxů ve dvou výškových pásmech – 3× box výšky 220 mm, 3× 170 mm "
            "a 2× 120 mm.\n\n"
            "Tohle je jedno z provedení, ne jediná možnost. Sestavu postavíme "
            "přesně podle vašich kufrů a vercajku, na milimetr – patro jde "
            "posunout, přidat i úplně vynechat.\n\n"
            "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
            "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
            "požadavky na homologaci.\n\n"
            "Nad boxy si vyberete z několika provedení horního bloku pro delší "
            "předměty – od samotného rámu po plnou výplň s policí. Výšku sestavy "
            "omezuje výška zadního nakládacího otvoru (1250 mm); regál se nakládá "
            "zadními dveřmi a musí jimi projít."
        ),
        "meta_title": "Regál na euroboxy do Fiat Doblò L1H1 | na míru",
        "meta_description": (
            "Hliníkový regál na euroboxy do Fiat Doblò L1H1 (do 2022). Osm boxů "
            "ve dvou pásmech, profil 30×30 mm, několik provedení horního bloku. "
            "Stavíme na míru na milimetr."
        ),
    },
    {
        "klic": "jumpy_l2",
        "sku": "K-118-EB-1030",
        "name": "Regál na euroboxy – Citroën Jumpy Crew Cab L2 (od 2016)",
        "slug": "regal-na-euroboxy-citroen-jumpy-crew-cab-l2-od-2016",
        "sestavy": [348, 353, 354],
        "short_description": (
            "Hliníkový regál na euroboxy na míru pro Citroën Jumpy Crew Cab L2 "
            "(od 2016), na výběr tři skladby boxů."
        ),
        "description": (
            "Hliníkový regálový systém do nákladového prostoru Citroën Jumpy "
            "Crew Cab L2 (od 2016). Na výběr jsou tři skladby euroboxů: 2× box "
            "výšky 170 mm a 4× 120 mm; osm boxů výšky 120 mm; nebo 2× 220 mm, "
            "2× 170 mm a 2× 120 mm.\n\n"
            "Rozměry nejsou dané. Každý díl jde posunout, zvětšit nebo vynechat "
            "na milimetr přesně tak, aby sestava seděla na vaše kufry a nářadí.\n\n"
            "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
            "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
            "požadavky na homologaci.\n\n"
            "Výšku sestavy omezuje výška zadního nakládacího otvoru (1220 mm) – "
            "regál se do auta nakládá zadními dveřmi a musí jimi projít."
        ),
        "meta_title": "Regál na euroboxy do Citroën Jumpy Crew Cab L2",
        "meta_description": (
            "Hliníkový regál na euroboxy do Citroën Jumpy Crew Cab L2 (od 2016). "
            "Tři skladby boxů na výběr. Stavíme na míru na milimetr podle toho, "
            "co v autě vozíte."
        ),
    },
    {
        "klic": "jumpy_l3",
        "sku": "K-119-EB-1030",
        "name": "Regál na euroboxy – Citroën Jumpy Crew Cab L3 (od 2016)",
        "slug": "regal-na-euroboxy-citroen-jumpy-crew-cab-l3-od-2016",
        "sestavy": [349, 350, 351],
        "short_description": (
            "Hliníkový regál na euroboxy na míru pro Citroën Jumpy Crew Cab L3 "
            "(od 2016), na výběr tři skladby boxů."
        ),
        "description": (
            "Hliníkový regálový systém do nákladového prostoru Citroën Jumpy "
            "Crew Cab L3 (od 2016). Delší karoserie proti verzi L2 unese hustší "
            "skladbu – na výběr je 3× box výšky 170 mm a 6× 120 mm, dvanáct boxů "
            "výšky 120 mm, nebo 3× 220 mm, 3× 170 mm a 3× 120 mm.\n\n"
            "Cokoli v sestavě jde upravit, změnit, předělat nebo přestavět – na "
            "míru, na milimetr, podle toho, co v autě opravdu vozíte, podle "
            "vašich kufrů a vercajku.\n\n"
            "Konstrukce se kotví do zpevněných částí karoserie (bočnice a "
            "podlaha). Montáž zahrnuje vrtání do těchto částí, v souladu s "
            "požadavky na homologaci.\n\n"
            "Výšku sestavy omezuje výška zadního nakládacího otvoru (1220 mm) – "
            "regál musí zadními dveřmi projít dovnitř."
        ),
        "meta_title": "Regál na euroboxy do Citroën Jumpy Crew Cab L3",
        "meta_description": (
            "Hliníkový regál na euroboxy do Citroën Jumpy Crew Cab L3 (od 2016). "
            "Tři skladby boxů, až dvanáct pozic. Stavíme na míru na milimetr "
            "podle vašeho nářadí."
        ),
    },
]

# Sestava 340 tady ZAMERNE NENI. Bot3 si vyzadal overeni, jestli je to
# legitimni konfigurace, nebo duplicita 346 - zmereno: jejich 110 realnych
# dilu je bit-shodnych (part_id, role, position, quaternion, scale) a 340
# ma navic 10 dilu s roli `kontrolni-pomucka-kota-*` (kotovaci cary a
# sipky k podbehu). Je to MERICI KOPIE 346, ne prodejni varianta.
VYNECHANE = {340: "merici kopie 346 (+10 dilu kontrolni-pomucka-kota-*)"}

# Sestava 342 jako jedina ze sedmi doblovskych nema `car_model_id`, i kdyz
# je to tataz serie, tataz karoserie K-075 a tataz karta. Dusledek: byla by
# to jedina varianta karty, ktera se nedostane na storefront, zatimco
# sourozenci ano.
#
# WORKFLOW.md pravidlo 25 varuje, ze doplneni `car_model_id` ma publikacni
# vedlejsi ucinek a nema probehnout drive, nez je vynucene pravidlo 24.
# Tady ta obava neplati ze dvou duvodu a oba se daji overit, ne jen tvrdit:
#   1. 342 uz JE schvalena (`technicky_ok=1`) - pravidlo 25 chrani pred
#      unikem NESCHVALENE sestavy, coz tohle neni.
#   2. Karta, na ktere 342 visi, vznika s `active=0`, a od opravy bot3
#      (`ae8068b2`) `api/car_storefronts.py` skryva i sestavu bez karty.
#      Obe cesty ven jsou tedy zavrene nezavisle na `car_model_id`.
# Rozhodl bot3 jako koordinator; overeno zivym volanim endpointu po zapisu.
DOPLNIT_CAR_MODEL = {342: 7}


def nacti_stav(cur):
    placeholders = ",".join(["%s"] * len(KARTY))
    cur.execute(
        "SELECT id, sku, name, slug, active, is_archived FROM shop_products "
        f"WHERE sku IN ({placeholders})",
        tuple(k["sku"] for k in KARTY),
    )
    return {r["sku"]: r for r in cur.fetchall()}


def zaloz_kartu(cur, k):
    cur.execute(
        """INSERT INTO shop_products
             (sku, name, slug, unit, category_id, description, short_description,
              meta_title, meta_description, availability_text, stock_qty,
              price_visible_default, hover_show_price, hover_show_availability,
              active, is_archived)
           VALUES (%s,%s,%s,'ks',%s,%s,%s,%s,%s,%s,0,1,1,0,0,0)""",
        (k["sku"], k["name"], k["slug"], ESHOP_KATEGORIE_ID, k["description"],
         k["short_description"], k["meta_title"], k["meta_description"], DOSTUPNOST),
    )
    return cur.lastrowid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="skutecne zapsat (jinak dry-run)")
    args = ap.parse_args()
    rezim = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Nove skladove karty 10/30 mm — {rezim} ===\n")

    conn = get_conn()
    zmeny = []
    try:
        with conn.cursor() as cur:
            existujici = nacti_stav(cur)

            # Kontrola vstupu: sestavy musi existovat a byt schvalene.
            vsechny = [i for k in KARTY for i in k["sestavy"]]
            cur.execute(
                "SELECT id, name, technicky_ok, shop_product_id, car_model_id "
                "FROM product_assemblies WHERE id IN (%s)" % ",".join(["%s"] * len(vsechny)),
                tuple(vsechny),
            )
            sest = {r["id"]: r for r in cur.fetchall()}
            chybi = [i for i in vsechny if i not in sest]
            if chybi:
                print(f"CHYBA: sestavy neexistuji: {chybi}")
                return 1
            neschvalene = [i for i, r in sest.items() if not r["technicky_ok"]]
            if neschvalene:
                # WORKFLOW.md pravidlo 24 - do produktu smi jen zaskrtnuta sestava.
                print(f"CHYBA: sestavy bez technicky_ok: {neschvalene}")
                return 1

            # Archivace stare karty MUSI byt PRVNI krok: `slug` je UNIQUE a
            # 3942 drzi presne ten, ktery ma prevzit nastupkyne. Kdyby se
            # archivovalo az nakonec, INSERT nove karty by spadl na duplicitni
            # klic. Cely beh je jedna transakce, takze mezistav (archivovana
            # karta, sestavy jeste neprepojene) se ven nikdy nedostane.
            cur.execute(
                "SELECT id, sku, slug, active, is_archived FROM shop_products WHERE id=%s",
                (STARA_KARTA_ID,),
            )
            stara = cur.fetchone()
            if not stara:
                print(f"POZOR: karta {STARA_KARTA_ID} neexistuje, archivaci preskakuji\n")
            elif stara["is_archived"] and not stara["active"] and stara["slug"] == SLUG_ARCHIV_3942:
                print(f"[3942] uz je archivovana, preskakuji\n")
            else:
                print(f"[3942] ARCHIVOVAT: active {stara['active']}->0, "
                      f"is_archived {stara['is_archived']}->1")
                print(f"       slug {stara['slug']} -> {SLUG_ARCHIV_3942}")
                print(f"       sku ZUSTAVA {stara['sku']} (bot3: nesahat)\n")
                if args.apply:
                    cur.execute(
                        "UPDATE shop_products SET active=0, is_archived=1, slug=%s WHERE id=%s",
                        (SLUG_ARCHIV_3942, STARA_KARTA_ID),
                    )
                    cur.execute(
                        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                        "VALUES (NULL,'archive','shop_product',%s,%s)",
                        (STARA_KARTA_ID,
                         "bot5 skript 2026-09-12: nahrazena kartou pro sestavy 10/30 mm, "
                         "slug uvolnen nastupkyni"),
                    )
                zmeny.append(("archivace", STARA_KARTA_ID))

            for k in KARTY:
                stav = existujici.get(k["sku"])
                if stav:
                    karta_id = stav["id"]
                    print(f"[{k['klic']}] karta uz existuje: id={karta_id} sku={k['sku']} (nezakladam znovu)")
                else:
                    if args.apply:
                        karta_id = zaloz_kartu(cur, k)
                    else:
                        karta_id = "<nova>"
                    print(f"[{k['klic']}] ZALOZIT kartu sku={k['sku']} -> id={karta_id}")
                    print(f"           name: {k['name']}")
                    print(f"           slug: {k['slug']}")
                    zmeny.append(("karta", k["sku"]))

                for sid in k["sestavy"]:
                    stary = sest[sid]["shop_product_id"]
                    if stary == karta_id:
                        print(f"           sestava {sid}: uz navazana, preskakuji")
                        continue
                    print(f"           sestava {sid}: shop_product_id {stary} -> {karta_id}")
                    if args.apply:
                        cur.execute(
                            "UPDATE product_assemblies SET shop_product_id=%s WHERE id=%s",
                            (karta_id, sid),
                        )
                    zmeny.append(("vazba", sid))

                if args.apply and not stav:
                    cur.execute(
                        "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                        "VALUES (NULL,'create','shop_product',%s,%s)",
                        (karta_id,
                         f"bot5 skript 2026-09-12: karta pro sestavy 10/30 mm, "
                         f"sestavy {k['sestavy']}"),
                    )

            # Dorovnani chybejiciho `car_model_id` - viz DOPLNIT_CAR_MODEL vyse.
            for sid, model_id in DOPLNIT_CAR_MODEL.items():
                cur.execute("SELECT car_model_id FROM product_assemblies WHERE id=%s", (sid,))
                r = cur.fetchone()
                if not r:
                    print(f"\n[{sid}] sestava neexistuje, preskakuji")
                elif r["car_model_id"] == model_id:
                    print(f"\n[{sid}] car_model_id uz je {model_id}, preskakuji")
                elif r["car_model_id"] is not None:
                    # Prepsat CIZI hodnotu by bylo neco jineho nez doplnit
                    # chybejici - to tenhle skript delat nema.
                    print(f"\n[{sid}] POZOR: car_model_id uz je {r['car_model_id']}, "
                          f"necham byt (cekal jsem NULL)")
                else:
                    print(f"\n[{sid}] DOPLNIT car_model_id: NULL -> {model_id}")
                    if args.apply:
                        cur.execute(
                            "UPDATE product_assemblies SET car_model_id=%s WHERE id=%s",
                            (model_id, sid),
                        )
                        cur.execute(
                            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) "
                            "VALUES (NULL,'update','product_assembly',%s,%s)",
                            (sid, f"bot5 skript 2026-09-12: doplnen car_model_id={model_id} "
                                  f"(jedina ze serie ho nemela)"),
                        )
                    zmeny.append(("car_model_id", sid))

        if args.apply:
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print(f"\nDRY-RUN: nic nezapsano. Zmen k provedeni: {len(zmeny)}")
    finally:
        conn.close()

    if VYNECHANE:
        print("\nZamerne vynechane sestavy:")
        for sid, duvod in VYNECHANE.items():
            print(f"  {sid}: {duvod}")

    # Overeni z NOVEHO spojeni (tokenova disciplina bod 8: chybejici vyjimka
    # neni dukaz, ze zapis probehl).
    if args.apply:
        print("\n=== OVERENI z noveho spojeni ===")
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                for k in KARTY:
                    cur.execute(
                        "SELECT id, name, slug, active, is_archived FROM shop_products WHERE sku=%s",
                        (k["sku"],),
                    )
                    r = cur.fetchone()
                    if not r:
                        print(f"  CHYBA: karta {k['sku']} nenalezena!")
                        continue
                    cur.execute(
                        "SELECT id FROM product_assemblies WHERE shop_product_id=%s ORDER BY id",
                        (r["id"],),
                    )
                    nav = [x["id"] for x in cur.fetchall()]
                    ok = nav == sorted(k["sestavy"])
                    print(f"  {k['sku']}: id={r['id']} active={r['active']} "
                          f"sestavy={nav} {'OK' if ok else 'NESEDI, cekal jsem ' + str(sorted(k['sestavy']))}")
                cur.execute(
                    "SELECT active, is_archived, slug, sku FROM shop_products WHERE id=%s",
                    (STARA_KARTA_ID,),
                )
                print(f"  3942: {cur.fetchone()}")
                cur.execute(
                    "SELECT COUNT(*) n FROM product_assemblies WHERE shop_product_id=%s",
                    (STARA_KARTA_ID,),
                )
                print(f"  3942 navazanych sestav: {cur.fetchone()['n']} (ceka se 0)")
                for sid, model_id in DOPLNIT_CAR_MODEL.items():
                    cur.execute("SELECT car_model_id FROM product_assemblies WHERE id=%s", (sid,))
                    mam = cur.fetchone()["car_model_id"]
                    print(f"  sestava {sid} car_model_id={mam} "
                          f"{'OK' if mam == model_id else 'NESEDI, cekal jsem ' + str(model_id)}")
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
