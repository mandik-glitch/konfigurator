#!/usr/bin/env python3
"""Řemeslo - jednorázový seed dat do remeslo_workflow_apps/_features/
_app_features - bot10, 2026-08-18. Zdroj dat: REMESLO_APPKY_SROVNANI.md
(sloučený podklad ze 3 průzkumů - REMESLO_PRUZKUM_WORKFLOW_APPS.md,
REMESLO_PRUZKUM_APPKY_GOOGLE_PLAY.md, REMESLO_PRUZKUM_APP_STORE.md).

Idempotentní - INSERT ... ON DUPLICATE KEY UPDATE (unikátní klíč
`name`, přidán níže při prvním běhu pokud chybí) / DELETE+INSERT pro
M:N vazby, takže re-run po opravě dat je bezpečný.

Použití:
    api/venv/bin/python3 scripts/2026-08-18_remeslo_workflow_apps_seed.py --kontrola
    api/venv/bin/python3 scripts/2026-08-18_remeslo_workflow_apps_seed.py --apply
"""
import argparse
import os
import sys

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for _line in open(_ENV_PATH, encoding="utf-8"):
    _line = _line.strip()
    if not _line or _line.startswith("#") or "=" not in _line:
        continue
    _k, _v = _line.split("=", 1)
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
# POZOR: remeslo_* tabulky ZIJI OD 2026-08-19 VE VLASTNI DB "Remeslnik"
# (viz REMESLO_KONCEPT.md "Infrastruktura - presun na vlastni DB").
# get_conn() z app.py miri na HLAVNI DB, kde uz jsou remeslo_* tabulky
# jen zmrzly snimek - zapis pres nej by tise skoncil v nepouzivane
# kopii. Proto get_remeslo_conn(). Nalezeno auditem (bot14, 2026-08-19).
from remeslo import get_remeslo_conn as get_conn  # noqa: E402

RESEARCHED_AT = "2026-08-18"
SOURCE_DOC = "REMESLO_APPKY_SROVNANI.md"

FEATURES = [
    ("fakturace", "Fakturace"),
    ("zakazky", "Evidence zakázek/projektu"),
    ("planovani", "Plánování/kalendář/dispatch"),
    ("foto", "Foto-dokumentace"),
    ("cas", "Sledování odpracovaného času"),
    ("gps", "GPS sledování / kniha jízd"),
    ("crm", "CRM / historie zákazníka"),
    ("platby", "Online platby v appce"),
    ("offline", "Offline režim"),
    ("cestina", "Čeština"),
    ("ucetnictvi", "Integrace účetnictví"),
    ("tym", "Tým / subdodavatelé"),
    ("ziskovost", "Ziskovost/marže zakázky"),
    ("sklad", "Materiál / sklad"),
]

