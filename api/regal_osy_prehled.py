"""Přehledy > Typologie/umístění regálů - bot16, 2026-09-13.

Zadání Robert (přímo v chatu, relayováno přes bot9): admin má mít živě
čtený katalogový přehled DVOU nezávislých os, podle kterých se dnes
staví regálové sestavy - "systém/obsah" (`regal_typologie` - EB/UN/OS/
EV/UK) a "umístění" (`regal_umisteni` - RB/RP/DP/VZ/VB/VP). Reálný
produkt je kombinace jedné položky z každé osy (dnes rozpracováno jen
RB × EB, vzor Doblo C - viz `sql/2026-09-13_regal_umisteni.sql`).

STEJNÝ princip jako `Přehledy > Pravidla/Postupy` (bot9, pravidla.py):
ŽÁDNÁ kopie obsahu do vlastní tabulky - číselníky (`regal_typologie`/
`regal_umisteni`, vč. `nazev`/`popis`) i počty použití (`product_
assemblies.typologie_id`/`umisteni_id`, `verze`) se čtou živě při
každém requestu, ať panel neshnije jako statický dokument.

Druhá tabulka v panelu (rozpad `product_assemblies.verze`) je čistě
informativní - Robert 2026-09-13 upřesnil, že počet poloh NENÍ pevná
trojka napříč katalogem (malé dodávky 3-4 polohy, větší víc), tenhle
rozpad to má v adminu držet viditelné a aktuální bez dohadování.

Zámerně BEZ zápisu/editace odsud - úprava číselníků `regal_typologie`/
`regal_umisteni` (název/popis/pořadí) zůstává tam, kde dnes je (přímé
SQL migrace bot9/bot10 podle Robertova zadání v chatu), tenhle modul je
čistě READ-ONLY přehled.
"""
from flask import jsonify

from app import app, get_conn, require_permission


def _osa_radky(cur, tabulka, fk_sloupec, osa_key, osa_label):
    cur.execute(f"""
        SELECT kod, nazev, popis, aktivni,
          (SELECT COUNT(*) FROM product_assemblies pa WHERE pa.{fk_sloupec} = t.id) AS pocet_sestav
        FROM {tabulka} t
        ORDER BY sort_order
    """)
    return [
        {
            "osa": osa_key,
            "osa_label": osa_label,
            "kod": r["kod"],
            "nazev": r["nazev"],
            "popis": r["popis"],
            "aktivni": bool(r["aktivni"]),
            "pocet_sestav": r["pocet_sestav"],
        }
        for r in cur.fetchall()
    ]


@app.get("/api/admin/regal-typologie-prehled")
@require_permission("nastaveni", "zobrazit")
def admin_regal_typologie_prehled():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            osy = (
                _osa_radky(cur, "regal_typologie", "typologie_id", "systemobsah", "Systém/obsah")
                + _osa_radky(cur, "regal_umisteni", "umisteni_id", "umisteni", "Umístění")
            )
            cur.execute("""
                SELECT COALESCE(verze, '—') AS verze, COUNT(*) AS pocet
                FROM product_assemblies
                GROUP BY verze
                ORDER BY verze IS NULL, verze
            """)
            verze_rozpad = cur.fetchall()
            cur.execute("SELECT COUNT(*) AS n FROM product_assemblies")
            celkem_sestav = cur.fetchone()["n"]
    finally:
        conn.close()
    return jsonify({
        "osy": osy,
        "verze_rozpad": verze_rozpad,
        "celkem_sestav": celkem_sestav,
    })
