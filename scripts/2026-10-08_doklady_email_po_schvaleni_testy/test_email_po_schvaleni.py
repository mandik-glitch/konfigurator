#!/opt/konfigurator/api/venv/bin/python
"""E-mail s dokladem jen po schvaleni dokladu (bot5, 2026-10-08; Robert pres bot16: "nemuze se nabidnout odeslat e-mail o potvrzeni zaslani dokladu, ktery neni schvaleny").
Pravidlo: dokud shop_documents.approval_status != 'schvaleno', e-mail s dokladem se NEZARADI do fronty (auto), NEODESLE (rucne ani schvalenim cekajiciho e-mailu); po schvaleni dokladu se zakaznicky
e-mail zaradi prave jednou. Vsechno nad DOCASNYMI kopiemi tabulek shop_emails / shop_documents / shop_orders (stejne spojeni jako get_conn(), radek dokladu a objednavky se zkopiruje z ostre DB,
e-mail zakaznika se v kopii nahradi), send_email, PDF, audit a hak ucetni jsou atrapy - nic se neposila ani nezapisuje do ostre DB.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_doklady_email_po_schvaleni_testy/test_email_po_schvaleni.py"""
import os
import sys
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api")))
sys.dont_write_bytecode = True
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
import app as appmod  # noqa: E402
import approvals  # noqa: E402
import documents  # noqa: E402
import emails  # noqa: E402
import ucetni_hak  # noqa: E402
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)[:500]))


conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
cur = real.cursor()
for t in ("shop_emails", "shop_documents", "shop_orders"):
    cur.execute("CREATE TEMPORARY TABLE `_tpl_%s` LIKE `%s`" % (t, t))
    cur.execute("INSERT INTO `_tpl_%s` SELECT * FROM `%s`" % (t, t))
    cur.execute("CREATE TEMPORARY TABLE `%s` LIKE `_tpl_%s`" % (t, t))
cur.execute("DELETE FROM shop_emails")
cur.execute("SELECT * FROM _tpl_shop_documents ORDER BY id DESC LIMIT 1")
vzor_doc = cur.fetchone()
cur.execute("SELECT * FROM _tpl_shop_orders WHERE id=%s", (vzor_doc["order_id"],))
vzor_obj = cur.fetchone()
if not vzor_doc or not vzor_obj:
    raise SystemExit("ABORT: v ostre DB neni zadny doklad s objednavkou, ze ktereho by se kopie udelala")


def vloz(tabulka, radek, **zmeny):
    r = dict(radek, **zmeny)
    cur.execute("INSERT INTO %s (%s) VALUES (%s)" % (tabulka, ", ".join("`%s`" % k for k in r), ", ".join(["%s"] * len(r))), list(r.values()))
    real.commit()
    return r["id"]


cur.execute("DELETE FROM shop_orders")
cur.execute("DELETE FROM shop_documents")
real.commit()
OBJ = vloz("shop_orders", vzor_obj, id=900001, is_test=0, customer_email="zakaznik@invalid.test", order_number="TEST-1")
OBJ_TEST = vloz("shop_orders", vzor_obj, id=900002, is_test=1, customer_email="zakaznik@invalid.test", order_number="TEST-2")
poradi = [0]


def novy_doklad(typ="payment_tax_document", stav="ceka_schvaleni", obj=OBJ):
    poradi[0] += 1
    return vloz("shop_documents", vzor_doc, id=900100 + poradi[0], order_id=obj, document_type=typ, document_number="T%05d" % poradi[0], approval_status=stav,
                approved_at=None, seq_number=900100 + poradi[0])


poslano = []
emails.send_email = lambda *a, **k: poslano.append(a[0])
documents.render_document_pdf = lambda doc: b"%PDF-zastupny"
admin = {"id": 1, "name": "Test Admin", "email": "x@invalid.test", "active": 1}
approvals.current_user = lambda: admin
approvals.log_audit = lambda *a, **k: None
emails.current_user = lambda: admin
emails.log_audit = lambda *a, **k: None
ucetni_hak.zaradit_vydany = lambda doc_id: None                      # hak ucetni neni predmetem testu (cte nastaveni z ostre DB)