# (name, publisher, category, play_pkg, app_store_id, rating_play, count_play,
#  rating_as, count_as, price_note, target_note, cz, not_found, features[])
APPS = [
    ("Jobber", "Jobber Software", "field_service", "com.getjobber.jobber", None,
     4.44, 6632, None, None, "od $25/měsíc, freemium", "malé firmy 1-15 vozidel", 0, 0,
     ["fakturace", "zakazky", "planovani", "cas", "gps", "crm", "platby", "ucetnictvi", "tym"]),
    ("Housecall Pro", "Codefied Inc.", "field_service", "housecall.pros", None,
     4.49, 6625, None, None, "$59-329/měsíc + povinné doplatky $40-149/měsíc", "5-50 techniků", 0, 0,
     ["fakturace", "zakazky", "planovani", "foto", "gps", "crm", "platby", "ucetnictvi", "tym"]),
    ("Tradify", "Tradify Limited", "field_service", "com.tradifyhq.tradifyapp", None,
     4.37, 3080, None, None, "$48-62/měsíc", "malé-střední řemeslné firmy (NZ/AU)", 0, 0,
     ["fakturace", "zakazky", "planovani", "foto", "cas", "ucetnictvi", "tym", "ziskovost"]),
    ("Fergus", "Fergus Software Ltd.", "field_service", "com.fergus.app", None,
     None, None, None, None, "podobný řád jako Tradify", "o trochu větší firmy než Tradify", 0, 0,
     ["fakturace", "zakazky", "planovani", "ziskovost", "sklad"]),
    ("mHelpDesk", "mHelpDesk", "field_service", "com.mhelpdesk.endeavor", None,
     1.95, 521, 3.5, 197, "$169-299/měsíc", "1-20 techniků", 0, 0,
     ["fakturace", "zakazky", "planovani", "crm", "offline", "ucetnictvi", "sklad"]),
    ("ServiceTitan Mobile", "ServiceTitan Mobile", "field_service", "com.servicetitan.mobile", None,
     2.39, 1022, None, None, "enterprise, cena na dotaz", "střední-velké firmy", 0, 0,
     ["fakturace", "zakazky", "planovani", "foto", "platby"]),
    ("Contractor+", "Contractor Plus, Inc.", "field_service", "contractorplus.app", None,
     4.39, 666, None, None, "freemium, AI odhady", "handyman kontraktoři", 0, 0,
     ["fakturace", "zakazky", "planovani", "cas", "gps", "crm", "platby", "sklad"]),
    ("CompanyCam", "Company Cam", "field_service", "com.agilx.companycam", None,
     4.69, 7603, None, None, "freemium", "foto-dokumentace specificky (ne plný workflow)", 0, 0,
     ["foto", "gps", "tym"]),
    ("ServiceTrade", "ServiceTrade Inc", "field_service", "com.servicenet.mobile", None,
     4.11, 270, None, None, "enterprise", "komerční servisní kontraktoři (HVAC/mechanical/fire)", 0, 0,
     ["zakazky", "planovani", "foto", "cas", "crm"]),
    ("Fieldwire", "Fieldwire", "field_service", "net.fieldwire.app", None,
     4.35, 4862, None, None, "freemium", "stavební týmy, ne solo řemeslník", 0, 0,
     ["zakazky", "planovani", "tym"]),
    ("ServiceM8", "Eroldawn Pty Ltd", "field_service", None, None,
     None, None, 4.6, 809, "Lite $8,99 - Premium $149,99/měsíc", "sólo řemeslníci až 20 zaměstnanců", 0, 0,
     ["fakturace", "zakazky", "cas", "gps", "crm", "platby", "ucetnictvi", "tym"]),
    ("Workiz", "Send A Job Inc", "field_service", None, None,
     None, None, 4.6, 2100, "zdarma + prémiové tarify (přesná cena mimo appku)", "terénní služby, malé-střední firmy", 0, 0,
     ["fakturace", "zakazky", "planovani", "crm", "platby", "tym"]),
    ("Joist", "Joist Software Inc.", "field_service", None, None,
     None, None, None, None, "Basics €8,99 - Run €99,99/měsíc", "generální dodavatelé, hendymani", 0, 0,
     ["fakturace", "zakazky", "foto", "crm", "platby", "ucetnictvi"]),
    ("QuoteIQ", "QuoteIQ LLC", "field_service", None, None,
     None, None, 4.7, 3300, "od $29,99/měsíc", "tlakové mytí, HVAC, instalatéři, elektrikáři...", 0, 0,
     ["fakturace", "zakazky", "planovani", "crm", "platby"]),

    ("Buildo", "Team Buildo", "construction_diary", "net.spacive.buildo", None,
     4.0, 257, None, None, "zdarma", "CZ stavební firmy", 1, 0,
     ["zakazky", "sklad"]),
    ("Buildary.Online", "First information systems", "construction_diary", "com.firstis.buildary", None,
     None, None, None, None, "zdarma", "CZ", 1, 0,
     ["zakazky"]),
    ("SiteLogs", "apptech_Infotech", "construction_diary", "com.construction.diary", None,
     None, None, None, None, "zdarma", None, 0, 0,
     ["zakazky"]),

    ("iDoklad", "Seyfor, a.s.", "invoicing_only", None, None,
     None, None, 4.8, 3300, "Basic 329 Kč, Favorites 579 Kč, Premium 949 Kč", "podnikatelé a malé firmy (300 tis. uživatelů)", 1, 0,
     ["fakturace", "ucetnictvi"]),
    ("SuperFaktura", "SuperFaktura, s.r.o.", "invoicing_only", None, None,
     None, None, 4.8, 158, "Basic 199-239 Kč/měs., Standard 479 Kč/měs., Premium 699-769 Kč/měs.", "živnostníci a malé firmy", 1, 0,
     ["fakturace", "sklad"]),
    ("BitFaktura", "BitFaktura s.r.o.", "invoicing_only", None, None,
     None, None, 4.8, 24, "Start 99 Kč, Standard 179 Kč, Pro 249 Kč, Pro Plus 399 Kč", "živnostníci, začínající podnikatelé", 1, 0,
     ["fakturace", "foto", "tym"]),
    ("Doklado", "SmartLab s.r.o.", "invoicing_only", None, None,
     None, None, None, None, "zdarma + předplatné PLUS", "malí/střední podnikatelé, účetní (SK/CZ)", 0, 0,
     ["fakturace", "foto", "ucetnictvi", "tym"]),
    ("Fintoro", "Fintoro s.r.o.", "invoicing_only", None, None,
     None, None, 5.0, 15, "free do 15 faktur, Mini 6,49 €, Standard 13,49 €", "živnostníci, freelanceři (SK)", 0, 0,
     ["fakturace", "ucetnictvi"]),
    ("Faktury.co", "Kajetan Dudczak", "invoicing_only", "co.faktury", None,
     None, None, None, None, "zdarma", None, 1, 0,
     ["fakturace"]),
    ("Faktura", "Weis & Wise A/S", "invoicing_only", "com.weiswise.faktura", None,
     None, None, None, None, "zdarma", None, 0, 0,
     ["fakturace"]),
    ("KROS Fakturácia", "KROS a.s.", "invoicing_only", "sk.kros.fakturacia.twa", None,
     None, None, None, None, "zdarma", "SK", 0, 0,
     ["fakturace"]),

    ("Timoty", "Timoty s.r.o.", "full_workflow_cz", None, None,
     None, None, 4.3, 10, "appka zdarma, ceny řešeny přes web timoty.cz", "manažeři terénních operací, stavební/servisní firmy", 1, 0,
     ["zakazky", "planovani", "cas", "tym", "sklad"]),
    ("Logeto", "Systemart s.r.o.", "full_workflow_cz", "cz.vykazprace", None,
     4.25, 352, 4.0, 47, "zdarma pro jednotlivce, placeně pro firmy dle rozsahu", "malé firmy, podnikatelé, OSVČ", 1, 0,
     ["zakazky", "planovani", "cas", "gps", "ucetnictvi", "tym"]),
    ("DílnaTech", "ErokoTech, s.r.o.", "full_workflow_cz", "cz.dilnatech", None,
     None, None, None, None, None, "servisní dílna", 1, 0,
     ["zakazky", "crm", "tym", "sklad"]),

    # Nenalezeno na zadnem store (potvrzeno nezavisle 2x, bot10 i bot11) -
    # zaznamenano dle funkci z jejich vlastniho webu, ne fabrikovano.
    ("PROFIDAT", None, "full_workflow_cz", None, None,
     None, None, None, None, "nedohledáno zvenčí (tarify BASIC/STANDARD za přihlášením)", "řemeslníci, technici, malé firmy", 1, 1,
     ["zakazky", "foto", "ziskovost", "cas"]),
    ("Řemeslník PRO", "elhacom.cz", "full_workflow_cz", None, None,
     None, None, None, None, "365 Kč/rok", "menší řemeslníci a živnostníci", 1, 1,
     ["fakturace", "zakazky", "foto"]),
    ("EasyZakázky", None, "full_workflow_cz", None, None,
     None, None, None, None, None, "malé firmy a živnostníci", 1, 1,
     ["zakazky"]),
    ("Kalendo", None, "full_workflow_cz", None, None,
     None, None, None, None, None, "řemeslníci a živnostníci", 1, 1,
     ["fakturace", "zakazky", "planovani"]),
    ("Ř21", None, "full_workflow_cz", None, None,
     None, None, None, None, "188 Kč/měsíc (plánovaná placená verze, dle staršího zdroje)", "řemeslníci", 1, 1,
     ["fakturace", "zakazky", "foto"]),
]


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true")
    grp.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            print(f"Funkce: {len(FEATURES)}, appky: {len(APPS)}")
            if not args.apply:
                for name, *_rest, features in APPS:
                    print(f"  [kontrola] {name} - {len(features)} funkcí")
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
                return

            for slug, name in FEATURES:
                cur.execute(
                    "INSERT INTO remeslo_workflow_features (slug, name, sort_order) "
                    "VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE name=VALUES(name)",
                    (slug, name, FEATURES.index((slug, name))),
                )
            cur.execute("SELECT id, slug FROM remeslo_workflow_features")
            feature_id_by_slug = {r["slug"]: r["id"] for r in cur.fetchall()}

            written = 0
            for (name, publisher, category, play_pkg, app_store_id, rating_play, count_play,
                 rating_as, count_as, price_note, target_note, cz, not_found, features) in APPS:
                cur.execute("SELECT id FROM remeslo_workflow_apps WHERE name=%s", (name,))
                existing = cur.fetchone()
                if existing:
                    app_id = existing["id"]
                    cur.execute(
                        "UPDATE remeslo_workflow_apps SET publisher=%s, category=%s, play_store_package=%s, "
                        "app_store_id=%s, rating_play=%s, rating_count_play=%s, rating_appstore=%s, "
                        "rating_count_appstore=%s, price_note=%s, target_audience_note=%s, language_cs=%s, "
                        "not_found_on_stores=%s, source_doc=%s, researched_at=%s WHERE id=%s",
                        (publisher, category, play_pkg, app_store_id, rating_play, count_play, rating_as,
                         count_as, price_note, target_note, cz, not_found, SOURCE_DOC, RESEARCHED_AT, app_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO remeslo_workflow_apps "
                        "(name, publisher, category, play_store_package, app_store_id, rating_play, "
                        " rating_count_play, rating_appstore, rating_count_appstore, price_note, "
                        " target_audience_note, language_cs, not_found_on_stores, source_doc, researched_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (name, publisher, category, play_pkg, app_store_id, rating_play, count_play,
                         rating_as, count_as, price_note, target_note, cz, not_found, SOURCE_DOC, RESEARCHED_AT),
                    )
                    app_id = cur.lastrowid

                cur.execute("DELETE FROM remeslo_workflow_app_features WHERE app_id=%s", (app_id,))
                for slug in features:
                    cur.execute(
                        "INSERT INTO remeslo_workflow_app_features (app_id, feature_id) VALUES (%s,%s)",
                        (app_id, feature_id_by_slug[slug]),
                    )
                written += 1

            conn.commit()
            print(f"OK - zapsáno {written} appek + {len(FEATURES)} funkcí.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
