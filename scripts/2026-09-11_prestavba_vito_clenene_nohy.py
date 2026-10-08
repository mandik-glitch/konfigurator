#!/usr/bin/env python3
"""Přestavba spodní části členěné nohy - 14 sestav (Mercedes Vito + T6, Robert 2026-09-11).

Robert doslova: "u techto sestav musis predelat geomterii spodni casto
clenene nohy uprostred. spodní příčku je potreba zvednout o 60mm, smazat
vsechny uhelniky a nahodit komplet uhelniky znovu."

Rozsah (14 sestav, ověřeno proti názvům - ne odhadnuto z ID):
  Mercedes Vito Extra Long K-290 (2014-) A, B, C
  Mercedes Vito K-291e (2014-) A, B, C, D
  Mercedes Vito K-293e (2014-) A
  T6 K-281 (2014-) A, B, C
  T6 K-282 (2014-) A, B, C
POZOR na past: K-293e je JINÉ vozidlo než K-291e (přípona "e" mění
karoserii, ne variantu) - jen A je v rozsahu, B/C (225/295) NE.
T6 puvodne dostal jine zadani ("predelej na 3 nohy") - Robert to opravil
na TENTYZ zasah jako Vito, ctvrta noha zustava beze zmeny.

=== CO JE "SPODNÍ PŘÍČKA" - ZMĚŘENO, NE ODHADNUTO ===
Role `pricka-uzavreni-vyrezu` - jediný díl v noze, jehož název doslova
znamená "příčka" (na rozdíl od `spojnice-dolni`, což je "spojnice").
Změřeno na reálné GLB geometrii (#79): sedí přesně na styku mezi krátkým
pahýlem (`sloupek-pred-podbehem`, Y=[1,42]) a začátkem vysokého zadního
sloupku (`zadni-svislice-nad-zarezem`, Y=[42,901]) - X rozpětí [-772.5,
-483.5] přemosťuje OBA boční sloupky (predni-svislice na -483.5,
zadni-svislice-nad-zarezem na -772.5..-802.5), oba sahající do plné výšky
nohy, takže posun čistě po Y neruší ŽÁDNÝ boční spoj (oba sloupky mají
dost výšky, aby příčka zůstala uvnitř jejich rozsahu i po posunu).

Naopak spodní pahýl (`sloupek-pred-podbehem`) se NEHÝBE - posunem příčky
vznikne mezi pahýlem a příčkou NOVÁ 60mm mezera. To NENÍ vada (žádný spoj
se nerozpojuje, mezera tam předtím nebyla proto, že by na sebe dosedaly
funkčně, ale protože "výřez" byl 0mm vysoký) - je to PŘESNĚ požadovaná
změna: výřez pro podběh je teď o 60mm vyšší.

DŮSLEDEK PRO KOLIZE (Robert to zmínil sám, potvrzeno měřením): kolizní
úhelník skupiny 1 (7 sestav Vito, `uhelnik-noha1` proniká do
`spojnice-dolni`) dosedá PRÁVĚ na `pricka-uzavreni-vyrezu` (viz
nalezy_mesh.json, pole "dosedy"). Po posunu příčky o 60mm nahoru se
regenerují úhelníky na NOVÉM místě - stejný joint, ale 60mm výš, mimo
dosah `spojnice-dolni`. Ověřeno v --dry-run níže mesh sweepem, ne
předpokládáno.

=== GENEROVÁNÍ ÚHELNÍKŮ - PŘESNÁ KOPIE PRODUKČNÍ LOGIKY ===
`isLegProfile`/seskupení podle Z/`applyUhelnikyToLeg`/kontrola NaN+velikost
+flush gap<1mm jsou DOSLOVNÁ KOPIE scripts/2026-09-05_add_uhelniky_all_legs.js
(skript použitý 2026-09-05 na celý katalog) - ne vlastní paralelní
implementace (VLASTNOSTI_PROFILU.md metodika bod 4: "otestuj PŘESNOU
KOPII výsledného produkčního kódu").

VYCHOZI STAV: NEDELA NIC. --dry-run vypise nahled a zapise ho do JSON.
--provest zapise do DB (jen az Robert/bot3 rekne).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402

os.environ.update(_env.load_env())
import app  # noqa: E402,F401 - driv nez product_assemblies (kruhovy import)
import product_assemblies  # noqa: E402
import kolize_priznak  # noqa: E402

ZALOHA = os.path.join(REPO, "backups", "2026-09-11_vito_clenena_noha_pred_zmenou.json")
ZVEDNUTI_MM = 60.0
TOLERANCE_MM = 0.6

# Odsouhlaseny rozsah + ocekavana pozice pricky PRED posunem (zapsano
# natvrdo z mereni, ne dopocitavano za behu - stejna disciplina jako u
# vsech predchozich mazacich/posouvacich skriptu v tomhle adresari).
#
# ROZSAH (bot3/Robert 2026-09-11): stejny zasah na 14 sestavach - 8x
# Mercedes Vito + 6x T6 (K-281 A/B/C, K-282 A/B/C). Puvodne zadano zvlast
# pro T6 jako "predelej na 3 nohy" - Robert to OPRAVIL: "U t6 jsem ti
# nezadaval predelavat celou geometrii regalu pouze spodek prostredni
# nohy cti poradne zadani." Ctvrta noha ZUSTAVA, meni se jen prostredni
# clenena noha - presne stejny zasah jako u Vita, zadna prestavba poctu
# noh ani zadny novy generator.
#
# T6 MA DVE role `pricka-uzavreni-vyrezu` na sestavu, ne jednu - druha
# (Y~16, Z~8) patri ZADNI noze u konce vozidla a NENI "uprostred", tou se
# nehybe. Vybrana je vzdy ta ve VYSSI Y poloze (~330-345mm), ktera odpovida
# jiz drive zmerene kolizni skupine "uprostred nohy, v pasmu luzka"
# (nalezy_mesh.json 2026-09-11, uhelnik-noha2 dosedajici prave na tento dil).
SEZNAM = {
    79:  ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    224: ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    294: ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    83:  ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    151: ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    152: ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    173: ("pricka-uzavreni-vyrezu", -628.0, 57.0, -1136.0),
    82:  ("pricka-uzavreni-vyrezu", -628.0, 324.0, -906.0),
    116: ("pricka-uzavreni-vyrezu", -608.0, 344.2, -679.8),
    250: ("pricka-uzavreni-vyrezu", -608.0, 344.2, -679.8),
    320: ("pricka-uzavreni-vyrezu", -608.0, 344.2, -679.8),
    117: ("pricka-uzavreni-vyrezu", -608.0, 331.7, -719.5),
    251: ("pricka-uzavreni-vyrezu", -608.0, 331.7, -719.5),
    321: ("pricka-uzavreni-vyrezu", -608.0, 331.7, -719.5),
}


def sedi(part, ocekavano):
    role, x, y, z = ocekavano
    if (part.get("role") or "") != role:
        return False
    p = part.get("position") or []
    return len(p) == 3 and all(abs(p[i] - v) <= TOLERANCE_MM for i, v in enumerate((x, y, z)))


def _spust_regeneraci(radky):
    """Pusti Node skript (posun prick + smazani/nahozeni uhelniku + overeni
    flush + kolizni sweep) nad danymi radky. Vraci parsovany JSON vysledek.
    Zadny zapis do DB - cisty vypocet nad daty predanymi v pameti."""
    vstup = vystup = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"radky": [{"id": r["id"], "name": r["name"],
                                   "data": r["data"] if isinstance(r["data"], str) else json.dumps(r["data"])}
                                  for r in radky],
                       "seznam": SEZNAM, "zvednuti": ZVEDNUTI_MM, "tolerance": TOLERANCE_MM},
                      f, ensure_ascii=False)
            vstup = f.name
        vystup = vstup + ".out.json"
        skript = os.path.join(REPO, "scripts", "2026-09-11_prestavba_vito_geometrie.cjs")
        p = subprocess.run(["node", skript, vstup, vystup], capture_output=True, text=True, cwd=REPO)
        sys.stderr.write(p.stderr)
        if p.returncode != 0:
            raise SystemExit(f"Node regenerace skoncila kodem {p.returncode} - NEPOKRACUJI.")
        with open(vystup, encoding="utf-8") as f:
            return json.load(f)
    finally:
        for c in (vstup, vystup):
            if c and os.path.exists(c):
                os.unlink(c)


def main():
    ap = argparse.ArgumentParser(description="Přestavba spodní části členěné nohy - 8 sestav Vito")
    ap.add_argument("--provest", action="store_true", help="ZAPSAT do DB (bez toho jen náhled)")
    a = ap.parse_args()
    ids = sorted(SEZNAM)

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, name, data FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            radky = cur.fetchall()
    finally:
        conn.close()
    if len(radky) != len(ids):
        print(f"CHYBA: očekával jsem {len(ids)} sestav, našel {len(radky)} - NEMĚNÍM NIC.", file=sys.stderr)
        return 1

    # Pre-kontrola shody (jestli se od meření něco nezměnilo) - i pro
    # --dry-run, ať náhled hlásí totéž jako ostrý běh by zjistil.
    problemy = []
    for r in radky:
        d = json.loads(r["data"]) if isinstance(r["data"], str) else r["data"]
        nalez = [p for p in d.get("parts", []) if sedi(p, SEZNAM[r["id"]])]
        if len(nalez) != 1:
            problemy.append(f"#{r['id']}: {SEZNAM[r['id']]} -> nalezeno {len(nalez)}x (očekáváno 1)")
    if problemy:
        print("CHYBA: odsouhlasený rozsah už neodpovídá datům - NEMĚNÍM NIC:", file=sys.stderr)
        for x in problemy:
            print("   " + x, file=sys.stderr)
        return 1

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {'ZAPIS' if a.provest else 'NAHLED'} - "
          f"zvednutí spodní příčky členěné nohy o {ZVEDNUTI_MM} mm + kompletní přegenerování úhelníků\n")
    vysledek = _spust_regeneraci(radky)

    if vysledek.get("chyba"):
        print("CHYBA při regeneraci - NEMĚNÍM NIC:", vysledek["chyba"], file=sys.stderr)
        return 1

    for s in vysledek["sestavy"]:
        print(f"#{s['id']} {s['name'][:56]}")
        print(f"   příčka:  Y {s['pricka_pred']:.1f} -> {s['pricka_po']:.1f}")
        print(f"   úhelníky: smazáno {s['uhelniku_smazano']}, nově vygenerováno {s['uhelniku_nove']}"
              f"  (nohou zpracováno {s['noh_zpracovano']}, selhání {s['noh_selhani']})")
        if s["noh_selhani"]:
            for f in s["selhani"][:5]:
                print(f"      SELHALO leg Z={f['z']}: {f['duvod']}")
        print(f"   flush kontrola: max odchylka od stěny rohu = {s['max_gap_mm']:.4f} mm"
              f"  ({'OK' if s['max_gap_mm'] < 1.0 else 'POZOR >= 1mm'})")
        print(f"   kolizních úhelníků PŘED: {s['kolizi_pred']}  PO: {s['kolizi_po']}"
              f"  ({'OK, zmizely' if s['kolizi_po'] == 0 else 'POZOR, zbývají'})")
        print()

    celkem_selhani = sum(s["noh_selhani"] for s in vysledek["sestavy"])
    celkem_kolizi_po = sum(s["kolizi_po"] for s in vysledek["sestavy"])
    print(f"CELKEM: {len(vysledek['sestavy'])} sestav, selhání regenerace: {celkem_selhani}, "
          f"kolizních úhelníků po přestavbě: {celkem_kolizi_po}")

    S = "/tmp/claude-0/-opt-mail-relay/49b0ff3c-ad34-4deb-9806-2bd03aa7bdf2/scratchpad"
    nahled_out = os.path.join(S, "vito_prestavba_nahled.json")
    os.makedirs(S, exist_ok=True)
    with open(nahled_out, "w", encoding="utf-8") as f:
        json.dump(vysledek, f, ensure_ascii=False, indent=1)
    print(f"\nnáhled -> {nahled_out}")

    if not a.provest:
        print("\n--dry-run (výchozí): nic se nezapisuje. Zápis provedeš přidáním --provest.")
        return 0

    if celkem_selhani or celkem_kolizi_po:
        print("\nCHYBA: regenerace má selhání nebo zbylé kolize - NEZAPISUJI.", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(ZALOHA), exist_ok=True)
    with open(ZALOHA, "w", encoding="utf-8") as f:
        json.dump({"vytvoreno": datetime.now().isoformat(),
                   "duvod": "Robert 2026-09-11: zvednuti spodni pricky clenene nohy o 60mm + "
                            "kompletni prehozeni uhelniku, 8 sestav Mercedes Vito",
                   "sestavy": [{"id": r["id"], "name": r["name"], "data": r["data"]} for r in radky]},
                  f, ensure_ascii=False, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    vel = os.path.getsize(ZALOHA)
    if vel < 1000:
        print(f"CHYBA: záloha {ZALOHA} je podezřele malá ({vel} B) - NEZAPISUJI.", file=sys.stderr)
        return 1
    print(f"\nZáloha před zápisem: {ZALOHA} ({vel} B)")

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            mapy = product_assemblies.nacti_mapy_znacek(cur)
            for s in vysledek["sestavy"]:
                cur.execute("UPDATE product_assemblies SET data=%s WHERE id=%s",
                            (json.dumps(s["data"], ensure_ascii=False), s["id"]))
                fid = product_assemblies.zrcadli_sestavu_na_disk(cur, s["id"], s["name"], s["data"], None, mapy=mapy)
                print(f"   #{s['id']}: zapsáno, zrcadlo file_id={fid}")
            v = kolize_priznak.prepocti(cur, ids)
            print(f"   příznak kolizí přepočten: {v}")
        conn.commit()
    finally:
        conn.close()

    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            fmt = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, kolize_pocet FROM product_assemblies WHERE id IN ({fmt}) ORDER BY id", ids)
            print("\nKontrola čerstvým spojením:")
            zbylo = 0
            for r in cur.fetchall():
                zbylo += r["kolize_pocet"] or 0
                print(f"  #{r['id']}: kolizních úhelníků {r['kolize_pocet']}")
    finally:
        conn.close()
    return 0 if zbylo == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
