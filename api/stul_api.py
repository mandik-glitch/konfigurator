"""API konfiguratoru stolu (bot8, 2026-10-02) - tenka vrstva nad api/stul_konfigurator.py.

  GET /api/stul/konfigurace?sirka=1200&hloubka=800&vyska=840&police=1&kolecka=1&panely=1&led=1&suplik=1&elektrozlab=1
                           &drzak_pet=1&suplik_posun=0&stredni_noha=600
      -> {parametry, dily, problemy, rozmery, spoje, pocet_spoju, volby, rozsah}
      `dily` = pole ve formatu custom_shapes.data.parts (scena je vlozi pres insertCustomShape), `problemy` = porusena
      konstrukcni pravidla (prazdne = vse napojeno), `volby` = pro kazdy vypnuty prepinac null nebo duvod, proc ho nelze zapnout.
      Vsechny parametry jsou nepovinne (vychozi = konfigurace #577); chybny vstup -> 400 {error, kod}.

Zatim JEN pro zamestnance (@staff_required) - cte ho stranka Generator stolu (webapp/stul-konfigurator.html ma query ve vyrobnich odkazech) a prijemce ve scene
(webapp/js/scene/stul-konfigurator.js: stul poslany z teto stranky tlacitkem "Vlozit do Sceny").
Zakaznicky prohlizec + cena/kosik navazuji pozdeji (bot5: api/configurator_price.py bere stejne `dily`).
Zadny zapis do DB, zadny stav - cista funkce parametru.
"""
import json
import math
import re
import time

from flask import Response, jsonify, request

from app import app, get_conn, staff_required, require_permission, get_setting, admin_required
import configurator_price
import stul_glb
import stul_konfigurator as S

_CTX = {"t": 0.0, "ctx": None}
CTX_TTL_S = 120          # katalog cen se mezi pozadavky nemeni (a slider vola API opakovane)
SAZBA_DPH = 21.0         # jako v kontraktu konfiguratoru (price.vat_rate); cenu pocita server

# karty, ktere nejsou viditelne ve scene ani nemaji GLB (load_ctx je proto nezna), ale konfigurator je potrebuje ocenit: tvar vyrabi stul_glb,
# cena je cena karty (jen cteni; karta zustava neaktivni - pravidlo 54). 3025 = Kulickova jednotka 15mm - 20kg (Kola Pirkl) = loziskova jednotka
DOPLNKOVE_KARTY = (3025, 3251)      # 3025 loziskova jednotka, 3251 vyrovnavaci patka M8 (Dogus; zaslepka 3071 je ve scene viditelna = v ctx uz je)


# spojovaci material ke spojkam (Robert 2026-10-04): karty se hledaji podle SKU (S.SPOJOVACI_MATERIAL); chybi-li karta v katalogu, radek v kusovniku je, ale bez ceny
DOPLNKOVE_SKU = tuple(sorted({sku for lst in S.SPOJOVACI_MATERIAL.values() for sku, _ks, _n in lst if sku}))


def _doplnky_ctx(cur, ctx):
    cur.execute("SELECT id, name, sku, weight_g, price_czk_placeholder, unit, dogus_url, is_profile_material FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(DOPLNKOVE_KARTY)) + ")"
                " OR sku IN (" + ",".join(["%s"] * len(DOPLNKOVE_SKU)) + ")", tuple(DOPLNKOVE_KARTY) + tuple(DOPLNKOVE_SKU))
    for r in cur.fetchall():
        part_id = f"product_{r['id']}"
        if part_id in ctx["parts"]:
            continue
        ctx["parts"][part_id] = {
            "id": part_id, "name": r["name"], "layer": "produkt", "sku": r.get("sku"),
            "length_mm": None, "cross_section_mm": [None, None],
            "weight_kg": float(r["weight_g"]) / 1000 if r["weight_g"] is not None else None,
            "price_czk": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None, "price_per_cut_czk": None,
            "is_board_material": False, "source": "product", "scene_coef": bool(r.get("is_profile_material")) or bool(r.get("dogus_url")),
            "unit": (r.get("unit") or "").strip().lower() or None, "price_basis": None,
        }


def _ctx_ceny():
    """Kontext cen (katalog dilu, sazby) - cte se pres kurzor bez commitu/rollbacku, drzi se TTL sekund."""
    if _CTX["ctx"] is None or time.time() - _CTX["t"] > CTX_TTL_S:
        conn = get_conn()
        cur = conn.cursor()
        ctx = configurator_price.load_ctx(cur)
        pred = set(ctx["parts"])
        _doplnky_ctx(cur, ctx)
        configurator_price.apply_scene_coefficient([v for k, v in ctx["parts"].items() if k not in pred], ctx["pricing"].get("scene_price_coefficient", 1.0))     # dily z Dogusu stejne jako ve scene
        _CTX["ctx"] = ctx
        _CTX["t"] = time.time()
    return _CTX["ctx"]


