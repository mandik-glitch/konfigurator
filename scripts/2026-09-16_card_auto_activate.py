#!/usr/bin/env python3
"""Automat, ktery sam aktivuje kartu, jakmile ma dokonceny render
(bot5, 2026-09-16, Robert primo: "proc si neudelas script nebo jinou
automatiku, ktera detekuje hotove rendery cimz se vse aktivuje
autonomne").

Doplnuje konfigurator-render-auto-dispatch (bot4) z DRUHE strany -
tamten sam ZARADI pripravenou sestavu do renderovaci fronty, tenhle
sam AKTIVUJE kartu, jakmile render dobehne. Predtim tenhle posledni
krok delal clovek/bot rucne (a nekdy se na nej zapomnelo, viz
AGENTS_LOG 2026-09-16 - karty K-237/K-239 mely hotovy render, ale
zustaly nekolik hodin active=0, protoze nikdo bota nenatipnul).

Pravidlo zverejneni (PLAN_TVORBY_SESTAV.md, bot9/bot3 2026-09-15):
"preferuje se zverejnit prestoze nema karta kompletni data o vsech
variantach... ke zverejneni karty staci 1 kompletni varianta renderu"
- KOMPLETNI = cena (price_summary.total_czk) A dokonceny render
(product_turntable_frames.is_active=1) SOUCASNE na TE SAME sestave,
ne kazde zvlast na jine.

Nikdy neaktivuje kartu, ktera uz NEKDY byla aktivni (`activated_at`
IS NOT NULL) - i kdyz je prave ted active=0, mohlo jit o Robertovo
VLASTNI schvalne stazeni z prodeje, ne o cekani na render (viz
sql/2026-09-16_shop_products_activated_at.sql). Vypinac:
app_settings['card_auto_activate_povoleno'] = '0' (stejny vzor jako
render_auto_dispatch_povoleno).

Spousti konfigurator-card-auto-activate.timer, kazdych 15 minut.
Nic NEMAZE, jen UPDATE shop_products.active/activated_at - zadna
zmena kod_sestavy/napojeni sestav, to zustava vyhradne rucni
(technicky_ok je Robertovo vlastni rozhodnuti primo ve scene,
napojeni sestavy na kartu dela bot5 po jeho overeni - tenhle automat
se dotyka jen POSLEDNIHO kroku, kdyz uz je vsechno predtim hotove).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ma_kompletni_variantu(cur, karta_id):
    """True, kdyz ALESPON JEDNA sestava napojena na kartu ma soucasne
    (a) technicky_ok=1, (b) spocitanou cenu a (c) dokonceny render."""
    cur.execute(
        "SELECT id, data FROM product_assemblies WHERE shop_product_id=%s AND technicky_ok=1",
        (karta_id,),
    )
    sestavy = cur.fetchall()
    for r in sestavy:
        try:
            data = json.loads(r["data"] or "{}")
        except (TypeError, ValueError):
            data = {}
        ma_cenu = bool((data.get("price_summary") or {}).get("total_czk"))
        if not ma_cenu:
            continue
        cur.execute(
            "SELECT COUNT(*) AS n FROM product_turntable_frames WHERE assembly_id=%s AND is_active=1",
            (r["id"],),
        )
        if cur.fetchone()["n"] > 0:
            return True
    return False


def _log(zprava):
    print(zprava)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## card-auto-activate (automaticky, scripts/2026-09-16_card_auto_activate.py) — {ts}\n\n{zprava}\n"
    try:
        with open(os.path.join(REPO_ROOT, "AGENTS_LOG.md"), "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError as e:
        print(f"[card-auto-activate] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='card_auto_activate_povoleno'")
            row = cur.fetchone()
            if row and row["setting_value"] == "0":
                print("[card-auto-activate] vypnuto (app_settings.card_auto_activate_povoleno=0)")
                return 0

            cur.execute(
                "SELECT DISTINCT sp.id, sp.sku, sp.name FROM shop_products sp "
                "JOIN product_assemblies pa ON pa.shop_product_id = sp.id "
                "WHERE sp.active=0 AND sp.activated_at IS NULL AND pa.technicky_ok=1"
            )
            kandidati = cur.fetchall()
            if not kandidati:
                print("[card-auto-activate] 0 kandidatu, konec")
                return 0

            aktivovano = []
            for k in kandidati:
                if _ma_kompletni_variantu(cur, k["id"]):
                    cur.execute(
                        "UPDATE shop_products SET active=1, activated_at=NOW() WHERE id=%s",
                        (k["id"],),
                    )
                    aktivovano.append(k)
                    print(f"[card-auto-activate] AKTIVOVANO {k['id']} {k['sku']} - {k['name']}")
        conn.commit()
    finally:
        conn.close()

    if aktivovano:
        seznam = "\n".join(f"- {k['id']} `{k['sku']}` — {k['name']}" for k in aktivovano)
        _log(f"Aktivovano {len(aktivovano)} karet (dokoncen render + cena na alespon 1 schvalene variante):\n\n{seznam}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
