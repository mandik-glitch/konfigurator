#!/opt/konfigurator/api/venv/bin/python
"""Skutecny cas odeslani e-mailu (sloupec sent_at v shop_emails a system_emails) - bot5, 2026-10-08 (pozadavek bot16 po Robertovi: schvaleni v dashboardu bylo az pozdeji nez created_at).
Vsechno nad DOCASNYMI kopiemi tabulek shop_emails / system_emails (stejne spojeni jako get_conn(), ostra data se nemeni), send_email je atrapa (nic se neposila), log_audit/current_user atrapy.
M1-M3 = migrace sql/2026-10-08_shop_emails_sent_at.sql na kopii BEZ sloupce sent_at a zpetne doplneni proti skutecnemu audit_log; K1-K10 = kod (send_and_log, approve, reject, serializace, filtr, system_emails).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_emaily_sent_at_testy/test_sent_at.py"""
import datetime
import importlib.util
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.dont_write_bytecode = True
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
import app as appmod  # noqa: E402
import emails  # noqa: E402
import system_emails  # noqa: E402
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)[:500]))


spec = importlib.util.spec_from_file_location("mig", os.path.join(REPO, "scripts", "2026-10-08_bot5_sent_at_migrace.py"))
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
cur = real.cursor()


# ---- M: migrace na kopii s ostrymi daty bez sent_at
for t in ("shop_emails", "system_emails"):
    cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
    cur.execute("INSERT INTO `_tpl_%s` SELECT * FROM `%s`" % (t, t))              # kopie ostrych radku (cteni)
    cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
    cur.execute("INSERT INTO `%s` SELECT * FROM `_tpl_%s`" % (t, t))
    cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='sent_at'", (t,))
    if cur.fetchone()["n"]:                                                          # ostra tabulka sloupec uz ma (migrace pustena): na kopii ho zahodime a otestujeme znovu
        cur.execute("ALTER TABLE `%s` DROP COLUMN sent_at" % t)
cur.execute("SELECT id FROM shop_emails WHERE id IN (197,201,203) ORDER BY id")
ma_data = [r["id"] for r in cur.fetchall()] == [197, 201, 203]
over("M0 kopie ostrych dat obsahuje radky 197/201/203", ma_data)
prik = mig._sql_prikazy()
over("M1 migrace ma 2 ALTER + 3 UPDATE", [q.split()[0] for q in prik] == ["ALTER", "ALTER", "UPDATE", "UPDATE", "UPDATE"], [q[:20] for q in prik])
for q in prik:
    cur.execute(q)
cur.execute("SELECT id, status, created_at, sent_at FROM shop_emails ORDER BY id")
se = {r["id"]: r for r in cur.fetchall()}
D = datetime.datetime
over("M2a #197 auto: cas schvaleni z audit_log 3556 = 2026-08-24 10:04:06", se[197]["sent_at"] == D(2026, 8, 24, 10, 4, 6), se[197])
over("M2b #201 auto: cas schvaleni z audit_log 6392 = 2026-09-29 09:32:42 (ne editace 6099 z 28. 9.)", se[201]["sent_at"] == D(2026, 9, 29, 9, 32, 42), se[201])
over("M2c #203 rucni: sent_at = created_at = 2026-09-29 10:06:57", se[203]["sent_at"] == D(2026, 9, 29, 10, 6, 57) == se[203]["created_at"], se[203])
cur.execute("SELECT id, status, sent_at FROM system_emails ORDER BY id")
sy = {r["id"]: r for r in cur.fetchall()}
over("M3a system #20 sent: 2026-09-28 00:59:39 (audit 6094)", sy[20]["sent_at"] == D(2026, 9, 28, 0, 59, 39), sy[20])
over("M3b system #22 sent: 2026-09-15 22:14:38 (audit 3903)", sy[22]["sent_at"] == D(2026, 9, 15, 22, 14, 38), sy[22])
over("M3c zamitnute system e-maily zustavaji NULL", all(r["sent_at"] is None for r in sy.values() if r["status"] != "sent"), [r for r in sy.values() if r["status"] != "sent" and r["sent_at"]])
pred = [(r["id"], r["sent_at"]) for r in se.values()]
for q in prik[2:]:
    cur.execute(q)