def nazvy_karet(ctx=None):
    """{sku: nazev karty} spojovaciho materialu ke spojkam - nazvy dava KARTA v katalogu (nic si nevymyslime); SKU bez karty tu neni."""
    ctx = ctx or _ctx_ceny()
    return {str(v["sku"]): v["name"] for v in ctx["parts"].values() if v.get("sku") and str(v["sku"]) in DOPLNKOVE_SKU}


def entries_s_materialem(dily, ctx=None):
    """(entries, chybejici): polozky ceny dilu stolu (S.entries_pro_cenu) + SPOJOVACI MATERIAL ke spojkam (S.spojovaci_material) jako polozky podle karty z katalogu (SKU -> part_id).
    `chybejici` = [{sku, nazev, mnozstvi}] materialu, ktery nema v katalogu kartu (cena se nezapocita; kusovnik ho ukaze s varovanim)."""
    ctx = ctx or _ctx_ceny()
    sku_na_id = {str(v.get("sku")): k for k, v in ctx["parts"].items() if v.get("sku")}
    entries, chybejici = list(S.entries_pro_cenu(dily)), []
    for m in S.spojovaci_material(dily, nazvy_karet(ctx)):
        pid = sku_na_id.get(str(m["sku"])) if m["sku"] else None
        if pid is None:
            chybejici.append({"sku": m["sku"], "nazev": m["nazev"], "mnozstvi": m["mnozstvi"]})
            continue
        entries.extend({"part_id": pid} for _ in range(m["mnozstvi"]))
    return entries, chybejici


def cena_navleku(delka_mm, system=None):
    """Cena JEDNOHO navleku nohy (jekl 40x40x2 vc. zaslepky, Kc bez DPH) pri delce `delka_mm` (200-400): Robert 2026-10-05 - 200 mm = 370 Kc, 400 mm = 550 Kc, mezi tim linearne (pravidla
    `cena_navlek_200` / `cena_navlek_400` v Pravidlech stolu SYSTEMU `system` (None = aktivni); vychozi 370 / 550)."""
    c200 = float(S.pravidlo("cena_navlek_200", system) or 0)
    c400 = float(S.pravidlo("cena_navlek_400", system) or 0)
    d0, d1 = S.ROZSAH["navlek_delka"]
    return round(c200 + (c400 - c200) * (float(delka_mm) - d0) / (d1 - d0), 2)


def cena_nohy_sse(spojnice_mm, system=None):
    """Cena JEDNE nohy SSE (2 jekly 40x40, spojnice, 2 plechove patky, 2 vnitrni profily 35x35 se zaslepkami; Kc bez DPH) pri delce jeklove spojnice `spojnice_mm` (400-1100): pravidla
    `cena_noha_sse_400` / `cena_noha_sse_1100` v Pravidlech stolu SYSTEMU `system` (None = aktivni), mezi nimi linearne. Nezadano = 0."""
    c0 = float(S.pravidlo("cena_noha_sse_400", system) or 0)
    c1 = float(S.pravidlo("cena_noha_sse_1100", system) or 0)
    d0, d1 = S.SSE_SPOJNICE_MIN, S.SSE_SPOJNICE_MAX
    return round(c0 + (c1 - c0) * (float(spojnice_mm) - d0) / (d1 - d0), 2)


def spojnice_nohou_sse(dily):
    """{delka spojnice (mm): pocet nohou SSE} z dilu stolu (spojnice = jekl lezici podel hloubky; svisle jekly maji kvaternion identity)."""
    out = {}
    for d in dily:
        if d["part_id"] == S.SSE_JEKL_PART and abs(d["quaternion"][2]) > 0.5:
            L = round(1000.0 * d["scale"][1], 1)
            out[L] = out.get(L, 0) + 1
    return out


