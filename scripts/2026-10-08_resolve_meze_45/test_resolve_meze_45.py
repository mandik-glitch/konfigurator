#!/opt/konfigurator/api/venv/bin/python
"""Test: `options` v odpovedi resolve() nesou meze posuvniku PODLE SYSTEMU (system 45 "Robustni": hloubka az 2500 mm; ostatni 1500) - nalez bot16 2026-10-08: `POST /api/shop/configurator/resolve`
pro kartu #5353 (system 45) vracel `options.d = {min: 400, max: 1500}` (globalni rozsah misto systemoveho), zatimco schema (`GET /api/shop/products/5353/configurator`) ma `slider.max = 2500`;
klient se rida `options`, takze v embedu / na karte / v mini-shopu nesla hloubka nad 1500 mm nastavit (hodnota se orizla a napoveda ukazovala "Povoleno od 400 do 1500 mm").

Hlida: (1) funkce `resolve(sel, lang, system=...)`: system 45 + d 2500 -> vybrana hloubka 2500 a `options.d.max` 2500; systemy 30 / 35 / 40 a SSE hloubku orizou na 1500 a `options.d.max` 1500; (2) STEJNE pres skutecnou trasu
`POST /api/shop/configurator/resolve` (Flask test client, cteni; karty #5353 = system 45, #4954 = system 40, #4934 = system 30); (3) `options.d` odpovida meze posuvniku ve schematu karty (`slider.max`) u vsech tri karet;
(4) ostatni posuvniky (w, h, ov, arm) maji meze jako dosud.

Spusteni (DB pres systemd): systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRIVATE_FILES_DIR=/tmp/pf_meze45 \\
   --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_resolve_meze_45/test_resolve_meze_45.py        (kandidat: MEZE_DIR=<koren prekryvu s api/>)"""
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.path.join(os.environ["MEZE_DIR"], "api") if os.environ.get("MEZE_DIR") else os.path.join(REPO, "api")
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import app as appmod  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_shop as SH  # noqa: E402
finally:
    threading.Thread.start = _o

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


print("## 1) funkce resolve(): meze podle systemu")
for system, ocek in ((45, 2500), (40, 1500), (35, 1500), (30, 1500)):
    r = SH.resolve({**SH.vychozi_vyber(system), "d": 2500}, "cs", system=system)
    over(f"1.{system} system {system}: d=2500 -> vybrano {ocek}, options.d = 400..{ocek}", r["selection"]["d"] == ocek and r["options"]["d"] == {"min": 400, "max": ocek}, {"d": r["selection"]["d"], "options": r["options"]["d"]})
r = SH.resolve({**SH.vychozi_vyber(45), "d": 300}, "cs", system=45)
over("1.45b system 45: d=300 se zvedne na 400 (spodni mez), options.d min 400", r["selection"]["d"] == 400 and r["options"]["d"]["min"] == 400, r["selection"]["d"])

print("\n## 2) skutecna trasa POST /api/shop/configurator/resolve")
c = appmod.app.test_client()
KARTY = ((5353, 45, 2500), (4954, 40, 1500), (4934, 30, 1500))
for pid, system, ocek in KARTY:
    sch = c.get(f"/api/shop/products/{pid}/configurator")
    if sch.status_code != 200:
        over(f"2.{pid} karta #{pid} (system {system}): schema je k dispozici", False, sch.status_code)
        continue
    schema = sch.get_json()
    slot_d = next((sl for sl in schema["slots"] if sl["id"] == "d"), None)
    slider_d = slot_d["slider"] if slot_d else None
    r = c.post("/api/shop/configurator/resolve", json={"product_id": pid, "selection": {**SH.vychozi_vyber(system), "d": 2500}})
    j = r.get_json() or {}
    od = (j.get("options") or {}).get("d")
    over(f"2.{pid} karta #{pid} (system {system}): resolve d=2500 -> options.d max {ocek}, vybrana hloubka {ocek}", r.status_code == 200 and od == {"min": 400, "max": ocek} and (j.get("selection") or {}).get("d") == ocek, {"status": r.status_code, "options.d": od, "d": (j.get("selection") or {}).get("d")})
    over(f"2.{pid}b karta #{pid}: options.d odpovida posuvniku ve schematu (slider.max {slider_d and slider_d.get('max')})", slider_d is not None and od is not None and od["max"] == slider_d["max"] and od["min"] == slider_d["min"], {"schema": slider_d and {k: slider_d.get(k) for k in ("min", "max")}, "options": od})
    ostatni = {sid: j["options"][sid] for sid in ("w", "h", "ov", "arm")}
    ocek_o = {"w": {"min": int(S.ROZSAH["sirka"][0]), "max": int(S.ROZSAH["sirka"][1])}, "h": {"min": int(S.ROZSAH["vyska"][0]), "max": int(S.ROZSAH["vyska"][1])}, "ov": {"min": int(S.ROZSAH["presah"][0]), "max": int(S.ROZSAH["presah"][1])}}
    over(f"2.{pid}c karta #{pid}: posuvniky w / h / ov maji meze jako dosud", all(ostatni[k] == ocek_o[k] for k in ocek_o), ostatni)

print(f"\n{sum(vysl)}/{len(vysl)} OK")
sys.exit(0 if all(vysl) else 1)
