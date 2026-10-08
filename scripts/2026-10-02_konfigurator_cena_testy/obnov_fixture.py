#!/opt/konfigurator/api/venv/bin/python
"""Obnova fixture katalogu dilu pro test_cena_parita.py (bot5, 2026-10-02) - DB JEN KE CTENI.

Fixture = to, co vidi scena: odpoved GET /api/katalog (po aplikaci koeficientu) a GET /api/pricing-config, tedy NEZAVISLE na
configurator_price.load_ctx (ten se zvlast porovnava s temito endpointy v test_cena_db.py). Do fixture jdou jen dily s cenou
relevantni pro konfigurace (zdroj profil a product, ne karoserie car_body_*), pole v tvaru, jaky pouziva scene.html (CATALOG).
Endpointy se volaji jako holé funkce (__wrapped__ obejde @staff_required/@login_required) uvnitr test_request_context.

Spusteni (DB prihlaseni pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-02_konfigurator_cena_testy/obnov_fixture.py
"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)
import app as A  # noqa: E402
import admin_settings as S  # noqa: E402
import production_overview as PO  # noqa: E402

with A.app.test_request_context("/api/katalog"):
    katalog = A.katalog.__wrapped__().get_json()
with A.app.test_request_context("/api/pricing-config"):
    pricing = S.pricing_config.__wrapped__().get_json()

scene = open(os.path.join(HERE, "..", "..", "webapp", "scene.html"), encoding="utf-8").read()
scene_verze = int(re.search(r"^const JOINT_RULE_VERSION = (\d+);", scene, re.M).group(1))
assert scene_verze == PO.CURRENT_JOINT_RULE_VERSION, (scene_verze, PO.CURRENT_JOINT_RULE_VERSION)

dily = []
for p in katalog["parts"]:
    if p.get("source") not in ("profil", "product"):
        continue
    dily.append({
        "id": p["id"], "name": p["name"], "layer": p["layer"], "sku": p.get("sku"),
        "length_mm": p.get("length_mm"), "cross_section_mm": p.get("cross_section_mm"),
        "weight_kg": p.get("weight_kg_approx"), "price_czk": p.get("price_czk_approx_PLACEHOLDER"),
        "price_per_cut_czk": p.get("price_per_cut_czk"), "is_board_material": bool(p.get("is_board_material")),
        "scene_coef": bool(p.get("scene_coef")), "source": p["source"], "unit": p.get("unit"), "price_basis": p.get("price_basis"),
    })

out = {
    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "price_coefficient": katalog["price_coefficient"],
    "joint_rule_version": scene_verze,
    "pricing": pricing,
    "parts": dily,
}
cesta = os.path.join(HERE, "katalog_fixture.json")
with open(cesta, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"fixture zapsana: {cesta} - dilu {len(dily)} (z toho profilu {sum(1 for d in dily if d['length_mm'] and d['cross_section_mm'] and d['cross_section_mm'][0] is not None)}, "
      f"desek {sum(1 for d in dily if d['is_board_material'])}, s cenou {sum(1 for d in dily if d['price_czk'] is not None)}), "
      f"koeficient {katalog['price_coefficient']}, verze pravidel spoju {scene_verze}")
