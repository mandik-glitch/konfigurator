#!/usr/bin/env python3
"""bot28, 2026-09-01: append a note to car_body_placement_methods.id=1
about the "which wall does the rack actually touch" gap found while
building the Jumpy family (CI13-CI26). See KOMPONENTY_EUROBOXY.md /
AGENTS_LOG.md for full narrative. Read-modify-write of the definition
JSON, version bump, verified_by left as the numeric-verification bot
(never 'robert', per WORKFLOW.md discipline)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pymysql
from _env import load_env as _load_env

_cfg = _load_env()
conn = pymysql.connect(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
)
cur = conn.cursor()
cur.execute("SELECT definition, version FROM car_body_placement_methods WHERE id=1")
row = cur.fetchone()
definition = json.loads(row[0])
old_version = row[1]

note_key = "vylouceni_bocniho_dvernich_otvoru_kterou_stenu_testovat_2026_09_01"
if note_key in definition:
    print("Note already present, nothing to do.")
    sys.exit(0)

definition[note_key] = {
    "zjisteni": (
        "Detekce dveřního otvoru (klíč vylouceni_bocniho_dvernich_otvoru_2026_09_02 výše) "
        "testuje vertex-gap heuristiku na jmenovitě zadané straně stěny, ale VŠECHNY dosud "
        "napsané skripty (vč. bot26's scripts/2026-09-03_class4_doorvoid_audit.js, celokatalogovy "
        "audit 48 kandidátů) testují NAPEVNO jen _R_D.glb, bez ohledu na to, na které straně "
        "(L, nebo R_D) regál skutečně stojí. Zjištěno při stavbě Jumpy CI13-CI26 (bot25/bot28, "
        "2026-09-01): regál je postaven proti _L.glb (X range rack ⊂ wallL bbox X, ne wallR), "
        "ale vertex-gap sken _R_D.glb hlásil 'nohu v otvoru' na 6 z 8 karoserií - VŠECHNY "
        "falešně pozitivní, potvrzeno raycastingem (viz níže)."
    ),
    "pravidlo": (
        "Než se kterýkoli díl nohy prohlásí za 'uvnitř dveřního otvoru', NEJDŘÍV zjisti, "
        "PROTI KTERÉ stěně (_L nebo _R_D) regál skutečně stojí - porovnej X-rozsah "
        "zapsaných dílů (part_id != car_body_*) s bounding-boxem obou stěn (car_bodies "
        "_L.glb vs _R_D.glb). Testuj dveřní otvor VÝHRADNĚ na téhle stěně - ne automaticky "
        "na _R_D. FO31/VW25 (původní nález, viz vylouceni_bocniho_dvernich_otvoru_2026_09_02) "
        "měly regál skutečně na _R_D straně, proto tam test na tuhle stěnu byl správný - "
        "ale to není univerzální pravidlo napříč celým katalogem."
    ),
    "ground_truth_metoda_doporucena": (
        "Vertex-gap heuristika (mezera >150mm mezi Z-seřazenými vertexy) je jen návrh "
        "kandidáta, NE důkaz - u řídce tesselované geometrie (velký plochý čtyřúhelník bez "
        "vnitřních vertexů) dává i FALEŠNÉ POZITIVY na zcela plné stěně (přesně tenhle případ "
        "u Jumpy - jedna z kandidátních mezer měla ve skutečnosti 0 % skutečné díry). "
        "Doporučený ground-truth krok před jakoukoli opravou: hustý rastr raycastů "
        "(THREE.Raycaster) zvenčí vozidla napříč celým Y∈[200,900] × sporným Z-rozsahem, "
        "kolmo na stěnu - hitFraction≈0 = skutečná díra, hitFraction≈1 = plná stěna, nic mezi "
        "tím prakticky nenastalo v žádném dosud změřeném případě. `scripts/tmp_2026-09-02_"
        "verify_raycast_check.js` (bot28, argumenty: <car_body_base> <zLo> <zHi>) je hotová, "
        "znovupoužitelná implementace."
    ),
    "dopad_na_otevreny_ukol": (
        "TASKS.md úkol 'Audit zbylých ~113 eurobox regálů... otvoru bočních dveří' a "
        "KOMPONENTY_EUROBOXY.md sekce 'Třída 4' (48 kandidátů z bot26's celokatalogového "
        "auditu) POTŘEBUJÍ přepočet s touto opravou dřív, než se kterýkoli z 48 kandidátů "
        "bude opravovat - současný seznam pravděpodobně obsahuje falešné pozitivy u "
        "karoserií, kde regál stojí na _L straně (jako celá Jumpy rodina by v tomhle seznamu "
        "skončila, kdyby byla postavena dřív a auditována týmž skriptem), a teoreticky může "
        "chybět reálné nálezy u karoserií, kde je skutečný otvor na _L straně a regál na ní "
        "taky stojí (nikdy netestováno, protože skript vždy čte jen _R_D). NEOPRAVENO touto "
        "session (mimo její rozsah) - zapsáno do TASKS.md pro navazujícího bota."
    ),
    "zdroj": "bot25 (stavba)/bot28 (nezávislé přeověření), 2026-09-01, stavba Jumpy CI13-CI26",
}

new_version = old_version + 1
cur.execute(
    "UPDATE car_body_placement_methods SET definition=%s, version=%s WHERE id=1",
    (json.dumps(definition, ensure_ascii=False), new_version),
)
conn.commit()
print(f"OK: car_body_placement_methods.id=1 version {old_version} -> {new_version}, key '{note_key}' added.")
cur.close()
conn.close()
