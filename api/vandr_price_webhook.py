"""Prijima webhook z vanDrawee admina (test.logiman.cz) pri ulozeni
ceny casti sestavy - SKUTECNE 1:1 napojeni ceny Vandr karet na
vandrawee_work (Robert primo, 2026-09-26: "kdyz se zmeni cena v db
musí se to změnit i na eshopu", odmitnul i "tlacitko/mezikrok").

Doplnuje scripts/2026-09-25_vandr_cena_sync.py (denni beh, zalozni sit
+ parovani novych karet) - OBA pouzivaji stejny vzorec z
scripts/_vandr_cena.py, nemuzou se rozejit v tom, co je "spravna cena".

Vola to vanDrawee (PHP/Laravel), viz StoredModelPart::boot() tam -
kdyz se ulozi zmena `stored_model_parts.price`, najde VSECHNY
`stored_models`, ktere na tu cast odkazuji (left/right/bulkhead_part_id),
a pro KAZDOU zavola tenhle endpoint s jejim uuid. Jedna cast muze byt
sdilena vice sestavami (napr. bulkhead), proto "jeden pozadavek = jedna
sestava", ne "jeden pozadavek = jedna cast".

Autentizace: sdilene tajemstvi (VANDR_WEBHOOK_SECRET v obou .env), stejny
vzor jako BOT_STEP_TOKEN v api/production_overview.py (hmac.compare_digest).

Vsechny 3 vysledne stavy (updated/unchanged/ignored) se logujou (bot3,
2026-09-26: "ignored" je OCEKAVANY stav pro jeste-neparovane UUID, ne
chyba/alarm - nesmi se to tak ani tvarit v logu) - POZOR, `app.logger.*`
se v tomhle gunicorn provozu NIKAM nezapisuje (zadny handler pripojeny,
overeno zive 2026-09-26), proto obycejny `print(..., file=sys.stderr)`,
stejna konvence jako api/qa_checks.py (jedine, co se zobrazi v
`journalctl -u konfigurator.service`).
"""
import hmac
import os
import sys

from flask import request, jsonify

from app import app, get_conn

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)
import _vandr_cena  # noqa: E402

VANDR_WEBHOOK_SECRET = os.environ.get("VANDR_WEBHOOK_SECRET", "")


@app.post("/api/vandr/price-webhook")
def vandr_price_webhook():
    if not VANDR_WEBHOOK_SECRET:
        return jsonify({"error": "VANDR_WEBHOOK_SECRET není na serveru nakonfigurovaný."}), 503
    if not hmac.compare_digest(request.headers.get("X-Vandr-Webhook-Secret") or "", VANDR_WEBHOOK_SECRET):
        return jsonify({"error": "Neplatný token."}), 401

    body = request.get_json(silent=True) or {}
    uuid_str = (body.get("uuid") or "").strip().lower()
    if len(uuid_str) != 36:
        return jsonify({"error": "Chybí nebo neplatné 'uuid' (očekáván dashed string, 36 znaků)."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sku, price_czk_placeholder FROM shop_products "
                "WHERE vandr_stored_model_uuid=%s",
                (uuid_str,),
            )
            row = cur.fetchone()
            if not row:
                # Nejde o tichou dieru - vanDrawee normalne vola i pro
                # sestavy, ktere u nas jeste nemaji kartu/parovani (novy
                # export, jeste nezpracovany watcherem). To je OCEKAVANY
                # stav, ne chyba - denni sync je doplni pri parovani.
                print(f"[vandr_price_webhook] uuid={uuid_str} ignorováno, bez párované karty "
                      f"(očekávané u nové/nespárované sestavy)", file=sys.stderr)
                return jsonify({"status": "ignored", "reason": "uuid nema u nas parovanou kartu"}), 200

            vconn = _vandr_cena.vandr_conn()
            try:
                with vconn.cursor() as vcur:
                    nova_cena = _vandr_cena.cena_pro_uuid(vcur, uuid_str)
            finally:
                vconn.close()
            if nova_cena is None:
                print(f"[vandr_price_webhook] POZOR: karta id={row['id']} sku={row['sku']} má "
                      f"vandr_stored_model_uuid={uuid_str}, ale ve vandrawee_work už neexistuje "
                      f"(osiřelá vazba?)", file=sys.stderr)
                return jsonify({"error": "uuid nenalezeno ve vandrawee_work (osirela vazba?)"}), 404

            nova_cena_kc = round(nova_cena)
            stara_cena = float(row["price_czk_placeholder"]) if row["price_czk_placeholder"] is not None else None
            if stara_cena is not None and round(stara_cena) == nova_cena_kc:
                conn.rollback()
                print(f"[vandr_price_webhook] id={row['id']} sku={row['sku']} beze změny ({nova_cena_kc} Kč)",
                      file=sys.stderr)
                return jsonify({"status": "unchanged", "id": row["id"], "sku": row["sku"], "price_czk_placeholder": nova_cena_kc}), 200

            cur.execute(
                "UPDATE shop_products SET price_czk_placeholder=%s WHERE id=%s",
                (nova_cena_kc, row["id"]),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return jsonify({"error": f"UPDATE zasáhl {cur.rowcount} řádků místo 1."}), 500
            conn.commit()
            print(f"[vandr_price_webhook] id={row['id']} sku={row['sku']} {stara_cena} -> {nova_cena_kc} Kč",
                  file=sys.stderr)
            return jsonify({
                "status": "updated", "id": row["id"], "sku": row["sku"],
                "old_price_czk": stara_cena, "new_price_czk": nova_cena_kc,
            }), 200
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
