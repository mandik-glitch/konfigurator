#!/opt/konfigurator/api/venv/bin/python
"""Hak "schvaleny doklad -> e-mail ucetni do FRONTY ke schvaleni" (bot5, 2026-10-06): api/ucetni_hak.py + patche approvals.py, incoming_documents.py, emails.py, app.py (send_email: vic adres v Cc).

Robert 2026-10-06: schvalene doklady pujdou ucetni DO FRONTY ke schvaleni (`pending`, odejde az po jeho schvaleni; pravidlo 16 BEZ ZMENY). Adresy podle typu z tabulky "E-maily ucetni" (bot16).
SKUTECNE routy (approve vydaneho dokladu, approve + bulk-approve prijateho) pres Flask test client nad DOCASNYMI tabulkami; send_email je ATRAPA (NIC se neodesila), PDF dokladu je atrapa,
soubory prijatych dokladu jsou v docasnych adresarich. Ostre tabulky se jen ctou (zaklad zakaznika/dokladu) a po testu se porovnavaji pocty.
Kandidati: KAND_DIR=/cesta (approvals.py, incoming_documents.py, emails.py, app.py, ucetni_hak.py) nebo zive soubory v api/.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-06_ucetni_hak_testy/test_ucetni_hak.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KAND_DIR = os.environ.get("KAND_DIR")
tmp = tempfile.mkdtemp(prefix="kand_ucetni_")
TAPI = os.path.join(tmp, "api")
os.makedirs(TAPI)
KAND = {"approvals.py", "incoming_documents.py", "emails.py", "app.py", "ucetni_hak.py"}
for f in os.listdir(API):
    if f not in KAND and f not in ("__pycache__", "venv"):
        os.symlink(os.path.join(API, f), os.path.join(TAPI, f))
for d in ("webapp", "private-files", "katalog", "scripts", "sql", "docs", "backups"):
    if os.path.exists(os.path.join(REPO, d)):
        os.symlink(os.path.join(REPO, d), os.path.join(tmp, d))
os.symlink(os.path.join(REPO, "DEPLOY_LOCK.json"), os.path.join(tmp, "DEPLOY_LOCK.json"))
for f in KAND:
    src = os.path.join(KAND_DIR, f) if KAND_DIR and os.path.exists(os.path.join(KAND_DIR, f)) else os.path.join(API, f)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(TAPI, f))
sys.path.insert(0, TAPI)

import pymysql  # noqa: E402
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


if not os.path.exists(os.path.join(TAPI, "ucetni_hak.py")):
    over("0 existuje api/ucetni_hak.py (kandidat nebo zivy)", False, "chybi")
    print(f"\nVYSLEDEK hak ucetni: 0/{len(vysl)} OK")
    sys.exit(1)
import app as appmod  # noqa: E402
import documents  # noqa: E402
import emails  # noqa: E402
import drive  # noqa: E402
import incoming_documents as inc  # noqa: E402
import ucetni_emaily  # noqa: E402
import ucetni_hak  # noqa: E402
import qa_checks  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

VOLANI = []
SELHAT = [False]


def atrapa_email(to_email, subject, body_text, cc_email=None, attachments=None):
    VOLANI.append({"to": to_email, "subject": subject, "cc": cc_email, "prilohy": [(a[0], a[1], a[2]) for a in (attachments or [])]})
    if SELHAT[0]:
        raise RuntimeError("SMTP nedostupne (test)")


emails.send_email = atrapa_email                       # NIC se neodesila
appmod.send_email = atrapa_email
documents.render_document_pdf = lambda doc: b"%PDF-1.4 atrapa dokladu " + str(doc["id"]).encode()
AUDIT = []
for m in (appmod, sys.modules["approvals"], inc):
    m.log_audit = lambda *a, **k: AUDIT.append((a, k))
inc.INCOMING_DOCS_DIR = tempfile.mkdtemp(prefix="kand_ucetni_prichozi_")
inc.DRIVE_FILES_DIR = tempfile.mkdtemp(prefix="kand_ucetni_drive_")
drive.DRIVE_FILES_DIR = inc.DRIVE_FILES_DIR

real = appmod.get_conn()
TABS = ("shop_documents", "shop_emails", "app_settings", "incoming_documents", "shared_drive_files", "shared_drive_folders", "app_users", "role_permissions")


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def kopie_z_ostre(t, kde=""):
    c0 = ostre()
    try:
        with c0.cursor() as cur0:
            cur0.execute(f"SELECT * FROM `{t}` {kde}")
            return cur0.fetchall()
    finally:
        c0.close()


def stav_ostre():
    c0 = ostre()
    try:
        with c0.cursor() as cur0:
            cur0.execute("SELECT COUNT(*) AS n, COALESCE(SUM(status='pending'),0) AS p FROM shop_emails")
            em = cur0.fetchone()
            cur0.execute("SELECT COUNT(*) AS n, COALESCE(SUM(approval_status='schvaleno'),0) AS s FROM shop_documents")
            dk = cur0.fetchone()
            cur0.execute("SELECT COUNT(*) AS n, COALESCE(SUM(approval_status='schvaleno'),0) AS s FROM incoming_documents")
            pr = cur0.fetchone()
            return em, dk, pr
    finally:
        c0.close()


PRED = stav_ostre()
try:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()
    radky = kopie_z_ostre("app_users", "WHERE active=1 AND role='admin' ORDER BY id LIMIT 1")
    adm = radky[0]
    sql(f"INSERT INTO app_users ({', '.join(adm)}) VALUES ({', '.join(['%s'] * len(adm))})", list(adm.values()))
    ADMIN = adm["id"]
    zakl = kopie_z_ostre("shop_documents", "ORDER BY id LIMIT 1")
    ZAKLAD = zakl[0] if zakl else None

    def dok(typ="invoice", stav="ceka_schvaleni", cislo=None):
        """Novy doklad v docasne tabulce: kopie zakladniho radku (jinak minimalni), upraveny typ, stav a cislo."""
        r = dict(ZAKLAD)
        r.pop("id", None)
        r.update({"document_type": typ, "approval_status": stav, "document_number": cislo or f"T{len(vysl)}{typ[:2]}{os.urandom(2).hex()}"})
        sql(f"INSERT INTO shop_documents ({', '.join(r)}) VALUES ({', '.join(['%s'] * len(r))})", list(r.values()))
        return jedno("SELECT * FROM shop_documents WHERE document_number=%s", (r["document_number"],))

    def nastav_adresy(radky_):
        sql("DELETE FROM app_settings WHERE setting_key='ucetni_emaily'")
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('ucetni_emaily', %s)", (json.dumps({"v": 1, "radky": radky_}),))

    def fronta():
        return sql("SELECT id, status, template_key, recipient_email, cc_email, subject, document_id, trigger_type, body_text FROM shop_emails "
                   "WHERE template_key='ucetni_doklad' OR template_key LIKE 'prijaty_doklad:%%' ORDER BY id")       # jen e-maily ucetni; zakaznicky e-mail k dokladu (od 2026-10-08 po schvaleni dokladu) testuje test_email_po_schvaleni.py

    def reset():
        VOLANI.clear()
        SELHAT[0] = False
        sql("DELETE FROM shop_emails")
        ucetni_hak_vypnuto[0] = False

    ucetni_hak_vypnuto = [False]
    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def vol(metoda, cesta, uid, body=None):
        appmod._rate_limit_buckets.clear()
        h = {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}
        return cl.open(cesta, method=metoda, headers=h, json=body) if body is not None else cl.open(cesta, method=metoda, headers=h)

    if ZAKLAD is None:
        over("0 v databazi je alespon jeden doklad pro zaklad testu", False, None)
        raise SystemExit(1)

    # ------------------------------------------------------------------------------------------------------------------------- A) vydane doklady
    print("== A vydane doklady (approvals.approve_document)")
    ADR = {"invoice": {"adresy": ["ucetni@firma.cz", "druha@firma.cz"], "aktivni": True, "poznamka": ""},
           "credit_note": {"adresy": ["dobropisy@firma.cz"], "aktivni": False, "poznamka": ""},
           "delivery_note": {"adresy": [], "aktivni": True, "poznamka": ""},
           "prijaty_doklad": {"adresy": ["prijate@firma.cz", "kopie@firma.cz", "treti@firma.cz"], "aktivni": True, "poznamka": ""}}
    nastav_adresy(ADR)
    reset()
    d1 = dok("invoice")
    r = vol("POST", f"/api/admin/documents/{d1['id']}/approve", ADMIN)
    f = fronta()
    over("A1 schvaleni faktury s nastavenymi adresami: 200, do FRONTY pribyl 1 e-mail 'pending' (prijemce 1. adresa, Cc 2. adresa, document_id, trigger auto, predmet s cislem dokladu), NIC se neodeslo",
         r.status_code == 200 and len(f) == 1 and f[0]["status"] == "pending" and f[0]["recipient_email"] == "ucetni@firma.cz" and f[0]["cc_email"] == "druha@firma.cz" and f[0]["document_id"] == d1["id"]
         and f[0]["template_key"] == "ucetni_doklad" and f[0]["trigger_type"] == "auto" and d1["document_number"] in f[0]["subject"] and "Faktura" in f[0]["subject"] and len(VOLANI) == 0
         and jedno("SELECT approval_status FROM shop_documents WHERE id=%s", (d1["id"],))["approval_status"] == "schvaleno", (r.status_code, f, VOLANI))
    ucetni_hak.zaradit_vydany(d1["id"])
    over("A2 opakovane zarazeni stejneho dokladu (retry, dvojklik) nic nepridava: porad 1 e-mail", len(fronta()) == 1, fronta())
    d2 = dok("credit_note")
    r2 = vol("POST", f"/api/admin/documents/{d2['id']}/approve", ADMIN)
    d3 = dok("delivery_note")
    r3 = vol("POST", f"/api/admin/documents/{d3['id']}/approve", ADMIN)
    d4 = dok("proforma_invoice")
    r4 = vol("POST", f"/api/admin/documents/{d4['id']}/approve", ADMIN)
    over("A3 typ s NEAKTIVNIM radkem, s PRAZDNYMI adresami a typ BEZ radku: doklad se schvali (200), ale do fronty nepribyde nic", r2.status_code == r3.status_code == r4.status_code == 200 and len(fronta()) == 1, (r2.status_code, r3.status_code, r4.status_code, fronta()))
    sql("UPDATE app_settings SET setting_value='{rozbity json' WHERE setting_key='ucetni_emaily'")
    d5 = dok("invoice")
    r5 = vol("POST", f"/api/admin/documents/{d5['id']}/approve", ADMIN)
    over("A4 poskozene nastaveni (rozbity JSON): fail closed - doklad se schvali, nic se nezaradi", r5.status_code == 200 and len(fronta()) == 1, (r5.status_code, fronta()))
    nastav_adresy(ADR)
    d6 = dok("invoice", stav="ceka_schvaleni")
    over("A5 doklad, ktery NENI schvaleny, se nezaradi (zaradit_vydany vola jen schvaleni; primo volany vrati None)", ucetni_hak.zaradit_vydany(d6["id"]) is None and len(fronta()) == 1, fronta())
    puvodni = ucetni_hak.zaradit_vydany
    def spadne(doc_id):
        raise RuntimeError("test: hak spadl")
    sys.modules["ucetni_hak"].zaradit_vydany = spadne
    r7 = vol("POST", f"/api/admin/documents/{d6['id']}/approve", ADMIN)
    sys.modules["ucetni_hak"].zaradit_vydany = puvodni
    over("A6 chyba haku NIKDY nerozbije schvaleni dokladu: 200, doklad je schvaleny", r7.status_code == 200 and jedno("SELECT approval_status FROM shop_documents WHERE id=%s", (d6["id"],))["approval_status"] == "schvaleno", r7.status_code)
    # schvaleni e-mailu adminem (Robert) -> odejde s PDF a obema adresami
    em = fronta()[0]
    status_row, status, err = emails.approve_pending_email(em["id"], dict(adm))
    over("A7 po SCHVALENI e-mailu adminem odejde: prijemce 1. adresa, Cc 2. adresa, priloha PDF dokladu (nazev invoice_<cislo>.pdf, obsah z dokladu), stav 'sent'",
         status == "sent" and len(VOLANI) == 1 and VOLANI[0]["to"] == "ucetni@firma.cz" and VOLANI[0]["cc"] == "druha@firma.cz" and len(VOLANI[0]["prilohy"]) == 1
         and VOLANI[0]["prilohy"][0][0] == f"invoice_{d1['document_number']}.pdf" and VOLANI[0]["prilohy"][0][1].startswith(b"%PDF") and VOLANI[0]["prilohy"][0][2] == "pdf", (status, err, VOLANI))

    # ------------------------------------------------------------------------------------------------------------------------- B) prijate doklady
    print("== B prijate doklady (incoming_documents approve + bulk-approve)")
    reset()

    def prijaty(nazev="faktura_dodavatel.pdf", obsah=b"%PDF-1.4 prijata faktura", s_souborem=True):
        stored = None
        if s_souborem:
            stored = "stag_" + os.urandom(4).hex() + ".pdf"
            with open(os.path.join(inc.INCOMING_DOCS_DIR, stored), "wb") as fh:
                fh.write(obsah)
        sql("INSERT INTO incoming_documents (source_email, source_name, subject, received_at, filename, stored_filename, content_type, size_bytes, approval_status, supplier_name) "
            "VALUES ('dodavatel@x.cz','Dodavatel s.r.o.','Faktura',NOW(),%s,%s,%s,%s,'ceka_schvaleni','Dodavatel s.r.o.')", (nazev if s_souborem else None, stored, "application/pdf" if s_souborem else None, len(obsah) if s_souborem else None))
        return jedno("SELECT id FROM incoming_documents ORDER BY id DESC LIMIT 1")["id"]
    p1 = prijaty()
    rp1 = vol("POST", f"/api/admin/incoming-documents/{p1}/approve", ADMIN)
    f = fronta()
    over("B1 schvaleni prijateho dokladu se souborem: 200, do FRONTY pribyl e-mail 'pending' (template_key prijaty_doklad:<id>, prijemce 1. adresa, Cc zbyle 2, predmet s nazvem souboru), nic se neodeslo",
         rp1.status_code == 200 and len(f) == 1 and f[0]["status"] == "pending" and f[0]["template_key"] == f"prijaty_doklad:{p1}" and f[0]["recipient_email"] == "prijate@firma.cz"
         and f[0]["cc_email"] == "kopie@firma.cz, treti@firma.cz" and "faktura_dodavatel.pdf" in f[0]["subject"] and f[0]["document_id"] is None and len(VOLANI) == 0, (rp1.status_code, f, VOLANI))
    status_row, status, err = emails.approve_pending_email(f[0]["id"], dict(adm))
    over("B2 po schvaleni e-mailu adminem odejde s PRILOHOU ze Sdileneho disku (nazev i obsah souboru shodny s prijatym dokladem, pdf), Cc se vsemi zbylymi adresami",
         status == "sent" and len(VOLANI) == 1 and VOLANI[0]["to"] == "prijate@firma.cz" and VOLANI[0]["cc"] == "kopie@firma.cz, treti@firma.cz" and VOLANI[0]["prilohy"] == [("faktura_dodavatel.pdf", b"%PDF-1.4 prijata faktura", "pdf")], (status, err, VOLANI))
    reset()
    p2, p3 = prijaty("a.pdf", b"AAA"), prijaty("b.pdf", b"BBB")
    rb = vol("POST", "/api/admin/incoming-documents/bulk-approve", ADMIN, {"ids": [p2, p3]})
    f = fronta()
    over("B3 hromadne schvaleni 2 prijatych dokladu: kazdy dostane SVUJ e-mail ve fronte (2 x pending), spravne soubory", rb.status_code == 200 and len(f) == 2 and {x["template_key"] for x in f} == {f"prijaty_doklad:{p2}", f"prijaty_doklad:{p3}"}
         and all(x["status"] == "pending" for x in f), (rb.status_code, rb.get_json(), f))
    reset()
    p4 = prijaty(s_souborem=False)
    rp4 = vol("POST", f"/api/admin/incoming-documents/{p4}/approve", ADMIN)
    over("B4 prijaty doklad BEZ souboru (jen text e-mailu): schvali se, ale ucetni se nic neposila (nemela by co prilozit)", rp4.status_code == 200 and fronta() == (), (rp4.status_code, fronta()))
    reset()
    nastav_adresy({"prijaty_doklad": {"adresy": ["prijate@firma.cz"], "aktivni": False, "poznamka": ""}})
    p5 = prijaty()
    rp5 = vol("POST", f"/api/admin/incoming-documents/{p5}/approve", ADMIN)
    over("B5 neaktivni radek 'prijaty_doklad': nic se nezaradi", rp5.status_code == 200 and fronta() == (), fronta())
    nastav_adresy(ADR)
    reset()
    p6 = prijaty()
    vol("POST", f"/api/admin/incoming-documents/{p6}/approve", ADMIN)
    em = fronta()[0]
    sql("DELETE FROM shared_drive_files")
    st_row, st, er = emails.approve_pending_email(em["id"], dict(adm))
    over("B6 soubor prijateho dokladu na Sdilenem disku chybi (smazany): e-mail se NEodesle (zadne volani SMTP), stav se vrati na 'pending' (jde schvalit znovu), vrati se citelna chyba",
         st == "failed" and "Příloha" in (er or "") and len(VOLANI) == 0 and jedno("SELECT status FROM shop_emails WHERE id=%s", (em["id"],))["status"] == "pending", (st, er, VOLANI))
    ucetni_hak.zaradit_prijaty(p6)
    over("B7 opakovane zarazeni stejneho prijateho dokladu nic nepridava", len(fronta()) == 1, fronta())

    # ------------------------------------------------------------------------------------------------------------------------- C) send_email a Cc, tabulka, staticke kontrakty
    print("== C send_email (vic adres v Cc), tabulka v adminu, pravidlo 16")
    zachyt = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def starttls(self, **k):
            pass

        def login(self, *a):
            pass

        def sendmail(self, od, komu, zprava):
            zachyt["komu"] = list(komu)

        def quit(self):
            pass
    import smtplib
    puvodni_smtp, puvodni_cfg = smtplib.SMTP, appmod._get_smtp_config
    smtplib.SMTP = FakeSMTP
    appmod._get_smtp_config = lambda: {"host": "smtp.test", "port": 587, "user": "u", "password": "p", "from": "from@test.cz"}
    SKUTECNY_SEND = sys.modules["app"].__dict__["send_email"] if sys.modules["app"].__dict__["send_email"] is not atrapa_email else None
    # skutecna funkce je prepsana atrapou - vezmeme ji ze zdroje app.py (kandidat) pres exec jen dane funkce
    import ast
    zdroj_app = open(os.path.join(TAPI, "app.py"), encoding="utf-8").read()
    strom = ast.parse(zdroj_app)
    fn = next(n for n in strom.body if isinstance(n, ast.FunctionDef) and n.name == "send_email")
    ns = {"re": re, "smtplib": smtplib, "ssl": __import__("ssl"), "MIMEMultipart": __import__("email.mime.multipart", fromlist=["x"]).MIMEMultipart,
          "MIMEText": __import__("email.mime.text", fromlist=["x"]).MIMEText, "MIMEApplication": __import__("email.mime.application", fromlist=["x"]).MIMEApplication, "_get_smtp_config": appmod._get_smtp_config}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app_send_email", "exec"), ns)
    ns["send_email"]("to@x.cz", "Predmet", "Telo", cc_email="a@x.cz, b@x.cz; c@x.cz")
    smtplib.SMTP, appmod._get_smtp_config = puvodni_smtp, puvodni_cfg
    over("C1 send_email s vice adresami v Cc: SMTP dostane KAZDOU adresu zvlast (to + 3 Cc), ne jeden retezec 'a, b; c'", zachyt.get("komu") == ["to@x.cz", "a@x.cz", "b@x.cz", "c@x.cz"], zachyt)
    t = vol("GET", "/api/admin/ucetni-emaily", ADMIN).get_json()
    over("C2 po zapojeni haku tabulka v adminu hlasi odesilani_zapojeno = true (UI uz nepise 'zatim nezapojeno'), ucetni_emaily.ODESILANI_ZAPOJENO je True", ucetni_emaily.ODESILANI_ZAPOJENO is True and t["odesilani_zapojeno"] is True, t.get("odesilani_zapojeno"))
    with real.cursor() as cur:
        nalez = qa_checks.check_direct_send_email_bypass(cur)
    zdroj_hak = open(os.path.join(TAPI, "ucetni_hak.py"), encoding="utf-8").read()
    over("C3 pravidlo 16: modul NIKDY nevola send_email primo (jen emails.send_and_log(auto=True) = fronta 'pending'), QA kontrola prime odesilani nenachazi nic noveho",
         "send_email(" not in zdroj_hak and zdroj_hak.count("auto=True") == 2 and (not nalez or all("ucetni_hak" not in str(n) for n in nalez)), nalez)
    zdroj_ap = open(os.path.join(TAPI, "approvals.py"), encoding="utf-8").read()
    zdroj_in = open(os.path.join(TAPI, "incoming_documents.py"), encoding="utf-8").read()
    over("C4 hak je zapojen po commitu vsech TRI cest schvaleni (vydany doklad, prijaty approve, prijaty bulk-approve) a v kazde je v try/except", "ucetni_hak.zaradit_vydany(doc_id)" in zdroj_ap and zdroj_in.count("ucetni_hak.zaradit_prijaty(doc_id)") == 2
         and zdroj_ap.count("except Exception") >= 1 and zdroj_in.count("ucetni hak: prijaty doklad") == 2, None)
    # mutace: bez haku by se nic do fronty nedostalo (A1 to zachyti)
    reset()
    nastav_adresy(ADR)
    sys.modules["ucetni_hak"].zaradit_vydany = lambda doc_id: None
    dm = dok("invoice")
    vol("POST", f"/api/admin/documents/{dm['id']}/approve", ADMIN)
    sys.modules["ucetni_hak"].zaradit_vydany = puvodni
    over("MUT1 mutace: bez haku se do fronty nic nedostane (testy A1 tedy opravdu hlidaji zapojeni)", fronta() == (), fronta())
finally:
    with real.cursor() as cur:
        for t in TABS:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
    shutil.rmtree(tmp, ignore_errors=True)
    for d in (inc.INCOMING_DOCS_DIR, inc.DRIVE_FILES_DIR):
        shutil.rmtree(d, ignore_errors=True)
PO = stav_ostre()
over("Z ostre tabulky shop_emails, shop_documents a incoming_documents se testem nezmenily (pocty radku, cekajici, schvalene)", PRED == PO, (PRED, PO))
print(f"\nVYSLEDEK hak ucetni: {sum(vysl)}/{len(vysl)} OK")
sys.exit(0 if all(vysl) else 1)