def extra_prace(dily, system=None):
    """Dalsi prace do ceny mimo dily: CENA ZA VYREZ v pracovni desce (Robert 2026-10-04: "cenu za vyrez chci stanovovat primo v generatoru" - pravidlo `cena_vyrez`, Kc bez DPH za kus)
    a NAVLEKY NOHOU (Robert 2026-10-05: jekl 40x40x2 vc. zaslepky, cena podle delky - viz cena_navleku; kazda noha jeden kus). Pravidla (ceny) jsou PO SYSTEMECH: `system` None = podle dilu sestavy."""
    system = system or S.system_z_dilu(dily)
    n = sum(int(d.get("deska_vyrezu") or 0) for d in dily)
    c = float(S.pravidlo("cena_vyrez", system) or 0)
    out = [{"name": "Výřezy v pracovní desce", "qty": n, "unit_czk": c}] if (n and c) else []
    podle_delky = {}
    for d in dily:
        if d["part_id"] == S.NAVLEK_PART:
            L = round(1000.0 * d["scale"][1], 1)
            podle_delky[L] = podle_delky.get(L, 0) + 1
    for L in sorted(podle_delky):
        out.append({"name": f"Návlek nohy – jekl 40×40×2, délka {L:g} mm, {S.NAVLEK_BARVA} lesk (vč. záslepky)", "qty": podle_delky[L], "unit_czk": cena_navleku(L, system)})
    if system == S.SYSTEM_SSE:                                  # nohy SSE: cena je pravidlo (dily nohy nemaji kartu katalogu), podle delky spojnice; nezadana cena (0) se do ceny nepocita
        nohy = spojnice_nohou_sse(dily)
        for L in sorted(nohy):
            c = cena_nohy_sse(L, system)
            if c:
                out.append({"name": f"Noha SSE – jeklová spojnice {L:g} mm (2 jekly 40×40, plechové patky, vnitřní profily 35×35, záslepky), {S.NAVLEK_BARVA} lesk", "qty": nohy[L], "unit_czk": c})
    return out


def cena_konfigurace(dily, system=None):
    """{bez_dph, s_dph, mena, souhrn, varovani} z dilu stolu (stejna pravidla jako cena sestavy ve scene) + spojovaci material ke spojkam, nebo None. `system` None = podle dilu sestavy
    (ceny vyrezu a navleku jsou pravidla po systemech)."""
    system = system or S.system_z_dilu(dily)
    try:
        entries, chybejici = entries_s_materialem(dily)
        r = configurator_price.price_entries(entries, _ctx_ceny(), extra_work=extra_prace(dily, system))
    except Exception as e:                                   # cena je doplnek - chyba nesmi shodit konfigurator
        app.logger.warning("stul: cena konfigurace selhala: %s", e)
        return None
    ps = r["price_summary"]
    s_dph = round(ps["total_czk"] * (1 + SAZBA_DPH / 100.0))
    varovani_noha = (["Cena nohou SSE není zadaná – doplň ji v Pravidlech stolu (systém SSE: cena nohy SSE); do ceny se zatím nepočítají."]
                     if system == S.SYSTEM_SSE and any(not cena_nohy_sse(L, system) for L in spojnice_nohou_sse(dily)) else [])
    kus = kusovnik_z_ceny(r, _ctx_ceny(), s_dph, chybejici)
    kus["varovani"] = list(kus.get("varovani") or []) + varovani_noha                               # staff stranka ukazuje varovani kusovniku (ne cena.varovani)
    return {"bez_dph": ps["total_czk"], "s_dph": s_dph, "sazba_dph": SAZBA_DPH,
            "mena": "CZK", "souhrn": {k: ps.get(k) for k in ("material_czk", "cut_czk", "joint_czk", "accessory_czk", "packaging_czk", "joint_count", "weight_kg")},
            "kusovnik": kus,
            "varovani": r.get("warnings", []) + [f"Chybí karta v katalogu: {m['nazev']}" + (f" [{m['sku']}]" if m["sku"] else " [SKU zatím není určeno]") + f" – {m['mnozstvi']} ks bez ceny" for m in chybejici]
            + varovani_noha}


