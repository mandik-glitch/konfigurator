#!/opt/konfigurator/api/venv/bin/python
"""Mutacni kontrola testu test_offer_markup_requests.py (bot16, 2026-10-07): do KOPIE modulu api/offer_markup_requests.py se vnese jedna chyba a test MUSI selhat
na ocekavanych kontrolach (kandidat se predava env OMR_PY, zivy modul se nemeni). Nezachycena mutace = test nic nehlida.
Spusteni stejne jako test (systemd-run s EnvironmentFile=/opt/konfigurator/api/.env, --working-directory=<REPO>)."""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MODUL = os.path.join(REPO, "api", "offer_markup_requests.py")
TEST = os.path.join(HERE, "test_offer_markup_requests.py")

# (nazev, puvodni text v modulu, nahrada, ocekavana selhani - podretezce nazvu kontrol[, pocet vyskytu puvodniho textu - vychozi 1[, modul: "omr" (vychozi) | "so" = api/scene_offers.py]])
MUTACE = [
    ("gating: kazda nabidka umi zakreslovani", 'return opts.get("source") == "configurator" or opts.get("vandr_single_drawing") is True', "return True",
     ["B nabidka ze sceny", "E2 nabidka ze sceny", "E5 markup_requests_enabled(jiny zdroj)"]),
    ("admin token se neodmita (403 pryc)", 'if hashlib.sha256(token.encode()).hexdigest() == offer["admin_view_token_hash"]:', "if False:", ["E1 ADMIN token"]),
    ("honeypot vypnuty", 'if (request.form.get("website") or "").strip():', "if False:", ["F1 honeypot"]),
    ("rate limit vypnuty", 'limited = scene_offers._public_offer_rate_limited(token, "markup", 3, 8)', "limited = None", ["F2 rate limit na token", "F3 rate limit na IP"]),
    ("uklid souboru pri chybe vypnuty", "                os.remove(cesta)\n", "                pass\n", ["G1 pad pri e-mailech", "G2 pad pri kopii do galerie"]),
    ("priznak/e-maily: odeslani primo misto fronty (status sent)", "'pending','auto')", "'sent','auto')", ["C9 e-maily jen do FRONTY"], 2),
    ("neexpirovana kontrola vynechana (expirovana nabidka projde)", 'if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():', 'if not offer or not offer["is_active"]:', ["E3 expirovana nabidka"]),
    ("e-mail: ochrana pred novym radkem vypnuta", 'if not _EMAIL_RE.fullmatch(email):', 'if "@" not in email or "." not in email.split("@")[-1]:', ["D e-mail s novym radkem", "D e-mail s mezerou"]),
    ("popisek pohledu se neslucuje na jeden radek", 'out.append({"label": " ".join((label or "").split()), "page": page,', 'out.append({"label": (label or "").strip(), "page": page,', ["C13 popisek pohledu s novym radkem"]),
    ("limit 6 pohledu zruseny", "not (1 <= len(views_raw) <= pm.MAX_VIEWS)", "not (1 <= len(views_raw) <= 99)", ["D 7 pohledu (limit 6)"]),
    # ---- integrace s prohlizecem (sekce J: skutecny surovy POST z online nabidky): zmena kontraktu na strane backendu, ktera se tyka JEN vlastnosti toho skutecneho pozadavku
    # (view.key 'bokorys' = 7 znaku, znacka typu 'pen', popisek 'Levá strana' = 11 znaku), musi shodit sekci J (starsi sekce pouzivaji kratsi klice/popisky a znacku 'ellipse')
    ("kontrakt: klic pohledu (view.key) delsi nez 6 znaku se odmita ('bokorys')", "MAX_KEY_LEN = 80", "MAX_KEY_LEN = 6", ["J1 surovy POST"]),
    ("kontrakt: znacky typu pen (tuzka z prohlizece) se odmitaji", 'marks, marks_err = pm._validate_marks(json.dumps(v.get("marks") or []))',
     'marks, marks_err = pm._validate_marks(json.dumps(v.get("marks") or []))\n        if any(m.get("kind") == "pen" for m in (marks or [])):\n            marks_err = "mutace: pen"', ["J1 surovy POST"]),
    ("kontrakt: popisek pohledu (label) delsi nez 10 znaku se odmita ('Levá strana')", "MAX_LABEL_LEN = 120", "MAX_LABEL_LEN = 10", ["J1 surovy POST"]),
    ("integrita: priloha poptavky se ulozi o bajt kratsi", "quotes.save_lead_attachment(cur, message_id, lead_id, nazev, mime, data)", "quotes.save_lead_attachment(cur, message_id, lead_id, nazev, mime, data[:-1])", ["J5 prilohy ve slozce poptavky"]),
    ("integrita: kopie v galerii se ulozi o bajt kratsi", "fh.write(data)", "fh.write(data[:-1])", ["J6 galerie poptavky"]),
    # ---- scene_offers.py (zmeny pro zakreslovani a stranku Vandr vykresu)
    ("scene_offers: drawings_vandr chybi v OFFER_PAGE_KEYS", '"drawings_2", "drawings_vandr", "view_3d",', '"drawings_2", "view_3d",', ["I0 OFFER_PAGE_KEYS", "I1 Dotaz", "I2 /event", "I4 PUT markups", "I5 admin statistiky"], 1, "so"),
    ("scene_offers: markup_request_draw chybi v CLICK_TARGETS", '    "markup_request_draw",  # zakaznik otevrel kreslici nastroj (klik "Zakreslit zmenu")\n', "", ["I0b CLICK_TARGETS", "I3 /event"], 1, "so"),
    ("scene_offers: priznak markup_requests vzdy False", "markup_requests = bool(markup_requests_enabled(offer))", "markup_requests = False", ["B nabidka z konfigurace stolu, klientsky token", "B nabidka z Vandr karty"], 1, "so"),
]

