#!/usr/bin/env python3
"""GLB karty stolu z konfigurace (karta `STUL-S<system>-<hash8>`, vznika tlacitkem "Vytvorit kartu" v generatoru; bot10, 2026-10-07; kontrakt s bot4 / bot8 v docs/KONTRAKT_KARTA_Z_KONFIGURACE.md).

  scripts/stul_karta_glb.py <id karty> [--razitka] -o <vystup.glb>      postavi model karty znovu z ulozeneho vyberu (app_settings `stul_karta_<id>`)
  scripts/stul_karta_glb.py <id karty> --info                          jen vypise zaznam karty a overi hash (bez stavby modelu)

  --razitka           model S razitky loga na profilech (pro render a online nabidku; GLB ulozeny na karte, webapp/katalog/stul/<SKU>.glb, je od 2026-10-08 - pravidlo 61 - taky S razitky; bez prepinace model BEZ razitek = diagnostika)
  --bez-kontroly-hashe  postavi model i kdyz se kanonicky hash od zalozeni karty zmenil (zmena pravidel / RULES_VERSION) - jen diagnostika, model pak NEODPOVIDA karte

Kontrola, ktera ma "hotova k renderu" platit (bot4): SKU odpovida ^STUL-S(30|35|40|41|45)-[0-9a-f]{8}$, zaznam `stul_karta_<id>` existuje, system v SKU = system v zaznamu, hash8 v SKU = prvnich 8 znaku
KANONICKEHO hashe vyberu spocitaneho DNES (stul_glb.kanonicky_hash) a shoduje se s hashem ulozenym pri zalozeni. Cokoli nesedi = konec s chybou (kod 3), nikdy napul hotovy model.

Konci kodem: 0 ok | 2 neplatna karta / chybi zaznam | 3 hash nesedi (pravidla se zmenila) | 4 model nevznikl. Na stdout jeden radek JSON (id, sku, system, hash, bytes, razitka, front).
Cte jen (DB i soubory); DB prihlaseni bere z prostredi (systemd EnvironmentFile) nebo z api/.env pres scripts/_env.py.
ULOZENA PRAVIDLA STOLU (app_settings `stul_pravidla` = prahy po systemech + format tabule karty 4933) se nacitaji STEJNE jako v API pred kazdou trasou konfiguratoru (stul_api.obnov_pravidla): hash i model karty
zavisi na prazich (napr. sirka stredni nohy u systemu 40 = 2000 misto vychozich 1500). Bez toho by CLI pocitalo s vychozimi prahy a koncilo kodem 3 (hash nesedi), i kdyz se pravidla nezmenila (2026-10-08, karta #5361)."""
import argparse
import json
import os
import re
import sys
import tempfile
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKU_RE = re.compile(r"^STUL-S(30|35|40|41|45)-([0-9a-f]{8})$")            # stejne jako api/stul_karta.SKU_RE (kontrakt s bot4)
KLIC_KARTY = "stul_karta_"


class CliChyba(Exception):
    def __init__(self, kod, zprava):
        super().__init__(zprava)
        self.kod, self.zprava = kod, zprava


_PRAVIDLA_NACTENA = False          # nastavuje nacti_pravidla(); testy nad docasnymi tabulkami ho davaji na True (pravidla v procesu drzi test)


def nacti_pravidla():
    """Nacte ulozena pravidla stolu do generatoru (viz hlavicka): STEJNE jako API pred kazdou trasou konfiguratoru. Volat PRED otevrenim vlastniho spojeni / kurzoru (obnov_pravidla bere sdilene spojeni a jeho
    close() je rollback). Chyba cteni se jen zaloguje (stul_api) - hash pak sedet nebude a CLI skonci kodem 3, nikdy nepostavi model s tichymi vychozimi prahy."""
    global _PRAVIDLA_NACTENA
    import stul_api
    stul_api.obnov_pravidla(force=True)
    _PRAVIDLA_NACTENA = True


def _nacti_moduly():
    """Import api modulu bez spusteni "render-dozorce" (import app jinak po 60 s hlida zivou frontu renderu - viz paměť reference_import_app_spousti_render_dozorce)."""
    if not os.environ.get("DB_HOST"):
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        from _env import load_env
        for k, v in load_env().items():
            os.environ.setdefault(k, v)
    sys.path.insert(0, os.path.join(REPO, "api"))
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    puvodni = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else puvodni(self, *a, **k)
    try:
        import app as appmod
        import stul_shop
        import stul_glb
        import v3d_glb
    finally:
        threading.Thread.start = puvodni
    return appmod, stul_shop, stul_glb, v3d_glb