def kusovnik_z_ceny(r, ctx, s_dph, chybejici=None):
    """Kompletni kusovnik s cenami pro zamestnance (Robert 2026-10-03: "potrebuju videt v generatoru internim kompletni kusovnik s cenami"): radky dilu z
    configurator_price.price_entries (profily, desky, prislusenstvi - kazdy radek ma SKU v nazvu) + vse, co cenu doplnuje (rezy, pausal za profil, spoje, spojovaci
    material na spoj, balne) a zaokrouhleni, aby SOUCET RADKU = CELKEM bez DPH. Vsechny castky v Kc bez DPH. Jen pro zamestnance (verejne API ceny po radcich nevraci)."""
    ps, pr = r["price_summary"], ctx["pricing"]
    radky = [{"nazev": b["name"], "rozmer": b["dim"], "mnozstvi": b["qty"], "cena_ks": b["unit_price"], "celkem": b["total"]} for b in r["bom"]]
    for m in chybejici or []:                       # spojovaci material bez karty v katalogu: radek je (at se na nej nezapomene), cena 0 a varovani
        radky.append({"nazev": m["nazev"] + (f" [{m['sku']}]" if m["sku"] else " [SKU zatím není určeno]") + " – karta chybí v katalogu", "rozmer": None, "mnozstvi": m["mnozstvi"], "cena_ks": None, "celkem": 0})
    prace = []
    if ps.get("cut_czk"):
        prace.append({"nazev": "Řezy profilů", "rozmer": None, "mnozstvi": None, "cena_ks": None, "celkem": ps["cut_czk"]})        # jen profily - rezy desek se neceni (Robert 2026-10-04)
    fee = pr.get("profile_flat_fee_czk") or 0
    if ps.get("profile_flat_fee_czk"):
        prace.append({"nazev": "Paušál za profil", "rozmer": None, "mnozstvi": round(ps["profile_flat_fee_czk"] / fee) if fee else None, "cena_ks": fee or None, "celkem": ps["profile_flat_fee_czk"]})
    if ps.get("joint_czk"):
        prace.append({"nazev": "Spoje profilů", "rozmer": None, "mnozstvi": ps.get("joint_count"), "cena_ks": pr.get("joint_price_czk"), "celkem": ps["joint_czk"]})
    for acc in pr.get("accessories") or []:
        mnozstvi = (acc.get("qty_per_joint") or 0) * (ps.get("joint_count") or 0)
        if mnozstvi:
            prace.append({"nazev": "Spojovací materiál: " + str(acc.get("name")), "rozmer": None, "mnozstvi": mnozstvi, "cena_ks": acc.get("price_czk"),
                          "celkem": round(mnozstvi * (acc.get("price_czk") or 0))})
    for x in ps.get("extra_work") or []:
        prace.append({"nazev": x["name"], "rozmer": None, "mnozstvi": x["qty"], "cena_ks": x["unit_czk"], "celkem": x["czk"]})
    if ps.get("packaging_czk"):
        prace.append({"nazev": "Balné (" + ("%g" % (pr.get("packaging_pct") or 0)) + " %)", "rozmer": None, "mnozstvi": None, "cena_ks": None, "celkem": ps["packaging_czk"]})
    soucet = sum(x["celkem"] for x in radky) + sum(x["celkem"] for x in prace)
    if soucet != ps["total_czk"]:
        prace.append({"nazev": "Zaokrouhlení (ceny za kus × množství)", "rozmer": None, "mnozstvi": None, "cena_ks": None, "celkem": ps["total_czk"] - soucet})
    return {"radky": radky, "prace": prace,
            "celkem": {"bez_dph": ps["total_czk"], "dph": s_dph - ps["total_czk"], "s_dph": s_dph, "sazba_dph": SAZBA_DPH},
            "montaz": {"pct": ps.get("montaz_pct_applied") or 0, "czk": ps.get("montaz_czk") or 0, "poznamka": "volitelná služba, není v ceně"},
            "hmotnost_kg": ps.get("weight_kg"), "varovani": r.get("warnings", [])}


# ---- NASTAVITELNA PRAVIDLA STOLU (Robert 2026-10-04: prah hloubky 900 mm jako promenna s textovym polem) -----------------------------------------------------------------
# app_settings `stul_pravidla` = JSON {"30": {"hloubka_stredni_profil": 900, ...}, "35": {...}, "40": {...}} (PO SYSTEMECH, jen hodnoty ruzne od vychozich; Robert 2026-10-05: "kazdemu
# systemu zadam hodnoty individualne"; starsi plochy tvar {"cena_vyrez": 2800.0} = tatez sada pro vsechny systemy); generator (stul_konfigurator.PRAVIDLA_SYSTEMU) je cista funkce, proto se hodnoty nactou pred kazdym pozadavkem na stul
# (cache PRAVIDLA_TTL_S, aby to nebyl dotaz do DB na kazde tahnuti jezdce). Chybna / nedostupna hodnota = zustane posledni platna (nikdy neshodi stul).
PRAVIDLA_KLIC = "stul_pravidla"
PRAVIDLA_TTL_S = 5.0
_PRAVIDLA_STAV = {"t": 0.0}


TABULE_KARTA_ID = 4933            # karta laminodesky stolu (shop_products): formaty tabule `board_sheet_width_mm` x `board_sheet_height_mm` (prazdne = vychozi 2070 x 2800 mm)


def pravidla_z_json(raw):
    """Ulozeny JSON (app_settings `stul_pravidla`) -> {system: {klic: cislo}} pro VSECHNY systemy. Dve podoby (stara ulozena data zustavaji platna): plochy slovnik {"cena_vyrez": 2800.0} (jedna sada
    pro vsechny systemy - stav do 2026-10-05) = tatez sada pro 30, 35 i 40; po systemech {"30": {...}, "35": {...}, "40": {...}} (chybejici system = vychozi hodnoty). Jine = ValueError."""
    d = json.loads(raw) if raw else {}
    if not isinstance(d, dict):
        raise ValueError("stul_pravidla musi byt objekt")
    nazvy = {str(x) for x in S.SYSTEMY}
    if d and all(str(k) in nazvy for k in d):
        if not all(isinstance(v, dict) for v in d.values()):
            raise ValueError("stul_pravidla po systemech: hodnota systemu musi byt objekt")
        return {int(k): v for k, v in d.items()}
    return {x: (dict(d) if x in S.SYSTEMY_PLOCHA else {}) for x in S.SYSTEMY}          # plochy tvar = jedna sada pro 30 / 35 / 40; SSE (od 2026-10-05) ho nededi - ma vlastni vychozi hodnoty


