"""VANDR SYSTEM U NAS - registr komponent (bot10, 2026-10-05). Robert: "Zacneme postupne pretahovat vandr system k nam. Priprav si nejakou strukturu pro ruzne
komponenty ... nemichat Vandr s prvni vetvi" (tj. s nativni / klasickou vetvi: komponenty, product_assemblies, cfg_dily, custom_shapes a jejich SKU).

Co to je: komponenty ze starsiho systemu vanDrawee (Unity + Laravel, `components` v DB vandrawee_work) preberane k nam jedna po druhe. Kazda komponenta ma v NASEM systemu:
  - radek v `vd_komponenty` (kod, nazvy, kategorie, typ pevny / parametricky, parametrizace, soubor modelu, vychozi cena a vaha, SKU a karta),
  - radky kusovniku v `vd_komponenty_dily` (dil, pocet, cena a vaha kusu, u delkove zavislych dilu pravidlo delky - cena a vaha za 1 mm),
  - model GLB v CHRANENE slozce `webapp/katalog/vandr/komponenty/<kod>.glb` (Vandr 3D se nesmi dostat verejne, jen zamestnanci / podepsana nabidka).
OKOLI: tabulky `vd_*` a SKU `VDK-...` jsou VLASTNI prostor Vandr systemu. Nic z toho se nezapisuje do nativni vetve (tabulky `komponenty*`, `product_assemblies`, `cfg_dily`,
`custom_shapes`) a SKU `VD-<uuid>` zustava automatum Vandru (cena-sync, razitka, render, aktivace berou VSECHNY `VD-%` jako sestavy z FBX a ctou z SKU uuid).

Cena parametricke komponenty se pocita jako ve Vandru (app/Models/Part.php::computePriceWeight): cena komponentu = SOUCET cen dilu x pocet; dil s pevnou cenou (vcetne operaci) ma
`cena_ks`, delkove zavisly dil ma navic `delka_pravidlo` {sablona, delka0, cena_za_mm, vaha_za_mm} - cena a vaha novych delek se pocitaji z materialu, operace se nemeni.

Modul je bez Flasku a bez zavislosti na nativni vetvi: funkce nad slovniky (`kusovnik`, `cena`, `over_hodnoty`) a nad kurzorem (`nacti_komponentu`, `zaregistruj`, `zaloz_schema`).
Docs: docs/VANDR_SYSTEM.md."""
import datetime
import decimal
import json
import os
import re

SKU_PREFIX = "VDK-"                     # komponenty Vandr systemu; `VD-<uuid>` = sestavy z FBX (automaty Vandru), klasicka (1.) vetev ma jina SKU
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLB_DIR = os.path.join(REPO, "webapp", "katalog", "vandr", "komponenty")
KOD_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TYPY = ("pevny", "parametricky")
STAVY = ("koncept", "schvaleno")

