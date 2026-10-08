#!/opt/konfigurator/api/venv/bin/python
"""Ma popisek koeficientu Doguskalip (admin.html x2, skladova karta) pravdu? (bot5, 2026-10-01; nalez bot16 pres bot3)
Popisky tvrdi: koeficient kategorie (content_categories.dogus_price_coefficient) pocita E-SHOPOVOU cenu z Dogus USD:
USD x kurz Fio (prodej) x koeficient, u tyci x 3, nahoru na cele Kc; casovac jede kazdou noc ve 3:20; kategorie bez
koeficientu se preskoci a hlasi to QA (Dashboard, "Navrhy na doplneni"); scena cte e-shopovou cenu (profil / 3).
Tenhle test overuje kazde z tvrzeni PROTI ZDROJI (kod/casovac), ne proti textu popisku - kdyby se zdroj zmenil
(napr. casovac zase tydenni, jina zaokrouhlovaci pravidla), test selze a popisky je treba opravit.
Bez DB, nic nezapisuje.   Spusteni: api/venv/bin/python3 test_popisky_dogus_fakta.py
"""
import ast
import importlib.util
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def cti(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as f:
        return f.read()


# --- 1) vzorec (jedno misto pravdy _dogus_formula_kc v admin_profily.py; stejny vzorec ma skript noci)
src = cti("api/admin_profily.py")
strom = ast.parse(src)
fn = next(n for n in ast.walk(strom) if isinstance(n, ast.FunctionDef) and n.name == "_dogus_formula_kc")
ns = {"math": math}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "_dogus_formula_kc", "exec"), ns)
f = ns["_dogus_formula_kc"]
over("F1 tyc (tyc_3m): USD x kurz x koeficient x 3, nahoru - 1,01 USD x 22 x 1,25 x 3 = 83,325 -> 84 Kc", f("tyc_3m", 1.01, 22.0, 1.25)[0] == 84, f("tyc_3m", 1.01, 22.0, 1.25))
over("F2 tyc: kratke desetinne misto se zaokrouhli NAHORU (ne matematicky): 0,5 x 22 x 1 x 3 = 33,0 -> 33; 0,51 -> 34",
     f("tyc_3m", 0.5, 22.0, 1.0)[0] == 33 and f("tyc_3m", 0.51, 22.0, 1.0)[0] == 34, (f("tyc_3m", 0.5, 22.0, 1.0), f("tyc_3m", 0.51, 22.0, 1.0)))
over("F3 metraz a kus: BEZ x 3, nahoru - 1,01 x 22 x 1,25 = 27,775 -> 28", f("metraz", 1.01, 22.0, 1.25)[0] == 28 and f("kus", 1.01, 22.0, 1.25)[0] == 28, (f("metraz", 1.01, 22.0, 1.25), f("kus", 1.01, 22.0, 1.25)))
over("F4 zaokrouhleni nahoru i u kusu (0,04 USD x 22 x 1,2 = 1,056 -> 2 Kc)", f("kus", 0.04, 22.0, 1.2)[0] == 2, f("kus", 0.04, 22.0, 1.2))

# --- 2) skript noci pocita stejne a preskakuje kategorie bez koeficientu
skript = cti("scripts/2026-08-09_dogus_price_recompute.py")
over("S1 skript preskoci kategorii bez koeficientu (chybova hlaska, cena zustane)", "PRESKOCENO (chybi koeficient kategorie)" in skript and "kategorie nema dogus_price_coefficient nastaveny" in skript)
over("S2 skript: tyc_3m = USD x kurz x koeficient x 3, metraz a kus bez x 3",
     "list_price_usd * fio_rate * coef * 3.0" in skript and "list_price_usd * fio_rate * coef)" in skript)
over("S3 skript zaokrouhluje nahoru (math.ceil) a pise e-shopovou cenu shop_products.price_czk_placeholder",
     re.search(r"def zaokrouhli_cenu[^\n]*\n(?:[^\n]*\n){0,12}?\s*return math\.ceil", skript) is not None and "UPDATE shop_products SET price_czk_placeholder=%s" in skript)

# --- 3) scena cte e-shopovou cenu profilu / 3 (a koeficient sceny je jiny nastaveni)
app = cti("api/app.py")
over("A1 katalog sceny: cena profilu za metr = shop_products.price_czk_placeholder / 3", 'round(float(r["price_czk_placeholder"]) / 3.0, 2)' in app)
over("A2 koeficient sceny je SAMOSTATNE nastaveni app_settings.scene_price_coefficient (ne dogus_price_coefficient)",
     'SCENE_PRICE_COEF_KEY = "scene_price_coefficient"' in app and 'SCENE_PRICE_COEF_KEY = "dogus_price_coefficient"' not in app)

# --- 4) QA hlidac chybejiciho koeficientu a kam se hlasi
spec = importlib.util.spec_from_file_location("qa_checks_test", os.path.join(REPO, "api", "qa_checks.py"))
sys.path.insert(0, os.path.join(REPO, "api"))
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
over("Q1 QA kontrola missing_dogus_price_coefficient existuje a je v kategorii 'doplnit'",
     "missing_dogus_price_coefficient" in qa.CHECKS and qa.CHECK_CATEGORY.get("missing_dogus_price_coefficient") == "doplnit", qa.CHECK_CATEGORY.get("missing_dogus_price_coefficient"))
dash = cti("webapp/admin/js/dashboard.js")
html = cti("webapp/admin.html")
m = re.search(r'doplnit:\s*\{\s*panel:\s*"(\w+)"', dash)
panel = m.group(1) if m else None
nadpis = re.search(r'id="%s"[^>]*>\s*<div[^>]*>\s*<span class="dash-panel-title">([^<]*)' % re.escape(panel or "x"), html)
over("Q2 kategorie 'doplnit' se na Dashboardu ukazuje v panelu s nadpisem 'Navrhy na doplneni'",
     panel is not None and "Návrhy na doplnění" in html and panel == "qaDataPanel" and 'id="qaDataTotal"' in html, (panel, nadpis.group(1) if nadpis else None))

# --- 5) casovac: kazdou noc ve 3:20 (ne tydne)
try:
    t = subprocess.run(["systemctl", "cat", "konfigurator-refresh-dogus-profile-prices.timer"], capture_output=True, text=True, timeout=20).stdout
except Exception as e:  # noqa: BLE001
    t = ""
    print("(systemctl nedostupny:", e, ")")
cal = re.search(r"^OnCalendar=(.*)$", t, re.M)
over("T1 casovac konfigurator-refresh-dogus-profile-prices.timer: OnCalendar = kazdy den 03:20 (ne jednou tydne)",
     cal is not None and cal.group(1).strip() == "*-*-* 03:20:00", cal.group(1) if cal else t[:200])

ok = sum(vysl)
print(f"\n{ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