cur.execute("SELECT id, sent_at FROM shop_emails ORDER BY id")
over("M4 druhe spusteni doplneni nic nemeni (idempotence)", [(r["id"], r["sent_at"]) for r in cur.fetchall()] == sorted(pred))

# ---- K: kod nad kopiemi uz se sloupcem sent_at (z M ho tabulky maji)
cur.execute("DELETE FROM shop_emails")
cur.execute("DELETE FROM system_emails")
real.commit()
puvodni_send = emails.send_email
poslano = []
def ok_send(*a, **k): poslano.append(a[0])
def spatny_send(*a, **k): raise RuntimeError("smtp dole")
admin = {"id": 1, "name": "Test Admin", "email": "x@invalid.test", "active": 1}


def radek(i):
    cur.execute("SELECT * FROM shop_emails WHERE id=%s", (i,))
    return cur.fetchone()


def vloz_cekajici(stari_dni):
    cur.execute("INSERT INTO shop_emails (order_id, template_key, recipient_email, subject, body_text, status, trigger_type, created_at) "
                "VALUES (NULL, 'custom', 'a@invalid.test', 's', 'b', 'pending', 'auto', NOW() - INTERVAL %s DAY)", (stari_dni,))
    real.commit()
    return cur.lastrowid


def blizko_db(dt):
    cur.execute("SELECT TIMESTAMPDIFF(SECOND, %s, NOW()) AS s", (dt,))
    s = cur.fetchone()["s"]
    return s is not None and 0 <= s <= 5

emails.send_email = ok_send
log_id, st, err = emails.send_and_log(None, template_key="custom", recipient="a@invalid.test", subject="s", body="b", admin=admin)
r = radek(log_id)
over("K1 rucni odeslani: status sent, sent_at = ted", st == "sent" and r["status"] == "sent" and blizko_db(r["sent_at"]), r)
emails.send_email = spatny_send
log_id, st, err = emails.send_and_log(None, template_key="custom", recipient="a@invalid.test", subject="s", body="b", admin=admin)
r = radek(log_id)
over("K2 rucni selhani: failed, sent_at NULL", st == "failed" and r["sent_at"] is None, r)
emails.send_email = ok_send
log_id, st, err = emails.send_and_log(None, template_key="custom", recipient="a@invalid.test", subject="s", body="b", auto=True)
r = radek(log_id)
over("K3 automaticky e-mail: pending, sent_at NULL (cas zarazeni = created_at)", st == "pending" and r["sent_at"] is None and r["created_at"] is not None, r)
log_id, st, err = emails.send_and_log(None, template_key="custom", recipient="", subject="s", body="b", admin=admin)
over("K4 bez prijemce: failed, sent_at NULL", st == "failed" and radek(log_id)["sent_at"] is None)

i = vloz_cekajici(2)
row, st, err = emails.approve_pending_email(i, admin)
r = radek(i)
over("K5 schvaleni 2 dny stareho cekajiciho: sent_at = ted, created_at zustava stare", st == "sent" and blizko_db(r["sent_at"]) and (r["sent_at"] - r["created_at"]).days >= 1, r)
over("K5b e-mail skutecne ,,odesel`` pres atrapu", poslano[-1] == "a@invalid.test")
emails.send_email = spatny_send
i = vloz_cekajici(1)
row, st, err = emails.approve_pending_email(i, admin)
r = radek(i)
over("K6 schvaleni se selhanim SMTP: failed, sent_at NULL", st == "failed" and r["status"] == "failed" and r["sent_at"] is None, r)
i = vloz_cekajici(1)
row, st = emails.reject_pending_email(i, admin)
over("K7 zamitnuti: rejected, sent_at NULL", st == "rejected" and radek(i)["sent_at"] is None)