def radky(**podm):
    kde = " AND ".join("%s=%%s" % k for k in podm) or "1=1"
    cur.execute("SELECT * FROM shop_emails WHERE " + kde + " ORDER BY id", list(podm.values()))
    return cur.fetchall()


def volej(fn, cesta, json_body=None, method="POST", **kw):
    with appmod.app.test_request_context(cesta, method=method, json=json_body):
        r = fn.__wrapped__(**kw)
    kod = r[1] if isinstance(r, tuple) else r.status_code
    resp = r[0] if isinstance(r, tuple) else r
    return kod, resp.get_json()


# ---- A: neschvaleny doklad -> nic do fronty ani ven
D1 = novy_doklad()
documents._auto_email_after_issue(OBJ, D1)
over("A1 vystaveni neschvaleneho dokladu: e-mail se NEzaradi do fronty", not radky(document_id=D1), radky(document_id=D1))
log_id, st, err = emails.send_document_email_auto(OBJ, D1)
over("A2 send_document_email_auto: not_approved s hlaskou, nic nezalogovano", log_id is None and st == "not_approved" and "ještě není schválený" in err and not radky(document_id=D1), (log_id, st, err))
for auto in (True, False):
    r_ = emails.send_and_log(OBJ, template_key="payment_tax_document", recipient="zakaznik@invalid.test", subject="s", body="b", document_id=D1, admin=None if auto else admin, auto=auto)
    over("A3 send_and_log(auto=%s) s neschvalenym dokladem: not_approved, nic nezalogovano ani neodeslano" % auto, r_[0] is None and r_[1] == "not_approved" and not radky(document_id=D1) and not poslano, (r_, poslano))
k, j = volej(emails.admin_document_send_email, "/api/admin/documents/%d/email" % D1, {}, doc_id=D1)
over("A4 rucni odeslani dokladu (POST /documents/<id>/email): 409 s textem a kodem", k == 409 and j["code"] == "document_not_approved" and "Doklad č. T00001 ještě není schválený – e-mail s ním nejde odeslat. Nejdřív ho schval na Dashboardu." == j["error"], (k, j))
k, j = volej(emails.admin_order_send_email, "/api/admin/orders/%d/emails" % OBJ, {"kind": "custom", "subject": "s", "body": "b", "attach_document_id": D1}, order_id=OBJ)
over("A5 rucni e-mail k objednavce s prilohou neschvaleneho dokladu: 409", k == 409 and j["code"] == "document_not_approved", (k, j))
k, j = volej(emails.admin_order_send_email, "/api/admin/orders/%d/emails" % OBJ, {"kind": "custom", "subject": "s", "body": "b"}, order_id=OBJ)
over("A6 bezny rucni e-mail BEZ dokladu dal funguje (200, odesel)", k == 200 and j["status"] == "ok" and poslano == ["zakaznik@invalid.test"], (k, j, poslano))
poslano.clear()
cur.execute("INSERT INTO shop_emails (order_id, document_id, template_key, recipient_email, subject, body_text, status, trigger_type) VALUES (%s,%s,'payment_tax_document','zakaznik@invalid.test','s','b','pending','auto')", (OBJ, D1))
real.commit()
p_id = cur.lastrowid
row, st, err = emails.approve_pending_email(p_id, admin)
over("A7 cekajici e-mail s neschvalenym dokladem (puvodni fronta): approve_pending_email = doc_not_approved, zustava pending, neodesel", st == "doc_not_approved" and radky(id=p_id)[0]["status"] == "pending" and not poslano, (st, poslano))
k, j = volej(emails.admin_email_review, "/api/admin/emails/%d" % p_id, {"approved": True}, method="PUT", email_id=p_id)
over("A8 schvaleni takoveho e-mailu v adminu: 409 s hlaskou, e-mail porad pending", k == 409 and j["code"] == "document_not_approved" and radky(id=p_id)[0]["status"] == "pending", (k, j))
cur.execute("DELETE FROM shop_emails")
real.commit()