DDL = [
    """CREATE TABLE IF NOT EXISTS vd_komponenty (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        kod VARCHAR(80) NOT NULL,
        sku VARCHAR(80) NULL,
        shop_product_id INT NULL,
        vandr_unity_id VARCHAR(160) NULL,
        vandr_component_id INT NULL,
        nazev_cs VARCHAR(255) NOT NULL,
        nazev_en VARCHAR(255) NULL,
        kategorie VARCHAR(60) NULL,
        typ ENUM('pevny','parametricky') NOT NULL DEFAULT 'pevny',
        hloubka_mm DECIMAL(8,1) NULL,
        parametrizace_json JSON NULL,
        glb_soubor VARCHAR(255) NULL,
        mena CHAR(3) NOT NULL DEFAULT 'CZK',
        cena0 DECIMAL(12,2) NOT NULL,
        vaha0_g DECIMAL(12,2) NOT NULL,
        cenik_snimek DATE NULL,
        stav ENUM('koncept','schvaleno') NOT NULL DEFAULT 'koncept',
        poznamka TEXT NULL,
        created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_vd_komponenty_kod (kod),
        UNIQUE KEY uq_vd_komponenty_sku (sku),
        KEY ix_vd_komponenty_shop (shop_product_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
    """CREATE TABLE IF NOT EXISTS vd_komponenty_dily (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        komponenta_id INT NOT NULL,
        poradi INT NOT NULL,
        dil VARCHAR(160) NOT NULL,
        ks INT NOT NULL,
        cena_ks DECIMAL(12,4) NOT NULL,
        vaha_ks_g DECIMAL(12,4) NOT NULL,
        delka_pravidlo_json JSON NULL,
        UNIQUE KEY uq_vd_dily_poradi (komponenta_id, poradi),
        CONSTRAINT fk_vd_dily_komponenta FOREIGN KEY (komponenta_id) REFERENCES vd_komponenty (id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci""",
]


def zaloz_schema(cur):
    """Idempotentne zalozi tabulky vd_* (CREATE TABLE IF NOT EXISTS)."""
    for sql in DDL:
        cur.execute(sql)


def kod_na_sku(kod):
    """SKU karty komponentu: `VDK-` + kod velkymi pismeny (kod `kufrik-3x43-vysuv-d459` -> `VDK-KUFRIK-3X43-VYSUV-D459`)."""
    if not KOD_RE.match(kod or ""):
        raise ValueError("neplatny kod komponentu: %r (male pismeno / cislice oddelene pomlckou)" % (kod,))
    return SKU_PREFIX + kod.upper()


def glb_cesta(komp):
    """Absolutni cesta k souboru modelu komponentu (nebo None); lezi v chranene slozce, verejne se NIKDY neservíruje."""
    if not komp.get("glb_soubor"):
        return None
    cesta = os.path.realpath(os.path.join(GLB_DIR, komp["glb_soubor"]))
    if not cesta.startswith(os.path.realpath(GLB_DIR) + os.sep):
        raise ValueError("soubor modelu mimo slozku komponent")
    return cesta


def _json(v):
    if v is None or isinstance(v, (dict, list)):
        return v
    return json.loads(v)


def nacti_komponentu(cur, kod):
    """Komponenta vcetne kusovniku a parametrizace (slovnik) nebo None. `cur` = kurzor se slovniky (pymysql DictCursor, jako v aplikaci)."""
    cur.execute("SELECT * FROM vd_komponenty WHERE kod=%s", (kod,))
    k = cur.fetchone()
    if not k:
        return None
    k = {n: (float(v) if isinstance(v, decimal.Decimal) else v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v) for n, v in k.items()}
    k["parametrizace"] = _json(k.pop("parametrizace_json", None))
    cur.execute("SELECT poradi, dil, ks, cena_ks, vaha_ks_g, delka_pravidlo_json FROM vd_komponenty_dily WHERE komponenta_id=%s ORDER BY poradi", (k["id"],))
    k["dily"] = [{"poradi": r["poradi"], "dil": r["dil"], "ks": int(r["ks"]), "cena_ks": float(r["cena_ks"]), "vaha_ks_g": float(r["vaha_ks_g"]),
                  "delka_pravidlo": _json(r["delka_pravidlo_json"])} for r in cur.fetchall()]
    for c in ("cena0", "vaha0_g"):
        k[c] = float(k[c])
    return k


# ------------------------------------------------------------------------------------------------------------------------- parametry a cena
def _parametry(komp):
    p = komp.get("parametrizace") or {}
    return list(p.get("parametry") or [])


def hodnoty_vychozi(komp):
    """{id parametru: vychozi hodnota}; u pevne komponenty prazdne."""
    return {p["id"]: p["vychozi"] for p in _parametry(komp)}


def over_hodnoty(komp, hodnoty=None):
    """Hodnoty parametru doplni vychozimi a zkontroluje (znamy parametr, cislo, rozsah min-max); ValueError pri chybe. Vraci novy slovnik."""
    zn = {p["id"]: p for p in _parametry(komp)}
    out = hodnoty_vychozi(komp)
    for k, v in (hodnoty or {}).items():
        if k not in zn:
            raise ValueError("neznamy parametr '%s' komponentu %s" % (k, komp.get("kod")))
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
            raise ValueError("parametr '%s' musi byt cislo" % k)
        p = zn[k]
        if not (p["min"] <= v <= p["max"]):
            raise ValueError("parametr '%s' = %s mm je mimo rozsah %s-%s mm" % (k, v, p["min"], p["max"]))
        out[k] = v
    return out


def delta_mm(komp, hodnoty=None):
    """Zmena rozmeru proti vychozimu (mm) u parametricke komponenty typu 'natazeni_podle_roviny' (jediny parametr); 0 u pevne komponenty."""
    par = komp.get("parametrizace")
    if not par or not _parametry(komp):
        return 0.0
    if par.get("typ") != "natazeni_podle_roviny":
        raise ValueError("neznamy typ parametrizace: %r" % (par.get("typ"),))
    h = over_hodnoty(komp, hodnoty)
    p = _parametry(komp)[0]
    return float(h[p["id"]]) - float(p["vychozi"])


def _fmt_delka(v):
    return "%g" % (round(v * 10) / 10)


def kusovnik(komp, hodnoty=None):
    """Kusovnik, cena a vaha komponentu pro hodnoty parametru: pevne dily beze zmeny, delkove zavisle s cenou a vahou prepoctenou z materialu a upravenym nazvem.
    -> {"hodnoty", "mena", "cena", "vaha_g", "cenik_snimek", "radky": [{"dil", "ks", "cena_ks", "cena", "vaha_ks_g", "zmena"}]}"""
    d = delta_mm(komp, hodnoty)
    radky, cena, vaha = [], 0.0, 0.0
    for r in komp["dily"]:
        c, v, jm = r["cena_ks"], r["vaha_ks_g"], r["dil"]
        pr = r.get("delka_pravidlo")
        if pr:
            c += pr["cena_za_mm"] * d
            v += pr["vaha_za_mm"] * d
            jm = pr["sablona"].replace("{L}", _fmt_delka(pr["delka0"] + d))
        cena += c * r["ks"]
        vaha += v * r["ks"]
        radky.append({"dil": jm, "ks": r["ks"], "cena_ks": round(c, 2), "cena": round(c * r["ks"], 2), "vaha_ks_g": round(v, 2), "zmena": bool(pr)})
    return {"hodnoty": over_hodnoty(komp, hodnoty), "mena": komp.get("mena", "CZK"), "cena": round(cena, 2), "vaha_g": round(vaha, 2),
            "cenik_snimek": str(komp["cenik_snimek"]) if komp.get("cenik_snimek") else None, "radky": radky}


def cena(komp, hodnoty=None):
    return kusovnik(komp, hodnoty)["cena"]


# ------------------------------------------------------------------------------------------------------------------------- zapis (registrace)
def pripoj_kartu(cur, kod, shop_product_id):
    """Zapise do registru SKU (z kodu) a id produktove karty komponentu; jine SKU / jine id uz zapsane = ValueError (karta se nepreklapa). Vraci SKU. Transakci ridi volajici."""
    sku = kod_na_sku(kod)
    cur.execute("SELECT id, sku, shop_product_id FROM vd_komponenty WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if not r:
        raise ValueError("komponenta %s neni v registru" % kod)
    if (r["sku"] not in (None, sku)) or (r["shop_product_id"] not in (None, shop_product_id)):
        raise ValueError("komponenta %s uz ma kartu: SKU %s, id %s" % (kod, r["sku"], r["shop_product_id"]))
    cur.execute("UPDATE vd_komponenty SET sku=%s, shop_product_id=%s WHERE id=%s", (sku, int(shop_product_id), r["id"]))
    if cur.rowcount not in (0, 1):
        raise ValueError("neocekavany pocet upravenych radku: %s" % cur.rowcount)
    return sku


def zaregistruj(cur, d):
    """Zalozi / aktualizuje komponentu podle `kod` (upsert) a nahradi jeji kusovnik. `d` = slovnik: kod, nazev_cs, [nazev_en, kategorie, typ, hloubka_mm, parametrizace (dict),
    glb_soubor, mena, cena0, vaha0_g, cenik_snimek, vandr_unity_id, vandr_component_id, stav, poznamka], dily = [{dil, ks, cena_ks, vaha_ks_g, [delka_pravidlo]}].
    Vraci id. Kontroluje, ze soucet dilu = cena0 / vaha0_g (kusovnik a hlavicka si nesmi odporovat). Transakci ridi volajici (commit)."""
    kod = d["kod"]
    kod_na_sku(kod)                                              # validace tvaru
    typ = d.get("typ", "pevny")
    if typ not in TYPY or d.get("stav", "koncept") not in STAVY:
        raise ValueError("neplatny typ nebo stav")
    if typ == "parametricky" and not (d.get("parametrizace") or {}).get("parametry"):
        raise ValueError("parametricka komponenta musi mit parametrizaci s parametry")
    dily = d["dily"]
    soucet_c = round(sum(float(r["cena_ks"]) * int(r["ks"]) for r in dily), 2)
    soucet_v = round(sum(float(r["vaha_ks_g"]) * int(r["ks"]) for r in dily), 2)
    if abs(soucet_c - float(d["cena0"])) > 0.01 or abs(soucet_v - float(d["vaha0_g"])) > 0.01:
        raise ValueError("soucet dilu (%.2f, %.2f g) nesedi s cena0 / vaha0_g (%s, %s)" % (soucet_c, soucet_v, d["cena0"], d["vaha0_g"]))
    sloupce = {"kod": kod, "nazev_cs": d["nazev_cs"], "nazev_en": d.get("nazev_en"), "kategorie": d.get("kategorie"), "typ": typ, "hloubka_mm": d.get("hloubka_mm"),
               "parametrizace_json": json.dumps(d["parametrizace"], ensure_ascii=False) if d.get("parametrizace") else None, "glb_soubor": d.get("glb_soubor"),
               "mena": d.get("mena", "CZK"), "cena0": d["cena0"], "vaha0_g": d["vaha0_g"], "cenik_snimek": d.get("cenik_snimek"), "vandr_unity_id": d.get("vandr_unity_id"),
               "vandr_component_id": d.get("vandr_component_id"), "stav": d.get("stav", "koncept"), "poznamka": d.get("poznamka")}
    cur.execute("SELECT id FROM vd_komponenty WHERE kod=%s", (kod,))
    r = cur.fetchone()
    if r:
        kid = r["id"] if isinstance(r, dict) else r[0]
        sets = ", ".join("%s=%%s" % k for k in sloupce if k != "kod")
        cur.execute("UPDATE vd_komponenty SET " + sets + " WHERE id=%s", [v for k, v in sloupce.items() if k != "kod"] + [kid])
    else:
        cur.execute("INSERT INTO vd_komponenty (" + ", ".join(sloupce) + ") VALUES (" + ", ".join(["%s"] * len(sloupce)) + ")", list(sloupce.values()))
        kid = cur.lastrowid
    cur.execute("DELETE FROM vd_komponenty_dily WHERE komponenta_id=%s", (kid,))                     # jen v NASI tabulce
    for i, x in enumerate(dily, 1):
        cur.execute("INSERT INTO vd_komponenty_dily (komponenta_id, poradi, dil, ks, cena_ks, vaha_ks_g, delka_pravidlo_json) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (kid, i, x["dil"], int(x["ks"]), x["cena_ks"], x["vaha_ks_g"], json.dumps(x["delka_pravidlo"], ensure_ascii=False) if x.get("delka_pravidlo") else None))
    return kid
