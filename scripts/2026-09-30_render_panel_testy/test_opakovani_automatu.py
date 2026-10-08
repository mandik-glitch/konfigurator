# Render automaty nevzdavaji navzdy (production_work_claims.blokovano): po max_fail selhanich pocka odstup
# (30 min, 1 h, 2 h ... max 24 h) a zkusi znovu. Falesny kurzor, bez DB. Kontroluje i to, ze oba automaty
# `blokovano` pouzivaji a nezustal v nich puvodni "navzdy" tvar.
# Spusteni: api/venv/bin/python3 test_opakovani_automatu.py   (konci kodem 0 jen kdyz VSE prosla)
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import production_work_claims as pwc  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


class FakeCur:
    def __init__(self, row):
        self.row = row
        self.sql = None

    def execute(self, sql, params=()):
        self.sql = (" ".join(sql.split()), params)

    def fetchone(self):
        return self.row


def b(row, max_fail=3):
    return pwc.blokovano(FakeCur(row), "assembly", 1, "krok", max_fail)


over("zadny zaznam (nikdy se nezkousel) -> neblokovat", b(None) is False)
over("2 selhani (pod limitem) -> neblokovat", b({"fail_count": 2, "stari_s": 10}) is False)
over("3 selhani pred 5 min -> blokovat (odstup 30 min)", b({"fail_count": 3, "stari_s": 300}) is True)
over("3 selhani pred 31 min -> zkusit znovu", b({"fail_count": 3, "stari_s": 31 * 60}) is False)
over("4 selhani pred 31 min -> STALE blokovat (odstup 1 h)", b({"fail_count": 4, "stari_s": 31 * 60}) is True)
over("4 selhani pred 61 min -> zkusit znovu", b({"fail_count": 4, "stari_s": 61 * 60}) is False)
over("6 selhani pred 3 h -> blokovat (odstup 4 h)", b({"fail_count": 6, "stari_s": 3 * 3600}) is True)
over("6 selhani pred 4,1 h -> zkusit znovu", b({"fail_count": 6, "stari_s": int(4.1 * 3600)}) is False)
over("odstup ma strop 24 h (20 selhani pred 23 h -> blokovat, pred 25 h -> zkusit)",
     b({"fail_count": 20, "stari_s": 23 * 3600}) is True and b({"fail_count": 20, "stari_s": 25 * 3600}) is False)
over("radek bez released_at (prave zabrany) -> neblokuje (rozhoduje claim/lease)", b({"fail_count": 9, "stari_s": None}) is False)
over("jiny max_fail (5): 4 selhani -> neblokovat", b({"fail_count": 4, "stari_s": 5}, max_fail=5) is False)

c = FakeCur({"fail_count": 3, "stari_s": 1})
pwc.blokovano(c, "shop_product", 4601, "vandr_render_auto_dispatch", 3)
over("SQL cte jen jeden radek podle (typ, id, krok)", "FROM production_work_claims" in c.sql[0] and c.sql[1] == ("shop_product", 4601, "vandr_render_auto_dispatch"), c.sql)

for soubor in ("scripts/2026-09-14_render_auto_dispatch.py", "scripts/2026-09-23_vandr_render_auto_dispatch.py", "scripts/2026-09-11_watchdog_prace.py"):
    zdroj = open(os.path.join("/opt/konfigurator", soubor), encoding="utf-8").read()
    over("%s pouziva pwc.blokovano" % soubor, "pwc.blokovano(" in zdroj)
    over("%s uz nevzdava navzdy (zadne `fail_count_of(...)` s porovnanim)" % soubor, "fail_count_of(" not in zdroj and "fc >= MAX_FAIL" not in zdroj)

print("\nVYSLEDEK opakovani automatu: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