MODULY = {"omr": (MODUL, "OMR_PY"), "so": (os.path.join(REPO, "api", "scene_offers.py"), "SO_PY")}
zive = 0
for nazev, puvodni, nahrada, ocekavane, *dalsi in MUTACE:
    pocet = dalsi[0] if dalsi else 1
    soubor, promenna = MODULY[dalsi[1] if len(dalsi) > 1 else "omr"]
    zdroj = open(soubor, encoding="utf-8").read()
    if zdroj.count(puvodni) != pocet:
        print(f"CHYBA mutace '{nazev}': puvodni text se v {os.path.basename(soubor)} nenasel presne {pocet}x ({zdroj.count(puvodni)}x)")
        sys.exit(2)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(zdroj.replace(puvodni, nahrada))
        cesta = fh.name
    try:
        p = subprocess.run([sys.executable, TEST], env={**os.environ, promenna: cesta}, capture_output=True, text=True, timeout=900)
    finally:
        os.unlink(cesta)
    selhalo = [l[5:] for l in p.stdout.splitlines() if l.startswith("FAIL ")]
    chybi = [o for o in ocekavane if not any(o in s for s in selhalo)]
    zachyceno = p.returncode != 0 and not chybi
    zive += 0 if zachyceno else 1
    print(("ZACHYCENA   " if zachyceno else "NEZACHYCENA ") + nazev + f"  (selhalo {len(selhalo)} kontrol" + (f"; chybi ocekavane: {chybi}" if chybi else "") + (f"; rc={p.returncode}" if p.returncode not in (0, 1) else "") + ")")
    if p.returncode not in (0, 1):
        print("   " + (p.stdout + p.stderr)[-400:].replace("\n", "\n   "))
print(f"\nVYSLEDEK mutace: {len(MUTACE) - zive}/{len(MUTACE)} zachyceno")
sys.exit(1 if zive else 0)
