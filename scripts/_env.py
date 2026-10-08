"""Sdileny loader api/.env + get_conn() pro pomocne/jednorazove skripty.

Ucel (bot6 bezpecnostni nalez 2026-09-02): zadne literaly hesla/hostu/
uzivatele natvrdo v tracked souborech - vzdy cist z api/.env (nebo
os.environ, kdyz bezi pod systemd EnvironmentFile=). Stejna konvence
jako scripts/handover.py a scripts/qa_product_audit.py.
"""
import os
import re

import pymysql

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, "api", ".env")


def load_env(path=None):
    path = path or ENV_PATH
    out = dict(os.environ)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


# --- Zabrana proti NECHTENEMU zapisu do app_users -------------------------
#
# TOHLE NENI BEZPECNOSTNI OPATRENI a nesmi se tak tvarit. Jde OBEJIT -
# staci si otevrit vlastni `pymysql.connect(...)` misto get_conn(), a
# zabrana neplati. Je to ZAMERNE: boti bezi jako root a ctou `api/.env`,
# takze se k DB dostanou i mimo tenhle helper. Kdyby se tohle vydavalo za
# ochranu, bylo by to horsi nez zadna - nekdo by si myslel, ze neco drzi.
#
# Co to tedy je: zabrana proti OMYLU, na miste, kde vznika skoda. Stejna
# logika jako u kontroly beziciho renderu v restart_konfigurator.sh.
#
# Proc prave app_users (WORKFLOW.md pravidlo 30, Robert 2026-09-11: "bot
# nemuze mit admin ucet"): ucet `bot8-test-scene@test.local` s roli admin
# vznikl primym SQL INSERTem mimo aplikaci - v `audit_log` po jeho
# zalozeni neni zadny zaznam, prestoze admin API zakladani loguje. Tudy
# uz dalsi vzniknout nema.
#
# CTENI (SELECT) je bez omezeni - do app_users boti bezne koukaji.
_ZAPIS_DO_APP_USERS = re.compile(
    r"\b(?:insert\s+(?:ignore\s+)?into|replace\s+into|update(?:\s+ignore)?|"
    r"delete\s+from|truncate(?:\s+table)?|alter\s+table|drop\s+table)\s+"
    r"(?:`?\w+`?\s*\.\s*)?`?app_users`?\b",
    re.IGNORECASE | re.DOTALL,
)

_HLASKA = (
    "ZABRANA: tenhle dotaz zapisuje do `app_users`.\n"
    "\n"
    "WORKFLOW.md pravidlo 30: bot si nezaklada uzivatelsky ucet a zadny\n"
    "neosobni ucet nedostane roli admin. Realne zasahy v produkci musi jit\n"
    "dohledat ke konkretni osobe; smyslena identita to rusi.\n"
    "\n"
    "CO DELAT MISTO TOHO:\n"
    "  * Vetsina prace zadny ucet nepotrebuje - skript pres scripts/_env.py\n"
    "    bezi ze serveru bez prihlasovani. To je vychozi volba.\n"
    "  * Potrebujes otevrit 3D scenu? Brana scene_html_gate nevyzaduje\n"
    "    admina, pusti kteroukoli roli z PERMISSION_ROLES (nejslabsi je\n"
    "    `monter`). O ucet si rekni Robertovi, nezakladej si ho.\n"
    "  * Ucet, ktery doslouzil, se NEMAZE (prijde o autorstvi navazanych\n"
    "    radku) - odebrat roli, active=0, prejmenovat.\n"
    "\n"
    "Kdyz to Robert vyslovne schvalil (napr. odstaveni konkretniho uctu),\n"
    "otevri spojeni pres get_conn(zapis_do_app_users=True) - tim to rikas\n"
    "nahlas a je to videt v kodu i pri revizi.\n"
    "\n"
    "POZN.: tahle zabrana NENI bezpecnostni opatreni. Jde obejit vlastnim\n"
    "pymysql.connect() a je to tak zamerne - chrani pred omylem, ne pred\n"
    "zamerem."
)


class ZapisDoAppUsersOdmitnut(RuntimeError):
    """Vyhozeno zabranou nize. Neodchytavat jen proto, aby zapis prosel."""


class _StrazniCursor(pymysql.cursors.DictCursor):
    """DictCursor, ktery odmitne zapis do app_users. Viz komentar vyse."""

    def execute(self, query, args=None):
        if _ZAPIS_DO_APP_USERS.search(query or ""):
            raise ZapisDoAppUsersOdmitnut(_HLASKA + "\n\nDotaz: " + " ".join((query or "").split())[:200])
        return super().execute(query, args)

    def executemany(self, query, args=None):
        if _ZAPIS_DO_APP_USERS.search(query or ""):
            raise ZapisDoAppUsersOdmitnut(_HLASKA + "\n\nDotaz: " + " ".join((query or "").split())[:200])
        return super().executemany(query, args)


def get_conn(env=None, database=None, zapis_do_app_users=False, **kwargs):
    """Spojeni do DB pro pomocne skripty.

    `zapis_do_app_users=True` vypne zabranu proti zapisu do `app_users` -
    pouzij VYHRADNE tam, kde zasah do uctu vyslovne schvalil Robert (dnes:
    scripts/2026-09-11_smazat_testovaci_ucet_765.py a
    scripts/2026-09-11_odstavit_ucet_662.py). Viz WORKFLOW.md pravidlo 30.
    """
    e = env or load_env()
    kwargs.setdefault("cursorclass",
                      pymysql.cursors.DictCursor if zapis_do_app_users else _StrazniCursor)
    return pymysql.connect(
        host=e["DB_HOST"], port=int(e.get("DB_PORT", 3306)),
        user=e["DB_USER"], password=e["DB_PASSWORD"],
        database=database or e["DB_NAME"], charset="utf8mb4",
        **kwargs
    )
