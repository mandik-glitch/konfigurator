"""scene_materials.py - VYCHOZI VLASTNOSTI MATERIALU SCENY.

Robert 2026-09-10: *"Kdyz zmenim barvu napriklad na uhelniku tak se to
nedostane do dalsi sestavy, chybi tam tlacitko ulozit jako vychozi kterym
se pak prepocita vsechno stavajici."*

PROC TO DRIV NEFUNGOVALO:
Panel materialu ve scene (webapp/js/scene/material-panel.js) uklada barvu,
kovovost a drsnost do `localStorage`. To znamena:
  * hodnota plati jen v prohlizeci, kde se nastavila,
  * jina sestava otevrena jinde ji nevidi,
  * a hlavne o ni NEVI RENDEROVACI VETEV - scripts/2026-09-09_turntable_job.py
    ma tytez cisla natvrdo v PART_MATERIAL_COLOR/METALNESS/ROUGHNESS.
Bylo to takhle mysleno jako osobni ladeni ("kazdy si ladi svoje"), ale
chybel druhy krok: povysit naladene hodnoty na VYCHOZI pro vsechny.

JAK TO RESIME:
Jeden zaznam v `app_settings` pod klicem `scene_material_defaults` s JSON
mapou {klic_materialu: {color, metal, rough}}. Cte ho scena i renderovaci
vetev, takze existuje jedno misto pravdy.

PROC SE NIC "NEPREPOCITAVA":
Sestavy barvu dilu NENESOU - `product_assemblies.data.parts` ma jen
part_id/position/quaternion/scale (overeno 2026-09-10 na sestave 279).
Material se odvozuje az pri vykresleni z katalogu (`color_hex` ->
paleta), takze zmena vychozich hodnot se do VSECH sestav propise sama,
bez jakekoli migrace dat. Prepocitat je potreba jedine UZ VYRENDEROVANE
obrazky - ty se musi poslat do fronty znovu.
"""
import json
import os

from flask import jsonify, request

from app import app, get_conn, admin_required, log_audit

NASTAVENI_KLIC = "scene_material_defaults"

# Materialy, ktere se daji ulozit jako vychozi.
#
# `alu` (profily) se ve SCENE ovlada jinym panelem nez ostatni materialy -
# ma sve ctyri posuvniky na HDRI ovladaci, aby se ovladani neduplikovalo
# (Robert 2026-09-10: "jestli mas v materialech hlinik, a zaroven na
# hlavnim panelu tak se to bije"). ULOZISTE ale ma spolecne s ostatnimi,
# jinak by pro nej muselo vzniknout druhe, paralelni - presne ten stav,
# ktery Robert oznacil za neporadek ("cim se uklada nastaveni pro profily?
# postav to poradne").
POVOLENE_KLICE = {"alu", "zinc", "plast_svetly", "mdf", "black", "guma"}


