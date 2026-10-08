#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""Skutecne GET /api/admin/emails (kod z HEAD, SKUTECNA DB, jen cteni) - ma vratit sent_at u radku 197 / 201 / 203 (bot16, 2026-10-08; backend bot5, commit 49467408).
Robert (pres bot9): radek 201 "Danovy doklad k prijate platbe 26VDD00001" ukazoval jako cas odeslani cas ZARAZENI (28. 9. 0:42:08), odeslano bylo az po schvaleni (29. 9. 9:32:42).
Zapisuje JEN soubor s odpovedi (argument 1) pro nahled v admin.html; do DB se nezapisuje (jen GET). Spusteni:
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-08_emaily_cas_odeslani_testy/ostre_sent_at.py <vystup.json>"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "api")))
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402

vystup = sys.argv[1] if len(sys.argv) > 1 else None
c = appmod.app.test_client()
with c.session_transaction() as s:
    s["user_id"] = 1
r = c.get("/api/admin/emails?page=1&page_size=50")
data = r.get_json()
print("HTTP", r.status_code, "radku:", len(data.get("emails", [])), "klice:", sorted(data.get("emails", [{}])[0].keys()) if data.get("emails") else None)
chyby = 0
for e in data.get("emails", []):
    print(" id=%-4s %-9s %-7s zarazeno=%s odeslano=%s" % (e["id"], e["status"], e["trigger_type"], e["created_at"], e.get("sent_at")))
ocek = {197: "2026-08-24T10:04:06", 201: "2026-09-29T09:32:42", 203: "2026-09-29T10:06:57"}
for e in data.get("emails", []):
    if e["id"] in ocek:
        ok = e.get("sent_at") == ocek[e["id"]]
        chyby += 0 if ok else 1
        print(("OK   " if ok else "FAIL ") + "id %s: sent_at %r (ocekavano %r)" % (e["id"], e.get("sent_at"), ocek[e["id"]]))
for k in ocek:
    if not any(e["id"] == k for e in data.get("emails", [])):
        chyby += 1
        print("FAIL chybi radek", k)
r2 = c.get("/api/admin/system-emails?page=1&page_size=50")
d2 = r2.get_json()
print("system-emails HTTP", r2.status_code, "radku:", len(d2.get("emails", [])), "sent_at v klicich:", all("sent_at" in x for x in d2.get("emails", [])))
if vystup:
    with open(vystup, "w", encoding="utf-8") as f:
        json.dump({"emails": data, "system": d2}, f, ensure_ascii=False)
sys.exit(1 if chyby else 0)
