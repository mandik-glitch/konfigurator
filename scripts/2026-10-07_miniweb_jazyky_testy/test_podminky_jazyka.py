#!/usr/bin/env python3
"""Mini-shop: podminky spusteni (--go-live) zahrnuji JAZYKOVOU USPLNOST (bot16, 2026-10-07; Robert: kopie shopu v dalsich jazycich nesmi mlcky spadnout na jiny jazyk).
Jen cteni souboru (zadna DB, zadna sit): `_podminky_jazyka(lang, repo)` nad umele sestavenym repem (dockazuje kazdou podminku zvlast) a nad skutecnym repem (en a sk splneno, de/hu zatim ne,
kdyz jejich soubory chybi - jinak splneno)."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


spec = importlib.util.spec_from_file_location("miniweb_shop", os.path.join(REPO, "scripts", "miniweb_shop.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def sestav(tmp, i18n, sablony, paths, balicky=()):
    os.makedirs(os.path.join(tmp, "webapp", "miniweb", "i18n"))
    os.makedirs(os.path.join(tmp, "api", "jazyky"))
    for l, d in i18n.items():
        json.dump(d, open(os.path.join(tmp, "webapp", "miniweb", "i18n", l + ".json"), "w", encoding="utf-8"))
    json.dump(sablony, open(os.path.join(tmp, "api", "miniweb_seo_sablony.json"), "w", encoding="utf-8"))
    open(os.path.join(tmp, "api", "miniweb_seo.py"), "w", encoding="utf-8").write("PATHS = %r\n" % (paths,))
    for l in balicky:
        json.dump({"lang": l}, open(os.path.join(tmp, "api", "jazyky", l + ".json"), "w"))


def stav(lang, tmp):
    return {popis.split(" ")[0] + popis[:60]: ok for ok, popis in M._podminky_jazyka(lang, repo=tmp)}, M._podminky_jazyka(lang, repo=tmp)


SK = {"a.b": "Ahoj {name}", "c": "Text", "d.multi": "Vice"}
SAB_SK = {"home": {"title": "x", "robots": "y"}, "cart": {"title": "z"}}
PATHS = {"sk": {"category": "/k/"}, "de": {"category": "/kat/"}}

tmp = tempfile.mkdtemp(prefix="jazyky_test_")
try:
    # 1) uplny nemecky shop: vse splneno
    t1 = os.path.join(tmp, "uplny"); os.makedirs(t1)
    sestav(t1, {"sk": SK, "de": {"a.b": "Hallo {name}", "c": "Text", "d.multi": "Mehr"}}, {"sk": SAB_SK, "de": {"home": {"title": "t", "robots": "r"}, "cart": {"title": "c"}}}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t1)
    over("A1 uplny jazyk (de): vsech %d podminek splneno" % len(r), r and all(ok for ok, _ in r), [p for ok, p in r if not ok])
    # 2) chybi soubor i18n
    t2 = os.path.join(tmp, "bez_i18n"); os.makedirs(t2)
    sestav(t2, {"sk": SK}, {"sk": SAB_SK, "de": SAB_SK}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t2)
    over("A2 chybi i18n/de.json -> nesplneno (a nepada)", any((not ok) and "i18n/de.json existuje" in p for ok, p in r), r)
    # 3) chybi klic
    t3 = os.path.join(tmp, "chybi_klic"); os.makedirs(t3)
    sestav(t3, {"sk": SK, "de": {"a.b": "Hallo {name}", "c": "Text"}}, {"sk": SAB_SK, "de": SAB_SK}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t3)
    over("A3 chybi klic d.multi -> nesplneno a jmenuje ho", any((not ok) and "d.multi" in p for ok, p in r), r)
    # 4) jiny placeholder
    t4 = os.path.join(tmp, "placeholder"); os.makedirs(t4)
    sestav(t4, {"sk": SK, "de": {"a.b": "Hallo {nazev}", "c": "Text", "d.multi": "Mehr"}}, {"sk": SAB_SK, "de": SAB_SK}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t4)
    over("A4 jiny {placeholder} -> nesplneno a jmenuje klic", any((not ok) and "placeholdery" in p and "a.b" in p for ok, p in r), r)
    # 5) SEO sablony: chybi jazyk / chybi sekce
    t5 = os.path.join(tmp, "seo"); os.makedirs(t5)
    sestav(t5, {"sk": SK, "de": {"a.b": "H {name}", "c": "T", "d.multi": "M"}}, {"sk": SAB_SK}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t5)
    over("A5a bez SEO sablon jazyka -> nesplneno", any((not ok) and "SEO šablony pro jazyk de" in p for ok, p in r), r)
    t6 = os.path.join(tmp, "seo2"); os.makedirs(t6)
    sestav(t6, {"sk": SK, "de": {"a.b": "H {name}", "c": "T", "d.multi": "M"}}, {"sk": SAB_SK, "de": {"home": {"title": "t"}}}, PATHS, balicky=("de",))
    r = M._podminky_jazyka("de", repo=t6)
    over("A5b chybi sekce/klice sablon (cart, home.robots) -> nesplneno", any((not ok) and "cart" in p and "home.robots" in p for ok, p in r), r)
    # 6) PATHS a serverova sada
    t7 = os.path.join(tmp, "paths"); os.makedirs(t7)
    sestav(t7, {"sk": SK, "hu": {"a.b": "H {name}", "c": "T", "d.multi": "M"}}, {"sk": SAB_SK, "hu": SAB_SK}, PATHS, balicky=())
    r = M._podminky_jazyka("hu", repo=t7)
    over("A6a jazyk bez PATHS -> nesplneno", any((not ok) and "cesty hezkých adres jazyka hu" in p for ok, p in r), r)
    over("A6b jazyk mimo cs/en/sk bez serverove sady api/jazyky/hu.json -> nesplneno", any((not ok) and "api/jazyky/hu.json" in p for ok, p in r), r)
    # 7) cs/en/sk serverovou sadu nepotrebuji
    r = M._podminky_jazyka("sk", repo=t1)
    over("A7 sk (referencni) nepotrebuje api/jazyky/sk.json a nema nic nesplneno (kromě PATHS sk, ktere je v umelem repu)", all(ok for ok, _ in r) and not any("api/jazyky" in p for _, p in r), r)
    # 8) UPLNOST serverove sady vuci kodu (parita): sada existuje, ale kod mezitim dostal nove retezce (perforovany panel 2026-10-07) -> go-live se zablokuje
    volano = []
    def uplna(base, ref):
        volano.append((base, ref)); return [(True, f"serverová sada {base}: položky vůči {ref} (340)")]
    def neuplna(base, ref):
        volano.append((base, ref)); return [(False, f"serverová sada {base}: položky vůči {ref} (340) - vyplněno 326; chybí 16: stul_shop.TEXTY.panellen")]
    r = M._podminky_jazyka("de", repo=t1, parita=uplna)
    over("A8a uplna serverova sada (parita bez mezery) -> vse splneno a parita zavolana pro de/sk", r and all(ok for ok, _ in r) and volano == [("de", "sk")] and any("položky vůči sk (340)" in p for _, p in r), (volano, [p for ok, p in r if not ok]))
    r = M._podminky_jazyka("de", repo=t1, parita=neuplna)
    over("A8b neuplna serverova sada (kod ma nove retezce) -> nesplneno a jmenuje, co chybi", any((not ok) and "chybí 16" in p and "panellen" in p for ok, p in r) and all(ok for ok, p in r if "chybí 16" not in p), r)
    volano.clear()
    r = M._podminky_jazyka("hu", repo=t7, parita=uplna)
    over("A8c bez souboru sady se parita NEvola (uz je nesplnena existence souboru)", volano == [] and any((not ok) and "api/jazyky/hu.json" in p for ok, p in r), (volano, r))
    r = M._podminky_jazyka("sk", repo=t1, parita=neuplna)
    over("A8d sk (referencni, v kodu) paritu nepouziva", volano == [] and all(ok for ok, _ in r), (volano, r))
    # parita se defaultne zapina JEN pro skutecne repo (umele repo nema scripts/): podproces by selhal a zablokoval vsechno; test: umele repo bez `parita` -> zadny podproces
    puvodni = M._parita_server
    M._parita_server = lambda *a, **k: (_ for _ in ()).throw(AssertionError("parita se pro umele repo nema volat"))
    try:
        r = M._podminky_jazyka("de", repo=t1)
        over("A8e umele repo bez parametru parita: kontrola se nespousti (a zadna chyba)", r and all(ok for ok, _ in r), r)
    finally:
        M._parita_server = puvodni
    # skutecna funkce _parita_server: kontrola, kterou nejde provest, je NESPLNENA a nepadne
    prazdne = os.path.join(tmp, "bez_nastroje"); os.makedirs(prazdne)
    r = M._parita_server("de", "sk", repo=prazdne)
    over("A8f nastroj chybi / podproces selze -> jedna nesplnena podminka se vysvetlenim (brana nic mlcky nepropusti)", len(r) == 1 and r[0][0] is False and "nepodařilo ověřit" in r[0][1], r)
    # 9) sada v repu, ale API ji jeste nenacetlo (commit ceka na planovane nasazeni): NEZAVAZNE varovani (neblokuje go-live)
    r = M._podminky_jazyka("de", repo=t1, parita=uplna)
    over("A9a cekajici nasazeni sady NENI podminka go-live (podminky zustavaji splnene)", r and all(ok for ok, _ in r), [p for ok, p in r if not ok])
    cekaji = lambda base: [(False, f"sada api/jazyky/{base}.json je nasazená v běžícím API (nečeká na plánované nasazení) - čeká commit abc1234")]
    nasazeno_ok = lambda base: [(True, f"sada api/jazyky/{base}.json je nasazená v běžícím API (nečeká na plánované nasazení)")]
    w = M._varovani_jazyka("de", repo=t1, nasazeno=cekaji)
    over("A9b sada ceka na nasazeni -> varovani s commitem", len(w) == 1 and "abc1234" in w[0], w)
    over("A9c sada uz nasazena -> zadne varovani", M._varovani_jazyka("de", repo=t1, nasazeno=nasazeno_ok) == [], M._varovani_jazyka("de", repo=t1, nasazeno=nasazeno_ok))
    over("A9d sk / en / cs nemaji serverovou sadu -> zadne varovani (kontrola se ani nevola)", all(M._varovani_jazyka(l, repo=t1, nasazeno=lambda b: (_ for _ in ()).throw(AssertionError("nevolat"))) == [] for l in ("sk", "en", "cs")), None)
    over("A9e jazyk bez souboru sady -> zadne varovani (nesplnena je uz podminka existence)", M._varovani_jazyka("hu", repo=t7, nasazeno=cekaji) == [], M._varovani_jazyka("hu", repo=t7, nasazeno=cekaji))
    puvodni = M._sada_nasazena
    M._sada_nasazena = lambda *a, **k: (_ for _ in ()).throw(AssertionError("nasazeni se pro umele repo nema volat"))
    try:
        over("A9f umele repo bez parametru nasazeno: kontrola se nespousti", M._varovani_jazyka("de", repo=t1) == [], None)
    finally:
        M._sada_nasazena = puvodni
    # skutecna funkce _sada_nasazena nad dockou repa se stub nasazeni.py: ceka commit se sadou / s jinym souborem / nasazeni.py je rozbite
    import subprocess
    def repo_s_nasazenim(jmeno, stub):
        d = os.path.join(tmp, jmeno); os.makedirs(os.path.join(d, "scripts")); os.makedirs(os.path.join(d, "api", "jazyky"))
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", d] + list(a), capture_output=True, text=True, check=True).stdout.strip()
        git("init", "-q"); open(os.path.join(d, "api", "jazyky", "de.json"), "w").write("{}\n"); open(os.path.join(d, "api", "app.py"), "w").write("#\n"); git("add", "-A"); git("commit", "-q", "-m", "zaklad")
        open(os.path.join(d, "api", "jazyky", "de.json"), "w").write('{"x": 1}\n'); git("add", "-A"); git("commit", "-q", "-m", "sada")
        h_sada = git("rev-parse", "--short", "HEAD")
        open(os.path.join(d, "api", "app.py"), "w").write("# 2\n"); git("add", "-A"); git("commit", "-q", "-m", "jen app")
        h_app = git("rev-parse", "--short", "HEAD")
        open(os.path.join(d, "scripts", "nasazeni.py"), "w").write(stub(h_sada, h_app)); return d, h_sada, h_app
    stub_ceka_sadu = lambda hs, ha: "import json\nprint(json.dumps({'ceka': [{'hash': '%s'}, {'hash': '%s'}]}))\n" % (hs, ha)
    stub_ceka_app = lambda hs, ha: "import json\nprint(json.dumps({'ceka': [{'hash': '%s'}]}))\n" % ha
    stub_rozbite = lambda hs, ha: "raise SystemExit(3)\n"
    d1, hs1, _ = repo_s_nasazenim("nas1", stub_ceka_sadu)
    r = M._sada_nasazena("de", repo=d1)
    over("A9g mezi cekajicimi commity je commit se souborem sady -> nenasazena a jmenuje commit", len(r) == 1 and r[0][0] is False and hs1 in r[0][1], r)
    d2, _, _ = repo_s_nasazenim("nas2", stub_ceka_app)
    r = M._sada_nasazena("de", repo=d2)
    over("A9h cekajici je jen jiny commit (api/app.py) -> sada je nasazena", len(r) == 1 and r[0][0] is True, r)
    d3, _, _ = repo_s_nasazenim("nas3", stub_rozbite)
    r = M._sada_nasazena("de", repo=d3)
    over("A9i nasazeni.py selze -> nesplneno s vysvetlenim (neprojde mlcky), bez vyjimky", len(r) == 1 and r[0][0] is False and "nepodařilo se ověřit" in r[0][1], r)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# skutecne repo
for lg, ma_byt in (("sk", True), ("en", True), ("cs", None), ("de", None), ("hu", None)):
    r = M._podminky_jazyka(lg, repo=REPO)
    nespl = [p for ok, p in r if not ok]
    if ma_byt is True:
        over(f"R {lg}: skutecne repo splnuje vsechny jazykove podminky ({len(r)})", not nespl, nespl)
    else:
        print(f"info {lg}: {len(r) - len(nespl)}/{len(r)} podminek splneno" + ("" if not nespl else " | chybi: " + "; ".join(x[:70] for x in nespl[:4])))

ok = sum(vysl)
print(f"\nVYSLEDEK podminky jazykove uplnosti pri go-live: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