def nacti_vychozi():
    """{klic: {color, metal, rough}} - prazdny slovnik, kdyz nic ulozeno."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s",
                    (NASTAVENI_KLIC,))
        row = cur.fetchone()
    if not row or not row.get("setting_value"):
        return {}
    try:
        data = json.loads(row["setting_value"])
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _je_hex(s):
    s = str(s or "").strip().lower()
    if len(s) != 7 or s[0] != "#":
        return None
    try:
        int(s[1:], 16)
    except ValueError:
        return None
    return s


def _prebarvi_katalog(zmeny):
    """Prepise `color_hex` u dilu, ktere se hlasily k PUVODNI barve materialu.

    Robert 2026-09-10: *"potrebujeme aby barva kterou nastavim pro ruzne
    objekty ve scene se ulozila napric vsemi sestavami I V KATALOGU"*,
    *"nekde proste musim nastavit ulozit a musi se to promitnout ve vsech
    stavajicich sestavach"*.

    PROC TO MUSI BYT: dil se ke svemu materialu hlasi VYHRADNE podle sve
    barvy z katalogu (viz resolve_material a material-panel.js). Kdyby se
    prepsala jen paleta a katalog zustal na starem odstinu, dily by se k
    materialu prestaly hlasit a zmena by se nikde neprojevila - presne to
    Robert hlasil u uhelniku ("Uhelniky nemeni barvu, ten zinek na to neni
    navazany").

    `zmeny` = [(stary_hex, novy_hex)]. Vraci pocty prepsanych radku a
    seznam radku PRED zmenou (pro zalohu).
    """
    conn = get_conn()
    pred, pocty = [], {"shop_products": 0, "cfg_dily": 0}
    with conn.cursor() as cur:
        for stary, novy in zmeny:
            if not stary or not novy or stary == novy:
                continue
            for tabulka, sloupec_id in (("shop_products", "id"), ("cfg_dily", "id")):
                cur.execute("SELECT %s AS id, color_hex FROM %s WHERE LOWER(color_hex)=%%s"
                            % (sloupec_id, tabulka), (stary,))
                radky = cur.fetchall()
                if not radky:
                    continue
                pred.extend({"tabulka": tabulka, "id": r["id"],
                             "color_hex": r["color_hex"]} for r in radky)
                cur.execute("UPDATE %s SET color_hex=%%s WHERE LOWER(color_hex)=%%s"
                            % tabulka, (novy, stary))
                pocty[tabulka] += cur.rowcount
    conn.commit()
    return pocty, pred


def _uloz_zalohu(pred):
    """Stav katalogu PRED prebarvenim - do backups/, nez se cokoli prepise."""
    if not pred:
        return None
    import datetime
    slozka = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "backups")
    os.makedirs(slozka, exist_ok=True)
    nazev = "%s_katalog_barvy_pred_zmenou.json" % datetime.date.today().isoformat()
    cesta = os.path.join(slozka, nazev)
    stare = []
    if os.path.exists(cesta):
        try:
            with open(cesta, encoding="utf-8") as fh:
                stare = json.load(fh)
        except (ValueError, OSError):
            stare = []
    with open(cesta, "w", encoding="utf-8") as fh:
        json.dump(stare + pred, fh, ensure_ascii=False, indent=1)
    return nazev


def _ocisti(data):
    """Propusti jen zname klice a hodnoty v rozsahu. Panel posila hodnoty
    z posuvniku, ale endpoint je verejne volatelny - nesmi jit ulozit
    nesmysl, ktery by pak rozbil kazdy render."""
    out = {}
    for klic, v in (data or {}).items():
        if klic not in POVOLENE_KLICE or not isinstance(v, dict):
            continue
        polozka = {}
        barva = str(v.get("color") or "").strip().lower()
        if len(barva) == 7 and barva[0] == "#":
            try:
                int(barva[1:], 16)
                polozka["color"] = barva
            except ValueError:
                pass
        for pole in ("metal", "rough"):
            try:
                cislo = float(v.get(pole))
            except (TypeError, ValueError):
                continue
            if 0.0 <= cislo <= 1.0:
                polozka[pole] = round(cislo, 4)
        if polozka:
            out[klic] = polozka
    return out


@app.get("/api/scene/material-defaults")
def scene_material_defaults_get():
    """Cte i scena pro prihlaseneho uzivatele - bez prav se vraci prazdno,
    aby se scena nerozbila (vychozi hodnoty ma i v kodu)."""
    return jsonify({"ok": True, "materials": nacti_vychozi()})


@app.post("/api/scene/material-defaults")
@admin_required
def scene_material_defaults_post():
    data = request.get_json(silent=True) or {}
    ocistene = _ocisti(data.get("materials"))
    if not ocistene:
        return jsonify({"ok": False, "error": "Zadne platne hodnoty k ulozeni."}), 400

    # Slucujeme, ne prepisujeme - panel muze poslat jen jeden material.
    slouceno = nacti_vychozi()
    slouceno.update(ocistene)

    # PREBARVENI KATALOGU: panel posila u kazdeho materialu i `prev` -
    # odstin, pod kterym se k nemu dily dosud hlasily. Bez nej bychom
    # nevedeli, ktere radky prepsat (paleta uz je nova).
    zmeny = []
    for klic, v in (data.get("materials") or {}).items():
        if klic not in ocistene or "color" not in ocistene[klic]:
            continue
        stary = _je_hex(v.get("prev"))
        novy = ocistene[klic]["color"]
        if stary and stary != novy:
            zmeny.append((stary, novy))

    pocty, pred = ({"shop_products": 0, "cfg_dily": 0}, [])
    zaloha = None
    if zmeny:
        pocty, pred = _prebarvi_katalog(zmeny)
        zaloha = _uloz_zalohu(pred)

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)",
            (NASTAVENI_KLIC, json.dumps(slouceno, ensure_ascii=False)))
    conn.commit()
    log_audit("scene_material_defaults", "update", None,
              "vychozi materialy sceny: %s; prebarveno v katalogu: %d produktu, %d dilu"
              % (", ".join(sorted(ocistene)), pocty["shop_products"], pocty["cfg_dily"]))
    return jsonify({"ok": True, "materials": slouceno,
                    "ulozeno": sorted(ocistene),
                    "prebarveno": pocty, "zaloha": zaloha})
