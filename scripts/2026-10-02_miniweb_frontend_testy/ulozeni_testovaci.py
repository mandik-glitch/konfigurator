"""Pomucky testu "Ulozit konfiguraci" pro mosty bridge_kosik.py a bridge_miniweb.py (bot16, 2026-10-05): podstrceni registru (ARES, RPO) a DNS (DoH, dig) a rizeni scenare z testu
(GET /__bridge/registry?ares=ok|404|down&rpo=ok|none|down&doh=ok|nx|unknown&dig=ok|unknown), vypis ulozenych radku (GET /__bridge/ulozeni). Nic se nevola ven, e-mail se neodesila."""
import re

REG = {"ares": "ok", "rpo": "ok", "doh": "ok", "dig": "ok"}
FIRMA = "TESTOVACÍ firma s.r.o."


def fake_http(url, timeout, headers=None):
    if "ares.gov.cz" in url:
        m = REG["ares"]
        return (200, {"obchodniJmeno": FIRMA, "dic": "CZ00000000", "sidlo": {"textovaAdresa": "Testovací 1, Praha"}}) if m == "ok" else ((404, {"kod": "NENALEZENO"}) if m == "404" else (None, None))
    if "statistics.sk" in url:
        m = REG["rpo"]
        ico = re.search(r"identifier=(\d+)", url).group(1)
        return (200, {"results": [{"identifiers": [{"value": ico}], "fullNames": [{"value": FIRMA, "validFrom": "2000-01-01"}]}]}) if m == "ok" else ((200, {"results": []}) if m == "none" else (None, None))
    if "cloudflare-dns.com" in url:
        m = REG["doh"]
        if m == "unknown":
            return None, None
        if m == "nx":
            return 200, {"Status": 3}
        return 200, {"Status": 0, "Answer": [{"type": 15, "data": "10 mx.example.cz."}]}
    raise AssertionError("neocekavane volani site: " + url)


def instal(U):
    U._http_json = fake_http
    U._mx_dig = lambda domain: "ok" if REG["dig"] == "ok" else "unknown"


def rizeni(path, q, sql):
    """-> (kod, obj) pro /__bridge/registry a /__bridge/ulozeni, jinak None."""
    if path == "/__bridge/registry":
        for k in REG:
            if k in q:
                REG[k] = q[k][0]
        return 200, dict(REG)
    if path == "/__bridge/ulozeni":
        rows = sql("SELECT id, karta_id, system_profilu, config_kod, ico, firma, email, phone, country, shop_host, crm_lead_id, selection_json, expires_at FROM stul_ulozene_konfigurace ORDER BY id")
        leads = sql("SELECT id, source, contact_email, contact_phone, company_name, estimated_value, subject FROM crm_leads ORDER BY id")
        msgs = sql("SELECT lead_id, body FROM crm_lead_messages ORDER BY id")
        return 200, {"saved": rows, "leads": leads, "messages": msgs}
    return None