def obnov_pravidla(force=False):
    """Nacte pravidla stolu z app_settings do generatoru (S.PRAVIDLA_SYSTEMU, po systemech) a format tabule laminodesky z karty 4933 (S.nastav_tabuli). Bez force nejvyse jednou za PRAVIDLA_TTL_S."""
    ted = time.time()
    if not force and ted - _PRAVIDLA_STAV["t"] < PRAVIDLA_TTL_S:
        return
    _PRAVIDLA_STAV["t"] = ted
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                raw = get_setting(cur, PRAVIDLA_KLIC)
        finally:
            conn.close()
        S.nastav_pravidla_po_systemech(pravidla_z_json(raw))
    except Exception as e:                                           # noqa: BLE001 - stul nesmi zavisiet na tom, ze je nastaveni citelne
        app.logger.warning("stul: pravidla z app_settings se nepodarilo nacist: %s", e)
    try:                                                             # format tabule zvlast: jeho chyba nesmi vzit pravidla (a naopak); nenacteno / prazdno = vychozi
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT board_sheet_width_mm, board_sheet_height_mm FROM shop_products WHERE id=%s", (TABULE_KARTA_ID,))
                r = cur.fetchone()
        finally:
            conn.close()
        S.nastav_tabuli(*((r.get("board_sheet_width_mm"), r.get("board_sheet_height_mm")) if isinstance(r, dict) else (None, None)))
    except Exception as e:                                           # noqa: BLE001
        app.logger.warning("stul: format tabule z karty %s se nepodarilo nacist: %s", TABULE_KARTA_ID, e)


# Trasy, ktere stul pocitaji (generator, schema, kosik, objednavky, mini-shop): pravidla (cena vyrezu, prahy, format tabule) se nacitaji PRED trasou, kde jeste neni rozdelana zadna transakce
# (obnov_pravidla bere sdilene spojeni a jeho close() je rollback - nikdy ji nevolat uvnitr kosiku / objednavky; bot5 2026-10-05). TTL PRAVIDLA_TTL_S drzi zatez nizko.
_STUL_CESTY = ("/api/stul/", "/api/shop/configurator", "/api/shop/stul/", "/api/cart", "/api/orders", "/api/admin/orders/", "/api/miniweb/quote", "/api/miniweb/orders",
               "/api/admin/konfigurace/")        # nabidka a karta z konfigurace (bot5 / bot10): bez toho by v cerstvem workeru pocitaly hash, cenu i model s VYCHOZIMI prahy misto ulozenych pravidel (2026-10-08)


@app.before_request
def _stul_pravidla_pred_pozadavkem():
    cesta = request.path
    if cesta.startswith(_STUL_CESTY) or (cesta.startswith("/api/shop/products/") and "/configurator" in cesta):
        obnov_pravidla()


# ---- ULOZENE PROSTREDI (HDRI) GENERATORU (Robert 2026-10-04 + bot10: admin meni HDRI primo v generatoru, "nahled + ulozit pro vsechny") ------------------------------------------
# jedna konfigurace na generator (app_settings `configurator_env_<product_id>`, JSON {hdri, strength, rot_deg, hemi}); cte ji verejne schema (pole `env`), meni jen admin-only PUT (stul_shop).
# Hodnoty se tady KONTROLUJI znovu (stejne meze jako V3D.normalizeEnvConfig v prohlizeci - docs/VIEWER3D_SETMODEL.md), nic se neorezava potichu: mimo meze = chyba.
ENV_HDRI = ("crossfit", "tv_studio", "berg_inner", "teufelsberg", "mistnost")
ENV_MEZE = {"strength": (0.1, 3.0), "rot_deg": (-180.0, 180.0), "hemi": (0.0, 1.2)}
ENV_TTL_S = 5.0
_ENV_CACHE = {}


