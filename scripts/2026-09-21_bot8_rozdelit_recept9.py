"""Rozdeleni receptu shape_geometry_methods.id=9 (horni-blok-pro-dlouhe-predmety,
v18, 44 897 znaku / 15 klicu) na mensi SAMOSTATNE recepty "dle vyznamu".

Robert 2026-09-21: "Recepty postupy musime rozdekat na mensi samostatne casti
dle vyznamu." Stejny vzor jako VLASTNOSTI_PROFILU.md -> 8 tematickych souboru:
puvodni radek zustava jako ROZCESTNIK, obsah se stehuje do novych receptu.

Duvod, proc zrovna ted (bot8 2026-09-21): prave v tomhle receptu se nasly TRI
rozpory, ktere vznikly jen tim, ze je to jeden rostouci blob - prah konzoly si
odporuje sam se sebou (algoritmus.9 vs kriticke_pasti.6 vs KOMPONENTY_EUROBOXY.md),
uzavreny seznam 6 provedeni uz neodpovida zivemu ciselniku horni_blok_varianty
(11 radku) a dve verze klice "vyskova pasma"/"varianty" leZi vedle sebe jako
platna i prekonana.

OBSAH SE NEPREPISUJE - klice se stehuji DOSLOVA (zachovava Robertem overene
zneni). Meni se jen: (a) vypousti se dva klice oznacene primo v textu jako
PREKONANE, (b) zastaraly uzavreny seznam variant nahrazen ukazatelem na zivy
ciselnik, (c) pripsana provenience a dva otevrene rozpory.

Spusteni: python3 scripts/2026-09-21_bot8_rozdelit_recept9.py [--apply]
Zaloha: backups/2026-09-21_recepty_pred_rozdelenim/shape_geometry_methods_full.json
"""
import sys, json, pymysql
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn

APPLY = "--apply" in sys.argv
PUVOD = ("Rozdeleno z shape_geometry_methods.id=9 v18 (verified_by=robert) - bot8, "
         "2026-09-21, na pokyn Roberta 'recepty postupy musime rozdelat na mensi "
         "samostatne casti dle vyznamu'. Zneni klicu je prevzato DOSLOVA, nebylo "
         "prepsano. verified_by zamerne NULL: obsah sice pochazi z Robertem overeneho "
         "receptu, ale rozdeleni samo Robert jeste nepotvrdil - nesmim si overeni "
         "nastavit sam (WORKFLOW.md pravidlo 44).")