def zaznam_karty(cur, card_id):
    """-> (sku, zaznam) z DB; CliChyba 2, kdyz to neni karta stolu z konfigurace nebo chybi / je poskozeny zaznam."""
    cur.execute("SELECT sku FROM shop_products WHERE id=%s", (card_id,))
    row = cur.fetchone()
    if not row:
        raise CliChyba(2, "Karta #%s neexistuje." % card_id)
    m = SKU_RE.match(row["sku"] or "")
    if not m:
        raise CliChyba(2, "Karta #%s (%s) není karta stolu z konfigurace (SKU STUL-S<systém>-<hash8>)." % (card_id, row["sku"]))
    cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC_KARTY + str(card_id),))
    r = cur.fetchone()
    try:
        zaz = json.loads(r["setting_value"]) if r and r["setting_value"] else None
    except ValueError:
        zaz = None
    if not isinstance(zaz, dict) or not isinstance(zaz.get("selection"), dict) or zaz.get("system") not in (30, 35, 40, 41, 45):
        raise CliChyba(2, "Karta #%s nemá platný záznam %s%s (system, selection, hash)." % (card_id, KLIC_KARTY, card_id))
    if str(zaz["system"]) != m.group(1):
        raise CliChyba(2, "Karta #%s: systém v SKU (%s) se liší od systému v záznamu (%s)." % (card_id, m.group(1), zaz["system"]))
    return row["sku"], zaz


def postav(cur, card_id, razitka=False, bez_kontroly=False, moduly=None):
    """-> (bytes GLB, info dict). CliChyba 2 / 3 / 4 (viz hlavicka)."""
    appmod, SH, stul_glb, v3d_glb = moduly or _nacti_moduly()
    if not _PRAVIDLA_NACTENA:                                # volani mimo main(): pravidla se nactou tady (main() je nacita driv, pred otevrenim spojeni)
        nacti_pravidla()
    sku, zaz = zaznam_karty(cur, card_id)
    system, sel = zaz["system"], zaz["selection"]
    try:
        p, _ = SH.normalizuj(sel, system)
        dnes = stul_glb.kanonicky_hash(p)
    except Exception as e:                                   # noqa: BLE001
        raise CliChyba(4, "Uložený výběr karty #%s nejde normalizovat: %s" % (card_id, e))
    hash8 = SKU_RE.match(sku).group(2)
    if not bez_kontroly and (dnes[:8] != hash8 or (zaz.get("hash") and dnes != zaz["hash"])):
        raise CliChyba(3, "Hash karty #%s nesedí: SKU %s, uložený %s, dnešní %s – pravidla konfigurátoru se od založení změnila, model by neodpovídal kartě." % (card_id, hash8, zaz.get("hash"), dnes))
    try:
        raw = SH.glb_bytes(sel, system, razitka=bool(razitka))
        spec = v3d_glb.embedded_spec(raw)
    except Exception as e:                                   # noqa: BLE001
        raise CliChyba(4, "Model karty #%s se nepodařilo postavit: %s" % (card_id, e))
    front = spec.get("front") if isinstance(spec, dict) else None
    if not (isinstance(front, (list, tuple)) and len(front) == 3):
        raise CliChyba(4, "Model karty #%s nemá extras.v3d.front." % card_id)
    return raw, {"id": card_id, "sku": sku, "system": system, "hash": dnes, "hash_shoda": dnes == zaz.get("hash"), "bytes": len(raw), "razitka": bool(razitka), "front": list(front)}


def zapis_atomicky(cesta, data):
    adresar = os.path.dirname(os.path.abspath(cesta)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".stul_karta_glb_", suffix=".tmp", dir=adresar)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, cesta)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main(argv=None):
    ap = argparse.ArgumentParser(description="GLB karty stolu z konfigurace (STUL-S<systém>-<hash8>) z uloženého výběru")
    ap.add_argument("id", type=int, help="id karty (shop_products.id)")
    ap.add_argument("--razitka", action="store_true", help="model s razítky loga na profilech (uložený GLB karty je od 2026-10-08 taky s razítky)")
    ap.add_argument("-o", "--out", help="výstupní soubor .glb")
    ap.add_argument("--info", action="store_true", help="jen vypsat záznam a ověřit hash")
    ap.add_argument("--bez-kontroly-hashe", action="store_true", help="postavit i při změněném hashi (diagnostika)")
    a = ap.parse_args(argv)
    if not a.info and not a.out:
        ap.error("chybí -o <výstup.glb> (nebo --info)")
    try:
        moduly = _nacti_moduly()
        nacti_pravidla()                                     # ulozena pravidla stolu (prahy, format tabule) jako v API - PRED otevrenim spojeni
        conn = moduly[0].get_conn()
        try:
            with conn.cursor() as cur:
                if a.info:
                    sku, zaz = zaznam_karty(cur, a.id)
                    p, _ = moduly[1].normalizuj(zaz["selection"], zaz["system"])
                    dnes = moduly[2].kanonicky_hash(p)
                    print(json.dumps({"id": a.id, "sku": sku, "system": zaz["system"], "hash_ulozeny": zaz.get("hash"), "hash_dnes": dnes, "hash_shoda": dnes == zaz.get("hash") and dnes[:8] == SKU_RE.match(sku).group(2),
                                      "zdroj_karta": zaz.get("zdroj_karta"), "kod": zaz.get("kod")}, ensure_ascii=False))
                    return 0
                raw, info = postav(cur, a.id, a.razitka, a.bez_kontroly_hashe, moduly)
        finally:
            conn.rollback()
            conn.close()
        zapis_atomicky(a.out, raw)
        info["out"] = a.out
        print(json.dumps(info, ensure_ascii=False))
        return 0
    except CliChyba as e:
        print("CHYBA: " + e.zprava, file=sys.stderr)
        return e.kod


if __name__ == "__main__":
    sys.exit(main())
