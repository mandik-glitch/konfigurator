# Hlasita chyba automatu: neplatne prirazeni v panelu (prejmenovane svetlo, chybejici soubor) ->
# PrirazeniNeplatne / zarad_render vraci (False, ...) a NESPUSTI render. Bez DB (FakeCur) a bez Blenderu.
# Predpoklad: X1_SCENA.blend na Sdilenem disku (cache svetel), jinak test skonci s chybou predem.
# Spusteni: api/venv/bin/python3 test_automat_hlasita_chyba.py
import os
import sys, json, importlib.util
sys.path.insert(0, "/opt/konfigurator/scripts")
import _render_prirazeni_lib as lib

SOUBORY = {"X1_SCENA.blend": "ae7af55d6ea118f1259953cc431bdd36.blend"}
for _f in SOUBORY.values():
    _cesta = [p for p in (os.path.join(d, _f) for d in ("/opt/konfigurator/private-files", "/opt/konfigurator/private-files/shared-drive")) if os.path.exists(p)]
    if not _cesta and not os.popen("find /opt/konfigurator -name %s -not -path '*/node_modules/*' 2>/dev/null | head -1" % _f).read().strip():
        sys.exit("PREDKONTROLA: soubor %s (X1_SCENA.blend) na Sdilenem disku neexistuje - test nema co cist" % _f)
class FakeCur:
    def __init__(self, stav): self.stav = stav; self.posl = None
    def execute(self, sql, params=()):
        self.posl = (sql, params)
    def fetchone(self):
        sql, params = self.posl
        if "app_settings" in sql:
            return {"setting_value": json.dumps(self.stav)} if self.stav is not None else None
        if "shared_drive_files" in sql and "filename=%s" in sql and "stored_filename=" not in sql:
            f = SOUBORY.get(params[0])
            return {"stored_filename": f} if f else None
        return None

zaklad = {"aktivni_pro_automat": True, "svetla_soubor": "X1_SCENA.blend", "hdri_sila": 2.0}
def pokus(stav):
    try:
        return "ARGS", lib.nacti_nastaveni_pro_automat(FakeCur(stav))
    except lib.PrirazeniNeplatne as e:
        return "NEPLATNE", str(e)

vysl = []
def over(n, c, d=None):
    vysl.append(c); print(("OK   " if c else "FAIL ") + n + ("" if c else "  -> %r" % (d,)))

r = pokus(dict(zaklad, svetla_vybrana=["Light", "Key_Renamed"]))
over("neplatny vyber -> PrirazeniNeplatne", r[0] == "NEPLATNE" and "Key_Renamed" in r[1], r)
r = pokus(dict(zaklad, svetla_vybrana=["Light", "Spot.002"]))
over("platny vyber -> argumenty s --svetla-jen=", r[0] == "ARGS" and "--svetla-jen=Light" in r[1] and "--svetla-jen=Spot.002" in r[1], r)
r = pokus(dict(zaklad, svetla_soubor="NENI_TAKOVY.blend"))
over("chybejici soubor svetel -> PrirazeniNeplatne", r[0] == "NEPLATNE", r)
r = pokus(dict(zaklad, aktivni_pro_automat=False, svetla_vybrana=["Zly"]))
over("automat vypnuty -> [] (nic se nevaliduje)", r == ("ARGS", []), r)
r = pokus(None)
over("zadne nastaveni -> []", r == ("ARGS", []), r)
r = pokus(dict(zaklad, svetla_aktivni=False, svetla_vybrana=["Zly"]))
over("svetla vypnuta -> bez svetel, bez chyby", r[0] == "ARGS" and not any("svetla" in a for a in r[1]), r)

# zarad_render: neplatne prirazeni -> (False, ...) a zadny subprocess
spec = importlib.util.spec_from_file_location("vd", "/opt/konfigurator/scripts/2026-09-23_vandr_render_auto_dispatch.py")
vd = importlib.util.module_from_spec(spec); spec.loader.exec_module(vd)
class C:
    def cursor(self):
        class X:
            def __enter__(s): return FakeCur(dict(zaklad, svetla_vybrana=["Zly"]))
            def __exit__(s, *a): return False
        return X()
    def close(self): pass
vd._conn = lambda: C()
volano = []
vd.subprocess.run = lambda *a, **k: volano.append(a) or (_ for _ in ()).throw(AssertionError("subprocess se nesmi spustit"))
ok, poz = vd.zarad_render(123456)
over("zarad_render vraci (False, ...) a nespusti render", ok is False and "neplatne" in poz and not volano, (ok, poz, volano))
print("\nVYSLEDEK: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
