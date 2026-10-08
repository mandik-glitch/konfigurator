#!/opt/konfigurator/api/venv/bin/python
"""Test CLI scripts/stul_karta_glb.py (GLB karty stolu z ulozeneho vyberu) nad DOCASNYMI tabulkami (bot10, 2026-10-07).

Karta se zalozi jadrem (api/stul_karta.py) do TEMPORARY tabulek se SKUTECNYM modelem; CLI funkce postav() pak bezi nad stejnym kurzorem. Overuje: stejne bajty jako verejny generator a jako GLB ulozeny
na karte, razitka jen na vyzadani, vsechny chybove cesty (kod 2 / 3 / 4) a atomicky zapis. main() se zkousi jen na neexistujici karte (cte ostrou DB, nic nezapisuje).

Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \
            api/venv/bin/python3 scripts/2026-10-07_stul_karta/test_karta_cli.py        (kandidat: KARTA_DIR=<adresar s kandidatnim stul_karta.py>)"""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
from contextlib import redirect_stderr, redirect_stdout

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
if os.environ.get("KARTA_DIR"):
    sys.path.insert(0, os.environ["KARTA_DIR"])
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
try:
    import app as appmod  # noqa: E402,F401
    import stul_karta as K  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import v3d_glb  # noqa: E402
finally:
    threading.Thread.start = _o
import stul_karta_glb as CLI  # noqa: E402
from _docasne import connect, KARTY, CIZI, stav_ostry, priprav  # noqa: E402

CLI._PRAVIDLA_NACTENA = True          # testy bezi nad docasnymi tabulkami a pravidla stolu drzi proces testu (nacitani z ostre DB by je prepsalo); nacitani pravidel hlida sekce 1b

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


def chyba(fn, *a, **k):
    try:
        fn(*a, **k)
    except CLI.CliChyba as e:
        return e
    return None


