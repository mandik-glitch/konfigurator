#!/usr/bin/env python3
"""Povysi `shape_geometry_methods.id=7` (uhelniky-na-spoje-nohy) na verzi 3.

CO SE MENI: pravidlo o koliznich uhelnicich. Verze 2 znela "kolizni uhelniky
DOLE V NOHACH smazat" - tedy dve podminky soucasne (prunik A misto na
sestave). Robert 2026-09-11 misto jako podminku zrusil, doslova:

    "Je jasne ze ruzne auta maji ruzne tvary takze pokud se vyskytne
     kolizni uhelnik tak nemusi mit stejnou pozici jako v doublu."

Verze 3 ma tedy kriterium CISTE GEOMETRICKE (prekryv hmoty) a navic meni
zpusob mereni: `Box3` prekryv uz neni verdikt, jen predfiltr.

Klic `kolizni_uhelniky_dole_v_nohach` se prejmenovava na `kolizni_uhelniky`
- stary nazev by cizimu ctenari tvrdil misto jako podminku i pote, co ji
Robert zrusil.

POJISTKY: --dry-run, zaloha puvodni definice do backups/ pred zapisem,
kontrola cerstvym spojenim po zapisu.
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, "/opt/konfigurator/scripts")
import _env  # noqa: E402
import pymysql  # noqa: E402

ZALOHA = "/opt/konfigurator/backups/2026-09-11_recept7_pred_v3.json"

NOVE_PRAVIDLO = (
    "⭐ PRAVIDLO v3 (Robert 2026-09-11): kriterium je PRUNIK HMOTY, NE POZICE. "
    "Doslova: „Je jasné že různé auta mají různé tvary takže pokud se vyskytne "
    "kolizní úhelník tak nemusí mít stejnou pozici jako v doublu.“\n\n"

    "ZMENA PROTI v2: verze 2 vyzadovala DVE podminky soucasne - prunik A "
    "soucasne 'dole v noze'. Robert misto jako podminku ZRUSIL. Kolize je "
    "kolize bez ohledu na to, kde na sestave sedi; jina karoserie ma jiny "
    "tvar, takze tataz vada sedi pokazde jinde a 'stejna pozice jako v Doblu' "
    "nemuze byt kriterium. Vyplyvalo to uz z mereni k v2 (zapsaneho v "
    "PRISLUSENSTVI_PRIPOJENI.md): 'dole' a 'jinde' byla tataz vada a pravidlo "
    "mazat jen kusy dole nemelo fyzikalni oporu - drzelo se jen proto, ze tak "
    "znelo zadani.\n\n"

    "VYSKA JAKO KRITERIUM NEFUNGUJE, a to je ZMERENE, ne nazor. Kalibrace na "
    "sestave 337 (stav pred 2026-09-10, backups/2026-09-10_pred_oznacenim_"
    "uhelniku.json): ponechane uhelniky byly na Y=31.5 (NIZ nez smazane) a "
    "jeden ponechany byl na Y=53.5, tedy ve STEJNE vysce jako oba smazane. "
    "Zadna vodorovna rovina ty dve skupiny neoddeluje.\n\n"

    "JAK SE KOLIZE MERI (v3): `Box3` prekryv je uz jen PREDFILTR, ne verdikt. "
    "Je to horni mez skutecneho pruniku (posun o nej obaly oddeli, takze "
    "oddeli i dily), takze co jim neprojde, kolidovat nemuze - ale co jim "
    "projde, kolidovat jeste nemusi. Duvod je past c.8 skillu `3d-scena-spoje`: "
    "u dilu s vnorovaci geometrii obal presah ma a hmota se neprekryva. Navic "
    "je obal osove zarovnany, takze u pootoceneho dilu nadhodnocuje. Verdikt "
    "dava scripts/2026-09-11_mesh_kolize_lib.js: prostor, kde se obaly "
    "prekryvaji, se navzorkuje a hleda se bod uvnitr OBOU skutecnych siti.\n\n"

    "VELIKOST KOLIZE SE HLASI DVEMA CISLY: `odsun` = nejmensi posun po svetove "
    "ose, po kterem se site prestanou prekryvat (odpoved na 'o kolik je "
    "zaboreny' i na 'slo by to spravit posunutim'), a `oblast` = rozmery "
    "spolecne hmoty. HLOUBKOU NENI nejmensi rozmer spolecne hmoty - u "
    "uhelniku, jehoz stena projde skrz profil, je roven TLOUSTCE PLECHU (6mm) "
    "a je stejny, at je zaboreny o 7mm nebo o 22mm. Hloubkou neni ani "
    "'nejhloubeji zanoreny vrchol' - dily sdileji roviny (flush dosed je ucel "
    "spoje), takze vrcholy zaboreneho dilu lezi presne NA stene toho druheho "
    "a vzdalenost od povrchu vyjde 0. Obe pasti drzi zavrene regresni test "
    "scripts/2026-09-11_test_mesh_kolize.cjs.\n\n"

    "CO SE S NALEZEM DELA: Robert 2026-09-11 „Napred mi je ukazat.“ Nalez se "
    "NEMAZE automaticky - sweep vyrabi vypis k posouzeni kus po kuse a "
    "rozhoduje se u kazdeho zvlast. Jedina vyjimka je skupina 24 kusu dole v "
    "nohach, kterou Robert odsouhlasil driv.\n\n"

    "DUSLEDEK PRO GENERATOR (beze zmeny od v2): metoda smi vyprodukovat "
    "uhelnik, ktery se pak zahodi. Neni to chyba metody a nema se 'opravovat' "
    "tak, aby uhelnik vznikl jinde - kontrola kolize patri az ZA generovani, "
    "jako filtr.\n\n"

    "PRVNI VYSKYT (historie v2): 2026-09-10 u provedeni 6/6 vzoru Dobla C. "
    "Robert nechal kolizni kusy oznacit ve scene cervene a rekl doslova: 'tak "
    "presne ty 2 cervene uhelniky smazat a je to'. Ty dva kusy slouzi dodnes "
    "jako kalibrace regresniho testu - ten musi ze sestavy 337 vybrat prave "
    "je, ani min, ani vic."
)

VYSLEDEK_SWEEPU = (
    "Sweep pres CELY katalog 2026-09-11 (scripts/2026-09-11_sweep_kolizni_uhelniky.cjs, "
    "nic nemaze). ROZSAH: 269 sestav, 263 s uhelniky, 5164 uhelniku, 472 185 porovnanych "
    "dvojic; predfiltrem obalek proslo 76 dvojic a sit potvrdila kolizi u vsech 76. "
    "VYSLEDEK: 60 koliznich uhelniku ve 22 sestavach, 16 ruznych vad; 16 kusu koliduje "
    "se dvema dily naraz.\n\n"

    "CO MERENI NA SITI ZMENILO: mnozinu nalezu ne, cisla zasadne. Presah obalek sel od "
    "5 do 22mm, skutecny odsun je u vsech 60 kusu mezi 4.96 a 5.95mm "
    "(obalka 5mm->odsun 4.96 u 6 kusu; 6mm->5.95 u 24; 7mm->5.27 u 4; 18mm->5.27 u 14; "
    "20mm->5.27 u 6; 22mm->5.27 u 6). Obalka nadhodnocovala podle toho, JAK DALEKO na "
    "profilu uhelnik sedi, ne podle toho, jak hluboko je zaboreny - u sestavy 116 sdili "
    "uhelnik s prickou tutez hranu v X, takze obalka hlasila 22mm a stacilo ho posunout "
    "o 5.27mm. Je to tedy JEDNA A TATAZ VADA posazena pokazde jinam, coz je nezavisle "
    "potvrzeni, ze pozice kriteriem byt nemuze.\n\n"

    "Past c.8 se v tomhle katalogu neprojevila (zadny presah obalky nebyl plany poplach) "
    "- obalka dala spravny VERDIKT a spatna CISLA. Neni to duvod se k ni vratit; ze se "
    "ta past umi projevit, drzi zavrene regresni test se zasouvaci geometrii.\n\n"

    "ROZDELENI: 24 kusu (sestavy 182, 189, 219, 289) koliduje vyhradne s dily STARYCH "
    "HORNICH BLOKU, ktere jsou na seznamu ke smazani - po tom uklidu zaniknou bez zasahu. "
    "Zbylych 36 kusu v 18 sestavach ceka na Robertovo posouzeni kus po kuse; z toho 30 "
    "'nema kam ustoupit' (zadny posun do 40mm kolizi neodstrani, aniz by uhelnik prisel "
    "o dosed) a 6 kusu u T6 by vyresil posun o 29mm po ose Z. Skupina 24 kusu dole v "
    "nohach, odsouhlasena bot8 jeste podle pravidla v2, je podmnozinou tech 30."
)


def main():
    dry = "--dry-run" in sys.argv
    env = _env.load_env()
    c = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT id, name, version, definition FROM shape_geometry_methods WHERE id=7")
            r = cur.fetchone()
    finally:
        c.close()
    if not r:
        print("CHYBA: recept id=7 neexistuje - NEZAPISUJI.", file=sys.stderr)
        return 1
    if r["name"] != "uhelniky-na-spoje-nohy":
        print(f"CHYBA: id=7 je '{r['name']}', ocekavano 'uhelniky-na-spoje-nohy' - NEZAPISUJI.", file=sys.stderr)
        return 1
    if int(r["version"]) != 2:
        print(f"CHYBA: ocekavana verze 2, v DB je {r['version']} - nekdo recept mezitim zmenil. NEZAPISUJI.",
              file=sys.stderr)
        return 1

    d = json.loads(r["definition"])
    stary_klic = "kolizni_uhelniky_dole_v_nohach"
    if stary_klic not in d:
        print(f"CHYBA: v definici chybi klic '{stary_klic}' - NEZAPISUJI.", file=sys.stderr)
        return 1

    novy = {}
    for k, v in d.items():
        if k == stary_klic:
            novy["kolizni_uhelniky"] = NOVE_PRAVIDLO
            if VYSLEDEK_SWEEPU:
                novy["kolizni_uhelniky_sweep_2026_09_11"] = VYSLEDEK_SWEEPU
        else:
            novy[k] = v

    print(f"recept id=7 '{r['name']}' verze {r['version']} -> 3")
    print(f"  klic '{stary_klic}' -> 'kolizni_uhelniky' ({len(NOVE_PRAVIDLO)} znaku)")
    if VYSLEDEK_SWEEPU:
        print(f"  + novy klic 'kolizni_uhelniky_sweep_2026_09_11' ({len(VYSLEDEK_SWEEPU)} znaku)")
    print(f"  ostatni klice beze zmeny: {', '.join(k for k in novy if not k.startswith('kolizni_'))}")
    if dry:
        print("\n--dry-run: nic se nezapisuje.")
        return 0

    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump({"vytvoreno": datetime.now().isoformat(), "duvod": "pred povysenim receptu 7 na v3",
                   "radek": {"id": r["id"], "name": r["name"], "version": r["version"],
                             "definition": r["definition"]}}, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    vel = os.path.getsize(ZALOHA)
    if vel < 1000:
        print(f"CHYBA: zaloha {ZALOHA} je podezrele mala ({vel} B) - NEZAPISUJI.", file=sys.stderr)
        return 1
    print(f"\nZaloha pred zapisem: {ZALOHA} ({vel} B)")

    c = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            cur.execute("UPDATE shape_geometry_methods SET version=3, definition=%s WHERE id=7 AND version=2",
                        (json.dumps(novy, ensure_ascii=False),))
            dotceno = cur.rowcount
        c.commit()
    finally:
        c.close()
    if dotceno != 1:
        print(f"CHYBA: UPDATE zmenil {dotceno} radku (ocekavan 1).", file=sys.stderr)
        return 1

    c = pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                        password=env["DB_PASSWORD"], database=env["DB_NAME"],
                        cursorclass=pymysql.cursors.DictCursor)
    try:
        with c.cursor() as cur:
            cur.execute("SELECT version, definition FROM shape_geometry_methods WHERE id=7")
            z = cur.fetchone()
    finally:
        c.close()
    zd = json.loads(z["definition"])
    ok = (int(z["version"]) == 3 and "kolizni_uhelniky" in zd
          and stary_klic not in zd and len(zd) >= len(d))
    print(f"\nKontrola cerstvym spojenim: verze={z['version']}, klicu={len(zd)}, "
          f"'kolizni_uhelniky' {'ANO' if 'kolizni_uhelniky' in zd else 'CHYBI'}, "
          f"stary klic {'PRYC' if stary_klic not in zd else 'PORAD TAM'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