# serializace + filtr pres zabalenou routu (bez prihlaseni, bez zapisu auditu)
emails.send_email = ok_send
cur.execute("DELETE FROM shop_emails")
cur.execute("INSERT INTO shop_emails (order_id, template_key, recipient_email, subject, body_text, status, trigger_type, created_at, sent_at) "
            "VALUES (NULL,'custom','a@invalid.test','poslano pozdeji','b','sent','auto','2026-09-28 00:42:08','2026-09-29 09:32:42')")
poz_id = cur.lastrowid
cur.execute("INSERT INTO shop_emails (order_id, template_key, recipient_email, subject, body_text, status, trigger_type, created_at, sent_at) "
            "VALUES (NULL,'custom','b@invalid.test','ceka','b','pending','auto','2026-09-28 12:00:00',NULL)")
real.commit()
over("K8 serializace: sent_at jako ISO text, u pending None", emails._serialize_email(radek(poz_id))["sent_at"] == "2026-09-29T09:32:42"
     and emails._serialize_email(dict(radek(poz_id), sent_at=None))["sent_at"] is None)
fn = emails.admin_emails_overview.__wrapped__
def volej(qs):
    with appmod.app.test_request_context("/api/admin/emails?" + qs):
        resp = fn()
    resp = resp[0] if isinstance(resp, tuple) else resp
    return [e["subject"] for e in resp.get_json()["emails"]], resp.get_json()
predmety, js = volej("")
over("K9a prehled vraci pole sent_at u obou radku", all("sent_at" in e for e in js["emails"]) and len(js["emails"]) == 2)
over("K9b filtr 29. 9. najde e-mail podle sent_at (poslano pozdeji), ne podle created_at", volej("date_from=2026-09-29&date_to=2026-09-29")[0] == ["poslano pozdeji"], volej("date_from=2026-09-29&date_to=2026-09-29")[0])
over("K9c filtr 28. 9. najde jen cekajici (bez sent_at -> created_at), poslany ne", volej("date_from=2026-09-28&date_to=2026-09-28")[0] == ["ceka"], volej("date_from=2026-09-28&date_to=2026-09-28")[0])

# system_emails: schvaleni / zamitnuti pres routu
system_emails.send_email = ok_send
system_emails.log_audit = lambda *a, **k: None
system_emails.current_user = lambda: admin
cur.execute("DELETE FROM system_emails")
for k in range(3):
    cur.execute("INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type, created_at) "
                "VALUES (NULL,'storefront_lead','a@invalid.test',%s,'b','pending','auto', NOW() - INTERVAL 3 DAY)", ("s%d" % k,))
real.commit()
cur.execute("SELECT id FROM system_emails ORDER BY id")
ids = [r["id"] for r in cur.fetchall()]
def sys_rev(i, approved):
    with appmod.app.test_request_context("/api/admin/system-emails/%d" % i, method="PUT", json={"approved": approved}):
        resp = system_emails.admin_system_email_review.__wrapped__(i)
    return (resp[0] if isinstance(resp, tuple) else resp).get_json()
def srad(i):
    cur.execute("SELECT * FROM system_emails WHERE id=%s", (i,))
    return cur.fetchone()
sys_rev(ids[0], True)
r = srad(ids[0])
over("K10a system schvaleni: sent, sent_at = ted, created_at 3 dny stare", r["status"] == "sent" and blizko_db(r["sent_at"]) and (r["sent_at"] - r["created_at"]).days >= 2, r)
sys_rev(ids[1], False)
over("K10b system zamitnuti: rejected, sent_at NULL", srad(ids[1])["status"] == "rejected" and srad(ids[1])["sent_at"] is None)
system_emails.send_email = spatny_send
sys_rev(ids[2], True)
over("K10c system selhani SMTP: failed, sent_at NULL", srad(ids[2])["status"] == "failed" and srad(ids[2])["sent_at"] is None)
with appmod.app.test_request_context("/api/admin/system-emails"):
    resp = system_emails.admin_system_emails_list.__wrapped__()
em = resp.get_json()["emails"]
over("K10d seznam system e-mailu nese sent_at", all("sent_at" in e for e in em) and sorted(e["sent_at"] is not None for e in em) == [False, False, True], [e["sent_at"] for e in em])

real.rollback()
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