# cilovy recept -> (nazev, popis, [(zdrojovy klic, cesta)])
# cesta: "top" = klic je na nejvyssi urovni, "alg" = uvnitr definition["algoritmus"]
PLAN = [
 ("horni-blok-kde-zacina",
  "KDE horni blok zacina a jak vysoka jsou jeho pasma. Povinna mezera 30mm nad "
  "nejvyssim euroboxem, min. 5mm nad nejvyssim uhelnikem, vyska pasma = T = 30mm, "
  "a kdy se misto noveho pasma recykluje uz existujici horni pricka nohy.",
  [("kdy_pouzit", "top"), ("2_vyskova_pasma", "alg"),
   ("10_reuse_stavajici_horni_pricky_jako_1_pasmo", "alg")]),

 ("horni-blok-nosna-kostra",
  "Nosna kostra bloku: ktere svislice ho nesou, T-styl segmentace podelniku "
  "(horni prubezne + zkraceni stredove nohy, spodni po segmentech) a pricky.",
  [("1_dva_svisle_sloupky_na_nohu", "alg"), ("3_T_styl_segmentace_HORNI_podelniky", "alg"),
   ("4_T_styl_segmentace_SPODNI_podelniky", "alg"), ("5_pricky", "alg")]),

 ("horni-blok-vyplne",
  "Vyplne bloku: MDF 8mm, zasun 7mm do drazky, dno o 1mm kratsi nez podelnik "
  "(2 zasuny misto 4), posuvna cela prvniho sloupce a minimalni svetla vyska kanalu.",
  [("6_vyplne_do_drazky", "alg"), ("posuvne_celo_sloupec0_04_2026_09_15", "top"),
   ("posuvne_celo_sloupec0_03_L3_2026_09_15", "top"),
   ("min_svetla_vyska_kanalu_04_2026_09_15", "top")]),

 ("horni-blok-hloubka-a-konzola",
  "Adaptivni hloubka bloku podle zuzeni karoserie (raycast, rezerva 20mm ke stene) "
  "a premostovaci konzola/bracket mezi puvodni nohou a posunutou zadni linii.",
  [("8_hloubka_adaptivni_na_zuzeni_karoserie", "alg"), ("9_konzola_kdy_je_potreba", "alg")]),

 ("horni-blok-volba-varianty",
  "Rozhodovaci postup, ktera varianta bloku se stavi (krok 1-4), tvrda podminka "
  "obsahu pro kod 0, past v nazvoslovi roli a pravidlo, ze kazda volba je prepinac "
  "generatoru, ne rucni zasah do jedne sestavy.",
  [("7_varianty_JEDEN_POSTUP", "alg"), ("generalizace_na_jine_auto", "top")]),

 ("horni-blok-ram-nad-uhelniky",
  "Varianty 05/06/07 - ram kotveny 5mm nad nejvyssim uhelnikem misto k vrcholu nohy "
  "(pro auta, kde 01-04 nesedi). 06 = bez zkracovani noh, 07 = dvirka misto cela.",
  [("varianta_05_ram_nad_uhelniky_2026_09_17", "top"),
   ("varianta_06_puvodni_sloupce_2026_09_17", "top")]),

 ("horni-blok-pasti-a-overeni",
  "Kriticke pasti zjistene pri pilotu (orientace profilu, detekce pasma, part_id vs "
  "GLB, zamerny zasun, kotveni polovicni vyplne, prah bracketu), stav overeni "
  "jednotlivych provedeni a hranice metody.",
  [("kriticke_pasti_zjistene_pri_pilotu", "top"), ("stav_overeni", "top"),
   ("rozsah_a_hranice", "top"), ("implementace", "top")]),
]

VYPUSTIT = ["2_vyskova_pasma_puvodni_znenie_v2", "7_varianty_puvodni_vycet_v6"]