def main():
    pred = stav_ostry(K)
    test = connect()
    priprav(test, K)
    cur = test.cursor()
    tmp = tempfile.mkdtemp(prefix="stul_karta_cli_")
    try:
        sel = dict(SH.vychozi_vyber(40)); sel["w"] = 1330
        p = K.plan(cur, K._vstup({"product_id": KARTY[40], "configuration": {"selection": sel, "rules_version": None}}), True)
        nid, slug, vyber = K.vytvor(cur, 1, p, adresar_glb=tmp)         # skutecny model
        test.commit()
        ulozeny = open(os.path.join(tmp, p["sku"] + ".glb"), "rb").read()

        print("\n## 1) postav(): ulozeny GLB karty = model S razitky (pravidlo 61); bez --razitka model BEZ razitek jako verejny generator pred pravidlem 61")
        raw, info = CLI.postav(cur, nid)
        over("1.1 bez --razitka = verejny generator BEZ razitek (razitka=False); GLB ulozeny na karte je S razitky (razitka=True, pravidlo 61) a je tedy jiny", raw == SH.glb_bytes(p["res"]["selection"], 40, razitka=False)
             and ulozeny == SH.glb_bytes(p["res"]["selection"], 40, razitka=True) and raw != ulozeny, (len(raw), len(ulozeny)))
        over("1.2 info: id, SKU, system, hash (shoda), bytes, front 3 cisla, razitka false", info["id"] == nid and info["sku"] == p["sku"] and info["system"] == 40 and info["hash"] == p["res"]["hash"] and info["hash_shoda"] is True
             and info["bytes"] == len(raw) and len(info["front"]) == 3 and info["razitka"] is False, info)
        raw_r, info_r = CLI.postav(cur, nid, razitka=True)
        over("1.3 --razitka: jiny model nez bez prepinace (razitka loga), STEJNE bajty jako GLB ulozeny na karte, porad platny GLB s front", raw_r != raw and raw_r[:4] == b"glTF" and info_r["razitka"] is True and len(v3d_glb.embedded_spec(raw_r)["front"]) == 3
             and raw_r == ulozeny == SH.glb_bytes(p["res"]["selection"], 40, razitka=True), (len(raw_r), len(raw)))

        print("\n## 1b) CLI nacita ULOZENA pravidla stolu jako API (2026-10-08, karta #5361: system 40 ma u Roberta prah sirky stredni nohy 2000 misto 1500 -> CLI koncilo kodem 3)")
        import stul_api as SA_
        import stul_konfigurator as S_
        puv_pravidla = dict(S_.pravidla_systemu(40))
        ulozena = dict(puv_pravidla)
        ulozena["sirka_stredni_noha"] = 2000.0 if float(puv_pravidla["sirka_stredni_noha"]) != 2000.0 else 1800.0          # prah ruzny od aktualniho (pracovni stav procesu)
        sel_b = dict(SH.vychozi_vyber(40)); sel_b["w"] = 1710                                                                  # sirka mezi obema prahy: stredni noha jen pri nizsim prahu
        puv_obnov, puv_flag = SA_.obnov_pravidla, CLI._PRAVIDLA_NACTENA
        volani = []
        try:
            S_.nastav_pravidla(ulozena, system=40)                                                                              # "API" zaklada kartu s ulozenymi pravidly
            p_b = K.plan(cur, K._vstup({"product_id": KARTY[40], "configuration": {"selection": sel_b, "rules_version": None}}), True)
            nid_b, _slug_b, _vyber_b = K.vytvor(cur, 1, p_b, adresar_glb=tmp)
            test.commit()
            S_.nastav_pravidla(puv_pravidla, system=40)                                                                         # "cerstvy proces CLI": vychozi / jina pravidla
            CLI._PRAVIDLA_NACTENA = True                                                                                         # bez nacitani pravidel (puvodni chovani)
            e_b = chyba(CLI.postav, cur, nid_b)
            over("1b.1 bez nacitani ulozenych pravidel: hash nesedi (kod 3) - puvodni chyba CLI", e_b and e_b.kod == 3, e_b and (e_b.kod, e_b.zprava))
            CLI._PRAVIDLA_NACTENA = False                                                                                        # CLI zacina v cerstvem procesu: pravidla nacte samo
            SA_.obnov_pravidla = lambda force=False: (S_.nastav_pravidla(ulozena, system=40), volani.append(force))              # stul_api.obnov_pravidla: ulozena pravidla do generatoru
            raw_b, info_b = CLI.postav(cur, nid_b, razitka=True)
            over("1b.2 CLI nacte ulozena pravidla (obnov_pravidla jednou, force=True) a hash sedi: karta se postavi", volani == [True] and info_b["hash_shoda"] is True and info_b["hash"] == p_b["res"]["hash"], (volani, info_b))
            over("1b.3 model postaveny s ulozenymi pravidly = GLB ulozeny na karte (S razitky)", raw_b == open(os.path.join(tmp, p_b["sku"] + ".glb"), "rb").read(), len(raw_b))
            CLI.postav(cur, nid_b)
            over("1b.4 pravidla se nactou jen JEDNOU za proces (druhe volani postav je nenacita znovu)", volani == [True], volani)
        finally:
            SA_.obnov_pravidla, CLI._PRAVIDLA_NACTENA = puv_obnov, puv_flag
            S_.nastav_pravidla(puv_pravidla, system=40)

        print("\n## 2) chybove cesty")
        e = chyba(CLI.postav, cur, 99999999)
        over("2.1 neexistujici karta = kod 2", e and e.kod == 2, e and (e.kod, e.zprava))
        e = chyba(CLI.postav, cur, CIZI)
        over("2.2 karta, ktera neni STUL-S (priprava Multiboxu) = kod 2", e and e.kod == 2 and "STUL-S" in e.zprava, e and (e.kod, e.zprava))
        cur.execute("DELETE FROM app_settings WHERE setting_key=%s", ("stul_karta_%d" % nid,))
        e = chyba(CLI.postav, cur, nid)
        over("2.3 chybi zaznam stul_karta_<id> = kod 2", e and e.kod == 2, e and (e.kod, e.zprava))
        zaz = {"v": 1, "system": 35, "selection": vyber, "rules_version": "x", "hash": p["res"]["hash"], "kod": "K", "zdroj_karta": KARTY[40], "sku": p["sku"]}
        cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)", ("stul_karta_%d" % nid, json.dumps(zaz)))
        e = chyba(CLI.postav, cur, nid)
        over("2.4 system v zaznamu se lisi od SKU = kod 2", e and e.kod == 2 and "systém" in e.zprava, e and (e.kod, e.zprava))
        zaz.update(system=40, hash="0" * 16)
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", (json.dumps(zaz), "stul_karta_%d" % nid))
        e = chyba(CLI.postav, cur, nid)
        over("2.5 ulozeny hash nesedi s dnesnim = kod 3 (pravidla se zmenila)", e and e.kod == 3, e and (e.kod, e.zprava))
        raw3, info3 = CLI.postav(cur, nid, razitka=True, bez_kontroly=True)
        over("2.6 --bez-kontroly-hashe model i tak postavi (S razitky = GLB ulozeny na karte), hash_shoda false", raw3 == ulozeny and info3["hash_shoda"] is False, info3)
        zaz.update(hash=p["res"]["hash"])
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", (json.dumps(zaz), "stul_karta_%d" % nid))
        cur.execute("UPDATE shop_products SET sku=%s WHERE id=%s", ("STUL-S40-00000000", nid))
        e = chyba(CLI.postav, cur, nid)
        over("2.7 hash8 v SKU nesedi s hashem vyberu = kod 3", e and e.kod == 3, e and (e.kod, e.zprava))
        cur.execute("UPDATE shop_products SET sku=%s WHERE id=%s", (p["sku"], nid))
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", ("{neplatny json", "stul_karta_%d" % nid))
        e = chyba(CLI.postav, cur, nid)
        over("2.8 poskozeny zaznam = kod 2", e and e.kod == 2, e and (e.kod, e.zprava))
        zaz_zle = dict(zaz); zaz_zle["selection"] = {"w": "ne-cislo", "d": None}
        cur.execute("UPDATE app_settings SET setting_value=%s WHERE setting_key=%s", (json.dumps(zaz_zle), "stul_karta_%d" % nid))
        e = chyba(CLI.postav, cur, nid)
        over("2.9 vyber, ktery nejde postavit = kod 3 nebo 4 (nikdy vyjimka ven)", e and e.kod in (3, 4), e and (e.kod, e.zprava))

        print("\n## 3) zapis souboru a main()")
        cil = os.path.join(tmp, "vystup.glb")
        CLI.zapis_atomicky(cil, b"abc")
        over("3.1 zapis_atomicky: soubor existuje, zadny docasny nezustal", open(cil, "rb").read() == b"abc" and not [f for f in os.listdir(tmp) if f.endswith(".tmp")], os.listdir(tmp))
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = CLI.main(["99999999", "-o", os.path.join(tmp, "nic.glb")])
        over("3.2 main() na neexistujici karte: kod 2, hlaska na stderr, zadny vystupni soubor", rc == 2 and "neexistuje" in err.getvalue() and not os.path.exists(os.path.join(tmp, "nic.glb")), (rc, err.getvalue()))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                CLI.main(["12"])
                rc2 = None
            except SystemExit as ex:
                rc2 = ex.code
        over("3.3 main() bez -o i bez --info = chyba argumentu (kod 2)", rc2 == 2, rc2)
    finally:
        test.rollback()
        test.close()
        shutil.rmtree(tmp, ignore_errors=True)

    po = stav_ostry(K)
    print("\n## 9) ostre tabulky a adresar se nezmenily")
    over("9.1 ostre shop_products, registr, klice karet, audit_log i webapp/katalog/stul beze zmeny", pred == po, {k: (pred[k], po[k]) for k in pred if pred[k] != po[k]})
    print("\n%d/%d OK" % (sum(vysl), len(vysl)))
    sys.exit(0 if all(vysl) else 1)


main()