def env_over(cfg):
    """Zkontroluje konfiguraci prostredi a vrati normalizovany dict {hdri, strength, rot_deg, hemi} (cisla zaokrouhlena na 2 mista), nebo vyhodi ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("prostredi musi byt objekt {hdri, strength, rot_deg, hemi}")
    if set(cfg) - {"hdri", "strength", "rot_deg", "hemi"}:
        raise ValueError("prostredi: neznamy klic " + ", ".join(sorted(set(cfg) - {"hdri", "strength", "rot_deg", "hemi"})))
    if cfg.get("hdri") not in ENV_HDRI:
        raise ValueError("hdri musi byt jedno z: " + ", ".join(ENV_HDRI))
    out = {"hdri": cfg["hdri"]}
    for k, (lo, hi) in ENV_MEZE.items():
        v = cfg.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"{k} musi byt cislo")
        if not lo <= v <= hi:
            raise ValueError(f"{k} {v} je mimo rozsah {lo:g} az {hi:g}")
        out[k] = round(float(v), 2)
    return out


def env_klic(product_id):
    return f"configurator_env_{int(product_id)}"


def nacti_env(product_id, force=False):
    """Ulozene prostredi generatoru (dict) nebo None (= vychozi). Cache ENV_TTL_S; chybna ulozena hodnota = None (nikdy neshodi schema)."""
    pid = int(product_id)
    ted = time.time()
    c = _ENV_CACHE.get(pid)
    if c and not force and ted - c[0] < ENV_TTL_S:
        return c[1]
    cfg = None
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                raw = get_setting(cur, env_klic(pid))
        finally:
            conn.close()
        cfg = env_over(json.loads(raw)) if raw else None
    except Exception as e:                                           # noqa: BLE001
        app.logger.warning("stul: ulozene prostredi %s se nepodarilo nacist: %s", pid, e)
    _ENV_CACHE[pid] = (ted, cfg)
    return cfg


def uloz_env(product_id, cfg):
    """Ulozi (cfg = dict po env_over) nebo SMAZE (cfg = None) ulozene prostredi generatoru. Vraci ulozenou hodnotu / None."""
    cfg = env_over(cfg) if cfg is not None else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if cfg is None:
                cur.execute("DELETE FROM app_settings WHERE setting_key=%s", (env_klic(product_id),))
            else:
                val = json.dumps(cfg, sort_keys=True)
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (env_klic(product_id), val, val))
        conn.commit()
    finally:
        conn.close()
    _ENV_CACHE[int(product_id)] = (time.time(), cfg)
    return cfg


# ---- VYCHOZI KONFIGURACE GENERATORU (Robert 2026-10-05: "postav mi admin tlacitko v generatoru, kterym ulozim konfiguraci jako vychozi") ---------------------------------------------------
# app_settings `configurator_default_<product_id>` = JSON UPLNY vyber konfigurace (slot -> hodnota, normalizovany tak, jak ho vraci resolve). Pouzije se MISTO vestavenych vychozich hodnot jako
# `default_selection` verejneho schematu produktu (stranka stolu pro zamestnance, stranka produktu, mini-shop, embed - vsude, kde se generator otevre bez odkazu); meni a maze ho jen admin
# (PUT / DELETE /api/shop/products/<id>/configurator/default v stul_shop.py), schema ho jen cte. Vestavene hodnoty (stul_shop.vychozi_vyber) se NEMENI: jsou zaklad pro klice, ktere v ulozenem
# vyberu chybi (slot pridany pozdeji), a pro "vratit puvodni". Pravidlo jako u prostredi: chybna / nedostupna ulozena hodnota = vestavene vychozi (nikdy neshodi schema).
VYCHOZI_KLIC = "configurator_default_"
VYCHOZI_TTL_S = 5.0
VYCHOZI_MAX_KLICU = 200
_VYCHOZI_CACHE = {}


def vychozi_klic(product_id):
    return f"{VYCHOZI_KLIC}{int(product_id)}"


def vychozi_over(sel):
    """Zkontroluje ulozitelny vyber ({slot: bool | cislo | text | null}) a vrati jeho kopii, nebo vyhodi ValueError (nic se neorezava potichu)."""
    if not isinstance(sel, dict) or not sel:
        raise ValueError("vychozi konfigurace musi byt neprazdny objekt {slot: hodnota}")
    if len(sel) > VYCHOZI_MAX_KLICU:
        raise ValueError("vychozi konfigurace ma prilis mnoho poli")
    out = {}
    for k, v in sel.items():
        if not isinstance(k, str) or not re.fullmatch(r"[a-z0-9_]{1,40}", k):
            raise ValueError(f"neplatny nazev pole vychozi konfigurace: {k!r}")
        if v is not None and not isinstance(v, (bool, int, float, str)):
            raise ValueError(f"pole {k}: hodnota musi byt cislo, text, ano/ne nebo null")
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError(f"pole {k}: hodnota musi byt konecne cislo")
        if isinstance(v, str) and len(v) > 40:
            raise ValueError(f"pole {k}: text je prilis dlouhy")
        out[k] = v
    return out


def nacti_vychozi(product_id, force=False):
    """Ulozena vychozi konfigurace generatoru (dict slot -> hodnota) nebo None (= vestavene vychozi). Cache VYCHOZI_TTL_S; chybna ulozena hodnota = None (nikdy neshodi schema)."""
    pid = int(product_id)
    ted = time.time()
    c = _VYCHOZI_CACHE.get(pid)
    if c and not force and ted - c[0] < VYCHOZI_TTL_S:
        return dict(c[1]) if c[1] else None
    sel = None
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                raw = get_setting(cur, vychozi_klic(pid))
        finally:
            conn.close()
        sel = vychozi_over(json.loads(raw)) if raw else None
    except Exception as e:                                           # noqa: BLE001
        app.logger.warning("stul: ulozena vychozi konfigurace %s se nepodarilo nacist: %s", pid, e)
    _VYCHOZI_CACHE[pid] = (ted, sel)
    return dict(sel) if sel else None


def uloz_vychozi(product_id, sel):
    """Ulozi (sel = dict po vychozi_over) nebo SMAZE (sel = None) vychozi konfiguraci generatoru. Vraci ulozenou hodnotu / None; chyba DB vyhodi vyjimku."""
    sel = vychozi_over(sel) if sel is not None else None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if sel is None:
                cur.execute("DELETE FROM app_settings WHERE setting_key=%s", (vychozi_klic(product_id),))
            else:
                val = json.dumps(sel, sort_keys=True)
                cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (vychozi_klic(product_id), val, val))      # rowcount 0 = stejna hodnota uz tam je (platny stav)
        conn.commit()
    finally:
        conn.close()
    _VYCHOZI_CACHE[int(product_id)] = (time.time(), sel)
    return dict(sel) if sel else None


def _pravidla_odpoved(system=None):
    """Odpoved GET / PUT /api/stul/pravidla: `pravidla` = plochy slovnik pravidel systemu `system` (vychozi 30; podoba pro starsi klienty), `systemy` = pravidla VSECH systemu {"30": {...}, ...},
    `navlek_systemy` = systemy, ktere navlek maji (ceny navleku se jinde nezadavaji), `vychozi` a `rozsah` jsou spolecne."""
    sy = S.over_system(system) if system is not None else S.SYSTEM_VYCHOZI
    return {"pravidla": S.pravidla_systemu(sy), "system": sy, "systemy": {str(x): S.pravidla_systemu(x) for x in S.SYSTEMY}, "navlek_systemy": list(S.NAVLEK_SYSTEMY),
            "sse_systemy": [S.SYSTEM_SSE], "hluboke_systemy": [x for x in S.SYSTEMY if S.SYSTEMY[x].get("hluboky")], "vychozi": dict(S.PRAVIDLA_VYCHOZI), "vychozi_systemu": {str(x): S.pravidla_vychozi(x) for x in S.SYSTEMY},
            "rozsah": {k: list(v) for k, v in S.PRAVIDLA_ROZSAH.items()}}


@app.get("/api/stul/pravidla")
@admin_required
def stul_pravidla_get():
    """Pravidla stolu VIDI JEN ADMIN (Robert 2026-10-05: "tyto pravidla vidi jen admin")."""
    obnov_pravidla(force=True)
    try:
        return jsonify(_pravidla_odpoved(request.args.get("system")))
    except S.StulChyba as e:
        return jsonify({"error": str(e)}), 400


@app.put("/api/stul/pravidla")
@admin_required
def stul_pravidla_put():
    """Ulozi pravidla stolu JEN PRO JEDEN SYSTEM: telo {"system": 30|35|40, "pravidla": {klic: cislo}} (hloubka_stredni_profil, sirka_stredni_noha, vzpery_od_ramene, cena_vyrez, cena_navlek_200,
    cena_navlek_400); posilane klice se prepisou, ostatni zustanou; prazdna hodnota = vychozi hodnota toho klice. Hodnota mimo rozsah / neznamy klic / neznamy system = 400 (nic se neulozi).
    Starsi plochy telo {klic: cislo} (bez `system`) plati JEN dokud maji vsechny systemy stejna pravidla (pak se nastavi vsem); jinak 409 - stary formular by prepsal individualne zadane hodnoty.
    Uklada se jen to, co se lisi od vychoziho. Jen admin."""
    body = request.get_json(silent=True) or {}
    obnov_pravidla(force=True)
    novy_tvar = "system" in body or isinstance(body.get("pravidla"), dict)
    try:
        if novy_tvar:
            sy = S.over_system(body.get("system"))
            sada = S.pravidla_systemu(sy)
            for k, v in (body.get("pravidla") or {}).items():
                if k not in S.PRAVIDLA_VYCHOZI:
                    raise ValueError(f"neznamy klic pravidla: {k}")
                sada[k] = S.pravidla_vychozi(sy)[k] if v in (None, "") else v
            S.nastav_pravidla(sada, system=sy)                        # overeni (ValueError pri chybe); pri chybe se nic neulozi
        else:
            sady = [S.pravidla_systemu(x) for x in S.SYSTEMY_PLOCHA]            # starsi plochy formular zna jen systemy 30 / 35 / 40
            if any(x != sady[0] for x in sady[1:]):
                return jsonify({"error": "Pravidla jsou nastavena po systemech (30 / 35 / 40) - obnov stranku (Ctrl+F5) a zadej je pro kazdy system zvlast.", "code": "po_systemech"}), 409
            nova = dict(sady[0])
            for k, v in body.items():
                if k not in S.PRAVIDLA_VYCHOZI:
                    raise ValueError(f"neznamy klic pravidla: {k}")
                nova[k] = S.PRAVIDLA_VYCHOZI[k] if v in (None, "") else v
            for x in S.SYSTEMY_PLOCHA:
                S.nastav_pravidla(nova, system=x)                     # vsem systemum 30 / 35 / 40 (SSE si drzi svoje)
    except (ValueError, S.StulChyba) as e:
        obnov_pravidla(force=True)
        return jsonify({"error": str(e)}), 400
    uloz = {str(x): {k: v for k, v in S.pravidla_systemu(x).items() if v != S.pravidla_vychozi(x)[k]} for x in S.SYSTEMY}
    plocha = [uloz[str(x)] for x in S.SYSTEMY_PLOCHA]
    if all(v == plocha[0] for v in plocha) and not any(uloz[str(x)] for x in S.SYSTEMY if x not in S.SYSTEMY_PLOCHA):          # SSE i 45 maji vlastni sadu: bez zmen jen kdyz je nikdo nezadal
        uloz = plocha[0]                                              # systemy 30 / 35 / 40 stejne a SSE bez zmen (nikdo nic po systemech nezadal) = plochy tvar jako dosud (a jde zpet na starsi kod)
    else:
        uloz = {k: v for k, v in uloz.items() if v}                   # po systemech: system bez zmen se neuklada
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = json.dumps(uloz, sort_keys=True)
            cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=%s", (PRAVIDLA_KLIC, val, val))
        conn.commit()
    finally:
        conn.close()
    _PRAVIDLA_STAV["t"] = time.time()
    return jsonify(_pravidla_odpoved(body.get("system") if novy_tvar else None))


@app.get("/api/stul/konfigurace")
@staff_required
def stul_konfigurace():
    try:
        parametry = S.parametry_z_dotazu(request.args)
        out = S.odpoved(parametry)
        out["cena"] = cena_konfigurace(out["dily"], out["parametry"]["system"])
        out["vodici"] = stul_glb.vodici(parametry, out)
        out.pop("ovladani_scena", None)                      # surove souradnice generatoru; ve vodici.ovladani jsou v souradnicich GLB
        out["hash"] = stul_glb.kanonicky_hash(parametry)
        out["kod"] = "STL-" + out["hash"][:6].upper()
        out["rules_version"] = stul_glb.RULES_VERSION
        qs = request.query_string.decode("utf-8")
        out["model_url"] = "/api/stul/model.glb" + ("?" + qs if qs else "")
        return jsonify(out)
    except S.StulChyba as e:
        return jsonify({"error": str(e), "kod": e.kod}), 400


@app.get("/api/stul/model.glb")
@staff_required
def stul_model():
    """GLB konfigurace poskladany na serveru (jednotky mm, zploštělé uzly, bez odkazu na katalog). ZATIM jen zamestnanci;
    verejny pristup pres kratce platny odkaz = kontrakt konfiguratoru (docs/KONTRAKT_KONFIGURATOR_UI.md)."""
    try:
        h, data = stul_glb.model_pro_parametry(S.parametry_z_dotazu(request.args))
    except S.StulChyba as e:
        return jsonify({"error": str(e), "kod": e.kod}), 400
    except stul_glb.GlbChyba as e:
        app.logger.error("stul: model nelze poskladat: %s", e)
        return jsonify({"error": "Model se nepodarilo poskladat.", "kod": "model"}), 500
    data, kodovani = stul_glb.zakoduj_pro_klienta(h, data, request.headers.get("Accept-Encoding"))          # br / gzip (viz stul_glb.vyber_kodovani)
    resp = Response(data, mimetype="model/gltf-binary")
    if kodovani:
        resp.headers["Content-Encoding"] = kodovani
    resp.headers["Vary"] = "Accept-Encoding"
    resp.headers["ETag"] = '"' + h + ("-" + kodovani if kodovani else "") + '"'
    resp.headers["Cache-Control"] = "private, max-age=300"
    resp.headers["Content-Disposition"] = "inline"
    return resp
