#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, krok 3 (bot5, 2026-10-02): MESICNI VYUCTOVANI provizi - api/dealer_statements.py nad DOCASNYMI tabulkami.

Vyuctovani je podklad, podle ktereho dealer vystavi fakturu nam. Generuje se tlacitkem (zadny casovac), admin ho schvali (cislo DV-RRRR-NNN, od te chvile je zamcene),
po uhrade se oznaci za zaplacene. Docasne kopie (CREATE TEMPORARY TABLE, bez FK; struktura dealers/dealer_rates/dealer_statements/dealer_statement_lines z migraci,
objednavky/polozky/vratky/historie/nastaveni jako LIKE ostrych tabulek). Ostre shop_products, content_categories a app_users se jen ctou. Pevny cas: 5. 11. 2026.

Cast A  co se dostane do mesice (hranice mesice, lhuta od pozdejsiho z zaplaceni/expedice, otevrene vraceni, jen cesta 'our', ne testovaci, ne cizi dealer)
Cast B  zivotni cyklus (draft, beze zmeny, prepocet, zastarale podklady, schvaleni a cislo, uzamceni, zaplaceno, zruseni a uvolneni radku)
Cast C  korekce (vraceni a storno PO vyuctovani = zaporny radek, otevrene vraceni ceka, zadne dvojite zahrnuti, zaporny soucet jen s force)
Cast D  dokument (HTML, escapovani, castky, razitko navrhu) a panel dealera (jen schvalena a zaplacena, jen vlastni)
Cast E  opravneni, nic se nemaze, nic se nezapisuje mimo vyuctovani, mutace
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_vyuctovani.py     (kandidati: --setenv=STATEMENTS_PY=... --setenv=COMMISSIONS_PY=... --setenv=DEALERS_PY=...)
"""
import ast
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KANDIDATI = {"dealers.py": os.environ.get("DEALERS_PY"), "dealer_commissions.py": os.environ.get("COMMISSIONS_PY"), "dealer_statements.py": os.environ.get("STATEMENTS_PY")}
SQL_DEALERS = os.path.join(REPO, "sql", "2026-10-02_dealers.sql")
SQL_STATEMENTS = os.path.join(REPO, "sql", "2026-10-02_dealer_statements.sql")
if any(KANDIDATI.values()):
    tmp = tempfile.mkdtemp(prefix="kand_vyuctovani_")
    for jmeno, cesta in KANDIDATI.items():
        if cesta:
            shutil.copy(cesta, os.path.join(tmp, jmeno))
    sys.path.insert(0, tmp)
sys.path.insert(1 if any(KANDIDATI.values()) else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402

for sekce in ("dealeri", "dealer_provize", "dealer_klice"):
    if sekce not in appmod.PERMISSION_SECTIONS:
        appmod.PERMISSION_SECTIONS = tuple(appmod.PERMISSION_SECTIONS) + (sekce,)
import dealers  # noqa: E402
import dealer_commissions as dc  # noqa: E402
import dealer_statements as ds  # noqa: E402
dealers.log_audit = lambda *a, **k: None
ds.log_audit = lambda *a, **k: None

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TEMP_ZE_SQL = ("dealers", "dealer_rates", "dealer_statements", "dealer_statement_lines")
TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_returns", "shop_return_items", "shop_order_status_history", "app_settings")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_orders", "shop_order_items", "shop_returns", "shop_order_status_history", "app_settings", "audit_log"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT table_name AS t FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name LIKE 'dealer_statement%'")
            out["tabulky_vyuctovani"] = sorted((r.get("t") or r.get("T")) for r in cur.fetchall())
            return out
    finally:
        c.close()


pred = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")


def prikazy(cesta):
    return [s.strip() for s in "\n".join(l for l in open(cesta, encoding="utf-8").read().splitlines() if not l.strip().startswith("--")).split(";") if s.strip()]


FK_RE = re.compile(r",\s*CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", re.I)


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


try:
    with real.cursor() as cur:
        cur.execute("CREATE TEMPORARY TABLE `_tpl_app_settings` LIKE `app_settings`")
        cur.execute("INSERT INTO `_tpl_app_settings` SELECT * FROM `app_settings`")
        for t in TEMP_LIKE:
            if t != "app_settings":
                cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        cur.execute("INSERT INTO app_settings SELECT * FROM _tpl_app_settings")
        cur.execute("DELETE FROM app_settings WHERE setting_key LIKE 'dealer_%'")
        for cesta in (SQL_DEALERS, SQL_STATEMENTS):
            for s in prikazy(cesta):
                if s.startswith("CREATE TABLE IF NOT EXISTS"):
                    nazev = re.match(r"CREATE TABLE IF NOT EXISTS (\w+)", s).group(1)
                    if nazev in TEMP_ZE_SQL:
                        cur.execute(FK_RE.sub("", re.sub(r"^CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", s)))
        cur.execute("SHOW COLUMNS FROM shop_orders LIKE 'dealer_id'")
        if not cur.fetchone():
            alter = re.sub(r",\s*ADD CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", "", [s for s in prikazy(SQL_DEALERS) if s.startswith("ALTER TABLE shop_orders")][0])
            cur.execute("SHOW CREATE TABLE shop_orders")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE")
            cur.execute(alter)
    real.commit()

    DEN = datetime.timedelta(days=1)
    NOW = datetime.datetime(2026, 11, 5, 12, 0, 0)
    CAS = [NOW]
    dc._now = lambda: CAS[0]
    ds._now = lambda: CAS[0]
    CITR = [0]

    def dt(m, d, y=2026):
        return datetime.datetime(y, m, d, 9, 0, 0)

    def dealer(name, ref, comm=10.0, user_id=None, ico="12345678"):
        sql("INSERT INTO dealers (ref_code, name, status, default_commission_pct, user_id, ico, billing_street, billing_city, billing_zip, bank_account) VALUES (%s,%s,'active',%s,%s,%s,'Ulice 5','Brno','60200','123456789/0100')",
            (ref, name, comm, user_id, ico))
        return sql("SELECT * FROM dealers WHERE ref_code=%s", (ref,))[0]

    def objednavka(d, vytvoreno, zaplaceno=None, expedovano=None, status="expedovana", path="our", is_test=0, total=1210.0):
        CITR[0] += 1
        sql("INSERT INTO shop_orders (order_number, status, customer_name, customer_email, total_czk, payment_received_at, payment_received_total_czk, dealer_id, order_path, is_test, created_at) "
            "VALUES (%s,%s,'Jan Novak','zakaznik@example.cz',%s,%s,%s,%s,%s,%s,%s)", (f"VY{CITR[0]:05d}", status, total, zaplaceno, total if zaplaceno else 0, d["id"], path, is_test, vytvoreno))
        oid = sql("SELECT id FROM shop_orders ORDER BY id DESC LIMIT 1")[0]["id"]
        if expedovano:
            sql("INSERT INTO shop_order_status_history (order_id, status, changed_at) VALUES (%s,'expedovana',%s)", (oid, expedovano))
        return oid

    def polozka(oid, line, qty=1):
        sql("INSERT INTO shop_order_items (order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (%s,NULL,'Polozka',%s,%s,%s)", (oid, round(line / qty, 2), qty, line))
        return sql("SELECT id FROM shop_order_items ORDER BY id DESC LIMIT 1")[0]["id"]

    def vratka(oid, item_id, qty, cena, status="vyrizeno", resolution="refund"):
        CITR[0] += 1
        sql("INSERT INTO shop_returns (order_id, return_number, return_type, status, resolution) VALUES (%s,%s,'odstoupeni',%s,%s)", (oid, f"VR{CITR[0]:05d}", status, resolution))
        rid = sql("SELECT id FROM shop_returns ORDER BY id DESC LIMIT 1")[0]["id"]
        sql("INSERT INTO shop_return_items (return_id, order_item_id, qty, unit_price_czk) VALUES (%s,%s,%s,%s)", (rid, item_id, qty, cena))
        return rid

    A = dealer("Alfa", "alfa000001", comm=10.0, ico="11111111")
    B = dealer("<script>alert(1)</script> & spol.", "beta000002", comm=20.0, ico="22222222")
    # --- dealer A (10 %)
    E1 = objednavka(A, dt(8, 20), dt(9, 1), dt(9, 5)); I1 = polozka(E1, 1000.0)                        # lhuta skoncila 19. 9.
    E2 = objednavka(A, dt(10, 1), dt(10, 10), dt(10, 12)); I2 = polozka(E2, 1000.0, qty=2)           # lhuta skonci 26. 10.
    E3 = objednavka(A, dt(10, 20), dt(10, 25), dt(10, 28)); polozka(E3, 1000.0)                      # lhuta skonci 11. 11. (po konci rijna)
    E4 = objednavka(A, dt(9, 25), dt(10, 5), dt(10, 7)); I4 = polozka(E4, 1000.0)                    # lhuta ok, ale otevrene vraceni
    vratka(E4, I4, 1, 1000.0, status="posuzovano", resolution=None)
    E5 = objednavka(A, dt(10, 2), None, None, status="nova"); polozka(E5, 1000.0)                    # nezaplacena
    E6 = objednavka(A, dt(8, 1), dt(8, 5), dt(8, 8), path="dealer"); polozka(E6, 1000.0)             # cesta dealer - bez provize
    E7 = objednavka(A, dt(8, 1), dt(8, 5), dt(8, 8), is_test=1); polozka(E7, 1000.0)                 # testovaci
    E9 = objednavka(A, dt(10, 5), dt(10, 15), dt(10, 19)); polozka(E9, 1000.0)                       # lhuta skonci 2. 11. (po konci rijna)
    # --- dealer B (20 %)
    F1 = objednavka(B, dt(8, 25), dt(9, 3), dt(9, 4)); polozka(F1, 500.0)                              # 100 Kc, lhuta skoncila 18. 9.

    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]
    uzivatele = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 3")]
    sql("UPDATE dealers SET user_id=%s WHERE id=%s", (uzivatele[0], A["id"]))
    sql("UPDATE dealers SET user_id=%s WHERE id=%s", (uzivatele[1], B["id"]))

    def klient(user_id):
        k = appmod.app.test_client()
        if user_id is not None:
            with k.session_transaction() as s_:
                s_["user_id"] = user_id
        return k

    adm, panel_a, panel_b, nepr, zakaznik = klient(admin_id), klient(uzivatele[0]), klient(uzivatele[1]), klient(None), klient(uzivatele[2])

    def generuj(period, dealer_id=None):
        return adm.post("/api/admin/dealer-statements/generate", json={"period": period, **({"dealer_id": dealer_id} if dealer_id else {})})

    def vyuct(sid):
        return adm.get(f"/api/admin/dealer-statements/{sid}?detail=1").get_json()["statement"]

    def radky(sid):
        return [(l["order_id"], l["line_type"], l["commission_czk"]) for l in vyuct(sid)["lines"]]

    # ============================================================================================================ A) co se dostane do mesice
    print("== A co se dostane do mesice")
    PB = ds.period_bounds
    def chyba_obdobi(x):
        try:
            PB(x)
            return False
        except ValueError:
            return True

    over("A1 period_bounds: 2026-10 -> 1. 10. az 1. 11. (konec vyloucen), prosinec -> 1. 1. dalsiho roku, neplatne obdobi -> ValueError",
         PB("2026-10") == (datetime.datetime(2026, 10, 1), datetime.datetime(2026, 11, 1)) and PB("2026-12")[1] == datetime.datetime(2027, 1, 1)
         and all(chyba_obdobi(x) for x in ("2026-13", "2026-00", "26-10", "", None, "2026-1", "2026/10", "2026-10-01")), [x for x in ("2026-13", "2026-1", "2026/10") if not chyba_obdobi(x)])

    r = generuj("2026-09")
    j = r.get_json()
    res = {x["dealer_id"]: x for x in j["results"]}
    over("A2 vyuctovani za zari (hranice 1. 10.): u Alfy jen E1 (lhuta skoncila 19. 9.), 100 Kc; u Bety jen F1, 100 Kc; ostatni objednavky Alfy (lhuta v rijnu/listopadu, otevrene vraceni, nezaplacena, cesta dealer, testovaci) nejsou",
         r.status_code == 200 and res[A["id"]]["action"] == "created" and res[A["id"]]["total_czk"] == 100.0 and res[A["id"]]["lines_count"] == 1 and res[B["id"]]["total_czk"] == 100.0 and radky(res[A["id"]]["statement_id"]) == [(E1, "commission", 100.0)]
         and radky(res[B["id"]]["statement_id"]) == [(F1, "commission", 100.0)], j)
    sepA, sepB = res[A["id"]]["statement_id"], res[B["id"]]["statement_id"]
    st = vyuct(sepA)
    over("A3 draft: status navrh, bez cisla, obdobi 2026-09, konec obdobi 30. 9. 23:59:59, snapshot dealera (nazev, ICO, adresa, ucet), radek ma snimek (stav, sazba po polozkach)",
         st["status"] == "navrh" and st["statement_number"] is None and st["period"] == "2026-09" and st["period_end"].startswith("2026-09-30T23:59:59") and st["dealer"]["name"] == "Alfa" and st["dealer"]["ico"] == "11111111"
         and st["dealer"]["bank_account"] == "123456789/0100" and st["lines"][0]["detail"]["lines"][0]["commission_pct"] == 10.0 and st["lines"][0]["detail"]["status"] == "k_vyplate", st)
    over("A4 budouci obdobi a neplatny format -> 400, neexistujici dealer_id -> 404", generuj("2026-12").status_code == 400 and generuj("2026-13").status_code == 400 and generuj("rijen").status_code == 400 and generuj("").status_code == 400
         and generuj("2026-09", dealer_id=99999).status_code == 404, None)

    # ============================================================================================================ B) zivotni cyklus
    print("== B zivotni cyklus")
    over("B1 schvaleni: cislo DV-2026-001, status schvaleno, schvalil/kdy; dalsi schvaleni dostane DV-2026-002 (rada se cisluje po rocich)",
         adm.post(f"/api/admin/dealer-statements/{sepA}/approve").get_json()["statement_number"] == "DV-2026-001" and adm.post(f"/api/admin/dealer-statements/{sepB}/approve").get_json()["statement_number"] == "DV-2026-002"
         and vyuct(sepA)["status"] == "schvaleno" and vyuct(sepA)["approved_by"] == admin_id and vyuct(sepA)["approved_at"], vyuct(sepA)["status"])
    over("B2 schvalene vyuctovani nejde schvalit znovu (409 bad_state) ani prepocitat (generovani stejneho obdobi -> skipped already_approved)",
         adm.post(f"/api/admin/dealer-statements/{sepA}/approve").status_code == 409 and next(x for x in generuj("2026-09").get_json()["results"] if x["dealer_id"] == A["id"])["action"] == "skipped", None)
    CAS[0] = NOW
    j = generuj("2026-10", A["id"]).get_json()["results"][0]
    octA = j["statement_id"]
    over("B3 vyuctovani za rijen (hranice 1. 11.): E2 (lhuta skoncila 26. 10.) ano; E1 uz je vyuctovana (zadna druha provize), E3 (lhuta 11. 11.) a E9 (lhuta 2. 11.) NE i kdyz je dnes uz 5. 11. (rozhoduje konec obdobi), E4 ceka na vraceni",
         j["action"] == "created" and radky(octA) == [(E2, "commission", 100.0)] and j["total_czk"] == 100.0, j)
    over("B4 opakovane generovani bez zmeny dat -> unchanged (zadny novy radek vyuctovani)", generuj("2026-10", A["id"]).get_json()["results"][0] == {"action": "unchanged", "statement_id": octA, "dealer_id": A["id"], "total_czk": 100.0, "lines_count": 1}
         and sql("SELECT COUNT(*) AS n FROM dealer_statements WHERE dealer_id=%s AND period='2026-10'", (A["id"],))[0]["n"] == 1, None)
    vratka(E2, I2, 1, 500.0)                                   # vraceno 1 z 2 ks -> provize 50
    j = generuj("2026-10", A["id"]).get_json()["results"][0]
    octA2 = j["statement_id"]
    over("B5 zmena podkladu (vyrizene vraceni) a novy vypocet: stary draft se oznaci 'zrusen' (nic se nemaze), vznikne novy s provizi 50",
         j["action"] == "replaced" and j["replaced_statement_id"] == octA and octA2 != octA and radky(octA2) == [(E2, "commission", 50.0)] and vyuct(octA)["status"] == "zrusen" and vyuct(octA)["cancelled_note"] == "Přepočteno novým návrhem."
         and sql("SELECT COUNT(*) AS n FROM dealer_statements WHERE dealer_id=%s AND period='2026-10'", (A["id"],))[0]["n"] == 2, j)
    E10 = objednavka(A, dt(10, 3), dt(10, 1), dt(10, 1)); I10 = polozka(E10, 800.0, qty=2)   # lhuta skoncila 15. 10. - vznikla po vygenerovani
    ap = adm.post(f"/api/admin/dealer-statements/{octA2}/approve")
    over("B6 schvaleni ZASTARALEHO navrhu (od generovani pribyla vyplatitelna objednavka) -> 409 stale_draft, nic se neschvali", ap.status_code == 409 and ap.get_json()["code"] == "stale_draft" and vyuct(octA2)["status"] == "navrh", ap.get_json())
    j = generuj("2026-10", A["id"]).get_json()["results"][0]
    octA3 = j["statement_id"]
    over("B7 po novem vygenerovani jsou v navrhu E2 (50) i E10 (80), soucet 130, a schvaleni projde: DV-2026-003",
         sorted(radky(octA3)) == sorted([(E2, "commission", 50.0), (E10, "commission", 80.0)]) and j["total_czk"] == 130.0 and adm.post(f"/api/admin/dealer-statements/{octA3}/approve").get_json()["statement_number"] == "DV-2026-003", j)
    over("B8 nic nebylo smazano: vsechna vyuctovani (zrusene i zive) jsou v tabulce, jedno ZIVE na dealera a obdobi (unikatni klic nad period_active)",
         sql("SELECT COUNT(*) AS n FROM dealer_statements")[0]["n"] == 5 and sql("SELECT COUNT(*) AS n FROM dealer_statements WHERE status='zrusen'")[0]["n"] == 2
         and sql("SELECT COUNT(*) AS n FROM dealer_statement_lines")[0]["n"] == 6, sql("SELECT status, period FROM dealer_statements"))

    # ============================================================================================================ C) korekce
    print("== C korekce po vyuctovani")
    CAS[0] = datetime.datetime(2026, 11, 12, 12, 0, 0)         # lhuta E3 (11. 11.) uz skoncila
    vratka(E2, I2, 1, 500.0)                                   # druhe vraceni E2 -> cela vracena
    sql("UPDATE shop_orders SET status='zrusena' WHERE id=%s", (E1,))   # E1 zrusena po vyplate
    vratka(E10, I10, 1, 400.0, status="posuzovano", resolution=None)   # E10: vraceni jedne ze dvou kusu se teprve posuzuje
    E11 = objednavka(A, dt(10, 30), dt(11, 1), dt(11, 6)); polozka(E11, 1000.0)                  # lhuta skonci 20. 11. (v den generovani 12. 11. jeste bezi)
    j = generuj("2026-11", A["id"]).get_json()["results"][0]
    novA = j["statement_id"]
    over("C1 vyuctovani za listopad: nove E3 (100) a E9 (100) jako 'commission'; korekce E1 -100 (zrusena po vyplate) a E2 -50 (cela vracena); E10 s otevrenym vracenim se NEMENI (ceka se); soucet 50",
         sorted(radky(novA)) == sorted([(E3, "commission", 100.0), (E9, "commission", 100.0), (E1, "adjustment", -100.0), (E2, "adjustment", -50.0)]) and j["total_czk"] == 50.0 and j["lines_count"] == 4, radky(novA))
    adj = [l for l in vyuct(novA)["lines"] if l["line_type"] == "adjustment"]
    over("C2 korekce nese snimek: co uz bylo vyuctovano (already_czk), kam se ma dostat (target_czk 0) a duvod", {l["order_id"]: (l["detail"]["already_czk"], l["detail"]["target_czk"], l["detail"]["reason"]) for l in adj} == {E1: (100.0, 0.0, "order_cancelled"), E2: (50.0, 0.0, "fully_returned")}, adj)
    over("C3 zadne dvojite zahrnuti: objednavky z rijnoveho a zarijoveho vyuctovani (E2, E10, E1) jsou v listopadu jen jako korekce, nikdy jako nova provize", all(t == "adjustment" for (o, t, c) in radky(novA) if o in (E1, E2, E10)) and E10 not in [o for (o, t, c) in radky(novA)], None)
    vratka(E10, I10, 1, 400.0, status="vyrizeno", resolution="refund")      # druhe vraceni E10 je vyrizene, prvni se porad posuzuje
    over("C4 vyrizene castecne vraceni E10 (400) pri JINE otevrene reklamaci: E10 dal ceka (ceka_na_vraceni), korekce se nevytvari -> navrh beze zmeny",
         generuj("2026-11", A["id"]).get_json()["results"][0]["action"] == "unchanged", None)
    over("C5 hranice 'k dnesku, ne ke konci mesice': generovani za listopad 12. 11. nezahrne E11 (lhuta skonci az 20. 11.)", E11 not in [o for (o, t_, c_) in radky(novA)], radky(novA))
    ap = adm.post(f"/api/admin/dealer-statements/{novA}/approve")
    over("C6 schvaleni listopadu projde (podklady se nezmenily): DV-2026-004, soucet 50", ap.status_code == 200 and ap.get_json()["statement_number"] == "DV-2026-004" and vyuct(novA)["total_czk"] == 50.0, ap.get_json())

    # --- zaporny soucet
    C = dealer("Gama", "gama000003", comm=10.0, ico="33333333")
    G1 = objednavka(C, dt(8, 1), dt(8, 5), dt(8, 8)); polozka(G1, 1000.0)
    CAS[0] = NOW
    gs = generuj("2026-09", C["id"]).get_json()["results"][0]["statement_id"]
    adm.post(f"/api/admin/dealer-statements/{gs}/approve")
    sql("UPDATE shop_orders SET status='zrusena' WHERE id=%s", (G1,))
    j = generuj("2026-10", C["id"]).get_json()["results"][0]
    over("C7 dealer, jehoz objednavka byla po vyplate zrusena: navrh za rijen ma jen korekci -100 (zaporny soucet, negative_total)", j["action"] == "created" and j["total_czk"] == -100.0 and j["negative_total"] is True and radky(j["statement_id"]) == [(G1, "adjustment", -100.0)], j)
    n1 = adm.post(f"/api/admin/dealer-statements/{j['statement_id']}/approve")
    over("C8 schvaleni zaporneho souctu bez potvrzeni -> 409 negative_total, s {force: true} projde", n1.status_code == 409 and n1.get_json()["code"] == "negative_total" and vyuct(j["statement_id"])["status"] == "navrh"
         and adm.post(f"/api/admin/dealer-statements/{j['statement_id']}/approve", json={"force": True}).status_code == 200, n1.get_json())

    # --- zaplaceno, zruseni, uvolneni radku
    pa = adm.post(f"/api/admin/dealer-statements/{sepA}/paid", json={"paid_at": "2026-10-20", "note": "prevod 20. 10."})
    CAS[0] = datetime.datetime(2026, 11, 12, 12, 0, 0)
    over("C9 zaplaceno: schvalene -> zaplaceno (datum, poznamka); navrh ani zaplacene znovu oznacit nejde (409), spatne datum 400",
         pa.status_code == 200 and vyuct(sepA)["status"] == "zaplaceno" and vyuct(sepA)["paid_at"].startswith("2026-10-20") and vyuct(sepA)["paid_note"] == "prevod 20. 10." and adm.post(f"/api/admin/dealer-statements/{sepA}/paid").status_code == 409
         and adm.post(f"/api/admin/dealer-statements/{octA3}/paid", json={"paid_at": "20.10.2026"}).status_code == 400, pa.status_code)
    over("C10 zaplacene vyuctovani nejde zrusit (409)", adm.post(f"/api/admin/dealer-statements/{sepA}/cancel").status_code == 409, None)
    cz = adm.post(f"/api/admin/dealer-statements/{novA}/cancel", json={"note": "chyba v podkladech"})
    j = generuj("2026-11", A["id"]).get_json()["results"][0]
    over("C11 zruseni schvaleneho (nezaplaceneho) vyuctovani uvolni jeho radky: nove generovani za listopad je zase obsahne (stejne 4 radky), zruseny radek zustane s poznamkou",
         cz.status_code == 200 and vyuct(novA)["status"] == "zrusen" and vyuct(novA)["cancelled_note"] == "chyba v podkladech" and j["action"] == "created" and j["lines_count"] == 4 and j["total_czk"] == 50.0 and j["statement_id"] != novA, j)
    over("C12 cislo zruseneho vyuctovani se nepouzije znovu: novy listopadovy navrh dostane pri schvaleni DV-2026-00(X) vyssi nez dosavadni maximum", adm.post(f"/api/admin/dealer-statements/{j['statement_id']}/approve").get_json()["statement_number"] > "DV-2026-004", None)

    # --- jiny rok: rada se cisluje po rocich
    Dd = dealer("Delta", "delt000004", comm=10.0, ico="44444444")
    H1 = objednavka(Dd, datetime.datetime(2025, 11, 1), datetime.datetime(2025, 11, 5), datetime.datetime(2025, 11, 8)); polozka(H1, 2000.0)
    h = generuj("2025-12", Dd["id"]).get_json()["results"][0]
    over("C13 obdobi z minuleho roku: vyuctovani za 2025-12 dostane cislo DV-2025-001 (rada se po rocich restartuje), provize 200", h["total_czk"] == 200.0 and adm.post(f"/api/admin/dealer-statements/{h['statement_id']}/approve").get_json()["statement_number"] == "DV-2025-001", h)

    # ============================================================================================================ D) dokument a panel
    print("== D dokument a panel dealera")
    doc = adm.get(f"/api/admin/dealer-statements/{sepB}/document")
    html_b = doc.get_data(as_text=True)
    over("D1 dokument: HTML, cislo a obdobi, vystavovatel, dealer, radek s castkou, soucet 'K fakturaci celkem (bez DPH)', poznamka ze dealer vystavi fakturu; Cache-Control no-store",
         doc.status_code == 200 and doc.mimetype == "text/html" and "DV-2026-002" in html_b and "2026-09" in html_b and "LOGIMAN s.r.o." in html_b and "100,00 Kč" in html_b and "K fakturaci celkem (bez DPH)" in html_b
         and "vystaví dealer fakturu" in html_b and doc.headers.get("Cache-Control") == "private, no-store", doc.status_code)
    over("D2 nazev dealera s HTML znackami se v dokumentu ESCAPUJE (zadny <script>), castky maji ceske formatovani (1 234,50)", "<script>alert(1)</script>" not in html_b and "&lt;script&gt;alert(1)&lt;/script&gt; &amp; spol." in html_b
         and ds._fmt(1234.5) == "1 234,50" and ds._fmt(-100) == "-100,00", None)
    dnavrh = adm.get(f"/api/admin/dealer-statements/{octA}/document").get_data(as_text=True)
    F2 = objednavka(B, dt(9, 20), dt(10, 1), dt(10, 2)); polozka(F2, 500.0)          # Beta: rijnovy navrh (neschvaleny)
    bn = generuj("2026-10", B["id"]).get_json()["results"][0]
    dnavrh2 = adm.get(f"/api/admin/dealer-statements/{bn['statement_id']}/document").get_data(as_text=True)
    over("D3 dokument zruseneho vyuctovani ma razitko 'ZRUŠENO', neschvaleneho navrhu 'NÁVRH – zatím není schváleno' a cislo '(návrh)'", "ZRUŠENO" in dnavrh and "NÁVRH – zatím není schváleno" in dnavrh2 and "(návrh)" in dnavrh2 and "ZRUŠENO" not in dnavrh2, (bn, "(návrh)" in dnavrh2))
    lst = panel_a.get("/api/dealer/statements").get_json()["statements"]
    over("D4 panel Alfy: vidi jen SCHVALENA a ZAPLACENA vyuctovani sve (zari zaplaceno, rijen schvaleno, listopad schvaleno), ne navrhy a zrusena, ne cizi (Betino, Gama, Delta)",
         {s["period"] + ":" + s["status"] for s in lst} == {"2026-09:zaplaceno", "2026-10:schvaleno", "2026-11:schvaleno"} and all(s["dealer"]["name"] == "Alfa" for s in lst), [(s["period"], s["status"]) for s in lst])
    over("D5 panel: detail s radky a dokument vlastniho schvaleneho vyuctovani 200; navrh, zruseny, cizi a neexistujici 404; ucet bez dealera 404 not_a_dealer; nepřihlášený 401",
         panel_a.get(f"/api/dealer/statements/{sepA}").status_code == 200 and len(panel_a.get(f"/api/dealer/statements/{octA3}").get_json()["statement"]["lines"]) == 2 and panel_a.get(f"/api/dealer/statements/{octA3}/document").status_code == 200
         and all(panel_a.get(f"/api/dealer/statements/{x}").status_code == 404 and panel_a.get(f"/api/dealer/statements/{x}/document").status_code == 404 for x in (octA, octA2, sepB, gs, 99999))
         and zakaznik.get("/api/dealer/statements").status_code == 404 and zakaznik.get("/api/dealer/statements").get_json()["code"] == "not_a_dealer" and nepr.get("/api/dealer/statements").status_code == 401, None)
    over("D6 panel nevidi osobni udaje zakaznika v zadne odpovedi (e-mail, jmeno)", not re.search(r"zakaznik@|Jan Novak", panel_a.get(f"/api/dealer/statements/{octA3}").get_data(as_text=True) + panel_a.get(f"/api/dealer/statements/{octA3}/document").get_data(as_text=True)), None)
    over("D7 panel Bety vidi jen sve (zari), ne Alfiny", [s["period"] for s in panel_b.get("/api/dealer/statements").get_json()["statements"]] == ["2026-09"], None)

    # ============================================================================================================ E) opravneni, nic se nemaze, mutace
    print("== E opravneni, nezapisuje mimo vyuctovani, mutace")
    over("E1 admin endpointy: nepřihlášený 401, zakaznik (role user) 403 (list, detail, dokument, generate, approve, paid, cancel)",
         all(nepr.get(u).status_code == 401 for u in ("/api/admin/dealer-statements", f"/api/admin/dealer-statements/{sepA}", f"/api/admin/dealer-statements/{sepA}/document"))
         and all(zakaznik.get(u).status_code == 403 for u in ("/api/admin/dealer-statements", f"/api/admin/dealer-statements/{sepA}", f"/api/admin/dealer-statements/{sepA}/document"))
         and all(zakaznik.post(u, json={"period": "2026-09"}).status_code == 403 for u in ("/api/admin/dealer-statements/generate", f"/api/admin/dealer-statements/{octA3}/approve", f"/api/admin/dealer-statements/{octA3}/paid", f"/api/admin/dealer-statements/{octA3}/cancel")), None)
    lst_all = adm.get("/api/admin/dealer-statements").get_json()["statements"]
    over("E2 admin seznam: bez zrusenych (vychozi), ?all=1 je ukaze, filtry dealer_id/period/status, jmeno dealera v radcich",
         all(s["status"] != "zrusen" for s in lst_all) and any(s["status"] == "zrusen" for s in adm.get("/api/admin/dealer-statements?all=1").get_json()["statements"])
         and {s["dealer_id"] for s in adm.get(f"/api/admin/dealer-statements?dealer_id={B['id']}").get_json()["statements"]} == {B["id"]}
         and {s["period"] for s in adm.get("/api/admin/dealer-statements?period=2026-09").get_json()["statements"]} == {"2026-09"} and all(s["status"] == "navrh" for s in adm.get("/api/admin/dealer-statements?status=navrh").get_json()["statements"])
         and any(s["dealer_name"] == "Alfa" for s in lst_all), None)
    over("E3 neexistujici vyuctovani 404 u detailu, dokumentu, schvaleni, zaplaceni i zruseni", all(c_ == 404 for c_ in (adm.get("/api/admin/dealer-statements/99999").status_code, adm.get("/api/admin/dealer-statements/99999/document").status_code,
         adm.post("/api/admin/dealer-statements/99999/approve").status_code, adm.post("/api/admin/dealer-statements/99999/paid").status_code, adm.post("/api/admin/dealer-statements/99999/cancel").status_code)), None)
    zdroj = open(ds.__file__, encoding="utf-8").read()
    over("E4 modul nic nemaze a neposila e-maily: zadny DELETE FROM / DROP / TRUNCATE, zadne send_email/smtp", not re.search(r"DELETE\s+FROM|DROP\s+TABLE|TRUNCATE|send_email|smtp", zdroj, re.I), None)
    over("E5 modul zapisuje jen do dealer_statements a dealer_statement_lines (zadny UPDATE/INSERT do objednavek, polozek, vratek, dealeru)", sorted(set(re.findall(r"(?:INSERT INTO|UPDATE)\s+(\w+)", zdroj))) == ["dealer_statement_lines", "dealer_statements"], sorted(set(re.findall(r"(?:INSERT INTO|UPDATE)\s+(\w+)", zdroj))))

    def mutant(funkce, stare, nove):
        t = ast.parse(zdroj)
        node = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == 1, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x"
        ns = dict(vars(ds))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    with real.cursor() as c:
        Eps = dealer("Eps1", "epsi000005", comm=10.0, ico="55555555")
        Eps2 = dealer("Eps2", "epsi000006", comm=10.0, ico="66666666")
        for d_ in (Eps, Eps2):
            polozka(objednavka(d_, dt(10, 5), dt(10, 15), dt(10, 19)), 1000.0)         # lhuta skonci 2. 11. = po konci rijna
        spravne = ds.generate_for_dealer(c, Eps, "2026-10", None, now=NOW)
        chybne = mutant("generate_for_dealer", "as_of = min(now, end_excl)", "as_of = now")(c, Eps2, "2026-10", None, now=NOW)
        real.commit()
        over("E6 mutace: vyuctovani ke dni generovani misto ke KONCI mesice by do rijna zatahlo provizi, jejiz lhuta skoncila az 2. 11. (rijen: no_lines, mutant: created) -> test B3 ji zachyti",
             spravne["action"] == "no_lines" and chybne["action"] == "created", (spravne, chybne))
        Aq = sql("SELECT * FROM dealers WHERE id=%s", (A["id"],))[0]
        CAS[0] = datetime.datetime(2026, 11, 12, 12, 0, 0)
        spravne_radky = ds.build_lines(c, Aq, CAS[0], None)
        chybne_radky = mutant("build_lines", "delta = round(target - already, 2)", "delta = round(target, 2)")(c, Aq, CAS[0], None)
        over("E7 mutace: bez odecteni uz vyuctovaneho by se provize vyuctovaly podruhe (spravne zadny novy radek, mutant radky ma) -> test C3 ji zachyti", len(spravne_radky) == 0 and len(chybne_radky) >= 2, (len(spravne_radky), len(chybne_radky)))
        m3 = mutant("_already_included", "st.status <> 'zrusen'", "1=1")
        over("E8 mutace: zrusena vyuctovani se ctou jako uz vyuctovana (radky by se po zruseni neuvolnily) - E3 je ve zrusenem a ve schvalenem listopadu: spravne 100, mutant 200 -> test C11 ji zachyti",
             ds._already_included(c, E3) == 100.0 and m3(c, E3) == 200.0, (ds._already_included(c, E3), m3(c, E3)))
finally:
    with real.cursor() as cur:
        for t in TEMP_ZE_SQL + TEMP_LIKE + tuple(f"_tpl_{x}" for x in TEMP_LIKE):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (objednavky, polozky, vratky, historie, nastaveni, audit_log) a seznam tabulek vyuctovani jsou po testu beze zmeny", po == pred, (pred, po))
ok = sum(vysl)
print(f"\nVYSLEDEK dealersky program krok 3 - mesicni vyuctovani: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