# ---- B: schvaleni dokladu -> zakaznicky e-mail do fronty prave jednou
k, j = volej(approvals.approve_document, "/api/admin/documents/%d/approve" % D1, method="POST", doc_id=D1)
fr = radky(document_id=D1)
over("B1 schvaleni dokladu: zakaznicky e-mail je ve fronte PRAVE JEDNOU (pending, auto, spravna sablona a prijemce)", k == 200 and len(fr) == 1 and fr[0]["status"] == "pending" and fr[0]["trigger_type"] == "auto"
     and fr[0]["template_key"] == "payment_tax_document" and fr[0]["recipient_email"] == "zakaznik@invalid.test" and not poslano, (k, fr, poslano))
documents._auto_email_after_issue(OBJ, D1)
over("B2 opakovane zarazeni (idempotence): porad jeden radek", len(radky(document_id=D1)) == 1)
k, j = volej(approvals.approve_document, "/api/admin/documents/%d/approve" % D1, method="POST", doc_id=D1)
over("B3 druhe schvaleni tehoz dokladu: 404 a zadny dalsi e-mail", k == 404 and len(radky(document_id=D1)) == 1, (k, j))
row, st, err = emails.approve_pending_email(fr[0]["id"], admin)
over("B4 schvaleni zarazeneho e-mailu ve fronte: odejde (doklad je schvaleny)", st == "sent" and poslano == ["zakaznik@invalid.test"] and radky(document_id=D1)[0]["status"] == "sent", (st, err, poslano))
poslano.clear()
k, j = volej(emails.admin_document_send_email, "/api/admin/documents/%d/email" % D1, {"recipient": "jiny@invalid.test"}, doc_id=D1)
over("B5 rucni (znovu)odeslani schvaleneho dokladu projde, pokud nebylo odeslano v poslednich 60 s (tady 409 already_sent z ochrany proti dvojkliku, ne kvuli schvaleni)", k in (200, 409) and (k == 200 or j.get("error") == "already_sent"), (k, j))
poslano.clear()

# ---- C: vyjimky
Dc = novy_doklad(typ="credit_note")
k, j = volej(approvals.approve_document, "/api/admin/documents/%d/approve" % Dc, method="POST", doc_id=Dc)
over("C1 dobropis: po schvaleni se zakaznikovi automaticky nic nezarazuje (jako dosud)", k == 200 and not radky(document_id=Dc), radky(document_id=Dc))
Dt = novy_doklad(obj=OBJ_TEST)
k, j = volej(approvals.approve_document, "/api/admin/documents/%d/approve" % Dt, method="POST", doc_id=Dt)
over("C2 testovaci objednavka: po schvaleni se nic nezarazuje", k == 200 and not radky(document_id=Dt), radky(document_id=Dt))
Ds = novy_doklad(stav="schvaleno")
documents._auto_email_after_issue(OBJ, Ds)
over("C3 doklad schvaleny uz pri vystaveni: e-mail se zaradi hned (1 radek)", len(radky(document_id=Ds)) == 1)
for typ in documents.AUTO_EMAIL_DOCUMENT_TYPES:
    Dx = novy_doklad(typ=typ, stav="schvaleno")
    documents._auto_email_after_issue(OBJ, Dx)
    over("C4 typ %s: po schvaleni se zaradi" % typ, len(radky(document_id=Dx)) == 1 and radky(document_id=Dx)[0]["template_key"] == typ)
sd = documents._serialize_document(radky_dok := (lambda: (cur.execute("SELECT * FROM shop_documents WHERE id=%s", (D1,)), cur.fetchone())[1])())
over("D1 serializace dokladu vraci approval_status a approved_at", sd["approval_status"] == "schvaleno" and sd["approved_at"] is not None, {k: sd.get(k) for k in ("approval_status", "approved_at")})
sd0 = documents._serialize_document((lambda: (cur.execute("SELECT * FROM shop_documents WHERE id=%s", (Dc,)), cur.fetchone())[1])())
over("D2 serializace nechybi ani u dokladu bez radku approved_at (None)", "approved_at" in sd0)

real.rollback()
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
