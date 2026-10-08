# scripts/_render_prirazeni_lib.py::sestav_material_knihovnu - cache sloucenych knihoven materialu (bot4 2026-10-02).
# Pricina: drive se pro KAZDE zarazeni renderu vyrobil novy tmp*.blend (13-25 MB, ~10 s Blenderu) a nikdy se nesmazal
# (303 souboru / 5,4 GB, disk /opt na 97 %). Blender je v testu atrapa (subprocess.run) - nic se nespousti, zadna DB.
# Spusteni: python3 test_sestav_knihovnu.py   (konci kodem 0 jen kdyz VSE prosla)
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, "/opt/konfigurator/scripts")
import _render_prirazeni_lib as L  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> %r" % (detail,)))


tmp = tempfile.mkdtemp(prefix="knihovny_test_")
L.SLOUCENE_KNIHOVNY_DIR = os.path.join(tmp, "alu_test")
os.makedirs(L.SLOUCENE_KNIHOVNY_DIR)
zdroje = os.path.join(tmp, "zdroje")
os.makedirs(zdroje)


def zdroj(nazev, obsah=b"blend"):
    p = os.path.join(zdroje, nazev)
    open(p, "wb").write(obsah)
    return p


volani = []


def falesny_blender(argv, **kw):
    volani.append(list(argv))
    open(argv[-1], "wb").write(b"SLOUCENO" * 100)          # vystup je posledni argument
    class R: returncode = 0
    return R()