def main():
    c = get_conn(); cur = c.cursor(pymysql.cursors.DictCursor)
    cur.execute("SELECT id,name,version,definition FROM shape_geometry_methods WHERE id=9")
    r = cur.fetchone()
    d = json.loads(r["definition"]) if isinstance(r["definition"], str) else r["definition"]
    alg = d.get("algoritmus", {})
    print(f"zdroj: #{r['id']} {r['name']} v{r['version']}, {len(json.dumps(d, ensure_ascii=False))} znaku\n")

    pouzite = set()
    nove = []
    for name, popis, klice in PLAN:
        nd = {"popis": popis, "rozcestnik": "shape_geometry_methods.id=9 (horni-blok-pro-dlouhe-predmety) - mapa cele rodiny receptu horniho bloku.", "puvod": PUVOD}
        chybi = []
        for k, kde in klice:
            src = alg if kde == "alg" else d
            if k not in src:
                chybi.append(f"{kde}:{k}"); continue
            nd[k] = src[k]
            pouzite.add((k, kde))
        if chybi:
            raise SystemExit(f"CHYBA: v id=9 chybi klice {chybi} pro recept {name} - nic nezapsano")
        nove.append((name, nd))

    # (b) zivy ciselnik misto zastaraleho uzavreneho seznamu
    for name, nd in nove:
        if name != "horni-blok-volba-varianty":
            continue
        vp = d.get("varianty_provedeni", {})
        nd["kod_0_tvrda_podminka"] = vp.get("kod_0")
        nd["past_v_nazvoslovi"] = vp.get("past_v_nazvoslovi")
        nd["stare_horni_bloky_neplati"] = (
            "Robert 2026-09-11: 'stare horni bloky neplati, vzorovy horni blok delame na "
            "Doblu C'. Prevzato z puvodniho klice varianty_provedeni.co_to_je. STAV "
            "K 2026-09-21: pravidlo se fakticky provedlo - vsech osm jmenovanych sestav "
            "(134/135/182/189/209/219/279/289) i vzorove 332-337 je z product_assemblies "
            "smazano, necitovat je jako zive.")
        nd["ciselnik_variant_ZDROJ_PRAVDY"] = (
            "ZIVY ciselnik je DB tabulka `horni_blok_varianty` (k 2026-09-21: 11 radku, "
            "kody 00-10), NE seznam v receptu. Puvodni klic varianty_provedeni.seznam "
            "(uzavreny seznam sesti provedeni, kody 1-6) byl pri rozdeleni VYPUSTEN, "
            "protoze uz neodpovidal skutecnosti: kody se 2026-09-14 preobsadily "
            "(scripts/2026-09-14_bot5_precislovani_horni_blok_01_04.py, mapovani "
            "2:01->09, 3:02->08, 4:03->10, 8:07->01, 5:04->02, 6:05->03, 7:06->04). "
            "DUSLEDEK PRO CTENI STARYCH ZAPISU: kazdy text starsi nez 2026-09-14, ktery "
            "mluvi o 'provedeni 06', mysli dnesni kod 04. Puvodni zneni seznamu je v "
            "backups/2026-09-21_recepty_pred_rozdelenim/shape_geometry_methods_full.json.")

    # (c) otevrene rozpory, at nezmizi pri stehovani
    for name, nd in nove:
        if name == "horni-blok-hloubka-a-konzola":
            nd["OTEVRENY_ROZPOR_prah_bracketu"] = (
                "NEVYRESENO k 2026-09-21. Tenhle recept (klic 9_konzola_kdy_je_potreba a "
                "kriticke_pasti.6) rika, ze bracket se smi stavet JEN KDYZ abs(posun) > T "
                "(30mm). KOMPONENTY_EUROBOXY.md:1802-1806 (novejsi, 2026-09-07) rika opak: "
                "prah opraven na 'posun != 0'. Neni to nahodny drift - DB past byla napsana "
                "jako vyslovna namitka proti prave te formulaci. Bracket-vetev je v OBOU "
                "verzich NEOVERENA na jakemkoli realnem aute (CI25, Doblo K-075 i Maxi K-078 "
                "do ni nespadly). Pred prvnim pouzitim rozhodnout, ne uhodnout.")
        if name == "horni-blok-kde-zacina":
            nd["OTEVRENY_ROZPOR_25mm_vs_30mm"] = (
                "shape_geometry_methods.id=13 (norma Doblo A/B) odkazuje v kroku 6 na "
                "'aktualne platne bezpecnostni pravidlo (2026-09-14: 25mm)', zatimco tady i "
                "v id=9 plati Robertovo 'mezera 30 milimetru povinna' (2026-09-06). Tyz "
                "recept id=13 navic oznacuje posun bloku kvuli 25mm mezere za SLEPY MEZIKROK, "
                "ktery byl cely vracen zpet. Plati 30mm; 25mm v id=13 je treba dotahnout.")
            nd["ZMENA_2026_09_21_generatory"] = (
                "Do 2026-09-21 generatory variant 05/06 (a tim i 07) pravidlo 30mm nad "
                "euroboxem NEVYNUCOVALY vubec - ram kotvily VYHRADNE k uhelnikum "
                "(yDol = nejvyssiUhelnik + 5). Zmereno nad celym katalogem: 46 sestav melo "
                "pasmo pod 30mm, z toho 31 ZAPORNOU mezeru (az -76mm = realny prunik do "
                "nejvyssiho euroboxu). Opraveno v scripts/2026-09-17_horni_blok_var05.js a "
                "_var06.js na yDol = max(nejvyssiUhelnik+5, nejvyssiBox+30).")

    print("=== NOVE RECEPTY ===")
    for name, nd in nove:
        print(f"  {name:<34} {len(json.dumps(nd, ensure_ascii=False)):>7} znaku, {len(nd)} klicu")

    zbyle = [k for k in d if k not in ("algoritmus",) and (k, "top") not in pouzite]
    zbyle_alg = [k for k in alg if (k, "alg") not in pouzite]
    print(f"\nzbyva na id=9 (top): {zbyle}")
    print(f"zbyva v algoritmu:   {zbyle_alg}")
    print(f"vypousti se jako PREKONANE: {VYPUSTIT}")

    rozcestnik = {
        "popis": ("ROZCESTNIK horniho regaloveho bloku. Do 2026-09-21 tohle byl jeden "
                  "rostouci recept (v18, 44 897 znaku, 15 klicu); na pokyn Roberta "
                  "('recepty postupy musime rozdelat na mensi samostatne casti dle vyznamu') "
                  "byl rozdelen tematicky. Tady uz obsah NENI - jen mapa, kam se ktera cast "
                  "prestehovala. Stejny vzor jako VLASTNOSTI_PROFILU.md -> 8 souboru."),
        "oficialni_nazev": d.get("popis", "")[:0] or "Horni regalovy blok (drive 'horni blok pro dlouhe predmety').",
        "kde_co_najdes": {n: p for n, p, _ in PLAN},
        "konkretni_geometrie_norma": ("shape_geometry_methods.id=13 'doblo-k075-ab-horni-blok-01-04' - "
                                      "OVERENA konkretni geometrie variant 01-04 pro Doblo K-075 A/B; "
                                      "Robert 2026-09-14: 'geometrie hornich bloku 01-04 jako maji Doblo "
                                      "A/B je nova platna norma pro horni bloky malych dodavek, pro "
                                      "skladovani dlouheho materialu'. Pro dalsi vozidlo teto kategorie "
                                      "zacinat tam, ne tady."),
        "dvirka": "shape_geometry_methods.id=12 'dvirka-40-20-do-horniho-bloku' (varianta 07).",
        "ciselnik_variant": "DB tabulka `horni_blok_varianty` (zdroj pravdy pro kody provedeni).",
        "detekce_ma_sestava_blok": ("Spolehlivy predikat je role zacinajici na 'podelnik' - podelnik se "
                                    "mimo horni blok nevyskytuje. NIKDY nedetekovat podle vyplni nebo "
                                    "podle roli obsahujicich 'horni' ('horni' v nazvu role znamena DRUHE "
                                    "PASMO, ne blok jako celek)."),
        "vypustene_zastarale_klice": ("Krome dvou PREKONANYCH klicu (viz nize) byly vypusteny i "
                                      "varianty_provedeni.seznam / .jak_cist / .co_to_je - uzavreny seznam "
                                      "sesti provedeni s kody 1-6, ktery uz neodpovida zivemu ciselniku "
                                      "horni_blok_varianty (11 radku, kody 00-10). Stale platna veta z "
                                      "co_to_je ('stare horni bloky neplati') je zachovana v receptu "
                                      "horni-blok-volba-varianty."),
        "vypustene_prekonane_klice": (f"Pri rozdeleni byly vypusteny klice {VYPUSTIT}, oba primo v textu "
                                      "oznacene jako PREKONANE. Puvodni zneni: backups/"
                                      "2026-09-21_recepty_pred_rozdelenim/shape_geometry_methods_full.json."),
        "puvod": PUVOD,
    }
    for k in zbyle:
        if k not in rozcestnik and k not in ("varianty_provedeni",):
            rozcestnik.setdefault("prevzato_z_v18", {})[k] = d[k]
    print(f"\nrozcestnik id=9: {len(json.dumps(rozcestnik, ensure_ascii=False))} znaku, {len(rozcestnik)} klicu")

    if not APPLY:
        print("\n(dry-run, nic nezapsano - spust s --apply)")
        return

    w = c.cursor()
    vlozeno = []
    for name, nd in nove:
        w.execute("SELECT id FROM shape_geometry_methods WHERE name=%s", (name,))
        if w.fetchone():
            raise SystemExit(f"CHYBA: recept {name} uz existuje - nic dalsiho nezapsano")
        w.execute("INSERT INTO shape_geometry_methods (name, version, definition, verified_by, created_by) "
                  "VALUES (%s, 1, %s, NULL, 'bot8')", (name, json.dumps(nd, ensure_ascii=False)))
        if w.rowcount != 1:
            raise SystemExit(f"CHYBA: insert {name} rowcount={w.rowcount}")
        vlozeno.append((w.lastrowid, name))
    w.execute("UPDATE shape_geometry_methods SET version=19, definition=%s WHERE id=9 AND version=18",
              (json.dumps(rozcestnik, ensure_ascii=False),))
    if w.rowcount != 1:
        raise SystemExit(f"CHYBA: update id=9 rowcount={w.rowcount} (ocekavano 1) - rollback")
    c.commit()
    print("\nZAPSANO:")
    for i, n in vlozeno:
        print(f"  #{i} {n}")
    print("  #9 prepsan na rozcestnik, v18 -> v19")

main()
