#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WORKFLOW.md pravidlo 52 (Robert: "nikdy nic se nesmi odkladat" +
na nalez o pravych stranach: "tak to je problem, udelej co je potreba").

Karty 4593 a 4903 (obe RP) uz MELY aktivni render (`is_active=1`)
pořízený PŘED tímhle patchem - tedy s globálním fallback azimutem 270°
(spravnym jen pro LEVE regaly), zatimco jejich SKUTECNY geometricky
predni azimut (scripts/2026-09-23_vandr_razitka_spocitat.py, Krok 3d)
je 90°. Prepocet razitek (2026-09-24) zapsal spravny
`vandr_predni_azimut_deg`, ale `vandr_razitka_json` samotny se
nezmenil (stejne pozice razitek), takze render-dispatch
(scripts/2026-09-23_vandr_render_auto_dispatch.py::kandidati(),
"aktualni_hash == vandr_render_razitka_otisk") by karty povazoval za
"uz spravne vyrenderovane" a PRESKOCIL je - presne tenhle mechanismus
uz jednou (bot4/bot3 2026-09-23, viz komentar u kandidati()) resil
STEJNY problem (aktivni snimek nesedici na aktualni razitka).

Tenhle skript NEVOLA render, jen NULLuje `vandr_render_razitka_otisk`
u techto 2 karet - to je zdokumentovany, existujici zpusob, jak
render-dispatchi rici "aktivni snimek uz nesedi, zpracuj znovu", ne
obchazeni "zadny manualni render dispatch" (feedback_no_manual_
render_dispatch_bot4.md) - render pak spusti VYHRADNE automat sam.
"""
import pymysql

ENV_PATH = "/opt/konfigurator/api/.env"
KARTY = (4593, 4903)


def _env():
    vals = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def main():
    e = _env()
    conn = pymysql.connect(host=e["DB_HOST"], port=int(e.get("DB_PORT", 3306)),
                            user=e["DB_USER"], password=e["DB_PASSWORD"],
                            database=e["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            for karta in KARTY:
                cur.execute("SELECT id, sku, umisteni_id, vandr_predni_azimut_deg, vandr_render_razitka_otisk "
                            "FROM shop_products WHERE id=%s", (karta,))
                pred = cur.fetchone()
                if not pred:
                    print("!! karta %s neexistuje, preskakuji" % karta)
                    continue
                cur.execute("UPDATE shop_products SET vandr_render_razitka_otisk=NULL WHERE id=%s", (karta,))
                cur.execute("SELECT vandr_render_razitka_otisk FROM shop_products WHERE id=%s", (karta,))
                po = cur.fetchone()
                assert po["vandr_render_razitka_otisk"] is None, "otisk se nevynuloval u karty %s" % karta
                print("karta %s (%s): pred=%s.. -> render_otisk NULL (azimut ted %s), render-dispatch ji "
                      "zpracuje znovu"
                      % (karta, pred["sku"], (pred["vandr_render_razitka_otisk"] or "")[:12],
                         pred["vandr_predni_azimut_deg"]))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