puvodni_run = subprocess.run
subprocess.run = falesny_blender
try:
    a, b, c = zdroj("Alumi2.blend"), zdroj("Blue.blend"), zdroj("Vychozi.blend")

    over("1 jeden zdrojovy soubor -> vrati se beze zmeny, Blender se nespusti", L.sestav_material_knihovnu([("alu", a), ("klt", a)]) == a and not volani, volani)
    over("2 zadny soubor -> None", L.sestav_material_knihovnu([("x", None)]) is None and not volani)

    v1 = L.sestav_material_knihovnu([("alu", a), ("klt", b)])
    over("3 dva ruzne soubory -> 1 beh Blenderu, vysledek knihovna_<otisk>.blend v cilove slozce", len(volani) == 1 and os.path.dirname(v1) == L.SLOUCENE_KNIHOVNY_DIR and os.path.basename(v1).startswith("knihovna_") and os.path.getsize(v1) > 0, (volani, v1))
    over("3b zdroje i vystup predany Blenderu spravne (zdroje serazene, vystup posledni, ne konecny nazev)", volani[0][-3:-1] == [a, b] and volani[0][-1] != v1 and volani[0][-1].endswith(".tmpbuild.blend"), volani[0][-4:])
    over("3c po behu nezustal zadny *.tmpbuild.blend ani docasny skript v cilove slozce", sorted(os.listdir(L.SLOUCENE_KNIHOVNY_DIR)) == [os.path.basename(v1)], os.listdir(L.SLOUCENE_KNIHOVNY_DIR))

    v2 = L.sestav_material_knihovnu([("alu", a), ("klt", b)])
    over("4 STEJNY vstup podruhe -> stejna cesta, Blender se NEspusti (cache)", v2 == v1 and len(volani) == 1, (v2, len(volani)))
    v3 = L.sestav_material_knihovnu([("klt", b), ("alu", a), ("jine", a)])
    over("5 poradi a opakovani zdroju nevadi (stejna mnozina souboru -> stejna cache)", v3 == v1 and len(volani) == 1, (v3, len(volani)))

    over("6 jina kombinace zdroju -> jina knihovna, 2. beh Blenderu", L.sestav_material_knihovnu([("alu", a), ("v", c)]) != v1 and len(volani) == 2, len(volani))

    time.sleep(1.1)
    zdroj("Blue.blend", b"zmeneno-obsah-jine-delky")           # zdroj se zmenil (cas i velikost)
    v4 = L.sestav_material_knihovnu([("alu", a), ("klt", b)])
    over("7 ZMENENY zdroj -> novy otisk, nova slouceniny (zadna zastarala cache)", v4 != v1 and len(volani) == 3 and os.path.exists(v4), (v4, len(volani)))

    # --- uklid starych --------------------------------------------------------------------------------------
    d = L.SLOUCENE_KNIHOVNY_DIR
    stary_dny = time.time() - 9 * 86400
    soubory_pro_test = {
        "tmp_stary1.blend": (True, stary_dny),                   # drivejsi docasna slouceniny, stara -> pryc
        "tmp_cerstvy.blend": (False, time.time() - 3600),        # cerstva -> zustane (muze ji pouzivat bezici uloha)
        "knihovna_stara0000000000.blend": (True, stary_dny),     # nepouzita cache -> pryc
        "vd_materialy_alu_test9.blend": (False, stary_dny),      # Robertuv rucni testovaci soubor -> NIKDY
        "jiny_soubor.txt": (False, stary_dny),
    }
    for n, (_smazat, cas) in soubory_pro_test.items():
        p = os.path.join(d, n)
        open(p, "wb").write(b"x")
        os.utime(p, (cas, cas))
    L.sestav_material_knihovnu([("alu", a), ("v", c), ("zase", b)])         # nova kombinace -> vyrobi a uklidi
    zbyva = set(os.listdir(d))
    over("8 uklid smaze stare tmp*.blend a nepouzivane knihovna_*.blend", "tmp_stary1.blend" not in zbyva and "knihovna_stara0000000000.blend" not in zbyva, sorted(zbyva))
    over("8b cerstve tmp*.blend zustava (mohla by ji pouzivat bezici uloha)", "tmp_cerstvy.blend" in zbyva, sorted(zbyva))
    over("8c rucni testovaci soubory a cizi soubory se NEDOTKNOU", "vd_materialy_alu_test9.blend" in zbyva and "jiny_soubor.txt" in zbyva, sorted(zbyva))

    # --- cache hit obnovuje cas, takze pouzivana knihovna uklidem neprijde ----------------------------------------
    pouzivana = L.sestav_material_knihovnu([("alu", a), ("v", c)])
    os.utime(pouzivana, (stary_dny, stary_dny))                               # tvari se jako stara...
    pocet_pred = len(volani)
    L.sestav_material_knihovnu([("alu", a), ("v", c)])                        # ...ale nekdo ji pouzije (cache hit)
    L.sestav_material_knihovnu([("alu", a), ("novy", zdroj("Dalsi.blend"))])  # a pak se spusti uklid
    over("9 pouzita (cache hit) knihovna se uklidem NEsmaze, a zadny dalsi beh Blenderu pro ni", os.path.exists(pouzivana) and len(volani) == pocet_pred + 1, (os.path.exists(pouzivana), len(volani) - pocet_pred))

    # --- selhani Blenderu nic nenecha ---------------------------------------------------------------------------------
    def spadly_blender(argv, **kw):
        open(argv[-1], "wb").write(b"rozdelane")
        raise subprocess.CalledProcessError(1, argv)
    subprocess.run = spadly_blender
    pred = set(os.listdir(d))
    try:
        L.sestav_material_knihovnu([("alu", a), ("klt", zdroj("Jeste_jina.blend"))])
        over("10 selhani Blenderu: vyjimka se propaguje (volajici ji zna)", False)
    except subprocess.CalledProcessError:
        over("10 selhani Blenderu: vyjimka se propaguje (volajici ji zna)", True)
    over("10b a nezustal rozdelany/poskozeny soubor v cache", set(os.listdir(d)) == pred, sorted(set(os.listdir(d)) ^ pred))
finally:
    subprocess.run = puvodni_run

zdroj_dispatch = open("/opt/konfigurator/scripts/2026-09-24_render_hdri_test_dispatch.py", encoding="utf-8").read()
over("11 dispatcher testovacich renderu uz nema vlastni (hromadici) kopii - deleguje na knihovni funkci",
     "mktemp" not in zdroj_dispatch and "_rpl.sestav_material_knihovnu(dvojice)" in zdroj_dispatch)
over("12 v knihovne uz neni tempfile.mktemp do alu_test (puvodni zdroj hromadeni)", "tempfile.mktemp(suffix=\".blend\", dir=os.path.join(REPO, \"private-files\", \"alu_test\"))" not in open("/opt/konfigurator/scripts/_render_prirazeni_lib.py", encoding="utf-8").read())

print("\nVYSLEDEK cache knihoven: %d/%d OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
