"""Recept #13 z konkretni sestavy na OBECNE pravidlo.

Robert 2026-09-21 (nad kartou v adminu): "Proc je konkretni sestava v navodu
v pravidle, pravidlo ma byt obecne."

Mel pravdu. #13 drzel ZMRAZENOU KOPII souradnic 70 dilu osmi konkretnich
sestav (369/370/382/379/383/380/384/385), ktere zaroven ZIJI v
product_assemblies - dva zdroje pravdy pro totez. Zmereno pred zasahem:
130 dilu se shoduje, 20 se lisi (jen zaokrouhleni 0,01mm, tedy jeste
nerozejite - ale drzet to dal by znamenalo cekat, az se rozejde doopravdy).
Overeno take, ze ta data NIC necte programove - je to ciste dokumentace.

Co zustava: obecne pravidlo (co je norma, pro jakou kategorii vozidel, jak
podle ni postupovat, ze A a B jsou geometricky totozne, pravidlo dorazove
desky). Co odchazi: 70 zmrazenych dilu -> nahrazeno ODKAZEM na zive sestavy.
Snapshot pro pripad potreby: backups/2026-09-21_recept13_pred_zobecnenim/.
"""
import sys, json, pymysql
sys.path.insert(0, '/opt/konfigurator/scripts')
from _env import get_conn

APPLY = "--apply" in sys.argv
c = get_conn(); cur = c.cursor(pymysql.cursors.DictCursor)
cur.execute("SELECT id,name,version,definition FROM shape_geometry_methods WHERE id=13")
r = cur.fetchone()
d = json.loads(r["definition"])

if APPLY:
    json.dump({"pred_zmenou": r["name"], "verze": r["version"], "definition": d},
              open("backups/2026-09-21_recept13_pred_zobecnenim/recept13_v2.json", "w"),
              ensure_ascii=False, indent=1)
    print("snapshot ulozen")

dilu_pryc = sum(len(v.get("dily") or []) for v in (d.get("varianty") or {}).values())

nove = {k: v for k, v in d.items() if k != "varianty"}
nove["popis"] = (
    "NORMA pro horni bloky MALYCH DODAVEK urcene ke skladovani dlouheho materialu "
    "(tyce, trubky, profily) - provedeni 01 az 04. Robert 2026-09-14: 'geometrie "
    "hornich bloku 01-04 jako maji Doblo A/B je nova platna norma pro horni bloky "
    "malych dodavek, pro skladovani dlouheho materialu.' Doblo K-075 A/B je "
    "REFERENCNI INSTANCE teto normy, ne jeji definice - konkretni souradnice se "
    "ctou ze zivych sestav, ne odsud.")
nove["referencni_sestavy"] = {
    "proc_tady_nejsou_souradnice": (
        "Robert 2026-09-21: 'proc je konkretni sestava v navodu v pravidle, pravidlo "
        "ma byt obecne'. Do teto verze recept obsahoval zmrazenou kopii " + str(dilu_pryc) +
        " dilu osmi konkretnich sestav, ktere zaroven ZIJI v product_assemblies - dva "
        "zdroje pravdy pro totez, ktere se musi driv nebo pozdeji rozejit. Zmereno pri "
        "odstraneni: 130 dilu se shodovalo, 20 se lisilo (zaokrouhleni 0,01mm). "
        "Souradnice ctej ze sestav nize; jejich snapshot k 2026-09-14 je v "
        "backups/2026-09-21_recept13_pred_zobecnenim/recept13_v2.json."),
    "kde_geometrii_vzit": (
        "product_assemblies.data.parts, role s prefixy podelnik- / pricka-spodni- / "
        "pricka-horni- / pricka-police- / vypln-. Horni blok je mezi A a B geometricky "
        "IDENTICKY (viz klic spolecne_pro_A_i_B), takze staci cist jednu stranu."),
    "sestavy": {var: (v.get("assembly_ids") or {}) for var, v in sorted((d.get("varianty") or {}).items())},
    "nazvy_provedeni": {var: v.get("nazev") for var, v in sorted((d.get("varianty") or {}).items())},
}

print(f"\nPUVODNI klice: {list(d.keys())}")
print(f"NOVE klice:    {list(nove.keys())}")
print(f"odchazi: varianty.*.dily = {dilu_pryc} zmrazenych dilu")
print(f"velikost: {len(json.dumps(d, ensure_ascii=False))} -> {len(json.dumps(nove, ensure_ascii=False))} znaku")

if not APPLY:
    print("\n(dry-run, nic nezapsano - spust s --apply)")
    sys.exit(0)

w = c.cursor()
w.execute("UPDATE shape_geometry_methods SET name=%s, version=%s, definition=%s, kategorie=%s, poradi=%s "
          "WHERE id=13 AND version=%s",
          ("horni-blok-norma-male-dodavky", r["version"] + 1,
           json.dumps(nove, ensure_ascii=False),
           "Horní blok/Co se staví – rozcestník a volba", 5, r["version"]))
assert w.rowcount == 1, w.rowcount
c.commit()

c2 = get_conn(); cur2 = c2.cursor(pymysql.cursors.DictCursor)
cur2.execute("SELECT id,name,version,kategorie,LENGTH(definition) dl FROM shape_geometry_methods WHERE id=13")
print("\novereno z noveho spojeni:", cur2.fetchone())
